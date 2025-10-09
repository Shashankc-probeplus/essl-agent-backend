"""
Multi-Device Stream Manager
Manages real-time event streaming from multiple ESSL devices

Architecture:
- One StreamManager instance per device
- Central coordinator manages all stream managers
- Can add/remove devices dynamically
- Each device streams independently
"""

import threading
from typing import Dict, List, Optional, Any
from datetime import datetime

from app.core.v1.stream_manager import StreamManager, StreamMode
from app.core.v1.device_pool import DevicePoolManager, DeviceInfo


# ==================== MULTI-DEVICE STREAM COORDINATOR ======================
class MultiDeviceStreamCoordinator:
    """
    Coordinates streaming from multiple devices.
    
    Features:
    - Manages multiple StreamManager instances (one per device)
    - Start/stop streaming for individual devices
    - Add/remove devices dynamically
    - Aggregate statistics from all streams
    """
    
    def __init__(
        self,
        device_pool: DevicePoolManager,
        server_url: str,
        server_endpoint: str = "/events/attendance",
        initial_sync_hours: int = 24
    ):
        """
        Initialize multi-device stream coordinator.
        
        Args:
            device_pool: DevicePoolManager instance
            server_url: Server URL for posting events
            server_endpoint: Endpoint path
            initial_sync_hours: Hours of history to sync per device
        """
        self.device_pool = device_pool
        self.server_url = server_url
        self.server_endpoint = server_endpoint
        self.initial_sync_hours = initial_sync_hours
        
        # Stream managers per device
        self.stream_managers: Dict[str, StreamManager] = {}
        
        # Coordinator lock
        self.lock = threading.Lock()
        
        print("🎛️  Multi-Device Stream Coordinator initialized")
    
    # ==================== DEVICE STREAMING CONTROL =========================
    
    def start_streaming_device(self, device_id: str) -> Dict[str, Any]:
        """
        Start streaming for a specific device.
        
        Args:
            device_id: Device identifier
            
        Returns:
            Start result
        """
        with self.lock:
            # Check if already streaming
            if device_id in self.stream_managers:
                return {
                    "success": False,
                    "message": f"Device {device_id} already streaming",
                    "device_id": device_id
                }
            
            # Get device info
            device_info = self.device_pool.get_device_info(device_id)
            if not device_info:
                return {
                    "success": False,
                    "error": f"Device {device_id} not found in pool",
                    "device_id": device_id
                }
            
            # Create stream manager for this device
            stream_manager = StreamManager(
                device_ip=device_info.device_ip,
                device_id=device_id,
                server_url=self.server_url,
                server_endpoint=self.server_endpoint,
                initial_sync_hours=self.initial_sync_hours
            )
            
            # Start streaming
            result = stream_manager.start()
            
            if result["success"]:
                self.stream_managers[device_id] = stream_manager
                print(f"✅ Started streaming for device: {device_id}")
            
            return result
    
    def stop_streaming_device(self, device_id: str) -> Dict[str, Any]:
        """
        Stop streaming for a specific device.
        
        Args:
            device_id: Device identifier
            
        Returns:
            Stop result
        """
        with self.lock:
            if device_id not in self.stream_managers:
                return {
                    "success": False,
                    "message": f"Device {device_id} not streaming",
                    "device_id": device_id
                }
            
            stream_manager = self.stream_managers[device_id]
            result = stream_manager.stop()
            
            if result["success"]:
                del self.stream_managers[device_id]
                print(f"🛑 Stopped streaming for device: {device_id}")
            
            return result
    
    def start_streaming_all(self) -> Dict[str, Any]:
        """
        Start streaming for all registered devices.
        
        Returns:
            Summary of results
        """
        devices = self.device_pool.get_active_devices()
        
        results = {
            "total": len(devices),
            "started": 0,
            "failed": 0,
            "details": []
        }
        
        for device in devices:
            device_id = device["device_id"]
            result = self.start_streaming_device(device_id)
            
            if result["success"]:
                results["started"] += 1
            else:
                results["failed"] += 1
            
            results["details"].append(result)
        
        print(f"📡 Started streaming: {results['started']}/{results['total']} devices")
        
        return results
    
    def stop_streaming_all(self) -> Dict[str, Any]:
        """
        Stop streaming for all devices.
        
        Returns:
            Summary of results
        """
        with self.lock:
            device_ids = list(self.stream_managers.keys())
        
        results = {
            "total": len(device_ids),
            "stopped": 0,
            "failed": 0,
            "details": []
        }
        
        for device_id in device_ids:
            result = self.stop_streaming_device(device_id)
            
            if result["success"]:
                results["stopped"] += 1
            else:
                results["failed"] += 1
            
            results["details"].append(result)
        
        print(f"🛑 Stopped streaming: {results['stopped']}/{results['total']} devices")
        
        return results
    
    # ==================== DEVICE MANAGEMENT ================================
    
    def add_device_and_stream(
        self,
        device_id: str,
        device_ip: str,
        port: int = 4370,
        name: Optional[str] = None,
        location: Optional[str] = None,
        auto_start_stream: bool = True
    ) -> Dict[str, Any]:
        """
        Add a new device and optionally start streaming.
        
        Args:
            device_id: Unique device identifier
            device_ip: Device IP address
            port: Device port
            name: Device name
            location: Device location
            auto_start_stream: Start streaming immediately
            
        Returns:
            Result dictionary
        """
        # Register device in pool
        register_result = self.device_pool.register_device(
            device_id=device_id,
            device_ip=device_ip,
            port=port,
            name=name,
            location=location
        )
        
        if not register_result["success"]:
            return register_result
        
        # Start streaming if requested
        if auto_start_stream:
            stream_result = self.start_streaming_device(device_id)
            return {
                "success": True,
                "message": f"Device added and streaming started",
                "device_id": device_id,
                "registration": register_result,
                "streaming": stream_result
            }
        
        return {
            "success": True,
            "message": f"Device added (streaming not started)",
            "device_id": device_id,
            "registration": register_result
        }
    
    def remove_device_and_stop_stream(self, device_id: str) -> Dict[str, Any]:
        """
        Remove device and stop its streaming.
        
        Args:
            device_id: Device identifier
            
        Returns:
            Result dictionary
        """
        # Stop streaming first
        stream_result = None
        if device_id in self.stream_managers:
            stream_result = self.stop_streaming_device(device_id)
        
        # Unregister from pool
        unregister_result = self.device_pool.unregister_device(device_id)
        
        return {
            "success": True,
            "message": f"Device removed and streaming stopped",
            "device_id": device_id,
            "streaming": stream_result,
            "unregistration": unregister_result
        }
    
    # ==================== STATUS & MONITORING ==============================
    
    def get_streaming_status(self, device_id: str) -> Optional[Dict[str, Any]]:
        """
        Get streaming status for specific device.
        
        Args:
            device_id: Device identifier
            
        Returns:
            Status dictionary or None if not streaming
        """
        with self.lock:
            stream_manager = self.stream_managers.get(device_id)
            if stream_manager:
                return stream_manager.get_status()
            return None
    
    def get_all_streaming_status(self) -> Dict[str, Any]:
        """
        Get streaming status for all devices.
        
        Returns:
            Aggregated status dictionary
        """
        with self.lock:
            statuses = {}
            for device_id, stream_manager in self.stream_managers.items():
                statuses[device_id] = stream_manager.get_status()
        
        # Aggregate statistics
        total_events = sum(
            status["statistics"]["total_events_sent"] 
            for status in statuses.values()
        )
        
        streaming_count = len(statuses)
        
        # Count by mode
        mode_counts = {}
        for status in statuses.values():
            mode = status["mode"]
            mode_counts[mode] = mode_counts.get(mode, 0) + 1
        
        return {
            "total_devices_streaming": streaming_count,
            "total_events_sent": total_events,
            "mode_breakdown": mode_counts,
            "devices": statuses
        }
    
    def get_coordinator_summary(self) -> Dict[str, Any]:
        """
        Get high-level summary of coordinator status.
        
        Returns:
            Summary dictionary
        """
        all_devices = self.device_pool.list_devices()
        streaming_status = self.get_all_streaming_status()
        
        return {
            "total_devices_registered": len(all_devices),
            "total_devices_streaming": streaming_status["total_devices_streaming"],
            "total_events_sent": streaming_status["total_events_sent"],
            "mode_breakdown": streaming_status["mode_breakdown"],
            "server_url": self.server_url,
            "server_endpoint": self.server_endpoint
        }
