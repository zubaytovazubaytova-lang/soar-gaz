from django.apps import AppConfig


class TolovlarConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.tolovlar'
    verbose_name = "To'lovlar"

    def ready(self):
        from . import signals  # noqa: F401  (to'lov → buyurtma «to'langan»)
