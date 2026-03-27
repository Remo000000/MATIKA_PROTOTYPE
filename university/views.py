from __future__ import annotations

import csv
import io
import logging

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.paginator import Paginator
from django.db import IntegrityError, transaction
from django.db.models import ProtectedError, Q
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse_lazy
from django.utils.translation import gettext_lazy as _
from django.views.generic import FormView, TemplateView, UpdateView

from accounts.mixins import AdminRequiredMixin
from accounts.models import User
from university.forms import (
    CsvImportForm,
    DisciplineManageForm,
    GroupManageForm,
    RoomManageForm,
    StudentCreateForm,
    StudentUpdateForm,
    TeacherCreateForm,
    TeacherUpdateForm,
    UserCreateForm,
    UserUpdateForm,
)
from university.models import Department, Discipline, Faculty, Group, Room, StudentProfile, TeacherProfile, TimeSlot

logger = logging.getLogger(__name__)


def _org_id(request):
    return getattr(request.user, "organization_id", None)


def _run_delete(request, delete_action, *, success_msg, protected_msg) -> None:
    try:
        delete_action()
        messages.success(request, success_msg)
    except ProtectedError:
        logger.warning("Delete blocked (protected FK)", exc_info=True)
        messages.error(request, protected_msg)
    except IntegrityError:
        logger.warning("Delete blocked (integrity)", exc_info=True)
        messages.error(request, protected_msg)
    except Exception:
        logger.exception("Unexpected delete failure")
        messages.error(request, _("Delete failed due to an unexpected error. Please try again."))


class IndexView(LoginRequiredMixin, TemplateView):
    template_name = "university/index.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        oid = _org_id(self.request)
        fac_q = Faculty.objects.filter(organization_id=oid)
        ctx["stats"] = {
            "faculties": fac_q.count(),
            "departments": Department.objects.filter(faculty__organization_id=oid).count(),
            "disciplines": Discipline.objects.filter(department__faculty__organization_id=oid).count(),
            "groups": Group.objects.filter(department__faculty__organization_id=oid).count(),
            "rooms": Room.objects.filter(organization_id=oid).count(),
            "teachers": TeacherProfile.objects.filter(department__faculty__organization_id=oid).count(),
            "students": StudentProfile.objects.filter(user__organization_id=oid).count(),
            "timeslots": TimeSlot.objects.filter(organization_id=oid).count(),
        }
        ctx["top_rooms"] = Room.objects.filter(organization_id=oid).order_by("-capacity", "name")[:8]
        ctx["top_teachers"] = (
            TeacherProfile.objects.filter(department__faculty__organization_id=oid)
            .select_related("user", "department")[:8]
        )
        ctx["top_students"] = (
            StudentProfile.objects.filter(user__organization_id=oid).select_related("user", "group")[:8]
        )
        return ctx


class CsvImportView(AdminRequiredMixin, FormView):
    template_name = "university/csv_import.html"
    form_class = CsvImportForm

    def form_valid(self, form):
        kind = form.cleaned_data["kind"]
        f = form.cleaned_data["file"]
        org_id = _org_id(self.request)

        content = f.read().decode("utf-8-sig")
        reader = csv.DictReader(io.StringIO(content))

        with transaction.atomic():
            if kind == "rooms":
                self._import_rooms(reader, org_id)
            elif kind == "groups":
                self._import_groups(reader, org_id)
            elif kind == "timeslots":
                self._import_timeslots(reader, org_id)
            else:
                messages.error(self.request, _("Unknown import type."))
                return redirect("university:csv_import")

        messages.success(self.request, _("Import completed."))
        return redirect("university:index")

    @staticmethod
    def _import_rooms(reader, org_id: int):
        for row in reader:
            Room.objects.update_or_create(
                organization_id=org_id,
                name=row["name"].strip(),
                defaults={
                    "capacity": int(row.get("capacity") or 0) or 30,
                    "building": (row.get("building") or "").strip(),
                    "room_type": (row.get("room_type") or "").strip(),
                    "floor": int(row.get("floor")) if row.get("floor") else None,
                    "equipment": (row.get("equipment") or "").strip(),
                },
            )

    @staticmethod
    def _import_groups(reader, org_id: int):
        # Expected columns: name, size, faculty, department
        for row in reader:
            faculty_name = (row.get("faculty") or "").strip() or "Default"
            dept_name = (row.get("department") or "").strip() or "General"
            faculty, _ = Faculty.objects.get_or_create(organization_id=org_id, name=faculty_name)
            dept, _ = Department.objects.get_or_create(faculty=faculty, name=dept_name)
            Group.objects.update_or_create(
                department=dept,
                name=row["name"].strip(),
                defaults={"size": int(row.get("size") or 0) or 25},
            )

    @staticmethod
    def _import_timeslots(reader, org_id: int):
        # Expected: day_of_week, period, start_time(optional), end_time(optional)
        for row in reader:
            TimeSlot.objects.update_or_create(
                organization_id=org_id,
                day_of_week=int(row["day_of_week"]),
                period=int(row["period"]),
                defaults={
                    "start_time": row.get("start_time") or None,
                    "end_time": row.get("end_time") or None,
                },
            )


class AdminDataManagementView(AdminRequiredMixin, TemplateView):
    """Hub for «Settings» in the sidebar — not a redirect to manage_users."""

    template_name = "university/manage_data.html"


class AdminUsersManageView(AdminRequiredMixin, TemplateView):
    template_name = "university/manage_users.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        q = (self.request.GET.get("q") or "").strip()
        role = (self.request.GET.get("role") or "").strip()
        oid = _org_id(self.request)
        items = User.objects.filter(organization_id=oid).order_by("-id")
        if q:
            items = items.filter(Q(email__icontains=q) | Q(full_name__icontains=q))
        if role:
            items = items.filter(role=role)
        ctx["items"] = items[:200]
        ctx["filters"] = {"q": q, "role": role}
        ctx["form"] = kwargs.get("form") or UserCreateForm(organization=self.request.user.organization)
        return ctx

    def post(self, request, *args, **kwargs):
        action = request.POST.get("action")
        if action == "create":
            form = UserCreateForm(request.POST, organization=request.user.organization)
            if form.is_valid():
                form.save()
                messages.success(request, _("User created."))
                return redirect("university:manage_users")
            return self.render_to_response(self.get_context_data(form=form))
        if action == "delete":
            oid = _org_id(request)
            obj = get_object_or_404(User, id=request.POST.get("id"), organization_id=oid)
            if obj.is_superuser:
                messages.error(request, _("Superuser cannot be deleted here."))
            else:
                obj.delete()
                messages.success(request, _("User deleted."))
        return redirect("university:manage_users")


class AdminTeachersManageView(AdminRequiredMixin, TemplateView):
    template_name = "university/manage_teachers.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        q = (self.request.GET.get("q") or "").strip()
        department_id = (self.request.GET.get("department") or "").strip()
        oid = _org_id(self.request)
        items = TeacherProfile.objects.filter(department__faculty__organization_id=oid).select_related(
            "user", "department"
        )
        if q:
            items = items.filter(
                Q(user__full_name__icontains=q)
                | Q(user__email__icontains=q)
                | Q(profession__icontains=q)
                | Q(department__name__icontains=q)
            )
        if department_id:
            items = items.filter(department_id=department_id)
        ctx["items"] = items.order_by("-id")[:200]
        ctx["filters"] = {"q": q, "department": department_id}
        ctx["departments"] = Department.objects.filter(faculty__organization_id=oid).order_by("name")
        ctx["form"] = kwargs.get("form") or TeacherCreateForm(organization=self.request.user.organization)
        return ctx

    def post(self, request, *args, **kwargs):
        action = request.POST.get("action")
        if action == "create":
            form = TeacherCreateForm(request.POST, organization=request.user.organization)
            if form.is_valid():
                form.save()
                messages.success(request, _("Teacher created."))
                return redirect("university:manage_teachers")
            return self.render_to_response(self.get_context_data(form=form))
        if action == "delete":
            oid = _org_id(request)
            obj = get_object_or_404(
                TeacherProfile,
                id=request.POST.get("id"),
                department__faculty__organization_id=oid,
            )
            user = obj.user

            def _delete_teacher():
                obj.delete()
                user.delete()

            _run_delete(
                request,
                _delete_teacher,
                success_msg=_("Teacher deleted."),
                protected_msg=_("Cannot delete object because it is used by related records."),
            )
        return redirect("university:manage_teachers")


class AdminStudentsManageView(AdminRequiredMixin, TemplateView):
    template_name = "university/manage_students.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        q = (self.request.GET.get("q") or "").strip()
        group_id = (self.request.GET.get("group") or "").strip()
        oid = _org_id(self.request)
        items = StudentProfile.objects.filter(user__organization_id=oid).select_related("user", "group")
        if q:
            items = items.filter(
                Q(user__full_name__icontains=q)
                | Q(user__email__icontains=q)
                | Q(group__name__icontains=q)
                | Q(student_id__icontains=q)
            )
        if group_id:
            items = items.filter(group_id=group_id)
        items = items.order_by("-id")
        paginator = Paginator(items, 50)
        page_obj = paginator.get_page(self.request.GET.get("page"))
        ctx["page_obj"] = page_obj
        ctx["items"] = page_obj
        params = self.request.GET.copy()
        params.pop("page", None)
        ctx["pagination_query"] = params.urlencode()
        ctx["filters"] = {"q": q, "group": group_id}
        ctx["groups"] = Group.objects.filter(department__faculty__organization_id=oid).order_by("name")
        ctx["form"] = kwargs.get("form") or StudentCreateForm(organization=self.request.user.organization)
        return ctx

    def post(self, request, *args, **kwargs):
        action = request.POST.get("action")
        if action == "create":
            form = StudentCreateForm(request.POST, organization=request.user.organization)
            if form.is_valid():
                form.save()
                messages.success(request, _("Student created."))
                return redirect("university:manage_students")
            return self.render_to_response(self.get_context_data(form=form))
        if action == "delete":
            oid = _org_id(request)
            obj = get_object_or_404(StudentProfile, id=request.POST.get("id"), user__organization_id=oid)
            user = obj.user

            def _delete_student():
                obj.delete()
                user.delete()

            _run_delete(
                request,
                _delete_student,
                success_msg=_("Student deleted."),
                protected_msg=_("Cannot delete object because it is used by related records."),
            )
        return redirect("university:manage_students")


class AdminGroupsManageView(AdminRequiredMixin, TemplateView):
    template_name = "university/manage_groups.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        q = (self.request.GET.get("q") or "").strip()
        department_id = (self.request.GET.get("department") or "").strip()
        oid = _org_id(self.request)
        items = Group.objects.filter(department__faculty__organization_id=oid).select_related("department")
        if q:
            items = items.filter(Q(name__icontains=q) | Q(department__name__icontains=q))
        if department_id:
            items = items.filter(department_id=department_id)
        ctx["items"] = items.order_by("name")
        ctx["filters"] = {"q": q, "department": department_id}
        ctx["departments"] = Department.objects.filter(faculty__organization_id=oid).order_by("name")
        ctx["form"] = kwargs.get("form") or GroupManageForm(organization=self.request.user.organization)
        return ctx

    def post(self, request, *args, **kwargs):
        action = request.POST.get("action")
        if action == "create":
            form = GroupManageForm(request.POST, organization=request.user.organization)
            if form.is_valid():
                form.save()
                messages.success(request, _("Group created."))
                return redirect("university:manage_groups")
            return self.render_to_response(self.get_context_data(form=form))
        if action == "delete":
            oid = _org_id(request)
            obj = get_object_or_404(Group, id=request.POST.get("id"), department__faculty__organization_id=oid)
            _run_delete(
                request,
                obj.delete,
                success_msg=_("Group deleted."),
                protected_msg=_("Cannot delete object because it is used by related records."),
            )
        return redirect("university:manage_groups")


class AdminRoomsManageView(AdminRequiredMixin, TemplateView):
    template_name = "university/manage_rooms.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        q = (self.request.GET.get("q") or "").strip()
        building = (self.request.GET.get("building") or "").strip()
        oid = _org_id(self.request)
        items = Room.objects.filter(organization_id=oid)
        if q:
            items = items.filter(
                Q(name__icontains=q)
                | Q(building__icontains=q)
                | Q(room_type__icontains=q)
                | Q(equipment__icontains=q)
            )
        if building:
            items = items.filter(building=building)
        ctx["items"] = items.order_by("name")
        ctx["filters"] = {"q": q, "building": building}
        ctx["buildings"] = [
            b
            for b in Room.objects.filter(organization_id=oid).order_by("building").values_list("building", flat=True).distinct()
            if b
        ]
        ctx["form"] = kwargs.get("form") or RoomManageForm(organization=self.request.user.organization)
        return ctx

    def post(self, request, *args, **kwargs):
        action = request.POST.get("action")
        if action == "create":
            form = RoomManageForm(request.POST, organization=request.user.organization)
            if form.is_valid():
                form.save()
                messages.success(request, _("Room created."))
                return redirect("university:manage_rooms")
            return self.render_to_response(self.get_context_data(form=form))
        if action == "delete":
            oid = _org_id(request)
            obj = get_object_or_404(Room, id=request.POST.get("id"), organization_id=oid)
            _run_delete(
                request,
                obj.delete,
                success_msg=_("Room deleted."),
                protected_msg=_("Cannot delete object because it is used by related records."),
            )
        return redirect("university:manage_rooms")


class AdminDisciplinesManageView(AdminRequiredMixin, TemplateView):
    template_name = "university/manage_disciplines.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        q = (self.request.GET.get("q") or "").strip()
        department_id = (self.request.GET.get("department") or "").strip()
        oid = _org_id(self.request)
        items = Discipline.objects.filter(department__faculty__organization_id=oid).select_related("department")
        if q:
            items = items.filter(Q(name__icontains=q) | Q(code__icontains=q) | Q(department__name__icontains=q))
        if department_id:
            items = items.filter(department_id=department_id)
        ctx["items"] = items.order_by("name")
        ctx["filters"] = {"q": q, "department": department_id}
        ctx["departments"] = Department.objects.filter(faculty__organization_id=oid).order_by("name")
        ctx["form"] = kwargs.get("form") or DisciplineManageForm(organization=self.request.user.organization)
        return ctx

    def post(self, request, *args, **kwargs):
        action = request.POST.get("action")
        if action == "create":
            form = DisciplineManageForm(request.POST, organization=request.user.organization)
            if form.is_valid():
                form.save()
                messages.success(request, _("Discipline created."))
                return redirect("university:manage_disciplines")
            return self.render_to_response(self.get_context_data(form=form))
        if action == "delete":
            oid = _org_id(request)
            obj = get_object_or_404(Discipline, id=request.POST.get("id"), department__faculty__organization_id=oid)
            _run_delete(
                request,
                obj.delete,
                success_msg=_("Discipline deleted."),
                protected_msg=_("Cannot delete object because it is used by related records."),
            )
        return redirect("university:manage_disciplines")


class UserEditView(AdminRequiredMixin, UpdateView):
    model = User
    form_class = UserUpdateForm
    template_name = "university/edit_item.html"
    success_url = reverse_lazy("university:manage_users")

    def get_queryset(self):
        return User.objects.filter(organization_id=self.request.user.organization_id)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["page_title"] = _("Edit user")
        return ctx

    def form_valid(self, form):
        messages.success(self.request, _("User updated."))
        return super().form_valid(form)


class TeacherEditView(AdminRequiredMixin, UpdateView):
    model = TeacherProfile
    form_class = TeacherUpdateForm
    template_name = "university/edit_item.html"
    success_url = reverse_lazy("university:manage_teachers")

    def get_queryset(self):
        return TeacherProfile.objects.filter(department__faculty__organization_id=self.request.user.organization_id)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["page_title"] = _("Edit teacher")
        return ctx

    def form_valid(self, form):
        messages.success(self.request, _("Teacher updated."))
        return super().form_valid(form)


class StudentEditView(AdminRequiredMixin, UpdateView):
    model = StudentProfile
    form_class = StudentUpdateForm
    template_name = "university/edit_item.html"
    success_url = reverse_lazy("university:manage_students")

    def get_queryset(self):
        return StudentProfile.objects.filter(user__organization_id=self.request.user.organization_id)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["page_title"] = _("Edit student")
        return ctx

    def form_valid(self, form):
        messages.success(self.request, _("Student updated."))
        return super().form_valid(form)


class GroupEditView(AdminRequiredMixin, UpdateView):
    model = Group
    form_class = GroupManageForm
    template_name = "university/edit_item.html"
    success_url = reverse_lazy("university:manage_groups")

    def get_queryset(self):
        return Group.objects.filter(department__faculty__organization_id=self.request.user.organization_id)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["organization"] = self.request.user.organization
        return kwargs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["page_title"] = _("Edit group")
        return ctx

    def form_valid(self, form):
        messages.success(self.request, _("Group updated."))
        return super().form_valid(form)


class RoomEditView(AdminRequiredMixin, UpdateView):
    model = Room
    form_class = RoomManageForm
    template_name = "university/edit_item.html"
    success_url = reverse_lazy("university:manage_rooms")

    def get_queryset(self):
        return Room.objects.filter(organization_id=self.request.user.organization_id)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["organization"] = self.request.user.organization
        return kwargs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["page_title"] = _("Edit room")
        return ctx

    def form_valid(self, form):
        messages.success(self.request, _("Room updated."))
        return super().form_valid(form)


class DisciplineEditView(AdminRequiredMixin, UpdateView):
    model = Discipline
    form_class = DisciplineManageForm
    template_name = "university/edit_item.html"
    success_url = reverse_lazy("university:manage_disciplines")

    def get_queryset(self):
        return Discipline.objects.filter(department__faculty__organization_id=self.request.user.organization_id)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["organization"] = self.request.user.organization
        return kwargs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["page_title"] = _("Edit discipline")
        return ctx

    def form_valid(self, form):
        messages.success(self.request, _("Discipline updated."))
        return super().form_valid(form)

