import logging
import os
from datetime import datetime
from logging.handlers import RotatingFileHandler

def setup_logging():
    """Setup logging configuration for the application"""
    
    # Create logs directory if it doesn't exist
    logs_dir = "logs"
    if not os.path.exists(logs_dir):
        os.makedirs(logs_dir)
    
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            # Console handler
            logging.StreamHandler(),
            # File handler with rotation
            RotatingFileHandler(
                os.path.join(logs_dir, 'app.log'),
                maxBytes=10*1024*1024,  # 10MB
                backupCount=5
            ),
            # Webhook specific log
            RotatingFileHandler(
                os.path.join(logs_dir, 'webhook.log'),
                maxBytes=5*1024*1024,  # 5MB
                backupCount=3
            )
        ]
    )
    
    # Create specific loggers
    webhook_logger = logging.getLogger('webhook')
    webhook_logger.setLevel(logging.INFO)
    
    call_logger = logging.getLogger('call')
    call_logger.setLevel(logging.INFO)
    
    return webhook_logger, call_logger

def log_webhook_event(event_type, payload, logger):
    """Log webhook events with proper formatting"""
    logger.info(f"Webhook Event: {event_type}")
    logger.info(f"Payload: {payload}")

def log_call_event(event_type, call_id, caller_id, logger):
    """Log call-related events"""
    logger.info(f"Call Event: {event_type} - Call ID: {call_id}, Caller: {caller_id}")

def log_error(error_message, logger):
    """Log errors with proper formatting"""
    logger.error(f"Error: {error_message}") 