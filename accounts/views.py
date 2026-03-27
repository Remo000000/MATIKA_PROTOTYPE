from __future__ import annotations

from django.contrib import messages
from django.contrib.auth import login, logout
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse_lazy
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.utils.translation import gettext_lazy as _
from django.views import View
from django.views.decorators.http import require_POST
from django.views.generic import FormView, ListView, UpdateView
from django_ratelimit.decorators import ratelimit

from accounts.forms import LoginForm, ProfileForm, RegisterForm
from accounts.mixins import AdminRequiredMixin
from accounts import notification_kinds as nk
from accounts.models import Notification, ProfileChangeRequest, User
from accounts.notifications import notify_organization_admins, notify_user
from university.scope import get_default_organization


def ratelimited_error(request: HttpRequest, exception) -> HttpResponse:
    return HttpResponse(_("Too many attempts. Please try again later."), status=429)


@method_decorator(ratelimit(key="ip", rate="5/m", method="POST"), name="dispatch")
class LoginView(FormView):
    template_name = "accounts/login.html"
    form_class = LoginForm
    success_url = reverse_lazy("dashboard:home")

    def form_valid(self, form):
        login(self.request, form.cleaned_data["user"])
        messages.success(self.request, _("Welcome back!"))
        return super().form_valid(form)


@method_decorator(require_POST, name="dispatch")
class LogoutView(View):
    """State change via POST only (CSRF-protected form in templates)."""

    def post(self, request: HttpRequest) -> HttpResponse:
        logout(request)
        return redirect("accounts:login")


@method_decorator(ratelimit(key="ip", rate="10/h", method="POST"), name="dispatch")
class RegisterView(FormView):
    template_name = "accounts/register.html"
    form_class = RegisterForm
    success_url = reverse_lazy("dashboard:home")

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["organization"] = get_default_organization()
        return kwargs

    def form_valid(self, form):
        user = form.save()
        login(self.request, user)
        messages.success(self.request, _("Account created."))
        return super().form_valid(form)


class ProfileView(LoginRequiredMixin, UpdateView):
    template_name = "accounts/profile.html"
    form_class = ProfileForm
    success_url = reverse_lazy("accounts:profile")

    def get_object(self, queryset=None):
        return self.request.user

    def form_valid(self, form):
        # Fresh row from DB (session-cached request.user can be stale in edge cases).
        user = User.objects.get(pk=self.request.user.pk)
        if user.is_admin:
            messages.success(self.request, _("Profile updated."))
            return super().form_valid(form)

        new_name = (
            (form.cleaned_data.get("full_name") if form.cleaned_data else None)
            or self.request.POST.get("full_name")
            or ""
        ).strip()
        current = (user.full_name or "").strip()
        if new_name == current:
            messages.info(self.request, _("No changes to submit."))
            return redirect(self.success_url)

        ProfileChangeRequest.objects.filter(
            user=user,
            status=ProfileChangeRequest.Status.PENDING,
        ).delete()
        pcr = ProfileChangeRequest.objects.create(
            user=user,
            proposed_full_name=new_name,
        )
        notify_organization_admins(
            organization_id=user.organization_id,
            kind=nk.PROFILE_CHANGE_PENDING,
            payload={"email": user.email, "name": new_name},
            profile_change_request=pcr,
        )
        messages.success(
            self.request,
            _("Your request was sent to an administrator. The name will update after approval."),
        )
        return redirect(self.success_url)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        user = self.request.user
        teacher_profile = getattr(user, "teacher_profile", None)
        student_profile = getattr(user, "student_profile", None)
        ctx["teacher_profile"] = teacher_profile
        ctx["student_profile"] = student_profile
        ctx["pending_profile_request"] = ProfileChangeRequest.objects.filter(
            user=user,
            status=ProfileChangeRequest.Status.PENDING,
        ).first()
        return ctx


class NotificationListView(LoginRequiredMixin, ListView):
    template_name = "accounts/notifications.html"
    model = Notification
    paginate_by = 20

    def get_queryset(self):
        return Notification.objects.filter(user=self.request.user).select_related(
            "profile_change_request",
            "profile_change_request__user",
        )


@require_POST
def notification_mark_read(request: HttpRequest, pk: int) -> HttpResponse:
    if not request.user.is_authenticated:
        return redirect("accounts:login")
    notif = get_object_or_404(Notification, pk=pk, user=request.user)
    notif.is_read = True
    notif.save(update_fields=["is_read"])
    return redirect("accounts:notifications")


@method_decorator(require_POST, name="dispatch")
class ApproveProfileChangeView(AdminRequiredMixin, View):
    def post(self, request: HttpRequest, pk: int) -> HttpResponse:
        req = get_object_or_404(
            ProfileChangeRequest.objects.select_related("user"),
            pk=pk,
            user__organization_id=request.user.organization_id,
            status=ProfileChangeRequest.Status.PENDING,
        )
        u = req.user
        u.full_name = req.proposed_full_name
        u.save(update_fields=["full_name"])
        req.status = ProfileChangeRequest.Status.APPROVED
        req.reviewed_at = timezone.now()
        req.reviewed_by = request.user
        req.save(update_fields=["status", "reviewed_at", "reviewed_by"])
        notify_user(
            user=u,
            kind=nk.PROFILE_CHANGE_APPROVED,
            payload={"name": req.proposed_full_name},
        )
        messages.success(
            request,
            _("Approved name change for %(email)s.") % {"email": u.email},
        )
        Notification.objects.filter(
            user=request.user,
            profile_change_request_id=req.pk,
        ).update(is_read=True)
        return redirect("accounts:notifications")


@method_decorator(require_POST, name="dispatch")
class RejectProfileChangeView(AdminRequiredMixin, View):
    def post(self, request: HttpRequest, pk: int) -> HttpResponse:
        req = get_object_or_404(
            ProfileChangeRequest.objects.select_related("user"),
            pk=pk,
            user__organization_id=request.user.organization_id,
            status=ProfileChangeRequest.Status.PENDING,
        )
        reason = (request.POST.get("reason") or "").strip()
        req.status = ProfileChangeRequest.Status.REJECTED
        req.reviewed_at = timezone.now()
        req.reviewed_by = request.user
        req.rejection_reason = reason
        req.save(update_fields=["status", "reviewed_at", "reviewed_by", "rejection_reason"])
        notify_user(
            user=req.user,
            kind=nk.PROFILE_CHANGE_REJECTED,
            payload={"reason": reason},
        )
        messages.success(
            request,
            _("Rejected name change for %(email)s.") % {"email": req.user.email},
        )
        Notification.objects.filter(
            user=request.user,
            profile_change_request_id=req.pk,
        ).update(is_read=True)
        return redirect("accounts:notifications")

