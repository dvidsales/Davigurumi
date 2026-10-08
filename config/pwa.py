import json
from pathlib import Path
from django.http import HttpResponse, JsonResponse
from django.conf import settings
from django.views.decorators.http import require_GET
from django.templatetags.static import static


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
    source = (settings.BASE_DIR / "static/js/service-worker.js").read_text()
    assets = [
        static(name)
        for name in (
            "css/app.css",
            "js/app.js",
            "icons/icon-192.png",
            "icons/icon-512.png",
        )
    ]
    source = "\n".join(
        (
            "const ASSETS = " + json.dumps(assets) + ";"
            if line.startswith("const ASSETS = ")
            else line
        )
        for line in source.splitlines()
    )
    response = HttpResponse(
        source,
        content_type="application/javascript",
    )
    response["Cache-Control"] = "no-cache"
    response["Service-Worker-Allowed"] = "/"
    return response
