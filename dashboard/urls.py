from django.urls import path

from dashboard import views

app_name = "dashboard"

urlpatterns = [
    path("", views.HomeView.as_view(), name="home"),
    path("analytics/", views.AnalyticsView.as_view(), name="analytics"),
    path("analytics/export.csv", views.AnalyticsExportCsvView.as_view(), name="analytics_export_csv"),
]

