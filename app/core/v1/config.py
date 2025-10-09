""" Configurations Module"""
import os
from pathlib import Path
from dotenv import load_dotenv, find_dotenv
from pydantic import BaseModel, ValidationError, ConfigDict
from typing import Optional
import psutil

env = ".env"
load_dotenv(dotenv_path=find_dotenv(filename=env))

def get_physical_mac():
    addrs = psutil.net_if_addrs()
    for iface_name, iface_addrs in addrs.items():
        if iface_name.startswith(("lo", "docker", "br-", "veth")):
            continue
        for addr in iface_addrs:
            if getattr(addr, "family", None) == psutil.AF_LINK:
                mac = addr.address
                if mac and mac != "00:00:00:00:00:00":
                    return mac
    return None


class Config(BaseModel):
    server_url: str
    agent_id: str
    mac_address: Optional[str] = None
    model_config = ConfigDict(arbitrary_types_allowed=True)

def load_config() -> Config:
    """
    Load and validate configuration from environment variables.

    Returns:
        Config: An instance of the Config class populated with environment variables.

    Raises:
        RuntimeError: If required environment variables are missing or invalid.
    """
   
    try:
        return Config(
            server_url=os.environ["SERVER_URL"],
            agent_id=os.environ["AGENT_ID"],
            mac_address=get_physical_mac()
        )
    except ValidationError as e:
        raise RuntimeError(f"Configuration validation error: {e}")

# Load the configuration
try:
    config = load_config()
except RuntimeError as e:
    raise RuntimeError(f"Failed to load configuration: {e}")