from __future__ import annotations

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import translation
from django.utils.translation import gettext as _

from accounts.models import User
from matika.demo_seed_aliases import (
    kazakh_equipment_line,
    normalize_demo_equipment,
    to_english_seed,
)
from university.models import Department, Discipline, Faculty, Room, TeacherProfile


class Command(BaseCommand):
    help = "Rewrite demo faculty/department/discipline names to Kazakh (gettext kk) from English or legacy Russian."

    @transaction.atomic
    def handle(self, *args, **options):
        translation.activate("kk")
        updated = 0

        for obj in Faculty.objects.all():
            base = to_english_seed(obj.name)
            new_name = _(base)
            if new_name != obj.name:
                obj.name = new_name
                obj.save(update_fields=["name"])
                updated += 1

        for obj in Department.objects.select_related("faculty"):
            base = to_english_seed(obj.name)
            new_name = _(base)
            if new_name != obj.name:
                obj.name = new_name
                obj.save(update_fields=["name"])
                updated += 1

        for obj in Discipline.objects.all():
            base = to_english_seed(obj.name)
            new_name = _(base)
            if new_name != obj.name:
                obj.name = new_name
                obj.save(update_fields=["name"])
                updated += 1

        for obj in Room.objects.all():
            changed = False
            b = to_english_seed(obj.building) or obj.building
            if b == "Lab":
                new_b = _("Lab")
                if new_b != obj.building:
                    obj.building = new_b
                    changed = True
            elif obj.building and obj.building != b:
                obj.building = b
                changed = True

            rt = to_english_seed(obj.room_type) or obj.room_type
            if rt in ("Lecture", "Practice", "Laboratory"):
                new_rt = _(rt)
                if new_rt != obj.room_type:
                    obj.room_type = new_rt
                    changed = True
            elif obj.room_type and obj.room_type != rt:
                obj.room_type = rt
                changed = True

            if obj.equipment:
                en_line = normalize_demo_equipment(obj.equipment)
                if en_line:
                    new_eq = kazakh_equipment_line(en_line)
                    if new_eq != obj.equipment:
                        obj.equipment = new_eq
                        changed = True
            if changed:
                obj.save(update_fields=["building", "room_type", "equipment"])
                updated += 1

        title_keys = (
            "Senior Lecturer",
            "Associate Professor",
            "Professor",
            "Assistant Professor",
            "Docent",
            "Lecturer",
        )
        for obj in TeacherProfile.objects.select_related("user"):
            changed = False
            raw_title = to_english_seed(obj.academic_title) or obj.academic_title
            if raw_title in title_keys:
                new_t = _(raw_title)
                if new_t != obj.academic_title:
                    obj.academic_title = new_t
                    changed = True
            prof = to_english_seed(obj.profession) or obj.profession
            if prof:
                new_p = _(prof)
                if new_p != obj.profession:
                    obj.profession = new_p
                    changed = True
            if obj.bio.startswith("Teaching and research in "):
                tail = obj.bio.replace("Teaching and research in ", "").split(";")[0].strip()
                dept_en = to_english_seed(tail) or tail
                new_bio = _("Teaching and research in %(subject)s; focus on applied courses.") % {
                    "subject": _(dept_en)
                }
                if new_bio != obj.bio:
                    obj.bio = new_bio
                    changed = True
            if changed:
                obj.save(update_fields=["academic_title", "profession", "bio"])
                updated += 1

        for obj in User.objects.filter(full_name__in=["Admin MATIKA", "Admin"]):
            obj.full_name = _("Administrator MATIKA")
            obj.save(update_fields=["full_name"])
            updated += 1

        self.stdout.write(self.style.SUCCESS(f"Done. Updated entries: {updated}"))
