from __future__ import annotations

from django import template

register = template.Library()


@register.filter
def get_item(d, key):
    if d is None:
        return None
    try:
        return d.get(key)
    except Exception:
        return None


@register.filter
def discipline_chip_tone(discipline_id):
    """Stable 0..4 from id for lesson chip color (no keyword heuristics)."""
    try:
        return int(discipline_id) % 5
    except (TypeError, ValueError):
        return 0

