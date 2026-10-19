import logging
import re


class RedactCredentials(logging.Filter):
    """Defense for SDK/server logs; business audit never receives these fields."""

    def filter(self, record):
        message = record.getMessage()
        message = re.sub(r"(/transfers/(?:upload|download)/)[A-Za-z0-9_-]+", r"\1[redacted]", message)
        message = re.sub(
            r"([?&](?:code|token|access_token|refresh_token|ticket)=)[^&\s\"]+", r"\1[redacted]", message
        )
        message = re.sub(r"(?i)(Bearer\s+)[A-Za-z0-9._~-]+", r"\1[redacted]", message)
        record.msg, record.args = message, ()
        return True


def protect_logs():
    loggers = [logging.getLogger()] + [
        value for value in logging.Logger.manager.loggerDict.values() if isinstance(value, logging.Logger)
    ]
    for logger in loggers:
        for handler in logger.handlers:
            if not any(isinstance(f, RedactCredentials) for f in handler.filters):
                handler.addFilter(RedactCredentials())
