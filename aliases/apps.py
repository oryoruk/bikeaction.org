from django.apps import AppConfig


class AliasesConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "aliases"

    def ready(self):
        import aliases.signals  # noqa: F401
