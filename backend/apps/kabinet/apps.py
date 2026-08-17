from django.apps import AppConfig


class KabinetConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.kabinet'
    verbose_name = 'Mijoz kabineti'

    def ready(self):
        from . import signals  # noqa: F401  — buyurtma holati o'zgarsa bildirishnoma yaratadi
