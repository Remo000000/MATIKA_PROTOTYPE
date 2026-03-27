from __future__ import annotations

import pytest
from django.urls import reverse

from accounts.models import User


@pytest.mark.django_db
def test_generate_schedule_redirects_non_admin(client, organization):
    user = User.objects.create_user(
        email="student-access@example.com",
        password="testpass12345",
        role=User.Role.STUDENT,
        organization=organization,
    )
    client.force_login(user)
    response = client.get(reverse("scheduling:generate"))
    assert response.status_code == 302
    assert response.url == reverse("scheduling:my_schedule")


@pytest.mark.django_db
def test_analytics_forbidden_for_student(client, organization):
    user = User.objects.create_user(
        email="stu-analytics@example.com",
        password="testpass12345",
        role=User.Role.STUDENT,
        organization=organization,
    )
    client.force_login(user)
    response = client.get(reverse("dashboard:analytics"))
    assert response.status_code == 403
