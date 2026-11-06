from django.db import connection
from django.db.utils import DatabaseError
from django.http import JsonResponse
from django.views.decorators.http import require_GET
from django.views.decorators.cache import never_cache


@never_cache
@require_GET
def health(request):
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
    except DatabaseError:
        return JsonResponse({"status": "unavailable"}, status=503)
    return JsonResponse({"status": "ok"})


@never_cache
@require_GET
def version(request):
    import os
    import re

    commit = os.getenv("RENDER_GIT_COMMIT", "")
    release = commit[:12] if re.fullmatch(r"[0-9a-f]{40}", commit) else "unknown"
    return JsonResponse({"release": release})
