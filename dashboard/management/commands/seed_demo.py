from __future__ import annotations

import random
from datetime import date, time

from django.core.management.base import BaseCommand
from django.db import transaction

from accounts.models import Notification, User
from accounts.notification_kinds import DEMO_SCHEDULE_AVAILABLE, DEMO_SCHEDULE_REMINDER, DEMO_SEEDED
from matika.demo_name_cleanup import fix_placeholder_full_names_for_organization
from matika.kazakh_demo_names import (
    ADMIN_EMAIL,
    ADMIN_FULL_NAME,
    build_teacher_and_student_pairs,
    email_from_pair,
    full_name_from_pair,
)

TEACHER_TITLES = (
    "Senior Lecturer",
    "Associate Professor",
    "Professor",
    "Assistant Professor",
    "Docent",
    "Lecturer",
)


def _course_year_from_group_name(group_name: str) -> int:
    """Infer year of study from codes like SE-201 (2) or KN-101 (1)."""
    try:
        num = int(group_name.split("-", 1)[1])
    except (IndexError, ValueError):
        return 1
    y = num // 100
    return min(4, max(1, y)) if y else 1
from scheduling.models import AcademicPeriod, SlotPedagogicalFeatures, TeachingRequirement
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

        # Faculties → departments (specialties) → study groups. More groups = more students.
        faculty_map = {
            "Engineering": {
                "Software Engineering": [
                    "SE-101",
                    "SE-102",
                    "SE-103",
                    "SE-104",
                    "SE-201",
                    "SE-202",
                    "SE-203",
                ],
                "Data Science": [
                    "DS-101",
                    "DS-102",
                    "DS-103",
                    "DS-104",
                    "DS-201",
                    "DS-202",
                    "DS-203",
                ],
                "Computer Science": [
                    "KN-101",
                    "KN-102",
                    "KN-103",
                    "KN-104",
                    "KN-201",
                    "KN-202",
                    "KN-203",
                ],
                "Cybersecurity": ["CB-101", "CB-102", "CB-103", "CB-201", "CB-202"],
                "Information Systems": ["IS-101", "IS-102", "IS-201", "IS-202"],
            },
            "Economics": {
                "Finance": ["FI-101", "FI-102", "FI-103", "FI-104", "FI-201", "FI-202", "FI-203"],
                "Business Analytics": ["BA-101", "BA-102", "BA-103", "BA-201", "BA-202", "BA-203"],
                "Management": ["MN-101", "MN-102", "MN-103", "MN-201", "MN-202"],
            },
            "Natural Sciences": {
                "Physics": ["PH-101", "PH-102", "PH-103", "PH-201", "PH-202"],
                "Chemistry": ["CH-101", "CH-102", "CH-103", "CH-201", "CH-202"],
                "Biology": ["BI-101", "BI-102", "BI-201", "BI-202"],
            },
            "Social Sciences": {
                "Law": ["LW-101", "LW-102", "LW-103", "LW-201", "LW-202"],
                "Psychology": ["PS-101", "PS-102", "PS-103", "PS-201", "PS-202"],
                "Sociology": ["SC-101", "SC-102", "SC-201", "SC-202"],
            },
            "Humanities": {
                "Philology": ["FL-101", "FL-102", "FL-103", "FL-201"],
                "History": ["HS-101", "HS-102", "HS-201"],
            },
        }

        disciplines_map = {
            "Software Engineering": [
                "Algorithms",
                "Databases",
                "Web Development",
                "Software Architecture",
            ],
            "Data Science": [
                "Linear Algebra",
                "Probability",
                "Machine Learning",
                "Data Engineering",
            ],
            "Computer Science": [
                "Programming",
                "Computer Networks",
                "Operating Systems",
                "Discrete Mathematics",
            ],
            "Cybersecurity": [
                "Network Security",
                "Cryptography",
                "Secure Software Development",
                "Digital Forensics",
            ],
            "Information Systems": [
                "Systems Analysis",
                "ERP Systems",
                "IT Governance",
                "Business Process Modeling",
            ],
            "Finance": [
                "Microeconomics",
                "Accounting",
                "Corporate Finance",
                "Statistics",
            ],
            "Business Analytics": [
                "Business Intelligence",
                "SQL Analytics",
                "Forecasting",
                "Optimization",
            ],
            "Management": [
                "Strategic Management",
                "Organizational Behavior",
                "Human Resource Management",
                "Operations Management",
            ],
            "Physics": ["Mechanics", "Thermodynamics", "Electrodynamics", "Quantum Physics"],
            "Chemistry": ["General Chemistry", "Organic Chemistry", "Physical Chemistry", "Analytical Chemistry"],
            "Biology": ["Cell Biology", "Genetics", "Ecology", "Microbiology"],
            "Law": ["Constitutional Law", "Civil Law", "Criminal Law", "International Law"],
            "Psychology": ["General Psychology", "Social Psychology", "Cognitive Science", "Research Methods"],
            "Sociology": ["Social Theory", "Urban Sociology", "Social Policy", "Survey Methods"],
            "Philology": ["Comparative Literature", "Stylistics", "Linguistics", "Translation Studies"],
            "History": ["World History", "Historiography", "Kazakhstan History", "Archival Studies"],
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

        # Демо деректер: дүйсенбі таңертеңгі слоттарда шаршау мен сауалнама көрсеткіштері әдейі жоғары —
        # оңтайлы уақытты болжау тақырыбын көрсету үшін. Keras жоқ кезде эвристикалық әдіс осы белгілерді пайдаланады.
        # Pedagogical signals for ML / heuristic scheduling (e.g. Monday morning fatigue).
        # Use get_or_create + save, not update_or_create: the latter uses select_for_update()+get_or_create
        # and worsens SQLite "database is locked" when runserver holds the DB (Windows WAL).
        for ts in TimeSlot.objects.filter(organization=org):
            monday_morning = ts.day_of_week == 1 and ts.period <= 2
            fatigue = 0.82 if monday_morning else 0.35 + 0.06 * ((ts.period + ts.day_of_week) % 5)
            survey = 0.78 if monday_morning else 0.42
            lms = 0.28 if monday_morning else 0.55 + 0.02 * (ts.period % 3)
            hist = 0.72 if monday_morning else 0.48
            defaults = {
                "student_fatigue_index": min(1.0, fatigue),
                "survey_burden_index": survey,
                "lms_activity_normalized": min(1.0, lms),
                "historical_semester_load": hist,
                "target_unfitness_label": None,
            }
            obj, created = SlotPedagogicalFeatures.objects.get_or_create(
                organization=org,
                timeslot=ts,
                defaults=defaults,
            )
            if not created:
                for key, value in defaults.items():
                    setattr(obj, key, value)
                obj.save(
                    update_fields=[
                        "student_fatigue_index",
                        "survey_burden_index",
                        "lms_activity_normalized",
                        "historical_semester_load",
                        "target_unfitness_label",
                    ]
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

        n_departments = sum(len(depts) for depts in faculty_map.values())
        n_groups = sum(
            len(group_names) for depts in faculty_map.values() for group_names in depts.values()
        )
        students_per_group = 26
        teachers_per_department = 7
        n_teachers = n_departments * teachers_per_department
        n_students = n_groups * students_per_group
        teacher_pairs, student_pairs, _remainder = build_teacher_and_student_pairs(
            rng, n_teachers=n_teachers, n_students=n_students
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

                # Teachers (several per department, varied titles)
                teacher_profiles[dept_name] = []
                for t_i in range(teachers_per_department):
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
                    teacher_profile.academic_title = TEACHER_TITLES[t_i % len(TEACHER_TITLES)]
                    teacher_profile.experience_years = 3 + (teacher_counter % 22)
                    teacher_profile.office_room = f"A-{100 + teacher_counter}"
                    teacher_profile.phone = f"+7700{teacher_counter:06d}"
                    teacher_profile.bio = f"Teaching and research in {dept_name}; focus on applied courses."
                    teacher_profile.preferred_days = [1, 2, 4, 5]
                    teacher_profile.preferred_periods = [1, 2, 3, 4, 5]
                    teacher_profile.save()
                    teacher_profiles[dept_name].append(teacher_profile)
                    teacher_counter += 1

                # Groups and students
                for group_name in groups:
                    group, _ = Group.objects.get_or_create(
                        department=dept,
                        name=group_name,
                        defaults={"size": students_per_group},
                    )
                    group.department = dept
                    group.size = students_per_group
                    group.save()
                    group_objects.append(group)

                    for n in range(1, students_per_group + 1):
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
                        profile.course_year = _course_year_from_group_name(group_name)
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

        # Extra academic periods for the UI (timetable rows stay on slug `default`).
        for slug, label, sd, ed in (
            ("2024-autumn", "2024/2025 — Autumn semester", date(2024, 9, 2), date(2024, 12, 20)),
            ("2025-spring", "2024/2025 — Spring semester", date(2025, 1, 20), date(2025, 6, 15)),
            ("2025-autumn", "2025/2026 — Autumn semester", date(2025, 9, 1), date(2025, 12, 25)),
        ):
            ap_defaults = {
                "name": label,
                "start_date": sd,
                "end_date": ed,
                "is_current": False,
            }
            ap, ap_created = AcademicPeriod.objects.get_or_create(
                organization=org,
                slug=slug,
                defaults=ap_defaults,
            )
            if not ap_created:
                ap.name = label
                ap.start_date = sd
                ap.end_date = ed
                ap.is_current = False
                ap.save(update_fields=["name", "start_date", "end_date", "is_current"])

        renamed_placeholders = fix_placeholder_full_names_for_organization(org.id, rng)

        demo_seed_defaults = {
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
        }
        n_demo, seed_created = Notification.objects.get_or_create(
            user=admin,
            kind=DEMO_SEEDED,
            defaults=demo_seed_defaults,
        )
        if not seed_created:
            n_demo.payload = demo_seed_defaults["payload"]
            n_demo.title = demo_seed_defaults["title"]
            n_demo.body = demo_seed_defaults["body"]
            n_demo.save(update_fields=["payload", "title", "body"])

        first_teacher = User.objects.filter(role=User.Role.TEACHER, organization=org).order_by("id").first()
        first_student = User.objects.filter(role=User.Role.STUDENT, organization=org).order_by("id").first()
        if first_teacher:
            rem_defaults = {"payload": {}, "title": "", "body": ""}
            nt, nt_created = Notification.objects.get_or_create(
                user=first_teacher,
                kind=DEMO_SCHEDULE_REMINDER,
                defaults=rem_defaults,
            )
            if not nt_created:
                nt.payload = rem_defaults["payload"]
                nt.title = rem_defaults["title"]
                nt.body = rem_defaults["body"]
                nt.save(update_fields=["payload", "title", "body"])
        if first_student:
            av_defaults = {"payload": {}, "title": "", "body": ""}
            ns, ns_created = Notification.objects.get_or_create(
                user=first_student,
                kind=DEMO_SCHEDULE_AVAILABLE,
                defaults=av_defaults,
            )
            if not ns_created:
                ns.payload = av_defaults["payload"]
                ns.title = av_defaults["title"]
                ns.body = av_defaults["body"]
                ns.save(update_fields=["payload", "title", "body"])

        msg = (
            "Demo data created: "
            f"faculties={Faculty.objects.filter(organization=org).count()}, "
            f"departments={Department.objects.filter(faculty__organization=org).count()}, "
            f"groups={Group.objects.filter(department__faculty__organization=org).count()}, "
            f"disciplines={Discipline.objects.filter(department__faculty__organization=org).count()}, "
            f"teachers={TeacherProfile.objects.filter(department__faculty__organization=org).count()}, "
            f"students={StudentProfile.objects.filter(user__organization=org).count()}, "
            f"rooms={Room.objects.filter(organization=org).count()}, "
            f"academic_periods={AcademicPeriod.objects.filter(organization=org).count()}, "
            f"lessons={created_lessons}"
        )
        if renamed_placeholders:
            msg += f", placeholder_names_fixed={renamed_placeholders}"
        self.stdout.write(self.style.SUCCESS(msg))

