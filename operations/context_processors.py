"""Small, owner-scoped notification summary for the persistent navigation."""
from .models import Notification


def notification_summary(request):
    if not request.user.is_authenticated:
        return {}
    return {
        "unread_notification_count": Notification.objects.filter(
            owner=request.user, read_at__isnull=True
        ).count()
    }
