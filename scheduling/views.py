from __future__ import annotations

import logging
from collections import defaultdict

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect
from django.utils.translation import gettext_lazy as _
from django.views import View
from django.views.generic import FormView, TemplateView

from accounts.mixins import AdminRequiredMixin, TeacherRequiredMixin
from scheduling.forms import TeacherPreferencesForm
from scheduling.models import AcademicPeriod, AlgorithmRunLog, Lesson
from scheduling.period import get_period_for_request
from scheduling.schedule_queryset import lessons_queryset_for_request
from scheduling.services import generate_schedule, optimize_schedule
from scheduling.ics import build_schedule_ics_bytes
from scheduling.xlsx import build_schedule_workbook
from university.models import Group, Room, TeacherProfile, TimeSlot

logger = logging.getLogger(__name__)


class MyScheduleView(LoginRequiredMixin, TemplateView):
    template_name = "scheduling/my_schedule.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        user = self.request.user
        oid = user.organization_id
        period = get_period_for_request(self.request, oid)

        group = None
        teacher = None
        room = None

        if user.is_student and hasattr(user, "student_profile"):
            group = user.student_profile.group
        elif user.is_teacher and hasattr(user, "teacher_profile"):
            teacher = user.teacher_profile

        if user.is_admin:
            # Allow admin to choose scope
            group_id = self.request.GET.get("group")
            teacher_id = self.request.GET.get("teacher")
            room_id = self.request.GET.get("room")
            if group_id:
                group = Group.objects.filter(id=group_id, department__faculty__organization_id=oid).first()
            if teacher_id:
                teacher = TeacherProfile.objects.filter(
                    id=teacher_id, department__faculty__organization_id=oid
                ).first()
            if room_id:
                room = Room.objects.filter(id=room_id, organization_id=oid).first()

        qs = lessons_queryset_for_request(self.request)

        day = self.request.GET.get("day")
        q = (self.request.GET.get("q") or "").strip()
        group_query = self.request.GET.get("group")
        teacher_query = self.request.GET.get("teacher")
        room_query = self.request.GET.get("room")

        # Enforce role-based data access even via direct URL params.
        if user.is_teacher and (group_query or teacher_query or room_query):
            if teacher_query and str(getattr(user, "teacher_profile", None).id if hasattr(user, "teacher_profile") else "") != str(teacher_query):
                raise PermissionDenied(_("You can only access your own schedule."))
            if group_query:
                allowed_groups = set(
                    Lesson.objects.filter(
                        teacher=user.teacher_profile,
                        academic_period_id=period.id,
                    ).values_list("group_id", flat=True)
                ) if hasattr(user, "teacher_profile") else set()
                if int(group_query) not in allowed_groups:
                    raise PermissionDenied(_("You are not allowed to open this group's schedule."))

        if user.is_student and (group_query or teacher_query or room_query):
            if not hasattr(user, "student_profile"):
                raise PermissionDenied(_("Student profile is not configured."))
            if group_query and str(user.student_profile.group_id) != str(group_query):
                raise PermissionDenied(_("You can only access your group's schedule."))
            if teacher_query or room_query:
                raise PermissionDenied(_("You can only access your group's schedule."))

        if day:
            qs = qs.filter(timeslot__day_of_week=int(day))
        if q:
            qs = qs.filter(discipline__name__icontains=q)

        lessons = list(qs)

        grid: dict[int, dict[int, list[Lesson]]] = defaultdict(lambda: defaultdict(list))
        for l in lessons:
            grid[l.timeslot.day_of_week][l.timeslot.period].append(l)

        timeslots = list(TimeSlot.objects.filter(organization_id=oid))
        periods = sorted({ts.period for ts in timeslots}) or [1, 2, 3, 4, 5]
        days = [1, 2, 3, 4, 5, 6]
        day_labels = {d: TimeSlot.Day(d).label for d in days}

        ctx.update(
            {
                "selected_period": period,
                "academic_periods": AcademicPeriod.objects.filter(organization_id=oid).order_by(
                    "-start_date", "name"
                ),
                "scope": {"group": group, "teacher": teacher, "room": room},
                "lessons": lessons,
                "grid": grid,
                "periods": periods,
                "days": days,
                "day_labels": day_labels,
                "filters": {
                    "day": int(day) if day else None,
                    "group_id": group.id if group else None,
                    "teacher_id": teacher.id if teacher else None,
                    "room_id": room.id if room else None,
                    "q": q,
                },
                "choices": {
                    "groups": Group.objects.filter(department__faculty__organization_id=oid).order_by("name"),
                    "teachers": TeacherProfile.objects.filter(department__faculty__organization_id=oid)
                    .select_related("user")
                    .order_by("user__full_name"),
                    "rooms": Room.objects.filter(organization_id=oid).order_by("name"),
                },
            }
        )
        return ctx


class GenerateScheduleView(AdminRequiredMixin, TemplateView):
    template_name = "scheduling/generate.html"

    def post(self, request: HttpRequest, *args, **kwargs) -> HttpResponse:
        action = request.POST.get("action") or "generate"
        try:
            org_id = request.user.organization_id
            period = get_period_for_request(request, org_id)
            if action == "optimize":
                opt_res = optimize_schedule(organization_id=org_id, academic_period_id=period.id)
                messages.success(
                    request,
                    _("Optimisation finished. Best fitness: %(f)s")
                    % {"f": opt_res.best_fitness},
                )
            else:
                clear_existing = request.POST.get("clear") == "1"
                res = generate_schedule(
                    organization_id=org_id,
                    academic_period_id=period.id,
                    clear_existing=clear_existing,
                )
                msg = _(
                    "Schedule generated. Created: %(c)s, skipped: %(s)s, conflicts: %(x)s. "
                    "Skipped means no room met capacity; conflicts means no free slot/room was found for a session."
                ) % {"c": res.created, "s": res.skipped, "x": res.conflicts}
                messages.success(request, msg)
                if res.failure_samples:
                    messages.warning(
                        request,
                        _("See the algorithm log below for sample rows that could not be placed."),
                    )
        except Exception:  # pragma: no cover - defensive UI guard
            logger.exception("Schedule generation or optimisation failed")
            messages.error(request, _("Generation failed. Administrators were notified in the server log."))
        return redirect("scheduling:generate")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        oid = self.request.user.organization_id
        ctx["selected_period"] = get_period_for_request(self.request, oid)
        ctx["academic_periods"] = AcademicPeriod.objects.filter(organization_id=oid).order_by("-start_date", "name")
        ctx["last_runs"] = AlgorithmRunLog.objects.filter(organization_id=oid).order_by("-created_at")[:10]
        ctx["last_generate_detail"] = None
        last = (
            AlgorithmRunLog.objects.filter(kind=AlgorithmRunLog.Kind.GENERATE, organization_id=oid)
            .order_by("-created_at")
            .first()
        )
        if last and last.details:
            ctx["last_generate_detail"] = last.details
        return ctx


class ExportScheduleXlsxView(LoginRequiredMixin, View):
    def get(self, request: HttpRequest) -> HttpResponse:
        wb = build_schedule_workbook(request=request)
        stream = wb.to_bytes()
        resp = HttpResponse(
            stream,
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        resp["Content-Disposition"] = 'attachment; filename="matika_schedule.xlsx"'
        return resp


class ExportScheduleIcsView(LoginRequiredMixin, View):
    def get(self, request: HttpRequest) -> HttpResponse:
        data = build_schedule_ics_bytes(request=request)
        resp = HttpResponse(data, content_type="text/calendar; charset=utf-8")
        resp["Content-Disposition"] = 'attachment; filename="matika_schedule.ics"'
        return resp


class MyGroupsView(TeacherRequiredMixin, TemplateView):
    template_name = "scheduling/my_groups.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        if not hasattr(self.request.user, "teacher_profile"):
            raise PermissionDenied(_("Teacher profile is not configured."))
        teacher = self.request.user.teacher_profile
        oid = self.request.user.organization_id
        period = get_period_for_request(self.request, oid)
        group_ids = (
            Lesson.objects.filter(
                teacher=teacher,
                academic_period_id=period.id,
                group__department__faculty__organization_id=oid,
            )
            .values_list("group_id", flat=True)
            .distinct()
        )
        ctx["groups"] = Group.objects.filter(id__in=group_ids, department__faculty__organization_id=oid).order_by("name")
        return ctx


class TeacherPreferencesView(TeacherRequiredMixin, FormView):
    template_name = "scheduling/preferences.html"
    form_class = TeacherPreferencesForm

    def get_form_kwargs(self):
        if not hasattr(self.request.user, "teacher_profile"):
            raise PermissionDenied(_("Teacher profile is not configured."))
        kwargs = super().get_form_kwargs()
        kwargs["teacher_profile"] = self.request.user.teacher_profile
        return kwargs

    def form_valid(self, form):
        form.save()
        messages.success(self.request, _("Preferences saved."))
        return redirect("scheduling:preferences")

