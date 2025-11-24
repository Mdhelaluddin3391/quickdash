import logging
from datetime import datetime

logger = logging.getLogger("quickdash")


def log_event(event_name, data=None):
    logger.info(f"[EVENT] {event_name} | {datetime.now()} | {data or {}}")
