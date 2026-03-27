"""Pytest hooks shared across the test suite."""

from __future__ import annotations

import pytest
from django.conf import settings

from university.scope import get_default_organization


@pytest.fixture
def organization(db):
    return get_default_organization()


@pytest.fixture
def academic_period(db, organization):
    from scheduling.period import ensure_default_period

    return ensure_default_period(organization.id)


@pytest.fixture(scope="session", autouse=True)
def _ensure_static_root_exists() -> None:
    """WhiteNoise logs a warning if STATIC_ROOT is missing; tests hit the app via Client."""
    root = getattr(settings, "STATIC_ROOT", None)
    if root:
        root.mkdir(parents=True, exist_ok=True)
