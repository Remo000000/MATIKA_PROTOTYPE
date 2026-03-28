"""Pull simulated LMS engagement and update SlotPedagogicalFeatures.lms_activity_normalized."""

from __future__ import annotations

from django.core.management.base import BaseCommand

from scheduling.lms_simulation import fetch_simulated_lms_payload
from scheduling.models import SlotPedagogicalFeatures
from university.models import TimeSlot
from university.scope import get_default_organization


class Command(BaseCommand):
    help = "Simulate Moodle/Univer LMS API and refresh LMS activity features per time slot"

    def add_arguments(self, parser):
        parser.add_argument("--organization-id", type=int, default=None)

    def handle(self, *args, **options):
        org_id = options["organization_id"] or get_default_organization().id
        ts_ids = list(TimeSlot.objects.filter(organization_id=org_id).values_list("id", flat=True))
        payload = fetch_simulated_lms_payload(org_id, ts_ids)
        slots = payload.get("slots") or {}
        n = 0
        for raw_id, data in slots.items():
            try:
                tid = int(raw_id)
            except ValueError:
                continue
            eng = float(data.get("engagement", 0.5))
            SlotPedagogicalFeatures.objects.filter(organization_id=org_id, timeslot_id=tid).update(
                lms_activity_normalized=max(0.0, min(1.0, eng))
            )
            n += 1
        from scheduling.ml.predict import clear_model_cache

        clear_model_cache()
        self.stdout.write(self.style.SUCCESS(f"LMS simulation: updated {n} slot rows (org {org_id})."))
