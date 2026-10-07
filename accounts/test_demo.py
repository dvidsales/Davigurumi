import uuid
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from materials.models import Material
from projects.models import Project
from .demo import create_demo, copy_demo


class DemoTests(TestCase):
    def setUp(self):
        self.owner = get_user_model().objects.create_user(
            username="demo_owner",
            email="demo_owner@example.test",
            password="Synthetic-Long-Password-17!",
        )

    def test_demo_is_separate_and_switching_preserves_authentication(self):
        self.client.force_login(self.owner)
        self.client.post(reverse("demo_switch"), {"action": "enter"})
        workspace = self.owner.demo_workspace
        self.assertFalse(Material.objects.filter(owner=self.owner).exists())
        response = self.client.get(reverse("materials:index"))
        self.assertContains(response, "Fio de demonstração")
        self.assertEqual(self.client.session["_auth_user_id"], str(self.owner.pk))
        self.client.post(reverse("demo_switch"), {"action": "exit"})
        self.assertNotContains(
            self.client.get(reverse("materials:index")), "Fio de demonstração"
        )
        self.assertEqual(create_demo(self.owner).pk, workspace.pk)

    def test_selective_copy_has_zero_stock_no_demo_costs_and_no_financial_records(self):
        workspace = create_demo(self.owner)
        project = Project.objects.get(owner=workspace.demo_user)
        key = uuid.uuid4()
        first = copy_demo(
            owner=self.owner,
            workspace=workspace,
            material_ids=[],
            project_ids=[project.pk],
            key=key,
        )
        self.assertEqual(
            copy_demo(
                owner=self.owner,
                workspace=workspace,
                material_ids=[],
                project_ids=[project.pk],
                key=key,
            ),
            first,
        )
        material = Material.objects.get(owner=self.owner)
        self.assertEqual(material.physical_stock, 0)
        self.assertFalse(material.layers.exists())
        copied = Project.objects.get(owner=self.owner)
        self.assertEqual(copied.current_revision.hourly_rate, 0)
        self.assertEqual(copied.current_revision.estimated_seconds, 0)
        self.assertEqual(copied.current_revision.materials.get().base_quantity, 120)
        from finance.models import Payment

        self.assertFalse(Payment.objects.filter(owner=self.owner).exists())

    def test_forged_demo_session_cannot_select_another_accounts_workspace(self):
        other = get_user_model().objects.create_user(
            username="other_demo", email="other_demo@example.test"
        )
        workspace = create_demo(other)
        self.client.force_login(self.owner)
        session = self.client.session
        session["demo_workspace"] = str(workspace.pk)
        session.save()
        self.assertNotContains(
            self.client.get(reverse("materials:index")), "Fio de demonstração"
        )
