from __future__ import annotations

from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _

from university.models import Discipline, Group, Organization, Room, TeacherProfile, TimeSlot


class AcademicPeriod(models.Model):
    """Semester / term: versions of the weekly timetable are scoped to a period."""

    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name="academic_periods",
        verbose_name=_("Organization"),
    )
    name = models.CharField(_("Name"), max_length=120)
    slug = models.SlugField(_("Slug"), max_length=64)
    start_date = models.DateField(_("Start date"), null=True, blank=True)
    end_date = models.DateField(_("End date"), null=True, blank=True)
    is_current = models.BooleanField(
        _("Current period"),
        default=False,
        help_text=_("Used as default when no period is selected in the session."),
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["organization", "slug"], name="uniq_academic_period_org_slug"),
        ]
        ordering = ["-start_date", "name"]
        verbose_name = _("Academic period")
        verbose_name_plural = _("Academic periods")

    def __str__(self) -> str:
        return f"{self.organization}: {self.name}"

    @property
    def localized_name(self) -> str:
        """Display name for UI; translates stored labels (e.g. semester names) for the active locale."""
        from django.utils.translation import gettext as _

        if self.slug == "default":
            return str(_("Default period"))
        return _(self.name)


class TeachingRequirement(models.Model):
    """
    A weekly requirement: group must have N sessions of a discipline taught by a teacher.
    This is the input to the generator.
    """

    group = models.ForeignKey(Group, on_delete=models.CASCADE, related_name="requirements")
    discipline = models.ForeignKey(Discipline, on_delete=models.PROTECT, related_name="requirements")
    teacher = models.ForeignKey(TeacherProfile, on_delete=models.PROTECT, related_name="requirements")
    sessions_per_week = models.PositiveIntegerField(default=1)
    min_room_capacity = models.PositiveIntegerField(default=0)

    class Meta:
        verbose_name = _("Teaching requirement")
        verbose_name_plural = _("Teaching requirements")

    def __str__(self) -> str:
        return f"{self.group} - {self.discipline} x{self.sessions_per_week}"


class Lesson(models.Model):
    """
    Scheduled lesson (one occurrence in a weekly timetable).
    """

    academic_period = models.ForeignKey(
        AcademicPeriod,
        on_delete=models.CASCADE,
        related_name="lessons",
        verbose_name=_("Academic period"),
    )
    group = models.ForeignKey(Group, on_delete=models.CASCADE, related_name="lessons")
    discipline = models.ForeignKey(Discipline, on_delete=models.PROTECT, related_name="lessons")
    teacher = models.ForeignKey(TeacherProfile, on_delete=models.PROTECT, related_name="lessons")
    room = models.ForeignKey(Room, on_delete=models.PROTECT, related_name="lessons")
    timeslot = models.ForeignKey(TimeSlot, on_delete=models.PROTECT, related_name="lessons")
    color = models.CharField(max_length=16, default="#58B2FF")
    is_frozen = models.BooleanField(
        default=False,
        help_text=_("If enabled, this lesson will not be changed by automatic algorithms."),
    )
    is_draft = models.BooleanField(
        _("Draft"),
        default=False,
        help_text=_("Draft lessons are hidden from students until published."),
    )
    published_at = models.DateTimeField(_("Published at"), null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["group", "timeslot", "academic_period"],
                name="uniq_lesson_group_slot_period",
            ),
            models.UniqueConstraint(
                fields=["teacher", "timeslot", "academic_period"],
                name="uniq_lesson_teacher_slot_period",
            ),
            models.UniqueConstraint(
                fields=["room", "timeslot", "academic_period"],
                name="uniq_lesson_room_slot_period",
            ),
        ]
        ordering = ["timeslot__day_of_week", "timeslot__period"]
        verbose_name = _("Lesson")
        verbose_name_plural = _("Lessons")

    def __str__(self) -> str:
        return f"{self.group} {self.discipline} @ {self.timeslot}"


class LessonChangeLog(models.Model):
    """Audit trail for manual edits and publish actions."""

    class Action(models.TextChoices):
        CREATE = "create", _("Create")
        UPDATE = "update", _("Update")
        PUBLISH = "publish", _("Publish")
        GENERATE = "generate", _("Generate")

    lesson = models.ForeignKey(Lesson, on_delete=models.CASCADE, related_name="change_logs")
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="lesson_change_logs",
    )
    action = models.CharField(max_length=32, choices=Action.choices)
    payload = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = _("Lesson change log")
        verbose_name_plural = _("Lesson change logs")


class AlgorithmRunLog(models.Model):
    """
    Lightweight log of schedule generation / optimisation runs.
    Used to surface algorithm errors and high level stats to admins.
    """

    class Kind(models.TextChoices):
        GENERATE = "generate", _("Generate")
        OPTIMIZE = "optimize", _("Optimize")

    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name="algorithm_run_logs",
        null=True,
        blank=True,
        verbose_name=_("Organization"),
    )
    created_at = models.DateTimeField(auto_now_add=True)
    kind = models.CharField(max_length=16, choices=Kind.choices)
    ok = models.BooleanField(default=True)
    message = models.CharField(max_length=255, blank=True)
    details = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = _("Algorithm run log")
        verbose_name_plural = _("Algorithm run logs")

    def __str__(self) -> str:
        return f"[{self.get_kind_display()}] {self.created_at:%Y-%m-%d %H:%M} ({'ok' if self.ok else 'error'})"


class SlotPedagogicalFeatures(models.Model):
    """
    Per–time-slot signals for neural scheduling: fatigue proxies, survey/LMS aggregates,
    historical load. Used as inputs to the slot-unfitness model (Keras) and as fallbacks
    when the model file is missing.
    """

    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name="slot_pedagogical_features",
        verbose_name=_("Organization"),
    )
    timeslot = models.ForeignKey(
        TimeSlot,
        on_delete=models.CASCADE,
        related_name="pedagogical_features",
        verbose_name=_("Time slot"),
    )
    student_fatigue_index = models.FloatField(
        _("Student fatigue index"),
        default=0.5,
        help_text=_("0 = low reported fatigue, 1 = high (questionnaires / self-report)."),
    )
    survey_burden_index = models.FloatField(
        _("Survey burden index"),
        default=0.5,
        help_text=_("0 = slot feels light, 1 = students rate it as overloaded / stressful."),
    )
    lms_activity_normalized = models.FloatField(
        _("LMS activity (normalized)"),
        default=0.5,
        help_text=_("0..1 relative engagement vs other slots (logins, submissions)."),
    )
    historical_semester_load = models.FloatField(
        _("Historical semester load"),
        default=0.5,
        help_text=_("0..1 from past timetables: how often this slot was heavily used."),
    )
    target_unfitness_label = models.FloatField(
        _("Target unfitness (supervised label)"),
        null=True,
        blank=True,
        help_text=_("Optional 0..1 label for training: high = avoid placing important lessons here."),
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "timeslot"],
                name="uniq_slot_pedagogical_features_org_slot",
            ),
        ]
        verbose_name = _("Slot pedagogical features")
        verbose_name_plural = _("Slot pedagogical features")

    def __str__(self) -> str:
        return f"{self.organization_id} · {self.timeslot}"


class TeacherPreferenceRequest(models.Model):
    """Schedule preference changes (days / periods) require admin approval before applying."""

    class Status(models.TextChoices):
        PENDING = "pending", _("Pending")
        APPROVED = "approved", _("Approved")
        REJECTED = "rejected", _("Rejected")

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="teacher_preference_requests",
    )
    proposed_preferred_days = models.JSONField(_("Preferred days"), default=list, blank=True)
    proposed_preferred_periods = models.JSONField(_("Preferred periods"), default=list, blank=True)
    status = models.CharField(
        max_length=16,
        choices=Status.choices,
        default=Status.PENDING,
        db_index=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reviewed_teacher_preference_requests",
    )
    rejection_reason = models.TextField(_("Rejection reason"), blank=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = _("Teacher preference request")
        verbose_name_plural = _("Teacher preference requests")
        indexes = [
            models.Index(fields=["user", "status"]),
        ]

    def __str__(self) -> str:
        return f"{self.user_id} prefs ({self.status})"
