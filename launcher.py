#!/usr/bin/env python3
"""
ESSL Agent Backend Launcher
This script is the entry point for the executable version of the ESSL Agent Backend.

Purpose:
- Load environment variables from .env file
- Start the FastAPI server using uvicorn
- Handle graceful shutdown
- Provide error messages if .env is missing or invalid
"""

import os
import sys
import uvicorn
from pathlib import Path
from dotenv import load_dotenv

# ============================================================================
# CONCEPT: Finding the .env file location
# ============================================================================
# When PyInstaller creates an executable, it can run in two modes:
# 1. One-folder mode: executable + _internal folder with dependencies
# 2. One-file mode: everything packed in a single executable
#
# We need to find where the .env file is located:
# - In development: same directory as this script
# - In executable: same directory as the .exe file
# ============================================================================

def get_application_path():
    """
    Get the path where the application is running from.
    
    Returns:
        Path: The directory containing the executable or script
    
    Why this is needed:
    - sys.executable gives the Python interpreter path (not what we want in dev)
    - __file__ gives this script's path (works in dev, but not in PyInstaller)
    - PyInstaller sets sys.frozen when running as executable
    """
    if getattr(sys, 'frozen', False):
        # Running as compiled executable
        # sys.executable is the path to the .exe file
        application_path = Path(sys.executable).parent
    else:
        # Running as a normal Python script
        application_path = Path(__file__).parent
    
    return application_path


def check_env_file():
    """
    Check if .env file exists and is readable.
    
    Returns:
        tuple: (success: bool, message: str, env_path: Path)
    
    Why this check is important:
    - Users might forget to include .env file
    - .env might have wrong permissions
    - Provides clear error messages instead of cryptic failures
    """
    app_path = get_application_path()
    env_path = app_path / '.env'
    
    if not env_path.exists():
        return False, f"❌ .env file not found at: {env_path}", env_path
    
    if not env_path.is_file():
        return False, f"❌ .env exists but is not a file: {env_path}", env_path
    
    # Try to read the file
    try:
        with open(env_path, 'r') as f:
            content = f.read()
        
        # Check for required variables
        if 'SERVER_URL' not in content:
            return False, "⚠️  .env file missing SERVER_URL variable", env_path
        
        if 'AGENT_ID' not in content:
            return False, "⚠️  .env file missing AGENT_ID variable", env_path
            
        return True, "✅ .env file loaded successfully", env_path
        
    except PermissionError:
        return False, f"❌ Permission denied reading .env file: {env_path}", env_path
    except Exception as e:
        return False, f"❌ Error reading .env file: {str(e)}", env_path


def load_environment():
    """
    Load environment variables from .env file.
    
    Returns:
        bool: True if successful, False otherwise
    
    The dotenv library:
    - Reads key=value pairs from .env file
    - Sets them as environment variables (os.environ)
    - Doesn't override existing environment variables
    """
    success, message, env_path = check_env_file()
    
    print("=" * 60)
    print("ESSL Agent Backend - Starting...")
    print("=" * 60)
    print(f"Application Path: {get_application_path()}")
    print(f"Looking for .env at: {env_path}")
    print(message)
    
    if not success:
        print("\n📝 Expected .env format:")
        print("SERVER_URL=http://your-server-url.com")
        print("AGENT_ID=your-agent-id")
        print("=" * 60)
        return False
    
    # Load the .env file
    load_dotenv(env_path)
    
    # Verify variables are loaded
    server_url = os.getenv('SERVER_URL')
    agent_id = os.getenv('AGENT_ID')
    
    print(f"\n📡 Configuration Loaded:")
    print(f"   SERVER_URL: {server_url}")
    print(f"   AGENT_ID: {agent_id}")
    print("=" * 60)
    
    return True


def start_server():
    """
    Start the FastAPI server using uvicorn.
    
    Why uvicorn.run() instead of subprocess/command line:
    - Direct Python API call (faster, more reliable)
    - Better error handling
    - Works the same in development and as executable
    """
    # Get configuration from environment (with defaults)
    host = os.getenv('HOST', '0.0.0.0')  # Listen on all interfaces
    port = int(os.getenv('PORT', '8000'))  # Default port 8000
    
    print(f"\n🚀 Starting server on http://{host}:{port}")
    print("=" * 60)
    print("Press CTRL+C to stop the server")
    print("=" * 60)
    
    try:
        # Start uvicorn server
        # app.main:app means:
        #   - Look in the 'app' package
        #   - Find the 'main' module
        #   - Get the 'app' FastAPI instance
        uvicorn.run(
            "app.main:app",
            host=host,
            port=port,
            reload=False,  # Disable reload in production (executable)
            log_level="info"
        )
    except KeyboardInterrupt:
        print("\n\n⏹️  Server stopped by user")
    except Exception as e:
        print(f"\n\n❌ Error starting server: {str(e)}")
        return False
    
    return True


def main():
    """
    Main entry point for the application.
    
    Flow:
    1. Load environment variables from .env
    2. Start the FastAPI server
    3. Handle errors gracefully
    """
    # Load environment configuration
    if not load_environment():
        print("\n❌ Failed to load environment configuration")
        print("Please ensure .env file exists and is properly configured")
        input("\nPress Enter to exit...")
        sys.exit(1)
    
    # Start the server
    try:
        start_server()
    except Exception as e:
        print(f"\n❌ Unexpected error: {str(e)}")
        input("\nPress Enter to exit...")
        sys.exit(1)


# ============================================================================
# Entry point when script is run directly
# ============================================================================
if __name__ == "__main__":
    main()
