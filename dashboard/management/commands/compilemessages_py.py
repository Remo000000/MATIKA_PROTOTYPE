from __future__ import annotations

from pathlib import Path

import polib
from django.conf import settings
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Compile locale .po files to .mo using pure Python (no GNU gettext required)."

    def handle(self, *args, **options):
        compiled = 0
        for locale_root in settings.LOCALE_PATHS:
            root = Path(locale_root)
            if not root.exists():
                continue
            for po_path in root.glob("*/LC_MESSAGES/django.po"):
                mo_path = po_path.with_suffix(".mo")
                po = polib.pofile(str(po_path))
                po.save_as_mofile(str(mo_path))
                compiled += 1
                self.stdout.write(self.style.SUCCESS(f"Compiled: {po_path} -> {mo_path.name}"))

        if not compiled:
            self.stdout.write(self.style.WARNING("No django.po files found in LOCALE_PATHS"))
        else:
            self.stdout.write(self.style.SUCCESS(f"Done. Compiled files: {compiled}"))

