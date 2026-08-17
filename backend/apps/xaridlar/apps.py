from django.apps import AppConfig


class XaridlarConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.xaridlar'
    verbose_name = 'Xaridlar (internet-do\'kon)'

    def ready(self):
        from . import signals  # noqa: F401  — to'lov holatini xaridga bog'laydi
