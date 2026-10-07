import json
from pathlib import Path
from django.http import HttpResponse, JsonResponse
from django.conf import settings
from django.views.decorators.http import require_GET


@require_GET
def manifest(request):
    return JsonResponse(
        {
            "name": "Davigurumi",
            "short_name": "Davigurumi",
            "lang": "pt-BR",
            "start_url": "/",
            "scope": "/",
            "display": "standalone",
            "background_color": "#f4f6f3",
            "theme_color": "#163d3b",
            "icons": [
                {
                    "src": "/static/icons/icon-192.png",
                    "sizes": "192x192",
                    "type": "image/png",
                    "purpose": "any",
                },
                {
                    "src": "/static/icons/icon-512.png",
                    "sizes": "512x512",
                    "type": "image/png",
                    "purpose": "any maskable",
                },
            ],
        },
        content_type="application/manifest+json",
    )


@require_GET
def service_worker(request):
    response = HttpResponse(
        (settings.BASE_DIR / "static/js/service-worker.js").read_text(),
        content_type="application/javascript",
    )
    response["Cache-Control"] = "no-cache"
    response["Service-Worker-Allowed"] = "/"
    return response
