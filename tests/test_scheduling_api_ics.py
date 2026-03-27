from __future__ import annotations

import pytest
from django.urls import reverse


@pytest.mark.django_db
def test_api_lessons_requires_authentication(client):
    url = reverse("scheduling:api_lessons")
    response = client.get(url)
    assert response.status_code == 403


@pytest.mark.django_db
def test_export_ics_redirects_to_login(client):
    url = reverse("scheduling:export_ics")
    response = client.get(url)
    assert response.status_code == 302
    assert "login" in (response.headers.get("Location") or "")
