from __future__ import annotations

from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _


class UserManager(BaseUserManager):
    use_in_migrations = True

    def _create_user(self, email: str, password: str | None, **extra_fields):
        if not email:
            raise ValueError("Email is required")
        if "organization" not in extra_fields and "organization_id" not in extra_fields:
            from university.scope import get_default_organization

            extra_fields["organization"] = get_default_organization()
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_user(self, email: str, password: str | None = None, **extra_fields):
        extra_fields.setdefault("is_staff", False)
        extra_fields.setdefault("is_superuser", False)
        return self._create_user(email, password, **extra_fields)

    def create_superuser(self, email: str, password: str, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("role", User.Role.ADMIN)
        return self._create_user(email, password, **extra_fields)


class User(AbstractUser):
    class Role(models.TextChoices):
        ADMIN = "admin", _("Administrator")
        TEACHER = "teacher", _("Teacher")
        STUDENT = "student", _("Student")

    username = None
    organization = models.ForeignKey(
        "university.Organization",
        on_delete=models.CASCADE,
        related_name="users",
        verbose_name=_("Organization"),
    )
    email = models.EmailField(_("email address"), unique=True)
    role = models.CharField(
        max_length=16,
        choices=Role.choices,
        default=Role.STUDENT,
        verbose_name=_("Role"),
    )
    full_name = models.CharField(_("Full name"), max_length=255, blank=True)
    email_verified_at = models.DateTimeField(_("Email verified at"), null=True, blank=True)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS: list[str] = []

    objects = UserManager()

    def __str__(self) -> str:
        return self.email

    def get_short_name(self) -> str:
        return self.full_name or self.email.split("@", 1)[0]

    @property
    def is_admin(self) -> bool:
        return self.role == self.Role.ADMIN or self.is_superuser

    @property
    def is_teacher(self) -> bool:
        return self.role == self.Role.TEACHER

    @property
    def is_student(self) -> bool:
        return self.role == self.Role.STUDENT


class Notification(models.Model):
    user = models.ForeignKey("accounts.User", on_delete=models.CASCADE, related_name="notifications")
    kind = models.CharField(
        max_length=64,
        blank=True,
        default="",
        db_index=True,
        help_text="Stable key for i18n rendering (empty = legacy title/body).",
    )
    payload = models.JSONField(default=dict, blank=True)
    title = models.CharField(max_length=200, blank=True)
    body = models.TextField(blank=True)
    created_at = models.DateTimeField(default=timezone.now)
    is_read = models.BooleanField(default=False)
    profile_change_request = models.ForeignKey(
        "accounts.ProfileChangeRequest",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="notifications",
    )

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        label = self.title or self.kind or "notification"
        return f"{self.user_id}: {label}"


class ProfileChangeRequest(models.Model):
    """Teacher/student full name changes require admin approval before applying."""

    class Status(models.TextChoices):
        PENDING = "pending", _("Pending")
        APPROVED = "approved", _("Approved")
        REJECTED = "rejected", _("Rejected")

    user = models.ForeignKey(
        "accounts.User",
        on_delete=models.CASCADE,
        related_name="profile_change_requests",
    )
    proposed_full_name = models.CharField(_("Proposed full name"), max_length=255)
    status = models.CharField(
        max_length=16,
        choices=Status.choices,
        default=Status.PENDING,
        db_index=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    reviewed_by = models.ForeignKey(
        "accounts.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reviewed_profile_change_requests",
    )
    rejection_reason = models.TextField(_("Rejection reason"), blank=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = _("Profile change request")
        verbose_name_plural = _("Profile change requests")
        indexes = [
            models.Index(fields=["user", "status"]),
        ]

    def __str__(self) -> str:
        return f"{self.user_id} → {self.proposed_full_name!r} ({self.status})"


class AdminActionLog(models.Model):
    actor = models.ForeignKey("accounts.User", on_delete=models.SET_NULL, null=True, blank=True, related_name="admin_logs")
    method = models.CharField(max_length=12, blank=True)
    path = models.CharField(max_length=500, blank=True)
    ip = models.GenericIPAddressField(null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now)
    extra = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.created_at:%Y-%m-%d %H:%M} {self.method} {self.path}"


class EmailVerificationToken(models.Model):
    user = models.ForeignKey("accounts.User", on_delete=models.CASCADE, related_name="email_verification_tokens")
    token = models.CharField(max_length=128, unique=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()

    class Meta:
        ordering = ["-created_at"]
        verbose_name = _("Email verification token")
        verbose_name_plural = _("Email verification tokens")

    def __str__(self) -> str:
        return f"{self.user_id}: {self.token[:8]}…"


class TeacherInvite(models.Model):
    """Optional invite code so a teacher can self-register without admin approval (when mode is pending)."""

    organization = models.ForeignKey(
        "university.Organization",
        on_delete=models.CASCADE,
        related_name="teacher_invites",
    )
    department = models.ForeignKey(
        "university.Department",
        on_delete=models.CASCADE,
        related_name="teacher_invites",
    )
    code = models.CharField(max_length=64, unique=True, db_index=True)
    max_uses = models.PositiveIntegerField(default=1)
    used_count = models.PositiveIntegerField(default=0)
    expires_at = models.DateTimeField(null=True, blank=True)
    note = models.CharField(max_length=255, blank=True)

    class Meta:
        verbose_name = _("Teacher invite")
        verbose_name_plural = _("Teacher invites")

    def __str__(self) -> str:
        return self.code

