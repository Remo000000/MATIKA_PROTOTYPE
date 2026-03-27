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
