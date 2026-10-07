import hashlib
import hmac
from datetime import timedelta
from django.conf import settings
from django.db import transaction
from django.http import HttpResponse
from django.utils import timezone
from .models import AuthThrottle
from .uploads import UploadBudgetHandler


class DevelopmentSecurityMiddleware:
    """Database-backed limits shared by workers. Does not trust forwarding headers."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.respond(request)
        response["Content-Security-Policy"] = (
            "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; object-src 'none'; base-uri 'self'; frame-ancestors 'none'; form-action 'self'"
        )
        response["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        if not request.path.startswith("/static/") and request.path not in {
            "/manifest.webmanifest",
            "/service-worker.js",
        }:
            response["Cache-Control"] = "private, no-store"
        return response

    def respond(self, request):
        if request.method in {"POST", "PUT", "PATCH"}:
            file_limit = (
                settings.ARCHIVE_UPLOAD_LIMIT
                if request.path == "/dados/completo/"
                else settings.PRIVATE_UPLOAD_LIMIT
            )
            try:
                content_length = int(request.META.get("CONTENT_LENGTH") or 0)
            except (ValueError, TypeError):
                return HttpResponse("Tamanho da requisição inválido.", status=400)
            if (
                content_length < 0
                or content_length > file_limit + settings.DATA_UPLOAD_MAX_MEMORY_SIZE
            ):
                return HttpResponse(
                    "Requisição excede o limite desta operação.", status=413
                )
            request.upload_handlers.insert(0, UploadBudgetHandler(request, file_limit))
        protected = {
            "/conta/entrar/",
            "/conta/criar/",
            "/conta/recuperar/",
            "/dados/completo/",
            "/demo/",
            "/conta/seguranca/",
            "/conta/senha/",
        }
        public_read = request.method in {"GET", "HEAD"} and request.path.startswith(
            "/portal/"
        )
        report_read = request.method in {"GET", "HEAD"} and (
            request.path == "/"
            or request.path.startswith(
                (
                    "/notificacoes/relatorios/",
                    "/pedidos/calendario/",
                    "/dados/materiais.",
                )
            )
        )
        general_write = request.method in {"POST", "PUT", "PATCH", "DELETE"}
        if general_write or public_read or report_read:
            address = request.META.get("REMOTE_ADDR", "unknown")
            bucket = (
                "/portal/"
                if request.path.startswith("/portal/")
                else (
                    "/conta/redefinir/"
                    if request.path.startswith("/conta/redefinir/")
                    else request.path
                )
            )
            auth_write = request.method == "POST" and (
                request.path in protected
                or request.path.startswith(("/portal/", "/conta/redefinir/"))
            )
            if public_read:
                bucket = "/portal/read/"
            elif report_read:
                bucket = "/reports/read/"
            elif general_write and not auth_write:
                bucket = "/writes/"
            digest = hmac.new(
                settings.SECRET_KEY.encode(),
                (bucket + address).encode(),
                hashlib.sha256,
            ).hexdigest()
            if public_read:
                window, limit = (
                    settings.PORTAL_READ_RATE_WINDOW_SECONDS,
                    settings.PORTAL_READ_RATE_LIMIT,
                )
            elif report_read:
                window, limit = (
                    settings.REPORT_READ_RATE_WINDOW_SECONDS,
                    settings.REPORT_READ_RATE_LIMIT,
                )
            elif auth_write:
                window, limit = (
                    settings.AUTH_RATE_WINDOW_SECONDS,
                    settings.AUTH_RATE_LIMIT,
                )
            else:
                window, limit = (
                    settings.WRITE_RATE_WINDOW_SECONDS,
                    settings.WRITE_RATE_LIMIT,
                )
            now = timezone.now()
            with transaction.atomic():
                row, _ = AuthThrottle.objects.get_or_create(
                    key=digest,
                    defaults={"expires_at": now + timedelta(seconds=window)},
                )
                row = AuthThrottle.objects.select_for_update().get(pk=row.pk)
                if row.expires_at <= now:
                    row.attempts = 0
                    row.expires_at = now + timedelta(seconds=window)
                row.attempts += 1
                row.save(update_fields=["attempts", "expires_at"])
                blocked = row.attempts > limit
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
        return self.get_response(request)
