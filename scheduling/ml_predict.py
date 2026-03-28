"""
Neural slot-unfitness prediction (TensorFlow/Keras).

Trained model path: MEDIA_ROOT/scheduling_ml/slot_unfitness.keras

If TensorFlow or the model file is missing, scheduling falls back to a deterministic
heuristic from :class:`scheduling.models.SlotPedagogicalFeatures` only (no NN).
"""

from __future__ import annotations

import logging
from functools import lru_cache
from pathlib import Path

from django.conf import settings

from scheduling.models import SlotPedagogicalFeatures
from university.models import TimeSlot

logger = logging.getLogger(__name__)

FEATURE_SIZE = 7

# Max extra penalty units added on top of teacher preference penalties (see services.py).
ML_PENALTY_SCALE = 12


def model_file_path() -> Path:
    root = Path(getattr(settings, "MEDIA_ROOT", "") or "")
    return root / "scheduling_ml" / "slot_unfitness.keras"


def _try_import_tf():
    try:
        import tensorflow as tf  # noqa: WPS433 — runtime optional dependency

        return tf
    except Exception as exc:  # pragma: no cover - env specific
        logger.debug("TensorFlow not available: %s", exc)
        return None


@lru_cache(maxsize=1)
def _load_keras_model():
    tf = _try_import_tf()
    if tf is None:
        return None
    path = model_file_path()
    if not path.is_file():
        return None
    try:
        return tf.keras.models.load_model(path)
    except Exception as exc:
        logger.warning("Could not load Keras model from %s: %s", path, exc)
        return None


def clear_model_cache() -> None:
    _load_keras_model.cache_clear()


def keras_model_available() -> bool:
    return _load_keras_model() is not None


def feature_vector_from_row(row: SlotPedagogicalFeatures | None, ts: TimeSlot) -> list[float]:
    if row is not None:
        fatigue = float(row.student_fatigue_index)
        survey = float(row.survey_burden_index)
        lms = float(row.lms_activity_normalized)
        hist = float(row.historical_semester_load)
    else:
        fatigue = survey = lms = hist = 0.5

    dow = int(ts.day_of_week)
    period = int(ts.period)
    monday_morning = 1.0 if (dow == 1 and period <= 2) else 0.0

    return [
        dow / 7.0,
        min(period, 12) / 12.0,
        max(0.0, min(1.0, fatigue)),
        max(0.0, min(1.0, survey)),
        max(0.0, min(1.0, lms)),
        max(0.0, min(1.0, hist)),
        monday_morning,
    ]


def feature_vector(organization_id: int, ts: TimeSlot) -> list[float]:
    row = (
        SlotPedagogicalFeatures.objects.filter(organization_id=organization_id, timeslot_id=ts.id)
        .only(
            "student_fatigue_index",
            "survey_burden_index",
            "lms_activity_normalized",
            "historical_semester_load",
        )
        .first()
    )
    return feature_vector_from_row(row, ts)


def heuristic_from_vector(v: list[float]) -> float:
    _, _, fatigue, survey, lms, hist, monday_morning = v
    raw = (
        0.38 * monday_morning
        + 0.22 * fatigue
        + 0.18 * survey
        + 0.12 * (1.0 - lms)
        + 0.10 * hist
    )
    return max(0.0, min(1.0, raw))


def heuristic_unfitness(organization_id: int, ts: TimeSlot) -> float:
    """Rule-based fallback when no trained network is available (same features, no NN)."""
    return heuristic_from_vector(feature_vector(organization_id, ts))


def predict_slot_unfitness(organization_id: int, ts: TimeSlot) -> float:
    """
    Return 0..1 (higher = less suitable for intensive lessons). Uses Keras when present
    and otherwise the heuristic above.
    """
    vec = feature_vector(organization_id, ts)
    model = _load_keras_model()
    if model is None:
        return heuristic_from_vector(vec)
    tf = _try_import_tf()
    if tf is None:
        return heuristic_from_vector(vec)
    x = tf.expand_dims(tf.constant(vec, dtype=tf.float32), 0)
    try:
        y = model(x, training=False)
        val = float(tf.squeeze(y))
        return max(0.0, min(1.0, val))
    except Exception as exc:
        logger.warning("Keras predict failed: %s", exc)
        return heuristic_from_vector(vec)


def ml_penalty_units(organization_id: int, ts: TimeSlot) -> int:
    """Integer penalty compatible with existing greedy / GA soft penalties."""
    u = predict_slot_unfitness(organization_id, ts)
    return int(round(ML_PENALTY_SCALE * u))


def slot_insights_for_organization(organization_id: int) -> tuple[list[dict], dict[str, object]]:
    """
    Rows for the admin «slot prediction / data analysis» UI: features per timeslot,
    predicted unfitness, and penalty units used by the scheduler.
    """
    path = model_file_path()
    keras_ready = keras_model_available()
    status: dict[str, object] = {
        "keras_ready": keras_ready,
        "model_file_exists": path.is_file(),
        "model_path": str(path),
        "prediction_backend": "keras" if keras_ready else "heuristic",
    }
    slots = list(
        TimeSlot.objects.filter(organization_id=organization_id).order_by("day_of_week", "period")
    )
    rows: list[dict] = []
    for ts in slots:
        row = SlotPedagogicalFeatures.objects.filter(
            organization_id=organization_id, timeslot_id=ts.id
        ).first()
        vec = feature_vector_from_row(row, ts)
        u = predict_slot_unfitness(organization_id, ts)
        pu = int(round(ML_PENALTY_SCALE * u))
        rows.append(
            {
                "timeslot": ts,
                "fatigue": vec[2],
                "survey_burden": vec[3],
                "lms": vec[4],
                "history": vec[5],
                "monday_morning": vec[6] >= 0.5,
                "unfitness": u,
                "unfitness_pct": max(0, min(100, int(round(100.0 * u)))),
                "penalty_units": pu,
                "has_features_row": row is not None,
            }
        )
    return rows, status
