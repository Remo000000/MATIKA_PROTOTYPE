from __future__ import annotations

import pytest

from scheduling.services import generate_schedule


@pytest.mark.django_db
def test_generate_schedule_no_data_returns_empty(organization, academic_period):
    res = generate_schedule(
        organization_id=organization.id,
        academic_period_id=academic_period.id,
        clear_existing=True,
    )
    assert res.created == 0
    assert res.skipped == 0
    assert res.conflicts == 0
