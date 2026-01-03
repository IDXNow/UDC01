"""
UDC-Studio Configuration Builder
AI-powered YAML configuration generation for UDC01
"""

__version__ = "1.0.0"

from .core.builder import ConfigurationBuilder
from .core.api_client import create_client, UDCClient, LocalUDCClient, CloudUDCClient

__all__ = [
    "ConfigurationBuilder",
    "create_client",
    "UDCClient",
    "LocalUDCClient",
    "CloudUDCClient"
]
