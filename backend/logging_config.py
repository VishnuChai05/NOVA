"""
Logging configuration for NOVA backend.
Logs are written to both console and file for easy review.
"""

import logging
import logging.handlers
from pathlib import Path
from datetime import datetime

# Create logs directory
LOGS_DIR = Path(__file__).parent / ".logs"
LOGS_DIR.mkdir(exist_ok=True)

# Log file paths
LOG_FILE = LOGS_DIR / "backend.log"
ERROR_LOG_FILE = LOGS_DIR / "backend_errors.log"
SCRAPER_LOG_FILE = LOGS_DIR / "scraper.log"

def setup_logging():
    """Configure logging for the application."""
    
    # Root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)
    
    # Console handler (existing output)
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    console_handler.setFormatter(console_formatter)
    
    # Main log file handler (all logs)
    file_handler = logging.handlers.RotatingFileHandler(
        LOG_FILE,
        maxBytes=10*1024*1024,  # 10MB
        backupCount=5
    )
    file_handler.setLevel(logging.DEBUG)
    file_formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s'
    )
    file_handler.setFormatter(file_formatter)
    
    # Error log file handler
    error_handler = logging.handlers.RotatingFileHandler(
        ERROR_LOG_FILE,
        maxBytes=5*1024*1024,  # 5MB
        backupCount=3
    )
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(file_formatter)
    
    # Scraper-specific log handler
    scraper_handler = logging.handlers.RotatingFileHandler(
        SCRAPER_LOG_FILE,
        maxBytes=10*1024*1024,  # 10MB
        backupCount=5
    )
    scraper_handler.setLevel(logging.DEBUG)
    scraper_handler.setFormatter(file_formatter)
    
    # Add handlers
    root_logger.addHandler(console_handler)
    root_logger.addHandler(file_handler)
    root_logger.addHandler(error_handler)
    
    # Configure scraper logger specifically
    scraper_logger = logging.getLogger("app.services.scraper")
    scraper_logger.addHandler(scraper_handler)
    
    # Log startup
    logging.info(f"Logging initialized at {datetime.now().isoformat()}")
    logging.info(f"Main log: {LOG_FILE}")
    logging.info(f"Error log: {ERROR_LOG_FILE}")
    logging.info(f"Scraper log: {SCRAPER_LOG_FILE}")
    
    return LOG_FILE, ERROR_LOG_FILE, SCRAPER_LOG_FILE
