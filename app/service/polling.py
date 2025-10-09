"""
Complete Polling Service Implementation
Polls server every 10 seconds for commands and executes them
"""

import asyncio
import httpx
from typing import Optional, Dict, Any
from datetime import datetime, timezone, timedelta
import time
from app.core.v1.config import config
from app.core.v1.device_pool import DevicePoolManager, MultiDeviceCommandHandler
import psutil
IST = timezone(timedelta(hours=5, minutes=30))


class PollingService:
    """
    Polls server for commands and executes them using command handler.
    
    Architecture:
    1. Poll server every 10 seconds: GET {server_url}/get_command
    2. If command received, execute it
    3. Send result back: POST {server_url}/send_result
    4. Handle errors and retries
    """
    
    def __init__(
        self,
        device_pool: DevicePoolManager,
        mac_adress: Optional[str] = None,
        poll_interval: int = 10,
    ):
        """
        Initialize polling service.
        
        Args:
            device_pool: DevicePoolManager instance
            poll_interval: Seconds between polls (default: 10)
        """
        self.base_url = config.server_url
        self.poll_interval = poll_interval
        self.is_running = False
        
        # Command handler
        self.command_handler = MultiDeviceCommandHandler(device_pool)
        
        # Statistics
        self.stats = {
            "total_polls": 0,
            "commands_received": 0,
            "commands_executed": 0,
            "commands_failed": 0,
            "last_poll_time": None,
            "last_command_time": None,
            "errors": []
        }
        
        print(f"🔄 Polling Service initialized")
        print(f"   Server: {self.base_url}")
        print(f"   Interval: {self.poll_interval} seconds")
    
    # ==================== LIFECYCLE METHODS ================================
    
    async def start(self):
        """
        Start the polling loop.
        Runs continuously until stopped.
        """
        if self.is_running:
            print("⚠️  Polling service already running")
            return
        
        self.is_running = True
        print(f"🚀 Polling service started")
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            while self.is_running:
                try:
                    await self._poll_cycle(client)
                except Exception as e:
                    self._log_error(f"Poll cycle error: {e}")
                    print(f"❌ Poll cycle error: {e}")
                
                # Wait before next poll
                await asyncio.sleep(self.poll_interval)
        
        print("🛑 Polling service stopped")
    
    def stop(self):
        """Stop the polling loop."""
        self.is_running = False
        print("🛑 Stopping polling service...")
    
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
                "server_url": self.base_url,
                "poll_interval": self.poll_interval,
                "statistics": self.stats
            },
            "device_ip": "",
            "device_id": "",
            "success": True,
            "timestamp": int(time.time())
        }
    
    # ==================== POLLING LOGIC ====================================
    
    async def _poll_cycle(self, client: httpx.AsyncClient):
        """
        One complete poll cycle:
        1. Poll server for command
        2. Execute command if present
        3. Send result back to server
        
        Args:
            client: Async HTTP client
        """
        self.stats["total_polls"] += 1
        self.stats["last_poll_time"] = int(time.time())
        
        # Step 1: Poll server for command
        command_data = await self._fetch_command(client)
        if not command_data:
            # No command available
            print("✓ Poll complete - No commands")
            return
        
        # Step 2: Execute command
        print(f"📨 Received command: {command_data.get('command')}")
        self.stats["commands_received"] += 1
        self.stats["last_command_time"] = int(time.time())
        
        result = self._execute_command(command_data)
        
        # Step 3: Send result back to server
        await self._send_result(client, command_data, result)
    
    async def _fetch_command(self, client: httpx.AsyncClient) -> Optional[Dict[str, Any]]:
        """
        Fetch command from server.
        
        Args:
            client: Async HTTP client
            
        Returns:
            Command data dictionary or None if no command
        """
        try:
            url = f"{self.base_url}/api/v1/get_command"
            body = {
                "agent_id": config.agent_id,
                "mac_address": config.mac_address,
            }
    
            response = await client.post(url, json=body)
            # Check status codes
            if response.status_code == 204:
                # No commands available
                return None
            
            if response.status_code == 404:
                # Endpoint not found
                print(f"⚠️  Endpoint not found: {url}")
                return None
            
            if response.status_code != 200:
                print(f"⚠️  Server returned status {response.status_code}")
                return None
            
            # Parse command
            command_data = response.json()
            
            if not command_data or not isinstance(command_data, dict):
                print(f"⚠️  Invalid command format received")
                return None
            if command_data.get("data") is None:
                print(f"⚠️  No command data received")
                return None
            return command_data.get("data")
            
        except httpx.ConnectError as e:
            self._log_error(f"Connection error: {e}")
            print(f"❌ Cannot connect to server: {self.base_url}")
            return None
        
        except httpx.TimeoutException as e:
            self._log_error(f"Timeout error: {e}")
            print(f"❌ Server timeout: {self.base_url}")
            return None
        
        except Exception as e:
            self._log_error(f"Fetch command error: {e}")
            print(f"❌ Failed to fetch command: {e}")
            return None
    
    def _execute_command(self, command_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute command using command handler.
        
        Args:
            command_data: Command to execute
            
        Returns:
            Execution result
        """
        try:
            result = self.command_handler.execute_command(command_data)
            
            if result.get("success"):
                self.stats["commands_executed"] += 1
                print(f"✅ Command executed: {command_data.get('command')}")
            else:
                self.stats["commands_failed"] += 1
                print(f"❌ Command failed: {result.get('error')}")
            
            return result
            
        except Exception as e:
            self.stats["commands_failed"] += 1
            self._log_error(f"Command execution error: {e}")
            print(f"❌ Command execution error: {e}")
            
            return {
                "success": False,
                "error": f"Execution error: {str(e)}",
                "command": command_data.get("command"),
                "executed_at": int(time.time())
            }
    
    async def _send_result(
        self,
        client: httpx.AsyncClient,
        command_data: Dict[str, Any],
        result: Dict[str, Any]
    ):
        """
        Send execution result back to server.
        
        Args:
            client: Async HTTP client
            command_data: Original command data
            result: Execution result
        """
        try:
            url = f"{self.base_url}/api/v1/send_result"
            
            payload = result.copy()
            response = await client.post(url, json=payload)
            print(response.text)
            if response.status_code in (200, 201, 204):
                print(f"✅ Result sent to server")
            else:
                print(f"⚠️  Server returned status {response.status_code} when sending result")
            
        except httpx.ConnectError as e:
            self._log_error(f"Connection error when sending result: {e}")
            print(f"❌ Cannot send result to server: {self.base_url}")
        
        except httpx.TimeoutException as e:
            self._log_error(f"Timeout when sending result: {e}")
            print(f"❌ Server timeout when sending result")
        
        except Exception as e:
            self._log_error(f"Send result error: {e}")
            print(f"❌ Failed to send result: {e}")
    
    # ==================== HELPER METHODS ===================================
    
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




