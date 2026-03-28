from django.urls import path

from scheduling import api_views, views

app_name = "scheduling"

urlpatterns = [
    path("my/", views.MyScheduleView.as_view(), name="my_schedule"),
    path("my-groups/", views.MyGroupsView.as_view(), name="my_groups"),
    path("preferences/", views.TeacherPreferencesView.as_view(), name="preferences"),
    path(
        "preferences/<int:pk>/approve/",
        views.ApproveTeacherPreferenceView.as_view(),
        name="approve_teacher_preferences",
    ),
    path(
        "preferences/<int:pk>/reject/",
        views.RejectTeacherPreferenceView.as_view(),
        name="reject_teacher_preferences",
    ),
    path("generate/", views.GenerateScheduleView.as_view(), name="generate"),
    path("export.xlsx", views.ExportScheduleXlsxView.as_view(), name="export_xlsx"),
    path("export.ics", views.ExportScheduleIcsView.as_view(), name="export_ics"),
    path("api/lessons/", api_views.LessonListAPIView.as_view(), name="api_lessons"),
]

