from __future__ import annotations

from django import forms
from django.db import transaction
from django.utils.translation import gettext_lazy as _

from accounts.models import User
from university.models import Department, Discipline, Group, Room, StudentProfile, TeacherProfile


class CsvImportForm(forms.Form):
    kind = forms.ChoiceField(
        label=_("Import type"),
        choices=[
            ("rooms", _("Rooms")),
            ("groups", _("Groups")),
            ("timeslots", _("Time slots")),
        ],
    )
    file = forms.FileField(label=_("CSV file"))


class UserCreateForm(forms.ModelForm):
    password = forms.CharField(label=_("Password"), widget=forms.PasswordInput, min_length=8)

    class Meta:
        model = User
        fields = ["email", "full_name", "role"]

    def __init__(self, *args, organization=None, **kwargs):
        self._organization = organization
        super().__init__(*args, **kwargs)

    def save(self, commit=True):
        user: User = super().save(commit=False)
        user.set_password(self.cleaned_data["password"])
        if self._organization:
            user.organization = self._organization
        if commit:
            user.save()
        return user


class UserUpdateForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ["email", "full_name", "role"]
        labels = {
            "email": _("Email"),
            "full_name": _("Full name"),
            "role": _("Role"),
        }


class TeacherCreateForm(forms.Form):
    email = forms.EmailField(label=_("Email"))
    full_name = forms.CharField(label=_("Full name"), max_length=255)
    password = forms.CharField(label=_("Password"), widget=forms.PasswordInput, min_length=8)
    department = forms.ModelChoiceField(label=_("Department"), queryset=Department.objects.none())
    academic_title = forms.CharField(label=_("Academic title"), required=False, max_length=120)
    profession = forms.CharField(label=_("Profession"), required=False, max_length=120)
    experience_years = forms.IntegerField(label=_("Experience (years)"), required=False, min_value=0, initial=0)
    office_room = forms.CharField(label=_("Office"), required=False, max_length=120)
    phone = forms.CharField(label=_("Phone"), required=False, max_length=40)

    def __init__(self, *args, organization=None, **kwargs):
        self._organization = organization
        super().__init__(*args, **kwargs)
        oid = getattr(organization, "id", None)
        if oid:
            self.fields["department"].queryset = Department.objects.filter(faculty__organization_id=oid).order_by(
                "name"
            )

    @transaction.atomic
    def save(self) -> TeacherProfile:
        user = User.objects.create(
            email=self.cleaned_data["email"],
            full_name=self.cleaned_data["full_name"],
            role=User.Role.TEACHER,
            organization=self._organization,
        )
        user.set_password(self.cleaned_data["password"])
        user.save()
        return TeacherProfile.objects.create(
            user=user,
            department=self.cleaned_data["department"],
            academic_title=self.cleaned_data.get("academic_title", ""),
            profession=self.cleaned_data.get("profession", ""),
            experience_years=self.cleaned_data.get("experience_years") or 0,
            office_room=self.cleaned_data.get("office_room", ""),
            phone=self.cleaned_data.get("phone", ""),
        )


class StudentCreateForm(forms.Form):
    email = forms.EmailField(label=_("Email"))
    full_name = forms.CharField(label=_("Full name"), max_length=255)
    password = forms.CharField(label=_("Password"), widget=forms.PasswordInput, min_length=8)
    group = forms.ModelChoiceField(label=_("Group"), queryset=Group.objects.none())
    student_id = forms.CharField(label=_("Student ID"), required=False, max_length=64)
    course_year = forms.IntegerField(label=_("Course"), required=False, min_value=1, initial=1)
    phone = forms.CharField(label=_("Phone"), required=False, max_length=40)
    gpa = forms.DecimalField(label=_("GPA"), required=False, max_digits=3, decimal_places=2, min_value=0, max_value=4)

    def __init__(self, *args, organization=None, **kwargs):
        self._organization = organization
        super().__init__(*args, **kwargs)
        oid = getattr(organization, "id", None)
        if oid:
            self.fields["group"].queryset = Group.objects.filter(department__faculty__organization_id=oid).order_by(
                "name"
            )

    @transaction.atomic
    def save(self) -> StudentProfile:
        user = User.objects.create(
            email=self.cleaned_data["email"],
            full_name=self.cleaned_data["full_name"],
            role=User.Role.STUDENT,
            organization=self._organization,
        )
        user.set_password(self.cleaned_data["password"])
        user.save()
        return StudentProfile.objects.create(
            user=user,
            group=self.cleaned_data["group"],
            student_id=self.cleaned_data.get("student_id", ""),
            course_year=self.cleaned_data.get("course_year") or 1,
            phone=self.cleaned_data.get("phone", ""),
            gpa=self.cleaned_data.get("gpa"),
        )


class TeacherUpdateForm(forms.ModelForm):
    email = forms.EmailField(label=_("Email"))
    full_name = forms.CharField(label=_("Full name"), max_length=255)
    preferred_days = forms.MultipleChoiceField(
        label=_("Preferred days"),
        required=False,
        choices=[
            ("1", _("Mon")),
            ("2", _("Tue")),
            ("3", _("Wed")),
            ("4", _("Thu")),
            ("5", _("Fri")),
            ("6", _("Sat")),
        ],
        widget=forms.CheckboxSelectMultiple,
    )
    preferred_periods = forms.MultipleChoiceField(
        label=_("Preferred periods"),
        required=False,
        choices=[(str(i), str(i)) for i in range(1, 9)],
        widget=forms.CheckboxSelectMultiple,
    )

    class Meta:
        model = TeacherProfile
        fields = [
            "department",
            "academic_title",
            "profession",
            "experience_years",
            "office_room",
            "phone",
            "bio",
            "preferred_days",
            "preferred_periods",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        oid = None
        if self.instance and self.instance.pk and self.instance.department_id:
            oid = self.instance.department.faculty.organization_id
        if oid:
            self.fields["department"].queryset = Department.objects.filter(faculty__organization_id=oid).order_by("name")
        if self.instance and self.instance.pk:
            self.fields["email"].initial = self.instance.user.email
            self.fields["full_name"].initial = self.instance.user.full_name
            self.fields["preferred_days"].initial = [str(d) for d in (self.instance.preferred_days or [])]
            self.fields["preferred_periods"].initial = [str(p) for p in (self.instance.preferred_periods or [])]

    def save(self, commit=True):
        profile: TeacherProfile = super().save(commit=False)
        profile.preferred_days = [int(x) for x in self.cleaned_data.get("preferred_days", [])]
        profile.preferred_periods = [int(x) for x in self.cleaned_data.get("preferred_periods", [])]
        user = profile.user
        user.email = self.cleaned_data["email"]
        user.full_name = self.cleaned_data["full_name"]
        if commit:
            user.save(update_fields=["email", "full_name"])
            profile.save()
        return profile


class StudentUpdateForm(forms.ModelForm):
    email = forms.EmailField(label=_("Email"))
    full_name = forms.CharField(label=_("Full name"), max_length=255)

    class Meta:
        model = StudentProfile
        fields = ["group", "student_id", "course_year", "phone", "gpa"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        oid = None
        if self.instance and self.instance.pk and self.instance.group_id:
            oid = self.instance.group.department.faculty.organization_id
        if oid:
            self.fields["group"].queryset = Group.objects.filter(department__faculty__organization_id=oid).order_by(
                "name"
            )
        if self.instance and self.instance.pk:
            self.fields["email"].initial = self.instance.user.email
            self.fields["full_name"].initial = self.instance.user.full_name

    def save(self, commit=True):
        profile: StudentProfile = super().save(commit=False)
        user = profile.user
        user.email = self.cleaned_data["email"]
        user.full_name = self.cleaned_data["full_name"]
        if commit:
            user.save(update_fields=["email", "full_name"])
            profile.save()
        return profile


class GroupManageForm(forms.ModelForm):
    class Meta:
        model = Group
        fields = ["name", "department", "size"]

    def __init__(self, *args, organization=None, **kwargs):
        self._organization = organization
        super().__init__(*args, **kwargs)
        oid = getattr(organization, "id", None)
        if oid:
            self.fields["department"].queryset = Department.objects.filter(faculty__organization_id=oid).order_by("name")

    def save(self, commit=True):
        obj: Group = super().save(commit=False)
        if commit:
            obj.save()
        return obj


class RoomManageForm(forms.ModelForm):
    class Meta:
        model = Room
        fields = ["name", "capacity", "building", "room_type", "floor", "equipment"]

    def __init__(self, *args, organization=None, **kwargs):
        self._organization = organization
        super().__init__(*args, **kwargs)

    def save(self, commit=True):
        obj: Room = super().save(commit=False)
        if self._organization:
            obj.organization = self._organization
        if commit:
            obj.save()
        return obj


class DisciplineManageForm(forms.ModelForm):
    class Meta:
        model = Discipline
        fields = ["department", "name", "code"]

    def __init__(self, *args, organization=None, **kwargs):
        super().__init__(*args, **kwargs)
        oid = getattr(organization, "id", None)
        if oid:
            self.fields["department"].queryset = Department.objects.filter(faculty__organization_id=oid).order_by("name")

