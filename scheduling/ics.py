from __future__ import annotations

from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from django.conf import settings
from django.core.exceptions import PermissionDenied
from django.http import HttpRequest
from django.utils.translation import gettext_lazy as _
from icalendar import Calendar, Event, vRecur

from scheduling.period import get_period_for_request
from scheduling.schedule_queryset import lessons_queryset_for_request


def _weekday_py_from_model(day_of_week: int) -> int:
    """TimeSlot.Mon=1..Sat=6 -> datetime.weekday() Mon=0..Sun=6."""
    return (int(day_of_week) - 1) % 7


def _first_date_on_or_after(start: date, weekday_py: int) -> date:
    delta = (weekday_py - start.weekday()) % 7
    return start + timedelta(days=delta)


def _lesson_slot_times(ts) -> tuple[time, time]:
    st = getattr(ts, "start_time", None)
    en = getattr(ts, "end_time", None)
    if st and en:
        return st, en
    if st and not en:
        return st, (datetime.combine(date.min, st) + timedelta(minutes=90)).time()
    base = time(9, 0)
    offset = max(0, (ts.period - 1) * 90)
    start_dt = datetime.combine(date.min, base) + timedelta(minutes=offset)
    end_dt = start_dt + timedelta(minutes=90)
    return start_dt.time(), end_dt.time()


def build_schedule_ics_bytes(*, request: HttpRequest) -> bytes:
    user = request.user
    oid = getattr(user, "organization_id", None)
    if oid is None:
        raise PermissionDenied(_("No organization context."))
    period = get_period_for_request(request, oid)
    qs = lessons_queryset_for_request(request)
    lessons = list(qs)

    tz = ZoneInfo(settings.TIME_ZONE)
    ap = period
    range_start = ap.start_date if ap and ap.start_date else date.today()
    range_end = ap.end_date if ap and ap.end_date else range_start + timedelta(days=180)
    if range_end < range_start:
        range_end = range_start + timedelta(days=180)

    cal = Calendar()
    cal.add("prodid", "-//MATIKA//Schedule//EN")
    cal.add("version", "2.0")
    cal.add("calscale", "GREGORIAN")
    cal.add("x-wr-calname", "MATIKA schedule")

    for lesson in lessons:
        ts = lesson.timeslot
        wd = _weekday_py_from_model(ts.day_of_week)
        first = _first_date_on_or_after(range_start, wd)
        if first > range_end:
            continue
        st_t, en_t = _lesson_slot_times(ts)
        dtstart = datetime.combine(first, st_t, tzinfo=tz)
        dtend = datetime.combine(first, en_t, tzinfo=tz)
        title = f"{lesson.discipline.name} — {lesson.room.name}"
        if getattr(user, "is_admin", False) or getattr(user, "is_teacher", False):
            title = f"{lesson.discipline.name} — {lesson.group.name} ({lesson.room.name})"
        elif getattr(user, "is_student", False):
            title = f"{lesson.discipline.name} — {lesson.teacher.user.get_short_name()} ({lesson.room.name})"

        ev = Event()
        host = request.META.get("HTTP_HOST", "matika.local")
        ev.add("uid", f"matika-lesson-{lesson.id}@{host}")
        ev.add("summary", title)
        ev.add("dtstart", dtstart)
        ev.add("dtend", dtend)
        until_dt = datetime.combine(range_end, time(23, 59, 59), tzinfo=tz)
        ev.add("rrule", vRecur(freq="weekly", until=until_dt))
        ev.add("location", lesson.room.name)
        cal.add_component(ev)

    return cal.to_ical()
