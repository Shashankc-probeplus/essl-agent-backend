"""
Device Pool Manager - Manages Multiple ESSL Devices Dynamically

Architecture:
- One agent handles multiple devices
- Devices can be added/removed dynamically
- Each device has its own core instance
- Connection pooling and lifecycle management
"""

from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
import time
import threading
from contextlib import contextmanager
import json
import os

from app.core.v1.essl import ESSLDeviceCore, DeviceError
from app.core.v1.config import config


IST = timezone(timedelta(hours=5, minutes=30))

DEFAULT_PORT = 4370
DEFAULT_PASSWORD = 0
DEFAULT_TIMEOUT = 10



@dataclass
class DeviceInfo:
    """
    Information about a managed device.
    """
    device_id: str              # Unique identifier (e.g., "device_001")
    device_ip: str              # IP address
    port: int = DEFAULT_PORT
    password: int = DEFAULT_PASSWORD
    timeout: int = DEFAULT_TIMEOUT
    
    # Metadata
    name: Optional[str] = None
    location: Optional[str] = None
    
    # Status
    is_active: bool = True
    last_seen: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "device_id": self.device_id,
            "device_ip": self.device_ip,
            "port": self.port,
            "name": self.name,
            "location": self.location,
            "is_active": self.is_active,
            "last_seen": self.last_seen
        }


# ==================== DEVICE POOL MANAGER ==================================
class DevicePoolManager:
    """
    Manages a pool of ESSL devices.
    
    Features:
    - Dynamic device registration/removal
    - Connection pooling per device
    - Thread-safe operations
    - Device health monitoring
    - Automatic cleanup of inactive devices
    """
    
    def __init__(self):
        """Initialize device pool manager."""
        self.devices: Dict[str, DeviceInfo] = {}
        self.device_cores: Dict[str, ESSLDeviceCore] = {}
        self.lock = threading.Lock()
        self.data_file = "data.json"
        
        # Load existing devices from file
        self._load_devices()
        
        print("🏊 Device Pool Manager initialized")
    
    # ==================== DEVICE REGISTRATION ==============================
    
    def register_device(
        self,
        device_id: str,
        device_ip: str,
        port: int = DEFAULT_PORT,
        password: int = DEFAULT_PASSWORD,
        name: Optional[str] = None,
        location: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Register a new device in the pool.
        
        Args:
            device_id: Unique device identifier
            device_ip: Device IP address
            port: Device port (default: 4370)
            password: Device password (default: 0)
            name: Human-readable name
            location: Physical location
            
        Returns:
            Registration result dictionary
        """
        with self.lock:
            if device_id in self.devices:
                return {
                    "success": False,
                    "message": f"Device {device_id} already registered",
                    "device_id": device_id
                }
            
            # ✅ FIX: Handle None values by using defaults
            actual_port = port if port is not None else DEFAULT_PORT
            actual_password = password if password is not None else DEFAULT_PASSWORD
            
            # Create device info
            device_info = DeviceInfo(
                device_id=device_id,
                device_ip=device_ip,
                port=actual_port,
                password=actual_password,
                name=name,
                location=location,
                is_active=True
            )
            
            # Create device core instance with guaranteed non-None values
            device_core = ESSLDeviceCore(
                device_ip=device_ip,
                port=actual_port,
                password=actual_password
            )
            
            # Store in pools
            self.devices[device_id] = device_info
            self.device_cores[device_id] = device_core
            
            # Save to file
            self._save_devices()
            
            print(f"✅ Registered device: {device_id} ({device_ip}:{actual_port})")
            
            return {
                "success": True,
                "message": f"Device {device_id} registered successfully",
                "device": device_info.to_dict()
            }
    
    def unregister_device(self, device_id: str) -> Dict[str, Any]:
        """
        Unregister a device from the pool.
        
        Args:
            device_id: Device identifier to remove
            
        Returns:
            Unregistration result
        """
        with self.lock:
            if device_id not in self.devices:
                return {
                    "success": False,
                    "message": f"Device {device_id} not found"
                }
            
            # Disconnect if connected
            if device_id in self.device_cores:
                try:
                    self.device_cores[device_id].disconnect()
                except Exception:
                    pass
                del self.device_cores[device_id]
            
            # Remove from registry
            del self.devices[device_id]
            
            # Save to file
            self._save_devices()
            
            print(f"🗑️  Unregistered device: {device_id}")
            
            return {
                "success": True,
                "message": f"Device {device_id} unregistered successfully"
            }
    
    def register_devices_bulk(
        self,
        devices: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Register multiple devices at once.
        
        Args:
            devices: List of device configuration dicts
            
        Returns:
            Bulk registration results
        """
        results = {
            "total": len(devices),
            "succeeded": 0,
            "failed": 0,
            "details": []
        }
        
        for device_config in devices:
            result = self.register_device(
                device_id=device_config.get("device_id"),
                device_ip=device_config.get("device_ip"),
                port=device_config.get("port", DEFAULT_PORT),
                password=device_config.get("password", DEFAULT_PASSWORD),
                name=device_config.get("name"),
                location=device_config.get("location")
            )
            
            if result["success"]:
                results["succeeded"] += 1
            else:
                results["failed"] += 1
            
            results["details"].append(result)
        
        return results
    
    # ==================== DEVICE ACCESS ====================================
    
    def get_device_core(self, device_id: str) -> Optional[ESSLDeviceCore]:
        """
        Get device core instance by device ID.
        
        Args:
            device_id: Device identifier
            
        Returns:
            ESSLDeviceCore instance or None if not found
        """
        with self.lock:
            return self.device_cores.get(device_id)
    
    def get_device_core_by_ip(self, device_ip: str) -> Optional[ESSLDeviceCore]:
        """
        Get device core instance by IP address.
        Creates temporary device core if IP not registered.
        
        Args:
            device_ip: Device IP address
            
        Returns:
            ESSLDeviceCore instance
        """
        with self.lock:
            # Try to find registered device with this IP
            for device_id, device_info in self.devices.items():
                if device_info.device_ip == device_ip:
                    return self.device_cores.get(device_id)
            
            # IP not registered - create temporary device core
            print(f"⚠️  Creating temporary device core for unregistered IP: {device_ip}")
            return ESSLDeviceCore(device_ip=device_ip)
    
    def get_device_info(self, device_id: str) -> Optional[DeviceInfo]:
        """
        Get device information.
        
        Args:
            device_id: Device identifier
            
        Returns:
            DeviceInfo or None if not found
        """
        with self.lock:
            return self.devices.get(device_id)
    
    def list_devices(self) -> List[Dict[str, Any]]:
        """
        List all registered devices.
        
        Returns:
            List of device info dictionaries
        """
        with self.lock:
            return [device.to_dict() for device in self.devices.values()]
    
    def get_active_devices(self) -> List[Dict[str, Any]]:
        """
        Get list of active devices.
        
        Returns:
            List of active device info dictionaries
        """
        with self.lock:
            return [
                device.to_dict() 
                for device in self.devices.values() 
                if device.is_active
            ]
    
    # ==================== DEVICE OPERATIONS ================================
    
    def execute_on_device(
        self,
        device_identifier: str,  # Can be device_id OR device_ip
        operation: str,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Execute an operation on a specific device.
        
        Args:
            device_identifier: Device ID or IP address
            operation: Operation name (e.g., "get_users", "unlock_door")
            **kwargs: Operation parameters
            
        Returns:
            Operation result dictionary
            
        Concept Explanation:
        - device_identifier is for ROUTING (which device to use)
        - kwargs are for the METHOD (what parameters the method needs)
        - We need to FILTER OUT routing info before calling the method
        """
        # Determine if identifier is ID or IP
        if device_identifier in self.devices:
            # It's a device ID
            device_core = self.get_device_core(device_identifier)
            device_id = device_identifier
        else:
            # Assume it's an IP address
            device_core = self.get_device_core_by_ip(device_identifier)
            device_id = device_identifier  # Use IP as ID in result
        
        if not device_core:
            return {
                "success": False,
                "error": f"Device {device_identifier} not found",
                "device_id": device_id
            }
        
        try:
            with device_core.connection():
                # Map operation name to method
                method = getattr(device_core, operation, None)
                
                if not method:
                    return {
                        "success": False,
                        "error": f"Unknown operation: {operation}",
                        "device_id": device_id
                    }
                
                # ✅ FIX: Remove routing parameters before calling method
                # These are used for routing, not method parameters
                routing_params = ['device_id', 'device_ip', 'agent_id']
                
                # Create clean kwargs with only method parameters
                method_kwargs = {
                    k: v for k, v in kwargs.items() 
                    if k not in routing_params
                }
                
                # Log what we're doing (helpful for debugging)
                print(f"🎯 Executing {operation} on device {device_id}")
                if method_kwargs:
                    print(f"   Parameters: {list(method_kwargs.keys())}")
                
                # Execute operation with cleaned parameters
                result = method(**method_kwargs)
                
                # Update last seen timestamp
                self._update_last_seen(device_id)
                
                return {
                    "success": True,
                    "device_id": device_id,
                    "operation": operation,
                    "result": result
                }
                
        except TypeError as e:
            # This catches parameter mismatch errors
            return {
                "success": False,
                "error": f"Parameter error: {str(e)}",
                "device_id": device_id,
                "operation": operation,
                "hint": "Check if method signature matches provided parameters"
            }
        except DeviceError as e:
            return {
                "success": False,
                "error": str(e),
                "device_id": device_id,
                "operation": operation
            }
        except Exception as e:
            return {
                "success": False,
                "error": f"Unexpected error: {str(e)}",
                "device_id": device_id,
                "operation": operation
            }
    
    def check_device_health(self, device_id: str) -> Dict[str, Any]:
        """
        Check health of a specific device.
        
        Args:
            device_id: Device identifier
            
        Returns:
            Health status dictionary with firmware info if available
        """
        device_core = self.get_device_core(device_id)
        device_info = self.get_device_info(device_id)
        
        if not device_core or not device_info:
            return {
                "device_id": device_id,
                "online": False,
                "error": "Device not found"
            }
        
        # Check if device is reachable at network level
        is_online = device_core.is_online()
        
        # Base health information
        health = {
            "device_id": device_id,
            "device_ip": device_info.device_ip,
            "online": is_online,
            "last_seen": device_info.last_seen
        }
        
        # If online, try to get detailed device information
        if is_online:
            try:
                with device_core.connection():
                    info = device_core.get_device_info()
                    
                    # Add firmware details to health
                    health.update({
                        "firmware": info.get("firmware"),
                        "platform": info.get("platform"),
                        "serial_number": info.get("serial_number"),
                        "device_time": info.get("device_time")
                    })
                    
                    # Update last seen timestamp
                    self._update_last_seen(device_id)
                    
            except DeviceError as e:
                # ✅ IMPROVEMENT: Log the error instead of silently passing
                error_msg = f"Device {device_id} online but failed to get info: {e}"
                print(f"⚠️  {error_msg}")
                
                # Add error to health dict for debugging
                health["connection_error"] = str(e)
                health["can_connect"] = False
                
            except Exception as e:
                # Catch unexpected errors
                error_msg = f"Unexpected error checking device {device_id}: {e}"
                print(f"❌ {error_msg}")
                health["unexpected_error"] = str(e)
        
        return health

    
    def check_all_devices_health(self) -> Dict[str, Any]:
        """
        Check health of all registered devices.
        
        Returns:
            Health status for all devices
        """
        health_results = []
        
        for device_id in self.devices.keys():
            health = self.check_device_health(device_id)
            health_results.append(health)
        
        online_count = sum(1 for h in health_results if h.get("online"))
        
        return {
            "total_devices": len(health_results),
            "online": online_count,
            "offline": len(health_results) - online_count,
            "devices": health_results
        }
    
    # ==================== HELPER METHODS ===================================
    
    def _update_last_seen(self, device_id: str):
        """Update last seen timestamp for device."""
        with self.lock:
            if device_id in self.devices:
                self.devices[device_id].last_seen = int(time.time())
    
    def cleanup_inactive_devices(self, inactive_hours: int = 24):
        """
        Remove devices that haven't been seen for specified hours.
        
        Args:
            inactive_hours: Hours of inactivity before removal
        """
        cutoff_epoch = int(time.time() - (inactive_hours * 3600))
        
        with self.lock:
            to_remove = []
            
            for device_id, device_info in self.devices.items():
                if device_info.last_seen and isinstance(device_info.last_seen, int):
                    if device_info.last_seen < cutoff_epoch:
                        to_remove.append(device_id)
            
            for device_id in to_remove:
                self.unregister_device(device_id)
                print(f"🧹 Cleaned up inactive device: {device_id}")
    
    def _save_devices(self):
        """Save devices to JSON file."""
        try:
            devices_data = {}
            for device_id, device_info in self.devices.items():
                devices_data[device_id] = device_info.to_dict()
            
            with open(self.data_file, 'w') as f:
                json.dump(devices_data, f, indent=2)
        except Exception as e:
            print(f"⚠️  Failed to save devices: {e}")
    
    def _load_devices(self):
        """Load devices from JSON file."""
        if not os.path.exists(self.data_file):
            return
        
        try:
            with open(self.data_file, 'r') as f:
                devices_data = json.load(f)
            
            for device_id, device_dict in devices_data.items():
                device_info = DeviceInfo(
                    device_id=device_dict['device_id'],
                    device_ip=device_dict['device_ip'],
                    port=device_dict.get('port', DEFAULT_PORT),
                    password=device_dict.get('password', DEFAULT_PASSWORD),
                    name=device_dict.get('name'),
                    location=device_dict.get('location'),
                    is_active=device_dict.get('is_active', True)
                )
                device_info.last_seen = device_dict.get('last_seen')
                
                device_core = ESSLDeviceCore(
                    device_ip=device_info.device_ip,
                    port=device_info.port,
                    password=device_info.password
                )
                
                self.devices[device_id] = device_info
                self.device_cores[device_id] = device_core
            
            print(f"📂 Loaded {len(self.devices)} devices from {self.data_file}")
        except Exception as e:
            print(f"⚠️  Failed to load devices: {e}")


# ==================== COMMAND HANDLER (MULTI-DEVICE) =======================
class MultiDeviceCommandHandler:
    """
    Command handler that routes commands to appropriate devices.
    Works with DevicePoolManager.
    """
    
    def __init__(self, device_pool: DevicePoolManager):
        """
        Initialize command handler.
        
        Args:
            device_pool: DevicePoolManager instance
        """
        self.device_pool = device_pool
    def _execute_management_command(self, command, params, command_id=""):
        try:
            result = {}
            if command == "register_device":
                # ✅ Call pool manager directly!
                result = self.device_pool.register_device(
                    device_id=params.get("device_id"),
                    device_ip=params.get("device_ip"),
                    port=params.get("port", DEFAULT_PORT),
                    password=params.get("password", DEFAULT_PASSWORD),
                    name=params.get("name"),
                    location=params.get("location")
                )
            
            elif command == "unregister_device":
                # ✅ Call pool manager directly!
                result = self.device_pool.unregister_device(params.get("device_id"))
            elif command == "list_devices":
                # ✅ Call pool manager directly!
                result = self.device_pool.list_devices()
            elif command == "device_health":
                print("🟢 Device health check requested")
                # ✅ Call pool manager directly!
                result = self.device_pool.check_device_health(params.get("device_id"))

            return {
                "id": command_id,
                "agent_id": config.agent_id,
                "command": command,
                "mac_address": config.mac_address,
                "result": result,
                "device_ip": params.get("device_ip", ""),
                "device_id": params.get("device_id", ""),
                "success": result.get("success", True),
                "timestamp": int(time.time())
            }

        except Exception as e:
            raise DeviceError(f"Failed to execute management command: {e}")

    def execute_command(self, command_data: Dict[str, Any]) -> Dict[str, Any]:

        id = command_data.get("id")
        command = command_data.get("command")
        params = command_data.get("params", {})
        
        # Handle management commands (agent-level)
        if command in ["register_device", "unregister_device", "list_devices", "device_health"]:
            return self._execute_management_command(command, params, id)
        
        # Get device identifier
        device_identifier = (
            command_data.get("device_id") or 
            command_data.get("device_ip")
        )
        
        if not device_identifier:
            return {
                "id": id,
                "agent_id": config.agent_id,
                "command": command,
                "mac_address": config.mac_address,
                "result": {"error": "Missing device_id or device_ip in command"},
                "device_ip": "",
                "device_id": "",
                "success": False,
                "timestamp": int(time.time())
            }
        
        if not command:
            return {
                "id": id,
                "agent_id": config.agent_id,
                "command": command,
                "mac_address": config.mac_address,
                "result": {"error": "Missing command in request"},
                "device_ip": "",
                "device_id": device_identifier,
                "success": False,
                "timestamp": int(time.time())
            }
        
        # Extended command map with sync commands
        command_map = {
            # User management
            "get_users": "get_users",
            "create_user": "create_user",
            "update_user": "update_user",
            "delete_user": "delete_user",
            
            # Attendance
            "get_attendance": "get_attendance",
            
            # Device info
            "get_device_info": "get_device_info",
        }
        
        operation = command_map.get(command)
        
        if not operation:
            return {
                "id": id,
                "agent_id": config.agent_id,
                "command": command,
                "mac_address": config.mac_address,
                "result": {"error": f"Unknown command: {command}"},
                "device_ip": "",
                "device_id": device_identifier,
                "success": False,
                "timestamp": int(time.time())
            }
        
        # Special handling for get_attendance with time filters
        if command == "get_attendance":
            # Extract time filters from params
            start_time = params.get("start_time")  # Unix timestamp
            end_time = params.get("end_time")      # Unix timestamp
            limit = params.get("limit", 1000)
            
            # Convert timestamps to datetime if provided
            from datetime import datetime, timezone
            
            if start_time:
                params["start_time"] = datetime.fromtimestamp(start_time, tz=timezone.utc)
            if end_time:
                params["end_time"] = datetime.fromtimestamp(end_time, tz=timezone.utc)
            
            params["limit"] = limit
        
        # Execute on device
        result = self.device_pool.execute_on_device(
            device_identifier=device_identifier,
            operation=operation,
            **params
        )
        
        # ✅ FIX: Ensure result is always a dictionary
        operation_result = result.get("result", result)
        
        # Wrap list results in dictionaries
        if isinstance(operation_result, list):
            # Determine which type of list based on command
            if command == "get_users":
                formatted_result = {
                    "users": operation_result,
                    "count": len(operation_result)
                }
            elif command == "get_attendance":
                formatted_result = {
                    "logs": operation_result,
                    "count": len(operation_result)
                }
            else:
                # Generic list wrapper
                formatted_result = {
                    "items": operation_result,
                    "count": len(operation_result)
                }
        elif isinstance(operation_result, dict):
            # Already a dict, use as-is
            formatted_result = operation_result
        else:
            # Primitive type (string, int, etc.) - wrap it
            formatted_result = {
                "value": operation_result
            }
        
        # Format response
        return {
            "id": id,
            "agent_id": config.agent_id,
            "command": command,
            "mac_address": config.mac_address,
            "result": formatted_result,  # ✅ Always a dict now!
            "device_ip": self.device_pool.devices.get(
                device_identifier, 
                DeviceInfo("", device_identifier)
            ).device_ip,
            "device_id": device_identifier,
            "success": result.get("success", True),
            "timestamp": int(time.time())
        }