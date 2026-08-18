from django.apps import AppConfig


class SmsAppConfig(AppConfig):
    # `default_auto_field` ataylab berilmagan — u `settings.DEFAULT_AUTO_FIELD`
    # dan olinadi, aks holda mavjud migratsiyalar qayta yaratilishi kerak bo'lardi.
    name = 'apps.sms_app'

    def ready(self):
        # Tekshiruvlar import paytida ro'yxatdan o'tadi.
        from . import checks  # noqa: F401
