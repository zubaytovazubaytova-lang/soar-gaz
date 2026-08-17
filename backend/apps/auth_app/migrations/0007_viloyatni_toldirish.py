"""Mavjud yozuvlarda `viloyat` maydonini `tuman` dan aniqlab to'ldiradi.

Ilgari faqat tuman saqlanardi. Endi viloyat alohida maydon — eski yozuvlar
bo'sh qolmasligi uchun tuman nomidan viloyatini topib qo'yamiz.
"""
from django.db import migrations

from apps.auth_app.hududlar import tuman_viloyati


def toldir(apps, schema_editor):
    Foydalanuvchi = apps.get_model('auth_app', 'Foydalanuvchi')
    for user in Foydalanuvchi.objects.exclude(tuman='').filter(viloyat=''):
        viloyat = tuman_viloyati(user.tuman)
        if viloyat:
            user.viloyat = viloyat
            user.save(update_fields=['viloyat'])


def orqaga(apps, schema_editor):
    """Ortga qaytarilsa viloyat bo'shatiladi — ma'lumot tumanda saqlanib qoladi."""
    Foydalanuvchi = apps.get_model('auth_app', 'Foydalanuvchi')
    Foydalanuvchi.objects.update(viloyat='')


class Migration(migrations.Migration):

    dependencies = [
        ('auth_app', '0006_foydalanuvchi_mahalla_foydalanuvchi_viloyat'),
    ]

    operations = [
        migrations.RunPython(toldir, orqaga),
    ]
