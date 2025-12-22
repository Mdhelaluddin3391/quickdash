import logging
import json
import datetime

class JSONFormatter(logging.Formatter):
    """
    Production-safe JSON Formatter.
    Recursively scrubs sensitive keys from logs.
    """
    
    # Lowercase set of keys to redact
    SENSITIVE_KEYS = {
        'password', 'token', 'access', 'refresh', 
        'otp', 'credit_card', 'cvv', 'secret', 
        'authorization', 'key', 'signature'
    }

    def _scrub(self, data):
        """
        Recursively redact sensitive data from dicts and lists.
        """
        if isinstance(data, dict):
            return {
                k: self._scrub(v) if k.lower() not in self.SENSITIVE_KEYS else '***REDACTED***' 
                for k, v in data.items()
            }
        if isinstance(data, list):
            return [self._scrub(i) for i in data]
        return data

    def format(self, record):
        # [SECURITY] Scrub the primary message if it's a dictionary (structured log)
        if isinstance(record.msg, dict):
            record.msg = self._scrub(record.msg)
            
        # [SECURITY] Scrub arguments if they are a dictionary
        if hasattr(record, 'args') and isinstance(record.args, dict):
             record.args = self._scrub(record.args)

        # Build Standard Log Record
        log_record = {
            "ts": datetime.datetime.utcnow().isoformat() + "Z",
            "lvl": record.levelname,
            "msg": record.getMessage(), # Uses string representation of msg
            "logger": record.name,
            "path": record.pathname,
            "line": record.lineno,
        }

        # Add Contextual Traceability
        if hasattr(record, 'order_id'):
            log_record['order_id'] = record.order_id
        if hasattr(record, 'user_id'):
            log_record['user_id'] = record.user_id
        
        # Exception Info
        if record.exc_info:
            log_record['exc'] = self.formatException(record.exc_info)

        return json.dumps(log_record)