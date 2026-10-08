import hashlib
import hmac
from django.conf import settings
from django.utils.crypto import constant_time_compare


def invite_code(secret, email):
    return hmac.new(
        secret.encode(), ("beta-v1:" + email.strip().lower()).encode(), hashlib.sha256
    ).hexdigest()


def valid_invite(email, code):
    email = email.strip().lower()
    return (
        email in settings.BETA_EMAILS
        and bool(settings.BETA_INVITE_SECRET)
        and constant_time_compare(invite_code(settings.BETA_INVITE_SECRET, email), code)
    )
