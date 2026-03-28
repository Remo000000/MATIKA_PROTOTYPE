"""Hard-constraint checks for generated timetables and Lesson DB rules."""

from __future__ import annotations

import uuid

import pytest
from django.db import IntegrityError

from accounts.models import User
from scheduling.models import AcademicPeriod, Lesson, TeachingRequirement
from scheduling.services import generate_schedule
from university.models import (
    Department,
    Discipline,
    Faculty,
    Group,
    Organization,
    Room,
    TeacherProfile,
    TimeSlot,
)


@pytest.fixture
def schedule_org_bundle(db):
    """Minimal org with one requirement, rooms, and time slots for greedy placement."""
    org = Organization.objects.create(name="Sched Test Org", slug=f"st-{uuid.uuid4().hex[:12]}")
    fac = Faculty.objects.create(organization=org, name="Faculty ST")
    dept = Department.objects.create(faculty=fac, name="Dept ST")
    group = Group.objects.create(department=dept, name="GRP-ST", size=20)
    disc = Discipline.objects.create(department=dept, name="Discipline ST")
    Room.objects.create(organization=org, name="Aud-A", capacity=40)
    Room.objects.create(organization=org, name="Aud-B", capacity=40)
    for day, period in ((1, 1), (2, 1), (3, 2)):
        TimeSlot.objects.create(organization=org, day_of_week=day, period=period)
    tu = User.objects.create_user(
        email=f"teacher-st-{uuid.uuid4().hex[:10]}@example.com",
        password="pass12345",
        role=User.Role.TEACHER,
        organization=org,
    )
    teacher = TeacherProfile.objects.create(user=tu, department=dept)
    TeachingRequirement.objects.create(
        group=group,
        discipline=disc,
        teacher=teacher,
        sessions_per_week=1,
        min_room_capacity=0,
    )
    period = AcademicPeriod.objects.create(
        organization=org,
        name="Term ST",
        slug=f"term-{uuid.uuid4().hex[:8]}",
        is_current=True,
    )
    return {"org": org, "period": period, "teacher": teacher, "group": group, "disc": disc}


@pytest.mark.django_db
def test_generate_schedule_no_teacher_double_booking(schedule_org_bundle):
    b = schedule_org_bundle
    res = generate_schedule(
        organization_id=b["org"].id,
        academic_period_id=b["period"].id,
        seed=42,
        clear_existing=True,
    )
    assert res.created >= 1
    lessons = Lesson.objects.filter(academic_period_id=b["period"].id)
    seen: set[tuple[int, int]] = set()
    for le in lessons:
        key = (le.teacher_id, le.timeslot_id)
        assert key not in seen
        seen.add(key)


@pytest.mark.django_db
def test_generate_schedule_no_group_double_booking(schedule_org_bundle):
    b = schedule_org_bundle
    generate_schedule(
        organization_id=b["org"].id,
        academic_period_id=b["period"].id,
        seed=7,
        clear_existing=True,
    )
    lessons = Lesson.objects.filter(academic_period_id=b["period"].id)
    seen: set[tuple[int, int]] = set()
    for le in lessons:
        key = (le.group_id, le.timeslot_id)
        assert key not in seen
        seen.add(key)


@pytest.mark.django_db
def test_generate_schedule_no_room_double_booking(schedule_org_bundle):
    b = schedule_org_bundle
    generate_schedule(
        organization_id=b["org"].id,
        academic_period_id=b["period"].id,
        seed=99,
        clear_existing=True,
    )
    lessons = Lesson.objects.filter(academic_period_id=b["period"].id)
    seen: set[tuple[int, int]] = set()
    for le in lessons:
        key = (le.room_id, le.timeslot_id)
        assert key not in seen
        seen.add(key)


@pytest.mark.django_db
def test_lesson_model_rejects_duplicate_teacher_slot(schedule_org_bundle):
    b = schedule_org_bundle
    ts = TimeSlot.objects.filter(organization=b["org"]).first()
    room = Room.objects.filter(organization=b["org"]).first()
    g2 = Group.objects.create(
        department=b["group"].department,
        name="GRP-ST-2",
        size=15,
    )
    disc2 = Discipline.objects.create(department=b["group"].department, name="Discipline ST 2")
    Lesson.objects.create(
        academic_period=b["period"],
        group=b["group"],
        discipline=b["disc"],
        teacher=b["teacher"],
        room=room,
        timeslot=ts,
    )
    with pytest.raises(IntegrityError):
        Lesson.objects.create(
            academic_period=b["period"],
            group=g2,
            discipline=disc2,
            teacher=b["teacher"],
            room=room,
            timeslot=ts,
        )


@pytest.mark.django_db
def test_lesson_model_rejects_duplicate_group_slot(schedule_org_bundle):
    b = schedule_org_bundle
    ts = TimeSlot.objects.filter(organization=b["org"]).order_by("day_of_week").first()
    rooms = list(Room.objects.filter(organization=b["org"]))
    assert len(rooms) >= 2
    tu2 = User.objects.create_user(
        email=f"t2-{uuid.uuid4().hex[:10]}@example.com",
        password="pass12345",
        role=User.Role.TEACHER,
        organization=b["org"],
    )
    t2 = TeacherProfile.objects.create(user=tu2, department=b["group"].department)
    disc2 = Discipline.objects.create(department=b["group"].department, name="Other Course")
    Lesson.objects.create(
        academic_period=b["period"],
        group=b["group"],
        discipline=b["disc"],
        teacher=b["teacher"],
        room=rooms[0],
        timeslot=ts,
    )
    with pytest.raises(IntegrityError):
        Lesson.objects.create(
            academic_period=b["period"],
            group=b["group"],
            discipline=disc2,
            teacher=t2,
            room=rooms[1],
            timeslot=ts,
        )
