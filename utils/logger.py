import logging
import os

def get_logger(name):
    """Set up and return a logger."""
    name = "." + name if not name == "" else name
    logger = logging.getLogger("aws_scanner" + name)

    # Get log level from environment variable (default to INFO if not set)
    log_level = os.getenv("LOG_LEVEL", "INFO").upper()

    # Set the log level
    logger.setLevel(log_level)

    # Create a stream handler (logs to console)
    handler = logging.StreamHandler()

    # Create a log format
    formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    handler.setFormatter(formatter)

    # Add the handler to the logger
    logger.addHandler(handler)

    return logger
