import hashlib
import hmac
from datetime import timedelta
from django.conf import settings
from django.db import transaction
from django.http import HttpResponse
from django.utils import timezone
from .models import AuthThrottle


class DevelopmentSecurityMiddleware:
    """Database-backed limits shared by workers. Does not trust forwarding headers."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        protected = {
            "/conta/entrar/",
            "/conta/criar/",
            "/conta/recuperar/",
            "/dados/completo/",
        }
        if request.method == "POST" and (
            request.path in protected or request.path.startswith("/portal/")
        ):
            address = request.META.get("REMOTE_ADDR", "unknown")
            bucket = "/portal/" if request.path.startswith("/portal/") else request.path
            digest = hmac.new(
                settings.SECRET_KEY.encode(),
                (bucket + address).encode(),
                hashlib.sha256,
            ).hexdigest()
            now = timezone.now()
            with transaction.atomic():
                row, _ = AuthThrottle.objects.get_or_create(
                    key=digest,
                    defaults={
                        "expires_at": now
                        + timedelta(seconds=settings.AUTH_RATE_WINDOW_SECONDS)
                    },
                )
                row = AuthThrottle.objects.select_for_update().get(pk=row.pk)
                if row.expires_at <= now:
                    row.attempts = 0
                    row.expires_at = now + timedelta(
                        seconds=settings.AUTH_RATE_WINDOW_SECONDS
                    )
                row.attempts += 1
                row.save(update_fields=["attempts", "expires_at"])
                blocked = row.attempts > settings.AUTH_RATE_LIMIT
            if blocked:
                response = HttpResponse(
                    "Muitas tentativas. Aguarde alguns minutos antes de tentar novamente.",
                    status=429,
                )
                response["Retry-After"] = str(
                    max(1, int((row.expires_at - now).total_seconds()))
                )
                response["Cache-Control"] = "no-store"
                return response
        response = self.get_response(request)
        response["Content-Security-Policy"] = (
            "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; object-src 'none'; base-uri 'self'; frame-ancestors 'none'; form-action 'self'"
        )
        if request.path.startswith("/portal/"):
            # Keeps tokens out of cross-origin referrers while allowing native
            # form POSTs to carry a valid Origin (Chromium sends null with no-referrer).
            response["Referrer-Policy"] = "same-origin"
            response["Cache-Control"] = "no-store"
        return response
