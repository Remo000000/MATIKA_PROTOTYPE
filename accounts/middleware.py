from __future__ import annotations

import logging

from django.shortcuts import redirect
from django.utils.deprecation import MiddlewareMixin

from accounts.models import AdminActionLog

logger = logging.getLogger(__name__)


class AdminActionLogMiddleware(MiddlewareMixin):
    """
    Minimal audit trail for admin actions.
    We only store requests from authenticated admin users and only for mutating HTTP methods.
    """

    MUTATING = {"POST", "PUT", "PATCH", "DELETE"}
    # Do not audit auth forms (passwords) or noisy endpoints; we never log request bodies.
    SKIP_AUDIT_PATH_PREFIXES = (
        "/admin/login/",
        "/accounts/login/",
        "/accounts/register/",
        "/accounts/logout/",
    )

    def process_request(self, request):
        user = getattr(request, "user", None)
        # Role UX policy: teacher/student trying to open admin pages
        # are redirected to personal schedule.
        if (
            request.path.startswith("/admin")
            and user
            and getattr(user, "is_authenticated", False)
            and not getattr(user, "is_admin", False)
        ):
            return redirect("scheduling:my_schedule")
        return None

    def process_response(self, request, response):
        try:
            user = getattr(request, "user", None)
            path = request.path or ""
            if any(path.startswith(p) for p in self.SKIP_AUDIT_PATH_PREFIXES):
                return response
            if (
                user
                and getattr(user, "is_authenticated", False)
                and getattr(user, "is_admin", False)
                and request.method in self.MUTATING
            ):
                AdminActionLog.objects.create(
                    actor=user,
                    method=request.method,
                    path=request.get_full_path()[:500],
                    ip=self._get_ip(request),
                    extra={
                        "status_code": getattr(response, "status_code", None),
                        "content_type": response.get("Content-Type", ""),
                        "audit": "path_and_meta_only",
                    },
                )
        except Exception:
            logger.exception("AdminActionLogMiddleware failed to write audit row")
        return response

    @staticmethod
    def _get_ip(request) -> str | None:
        xff = request.META.get("HTTP_X_FORWARDED_FOR")
        if xff:
            return xff.split(",")[0].strip()
        return request.META.get("REMOTE_ADDR")

