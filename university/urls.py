from django.urls import path

from university import views

app_name = "university"

urlpatterns = [
    path("", views.IndexView.as_view(), name="index"),
    path("import/csv/", views.CsvImportView.as_view(), name="csv_import"),
    path("manage/", views.AdminDataManagementView.as_view(), name="manage_data"),
    path("manage/users/", views.AdminUsersManageView.as_view(), name="manage_users"),
    path("manage/teachers/", views.AdminTeachersManageView.as_view(), name="manage_teachers"),
    path("manage/students/", views.AdminStudentsManageView.as_view(), name="manage_students"),
    path("manage/groups/", views.AdminGroupsManageView.as_view(), name="manage_groups"),
    path("manage/rooms/", views.AdminRoomsManageView.as_view(), name="manage_rooms"),
    path("manage/disciplines/", views.AdminDisciplinesManageView.as_view(), name="manage_disciplines"),
    path("manage/users/<int:pk>/edit/", views.UserEditView.as_view(), name="edit_user"),
    path("manage/teachers/<int:pk>/edit/", views.TeacherEditView.as_view(), name="edit_teacher"),
    path("manage/students/<int:pk>/edit/", views.StudentEditView.as_view(), name="edit_student"),
    path("manage/groups/<int:pk>/edit/", views.GroupEditView.as_view(), name="edit_group"),
    path("manage/rooms/<int:pk>/edit/", views.RoomEditView.as_view(), name="edit_room"),
    path("manage/disciplines/<int:pk>/edit/", views.DisciplineEditView.as_view(), name="edit_discipline"),
]

