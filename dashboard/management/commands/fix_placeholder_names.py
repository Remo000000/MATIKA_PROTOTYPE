"""Assign real Kazakh-style demo names to users stuck with Преподаватель/Teacher/… (no deletes)."""

from __future__ import annotations

import random

from django.core.management.base import BaseCommand, CommandError
from django.db import OperationalError

from accounts.models import User
from matika.demo_name_cleanup import fix_placeholder_full_names_for_queryset, is_placeholder_full_name
from university.scope import get_default_organization


class Command(BaseCommand):
    help = (
        "Replace placeholder full_name values (Преподаватель, Teacher, empty, …) with unique demo names. "
        "Does not delete users — safe when Lessons reference teachers."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--teachers-only",
            action="store_true",
            help="Only users with role teacher.",
        )
        parser.add_argument(
            "--students-only",
            action="store_true",
            help="Only users with role student.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Print how many would be renamed without saving.",
        )

    def handle(self, *args, **options):
        org = get_default_organization()
        rng = random.Random(42)

        base = User.objects.filter(organization=org)
        if options["teachers_only"]:
            base = base.filter(role=User.Role.TEACHER)
        elif options["students_only"]:
            base = base.filter(role=User.Role.STUDENT)

        would = sum(1 for u in base if is_placeholder_full_name(u.full_name))
        if options["dry_run"]:
            self.stdout.write(self.style.WARNING(f"Would rename {would} user(s) in org {org.id}."))
            return

        try:
            n = fix_placeholder_full_names_for_queryset(base, rng)
        except OperationalError as exc:
            if "locked" in str(exc).lower():
                raise CommandError(
                    "SQLite: database is locked. Stop `python manage.py runserver`, close DB tools, "
                    "then run this command again."
                ) from exc
            raise
        self.stdout.write(self.style.SUCCESS(f"Renamed {n} user(s) with placeholder full_name (org {org.id})."))
