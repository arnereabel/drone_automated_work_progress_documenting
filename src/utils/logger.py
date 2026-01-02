"""
Logging utilities for Drone Photography System.

Provides consistent logging across all modules with both
file and console output.
"""

import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

# Module-level logger registry
_loggers: dict = {}
_initialized: bool = False
_log_file_path: Optional[Path] = None


def setup_logger(
    level: str = "INFO",
    log_file: Optional[str] = None,
    console: bool = True,
    name: str = "drone_photo",
) -> logging.Logger:
    """
    Set up the root logger for the application.
    
    Args:
        level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL).
        log_file: Path to log file. If None, only console logging.
        console: Whether to log to console.
        name: Root logger name.
        
    Returns:
        Configured logger instance.
    """
    global _initialized, _log_file_path
    
    # Convert string level to logging constant
    numeric_level = getattr(logging, level.upper(), logging.INFO)
    
    # Create or get root logger
    logger = logging.getLogger(name)
    logger.setLevel(numeric_level)
    
    # Clear any existing handlers
    logger.handlers.clear()
    
    # Create formatter
    formatter = logging.Formatter(
        fmt='%(asctime)s | %(levelname)-8s | %(name)s | %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # Console handler
    if console:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(numeric_level)
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)
    
    # File handler
    if log_file:
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Add timestamp to log filename for uniqueness
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_file_with_timestamp = log_path.parent / f"{log_path.stem}_{timestamp}{log_path.suffix}"
        
        file_handler = logging.FileHandler(log_file_with_timestamp, encoding='utf-8')
        file_handler.setLevel(numeric_level)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
        
        _log_file_path = log_file_with_timestamp
    
    _initialized = True
    _loggers[name] = logger
    
    logger.info(f"Logger initialized - Level: {level}, Console: {console}, File: {log_file}")
    
    return logger


def get_logger(name: str = "drone_photo") -> logging.Logger:
    """
    Get a logger instance.
    
    If the root logger hasn't been initialized, creates a basic one.
    
    Args:
        name: Logger name. Use dot notation for hierarchy
              (e.g., "drone_photo.navigator").
              
    Returns:
        Logger instance.
    """
    global _initialized
    
    if not _initialized:
        # Create a basic logger if setup hasn't been called
        setup_logger()
    
    # For child loggers, get as child of root
    if name != "drone_photo" and not name.startswith("drone_photo."):
        name = f"drone_photo.{name}"
    
    return logging.getLogger(name)


def get_log_file_path() -> Optional[Path]:
    """
    Get the path to the current log file.
    
    Returns:
        Path to log file, or None if file logging not enabled.
    """
    return _log_file_path


class LoggerMixin:
    """
    Mixin class that provides a logger attribute to any class.
    
    Usage:
        class MyModule(LoggerMixin):
            def do_something(self):
                self.logger.info("Doing something...")
    """
    
    @property
    def logger(self) -> logging.Logger:
        """Get logger for this class."""
        if not hasattr(self, '_logger'):
            self._logger = get_logger(self.__class__.__name__)
        return self._logger


# Convenience context manager for logging blocks
class LogBlock:
    """
    Context manager for logging entry/exit of code blocks.
    
    Usage:
        with LogBlock("Processing waypoints"):
            # ... code ...
    """
    
    def __init__(self, description: str, logger: Optional[logging.Logger] = None):
        self.description = description
        self.logger = logger or get_logger()
        self.start_time = None
    
    def __enter__(self):
        self.start_time = datetime.now()
        self.logger.info(f"▶ Starting: {self.description}")
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        duration = (datetime.now() - self.start_time).total_seconds()
        
        if exc_type is not None:
            self.logger.error(
                f"✖ Failed: {self.description} after {duration:.2f}s - {exc_type.__name__}: {exc_val}"
            )
        else:
            self.logger.info(f"✔ Completed: {self.description} in {duration:.2f}s")
        
        return False  # Don't suppress exceptions
