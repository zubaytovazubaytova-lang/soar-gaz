from django.apps import AppConfig


class AuthAppConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.auth_app'

    def ready(self):
        from . import signals  # noqa: F401  — Django paneli o'zgarishlarini jurnalga ulaydi
