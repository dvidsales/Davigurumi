import logging
import re


class RedactPortalToken(logging.Filter):
    def filter(self, record):
        record.msg = re.sub(
            r"/portal/[^/\s?]+", "/portal/[redacted]", record.getMessage()
        )
        record.msg = re.sub(
            r"/conta/redefinir/[^/\s?]+/[^/\s?]+",
            "/conta/redefinir/[redacted]/[redacted]",
            record.msg,
        )
        record.args = ()
        return True
