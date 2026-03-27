from __future__ import annotations

from django import forms
from django.contrib.auth import authenticate
from django.contrib.auth.password_validation import validate_password
from django.db import transaction
from django.utils.translation import gettext_lazy as _

from accounts.models import User
from university.models import Department, Group, StudentProfile, TeacherProfile
from university.scope import get_default_organization


class LoginForm(forms.Form):
    email = forms.EmailField(label=_("Email"))
    password = forms.CharField(label=_("Password"), widget=forms.PasswordInput)

    def clean(self):
        cleaned = super().clean()
        email = cleaned.get("email")
        password = cleaned.get("password")
        if email and password:
            user = authenticate(email=email, password=password)
            if user is None:
                raise forms.ValidationError(_("Invalid email or password."))
            cleaned["user"] = user
        return cleaned


class RegisterForm(forms.ModelForm):
    password1 = forms.CharField(
        label=_("Password"),
        widget=forms.PasswordInput,
        min_length=8,
        help_text=_("At least 8 characters; must pass the same checks as in the admin panel."),
    )
    password2 = forms.CharField(label=_("Repeat password"), widget=forms.PasswordInput, min_length=8)
    group = forms.ModelChoiceField(
        label=_("Group"),
        queryset=Group.objects.none(),
        required=False,
        help_text=_("Required for students — your study group."),
    )
    department = forms.ModelChoiceField(
        label=_("Department"),
        queryset=Department.objects.none(),
        required=False,
        help_text=_("Required for teachers — your department at the university."),
    )

    class Meta:
        model = User
        fields = ["email", "full_name", "role"]
        labels = {
            "full_name": _("Full name"),
            "role": _("Role"),
        }

    def __init__(self, *args, organization=None, **kwargs):
        self._organization = organization or get_default_organization()
        super().__init__(*args, **kwargs)
        allowed_roles = {User.Role.TEACHER, User.Role.STUDENT}
        self.fields["role"].choices = [
            (value, label) for value, label in self.fields["role"].choices if value in allowed_roles
        ]
        oid = self._organization.id
        self.fields["group"].queryset = Group.objects.filter(department__faculty__organization_id=oid).order_by("name")
        self.fields["department"].queryset = Department.objects.filter(faculty__organization_id=oid).order_by("name")

    def clean_password1(self):
        password = self.cleaned_data.get("password1")
        if password:
            validate_password(password, User(email=self.cleaned_data.get("email") or "", organization=self._organization))
        return password

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("password1") != cleaned.get("password2"):
            raise forms.ValidationError(_("Passwords do not match."))
        role = cleaned.get("role")
        if role == User.Role.STUDENT and not cleaned.get("group"):
            raise forms.ValidationError(_("Please select your group."))
        if role == User.Role.TEACHER and not cleaned.get("department"):
            raise forms.ValidationError(_("Please select your department."))
        return cleaned

    def clean_role(self):
        role = self.cleaned_data.get("role")
        if role == User.Role.ADMIN:
            raise forms.ValidationError(_("You cannot register as administrator."))
        return role

    def clean_group(self):
        group = self.cleaned_data.get("group")
        if group and group.department.faculty.organization_id != self._organization.id:
            raise forms.ValidationError(_("Invalid group for this organization."))
        return group

    def clean_department(self):
        dept = self.cleaned_data.get("department")
        if dept and dept.faculty.organization_id != self._organization.id:
            raise forms.ValidationError(_("Invalid department for this organization."))
        return dept

    @transaction.atomic
    def save(self, commit=True):
        user: User = super().save(commit=False)
        user.set_password(self.cleaned_data["password1"])
        user.organization = self._organization
        if commit:
            user.save()
            if user.role == User.Role.TEACHER:
                TeacherProfile.objects.get_or_create(
                    user=user,
                    defaults={"department": self.cleaned_data["department"]},
                )
            elif user.role == User.Role.STUDENT:
                StudentProfile.objects.get_or_create(
                    user=user,
                    defaults={"group": self.cleaned_data["group"]},
                )
        return user


class ProfileForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ["full_name"]
        labels = {"full_name": _("Full name")}

    def clean(self):
        cleaned = super().clean()
        if self.data is not None:
            vals = self.data.getlist("full_name")
            if vals:
                cleaned["full_name"] = (vals[0] or "").strip()
        return cleaned
