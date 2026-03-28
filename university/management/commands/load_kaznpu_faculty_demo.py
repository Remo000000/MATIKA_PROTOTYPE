"""
Load anonymized faculty-level slot features (demo «ҚазҰлтҚызПУ 1 факультет») into SlotPedagogicalFeatures.

JSON: data/kaznpu_faculty1_anonymized.json — matches slots by day_of_week + period.
"""

from __future__ import annotations

import json
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from scheduling.models import SlotPedagogicalFeatures
from university.models import Faculty, Organization, TimeSlot
from university.scope import get_default_organization


class Command(BaseCommand):
    help = "Apply anonymized KazNPU-style faculty demo data to slot pedagogical features"

    def add_arguments(self, parser):
        parser.add_argument(
            "--json-path",
            type=str,
            default="",
            help="Override path to JSON (default: data/kaznpu_faculty1_anonymized.json under BASE_DIR)",
        )
        parser.add_argument("--organization-id", type=int, default=None)

    def handle(self, *args, **options):
        base = Path(settings.BASE_DIR)
        path = Path(options["json_path"]) if options["json_path"] else base / "data" / "kaznpu_faculty1_anonymized.json"
        if not path.is_file():
            raise CommandError(f"Missing file: {path}")

        payload = json.loads(path.read_text(encoding="utf-8"))
        slots = payload.get("slots") or []

        org_id = options["organization_id"] or get_default_organization().id
        org = Organization.objects.filter(id=org_id).first()
        if not org:
            raise CommandError(f"Organization {org_id} not found")

        # Tag one faculty name for demo visibility (optional).
        fac, _ = Faculty.objects.get_or_create(organization=org, name="KazNPU — Faculty demo (anonymized)")

        n = 0
        for row in slots:
            dow = int(row["day_of_week"])
            period = int(row["period"])
            ts = TimeSlot.objects.filter(organization_id=org_id, day_of_week=dow, period=period).first()
            if not ts:
                continue
            SlotPedagogicalFeatures.objects.update_or_create(
                organization_id=org_id,
                timeslot=ts,
                defaults={
                    "student_fatigue_index": float(row.get("student_fatigue_index", 0.5)),
                    "survey_burden_index": float(row.get("survey_burden_index", 0.5)),
                    "lms_activity_normalized": float(row.get("lms_activity_normalized", 0.5)),
                    "historical_semester_load": float(row.get("historical_semester_load", 0.5)),
                },
            )
            n += 1

        from scheduling.ml.predict import clear_model_cache

        clear_model_cache()
        self.stdout.write(self.style.SUCCESS(f"KazNPU demo: updated {n} slots; faculty '{fac.name}'."))
