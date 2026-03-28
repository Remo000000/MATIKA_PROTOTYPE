"""Slot ML heuristic / penalty integration (no TensorFlow required for baseline tests)."""

import pytest
from django.test import TestCase

from scheduling.ml_predict import heuristic_from_vector, ml_penalty_units
from scheduling.models import SlotPedagogicalFeatures
from university.models import Organization, TimeSlot


@pytest.mark.django_db
class TestHeuristicMondayMorning(TestCase):
    def test_monday_morning_higher_than_midweek(self):
        org = Organization.objects.create(name="O", slug="o-ml-test")
        mon = TimeSlot.objects.create(organization=org, day_of_week=1, period=1)
        wed = TimeSlot.objects.create(organization=org, day_of_week=3, period=3)
        SlotPedagogicalFeatures.objects.create(
            organization=org,
            timeslot=mon,
            student_fatigue_index=0.8,
            survey_burden_index=0.75,
            lms_activity_normalized=0.3,
            historical_semester_load=0.7,
        )
        SlotPedagogicalFeatures.objects.create(
            organization=org,
            timeslot=wed,
            student_fatigue_index=0.4,
            survey_burden_index=0.4,
            lms_activity_normalized=0.55,
            historical_semester_load=0.45,
        )
        p_mon = ml_penalty_units(org.id, mon)
        p_wed = ml_penalty_units(org.id, wed)
        assert p_mon > p_wed

    def test_heuristic_vector_bounds(self):
        v = [1 / 7, 2 / 12, 0.5, 0.5, 0.5, 0.5, 0.0]
        h = heuristic_from_vector(v)
        assert 0.0 <= h <= 1.0


@pytest.mark.django_db
class TestSlotInsights(TestCase):
    def test_slot_insights_returns_rows_and_status(self):
        from scheduling.ml_predict import slot_insights_for_organization

        org = Organization.objects.create(name="O2", slug="o2-insights")
        ts = TimeSlot.objects.create(organization=org, day_of_week=2, period=3)
        SlotPedagogicalFeatures.objects.create(
            organization=org,
            timeslot=ts,
            student_fatigue_index=0.5,
            survey_burden_index=0.5,
            lms_activity_normalized=0.5,
            historical_semester_load=0.5,
        )
        rows, status = slot_insights_for_organization(org.id)
        assert len(rows) == 1
        assert status["prediction_backend"] in ("keras", "heuristic")
        assert "unfitness_pct" in rows[0]
