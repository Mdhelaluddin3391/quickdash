import logging

# Use the standard Django logger configuration
logger = logging.getLogger("quickdash.events")

def log_event(event_name, data=None):
    """
    Standardized event logging helper.
    """
    payload = data or {}
    logger.info(f"{event_name} | {payload}")