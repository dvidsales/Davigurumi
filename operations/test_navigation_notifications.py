from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.test import RequestFactory, TestCase
from django.urls import reverse
from django.utils import timezone

from .context_processors import notification_summary
from .models import Notification


class NotificationNavigationTests(TestCase):
    def setUp(self):
        self.owner = get_user_model().objects.create_user(username="notification_owner", email="notification_owner@example.test")
        other = get_user_model().objects.create_user(username="notification_other", email="notification_other@example.test")
        self.unread = Notification.objects.create(owner=self.owner, key="unread", message="Sua notificação")
        Notification.objects.create(owner=self.owner, key="read", message="Já lida", read_at=timezone.now())
        Notification.objects.create(owner=other, key="other", message="Não pertence à conta")
        self.client.force_login(self.owner)

    def test_shortcut_is_persistent_and_count_is_owner_scoped(self):
        response = self.client.get(reverse("operations:material_report"))
        self.assertEqual(response.context["unread_notification_count"], 1)
        self.assertContains(response, 'aria-label="Notificações: 1 não lida"', count=2)
        self.assertNotContains(response, "Não pertence à conta")
        self.assertNotContains(response, '>Notificações</a>')

    def test_read_notification_updates_badge_on_next_page(self):
        response = self.client.post(reverse("operations:read", args=[self.unread.pk]), follow=True)
        self.assertEqual(response.context["unread_notification_count"], 0)
        self.assertNotContains(response, 'class="notification-count"')

    def test_anonymous_context_never_queries_notifications(self):
        request = RequestFactory().get("/")
        request.user = AnonymousUser()
        with self.assertNumQueries(0):
            self.assertEqual(notification_summary(request), {})

    def test_invalid_report_filters_are_not_reported_as_empty_results(self):
        response = self.client.get(reverse("operations:material_report"), {"start": "invalid"})
        self.assertContains(response, "Revise os filtros")
        self.assertNotContains(response, "Nenhum movimento neste período")
        response = self.client.get(reverse("production:calendar"), {"start": "invalid"})
        self.assertContains(response, "Revise os filtros da agenda")
        self.assertNotContains(response, "Tudo organizado")
