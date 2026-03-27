from django.contrib import admin

from university.models import (
    Department,
    Discipline,
    Faculty,
    Group,
    Organization,
    Room,
    StudentProfile,
    TeacherProfile,
    TimeSlot,
)


@admin.register(Organization)
class OrganizationAdmin(admin.ModelAdmin):
    list_display = ("name", "slug")
    search_fields = ("name", "slug")


@admin.register(Faculty)
class FacultyAdmin(admin.ModelAdmin):
    search_fields = ("name",)


@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    list_display = ("name", "faculty")
    list_filter = ("faculty",)
    search_fields = ("name",)


@admin.register(Group)
class GroupAdmin(admin.ModelAdmin):
    list_display = ("name", "department", "size")
    list_filter = ("department", "department__faculty")
    search_fields = ("name",)


@admin.register(Room)
class RoomAdmin(admin.ModelAdmin):
    list_display = ("name", "room_type", "building", "floor", "capacity")
    list_filter = ("room_type", "building")
    search_fields = ("name", "building", "room_type", "equipment")


@admin.register(Discipline)
class DisciplineAdmin(admin.ModelAdmin):
    list_display = ("name", "department", "code")
    list_filter = ("department", "department__faculty")
    search_fields = ("name", "code")


@admin.register(TimeSlot)
class TimeSlotAdmin(admin.ModelAdmin):
    list_display = ("day_of_week", "period", "start_time", "end_time")
    list_filter = ("day_of_week",)
    ordering = ("day_of_week", "period")


@admin.register(TeacherProfile)
class TeacherProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "department", "profession", "academic_title", "experience_years")
    list_filter = ("department", "department__faculty")
    search_fields = ("user__email", "user__full_name", "profession", "academic_title", "office_room")


@admin.register(StudentProfile)
class StudentProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "group", "student_id", "course_year", "gpa")
    list_filter = ("group", "group__department", "group__department__faculty")
    search_fields = ("user__email", "user__full_name", "group__name", "student_id")

