from django.apps import AppConfig


class PBAABPConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "pbaabp"

    def ready(self):
        import pbaabp.monkeypatching  # noqa: F401
        import pbaabp.signals  # noqa: F401
