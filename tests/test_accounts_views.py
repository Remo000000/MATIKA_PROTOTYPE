from __future__ import annotations

import pytest
from django.urls import reverse

from accounts.models import Notification, User


@pytest.mark.django_db
def test_logout_get_returns_405(client):
    response = client.get(reverse("accounts:logout"))
    assert response.status_code == 405
    assert "POST" in response.get("Allow", "")


@pytest.mark.django_db
def test_logout_post_logs_out(client, organization):
    user = User.objects.create_user(
        email="logout-test@example.com",
        password="testpass12345",
        role=User.Role.STUDENT,
        organization=organization,
    )
    client.force_login(user)
    response = client.post(reverse("accounts:logout"))
    assert response.status_code == 302
    assert response.url == reverse("accounts:login")


@pytest.mark.django_db
def test_notification_mark_read_get_returns_405(client, organization):
    user = User.objects.create_user(
        email="notif-test@example.com",
        password="testpass12345",
        role=User.Role.STUDENT,
        organization=organization,
    )
    n = Notification.objects.create(user=user, title="t", body="b")
    response = client.get(reverse("accounts:notification_read", kwargs={"pk": n.pk}))
    assert response.status_code == 405


@pytest.mark.django_db
def test_notification_mark_read_post(client, organization):
    user = User.objects.create_user(
        email="notif-post@example.com",
        password="testpass12345",
        role=User.Role.STUDENT,
        organization=organization,
    )
    n = Notification.objects.create(user=user, title="t", body="b", is_read=False)
    client.force_login(user)
    response = client.post(reverse("accounts:notification_read", kwargs={"pk": n.pk}))
    assert response.status_code == 302
    n.refresh_from_db()
    assert n.is_read is True


@pytest.mark.django_db
def test_notifications_mark_all_read_post(client, organization):
    user = User.objects.create_user(
        email="notif-all@example.com",
        password="testpass12345",
        role=User.Role.STUDENT,
        organization=organization,
    )
    n1 = Notification.objects.create(user=user, title="a", body="b", is_read=False)
    n2 = Notification.objects.create(user=user, title="c", body="d", is_read=False)
    client.force_login(user)
    response = client.post(reverse("accounts:notifications_mark_all_read"))
    assert response.status_code == 302
    assert response.url == reverse("accounts:notifications")
    n1.refresh_from_db()
    n2.refresh_from_db()
    assert n1.is_read and n2.is_read


@pytest.mark.django_db
def test_notifications_list_sort_order(client, organization):
    user = User.objects.create_user(
        email="notif-sort@example.com",
        password="testpass12345",
        role=User.Role.STUDENT,
        organization=organization,
    )
    n_old = Notification.objects.create(user=user, title="old", body="x", is_read=True)
    n_new = Notification.objects.create(user=user, title="new", body="y", is_read=True)
    client.force_login(user)
    r_new = client.get(reverse("accounts:notifications"))
    assert list(r_new.context["object_list"]) == [n_new, n_old]
    r_old = client.get(reverse("accounts:notifications"), {"order": "old"})
    assert list(r_old.context["object_list"]) == [n_old, n_new]


@pytest.mark.django_db
def test_notification_to_student_is_copied_to_org_admins(organization):
    User.objects.create_user(
        email="admin-copy@example.com",
        password="testpass12345",
        role=User.Role.ADMIN,
        organization=organization,
    )
    student = User.objects.create_user(
        email="student-copy@example.com",
        password="testpass12345",
        role=User.Role.STUDENT,
        organization=organization,
    )
    Notification.objects.create(user=student, title="Student event", body="Details")
    assert Notification.objects.filter(
        user__email="admin-copy@example.com", title="Student event"
    ).exists()
