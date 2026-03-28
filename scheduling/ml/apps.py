from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class SchedulingMlConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "scheduling.ml"
    label = "scheduling_ml"
    verbose_name = _("Scheduling ML")
