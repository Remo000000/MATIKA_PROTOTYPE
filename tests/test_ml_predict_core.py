"""ML vector helpers: bounds, determinism, and integration with scheduling.ml."""

from __future__ import annotations

import pytest
from django.test import TestCase

from scheduling.ml.predict import (
    ML_PENALTY_SCALE,
    clear_model_cache,
    feature_space_3d_plot_data,
    feature_vector,
    feature_vector_from_row,
    heuristic_from_vector,
    heuristic_unfitness,
    ml_penalty_units,
    predict_from_vector,
    predict_slot_unfitness,
    prediction_backend_label,
)
from scheduling.models import SlotPedagogicalFeatures
from university.models import Organization, TimeSlot


@pytest.mark.django_db
class TestPredictFromVector(TestCase):
    def test_predict_from_vector_in_unit_interval(self):
        vec = [3 / 7, 4 / 12, 0.4, 0.5, 0.6, 0.3, 0.0]
        u = predict_from_vector(vec)
        assert 0.0 <= u <= 1.0

    def test_clear_model_cache_runs(self):
        clear_model_cache()

    def test_prediction_backend_label(self):
        assert prediction_backend_label() in (
            "keras_mlp",
            "keras_transformer",
            "heuristic",
        )


@pytest.mark.django_db
def test_feature_vector_from_row_defaults_without_pedagogical_row():
    org = Organization.objects.create(name="Ovec", slug="ovec-1")
    ts = TimeSlot.objects.create(organization=org, day_of_week=4, period=2)
    vec = feature_vector_from_row(None, ts)
    assert len(vec) == 7
    assert vec[2] == vec[3] == vec[4] == vec[5] == 0.5


@pytest.mark.django_db
def test_heuristic_unfitness_matches_heuristic_from_vector():
    org = Organization.objects.create(name="Ovec2", slug="ovec-2")
    ts = TimeSlot.objects.create(organization=org, day_of_week=5, period=3)
    SlotPedagogicalFeatures.objects.create(
        organization=org,
        timeslot=ts,
        student_fatigue_index=0.2,
        survey_burden_index=0.3,
        lms_activity_normalized=0.9,
        historical_semester_load=0.1,
    )
    vec = feature_vector(org.id, ts)
    assert heuristic_unfitness(org.id, ts) == heuristic_from_vector(vec)


@pytest.mark.django_db
def test_predict_slot_unfitness_is_bounded():
    org = Organization.objects.create(name="Ovec4", slug="ovec-4")
    ts = TimeSlot.objects.create(organization=org, day_of_week=2, period=4)
    u = predict_slot_unfitness(org.id, ts)
    assert 0.0 <= u <= 1.0


@pytest.mark.django_db
def test_ml_penalty_units_within_scale():
    org = Organization.objects.create(name="Ovec3", slug="ovec-3")
    ts = TimeSlot.objects.create(organization=org, day_of_week=1, period=1)
    units = ml_penalty_units(org.id, ts)
    assert 0 <= units <= ML_PENALTY_SCALE


@pytest.mark.django_db
def test_feature_space_3d_plot_data_empty_and_nonempty():
    org_empty = Organization.objects.create(name="O3d0", slug="o3d-empty")
    empty = feature_space_3d_plot_data(org_empty.id)
    assert empty["points"] == []
    assert empty["vector_dim"] == 7
    assert "heuristic_surface" in empty and empty["heuristic_surface"]["z"]
    assert len(empty["heuristic_surface"]["z"]) == len(empty["heuristic_surface"]["y"])

    org = Organization.objects.create(name="O3d1", slug="o3d-1")
    TimeSlot.objects.create(organization=org, day_of_week=2, period=3)
    data = feature_space_3d_plot_data(org.id)
    assert len(data["points"]) == 1
    p0 = data["points"][0]
    assert "x" in p0 and "y" in p0 and "z" in p0
    assert len(p0["vec"]) == 7
    assert 0.0 <= p0["z"] <= 1.0
    assert len(data["heuristic_surface"]["z"]) == len(data["heuristic_surface"]["y"])
    assert len(data["heuristic_surface"]["z"][0]) == len(data["heuristic_surface"]["x"])
