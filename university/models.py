from __future__ import annotations

from django.conf import settings
from django.db import models
from django.utils.text import slugify
from django.utils.translation import gettext_lazy as _

from university.utils import latinize_text


class Organization(models.Model):
    """
    Tenant root: each installation may host multiple isolated organizations
    (e.g. universities). All faculty rooms and time grids belong to one organization.
    """

    name = models.CharField(_("Name"), max_length=255)
    slug = models.SlugField(_("Slug"), max_length=64, unique=True)

    class Meta:
        verbose_name = _("Organization")
        verbose_name_plural = _("Organizations")

    def __str__(self) -> str:
        return self.name

    def save(self, *args, **kwargs):
        self.name = latinize_text(self.name)
        if not (self.slug or "").strip():
            self.slug = (slugify(self.name) or "default")[:64]
        return super().save(*args, **kwargs)


class Faculty(models.Model):
    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name="faculties",
        verbose_name=_("Organization"),
    )
    name = models.CharField(max_length=255)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["organization", "name"], name="uniq_faculty_org_name"),
        ]
        verbose_name = _("Faculty")
        verbose_name_plural = _("Faculties")

    def __str__(self) -> str:
        return self.name

    def save(self, *args, **kwargs):
        self.name = latinize_text(self.name)
        return super().save(*args, **kwargs)


class Department(models.Model):
    faculty = models.ForeignKey(Faculty, on_delete=models.CASCADE, related_name="departments")
    name = models.CharField(max_length=255)

    class Meta:
        unique_together = [("faculty", "name")]
        verbose_name = _("Department")
        verbose_name_plural = _("Departments")

    def __str__(self) -> str:
        return f"{self.faculty}: {self.name}"

    def save(self, *args, **kwargs):
        self.name = latinize_text(self.name)
        return super().save(*args, **kwargs)


class Group(models.Model):
    department = models.ForeignKey(
        Department,
        on_delete=models.PROTECT,
        related_name="groups",
        verbose_name=_("Department"),
    )
    name = models.CharField(_("Name"), max_length=120)
    size = models.PositiveIntegerField(_("Size"), default=25)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["department", "name"], name="uniq_group_dept_name"),
        ]
        verbose_name = _("Group")
        verbose_name_plural = _("Groups")

    def __str__(self) -> str:
        return self.name

    def save(self, *args, **kwargs):
        self.name = latinize_text(self.name)
        return super().save(*args, **kwargs)


class Room(models.Model):
    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name="rooms",
        verbose_name=_("Organization"),
    )
    name = models.CharField(_("Name"), max_length=120)
    capacity = models.PositiveIntegerField(_("Capacity"), default=30)
    building = models.CharField(_("Building"), max_length=120, blank=True)
    room_type = models.CharField(_("Room type"), max_length=120, blank=True)
    floor = models.IntegerField(_("Floor"), null=True, blank=True)
    equipment = models.TextField(_("Equipment"), blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["organization", "name"], name="uniq_room_org_name"),
        ]
        verbose_name = _("Room")
        verbose_name_plural = _("Rooms")

    def __str__(self) -> str:
        return self.name

    def save(self, *args, **kwargs):
        self.name = latinize_text(self.name)
        self.building = latinize_text(self.building)
        self.room_type = latinize_text(self.room_type)
        self.equipment = latinize_text(self.equipment)
        return super().save(*args, **kwargs)


class Discipline(models.Model):
    department = models.ForeignKey(
        Department,
        on_delete=models.PROTECT,
        related_name="disciplines",
        verbose_name=_("Department"),
    )
    name = models.CharField(_("Name"), max_length=255)
    code = models.CharField(_("Code"), max_length=64, blank=True)

    class Meta:
        unique_together = [("department", "name")]
        verbose_name = _("Discipline")
        verbose_name_plural = _("Disciplines")

    def __str__(self) -> str:
        return self.name

    def save(self, *args, **kwargs):
        self.name = latinize_text(self.name)
        self.code = latinize_text(self.code)
        return super().save(*args, **kwargs)


class TimeSlot(models.Model):
    class Day(models.IntegerChoices):
        MON = 1, _("Mon")
        TUE = 2, _("Tue")
        WED = 3, _("Wed")
        THU = 4, _("Thu")
        FRI = 5, _("Fri")
        SAT = 6, _("Sat")

    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name="timeslots",
        verbose_name=_("Organization"),
    )
    day_of_week = models.IntegerField(choices=Day.choices)
    period = models.PositiveIntegerField(help_text=_("Pair number (1..N)"))
    start_time = models.TimeField(null=True, blank=True)
    end_time = models.TimeField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "day_of_week", "period"],
                name="uniq_timeslot_org_day_period",
            ),
        ]
        ordering = ["day_of_week", "period"]
        verbose_name = _("Time slot")
        verbose_name_plural = _("Time slots")

    def __str__(self) -> str:
        return f"{self.get_day_of_week_display()} #{self.period}"


class TeacherProfile(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="teacher_profile",
        verbose_name=_("User"),
    )
    department = models.ForeignKey(
        Department,
        on_delete=models.PROTECT,
        related_name="teachers",
        verbose_name=_("Department"),
    )
    academic_title = models.CharField(_("Academic title"), max_length=120, blank=True)
    profession = models.CharField(_("Profession"), max_length=120, blank=True)
    experience_years = models.PositiveIntegerField(_("Experience (years)"), default=0)
    office_room = models.CharField(_("Office"), max_length=120, blank=True)
    phone = models.CharField(_("Phone"), max_length=40, blank=True)
    bio = models.TextField(_("Bio"), blank=True)
    preferred_days = models.JSONField(_("Preferred days"), default=list, blank=True)  # [1..6]
    preferred_periods = models.JSONField(_("Preferred periods"), default=list, blank=True)  # [1..N]

    class Meta:
        verbose_name = _("Teacher")
        verbose_name_plural = _("Teachers")

    def __str__(self) -> str:
        return self.user.get_short_name()

    def save(self, *args, **kwargs):
        self.academic_title = latinize_text(self.academic_title)
        self.profession = latinize_text(self.profession)
        self.office_room = latinize_text(self.office_room)
        self.bio = latinize_text(self.bio)
        return super().save(*args, **kwargs)


class StudentProfile(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="student_profile",
        verbose_name=_("User"),
    )
    group = models.ForeignKey(Group, on_delete=models.PROTECT, related_name="students", verbose_name=_("Group"))
    student_id = models.CharField(_("Student ID"), max_length=64, blank=True)
    course_year = models.PositiveIntegerField(_("Course"), default=1)
    phone = models.CharField(_("Phone"), max_length=40, blank=True)
    gpa = models.DecimalField(_("GPA"), max_digits=3, decimal_places=2, null=True, blank=True)
    schedule_preferences = models.JSONField(
        _("Schedule / ML preferences"),
        default=dict,
        blank=True,
        help_text=_(
            "Optional weights for personalized slot scoring: fatigue_sensitivity, survey_sensitivity, "
            "prefer_morning (0..1)."
        ),
    )

    class Meta:
        verbose_name = _("Student")
        verbose_name_plural = _("Students")

    def __str__(self) -> str:
        return self.user.get_short_name()

    def save(self, *args, **kwargs):
        self.student_id = latinize_text(self.student_id)
        return super().save(*args, **kwargs)

