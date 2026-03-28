from __future__ import annotations

import csv
import logging

from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.db.models import Count
from django.db.utils import DatabaseError
from django.http import HttpResponse
from django.utils.translation import gettext_lazy as _
from django.views import View
from django.views.generic import TemplateView

from scheduling.ml.predict import dashboard_ml_series, neural_vs_heuristic_series, prediction_backend_label
from scheduling.ml.train_metrics import read_metrics
from scheduling.models import AlgorithmRunLog
from scheduling.period import get_period_for_request
from university.models import Group, Room, TeacherProfile
from university.scope import lesson_qs_for_organization

_FEAT_LABEL_KEYS = {
    "feat_dow": _("Day of week (normalized)"),
    "feat_period": _("Pair number (normalized)"),
    "feat_fatigue": _("Student fatigue index"),
    "feat_survey": _("Survey burden index"),
    "feat_lms": _("LMS activity (normalized)"),
    "feat_history": _("Historical semester load"),
    "feat_monday_morning": _("Monday morning indicator"),
}

logger = logging.getLogger(__name__)


class HomeView(LoginRequiredMixin, TemplateView):
    template_name = "dashboard/home.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        user = self.request.user
        unread = 0
        if getattr(user, "is_authenticated", False) and hasattr(user, "notifications"):
            try:
                unread = user.notifications.filter(is_read=False).count()
            except (AttributeError, DatabaseError) as exc:
                logger.warning("home unread count failed: %s", exc)
                unread = 0
        ctx["unread_notifications_count"] = unread
        oid = getattr(user, "organization_id", None)
        period = get_period_for_request(self.request, oid) if oid else None
        period_id = period.id if period else None
        if getattr(user, "is_teacher", False) and hasattr(user, "teacher_profile"):
            t_lessons = lesson_qs_for_organization(oid, period_id).filter(teacher=user.teacher_profile)
            by_day = t_lessons.values("timeslot__day_of_week").annotate(cnt=Count("id")).order_by("timeslot__day_of_week")
            ctx["teacher_stats"] = {
                "groups": t_lessons.values("group_id").distinct().count(),
                "lessons": t_lessons.count(),
                "rooms": t_lessons.values("room_id").distinct().count(),
                "by_day": list(by_day),
            }
        elif getattr(user, "is_student", False) and hasattr(user, "student_profile"):
            s_lessons = lesson_qs_for_organization(oid, period_id).filter(
                group=user.student_profile.group
            ).exclude(is_draft=True)
            ctx["student_stats"] = {
                "group": user.student_profile.group,
                "lessons": s_lessons.count(),
                "rooms": s_lessons.values("room_id").distinct().count(),
                "teachers": s_lessons.values("teacher_id").distinct().count(),
            }
        if getattr(user, "is_admin", False) and oid:
            series, worst = dashboard_ml_series(oid)
            if worst and worst.get("contributions"):
                for row in worst["contributions"]:
                    # str() resolves gettext_lazy for JSON in templates (Chart.js).
                    row["label"] = str(_FEAT_LABEL_KEYS.get(row["key"], row["key"]))
            ctx["ml_dashboard"] = {
                "series": series,
                "worst": worst,
                "backend": prediction_backend_label(),
            }
        return ctx


class AnalyticsView(LoginRequiredMixin, TemplateView):
    template_name = "dashboard/analytics.html"

    def get_context_data(self, **kwargs):
        if not getattr(self.request.user, "is_admin", False):
            raise PermissionDenied(_("Only administrators can view global analytics."))
        ctx = super().get_context_data(**kwargs)
        oid = self.request.user.organization_id
        period = get_period_for_request(self.request, oid)
        base_lessons = lesson_qs_for_organization(oid, period.id)

        teacher_load = (
            base_lessons.values("teacher__id", "teacher__user__full_name")
            .annotate(cnt=Count("id"))
            .order_by("-cnt")
        )
        room_use = (
            base_lessons.values("room__id", "room__name").annotate(cnt=Count("id")).order_by("-cnt")
        )

        ctx["kpis"] = {
            "teachers": TeacherProfile.objects.filter(department__faculty__organization_id=oid).count(),
            "groups": Group.objects.filter(department__faculty__organization_id=oid).count(),
            "rooms": Room.objects.filter(organization_id=oid).count(),
            "lessons": base_lessons.count(),
        }
        ctx["charts"] = {
            "teacher_load": list(teacher_load),
            "room_use": list(room_use),
        }
        ctx["algorithm_runs"] = AlgorithmRunLog.objects.filter(organization_id=oid).order_by("-created_at")[:25]
        ctx["page_title"] = _("Analytics")
        ctx["ml_compare"] = neural_vs_heuristic_series(oid)
        ctx["training_metrics"] = read_metrics()
        return ctx


class AnalyticsExportCsvView(LoginRequiredMixin, View):
    """CSV export of teacher load and room usage (same scope as analytics charts)."""

    def get(self, request, *args, **kwargs):
        if not getattr(request.user, "is_admin", False):
            raise PermissionDenied(_("Only administrators can export analytics."))
        oid = request.user.organization_id
        period = get_period_for_request(request, oid)
        base = lesson_qs_for_organization(oid, period.id)
        teacher_load = (
            base.values("teacher__user__full_name")
            .annotate(cnt=Count("id"))
            .order_by("-cnt")
        )
        room_use = base.values("room__name").annotate(cnt=Count("id")).order_by("-cnt")

        response = HttpResponse(content_type="text/csv; charset=utf-8")
        response["Content-Disposition"] = 'attachment; filename="matika_analytics.csv"'
        w = csv.writer(response)
        w.writerow([_("Section"), _("Name"), _("Lessons")])
        for row in teacher_load:
            w.writerow([_("Teacher"), row.get("teacher__user__full_name") or "", row["cnt"]])
        w.writerow([])
        for row in room_use:
            w.writerow([_("Room"), row.get("room__name") or "", row["cnt"]])
        return response

