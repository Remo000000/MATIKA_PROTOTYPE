"""
Single source of truth for lesson visibility (HTML schedule, API, ICS, XLSX).
"""

from __future__ import annotations

from django.core.exceptions import PermissionDenied
from django.db.models import QuerySet
from django.http import HttpRequest
from django.utils.translation import gettext_lazy as _

from scheduling.models import Lesson
from scheduling.period import get_period_for_request


def parse_optional_int(value: str | None) -> int | None:
    raw = (value or "").strip()
    if not raw or raw.lower() in {"none", "null", "undefined"}:
        return None
    try:
        return int(raw)
    except (TypeError, ValueError):
        return None


def _query_params(request: HttpRequest):
    return getattr(request, "query_params", request.GET)


def lessons_queryset_for_request(request: HttpRequest, *, user=None) -> QuerySet[Lesson]:
    """
    Org + academic period + role-based scope. Raises PermissionDenied when profile is missing
    or role cannot access the resource.
    """
    user = user or request.user
    oid = getattr(user, "organization_id", None)
    if oid is None:
        raise PermissionDenied(_("No organization context."))
    period = get_period_for_request(request, oid)
    qp = _query_params(request)
    qs = Lesson.objects.filter(
        group__department__faculty__organization_id=oid,
        academic_period_id=period.id,
    ).select_related(
        "group",
        "discipline",
        "teacher__user",
        "room",
        "timeslot",
        "academic_period",
    )
    if user.is_student:
        if not hasattr(user, "student_profile"):
            raise PermissionDenied(_("Student profile is not configured."))
        return qs.filter(group=user.student_profile.group).exclude(is_draft=True).order_by(
            "timeslot__day_of_week",
            "timeslot__period",
        )
    if user.is_teacher:
        if not hasattr(user, "teacher_profile"):
            raise PermissionDenied(_("Teacher profile is not configured."))
        return qs.filter(teacher=user.teacher_profile).order_by(
            "timeslot__day_of_week",
            "timeslot__period",
        )
    if user.is_admin:
        qs = qs.order_by("timeslot__day_of_week", "timeslot__period")
        group_id = parse_optional_int(qp.get("group"))
        teacher_id = parse_optional_int(qp.get("teacher"))
        room_id = parse_optional_int(qp.get("room"))
        if group_id:
            qs = qs.filter(group_id=group_id)
        if teacher_id:
            qs = qs.filter(teacher_id=teacher_id)
        if room_id:
            qs = qs.filter(room_id=room_id)
        return qs
    raise PermissionDenied(_("You cannot access this resource."))
