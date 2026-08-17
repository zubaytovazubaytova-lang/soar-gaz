"""
Admin foydalanuvchi yaratish skripti.

Ishlatish (parol muhit o'zgaruvchisidan olinadi — kodda saqlanmaydi):
    set ADMIN_TELEFON=+998918332249
    set ADMIN_PAROL=...
    python create_admin.py

ADMIN_PAROL berilmasa yangi admin YARATILMAYDI — bu productionda tasodifan
standart parol bilan hisob ochilib qolmasligi uchun.
"""
import os
import secrets
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'soargaz.settings')
django.setup()

from django.conf import settings                       # noqa: E402
from apps.auth_app.models import Foydalanuvchi         # noqa: E402

TELEFON = os.environ.get('ADMIN_TELEFON', '+998918332249')
PAROL = os.environ.get('ADMIN_PAROL', '')
ISM = os.environ.get('ADMIN_ISM', 'Administrator')

if Foydalanuvchi.objects.filter(telefon=TELEFON).exists():
    print(f"Admin allaqachon mavjud: {TELEFON}")
    raise SystemExit(0)

if not PAROL:
    if not settings.DEBUG:
        print("XATO: ADMIN_PAROL muhit o'zgaruvchisi berilmagan — admin yaratilmadi.")
        print("      set ADMIN_PAROL=... qilib qayta ishga tushiring.")
        raise SystemExit(1)
    # Dev rejimda tasodifiy parol yaratamiz va bir marta ekranga chiqaramiz
    PAROL = secrets.token_urlsafe(12)
    print(f"DIQQAT: ADMIN_PAROL berilmagan, tasodifiy parol yaratildi: {PAROL}")
    print("        Uni saqlab qo'ying — boshqa ko'rsatilmaydi.")

Foydalanuvchi.objects.create_user(
    telefon=TELEFON,
    password=PAROL,
    ism=ISM,
    rol='admin',
    is_staff=True,
    is_superuser=True,
)
print(f"Admin yaratildi: {ISM} ({TELEFON})")
