"""Optional SHAP attributions when the loaded model is an MLP on a 7-d vector."""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


def try_shap_values_for_vector(model: Any, vec: list[float], background: Any | None = None) -> list[float] | None:
    """
    Return 7 SHAP values (approximate) for one prediction, or None if unavailable.
    Uses DeepExplainer when shap and TensorFlow are importable.
    """
    try:
        import numpy as np
        import shap
        import tensorflow as tf
    except Exception as exc:  # pragma: no cover
        logger.debug("SHAP/TF import failed: %s", exc)
        return None

    try:
        x = np.array([vec], dtype=np.float32)
        if background is None:
            rng = np.random.default_rng(0)
            background = rng.uniform(0.0, 1.0, size=(32, 7)).astype(np.float32)
        explainer = shap.DeepExplainer(model, background)
        sv = explainer.shap_values(x)
        if isinstance(sv, list):
            sv = sv[0]
        row = np.asarray(sv).reshape(-1)[:7]
        return [float(v) for v in row]
    except Exception as exc:
        logger.debug("SHAP DeepExplainer failed: %s", exc)
        return None
