from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class UniversityConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "university"
    verbose_name = _("University")

    def ready(self) -> None:
        # Register seed strings for gettext discovery; runtime translations come from compiled .mo.
        import university.translation_catalog  # noqa: F401

