from fastapi import FastAPI
from contextlib import asynccontextmanager
import asyncio

from app.core.v1.device_pool import DevicePoolManager
from app.core.v1.stream import MultiDeviceStreamCoordinator  # ← NEW IMPORT
from app.service.polling import PollingService
from app.core.v1.config import config  # ← NEW IMPORT (for server_url)

# Global instances
device_pool = None
polling_service = None
stream_coordinator = None  # ← NEW: Stream coordinator instance


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan manager.
    
    Lifecycle:
    1. STARTUP: Initialize all services and start them
    2. RUNNING: Application handles requests
    3. SHUTDOWN: Gracefully stop all services
    """
    # ==================== STARTUP ====================
    global device_pool, polling_service, stream_coordinator
    
    print("🚀 Starting application services...")
    
    # Step 1: Initialize device pool (must be first - others depend on it)
    device_pool = DevicePoolManager()
    print("✅ Device pool initialized")
    
    # Step 2: Initialize stream coordinator (depends on device_pool)
    stream_coordinator = MultiDeviceStreamCoordinator(
        device_pool=device_pool,
        server_url=config.server_url,  # Your server URL from config
        server_endpoint="/api/v1/events/attendance",  # Endpoint where logs are sent
        initial_sync_hours=24  # Sync last 24 hours of logs on startup
    )
    print("✅ Stream coordinator initialized")
    
    # Step 3: Start streaming for ALL existing devices
    # This is critical! Without this, devices won't stream even if registered
    existing_devices = device_pool.list_devices()
    if existing_devices:
        print(f"📡 Starting streaming for {len(existing_devices)} registered devices...")
        stream_result = stream_coordinator.start_streaming_all()
        print(f"   ✅ Streaming started for {stream_result['started']}/{stream_result['total']} devices")
        
        if stream_result['failed'] > 0:
            print(f"   ⚠️  Failed to start streaming for {stream_result['failed']} devices")
    else:
        print("ℹ️  No devices registered yet. Register devices to start streaming.")
    
    # Step 4: Initialize polling service (polls server for commands)
    polling_service = PollingService(
        device_pool=device_pool,
        poll_interval=10
    )
    print("✅ Polling service initialized")
    
    # Step 5: Start polling in background
    asyncio.create_task(polling_service.start())
    print("✅ Polling service started")
    
    print("=" * 60)
    print("🎉 ALL SERVICES STARTED SUCCESSFULLY")
    print("=" * 60)
    
    yield  # ← Application runs here
    
    # ==================== SHUTDOWN ====================
    print("\n🛑 Shutting down application services...")
    
    # Stop streaming first (cleanly disconnect from devices)
    if stream_coordinator:
        print("📡 Stopping all streaming...")
        stream_coordinator.stop_streaming_all()
        print("✅ Streaming stopped")
    
    # Stop polling service
    if polling_service:
        print("🔄 Stopping polling service...")
        polling_service.stop()
        print("✅ Polling stopped")
    
    print("=" * 60)
    print("✅ ALL SERVICES STOPPED SUCCESSFULLY")
    print("=" * 60)


app = FastAPI(
    title="ESSL Device Agent",
    description="Multi-device ESSL agent with streaming and polling",
    version="1.0.0",
    lifespan=lifespan
)


# ==================== EXISTING ENDPOINTS ====================

@app.get("/polling/status")
async def get_polling_status():
    """Get polling service status and statistics."""
    if polling_service:
        return polling_service.get_status()
    return {"error": "Polling service not initialized"}


@app.post("/polling/stop")
async def stop_polling():
    """Stop the polling service."""
    if polling_service:
        polling_service.stop()
        return {"success": True, "message": "Polling stopped"}
    return {"error": "Polling service not initialized"}


# ==================== NEW STREAMING ENDPOINTS ====================

@app.get("/streaming/status")
async def get_streaming_status():
    """
    Get overall streaming status for all devices.
    
    Returns:
    - Total devices streaming
    - Total events sent
    - Per-device streaming status
    """
    if stream_coordinator:
        return stream_coordinator.get_all_streaming_status()
    return {"error": "Stream coordinator not initialized"}


@app.get("/streaming/status/{device_id}")
async def get_device_streaming_status(device_id: str):
    """
    Get streaming status for a specific device.
    
    Args:
        device_id: The device identifier
    """
    if stream_coordinator:
        status = stream_coordinator.get_streaming_status(device_id)
        if status:
            return status
        return {"error": f"Device {device_id} is not streaming"}
    return {"error": "Stream coordinator not initialized"}


@app.post("/streaming/start/{device_id}")
async def start_device_streaming(device_id: str):
    """
    Start streaming for a specific device.
    
    Use this when:
    - A new device is registered and you want to start streaming
    - Streaming was stopped and you want to restart it
    
    Args:
        device_id: The device identifier
    """
    if stream_coordinator:
        result = stream_coordinator.start_streaming_device(device_id)
        return result
    return {"error": "Stream coordinator not initialized"}


@app.post("/streaming/stop/{device_id}")
async def stop_device_streaming(device_id: str):
    """
    Stop streaming for a specific device.
    
    Args:
        device_id: The device identifier
    """
    if stream_coordinator:
        result = stream_coordinator.stop_streaming_device(device_id)
        return result
    return {"error": "Stream coordinator not initialized"}


@app.post("/streaming/start-all")
async def start_all_streaming():
    """
    Start streaming for ALL registered devices.
    
    Useful for:
    - Restarting all streams after maintenance
    - Starting streams for newly registered devices
    """
    if stream_coordinator:
        result = stream_coordinator.start_streaming_all()
        return result
    return {"error": "Stream coordinator not initialized"}


@app.post("/streaming/stop-all")
async def stop_all_streaming():
    """Stop streaming for all devices."""
    if stream_coordinator:
        result = stream_coordinator.stop_streaming_all()
        return result
    return {"error": "Stream coordinator not initialized"}


@app.get("/streaming/summary")
async def get_streaming_summary():
    """
    Get high-level summary of streaming system.
    
    Returns:
    - Total registered devices
    - Total devices currently streaming
    - Total events sent
    - Mode breakdown (sync/live)
    """
    if stream_coordinator:
        return stream_coordinator.get_coordinator_summary()
    return {"error": "Stream coordinator not initialized"}


# ==================== DEVICE MANAGEMENT ENDPOINTS ====================

@app.get("/devices")
async def list_devices():
    """List all registered devices."""
    if device_pool:
        return {"devices": device_pool.list_devices()}
    return {"error": "Device pool not initialized"}


@app.get("/devices/active")
async def list_active_devices():
    """List only active devices."""
    if device_pool:
        return {"devices": device_pool.get_active_devices()}
    return {"error": "Device pool not initialized"}


@app.get("/health")
async def health_check():
    """
    Complete health check of the application.
    
    Checks:
    - Polling service status
    - Streaming coordinator status
    - Device pool status
    """
    health = {
        "status": "healthy",
        "services": {}
    }
    
    # Check polling service
    if polling_service:
        poll_status = polling_service.get_status()
        health["services"]["polling"] = {
            "status": "running" if poll_status["result"]["is_running"] else "stopped",
            "stats": poll_status["result"]["statistics"]
        }
    
    # Check streaming
    if stream_coordinator:
        stream_summary = stream_coordinator.get_coordinator_summary()
        health["services"]["streaming"] = {
            "status": "active",
            "devices_streaming": stream_summary["total_devices_streaming"],
            "events_sent": stream_summary["total_events_sent"]
        }
    
    # Check device pool
    if device_pool:
        devices = device_pool.list_devices()
        health["services"]["device_pool"] = {
            "status": "active",
            "total_devices": len(devices)
        }
    
    return health