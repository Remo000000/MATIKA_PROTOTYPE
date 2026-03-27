"""
Rewrite existing demo users to Kazakh-style names and @gmail.com emails.

Run when the DB still has old placeholders (matika.local, Teacher N, Student N):

    python manage.py apply_kazakh_demo_identities
"""

from __future__ import annotations

import random

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from accounts.models import User
from matika.kazakh_demo_names import (
    ADMIN_EMAIL,
    ADMIN_FULL_NAME,
    MAX_PAIR_POOL,
    build_teacher_and_student_pairs,
    email_from_pair,
    full_name_from_pair,
)
from university.models import StudentProfile, TeacherProfile


class Command(BaseCommand):
    help = "Set Kazakh demo emails and full names on existing teacher/student/admin users."

    @transaction.atomic
    def handle(self, *args, **options):
        rng = random.Random(42)

        n_teachers = TeacherProfile.objects.count()
        n_students = StudentProfile.objects.count()
        if n_teachers + n_students > MAX_PAIR_POOL:
            raise CommandError(
                f"Too many profiles ({n_teachers} teachers + {n_students} students); "
                f"max {MAX_PAIR_POOL} unique demo name pairs."
            )

        teacher_pairs, student_pairs, remainder = build_teacher_and_student_pairs(
            rng, n_teachers=n_teachers, n_students=n_students
        )

        teacher_user_ids = list(TeacherProfile.objects.order_by("id").values_list("user_id", flat=True))
        student_user_ids = list(StudentProfile.objects.order_by("id").values_list("user_id", flat=True))
        super_ids = list(User.objects.filter(is_superuser=True).order_by("id").values_list("pk", flat=True))

        to_touch = set(teacher_user_ids) | set(student_user_ids) | set(super_ids)
        if not to_touch:
            self.stdout.write(self.style.WARNING("No users to update."))
            return

        for uid in sorted(to_touch):
            u = User.objects.get(pk=uid)
            u.email = f"__tmp_{uid}@matika.local"
            u.save(update_fields=["email"])

        supers = list(User.objects.filter(pk__in=super_ids).order_by("id"))
        if supers:
            main = supers[0]
            main.email = ADMIN_EMAIL
            main.full_name = ADMIN_FULL_NAME
            main.set_password("admin12345")
            main.is_staff = True
            main.is_superuser = True
            main.save()
            for j, extra in enumerate(supers[1:]):
                if j >= len(remainder):
                    raise CommandError("Not enough spare name pairs for extra superusers; remove extra superusers.")
                fi, li = remainder[j]
                extra.email = email_from_pair(fi, li)
                extra.full_name = full_name_from_pair(fi, li)
                extra.set_password("admin12345")
                extra.save()

        for i, uid in enumerate(teacher_user_ids):
            fi, li = teacher_pairs[i]
            u = User.objects.get(pk=uid)
            u.email = email_from_pair(fi, li)
            u.full_name = full_name_from_pair(fi, li)
            u.set_password("teacher12345")
            u.save()

        for i, uid in enumerate(student_user_ids):
            fi, li = student_pairs[i]
            u = User.objects.get(pk=uid)
            u.email = email_from_pair(fi, li)
            u.full_name = full_name_from_pair(fi, li)
            u.set_password("student12345")
            u.save()

        self.stdout.write(
            self.style.SUCCESS(
                f"Updated superuser(s): {len(super_ids)}, teachers: {n_teachers}, students: {n_students}."
            )
        )
