"""Replace generic demo full_name values (Преподаватель, Teacher, …) with Kazakh-style names."""

from __future__ import annotations

import itertools
import random
import re
import time

from django.db import OperationalError, transaction
from django.db.models import QuerySet

from accounts.models import User
from matika.kazakh_demo_names import LATIN_FIRST, LATIN_LAST, full_name_from_pair

_PLACEHOLDER_EXACT = frozenset(
    {
        "преподаватель",
        "студент",
        "teacher",
        "student",
    }
)

# "Преподаватель 1", "Teacher 2", "teacher 12"
_PLACEHOLDER_RE = re.compile(
    r"^(преподаватель|студент|teacher|student)(\s+\d+)?$",
    re.IGNORECASE | re.UNICODE,
)


def is_placeholder_full_name(name: str | None) -> bool:
    raw = (name or "").strip()
    if not raw:
        return True
    if raw.lower() in _PLACEHOLDER_EXACT:
        return True
    if _PLACEHOLDER_RE.match(raw):
        return True
    return False


def fix_placeholder_full_names_for_queryset(
    users: QuerySet[User],
    rng: random.Random,
) -> int:
    """Assign unique Kazakh-style demo names; skips users already with real names."""
    pool = list(itertools.product(range(len(LATIN_FIRST)), range(len(LATIN_LAST))))
    rng.shuffle(pool)
    used = {(u.full_name or "").strip() for u in User.objects.all()}
    pi = 0
    n = 0
    for u in users.order_by("id"):
        if not is_placeholder_full_name(u.full_name):
            continue
        while pi < len(pool):
            fi, li = pool[pi]
            pi += 1
            candidate = full_name_from_pair(fi, li)
            if candidate in used:
                continue
            u.full_name = candidate
            for attempt in range(40):
                try:
                    # One transaction per row: avoids a broken outer atomic if SQLite is briefly locked.
                    with transaction.atomic():
                        u.save(update_fields=["full_name"])
                    break
                except OperationalError as exc:
                    if "locked" not in str(exc).lower() or attempt == 39:
                        raise
                    time.sleep(0.15)
            used.add(candidate)
            n += 1
            break
    return n


def fix_placeholder_full_names_for_organization(org_id: int, rng: random.Random) -> int:
    return fix_placeholder_full_names_for_queryset(User.objects.filter(organization_id=org_id), rng)
