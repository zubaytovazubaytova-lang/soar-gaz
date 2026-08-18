"""Ishga tushirishdagi tekshiruvlar — noto'g'ri sozlangan server ko'tarilmasin.

Muammo: `sms_yubor()` konsol rejimida HAR DOIM `True` qaytaradi. Produksiyada
`SMS_PROVAYDER` / `ESKIZ_*` berilmay qolsa tizim "kod yuborildi" deb javob
beradi, lekin mijoz SMS olmaydi va ilovaga umuman kira olmaydi. Hech qanday
xato ko'rinmagani uchun buni faqat foydalanuvchilar shikoyatidan bilish
mumkin edi.

Shuning uchun `DEBUG=False` bo'lganda bu holat XATO deb hisoblanadi: server
`manage.py check --deploy` yoki oddiy ishga tushishda darhol to'xtaydi.
`DEBUG=True` da esa hech narsa talab qilinmaydi — dev rejimda kod log'ga
chiqadi va shu yetarli.
"""

import sys

from django.conf import settings
from django.core.checks import Error, register

from .gateway import sozlanganmi


def _test_rejimimi():
    """Testlar ishlayaptimi?

    Django test runner `DEBUG` ni majburan `False` qiladi, shuning uchun
    tekshiruvsiz `manage.py test` har doim shu xato bilan to'xtardi va
    birorta test umuman ishga tushmasdi. Testlarda SMS baribir yuborilmaydi,
    demak provayder kalitlari kerak emas.
    """
    return 'test' in sys.argv or sys.argv[0].endswith(('pytest', 'pytest.exe'))


@register()
def sms_sozlangan_mi(app_configs, **kwargs):
    if settings.DEBUG or _test_rejimimi() or sozlanganmi():
        return []

    return [
        Error(
            "SMS provayder sozlanmagan, lekin DEBUG=False.",
            hint=(
                "Bu holatda OTP kod hech kimga yuborilmaydi va mijozlar "
                "tizimga kira olmaydi. Muhit o'zgaruvchilarini bering: "
                "SMS_PROVAYDER=eskiz, ESKIZ_EMAIL, ESKIZ_PAROL, ESKIZ_FROM."
            ),
            id='sms_app.E001',
        )
    ]
