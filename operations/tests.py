import uuid
from unittest.mock import patch
from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.core import mail
from .models import Notification, NotificationPreference, OutboxEvent
from .services import emit, deliver_outbox


class NotificationTests(TestCase):
    @override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
    def test_external_failure_keeps_event_and_retries_without_duplicate_internal_notification(
        self,
    ):
        owner = get_user_model().objects.create_user(
            username="notify", email="notify@example.test"
        )
        NotificationPreference.objects.create(owner=owner, email_enabled=True)
        target = uuid.uuid4()
        emit(
            owner=owner,
            kind="approved",
            object_id=target,
            message="Orçamento aprovado.",
        )
        emit(
            owner=owner,
            kind="approved",
            object_id=target,
            message="Orçamento aprovado.",
        )
        self.assertEqual(Notification.objects.count(), 1)
        self.assertEqual(OutboxEvent.objects.count(), 1)
        with patch(
            "operations.services.send_mail", side_effect=OSError("synthetic failure")
        ):
            self.assertEqual(deliver_outbox(), {"sent": 0, "failed": 1})
        event = OutboxEvent.objects.get()
        self.assertEqual(event.status, "pending")
        self.assertEqual(event.attempts, 1)
        from django.utils import timezone

        event.next_attempt = timezone.now()
        event.save()
        self.assertEqual(deliver_outbox(), {"sent": 1, "failed": 0})
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(deliver_outbox(), {"sent": 0, "failed": 0})
