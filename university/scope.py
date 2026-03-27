from __future__ import annotations

from typing import TYPE_CHECKING

from django.conf import settings
from django.db.models import QuerySet

from university.models import Organization

if TYPE_CHECKING:
    from django.http import HttpRequest


def get_default_organization() -> Organization:
    slug = getattr(settings, "DEFAULT_ORGANIZATION_SLUG", "default")
    org, _ = Organization.objects.get_or_create(
        slug=slug,
        defaults={"name": getattr(settings, "DEFAULT_ORGANIZATION_NAME", "Default organization")},
    )
    return org


def lesson_qs_for_organization(org_id: int | None, academic_period_id: int | None = None) -> QuerySet:
    from scheduling.models import Lesson

    if org_id is None:
        return Lesson.objects.none()
    qs = Lesson.objects.filter(group__department__faculty__organization_id=org_id)
    if academic_period_id is not None:
        qs = qs.filter(academic_period_id=academic_period_id)
    return qs


def filter_queryset_by_organization(qs: QuerySet, org_id: int | None) -> QuerySet:
    """Narrow a Lesson queryset to one organization (when org_id is set)."""
    if org_id is None:
        return qs
    return qs.filter(group__department__faculty__organization_id=org_id)


def request_organization(request: HttpRequest) -> Organization | None:
    user = getattr(request, "user", None)
    if user and getattr(user, "is_authenticated", False) and getattr(user, "organization_id", None):
        return user.organization
    return None
