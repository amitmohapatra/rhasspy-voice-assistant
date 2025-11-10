"""
Centralized logging configuration with file rotation
Provides enterprise-grade logging with automatic rotation and retention
"""
import logging
import os
from logging.handlers import RotatingFileHandler
from pathlib import Path


def setup_logging(log_level: str = "INFO", log_dir: str = None):
    """
    Configure logging with console and rotating file handlers
    
    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_dir: Directory for log files (defaults to project root)
    """
    # Determine log directory
    if log_dir is None:
        # Default to project root (one level up from backend/)
        backend_dir = Path(__file__).parent.parent
        log_dir = backend_dir.parent
    
    log_dir = Path(log_dir)
    log_dir.mkdir(exist_ok=True)
    
    # Log file paths
    backend_log = log_dir / "backend.log"
    error_log = log_dir / "backend_errors.log"
    
    # Create formatters
    detailed_formatter = logging.Formatter(
        fmt='%(asctime)s | %(levelname)-8s | %(name)-30s | %(funcName)-20s | %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    simple_formatter = logging.Formatter(
        fmt='%(asctime)s %(levelname)s %(name)s: %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # Get root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, log_level.upper(), logging.INFO))
    
    # Clear any existing handlers
    root_logger.handlers.clear()
    
    # Console handler (INFO and above)
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(simple_formatter)
    root_logger.addHandler(console_handler)
    
    # Main file handler (all logs)
    # Rotate after 10MB, keep 5 backup files
    file_handler = RotatingFileHandler(
        backend_log,
        maxBytes=10 * 1024 * 1024,  # 10MB
        backupCount=5,
        encoding='utf-8'
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(detailed_formatter)
    root_logger.addHandler(file_handler)
    
    # Error file handler (ERROR and above only)
    # Rotate after 5MB, keep 3 backup files
    error_handler = RotatingFileHandler(
        error_log,
        maxBytes=5 * 1024 * 1024,  # 5MB
        backupCount=3,
        encoding='utf-8'
    )
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(detailed_formatter)
    root_logger.addHandler(error_handler)
    
    # Log startup message
    logger = logging.getLogger(__name__)
    logger.info("=" * 80)
    logger.info("Logging configured successfully")
    logger.info(f"Log level: {log_level}")
    logger.info(f"Main log file: {backend_log}")
    logger.info(f"Error log file: {error_log}")
    logger.info(f"Rotation: 10MB main log (5 backups), 5MB error log (3 backups)")
    logger.info("=" * 80)
    
    # Suppress noisy third-party loggers
    logging.getLogger('urllib3').setLevel(logging.WARNING)
    logging.getLogger('openai').setLevel(logging.WARNING)
    logging.getLogger('httpx').setLevel(logging.WARNING)
    logging.getLogger('httpcore').setLevel(logging.WARNING)
    
    return root_logger


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger instance with the given name
    
    Args:
        name: Logger name (typically __name__)
        
    Returns:
        Logger instance
    """
    return logging.getLogger(name)

