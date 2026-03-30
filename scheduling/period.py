from __future__ import annotations

from django.http import HttpRequest
from django.utils.translation import gettext as _

from scheduling.models import AcademicPeriod

SESSION_KEY = "selected_academic_period_id"


def ensure_default_period(organization_id: int) -> AcademicPeriod:
    """One default period per org; marks it as current."""
    period, _created = AcademicPeriod.objects.get_or_create(
        organization_id=organization_id,
        slug="default",
        defaults={"name": _("Default period"), "is_current": True},
    )
    AcademicPeriod.objects.filter(organization_id=organization_id).exclude(pk=period.pk).update(is_current=False)
    period.is_current = True
    period.save(update_fields=["is_current"])
    return period


def get_period_for_request(request: HttpRequest, organization_id: int) -> AcademicPeriod:
    """
    Resolve academic period from GET/POST ?period=, then session, then is_current, then newest.
    Creates a default period if none exist.
    """
    qs = AcademicPeriod.objects.filter(organization_id=organization_id)
    raw = request.GET.get("period") or request.POST.get("period")
    pid: int | None = None
    if raw not in (None, ""):
        try:
            pid = int(raw)
        except (TypeError, ValueError):
            pid = None
    if pid is None:
        sid = request.session.get(SESSION_KEY)
        if sid is not None:
            try:
                pid = int(sid)
            except (TypeError, ValueError):
                pid = None
    if pid is not None:
        p = qs.filter(pk=pid).first()
        if p:
            request.session[SESSION_KEY] = p.pk
            return p
    p = qs.filter(is_current=True).first()
    if p:
        request.session[SESSION_KEY] = p.pk
        return p
    p = qs.order_by("-id").first()
    if p:
        request.session[SESSION_KEY] = p.pk
        return p
    return ensure_default_period(organization_id)
