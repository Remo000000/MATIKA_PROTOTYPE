#!/usr/bin/env python3
"""Compile django.po -> django.mo using polib (no GNU msgfmt required). Run from repo root."""

from __future__ import annotations

import sys
from pathlib import Path

try:
    import polib
except ImportError:
    print("Install polib: pip install polib", file=sys.stderr)
    sys.exit(1)

ROOT = Path(__file__).resolve().parents[1]
LOCALE = ROOT / "locale"


def main() -> None:
    for po_path in sorted(LOCALE.glob("*/LC_MESSAGES/django.po")):
        mo_path = po_path.with_suffix(".mo")
        po = polib.pofile(str(po_path))
        po.save_as_mofile(str(mo_path))
        print(f"OK {mo_path.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
