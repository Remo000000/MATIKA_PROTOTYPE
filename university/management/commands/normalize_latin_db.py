from __future__ import annotations

from django.core.management.base import BaseCommand

from university.models import Department, Discipline, Faculty, Group, Room, StudentProfile, TeacherProfile
from university.utils import latinize_text


class Command(BaseCommand):
    help = "Normalize university dictionary text fields to Latin characters."

    def handle(self, *args, **options):
        updated = 0

        for obj in Faculty.objects.all():
            value = latinize_text(obj.name)
            if obj.name != value:
                obj.name = value
                obj.save(update_fields=["name"])
                updated += 1

        for obj in Department.objects.all():
            value = latinize_text(obj.name)
            if obj.name != value:
                obj.name = value
                obj.save(update_fields=["name"])
                updated += 1

        for obj in Group.objects.all():
            value = latinize_text(obj.name)
            if obj.name != value:
                obj.name = value
                obj.save(update_fields=["name"])
                updated += 1

        for obj in Room.objects.all():
            new_name = latinize_text(obj.name)
            new_building = latinize_text(obj.building)
            new_room_type = latinize_text(obj.room_type)
            new_equipment = latinize_text(obj.equipment)
            if (
                obj.name != new_name
                or obj.building != new_building
                or obj.room_type != new_room_type
                or obj.equipment != new_equipment
            ):
                obj.name = new_name
                obj.building = new_building
                obj.room_type = new_room_type
                obj.equipment = new_equipment
                obj.save(update_fields=["name", "building", "room_type", "equipment"])
                updated += 1

        for obj in Discipline.objects.all():
            new_name = latinize_text(obj.name)
            new_code = latinize_text(obj.code)
            if obj.name != new_name or obj.code != new_code:
                obj.name = new_name
                obj.code = new_code
                obj.save(update_fields=["name", "code"])
                updated += 1

        for obj in TeacherProfile.objects.all():
            new_profession = latinize_text(obj.profession)
            new_title = latinize_text(obj.academic_title)
            new_office = latinize_text(obj.office_room)
            new_bio = latinize_text(obj.bio)
            if (
                obj.profession != new_profession
                or obj.academic_title != new_title
                or obj.office_room != new_office
                or obj.bio != new_bio
            ):
                obj.profession = new_profession
                obj.academic_title = new_title
                obj.office_room = new_office
                obj.bio = new_bio
                obj.save(update_fields=["profession", "academic_title", "office_room", "bio"])
                updated += 1

        for obj in StudentProfile.objects.all():
            new_student_id = latinize_text(obj.student_id)
            if obj.student_id != new_student_id:
                obj.student_id = new_student_id
                obj.save(update_fields=["student_id"])
                updated += 1

        self.stdout.write(self.style.SUCCESS(f"Done. Updated rows: {updated}"))

