import logging
import re


class RedactPortalToken(logging.Filter):
    def filter(self, record):
        record.msg = re.sub(
            r"/portal/[^/\s?]+", "/portal/[redacted]", record.getMessage()
        )
        record.args = ()
        return True
