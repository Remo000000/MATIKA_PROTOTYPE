"""Persist last training metrics (accuracy, F1, MAE) next to the saved Keras file."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from django.conf import settings


def metrics_file_path() -> Path:
    root = Path(getattr(settings, "MEDIA_ROOT", "") or "")
    return root / "scheduling_ml" / "training_metrics.json"


def model_meta_path() -> Path:
    root = Path(getattr(settings, "MEDIA_ROOT", "") or "")
    return root / "scheduling_ml" / "model_meta.json"


def write_metrics(payload: dict[str, Any]) -> Path:
    path = metrics_file_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return path


def read_metrics() -> dict[str, Any] | None:
    path = metrics_file_path()
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
