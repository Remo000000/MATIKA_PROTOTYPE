from __future__ import annotations

import logging
import random
from dataclasses import dataclass

from django.db import IntegrityError, transaction

from scheduling.models import AlgorithmRunLog, Lesson, TeachingRequirement
from university.models import Room, TimeSlot

logger = logging.getLogger(__name__)

PALETTE = [
    "#58B2FF",
    "#8AD1FF",
    "#BEE6FF",
    "#7CB9FF",
    "#4FA3FF",
    "#6EC9FF",
]


@dataclass(frozen=True)
class GenerateResult:
    created: int
    skipped: int
    conflicts: int
    failure_samples: tuple[dict, ...] = ()


@dataclass(frozen=True)
class OptimizeResult:
    iterations: int
    population_size: int
    best_fitness: int
    initial_fitness: int
    hard_violations: int
    windows_penalty: int
    overload_penalty: int
    preference_penalty: int
    early_late_penalty: int


def generate_schedule(
    *,
    organization_id: int,
    academic_period_id: int,
    seed: int | None = None,
    clear_existing: bool = True,
    max_improve_steps: int = 800,
) -> GenerateResult:
    """
    Baseline: greedy placement by "hardness" (most constrained first).
    Improvement: local swaps / moves to reduce soft penalties (teacher preferences + student windows).

    Hard constraints:
    - teacher cannot be in two lessons at the same timeslot
    - room cannot be used by two lessons at the same timeslot
    - group cannot have two lessons at the same timeslot
    - room capacity must fit group size and requirement.min_room_capacity
    """
    rng = random.Random(seed)

    requirements = list(
        TeachingRequirement.objects.filter(
            group__department__faculty__organization_id=organization_id,
        ).select_related("group", "discipline", "teacher", "teacher__user")
    )
    timeslots = list(TimeSlot.objects.filter(organization_id=organization_id))
    rooms = list(Room.objects.filter(organization_id=organization_id))
    failure_samples: list[dict] = []

    def _sample(kind: str, **extra: object) -> None:
        if len(failure_samples) >= 40:
            return
        failure_samples.append({"kind": kind, **extra})

    if not requirements or not timeslots or not rooms:
        AlgorithmRunLog.objects.create(
            organization_id=organization_id,
            kind=AlgorithmRunLog.Kind.GENERATE,
            ok=False,
            message="Generation skipped: missing requirements, time slots, or rooms",
            details={
                "requirements": len(requirements),
                "timeslots": len(timeslots),
                "rooms": len(rooms),
                "organization_id": organization_id,
                "academic_period_id": academic_period_id,
            },
        )
        return GenerateResult(created=0, skipped=0, conflicts=0, failure_samples=tuple(failure_samples))

    # Precompute feasible rooms by requirement
    feasible_rooms: dict[int, list[Room]] = {}
    for req in requirements:
        cap_needed = max(req.group.size, req.min_room_capacity)
        feasible_rooms[req.id] = [r for r in rooms if r.capacity >= cap_needed]

    # Expand into session "jobs"
    jobs: list[TeachingRequirement] = []
    for req in requirements:
        jobs.extend([req] * req.sessions_per_week)

    def hardness(req: TeachingRequirement) -> tuple[int, int]:
        # less rooms => harder; teacher preferences narrowness also
        room_cnt = len(feasible_rooms.get(req.id, []))
        pref_days = len(req.teacher.preferred_days or [])
        pref_periods = len(req.teacher.preferred_periods or [])
        pref_narrow = (pref_days * pref_periods) if (pref_days and pref_periods) else 999
        return (room_cnt, pref_narrow)

    jobs.sort(key=hardness)

    org_lesson_q = {
        "group__department__faculty__organization_id": organization_id,
        "academic_period_id": academic_period_id,
    }

    if clear_existing:
        Lesson.objects.filter(**org_lesson_q).delete()

    created = 0
    skipped = 0
    conflicts = 0

    # Occupancy sets for hard constraints
    used_teacher: set[tuple[int, int]] = set()
    used_room: set[tuple[int, int]] = set()
    used_group: set[tuple[int, int]] = set()
    if not clear_existing:
        existing = Lesson.objects.filter(**org_lesson_q).values_list("teacher_id", "group_id", "room_id", "timeslot_id")
        for teacher_id, group_id, room_id, timeslot_id in existing:
            used_teacher.add((teacher_id, timeslot_id))
            used_group.add((group_id, timeslot_id))
            used_room.add((room_id, timeslot_id))

    # Greedy placement
    try:
        with transaction.atomic():
            for req in jobs:
                placed = False
                candidate_rooms = feasible_rooms.get(req.id, [])
                if not candidate_rooms:
                    skipped += 1
                    _sample(
                        "skipped_no_room",
                        requirement_id=req.id,
                        group=str(req.group),
                        discipline=str(req.discipline),
                        teacher=str(req.teacher),
                        min_capacity=max(req.group.size, req.min_room_capacity),
                    )
                    continue

                # Order timeslots: prefer teacher preferences and spread group
                ordered_slots = list(timeslots)
                rng.shuffle(ordered_slots)
                ordered_slots.sort(key=lambda ts: _slot_penalty(ts, req), reverse=False)

                for ts in ordered_slots:
                    if (req.teacher_id, ts.id) in used_teacher:
                        continue
                    if (req.group_id, ts.id) in used_group:
                        continue

                    room_candidates = list(candidate_rooms)
                    rng.shuffle(room_candidates)
                    room_candidates.sort(key=lambda r: abs(r.capacity - req.group.size))

                    for room in room_candidates:
                        if (room.id, ts.id) in used_room:
                            continue
                        # place
                        try:
                            Lesson.objects.create(
                                academic_period_id=academic_period_id,
                                group=req.group,
                                discipline=req.discipline,
                                teacher=req.teacher,
                                room=room,
                                timeslot=ts,
                                color=rng.choice(PALETTE),
                            )
                        except IntegrityError:
                            # Defensive check: DB can still reject in edge/race cases.
                            continue
                        used_teacher.add((req.teacher_id, ts.id))
                        used_group.add((req.group_id, ts.id))
                        used_room.add((room.id, ts.id))
                        created += 1
                        placed = True
                        break
                    if placed:
                        break

                if not placed:
                    conflicts += 1
                    _sample(
                        "conflict_no_slot",
                        requirement_id=req.id,
                        group=str(req.group),
                        discipline=str(req.discipline),
                        teacher=str(req.teacher),
                        feasible_rooms=len(candidate_rooms),
                        timeslots=len(timeslots),
                    )

        # Lightweight hill-climbing improvement (kept as a fast pass
        # before more advanced GA optimisation, if requested explicitly).
        _improve_schedule(
            rng=rng,
            steps=max_improve_steps,
            organization_id=organization_id,
            academic_period_id=academic_period_id,
        )

        AlgorithmRunLog.objects.create(
            organization_id=organization_id,
            kind=AlgorithmRunLog.Kind.GENERATE,
            ok=True,
            message="Greedy generation completed",
            details={
                "created": created,
                "skipped": skipped,
                "conflicts": conflicts,
                "clear_existing": clear_existing,
                "improve_steps": max_improve_steps,
                "organization_id": organization_id,
                "academic_period_id": academic_period_id,
                "failure_samples": failure_samples,
            },
        )
        return GenerateResult(
            created=created,
            skipped=skipped,
            conflicts=conflicts,
            failure_samples=tuple(failure_samples),
        )
    except Exception as exc:
        logger.exception("generate_schedule failed")
        AlgorithmRunLog.objects.create(
            organization_id=organization_id,
            kind=AlgorithmRunLog.Kind.GENERATE,
            ok=False,
            message=str(exc)[:255],
            details={"error": str(exc), "organization_id": organization_id, "academic_period_id": academic_period_id},
        )
        raise


def _slot_penalty_teacher(ts: TimeSlot, teacher) -> int:
    penalty = 0
    if teacher.preferred_days and ts.day_of_week not in teacher.preferred_days:
        penalty += 3
    if teacher.preferred_periods and ts.period not in teacher.preferred_periods:
        penalty += 2
    return penalty


def _slot_penalty(ts: TimeSlot, req: TeachingRequirement) -> int:
    return _slot_penalty_teacher(ts, req.teacher)


def _student_windows_penalty_from_lessons(lessons) -> int:
    """
    Penalize "windows" inside a day for each group.
    A window is a missing period between two lessons.
    """
    penalty = 0
    by_group: dict[int, dict[int, list[int]]] = {}
    for l in lessons:
        ts = l.timeslot
        if ts is None:
            continue
        by_group.setdefault(l.group_id, {}).setdefault(ts.day_of_week, []).append(ts.period)

    for _, by_day in by_group.items():
        for _, periods in by_day.items():
            periods = sorted(set(periods))
            if len(periods) < 3:
                continue
            for i in range(1, len(periods)):
                gap = periods[i] - periods[i - 1]
                if gap > 1:
                    penalty += (gap - 1) * 2
    return penalty


def _improve_schedule(*, rng: random.Random, steps: int, organization_id: int, academic_period_id: int) -> None:
    org_q = {
        "group__department__faculty__organization_id": organization_id,
        "academic_period_id": academic_period_id,
    }
    lessons = list(
        Lesson.objects.filter(**org_q).select_related("group", "teacher", "timeslot", "room")
    )
    if len(lessons) < 3:
        return

    slot_ids = list(TimeSlot.objects.filter(organization_id=organization_id).values_list("id", flat=True))
    rooms = list(Room.objects.filter(organization_id=organization_id))
    timeslots_by_id = {ts.id: ts for ts in TimeSlot.objects.filter(organization_id=organization_id)}
    if not slot_ids or not rooms:
        return

    def soft_score() -> int:
        s = 0
        for l in lessons:
            ts = timeslots_by_id.get(l.timeslot_id) or l.timeslot
            s += _slot_penalty_teacher(ts, l.teacher)
        s += _student_windows_penalty_from_lessons(lessons)
        return s

    best = soft_score()

    for _ in range(steps):
        if rng.random() < 0.6:
            # try move one lesson to another slot/room
            l = rng.choice(lessons)
            if l.is_frozen:
                continue
            new_slot = rng.choice(slot_ids)
            feasible_rooms = [r.id for r in rooms if r.capacity >= l.group.size]
            if not feasible_rooms:
                continue
            new_room = rng.choice(feasible_rooms)
            old_slot = l.timeslot_id
            old_room = l.room_id

            if new_slot == old_slot and new_room == old_room:
                continue

            # hard constraints check via unique_together collisions
            if (
                Lesson.objects.filter(**org_q)
                .filter(timeslot_id=new_slot, teacher_id=l.teacher_id)
                .exclude(id=l.id)
                .exists()
            ):
                continue
            if (
                Lesson.objects.filter(**org_q)
                .filter(timeslot_id=new_slot, group_id=l.group_id)
                .exclude(id=l.id)
                .exists()
            ):
                continue
            if (
                Lesson.objects.filter(**org_q)
                .filter(timeslot_id=new_slot, room_id=new_room)
                .exclude(id=l.id)
                .exists()
            ):
                continue

            Lesson.objects.filter(id=l.id).update(timeslot_id=new_slot, room_id=new_room)
            l.timeslot_id = new_slot
            l.room_id = new_room
            l.timeslot = timeslots_by_id[new_slot]
            cur = soft_score()
            if cur <= best:
                best = cur
            else:
                Lesson.objects.filter(id=l.id).update(timeslot_id=old_slot, room_id=old_room)
                l.timeslot_id = old_slot
                l.room_id = old_room
                l.timeslot = timeslots_by_id[old_slot]
        else:
            # swap timeslots between two lessons if no conflict
            a, b = rng.sample(lessons, 2)
            if a.is_frozen or b.is_frozen:
                continue
            if a.timeslot_id == b.timeslot_id:
                continue
            if (
                Lesson.objects.filter(**org_q)
                .filter(timeslot_id=b.timeslot_id, teacher_id=a.teacher_id)
                .exclude(id=a.id)
                .exists()
            ):
                continue
            if (
                Lesson.objects.filter(**org_q)
                .filter(timeslot_id=b.timeslot_id, group_id=a.group_id)
                .exclude(id=a.id)
                .exists()
            ):
                continue
            if (
                Lesson.objects.filter(**org_q)
                .filter(timeslot_id=a.timeslot_id, teacher_id=b.teacher_id)
                .exclude(id=b.id)
                .exists()
            ):
                continue
            if (
                Lesson.objects.filter(**org_q)
                .filter(timeslot_id=a.timeslot_id, group_id=b.group_id)
                .exclude(id=b.id)
                .exists()
            ):
                continue
            # Room+timeslot must stay unique (same as DB constraint).
            if (
                Lesson.objects.filter(**org_q)
                .filter(timeslot_id=b.timeslot_id, room_id=a.room_id)
                .exclude(id=a.id)
                .exists()
            ):
                continue
            if (
                Lesson.objects.filter(**org_q)
                .filter(timeslot_id=a.timeslot_id, room_id=b.room_id)
                .exclude(id=b.id)
                .exists()
            ):
                continue

            at, bt = a.timeslot_id, b.timeslot_id
            Lesson.objects.filter(id=a.id).update(timeslot_id=bt)
            Lesson.objects.filter(id=b.id).update(timeslot_id=at)
            a.timeslot_id = bt
            b.timeslot_id = at
            a.timeslot = timeslots_by_id[bt]
            b.timeslot = timeslots_by_id[at]
            cur = soft_score()
            if cur <= best:
                best = cur
            else:
                Lesson.objects.filter(id=a.id).update(timeslot_id=at)
                Lesson.objects.filter(id=b.id).update(timeslot_id=bt)
                a.timeslot_id = at
                b.timeslot_id = bt
                a.timeslot = timeslots_by_id[at]
                b.timeslot = timeslots_by_id[bt]


# === Genetic algorithm optimiser =====================================


def optimize_schedule(
    *,
    organization_id: int,
    academic_period_id: int,
    seed: int | None = None,
    population_size: int = 60,
    iterations: int = 120,
) -> OptimizeResult:
    """
    Genetic algorithm on top of the existing schedule.

    Hard constraints are never allowed in children that are written back
    to the database. During fitness evaluation they are heavily penalised.
    Frozen lessons are kept intact and never moved.
    """
    rng = random.Random(seed)
    org_q = {
        "group__department__faculty__organization_id": organization_id,
        "academic_period_id": academic_period_id,
    }

    base_lessons = list(
        Lesson.objects.filter(**org_q).select_related("group", "discipline", "teacher", "room", "timeslot")
    )
    if len(base_lessons) < 3:
        return OptimizeResult(
            iterations=0,
            population_size=0,
            best_fitness=0,
            initial_fitness=0,
            hard_violations=0,
            windows_penalty=0,
            overload_penalty=0,
            preference_penalty=0,
            early_late_penalty=0,
        )

    timeslots = list(TimeSlot.objects.filter(organization_id=organization_id))
    rooms = list(Room.objects.filter(organization_id=organization_id))
    if not timeslots or not rooms:
        return OptimizeResult(
            iterations=0,
            population_size=0,
            best_fitness=0,
            initial_fitness=0,
            hard_violations=0,
            windows_penalty=0,
            overload_penalty=0,
            preference_penalty=0,
            early_late_penalty=0,
        )

    # Represent an individual as mapping lesson_id -> (timeslot_id, room_id)
    frozen_ids = {l.id for l in base_lessons if l.is_frozen}
    base_genome: dict[int, tuple[int, int]] = {
        l.id: (l.timeslot_id, l.room_id) for l in base_lessons
    }

    def random_individual() -> dict[int, tuple[int, int]]:
        genome = dict(base_genome)
        # small random mutations
        mutable_ids = [lid for lid in genome.keys() if lid not in frozen_ids]
        for lid in mutable_ids:
            if rng.random() < 0.15:
                ts_id = rng.choice(timeslots).id
                # capacity-aware room choice
                lesson = next(bl for bl in base_lessons if bl.id == lid)
                feasible_rooms = [r for r in rooms if r.capacity >= lesson.group.size]
                room_id = rng.choice(feasible_rooms or rooms).id
                genome[lid] = (ts_id, room_id)
        return genome

    def decode(genome: dict[int, tuple[int, int]]) -> list[Lesson]:
        # Build lightweight lesson-like objects to evaluate fitness.
        snapshot: list[Lesson] = []
        idx_by_id = {l.id: l for l in base_lessons}
        for lid, (ts_id, room_id) in genome.items():
            src = idx_by_id[lid]
            clone = Lesson(
                id=lid,
                group=src.group,
                discipline=src.discipline,
                teacher=src.teacher,
                room=next(r for r in rooms if r.id == room_id),
                timeslot=next(t for t in timeslots if t.id == ts_id),
                color=src.color,
                is_frozen=src.is_frozen,
            )
            snapshot.append(clone)
        return snapshot

    def fitness(genome: dict[int, tuple[int, int]]) -> tuple[int, dict[str, int]]:
        lessons = decode(genome)

        # Hard constraints
        hard_violations = 0
        seen_teacher: set[tuple[int, int]] = set()
        seen_group: set[tuple[int, int]] = set()
        seen_room: set[tuple[int, int]] = set()

        for l in lessons:
            key_t = (l.teacher_id, l.timeslot_id)
            key_g = (l.group_id, l.timeslot_id)
            key_r = (l.room_id, l.timeslot_id)
            if key_t in seen_teacher:
                hard_violations += 1
            else:
                seen_teacher.add(key_t)
            if key_g in seen_group:
                hard_violations += 1
            else:
                seen_group.add(key_g)
            if key_r in seen_room:
                hard_violations += 1
            else:
                seen_room.add(key_r)
            # capacity
            if l.room.capacity < l.group.size:
                hard_violations += 1

        # Soft constraints (must use candidate genome, not DB state)
        windows_penalty = _student_windows_penalty_from_lessons(lessons)

        # overload: 3+ consecutive lessons for a group per day
        overload_penalty = 0
        by_group_day: dict[int, dict[int, list[int]]] = {}
        for l in lessons:
            by_group_day.setdefault(l.group_id, {}).setdefault(
                l.timeslot.day_of_week, []
            ).append(l.timeslot.period)
        for _, days in by_group_day.items():
            for _, periods in days.items():
                if len(periods) < 3:
                    continue
                p_sorted = sorted(periods)
                streak = 1
                for i in range(1, len(p_sorted)):
                    if p_sorted[i] == p_sorted[i - 1] + 1:
                        streak += 1
                    else:
                        if streak >= 3:
                            overload_penalty += (streak - 2) * 2
                        streak = 1
                if streak >= 3:
                    overload_penalty += (streak - 2) * 2

        # teacher preferences & early/late
        preference_penalty = 0
        early_late_penalty = 0
        for l in lessons:
            prefs_days = l.teacher.preferred_days or []
            prefs_periods = l.teacher.preferred_periods or []
            if prefs_days and l.timeslot.day_of_week not in prefs_days:
                preference_penalty += 3
            if prefs_periods and l.timeslot.period not in prefs_periods:
                preference_penalty += 2
            # early / late
            if l.timeslot.period == 1:
                early_late_penalty += 1
            if l.timeslot.period >= 6:
                early_late_penalty += 2

        # combine
        fitness_score = (
            -1000 * hard_violations
            - 10 * windows_penalty
            - 5 * overload_penalty
            - 3 * preference_penalty
            - 2 * early_late_penalty
        )

        breakdown = {
            "hard_violations": hard_violations,
            "windows_penalty": windows_penalty,
            "overload_penalty": overload_penalty,
            "preference_penalty": preference_penalty,
            "early_late_penalty": early_late_penalty,
        }
        return fitness_score, breakdown

    # Initial population
    population: list[dict[int, tuple[int, int]]] = [base_genome]
    for _ in range(population_size - 1):
        population.append(random_individual())

    def tournament_select(k: int = 3) -> dict[int, tuple[int, int]]:
        contenders = rng.sample(population, k=min(k, len(population)))
        scored = [(fitness(g)[0], g) for g in contenders]
        scored.sort(key=lambda x: x[0], reverse=True)
        return scored[0][1]

    def crossover(a: dict[int, tuple[int, int]], b: dict[int, tuple[int, int]]) -> dict[int, tuple[int, int]]:
        child: dict[int, tuple[int, int]] = {}
        for lid in a.keys():
            if lid in frozen_ids:
                child[lid] = a[lid]
                continue
            if rng.random() < 0.5:
                child[lid] = a[lid]
            else:
                child[lid] = b.get(lid, a[lid])
        return child

    def mutate(g: dict[int, tuple[int, int]], rate: float = 0.08) -> dict[int, tuple[int, int]]:
        mutated = dict(g)
        for lid, (ts_id, room_id) in list(mutated.items()):
            if lid in frozen_ids:
                continue
            if rng.random() < rate:
                ts_id = rng.choice(timeslots).id
                lesson = next(bl for bl in base_lessons if bl.id == lid)
                feasible_rooms = [r for r in rooms if r.capacity >= lesson.group.size]
                room_id = rng.choice(feasible_rooms or rooms).id
                mutated[lid] = (ts_id, room_id)
        return mutated

    best_genome = base_genome
    best_f, best_breakdown = fitness(best_genome)
    initial_fitness = best_f

    try:
        for _ in range(iterations):
            new_population: list[dict[int, tuple[int, int]]] = []
            # Elitism: keep a copy of the best
            new_population.append(best_genome)

            while len(new_population) < population_size:
                parent1 = tournament_select()
                parent2 = tournament_select()
                child = crossover(parent1, parent2)
                child = mutate(child)
                new_population.append(child)

            population = new_population

            # Evaluate and update global best
            for g in population:
                f, br = fitness(g)
                if f > best_f:
                    best_f, best_breakdown = f, br
                    best_genome = g

        # Never write back genomes that violate hard constraints.
        if best_breakdown["hard_violations"] > 0:
            AlgorithmRunLog.objects.create(
                organization_id=organization_id,
                kind=AlgorithmRunLog.Kind.OPTIMIZE,
                ok=False,
                message="Optimisation skipped apply: hard-constraint violations in best candidate",
                details={
                    "iterations": iterations,
                    "population_size": population_size,
                    "best_fitness": best_f,
                    "initial_fitness": initial_fitness,
                    "organization_id": organization_id,
                    "academic_period_id": academic_period_id,
                    **best_breakdown,
                },
            )
            return OptimizeResult(
                iterations=iterations,
                population_size=population_size,
                best_fitness=best_f,
                initial_fitness=initial_fitness,
                hard_violations=best_breakdown["hard_violations"],
                windows_penalty=best_breakdown["windows_penalty"],
                overload_penalty=best_breakdown["overload_penalty"],
                preference_penalty=best_breakdown["preference_penalty"],
                early_late_penalty=best_breakdown["early_late_penalty"],
            )

        # Apply by recreating only mutable lessons to avoid transient unique collisions.
        with transaction.atomic():
            mutable_lessons = {
                l.id: l
                for l in Lesson.objects.filter(**org_q)
                .select_related("group", "discipline", "teacher", "room", "timeslot")
                .filter(is_frozen=False)
            }
            Lesson.objects.filter(id__in=mutable_lessons.keys()).delete()
            to_create: list[Lesson] = []
            for lid, (ts_id, room_id) in best_genome.items():
                if lid in frozen_ids:
                    continue
                src = mutable_lessons.get(lid)
                if not src:
                    continue
                to_create.append(
                    Lesson(
                        academic_period_id=src.academic_period_id,
                        group=src.group,
                        discipline=src.discipline,
                        teacher=src.teacher,
                        room_id=room_id,
                        timeslot_id=ts_id,
                        color=src.color,
                        is_frozen=False,
                    )
                )
            Lesson.objects.bulk_create(to_create)

        AlgorithmRunLog.objects.create(
            organization_id=organization_id,
            kind=AlgorithmRunLog.Kind.OPTIMIZE,
            ok=True,
            message="GA optimisation completed",
            details={
                "iterations": iterations,
                "population_size": population_size,
                "best_fitness": best_f,
                "initial_fitness": initial_fitness,
                "organization_id": organization_id,
                "academic_period_id": academic_period_id,
                **best_breakdown,
            },
        )
    except Exception as exc:  # pragma: no cover - defensive logging
        logger.exception("GA optimisation failed")
        AlgorithmRunLog.objects.create(
            organization_id=organization_id,
            kind=AlgorithmRunLog.Kind.OPTIMIZE,
            ok=False,
            message=f"Error during GA optimisation: {exc}"[:255],
            details={"error": str(exc), "organization_id": organization_id, "academic_period_id": academic_period_id},
        )

    return OptimizeResult(
        iterations=iterations,
        population_size=population_size,
        best_fitness=best_f,
        initial_fitness=initial_fitness,
        hard_violations=best_breakdown["hard_violations"],
        windows_penalty=best_breakdown["windows_penalty"],
        overload_penalty=best_breakdown["overload_penalty"],
        preference_penalty=best_breakdown["preference_penalty"],
        early_late_penalty=best_breakdown["early_late_penalty"],
    )

