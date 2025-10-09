"""
Stream Manager - Real-time attendance event streaming to server

Architecture:
1. Starts in SYNC mode - Sends all existing logs to server
2. Switches to LIVE mode - Listens for real-time punch events
3. Makes immediate API call to server for each event
4. Runs in background thread (non-blocking)
5. Has reconnection logic and error handling
"""

import threading
import time
import queue
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, Optional, List
from enum import Enum
import httpx
from app.core.v1.config import config

from app.core.v1.essl import ESSLDeviceCore, DeviceError


# ==================== CONFIGURATION ========================================
DEVICE_IP = "10.10.3.60"
DEVICE_ID = "device_001"  # Unique identifier for this device/agent
SERVER_URL = config.server_url  # Your main server URL
SERVER_ENDPOINT = "/events/attendance"  # Endpoint to POST events

# Stream Manager Settings
INITIAL_SYNC_HOURS = 24  # Send last 24 hours of logs on startup
MAX_RETRY_ATTEMPTS = 3
RETRY_DELAY_SECONDS = 5
EVENT_QUEUE_MAX_SIZE = 1000  # Max events to queue if server is down

IST = timezone(timedelta(hours=5, minutes=30))


# ==================== ENUMS ================================================
class StreamMode(Enum):
    """Stream manager operational modes"""
    INITIALIZING = "initializing"
    SYNCING = "syncing"         # Sending historical logs
    LIVE = "live"                # Listening for real-time events
    RECONNECTING = "reconnecting"
    STOPPED = "stopped"
    ERROR = "error"


class EventType(Enum):
    """Event types for server"""
    HISTORICAL = "historical"    # From initial sync
    REALTIME = "realtime"        # Live punch event


# ==================== STREAM MANAGER =======================================
class StreamManager:
    """
    Manages real-time attendance event streaming to server.
    
    Lifecycle:
    1. Initialize -> Connect to device
    2. Sync Mode -> Send all existing logs
    3. Live Mode -> Stream real-time events
    4. Handle errors -> Reconnect and retry
    """
    
    def __init__(
        self,
        device_ip: str,
        device_id: str,
        server_url: str,
        server_endpoint: str = "/events/attendance",
        initial_sync_hours: int = 24
    ):
        """
        Initialize stream manager.
        
        Args:
            device_ip: ESSL device IP address
            device_id: Unique identifier for this device
            server_url: Main server base URL
            server_endpoint: Endpoint to POST events
            initial_sync_hours: Hours of historical data to sync
        """
        self.device_ip = device_ip
        self.device_id = device_id
        self.server_url = server_url
        self.server_endpoint = server_endpoint
        self.initial_sync_hours = initial_sync_hours
        
        # Device core instance
        self.device = ESSLDeviceCore(device_ip)
        
        # State management
        self.mode = StreamMode.INITIALIZING
        self.is_running = False
        self.thread: Optional[threading.Thread] = None
        
        # Event queue for failed sends (retry mechanism)
        self.event_queue = queue.Queue(maxsize=EVENT_QUEUE_MAX_SIZE)
        
        # Statistics
        self.stats = {
            "total_events_sent": 0,
            "historical_events_sent": 0,
            "realtime_events_sent": 0,
            "failed_events": 0,
            "last_event_time": None,
            "started_at": None,
            "errors": []
        }
        
        # HTTP client (will be created in thread)
        self.http_client: Optional[httpx.Client] = None
    
    # ==================== LIFECYCLE METHODS ================================
    
    def start(self) -> Dict[str, Any]:
        """
        Start the stream manager in a background thread.
        
        Returns:
            Status dictionary
        """
        if self.is_running:
            return {
                "success": False,
                "message": "Stream manager already running",
                "mode": self.mode.value
            }
        
        self.is_running = True
        self.stats["started_at"] = int(time.time())
        
        # Start background thread
        self.thread = threading.Thread(target=self._run_loop, daemon=True)
        self.thread.start()
        
        print(f"🚀 Stream Manager started for device: {self.device_id}")
        print(f"📡 Server: {self.server_url}{self.server_endpoint}")
        
        return {
            "id": "",
            "agent_id": config.agent_id,
            "command": "start_stream",
            "mac_address": config.mac_address,
            "result": {
                "message": "Stream manager started successfully",
                "mode": self.mode.value
            },
            "device_ip": self.device_ip,
            "device_id": self.device_id,
            "success": True,
            "timestamp": int(time.time())
        }
    
    def stop(self) -> Dict[str, Any]:
        """
        Stop the stream manager gracefully.
        
        Returns:
            Status dictionary with final statistics
        """
        if not self.is_running:
            return {
                "success": False,
                "message": "Stream manager not running"
            }
        
        print("🛑 Stopping stream manager...")
        self.is_running = False
        self.mode = StreamMode.STOPPED
        
        # Wait for thread to finish
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=10)
        
        # Cleanup
        if self.http_client:
            self.http_client.close()
        
        self.device.disconnect()
        
        print("✅ Stream manager stopped")
        
        return {
            "id": "",
            "agent_id": config.agent_id,
            "command": "stop_stream",
            "mac_address": config.mac_address,
            "result": {
                "message": "Stream manager stopped",
                "statistics": self.stats
            },
            "device_ip": self.device_ip,
            "device_id": self.device_id,
            "success": True,
            "timestamp": int(time.time())
        }
    
    def get_status(self) -> Dict[str, Any]:
        """
        Get current status and statistics.
        
        Returns:
            Status dictionary
        """
        return {
            "id": "",
            "agent_id": config.agent_id,
            "command": "get_status",
            "mac_address": config.mac_address,
            "result": {
                "is_running": self.is_running,
                "mode": self.mode.value,
                "statistics": self.stats,
                "queue_size": self.event_queue.qsize()
            },
            "device_ip": self.device_ip,
            "device_id": self.device_id,
            "success": True,
            "timestamp": int(time.time())
        }
    
    # ==================== MAIN LOOP ========================================
    
    def _run_loop(self):
        """
        Main loop running in background thread.
        
        Flow:
        1. Initialize connection and HTTP client
        2. Sync historical logs
        3. Switch to live mode
        4. Listen for real-time events
        5. Handle errors and reconnect
        """
        # Create HTTP client for this thread
        self.http_client = httpx.Client(timeout=10.0)
        
        try:
            # Phase 1: Initial Sync
            self._sync_historical_logs()
            
            # Phase 2: Live Streaming
            self._live_stream_loop()
            
        except Exception as e:
            self.mode = StreamMode.ERROR
            self._log_error(f"Fatal error in stream loop: {e}")
            print(f"❌ Fatal error: {e}")
        
        finally:
            if self.http_client:
                self.http_client.close()
    
    # ==================== SYNC MODE ========================================
    
    def _sync_historical_logs(self):
        """
        Phase 1: Send all existing attendance logs to server.
        This runs once at startup.
        """
        if not self.is_running:
            return
        
        self.mode = StreamMode.SYNCING
        print(f"📦 Starting historical sync (last {self.initial_sync_hours} hours)...")
        
        try:
            # Connect to device
            self.device.connect()
            
            # Calculate time window
            cutoff_time = datetime.now(IST) - timedelta(hours=self.initial_sync_hours)
            
            # Get attendance logs
            logs = self.device.get_attendance(
                start_time=cutoff_time
            )
            
            print(f"📊 Found {len(logs)} historical logs to sync")
            
            # Send each log to server
            synced_count = 0
            for log in logs:
                if not self.is_running:
                    break
                
                success = self._send_event_to_server(
                    event_data=log,
                    event_type=EventType.HISTORICAL
                )
                
                if success:
                    synced_count += 1
                    self.stats["historical_events_sent"] += 1
                
                # Small delay to avoid overwhelming server
                time.sleep(0.1)
            
            print(f"✅ Historical sync complete: {synced_count}/{len(logs)} logs sent")
            
        except DeviceError as e:
            self._log_error(f"Device error during sync: {e}")
            print(f"❌ Sync failed: {e}")
        except Exception as e:
            self._log_error(f"Unexpected error during sync: {e}")
            print(f"❌ Sync error: {e}")
    
    # ==================== LIVE MODE ========================================
    
    def _live_stream_loop(self):
        """
        Phase 2: Listen for real-time events and stream to server.
        This runs continuously until stopped.
        """
        if not self.is_running:
            return
        
        self.mode = StreamMode.LIVE
        print("🎧 Switching to LIVE mode - Listening for real-time events...")
        
        while self.is_running:
            try:
                # Ensure device is connected
                if not self.device.conn:
                    self.device.connect()
                
                # Listen for live events using SDK's live_capture
                print("👂 Listening for punch events...")
                
                for attendance in self.device.conn.live_capture():
                    if not self.is_running:
                        break
                    
                    if attendance is None:
                        continue
                    
                    # Convert to dictionary format
                    event_data = self._format_attendance_event(attendance)
                    
                    print(f"⚡ Live event detected: {event_data.get('user_id')} at {event_data.get('timestamp')}")
                    
                    # Send to server immediately
                    success = self._send_event_to_server(
                        event_data=event_data,
                        event_type=EventType.REALTIME
                    )
                    
                    if success:
                        self.stats["realtime_events_sent"] += 1
                        print(f"✅ Event sent to server")
                    else:
                        print(f"❌ Failed to send event")
                
            except DeviceError as e:
                self._log_error(f"Device error in live mode: {e}")
                print(f"❌ Device error: {e}")
                self._reconnect()
            
            except Exception as e:
                self._log_error(f"Unexpected error in live mode: {e}")
                print(f"❌ Error: {e}")
                self._reconnect()
    
    # ==================== EVENT HANDLING ===================================
    
    def _send_event_to_server(
        self,
        event_data: Dict[str, Any],
        event_type: EventType
    ) -> bool:
        """
        Send attendance event to server via HTTP POST.
        
        Args:
            event_data: Attendance event data
            event_type: HISTORICAL or REALTIME
            
        Returns:
            True if successful, False otherwise
        """
        payload = {
            "device_id": self.device_id,
            "event_type": event_type.value,
            "event_data": event_data,
            "timestamp": int(time.time())
        }
        
        url = f"{self.server_url}{self.server_endpoint}"
        
        # Try to send with retries
        for attempt in range(1, MAX_RETRY_ATTEMPTS + 1):
            try:
                response = self.http_client.post(url, json=payload)
                
                if response.status_code in (200, 201, 204):
                    self.stats["total_events_sent"] += 1
                    self.stats["last_event_time"] = int(time.time())
                    return True
                else:
                    print(f"⚠️  Server returned status {response.status_code}")
                    if attempt < MAX_RETRY_ATTEMPTS:
                        time.sleep(RETRY_DELAY_SECONDS)
                        continue
                    
            except httpx.RequestError as e:
                print(f"⚠️  HTTP error (attempt {attempt}/{MAX_RETRY_ATTEMPTS}): {e}")
                if attempt < MAX_RETRY_ATTEMPTS:
                    time.sleep(RETRY_DELAY_SECONDS)
                    continue
        
        # All retries failed
        self.stats["failed_events"] += 1
        self._queue_failed_event(payload)
        return False
    
    def _queue_failed_event(self, payload: Dict[str, Any]):
        """
        Queue failed event for later retry.
        
        Args:
            payload: Event payload that failed to send
        """
        try:
            self.event_queue.put_nowait(payload)
            print(f"📥 Event queued for retry (queue size: {self.event_queue.qsize()})")
        except queue.Full:
            print(f"⚠️  Event queue full! Discarding event.")
            self._log_error("Event queue full - event discarded")
    
    def _format_attendance_event(self, attendance) -> Dict[str, Any]:
        """
        Convert raw attendance object to dictionary.
        
        Args:
            attendance: Raw attendance object from SDK
            
        Returns:
            Formatted event dictionary
        """
        timestamp = getattr(attendance, "timestamp", None)
        if isinstance(timestamp, datetime):
            timestamp = int(timestamp.replace(tzinfo=IST).astimezone(timezone.utc).timestamp())
        
        return {
            "user_id": getattr(attendance, "user_id", None),
            "timestamp": timestamp,
            "status": getattr(attendance, "status", None),
            "punch": getattr(attendance, "punch", None),
            "uid": getattr(attendance, "uid", None),
            "captured_at": int(time.time())
        }
    
    # ==================== ERROR HANDLING ===================================
    
    def _reconnect(self):
        """
        Handle reconnection to device after error.
        """
        self.mode = StreamMode.RECONNECTING
        print("🔄 Reconnecting to device...")
        
        # Disconnect if connected
        self.device.disconnect()
        
        # Wait before reconnect
        time.sleep(5)
        
        # Try to reconnect
        max_attempts = 3
        for attempt in range(1, max_attempts + 1):
            if not self.is_running:
                return
            
            try:
                print(f"🔌 Reconnect attempt {attempt}/{max_attempts}")
                self.device.connect()
                print("✅ Reconnected successfully")
                return
            except DeviceError as e:
                print(f"❌ Reconnect failed: {e}")
                if attempt < max_attempts:
                    time.sleep(10)
        
        print("❌ All reconnect attempts failed")
        self.mode = StreamMode.ERROR
    
    def _log_error(self, error_message: str):
        """
        Log error to statistics.
        
        Args:
            error_message: Error message to log
        """
        self.stats["errors"].append({
            "message": error_message,
            "timestamp": int(time.time())
        })
        
        # Keep only last 50 errors
        if len(self.stats["errors"]) > 50:
            self.stats["errors"] = self.stats["errors"][-50:]


