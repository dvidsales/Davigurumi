"""Demo uses a separate owner; authentication continues to belong to the real user."""

import uuid
from decimal import Decimal
from django import forms
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.db import transaction
from django.shortcuts import redirect, render, get_object_or_404
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_POST
from materials.forms import MaterialForm
from materials.models import Material
from materials.services import create_material
from materials.stock import begin_operation, finish
from projects.models import Project
from projects.services import create_project, add_material
from sales.models import Client
from .models import DemoWorkspace


class DemoMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.real_user = request.user
        request.demo_workspace = None
        if (
            request.user.is_authenticated
            and request.session.get("demo_workspace")
            and not request.path.startswith(("/conta/", "/demo/"))
        ):
            workspace = (
                DemoWorkspace.objects.filter(
                    pk=request.session["demo_workspace"], owner=request.real_user
                )
                .select_related("demo_user")
                .first()
            )
            if workspace:
                request.demo_workspace = workspace
                request.user = workspace.demo_user
            else:
                request.session.pop("demo_workspace", None)
        return self.get_response(request)


@transaction.atomic
def create_demo(owner):
    get_user_model().objects.select_for_update().get(pk=owner.pk)
    existing = DemoWorkspace.objects.filter(owner=owner).first()
    if existing:
        return existing
    identity = uuid.uuid4().hex
    user = get_user_model().objects.create_user(
        username="demo_" + identity,
        email="demo_" + identity + "@example.test",
        first_name="Demonstração",
        password=None,
    )
    workspace = DemoWorkspace.objects.create(owner=owner, demo_user=user)
    form = MaterialForm(
        {
            "name": "Fio de demonstração",
            "kind": "yarn",
            "unit": "g",
            "initial_quantity": "508",
            "initial_unit_cost": ".10",
            "request_key": uuid.uuid4(),
            "color": "Azul",
        }
    )
    if not form.is_valid():
        raise ValidationError("Não foi possível criar a demonstração.")
    material = create_material(form=form, owner=user)
    project = create_project(
        owner=user,
        name="Boneco de demonstração",
        technique="Crochê",
        description="Exemplo fictício para experimentar o fluxo.",
        estimated_seconds=3600,
        hourly_rate=Decimal("30"),
    )
    add_material(
        owner=user,
        project_id=project.pk,
        material_id=material.pk,
        quantity=Decimal("120"),
    )
    Client.objects.create(
        owner=user, name="Cliente fictício", contact="exemplo@example.test"
    )
    return workspace


class CopyForm(forms.Form):
    key = forms.UUIDField(widget=forms.HiddenInput, initial=uuid.uuid4)
    materials = forms.ModelMultipleChoiceField(
        label="Materiais para copiar",
        queryset=Material.objects.none(),
        required=False,
        widget=forms.CheckboxSelectMultiple,
    )
    projects = forms.ModelMultipleChoiceField(
        label="Projetos para copiar (incluem seus materiais)",
        queryset=Project.objects.none(),
        required=False,
        widget=forms.CheckboxSelectMultiple,
    )
    password = forms.CharField(
        label="Confirme a senha da conta real", widget=forms.PasswordInput
    )

    def __init__(self, *args, workspace, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["materials"].queryset = Material.objects.filter(
            owner=workspace.demo_user
        )
        self.fields["projects"].queryset = Project.objects.filter(
            owner=workspace.demo_user
        )


@transaction.atomic
def copy_demo(*, owner, workspace, material_ids, project_ids, key):
    op, repeated = begin_operation(
        owner,
        key,
        "demo_copy",
        {
            "workspace": workspace.pk,
            "materials": sorted(map(str, material_ids)),
            "projects": sorted(map(str, project_ids)),
        },
    )
    if repeated:
        return op.result
    if workspace.owner_id != owner.pk:
        raise ValidationError("Espaço de demonstração não pertence à conta.")
    projects = list(
        Project.objects.filter(
            owner=workspace.demo_user, pk__in=project_ids
        ).select_related("current_revision")
    )
    if len(projects) != len(project_ids):
        raise ValidationError("Projeto inválido.")
    material_ids = set(material_ids)
    for project in projects:
        if Project.objects.filter(owner=owner, name__iexact=project.name).exists():
            raise ValidationError(
                "Já existe um projeto com este nome. Ajuste o nome na demonstração antes de copiar."
            )
        material_ids.update(
            project.current_revision.materials.values_list("material_id", flat=True)
        )
    mapping = {}
    for material in Material.objects.filter(
        owner=workspace.demo_user, pk__in=material_ids
    ):
        if Material.objects.filter(
            owner=owner,
            name__iexact=material.name,
            kind=material.kind,
            unit=material.unit,
        ).exists():
            raise ValidationError(
                "Material duplicado na conta real. Renomeie o exemplo antes de copiar."
            )
        payload = {
            field: getattr(material, field) for field in MaterialForm.Meta.fields
        }
        payload.update(
            initial_quantity="0",
            initial_unit_cost="",
            request_key=uuid.uuid5(key, str(material.pk)),
        )
        form = MaterialForm(payload)
        if not form.is_valid():
            raise ValidationError("Cadastro do exemplo inválido.")
        mapping[material.pk] = create_material(form=form, owner=owner)
    if len(mapping) != len(material_ids):
        raise ValidationError("Material inválido.")
    created = []
    for project in projects:
        revision = project.current_revision
        new = create_project(
            owner=owner,
            name=revision.name,
            description=revision.description,
            technique=revision.technique,
            base_quantity=revision.base_quantity,
        )
        for line in revision.materials.all():
            add_material(
                owner=owner,
                project_id=new.pk,
                material_id=mapping[line.material_id].pk,
                quantity=line.base_quantity,
            )
        created.append(str(new.pk))
    return finish(
        op,
        {"materials": [str(row.pk) for row in mapping.values()], "projects": created},
    )


@never_cache
@login_required
def index(request):
    workspace = DemoWorkspace.objects.filter(owner=request.user).first()
    form = CopyForm(request.POST or None, workspace=workspace) if workspace else None
    if request.method == "POST" and form and form.is_valid():
        if not request.user.check_password(form.cleaned_data["password"]):
            form.add_error("password", "Senha incorreta.")
        elif not form.cleaned_data["materials"] and not form.cleaned_data["projects"]:
            form.add_error(None, "Selecione ao menos um cadastro.")
        else:
            try:
                result = copy_demo(
                    owner=request.user,
                    workspace=workspace,
                    material_ids=list(
                        form.cleaned_data["materials"].values_list("pk", flat=True)
                    ),
                    project_ids=list(
                        form.cleaned_data["projects"].values_list("pk", flat=True)
                    ),
                    key=form.cleaned_data["key"],
                )
            except ValidationError as exc:
                form.add_error(None, exc)
            else:
                request.session.pop("demo_workspace", None)
                messages.success(
                    request,
                    f"Cadastros copiados: {len(result['materials'])} materiais e {len(result['projects'])} projetos. Estoque e preços devem ser preenchidos com seus dados reais.",
                )
                return redirect("dashboard")
    return render(
        request,
        "accounts/demo.html",
        {
            "workspace": workspace,
            "form": form,
            "demo_active": bool(request.session.get("demo_workspace")),
        },
    )


@require_POST
@login_required
def switch(request):
    if request.POST.get("action") == "exit":
        request.session.pop("demo_workspace", None)
    else:
        request.session["demo_workspace"] = str(create_demo(request.user).pk)
    return redirect("dashboard")
