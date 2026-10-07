from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.cache import never_cache
from .forms import MaterialForm
from .models import Material
from .services import create_material

@never_cache
@login_required
def index(request):
    query = request.GET.get("q", "").strip()[:160]
    materials = Material.objects.filter(owner=request.user).prefetch_related("movements")
    if query:
        materials = materials.filter(Q(name__icontains=query) | Q(brand__icontains=query) | Q(color__icontains=query))
    return render(request, "materials/index.html", {"page_obj": Paginator(materials, 20).get_page(request.GET.get("page")), "query": query})

@never_cache
@login_required
def create(request):
    form = MaterialForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            material = create_material(form=form, owner=request.user)
        except ValidationError as exc:
            form.add_error(None, exc)
        else:
            messages.success(request, "Material cadastrado. O histórico de estoque está disponível abaixo.")
            return redirect("materials:detail", pk=material.pk)
    return render(request, "materials/form.html", {"form": form})

@never_cache
@login_required
def detail(request, pk):
    material = get_object_or_404(Material.objects.prefetch_related("movements"), pk=pk, owner=request.user)
    return render(request, "materials/detail.html", {"material": material})
