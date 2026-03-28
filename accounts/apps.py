from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class AccountsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "accounts"
    verbose_name = _("Accounts")

    def ready(self) -> None:
        from django.conf import settings

        from accounts import signals  # noqa: F401

        from django.db.backends.signals import connection_created

        def _configure_sqlite(sender, connection, **kwargs):
            if connection.vendor != "sqlite":
                return
            try:
                with connection.cursor() as cursor:
                    cursor.execute("PRAGMA journal_mode=WAL;")
                    cursor.execute("PRAGMA synchronous=NORMAL;")
                    cursor.execute("PRAGMA busy_timeout=30000;")
            except Exception:
                pass

        connection_created.connect(_configure_sqlite, dispatch_uid="matika_sqlite_wal")

        # Each login runs UPDATE last_login on accounts_user — extra SQLite write that often loses the lock on Windows.
        if settings.DEBUG and "sqlite" in settings.DATABASES.get("default", {}).get("ENGINE", ""):
            from django.contrib.auth.signals import user_logged_in

            user_logged_in.disconnect(dispatch_uid="update_last_login")

