from __future__ import annotations

from typing import Any

from accounts.models import Notification, ProfileChangeRequest, User


def create_notification(
    *,
    user: User,
    kind: str = "",
    payload: dict[str, Any] | None = None,
    title: str = "",
    body: str = "",
    profile_change_request: ProfileChangeRequest | None = None,
) -> Notification:
    """Create an in-app notification. Prefer ``kind`` + ``payload`` for translatable UI."""
    return Notification.objects.create(
        user=user,
        kind=kind or "",
        payload=payload or {},
        title=title or "",
        body=body or "",
        profile_change_request=profile_change_request,
    )


def notify_organization_admins(
    *,
    organization_id: int,
    kind: str = "",
    payload: dict[str, Any] | None = None,
    title: str = "",
    body: str = "",
    profile_change_request: ProfileChangeRequest | None = None,
) -> int:
    """Create an in-app notification for every admin in the organization. Returns count created."""
    admins = User.objects.filter(organization_id=organization_id, role=User.Role.ADMIN)
    n = 0
    for admin in admins:
        create_notification(
            user=admin,
            kind=kind,
            payload=payload,
            title=title,
            body=body,
            profile_change_request=profile_change_request,
        )
        n += 1
    return n


def notify_user(
    *,
    user: User,
    kind: str = "",
    payload: dict[str, Any] | None = None,
    title: str = "",
    body: str = "",
) -> Notification:
    return create_notification(
        user=user,
        kind=kind,
        payload=payload,
        title=title,
        body=body,
    )
