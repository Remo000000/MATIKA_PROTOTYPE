"""Template filters: translate DB seed strings (English) via gettext."""

from __future__ import annotations

from django import template
from django.utils.translation import gettext as _

register = template.Library()


@register.filter
def trans_seed(value):
    """Translate faculty/department/discipline names stored in English in the database."""
    if value is None or value == "":
        return value
    return _(str(value))
