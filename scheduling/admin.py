from django.contrib import admin

from scheduling.models import AlgorithmRunLog, Lesson, TeachingRequirement


@admin.register(TeachingRequirement)
class TeachingRequirementAdmin(admin.ModelAdmin):
    list_display = ("group", "discipline", "teacher", "sessions_per_week", "min_room_capacity")
    list_filter = ("group", "teacher", "discipline")
    search_fields = ("group__name", "discipline__name", "teacher__user__full_name", "teacher__user__email")


@admin.register(Lesson)
class LessonAdmin(admin.ModelAdmin):
    list_display = ("group", "discipline", "teacher", "room", "timeslot", "is_frozen")
    list_filter = ("group", "teacher", "room", "timeslot__day_of_week", "is_frozen")
    search_fields = ("group__name", "discipline__name", "teacher__user__full_name", "room__name")


@admin.register(AlgorithmRunLog)
class AlgorithmRunLogAdmin(admin.ModelAdmin):
    list_display = ("created_at", "organization", "kind", "ok", "message")
    list_filter = ("organization", "kind", "ok", "created_at")
    readonly_fields = ("created_at",)

