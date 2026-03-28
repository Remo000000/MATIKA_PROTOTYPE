"""
Simulated LMS API (Moodle / Univer-style): returns per–time-slot engagement scores.

Used by ``sync_lms_activity`` to refresh ``SlotPedagogicalFeatures.lms_activity_normalized``.
"""

from __future__ import annotations

import hashlib
import random
from typing import Any


def _stable_noise(key: str) -> float:
    h = hashlib.sha256(key.encode("utf-8")).digest()
    return int.from_bytes(h[:4], "big") / 2**32


def fetch_simulated_lms_payload(organization_id: int, timeslot_ids: list[int]) -> dict[str, Any]:
    """
    Deterministic pseudo-random engagement per slot (demo / thesis).
    Shape mimics REST: { "source": "moodle_sim", "slots": { "<id>": { "engagement": 0..1 } } }
    """
    rng = random.Random(organization_id * 7919 + 42)
    slots: dict[str, dict[str, float]] = {}
    for ts_id in timeslot_ids:
        base = 0.35 + 0.45 * _stable_noise(f"{organization_id}:{ts_id}")
        jitter = rng.uniform(-0.06, 0.06)
        eng = max(0.0, min(1.0, base + jitter))
        slots[str(ts_id)] = {"engagement": eng, "logins_week": int(20 + 80 * eng), "submissions_pending": rng.randint(0, 3)}
    return {
        "source": "moodle_univer_simulation_v1",
        "organization_id": organization_id,
        "slots": slots,
    }
