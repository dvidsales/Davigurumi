from decimal import Decimal
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, render, redirect
from django.views.decorators.cache import never_cache
from .models import Project, ProjectMaterial
from .forms import ProjectForm, MaterialLineForm, AlternativeForm
from . import services


@never_cache
@login_required
def index(request):
    return render(
        request,
        "projects/index.html",
        {
            "page_obj": Paginator(
                Project.objects.filter(owner=request.user), 20
            ).get_page(request.GET.get("page"))
        },
    )


@never_cache
@login_required
def create(request):
    form = ProjectForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        values = form.cleaned_data.copy()
        values["estimated_seconds"] = int(values.pop("hours") * 3600)
        values["percentage"] /= Decimal(100)
        values["fee"] /= Decimal(100)
        try:
            project = services.create_project(owner=request.user, **values)
        except (ValidationError, ValueError) as exc:
            form.add_error(
                None, exc.messages if isinstance(exc, ValidationError) else str(exc)
            )
        else:
            return redirect("projects:detail", pk=project.pk)
    return render(
        request,
        "generic_form.html",
        {
            "form": form,
            "heading": "Novo projeto",
            "description": "A ficha é genérica: crochê, costura e outras técnicas.",
        },
    )


@never_cache
@login_required
def detail(request, pk):
    project = get_object_or_404(
        Project.objects.select_related("current_revision"), pk=pk, owner=request.user
    )
    snapshot = services.snapshot_project(
        owner=request.user,
        revision_id=project.current_revision_id,
        quantity=project.current_revision.base_quantity,
    )
    return render(
        request,
        "projects/detail.html",
        {
            "project": project,
            "revision": project.current_revision,
            "snapshot": snapshot,
        },
    )


@never_cache
@login_required
def material(request, pk):
    project = get_object_or_404(Project, pk=pk, owner=request.user)
    form = MaterialLineForm(request.POST or None, owner=request.user)
    if request.method == "POST" and form.is_valid():
        data = form.cleaned_data
        try:
            services.add_material(
                owner=request.user,
                project_id=pk,
                material_id=data["material"].pk,
                quantity=data["quantity"],
                unit=data["unit"] or None,
                manual_unit_cost=data["manual_unit_cost"],
            )
        except ValidationError as exc:
            form.add_error(None, exc.messages)
        else:
            return redirect("projects:detail", pk=pk)
    return render(
        request,
        "generic_form.html",
        {
            "form": form,
            "heading": "Adicionar material à ficha",
            "description": "Uma nova revisão preserva as fichas anteriores.",
        },
    )


@never_cache
@login_required
def alternative(request, pk):
    line = get_object_or_404(
        ProjectMaterial, pk=pk, revision__project__owner=request.user
    )
    form = AlternativeForm(request.POST or None, owner=request.user)
    if request.method == "POST" and form.is_valid():
        data = form.cleaned_data
        try:
            services.add_alternative(
                owner=request.user,
                line_id=pk,
                material_id=data["material"].pk,
                quantity=data["quantity"],
                note=data["note"],
            )
        except ValidationError as exc:
            form.add_error(None, exc.messages)
        else:
            return redirect("projects:detail", pk=line.revision.project_id)
    return render(
        request,
        "generic_form.html",
        {
            "form": form,
            "heading": "Cadastrar alternativa",
            "description": "Alternativas não são aplicadas automaticamente nem equivalentes por definição.",
        },
    )


@never_cache
@login_required
def edit(request, pk):
    project = get_object_or_404(Project, pk=pk, owner=request.user)
    revision = project.current_revision
    initial = {
        field: getattr(revision, field)
        for field in (
            "name",
            "description",
            "technique",
            "base_quantity",
            "hourly_rate",
            "additional_cost",
            "mode",
        )
    }
    initial.update(
        hours=Decimal(revision.estimated_seconds) / 3600,
        percentage=revision.percentage * 100,
        fee=revision.fee * 100,
        notes=project.notes,
    )
    form = ProjectForm(request.POST or None, initial=initial)
    if request.method == "POST" and form.is_valid():
        values = form.cleaned_data.copy()
        values["estimated_seconds"] = int(values.pop("hours") * 3600)
        values["percentage"] /= 100
        values["fee"] /= 100
        try:
            services.edit_project(owner=request.user, project_id=pk, **values)
        except (ValidationError, ValueError) as exc:
            form.add_error(
                None, exc.messages if isinstance(exc, ValidationError) else str(exc)
            )
        else:
            return redirect("projects:detail", pk=pk)
    return render(
        request,
        "generic_form.html",
        {
            "form": form,
            "heading": "Editar projeto",
            "description": "Cria uma revisão. Orçamentos e fichas anteriores preservam seus valores.",
        },
    )


@never_cache
@login_required
def edit_line(request, pk):
    line = get_object_or_404(
        ProjectMaterial, pk=pk, revision__project__owner=request.user
    )
    initial = {
        field: getattr(line, field)
        for field in ("material", "quantity", "unit", "manual_unit_cost")
    }
    form = MaterialLineForm(request.POST or None, initial=initial, owner=request.user)
    if request.method == "POST":
        try:
            if request.POST.get("action") == "remove":
                services.edit_line(owner=request.user, line_id=pk, remove=True)
            elif form.is_valid():
                values = form.cleaned_data.copy()
                values["material_id"] = values.pop("material").pk
                services.edit_line(owner=request.user, line_id=pk, **values)
            else:
                return render(
                    request,
                    "generic_form.html",
                    {"form": form, "heading": "Editar material da ficha"},
                )
        except ValidationError as exc:
            form.add_error(None, exc)
        else:
            return redirect("projects:detail", pk=line.revision.project_id)
    return render(
        request,
        "generic_form.html",
        {
            "form": form,
            "heading": "Editar material da ficha",
            "remove_allowed": True,
            "description": "A edição e a remoção criam nova revisão; o histórico permanece.",
        },
    )
