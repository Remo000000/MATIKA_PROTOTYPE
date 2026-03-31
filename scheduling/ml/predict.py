"""
Neural slot-unfitness prediction (TensorFlow/Keras).

Trained model path: MEDIA_ROOT/scheduling_ml/slot_unfitness.keras
Optional meta: MEDIA_ROOT/scheduling_ml/model_meta.json (transformer_week vs mlp_tabular)

If TensorFlow or the model file is missing, scheduling falls back to a deterministic
heuristic from :class:`scheduling.models.SlotPedagogicalFeatures` only (no NN).

Қазақша: слоттың «ыңғайсыздығын» болжау — Keras моделі барда нейрожелі, жоқта
SlotPedagogicalFeatures негізінде эвристикалық әдіс (толық НН емес).
"""

from __future__ import annotations

import json
import logging
from functools import lru_cache
from pathlib import Path
from typing import TYPE_CHECKING, Any

from django.conf import settings
from django.utils.translation import gettext as _

from scheduling.models import SlotPedagogicalFeatures
from university.models import TimeSlot

if TYPE_CHECKING:
    from university.models import StudentProfile

logger = logging.getLogger(__name__)

FEATURE_SIZE = 7

# Max extra penalty units added on top of teacher preference penalties (see services.py).
ML_PENALTY_SCALE = 12

_FEAT_NAMES = (
    "dow",
    "period",
    "fatigue",
    "survey",
    "lms",
    "history",
    "monday_morning",
)


def model_file_path() -> Path:
    root = Path(getattr(settings, "MEDIA_ROOT", "") or "")
    return root / "scheduling_ml" / "slot_unfitness.keras"


def model_meta_file_path() -> Path:
    root = Path(getattr(settings, "MEDIA_ROOT", "") or "")
    return root / "scheduling_ml" / "model_meta.json"


def _read_model_meta() -> dict[str, Any] | None:
    path = model_meta_file_path()
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        logger.warning("Could not read model meta: %s", exc)
        return None


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
    _seq_prediction_vector.cache_clear()


def keras_model_available() -> bool:
    return _load_keras_model() is not None


def _model_is_sequence(model) -> bool:
    """True if model expects (batch, time, 7); False for flat (batch, 7)."""
    try:
        shape = model.input_shape
        if shape is None:
            return False
        return len(shape) == 3 and shape[-1] == FEATURE_SIZE
    except Exception:
        return False


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


def apply_student_schedule_biases(vec: list[float], prefs: dict[str, Any] | None) -> list[float]:
    """Blend slot vector with student-stated sensitivities (0..1)."""
    if not prefs:
        return list(vec)
    v = list(vec)
    fs = float(prefs.get("fatigue_sensitivity", 0.5))
    ss = float(prefs.get("survey_sensitivity", 0.5))
    pm = float(prefs.get("prefer_morning", 0.5))
    v[2] = max(0.0, min(1.0, 0.5 + (v[2] - 0.5) * (0.4 + 1.2 * fs)))
    v[3] = max(0.0, min(1.0, 0.5 + (v[3] - 0.5) * (0.4 + 1.2 * ss)))
    early = 1.0 - min(1.0, v[1] * 1.2)
    v[6] = max(0.0, min(1.0, v[6] + 0.15 * (pm - 0.5) * early))
    return v


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


# Neutral baseline for ablation-style explainability (one feature at a time vs reference).
_EXPLAIN_BASELINE_VECTOR = [0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.0]

FEATURE_KEYS: tuple[str, ...] = (
    "feat_dow",
    "feat_period",
    "feat_fatigue",
    "feat_survey",
    "feat_lms",
    "feat_history",
    "feat_monday_morning",
)


def _week_matrix_for_meta(organization_id: int, meta: dict[str, Any]) -> tuple[Any, list[int]]:
    """Build (1, T, 7) tensor and slot id list; missing slots get zeros."""
    import numpy as np

    tf = _try_import_tf()
    sid_list = list(meta.get("slot_ids") or [])
    slots_by_id = {s.id: s for s in TimeSlot.objects.filter(organization_id=organization_id)}
    rows: list[list[float]] = []
    for sid in sid_list:
        ts = slots_by_id.get(sid)
        rows.append(feature_vector(organization_id, ts) if ts else [0.0] * FEATURE_SIZE)
    x = np.array([rows], dtype=np.float32)
    if tf is not None:
        x = tf.constant(x)
    return x, sid_list


def _predict_from_week_matrix(model, x_week) -> Any:
    import tensorflow as tf

    return model(x_week, training=False)


@lru_cache(maxsize=32)
def _seq_prediction_vector(organization_id: int, meta_key: str) -> tuple[float, ...]:
    """Cached per-slot predictions for sequence model (tuple aligned with meta slot order)."""
    meta = json.loads(meta_key)
    model = _load_keras_model()
    tf = _try_import_tf()
    if model is None or tf is None or not _model_is_sequence(model):
        return tuple()

    x_week, sid_list = _week_matrix_for_meta(organization_id, meta)
    try:
        y = _predict_from_week_matrix(model, x_week)
        arr = y.numpy().reshape(-1)
        return tuple(float(arr[i]) for i in range(len(sid_list)))
    except Exception as exc:
        logger.warning("Sequence forward pass failed: %s", exc)
        return tuple()


def predict_from_vector(vec: list[float]) -> float:
    """
    Run Keras on the 7-d feature vector when the model is an MLP; else heuristic.
    Sequence (Transformer) models need full-week context — vector-only calls use the heuristic.
    """
    model = _load_keras_model()
    if model is None:
        return heuristic_from_vector(vec)
    if _model_is_sequence(model):
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


def predict_slot_unfitness(
    organization_id: int,
    ts: TimeSlot,
    *,
    student_prefs: dict[str, Any] | None = None,
) -> float:
    """
    Return 0..1 (higher = less suitable for intensive lessons).
    Uses Transformer sequence model, MLP, or heuristic. Optional student_prefs personalize the vector.
    """
    vec = feature_vector(organization_id, ts)
    biased_vec = apply_student_schedule_biases(vec, student_prefs) if student_prefs else vec

    model = _load_keras_model()
    meta = _read_model_meta()
    if model is not None and meta and meta.get("architecture") == "transformer_week" and _model_is_sequence(model):
        sid_list = list(meta.get("slot_ids") or [])
        if ts.id not in sid_list:
            return heuristic_from_vector(biased_vec)
        if student_prefs:
            import numpy as np

            tf = _try_import_tf()
            slots_by_id = {s.id: s for s in TimeSlot.objects.filter(organization_id=organization_id)}
            rows = []
            for sid in sid_list:
                tsi = slots_by_id.get(sid)
                row_vec = feature_vector(organization_id, tsi) if tsi else [0.0] * FEATURE_SIZE
                if tsi and tsi.id == ts.id:
                    row_vec = apply_student_schedule_biases(row_vec, student_prefs)
                rows.append(row_vec)
            mat = np.array([rows], dtype=np.float32)
            try:
                y = model(tf.constant(mat, dtype=tf.float32), training=False)
                idx = sid_list.index(ts.id)
                val = float(tf.squeeze(y[0, idx]))
                return max(0.0, min(1.0, val))
            except Exception as exc:
                logger.warning("Personalized sequence predict failed: %s", exc)
                return heuristic_from_vector(biased_vec)
        meta_key = json.dumps(
            {"slot_ids": sid_list, "seq_len": meta.get("seq_len")},
            sort_keys=True,
        )
        preds = _seq_prediction_vector(organization_id, meta_key)
        if len(preds) == len(sid_list):
            idx = sid_list.index(ts.id)
            return max(0.0, min(1.0, preds[idx]))
        return heuristic_from_vector(biased_vec)

    return predict_from_vector(biased_vec)


def predict_slot_unfitness_for_student(
    organization_id: int,
    ts: TimeSlot,
    student_profile: "StudentProfile",
) -> float:
    prefs = getattr(student_profile, "schedule_preferences", None) or {}
    return predict_slot_unfitness(organization_id, ts, student_prefs=prefs if isinstance(prefs, dict) else {})


def explainability_ablation(organization_id: int, ts: TimeSlot) -> list[dict]:
    """
    SHAP-like attribution: per-feature impact vs a neutral baseline (ablation deltas),
    normalized to percentage shares. Works with sequence models (full week) or MLP/heuristic.
    """
    model = _load_keras_model()
    meta = _read_model_meta()
    if model is not None and meta and meta.get("architecture") == "transformer_week" and _model_is_sequence(model):
        sid_list = list(meta.get("slot_ids") or [])
        if ts.id not in sid_list:
            vec = feature_vector(organization_id, ts)
            base = predict_from_vector(vec)
            raw = [abs(base - predict_from_vector(_ablate_vec(vec, i))) for i in range(FEATURE_SIZE)]
        else:
            import numpy as np

            slots_by_id = {s.id: s for s in TimeSlot.objects.filter(organization_id=organization_id)}
            rows = []
            for sid in sid_list:
                tsi = slots_by_id.get(sid)
                rows.append(feature_vector(organization_id, tsi) if tsi else [0.0] * FEATURE_SIZE)
            mat = np.array([rows], dtype=np.float32)

            def pred_full(m: Any) -> float:
                tfx = _try_import_tf()
                if tfx is None:
                    return heuristic_from_vector(list(m[0, sid_list.index(ts.id)]))
                y = model(tfx.constant(m, dtype=tfx.float32), training=False)
                idx = sid_list.index(ts.id)
                return float(tfx.squeeze(y[0, idx]))

            base = pred_full(mat)
            raw = []
            for i in range(FEATURE_SIZE):
                m2 = mat.copy()
                m2[0, sid_list.index(ts.id), i] = _EXPLAIN_BASELINE_VECTOR[i]
                raw.append(abs(base - pred_full(m2)))
    else:
        vec = feature_vector(organization_id, ts)
        base = predict_from_vector(vec)
        raw = []
        for i in range(FEATURE_SIZE):
            v2 = list(vec)
            v2[i] = _EXPLAIN_BASELINE_VECTOR[i]
            raw.append(abs(base - predict_from_vector(v2)))

    total = sum(raw) or 1.0
    out: list[dict] = []
    for i in range(FEATURE_SIZE):
        out.append(
            {
                "key": FEATURE_KEYS[i],
                "pct": round(100.0 * raw[i] / total, 1),
                "delta": raw[i],
            }
        )
    out.sort(key=lambda x: -x["pct"])
    return out


def _ablate_vec(vec: list[float], i: int) -> list[float]:
    v2 = list(vec)
    v2[i] = _EXPLAIN_BASELINE_VECTOR[i]
    return v2


def explanation_sentence(organization_id: int, ts: TimeSlot) -> str:
    """
    Short human-readable reason for the prediction (for UI / thesis), using top feature contributions.
    """
    vec = feature_vector(organization_id, ts)
    contrib = explainability_ablation(organization_id, ts)
    top = contrib[:3]
    fatigue_pct = int(round(vec[2] * 100))
    hist_pct = int(round(vec[5] * 100))
    parts: list[str] = []
    for row in top:
        key = row["key"]
        pct = row["pct"]
        if key == "feat_fatigue":
            parts.append(_("~%(pct)s%% from fatigue signal (students ~%(fatigue)s%%)") % {"pct": pct, "fatigue": fatigue_pct})
        elif key == "feat_history":
            parts.append(_("~%(pct)s%% from past-semester load (~%(h)s%%)") % {"pct": pct, "h": hist_pct})
        elif key == "feat_monday_morning":
            parts.append(_("~%(pct)s%% from Monday morning pattern") % {"pct": pct})
        elif key == "feat_lms":
            parts.append(_("~%(pct)s%% from LMS engagement proxy") % {"pct": pct})
        elif key == "feat_survey":
            parts.append(_("~%(pct)s%% from survey burden") % {"pct": pct})
        else:
            parts.append(_("~%(pct)s%% from time-slot position") % {"pct": pct})
    if not parts:
        return _("Insufficient data for explanation.")
    return "; ".join(parts)


def try_shap_for_slot(organization_id: int, ts: TimeSlot) -> list[float] | None:
    """SHAP values for the 7 features when the active model is an MLP; else None."""
    model = _load_keras_model()
    if model is None or _model_is_sequence(model):
        return None
    vec = feature_vector(organization_id, ts)
    try:
        from scheduling.ml.shap_explain import try_shap_values_for_vector

        return try_shap_values_for_vector(model, vec)
    except Exception:
        return None


def dashboard_ml_series(organization_id: int) -> tuple[list[dict], dict | None]:
    """
    Chart data: unfitness per timeslot, plus explanation for the worst slot.
    """
    slots = list(
        TimeSlot.objects.filter(organization_id=organization_id).order_by("day_of_week", "period")
    )
    if not slots:
        return [], None
    series: list[dict] = []
    worst_ts: TimeSlot | None = None
    worst_u = -1.0
    for ts in slots:
        u = predict_slot_unfitness(organization_id, ts)
        series.append(
            {
                "label": str(ts),
                "u": round(u, 4),
                "u_pct": max(0, min(100, int(round(100.0 * u)))),
            }
        )
        if u > worst_u:
            worst_u = u
            worst_ts = ts
    worst_block: dict | None = None
    if worst_ts is not None:
        worst_block = {
            "slot_label": str(worst_ts),
            "contributions": explainability_ablation(organization_id, worst_ts),
        }
    return series, worst_block


def neural_vs_heuristic_series(organization_id: int) -> list[dict]:
    """Per-slot comparison for analytics: model (or seq) vs heuristic-only."""
    slots = list(
        TimeSlot.objects.filter(organization_id=organization_id).order_by("day_of_week", "period")
    )
    out: list[dict] = []
    for ts in slots:
        vec = feature_vector(organization_id, ts)
        h = heuristic_from_vector(vec)
        n = predict_slot_unfitness(organization_id, ts)
        out.append(
            {
                "label": str(ts),
                "heuristic": round(h, 4),
                "neural": round(n, 4),
                "delta": round(h - n, 4),
            }
        )
    return out


def prediction_backend_label() -> str:
    model = _load_keras_model()
    if model is None:
        return "heuristic"
    if _model_is_sequence(model):
        return "keras_transformer"
    return "keras_mlp"


def ml_penalty_units(organization_id: int, ts: TimeSlot) -> int:
    """Integer penalty compatible with existing greedy / GA soft penalties."""
    u = predict_slot_unfitness(organization_id, ts)
    return int(round(ML_PENALTY_SCALE * u))


# Grid resolution for the heuristic surface Z = heuristic(fatigue, survey) with other dims fixed.
_SURFACE_GRID_N = 28


def _baseline_vector_for_surface(organization_id: int) -> list[float]:
    """Anchor weekday, period, LMS, history, Monday flag; fatigue and survey are swept on the grid."""
    slots = list(
        TimeSlot.objects.filter(organization_id=organization_id).order_by("day_of_week", "period")
    )
    if slots:
        ts = slots[0]
        return feature_vector(organization_id, ts)
    return list(_EXPLAIN_BASELINE_VECTOR)


def feature_space_3d_plot_data(organization_id: int) -> dict[str, Any]:
    """
    3D chart data:

    * **heuristic_surface** — closed-form rule only: ``Z = heuristic_from_vector(v)`` on a grid where
      only fatigue (index 2) and survey (index 3) vary; indices 0–1, 4–6 come from the first slot
      (or neutral baseline). This is the **analytic** landscape, not Keras.

    * **points** — one scatter point per real slot: X/Y = fatigue/survey, Z = ``predict_slot_unfitness``
      (Keras / sequence / heuristic per project rules). Each point includes the full **7D** feature
      vector for tooltips.
    """
    n = _SURFACE_GRID_N
    base = _baseline_vector_for_surface(organization_id)
    xs = [round(i / max(1, n - 1), 4) for i in range(n)]
    ys = [round(i / max(1, n - 1), 4) for i in range(n)]
    z_grid: list[list[float]] = []
    for yi in ys:
        row: list[float] = []
        for xj in xs:
            v = list(base)
            v[2] = xj
            v[3] = yi
            row.append(round(float(heuristic_from_vector(v)), 5))
        z_grid.append(row)

    slots = list(
        TimeSlot.objects.filter(organization_id=organization_id).order_by("day_of_week", "period")
    )
    points: list[dict[str, Any]] = []
    for ts in slots:
        row = SlotPedagogicalFeatures.objects.filter(
            organization_id=organization_id, timeslot_id=ts.id
        ).first()
        vec = feature_vector_from_row(row, ts)
        u = float(predict_slot_unfitness(organization_id, ts))
        points.append(
            {
                "x": round(float(vec[2]), 4),
                "y": round(float(vec[3]), 4),
                "z": round(u, 4),
                "label": str(ts),
                "vec": [round(float(t), 4) for t in vec],
            }
        )

    return {
        "heuristic_surface": {"x": xs, "y": ys, "z": z_grid},
        "points": points,
        "vector_dim": FEATURE_SIZE,
        "vector_labels": [
            "dow/7",
            "period/12",
            "fatigue",
            "survey",
            "lms",
            "history",
            "monday_morning",
        ],
        "grid_n": n,
        "axis_x_key": "fatigue",
        "axis_y_key": "survey_burden",
        "axis_z_key": "predicted_unfitness",
    }


def slot_insights_for_organization(organization_id: int) -> tuple[list[dict], dict[str, object]]:
    """
    Rows for the admin «slot prediction / data analysis» UI: features per timeslot,
    predicted unfitness, and penalty units used by the scheduler.
    """
    path = model_file_path()
    keras_ready = keras_model_available()
    meta = _read_model_meta()
    status: dict[str, object] = {
        "keras_ready": keras_ready,
        "model_file_exists": path.is_file(),
        "model_path": str(path),
        "prediction_backend": prediction_backend_label(),
        "model_meta": meta or {},
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
        expl = explanation_sentence(organization_id, ts)
        pct = max(0, min(100, int(round(100.0 * u))))
        rows.append(
            {
                "timeslot": ts,
                "fatigue": vec[2],
                "survey_burden": vec[3],
                "lms": vec[4],
                "history": vec[5],
                "monday_morning": vec[6] >= 0.5,
                "unfitness": u,
                "unfitness_pct": pct,
                "penalty_units": pu,
                "has_features_row": row is not None,
                "explanation": expl,
            }
        )
    return rows, status
