import logging
import json
import datetime

class JSONFormatter(logging.Formatter):
    """
    Formatter that outputs JSON strings for logs.
    """
    def format(self, record):
        log_record = {
            "timestamp": datetime.datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "message": record.getMessage(),
            "logger": record.name,
            "module": record.module,
            "line": record.lineno,
        }

        if record.exc_info:
            log_record["exception"] = self.formatException(record.exc_info)
        
        # Add extra context if passed via extra={}
        if hasattr(record, 'order_id'):
            log_record['order_id'] = record.order_id
        if hasattr(record, 'user_id'):
            log_record['user_id'] = record.user_id

        return json.dumps(log_record)