"""If an academic period ended, retrain the slot-unfitness model (cron-friendly)."""

from __future__ import annotations

from datetime import timedelta

from django.core.management import call_command
from django.core.management.base import BaseCommand
from django.utils import timezone

from scheduling.models import AcademicPeriod
from university.scope import get_default_organization


class Command(BaseCommand):
    help = "Retrain slot-unfitness Keras model after semester end (checks AcademicPeriod.end_date)"

    def add_arguments(self, parser):
        parser.add_argument("--organization-id", type=int, default=None)
        parser.add_argument("--dry-run", action="store_true")

    def handle(self, *args, **options):
        org_id = options["organization_id"] or get_default_organization().id
        today = timezone.now().date()
        ended = (
            AcademicPeriod.objects.filter(organization_id=org_id, end_date__isnull=False, end_date__lt=today)
            .order_by("-end_date")
            .first()
        )
        if not ended:
            self.stdout.write("No completed academic period with end_date in the past — skip retraining.")
            return
        if ended.end_date < today - timedelta(days=365 * 5):
            self.stdout.write(self.style.WARNING("Latest ended period is very old; still retraining if not dry-run."))

        if options["dry_run"]:
            self.stdout.write(self.style.SUCCESS(f"Would retrain for org {org_id} (period {ended.name} ended {ended.end_date})."))
            return

        call_command("train_slot_unfitness_model", organization_id=org_id)
        self.stdout.write(self.style.SUCCESS(f"Retrained after period: {ended.name}"))
