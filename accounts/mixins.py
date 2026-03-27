from __future__ import annotations

from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect


class RoleRequiredMixin(LoginRequiredMixin):
    allowed_roles: set[str] = set()

    def dispatch(self, request, *args, **kwargs):
        user = request.user
        if not user.is_authenticated:
            return self.handle_no_permission()
        if self.allowed_roles and getattr(user, "role", None) not in self.allowed_roles and not getattr(user, "is_superuser", False):
            raise PermissionDenied
        return super().dispatch(request, *args, **kwargs)


class AdminRequiredMixin(RoleRequiredMixin):
    allowed_roles = {"admin"}

    def dispatch(self, request, *args, **kwargs):
        user = request.user
        if not user.is_authenticated:
            return self.handle_no_permission()
        if not getattr(user, "is_admin", False):
            # UX rule: non-admin users are redirected to their own schedule page.
            return redirect("scheduling:my_schedule")
        return super().dispatch(request, *args, **kwargs)


class TeacherRequiredMixin(RoleRequiredMixin):
    allowed_roles = {"teacher", "admin"}


class StudentRequiredMixin(RoleRequiredMixin):
    allowed_roles = {"student", "admin"}

