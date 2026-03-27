from __future__ import annotations

from rest_framework import serializers
from rest_framework.generics import ListAPIView
from rest_framework.permissions import IsAuthenticated

from scheduling.models import Lesson
from scheduling.schedule_queryset import lessons_queryset_for_request


class LessonListSerializer(serializers.ModelSerializer):
    group_name = serializers.CharField(source="group.name", read_only=True)
    discipline_name = serializers.CharField(source="discipline.name", read_only=True)
    room_name = serializers.CharField(source="room.name", read_only=True)
    day_of_week = serializers.IntegerField(source="timeslot.day_of_week", read_only=True)
    period = serializers.IntegerField(source="timeslot.period", read_only=True)
    teacher_name = serializers.SerializerMethodField()

    class Meta:
        model = Lesson
        fields = [
            "id",
            "academic_period_id",
            "group_name",
            "discipline_name",
            "teacher_name",
            "room_name",
            "day_of_week",
            "period",
            "is_draft",
            "color",
        ]

    def get_teacher_name(self, obj: Lesson) -> str:
        return obj.teacher.user.get_short_name()


class LessonListAPIView(ListAPIView):
    """Read-only weekly lessons for the current org and selected academic period (session / ?period=)."""

    permission_classes = [IsAuthenticated]
    serializer_class = LessonListSerializer

    def get_queryset(self):
        return lessons_queryset_for_request(self.request)
