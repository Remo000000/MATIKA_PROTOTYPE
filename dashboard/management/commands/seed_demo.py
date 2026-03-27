from __future__ import annotations

import random
from datetime import time

from django.core.management.base import BaseCommand
from django.db import transaction

from accounts.models import Notification, User
from accounts.notification_kinds import DEMO_SCHEDULE_AVAILABLE, DEMO_SCHEDULE_REMINDER, DEMO_SEEDED
from matika.kazakh_demo_names import (
    ADMIN_EMAIL,
    ADMIN_FULL_NAME,
    build_teacher_and_student_pairs,
    email_from_pair,
    full_name_from_pair,
)
from scheduling.models import TeachingRequirement
from scheduling.period import ensure_default_period
from scheduling.services import generate_schedule
from university.models import (
    Department,
    Discipline,
    Faculty,
    Group,
    Room,
    StudentProfile,
    TeacherProfile,
    TimeSlot,
)
from university.scope import get_default_organization


class Command(BaseCommand):
    help = "Seed demo data for MATIKA"

    def add_arguments(self, parser):
        parser.add_argument(
            "--skip-schedule",
            action="store_true",
            help="Populate users/reference data without lesson generation.",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        rng = random.Random(42)
        student_password = "student12345"
        teacher_password = "teacher12345"
        org = get_default_organization()

        def _ensure_user(email: str, role: str, full_name: str, password: str, **extra) -> User:
            user, _ = User.objects.get_or_create(
                email=email,
                defaults={"role": role, "full_name": full_name, "organization": org, **extra},
            )
            changed = False
            if user.organization_id != org.id:
                user.organization = org
                changed = True
            if user.role != role:
                user.role = role
                changed = True
            if user.full_name != full_name:
                user.full_name = full_name
                changed = True
            for key, value in extra.items():
                if getattr(user, key) != value:
                    setattr(user, key, value)
                    changed = True
            if not user.check_password(password):
                user.set_password(password)
                changed = True
            if changed:
                user.save()
            return user

        faculty_map = {
            "Engineering": {
                "Software Engineering": ["SE-101", "SE-102", "SE-103", "SE-201", "SE-202"],
                "Data Science": ["DS-101", "DS-102", "DS-103", "DS-201", "DS-202"],
            },
            "Economics": {
                "Finance": ["FI-101", "FI-102", "FI-201"],
                "Business Analytics": ["BA-101", "BA-102", "BA-201"],
            },
        }

        disciplines_map = {
            "Software Engineering": ["Algorithms", "Databases", "Web Development", "Software Architecture"],
            "Data Science": ["Linear Algebra", "Probability", "Machine Learning", "Data Engineering"],
            "Finance": ["Microeconomics", "Accounting", "Corporate Finance", "Statistics"],
            "Business Analytics": ["Business Intelligence", "SQL Analytics", "Forecasting", "Optimization"],
        }

        room_specs = [
            ("A-101", 40, "A", "Lecture", 1, "projector, speakers"),
            ("A-201", 36, "A", "Lecture", 2, "projector"),
            ("A-301", 32, "A", "Lecture", 3, "projector"),
            ("B-110", 28, "B", "Practice", 1, "whiteboard"),
            ("B-210", 30, "B", "Practice", 2, "whiteboard, projector"),
            ("LAB-1", 24, "Lab", "Laboratory", 1, "pc, internet"),
            ("LAB-2", 24, "Lab", "Laboratory", 2, "pc, internet"),
            ("LAB-3", 20, "Lab", "Laboratory", 3, "pc"),
        ]

        # Standard timeslots (Mon-Sat, 1..6)
        slot_times = {
            1: (time(8, 0), time(8, 50)),
            2: (time(9, 0), time(9, 50)),
            3: (time(10, 0), time(10, 50)),
            4: (time(11, 0), time(11, 50)),
            5: (time(12, 0), time(12, 50)),
            6: (time(13, 0), time(13, 50)),
        }
        for day in range(1, 7):
            for period in range(1, 7):
                st, et = slot_times[period]
                TimeSlot.objects.get_or_create(
                    organization=org,
                    day_of_week=day,
                    period=period,
                    defaults={"start_time": st, "end_time": et},
                )

        for name, capacity, building, room_type, floor, equipment in room_specs:
            room, _ = Room.objects.get_or_create(organization=org, name=name)
            room.capacity = capacity
            room.building = building
            room.room_type = room_type
            room.floor = floor
            room.equipment = equipment
            room.save()

        admin = _ensure_user(
            email=ADMIN_EMAIL,
            role=User.Role.ADMIN,
            full_name=ADMIN_FULL_NAME,
            password="admin12345",
            is_staff=True,
            is_superuser=True,
        )

        teacher_pairs, student_pairs, _remainder = build_teacher_and_student_pairs(
            rng, n_teachers=20, n_students=384
        )
        student_pair_idx = 0

        teacher_counter = 1
        student_counter = 1
        teacher_profiles: dict[str, list[TeacherProfile]] = {}
        group_objects: list[Group] = []

        for faculty_name, departments in faculty_map.items():
            faculty, _ = Faculty.objects.get_or_create(organization=org, name=faculty_name)
            for dept_name, groups in departments.items():
                dept, _ = Department.objects.get_or_create(faculty=faculty, name=dept_name)

                # Disciplines (specialties direction content)
                dept_disciplines: list[Discipline] = []
                for idx, disc_name in enumerate(disciplines_map.get(dept_name, []), start=1):
                    code = f"{dept_name[:2].upper()}{idx:02d}"
                    disc, _ = Discipline.objects.get_or_create(
                        department=dept,
                        name=disc_name,
                        defaults={"code": code},
                    )
                    if not disc.code:
                        disc.code = code
                        disc.save(update_fields=["code"])
                    dept_disciplines.append(disc)

                # Teachers
                teacher_profiles[dept_name] = []
                for t_i in range(5):
                    fi, li = teacher_pairs[teacher_counter - 1]
                    email = email_from_pair(fi, li)
                    full_name = full_name_from_pair(fi, li)
                    teacher_u = _ensure_user(
                        email=email,
                        role=User.Role.TEACHER,
                        full_name=full_name,
                        password=teacher_password,
                    )
                    teacher_profile, _ = TeacherProfile.objects.get_or_create(user=teacher_u, defaults={"department": dept})
                    teacher_profile.department = dept
                    teacher_profile.profession = dept_name
                    teacher_profile.academic_title = "Senior Lecturer" if t_i == 0 else "Associate Professor"
                    teacher_profile.experience_years = 5 + teacher_counter
                    teacher_profile.office_room = f"A-{100 + teacher_counter}"
                    teacher_profile.phone = f"+7700{teacher_counter:06d}"
                    teacher_profile.bio = f"Specialist in {dept_name}."
                    teacher_profile.preferred_days = [1, 2, 4, 5]
                    teacher_profile.preferred_periods = [1, 2, 3, 4, 5]
                    teacher_profile.save()
                    teacher_profiles[dept_name].append(teacher_profile)
                    teacher_counter += 1

                # Groups and students
                for group_name in groups:
                    group, _ = Group.objects.get_or_create(department=dept, name=group_name, defaults={"size": 24})
                    group.department = dept
                    group.size = 24
                    group.save()
                    group_objects.append(group)

                    for n in range(1, 25):
                        fi, li = student_pairs[student_pair_idx]
                        student_pair_idx += 1
                        email = email_from_pair(fi, li)
                        full_name = full_name_from_pair(fi, li)
                        student_u = _ensure_user(
                            email=email,
                            role=User.Role.STUDENT,
                            full_name=full_name,
                            password=student_password,
                        )
                        profile, _ = StudentProfile.objects.get_or_create(user=student_u, defaults={"group": group})
                        profile.group = group
                        profile.student_id = f"{group_name}-{n:02d}"
                        profile.course_year = (
                            1 if any(x in group_name for x in ("101", "102", "103")) else 2
                        )
                        profile.phone = f"+7701{student_counter:06d}"
                        profile.gpa = round(rng.uniform(2.5, 4.0), 2)
                        profile.save()
                        student_counter += 1

                # Requirements by group (clean old for current groups)
                dept_teachers = teacher_profiles.get(dept_name, [])
                for group in Group.objects.filter(department=dept, name__in=groups):
                    TeachingRequirement.objects.filter(group=group).delete()
                    for disc in dept_disciplines:
                        teacher = rng.choice(dept_teachers)
                        TeachingRequirement.objects.create(
                            group=group,
                            discipline=disc,
                            teacher=teacher,
                            sessions_per_week=2 if disc.name in {"Algorithms", "Databases", "Machine Learning"} else 1,
                            min_room_capacity=group.size,
                        )

        if options.get("skip_schedule"):
            created_lessons = 0
        else:
            period = ensure_default_period(org.id)
            res = generate_schedule(
                organization_id=org.id,
                academic_period_id=period.id,
                clear_existing=True,
                seed=42,
            )
            created_lessons = res.created

        Notification.objects.update_or_create(
            user=admin,
            kind=DEMO_SEEDED,
            defaults={
                "payload": {
                    "lessons_count": created_lessons,
                    "teachers_count": TeacherProfile.objects.filter(
                        department__faculty__organization_id=org.id
                    ).count(),
                    "students_count": StudentProfile.objects.filter(user__organization_id=org.id).count(),
                    "groups_count": Group.objects.filter(department__faculty__organization_id=org.id).count(),
                    "rooms_count": Room.objects.filter(organization_id=org.id).count(),
                },
                "title": "",
                "body": "",
            },
        )

        first_teacher = User.objects.filter(role=User.Role.TEACHER, organization=org).order_by("id").first()
        first_student = User.objects.filter(role=User.Role.STUDENT, organization=org).order_by("id").first()
        if first_teacher:
            Notification.objects.update_or_create(
                user=first_teacher,
                kind=DEMO_SCHEDULE_REMINDER,
                defaults={"payload": {}, "title": "", "body": ""},
            )
        if first_student:
            Notification.objects.update_or_create(
                user=first_student,
                kind=DEMO_SCHEDULE_AVAILABLE,
                defaults={"payload": {}, "title": "", "body": ""},
            )

        self.stdout.write(
            self.style.SUCCESS(
                "Demo data created: "
                f"faculties={Faculty.objects.count()}, "
                f"departments={Department.objects.count()}, "
                f"groups={Group.objects.count()}, "
                f"disciplines={Discipline.objects.count()}, "
                f"teachers={TeacherProfile.objects.count()}, "
                f"students={StudentProfile.objects.count()}, "
                f"rooms={Room.objects.count()}, "
                f"lessons={created_lessons}"
            )
        )

