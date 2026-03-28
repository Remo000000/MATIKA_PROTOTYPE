from __future__ import annotations

import uuid

import pytest
from django.urls import reverse

from accounts import notification_kinds as nk
from accounts.models import Notification, ProfileChangeRequest, User
from university.models import Department, Faculty, Group, StudentProfile


@pytest.mark.django_db
def test_profile_change_request_model_persists(organization):
    u = User.objects.create_user(
        email="orm-check@example.com",
        password="x",
        role=User.Role.STUDENT,
        organization=organization,
    )
    ProfileChangeRequest.objects.create(user=u, proposed_full_name="Test Name")
    assert ProfileChangeRequest.objects.filter(user=u).count() == 1


@pytest.mark.django_db
def test_student_profile_save_creates_pending_and_notifies_admin(client, organization):
    sid = uuid.uuid4().hex[:12]
    fac = Faculty.objects.create(name="Test Faculty", organization=organization)
    dept = Department.objects.create(name="Test Dept", faculty=fac)
    group = Group.objects.create(name="TG-1", department=dept, size=20)
    student = User.objects.create_user(
        email=f"stu-{sid}@example.com",
        password="testpass12345",
        role=User.Role.STUDENT,
        organization=organization,
        full_name="Old Name",
    )
    StudentProfile.objects.create(user=student, group=group)
    admin = User.objects.create_user(
        email=f"adm-{sid}@example.com",
        password="testpass12345",
        role=User.Role.ADMIN,
        organization=organization,
    )
    assert student.is_admin is False
    assert client.login(email=student.email, password="testpass12345")
    response = client.post(reverse("accounts:profile"), {"full_name": "New Approved Name"})
    assert response.status_code == 302
    assert response.url == reverse("accounts:profile")
    student.refresh_from_db()
    assert student.full_name == "Old Name"
    pending = ProfileChangeRequest.objects.filter(
        user=student,
        status=ProfileChangeRequest.Status.PENDING,
    ).first()
    assert pending is not None
    assert pending.proposed_full_name == "New Approved Name"
    admin_notif = Notification.objects.filter(user=admin).first()
    assert admin_notif is not None
    assert admin_notif.profile_change_request_id == pending.pk
    assert admin_notif.kind == nk.PROFILE_CHANGE_PENDING
    assert admin_notif.payload.get("email") == student.email

    assert client.login(email=admin.email, password="testpass12345")
    approve_url = reverse("accounts:approve_profile_request", kwargs={"pk": pending.pk})
    response = client.post(approve_url)
    assert response.status_code == 302
    assert response.url == reverse("accounts:notifications")
    student.refresh_from_db()
    assert student.full_name == "New Approved Name"
    pending.refresh_from_db()
    assert pending.status == ProfileChangeRequest.Status.APPROVED


@pytest.mark.django_db
def test_admin_profile_saves_directly(client, organization):
    admin = User.objects.create_user(
        email="adm-direct@example.com",
        password="testpass12345",
        role=User.Role.ADMIN,
        organization=organization,
        full_name="Admin Old",
    )
    assert client.login(email=admin.email, password="testpass12345")
    response = client.post(reverse("accounts:profile"), {"full_name": "Admin New"})
    assert response.status_code == 302
    admin.refresh_from_db()
    assert admin.full_name == "Admin New"
    assert not ProfileChangeRequest.objects.filter(user=admin).exists()
