"""Template filters: translate DB seed strings (English) via gettext."""

from __future__ import annotations

from django import template
from django.utils.translation import gettext as _

from matika.demo_seed_aliases import to_english_seed

register = template.Library()


@register.filter
def trans_seed(value):
    """Translate faculty/department/discipline names (English or localized demo strings)."""
    if value is None or value == "":
        return value
    return _(to_english_seed(str(value)))


@register.filter
def trans_algorithm_message(value):
    """Translate known AlgorithmRunLog messages; soften raw SQLite errors for end users."""
    if value is None or value == "":
        return value
    s = str(value)
    known = {
        "Greedy generation completed": _("Greedy generation completed"),
        "GA optimisation completed": _("GA optimisation completed"),
        "Generation skipped: missing requirements, time slots, or rooms": _(
            "Generation skipped: missing requirements, time slots, or rooms"
        ),
        "Optimisation skipped apply: hard-constraint violations in best candidate": _(
            "Optimisation skipped apply: hard-constraint violations in best candidate"
        ),
    }
    if s in known:
        return known[s]
    low = s.lower()
    if "database is locked" in low:
        return _("Database is busy. Close other apps using the database and try again.")
    if "no such table:" in low:
        return _("Database schema is outdated. Run migrations: python manage.py migrate")
    if s.startswith("Error during GA optimisation:"):
        return _("Error during optimisation.") + " " + s.split(":", 1)[-1].strip()
    return s
