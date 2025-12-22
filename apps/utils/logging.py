import logging
import json
import datetime

class JSONFormatter(logging.Formatter):
    def format(self, record):
        log_record = {
            "ts": datetime.datetime.utcnow().isoformat() + "Z",
            "lvl": record.levelname,
            "msg": record.getMessage(),
            "logger": record.name,
            "path": record.pathname,
            "line": record.lineno,
        }

        # [FIX] Traceability
        if hasattr(record, 'order_id'):
            log_record['order_id'] = record.order_id
        if hasattr(record, 'user_id'):
            log_record['user_id'] = record.user_id
        
        # Exception Info
        if record.exc_info:
            log_record['exc'] = self.formatException(record.exc_info)

        return json.dumps(log_record)