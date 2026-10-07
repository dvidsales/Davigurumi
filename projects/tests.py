from decimal import Decimal
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.http import Http404
from materials.models import Material
from .services import create_project, add_material, snapshot_project, add_alternative

D = Decimal


class ProjectTests(TestCase):
    def setUp(self):
        self.owner = get_user_model().objects.create_user(
            username="maker", email="maker@example.test"
        )
        self.material = Material.objects.create(
            owner=self.owner, name="Fio azul", kind="yarn", unit="g"
        )
        self.project = create_project(
            owner=self.owner,
            name="Kit",
            base_quantity=5,
            estimated_seconds=3600,
            hourly_rate=D("30"),
            additional_cost=D("5"),
        )

    def test_quantity_scales_materials_labor_and_additional_costs(self):
        add_material(
            owner=self.owner,
            project_id=self.project.pk,
            material_id=self.material.pk,
            quantity=D("100"),
            manual_unit_cost=D(".1"),
        )
        self.project.refresh_from_db()
        snapshot = snapshot_project(
            owner=self.owner, revision_id=self.project.current_revision_id, quantity=10
        )
        self.assertEqual(D(snapshot["materials"][0]["quantity"]), D("200"))
        self.assertEqual(D(snapshot["seconds"]), D("7200"))
        self.assertEqual(D(snapshot["cost"]), D("90"))
        self.assertEqual(D(snapshot["calculated_price"]), D("135"))

    def test_revision_is_preserved_after_adding_more_materials(self):
        previous = self.project.current_revision_id
        add_material(
            owner=self.owner,
            project_id=self.project.pk,
            material_id=self.material.pk,
            quantity=D("100"),
            manual_unit_cost=D(".1"),
        )
        self.assertEqual(self.project.revisions.get(pk=previous).materials.count(), 0)
        self.assertEqual(self.project.revisions.count(), 2)

    def test_alternative_requires_explicit_selection_and_adjusted_quantity(self):
        line = add_material(
            owner=self.owner,
            project_id=self.project.pk,
            material_id=self.material.pk,
            quantity=D("100"),
            manual_unit_cost=D(".1"),
        )
        other = Material.objects.create(
            owner=self.owner, name="Fio alternativo", kind="yarn", unit="g"
        )
        alternative = add_alternative(
            owner=self.owner, line_id=line.pk, material_id=other.pk, quantity=D("120")
        )
        self.project.refresh_from_db()
        new_line = self.project.current_revision.materials.get()
        original = snapshot_project(
            owner=self.owner, revision_id=self.project.current_revision_id, quantity=5
        )
        chosen = snapshot_project(
            owner=self.owner,
            revision_id=self.project.current_revision_id,
            quantity=5,
            choices={str(new_line.pk): str(alternative.pk)},
        )
        self.assertEqual(original["materials"][0]["material"], str(self.material.pk))
        self.assertEqual(chosen["materials"][0]["material"], str(other.pk))
        self.assertEqual(D(chosen["materials"][0]["quantity"]), D("120"))
        self.assertFalse(chosen["complete"])

    def test_foreign_owner_is_denied(self):
        other = get_user_model().objects.create_user(
            username="other", email="other@example.test"
        )
        with self.assertRaises(Http404):
            snapshot_project(
                owner=other, revision_id=self.project.current_revision_id, quantity=1
            )


class RevisionEditingTests(TestCase):
    def test_editing_and_removing_lines_preserves_previous_revision(self):
        from .services import edit_line

        owner = get_user_model().objects.create_user(
            username="editor", email="editor@example.test"
        )
        material = Material.objects.create(
            owner=owner, name="Fio", kind="yarn", unit="g"
        )
        project = create_project(owner=owner, name="Peça")
        old = add_material(
            owner=owner,
            project_id=project.pk,
            material_id=material.pk,
            quantity=Decimal("120"),
            manual_unit_cost=Decimal(".1"),
        )
        edit_line(
            owner=owner,
            line_id=old.pk,
            material_id=material.pk,
            quantity=Decimal("150"),
        )
        old.refresh_from_db()
        self.assertEqual(old.base_quantity, Decimal("120"))
        project.refresh_from_db()
        new = project.current_revision.materials.get()
        self.assertEqual(new.base_quantity, Decimal("150"))
        edit_line(owner=owner, line_id=new.pk, remove=True)
        project.refresh_from_db()
        self.assertEqual(project.current_revision.materials.count(), 0)
        self.assertEqual(old.revision.materials.count(), 1)
