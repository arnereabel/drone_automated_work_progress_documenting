"""
Utility modules for drone photography system.

Utilities:
- logger: Logging configuration and utilities
- storage: Photo storage management
"""

from .logger import setup_logger, get_logger
from .storage import StorageManager

__all__ = ["setup_logger", "get_logger", "StorageManager"]
