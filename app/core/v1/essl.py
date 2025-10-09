"""
ESSL Device Core Layer - Handles ALL device communication
This layer is independent of FastAPI and can be used by:
- API Routes
- Background Polling Service
- Command Handlers
- CLI Tools
"""

from datetime import datetime, timezone, timedelta
import time
from typing import List, Dict, Optional, Any
import base64
from contextlib import contextmanager

try:
    from zk import ZK, const
except ImportError:
    raise RuntimeError("Install pyzk: pip install pyzk")


# ==================== CORE DEVICE CLASS ====================================
class ESSLDeviceCore:
    """
    Core layer for ESSL device communication.
    """
    
    def __init__(
        self,
        device_ip: str,
        port: int = 4370,
        password: int = 0,
        timeout: int = 10,
        force_udp: bool = False
    ):
        """
        Initialize device core with connection parameters.
        
        Args:
            device_ip: IP address of ESSL device
            port: Device port (default: 4370)
            password: Device communication key (default: 0)
            timeout: Connection timeout in seconds
            force_udp: Force UDP protocol instead of TCP
        """
        self.device_ip = device_ip
        self.port = port
        self.password = password
        self.timeout = timeout
        self.force_udp = force_udp
        
        self.zk = None
        self.conn = None
        self.ist = timezone(timedelta(hours=5, minutes=30))
    
    # ==================== CONNECTION MANAGEMENT ============================
    
    def connect(self) -> None:
        """
        Establish connection to device.
        Raises DeviceError if connection fails.
        """
        if self.conn:
            return  # Already connected
        
        try:
            # ✅ FIX: Validate parameters before using them
            if self.port is None:
                raise DeviceError(f"Port is None for device {self.device_ip}")
            
            if self.password is None:
                raise DeviceError(f"Password is None for device {self.device_ip}")
            
            if self.timeout is None:
                raise DeviceError(f"Timeout is None for device {self.device_ip}")
            
            # Convert to int safely
            port_int = int(self.port)
            password_int = int(self.password)
            timeout_int = int(self.timeout)
            
            # Log connection attempt
            print(f"🔌 Connecting to {self.device_ip}:{port_int} (password={password_int}, timeout={timeout_int}s)")
            
            self.zk = ZK(
                self.device_ip,
                port=port_int,
                password=password_int,
                timeout=timeout_int,
                force_udp=self.force_udp,
                ommit_ping=False
            )
            
            self.conn = self.zk.connect()
            print(f"✅ Connected to {self.device_ip}:{port_int}")
            
        except ValueError as e:
            # Catch conversion errors
            raise DeviceError(f"Invalid parameter value for {self.device_ip}:{self.port} - {e}")
        except Exception as e:
            raise DeviceError(f"Failed to connect to {self.device_ip}:{self.port} - {e}")
    
    def disconnect(self) -> None:
        """Safely disconnect from device."""
        if self.conn:
            try:
                self.conn.disconnect()
            except Exception:
                pass
            finally:
                self.conn = None
                self.zk = None
    
    @contextmanager
    def connection(self):
        """
        Context manager for automatic connection handling.
        
        Usage:
            device = ESSLDeviceCore("10.10.3.60")
            with device.connection():
                users = device.get_users()
        """
        try:
            self.connect()
            yield self
        finally:
            self.disconnect()
    
    def _ensure_connected(self):
        """Internal helper to ensure we have active connection."""
        if not self.conn:
            raise DeviceError("Not connected to device. Call connect() first.")
    
    # ==================== DEVICE HEALTH & INFO =============================
    
    def get_device_info(self) -> Dict[str, Any]:
        """
        Get comprehensive device information.
        
        Returns:
            Dict with firmware, platform, serial, time, etc.
        """
        self._ensure_connected()
        
        try:
            return {
                "ip": self.device_ip,
                "port": self.port,
                "firmware": self.conn.get_firmware_version(),
                "platform": self.conn.get_platform(),
                "serial_number": self.conn.get_serialnumber(),
                "device_time": self._format_datetime(self.conn.get_time()),
            }
        except Exception as e:
            raise DeviceError(f"Failed to get device info: {e}")
    
    def get_device_status(self) -> Dict[str, Any]:
        """
        Get device status with counts.
        
        Returns:
            Dict with online status, user count, attendance count
        """
        self._ensure_connected()
        
        try:
            users = self.conn.get_users() or []
            attendance = self.conn.get_attendance() or []
            
            return {
                "online": True,
                "firmware": self.conn.get_firmware_version(),
                "platform": self.conn.get_platform(),
                "users_count": len(users),
                "attendance_count": len(attendance),
                "timestamp": int(time.time()),
            }
        except Exception as e:
            raise DeviceError(f"Failed to get device status: {e}")
    
    def is_online(self) -> bool:
        """Quick check if device is reachable."""
        import socket
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(3)
        try:
            s.connect((self.device_ip, int(self.port)))
            return True
        except Exception as e:
            print(f"❌ Connection to {self.device_ip}:{self.port} failed: {e}")
            return False
        finally:
            try:
                s.close()
            except Exception:
                pass
    
    # ==================== USER MANAGEMENT ==================================
    
    def get_users(self) -> List[Dict[str, Any]]:
        """
        Get all users from device.
        
        Returns:
            List of user dictionaries with uid, user_id, name, privilege, card
        """
        self._ensure_connected()
        
        try:
            raw_users = self.conn.get_users() or []
            users = []
            
            for user in raw_users:
                user_dict = {
                    "uid": getattr(user, "uid", None),
                    "user_id": self._decode_bytes(getattr(user, "user_id", None)),
                    "name": self._decode_bytes(getattr(user, "name", None)),
                    "privilege": getattr(user, "privilege", None),
                    "card": self._format_card(getattr(user, "card", None)),
                    "password": getattr(user, "password", None),
                }
                users.append(user_dict)
            
            return users
        except Exception as e:
            raise DeviceError(f"Failed to get users: {e}")
    
    def get_user_by_uid(self, uid: int) -> Optional[Dict[str, Any]]:
        """Get specific user by UID."""
        users = self.get_users()
        for user in users:
            if user["uid"] == uid:
                return user
        return None
    
    def create_user(
        self,
        user_id: str,
        name: str,
        privilege: int = 0,
        password: Optional[str] = None,
        card: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Create new user on device.
        
        Args:
            user_id: Unique user identifier
            name: Display name
            privilege: 0=Normal User, 14=Admin
            password: Optional numeric password
            card: Optional RFID card number
            
        Returns:
            Dict with success status and assigned UID
        """
        self._ensure_connected()
        
        try:
            # Check if user_id already exists
            existing_users = self.get_users()
            if any(u["user_id"] == user_id for u in existing_users):
                raise DeviceError(f"User ID '{user_id}' already exists")
            
            # Auto-generate UID
            if existing_users:
                max_uid = max(u["uid"] for u in existing_users if u["uid"])
                next_uid = max_uid + 1
            else:
                next_uid = 1
            
            # Create user on device
            self.conn.set_user(
                uid=next_uid,
                user_id=user_id,
                name=name,
                privilege=privilege,
                password=password or "",
                card=card
            )
            
            return {
                "success": True,
                "message": f"User {user_id} created successfully",
                "uid": next_uid,
                "user_id": user_id
            }
        except DeviceError:
            raise
        except Exception as e:
            raise DeviceError(f"Failed to create user: {e}")
    
    def update_user(
        self,
        uid: int,
        name: Optional[str] = None,
        privilege: Optional[int] = None,
        password: Optional[str] = None,
        card: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Update existing user. If a field is not provided,
        retain the existing value from the device.

        Args:
            uid: User UID to update
            name: New name (optional)
            privilege: New privilege level (optional)
            password: New password (optional)
            card: New card number (optional)

        Returns:
            Success status dict
        """
        self._ensure_connected()

        try:
            # 🔹 Step 1: Get existing user info
            users = self.conn.get_users()
            existing_user = next((u for u in users if u.uid == uid), None)

            if not existing_user:
                raise DeviceError(f"User with UID {uid} not found on device")

            # 🔹 Step 2: Keep previous values if not provided
            updated_name = name if name is not None else existing_user.name
            updated_privilege = privilege if privilege is not None else existing_user.privilege
            updated_password = password if password is not None else existing_user.password
            updated_card = card if card is not None else existing_user.card

            # 🔹 Step 3: Update user with merged data
            self.conn.set_user(
                uid=uid,
                user_id=existing_user.user_id,  # keep same user_id
                name=updated_name,
                privilege=updated_privilege,
                password=updated_password,
                card=updated_card
            )

            return {
                "success": True,
                "message": f"User {uid} updated successfully"
            }

        except Exception as e:
            raise DeviceError(f"Failed to update user: {e}")

    
    def delete_user(self, uid: int) -> Dict[str, Any]:
        """
        Delete user from device.
        
        Args:
            uid: User UID to delete
            
        Returns:
            Success status dict
        """
        self._ensure_connected()
        
        try:
            self.conn.delete_user(uid=uid)
            return {
                "success": True,
                "message": f"User {uid} deleted successfully"
            }
        except Exception as e:
            raise DeviceError(f"Failed to delete user: {e}")
    
    # ==================== ATTENDANCE OPERATIONS ============================
    
    def get_attendance(
        self,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        user_id: Optional[str] = None,
        limit: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Get attendance records with optional filters.
        
        Args:
            start_time: Filter records after this time
            end_time: Filter records before this time
            user_id: Filter by specific user
            limit: Maximum number of records
            
        Returns:
            List of attendance record dictionaries
        """
        self._ensure_connected()
        
        try:
            raw_logs = self.conn.get_attendance() or []
            logs = []
            
            for log in raw_logs:
                log_dict = {
                    "user_id": getattr(log, "user_id", None),
                    "timestamp": self._format_datetime(getattr(log, "timestamp", None)),
                    "status": getattr(log, "status", None),
                    "punch": getattr(log, "punch", None),
                    "uid": getattr(log, "uid", None),
                }
                logs.append(log_dict)
            
            # Apply filters
            if start_time:
                start_epoch = int(start_time.astimezone(timezone.utc).timestamp())
                logs = [l for l in logs if l["timestamp"] and l["timestamp"] >= start_epoch]
            if end_time:
                end_epoch = int(end_time.astimezone(timezone.utc).timestamp())
                logs = [l for l in logs if l["timestamp"] and l["timestamp"] <= end_epoch]
            if user_id:
                logs = [l for l in logs if l["user_id"] == user_id]
            
            # Sort by timestamp (newest first)
            logs.sort(key=lambda x: x["timestamp"] or 0, reverse=True)
            
            if limit:
                logs = logs[:limit]
            
            return logs
        except Exception as e:
            raise DeviceError(f"Failed to get attendance: {e}")
    
    def clear_attendance(self) -> Dict[str, Any]:
        """
        Clear all attendance logs from device.
        
        Returns:
            Success status dict
        """
        self._ensure_connected()
        
        try:
            self.conn.clear_attendance()
            return {
                "success": True,
                "message": "Attendance logs cleared successfully"
            }
        except Exception as e:
            raise DeviceError(f"Failed to clear attendance: {e}")
    
    # ==================== ACCESS CONTROL ===================================
    
    def unlock_door(self, seconds: int = 5) -> Dict[str, Any]:
        """
        Unlock door for specified duration.
        
        Args:
            seconds: Duration to keep door unlocked (1-60)
            
        Returns:
            Success status dict
        """
        self._ensure_connected()
        
        if not 1 <= seconds <= 60:
            raise DeviceError("Unlock duration must be between 1-60 seconds")
        
        try:
            self.conn.unlock(int(seconds))
            return {
                "success": True,
                "seconds": seconds,
                "message": f"Door unlocked for {seconds} seconds"
            }
        except Exception as e:
            raise DeviceError(f"Failed to unlock door: {e}")
    
    # ==================== DEVICE CONTROL ===================================
    
    def restart_device(self) -> Dict[str, Any]:
        """
        Restart the device.
        
        Returns:
            Success status dict
        """
        self._ensure_connected()
        
        try:
            self.conn.restart()
            return {
                "success": True,
                "message": "Device restart initiated"
            }
        except Exception as e:
            raise DeviceError(f"Failed to restart device: {e}")
    
    def set_device_time(self, new_time: datetime) -> Dict[str, Any]:
        """
        Set device clock time.
        
        Args:
            new_time: New datetime to set
            
        Returns:
            Success status dict
        """
        self._ensure_connected()
        
        try:
            self.conn.set_time(new_time)
            return {
                "success": True,
                "set_time": int(new_time.astimezone(timezone.utc).timestamp()),
                "message": "Device time updated successfully"
            }
        except Exception as e:
            raise DeviceError(f"Failed to set device time: {e}")
    
    # ==================== TEMPLATES & BIOMETRICS ===========================
    
    def get_templates(self) -> List[Dict[str, Any]]:
        """
        Get all biometric templates from device.
        
        Returns:
            List of template dictionaries with Base64 encoded data
        """
        self._ensure_connected()
        
        try:
            raw_templates = self.conn.get_templates() or []
            templates = []
            
            for template in raw_templates:
                if hasattr(template, 'template') and template.template:
                    template_dict = {
                        "uid": getattr(template, "uid", None),
                        "fid": getattr(template, "fid", None),
                        "template_data": base64.b64encode(template.template).decode('utf-8'),
                        "template_size": len(template.template)
                    }
                    templates.append(template_dict)
            
            return templates
        except Exception as e:
            raise DeviceError(f"Failed to get templates: {e}")
    
    def save_template(self, uid: int, fid: int, template_data: str) -> Dict[str, Any]:
        """
        Save biometric template to device.
        
        Args:
            uid: User UID
            fid: Finger/Face ID
            template_data: Base64 encoded template data
            
        Returns:
            Success status dict
        """
        self._ensure_connected()
        
        try:
            template_bytes = base64.b64decode(template_data)
            self.conn.save_user_template(uid=uid, fid=fid, template=template_bytes)
            
            return {
                "success": True,
                "message": f"Template saved for user {uid}, finger {fid}",
                "template_size": len(template_bytes)
            }
        except Exception as e:
            raise DeviceError(f"Failed to save template: {e}")

    def _decode_bytes(self, value: Any) -> Optional[str]:
        """Convert bytes to string, handle encoding."""
        if isinstance(value, bytes):
            return value.decode(errors="ignore").strip() or None
        return str(value) if value is not None else None
    
    def _format_card(self, card: Any) -> Optional[str]:
        """Format card number, return None for empty values."""
        if card in (None, 0, "0", ""):
            return None
        return str(card)
    
    def _format_datetime(self, dt: Any) -> Optional[int]:
        """Format datetime to epoch GMT integer."""
        if isinstance(dt, datetime):
            return int(dt.replace(tzinfo=self.ist).astimezone(timezone.utc).timestamp())
        return None


class DeviceError(Exception):
    """Custom exception for device-related errors."""
    pass

