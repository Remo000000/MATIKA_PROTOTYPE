from __future__ import annotations

import logging

from django.db.utils import DatabaseError

logger = logging.getLogger(__name__)


def sidebar_context(request):
    user = getattr(request, "user", None)
    unread_notifications = 0
    if getattr(user, "is_authenticated", False):
        try:
            unread_notifications = user.notifications.filter(is_read=False).count()
        except (AttributeError, DatabaseError) as exc:
            logger.warning("sidebar unread count failed: %s", exc)
            unread_notifications = 0
    return {
        "sidebar": {
            "is_authenticated": bool(getattr(user, "is_authenticated", False)),
            "role": getattr(user, "role", None),
            "unread_notifications": unread_notifications,
        }
    }

