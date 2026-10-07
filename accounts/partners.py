"""Owner-scoped contacts, searched in-page and registered in their workflow."""

import uuid
from django import forms
from django.db.models import Q
from django.core.exceptions import ValidationError
from accounts.quotas import ensure_capacity


def search_contacts(model, owner, query):
    rows = model.objects.filter(owner=owner)
    query = query.strip()[:160]
    if query:
        condition = Q(name__icontains=query) | Q(contact__icontains=query)
        try:
            condition |= Q(pk=uuid.UUID(query))
        except ValueError:
            pass
        rows = rows.filter(condition)
    return rows


def contact_choices(form, field, model, owner, query=""):
    ids = list(search_contacts(model, owner, query).values_list("pk", flat=True)[:8])
    selected = form.data.get(field) or form.initial.get(field)
    try:
        selected = uuid.UUID(str(selected))
    except ValueError:
        selected = None
    if selected and model.objects.filter(owner=owner, pk=selected).exists():
        ids.append(selected)
    form.fields[field].queryset = model.objects.filter(owner=owner, pk__in=ids)
    form.fields[field].widget = forms.RadioSelect(choices=form.fields[field].choices)
    form.fields[field].empty_label = "Sem cadastro selecionado"
    form.fields[field].label_from_instance = (
        lambda obj: f"{obj.name} · {obj.contact or 'Sem contato'}"
    )


def validate_contact(data, field):
    name = data.get("new_" + field + "_name", "").strip()
    contact = data.get("new_" + field + "_contact", "").strip()
    if name and data.get(field):
        raise ValidationError(
            "Escolha um cadastro existente ou preencha um novo, não ambos."
        )
    if contact and not name:
        raise ValidationError("Informe o nome do novo cadastro.")
    return data


def register_contact(model, owner, name, contact=""):
    if model.objects.filter(
        owner=owner, name__iexact=name.strip(), contact__iexact=contact.strip()
    ).exists():
        raise ValidationError(
            "Este nome e contato já estão cadastrados. Busque e selecione o cadastro existente."
        )
    ensure_capacity(owner, model._meta.label_lower)
    obj = model(owner=owner, name=name.strip(), contact=contact.strip())
    obj.full_clean()
    obj.save()
    return obj
