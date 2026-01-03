"""
UDC-Studio - Visual Configuration Builder for UDC01
----------------------------------------------------
AI-powered configuration builder for creating UDC01 data conversion YAMLs.

Features:
- Safety verification with 2/3 consensus
- Intelligent data profiling
- YAML configuration generation
- Multi-agent validation

Usage:
    python udc_studio.py
"""

__version__ = "1.0.0"

from .config_builder.core.builder import ConfigurationBuilder
from .config_builder.core.api_client import create_client

__all__ = ["ConfigurationBuilder", "create_client"]
