"""SMS shlyuzi — haqiqiy provayder orqali xabar yuborish.

Provayder `SMS_PROVAYDER` sozlamasi bilan tanlanadi:
    'konsol'  — hech qayerga yuborilmaydi, faqat log (dev rejim, standart)
    'eskiz'   — Eskiz.uz (https://notify.eskiz.uz)

Serverda quyidagi muhit o'zgaruvchilari beriladi:
    SMS_PROVAYDER=eskiz
    ESKIZ_EMAIL=...
    ESKIZ_PAROL=...
    ESKIZ_FROM=4546          # tasdiqlangan nick

Kalitlar berilmasa tizim avtomatik 'konsol' rejimiga tushadi — sayt
ishlashdan to'xtamaydi, lekin log'da ogohlantirish chiqadi.
"""

import json
import logging
import urllib.error
import urllib.parse
import urllib.request

from django.conf import settings
from django.core.cache import cache

logger = logging.getLogger(__name__)

ESKIZ_BAZA = 'https://notify.eskiz.uz/api'
TOKEN_KESH_KALITI = 'eskiz_token'
TOKEN_MUDDATI = 60 * 60 * 24 * 25   # Eskiz tokeni ~30 kun, zaxira bilan olamiz


class SmsXato(Exception):
    """SMS yuborishda provayder xatosi."""


def _sozlama(nom, standart=''):
    return getattr(settings, nom, standart)


def _eskiz_token(yangila=False):
    """Eskiz access tokenini oladi va keshlaydi."""
    if not yangila:
        token = cache.get(TOKEN_KESH_KALITI)
        if token:
            return token

    malumot = urllib.parse.urlencode({
        'email': _sozlama('ESKIZ_EMAIL'),
        'password': _sozlama('ESKIZ_PAROL'),
    }).encode()
    so_rov = urllib.request.Request(ESKIZ_BAZA + '/auth/login', data=malumot, method='POST')
    try:
        with urllib.request.urlopen(so_rov, timeout=10) as javob:
            natija = json.loads(javob.read())
    except (urllib.error.URLError, ValueError) as xato:
        raise SmsXato(f"Eskiz avtorizatsiyasi muvaffaqiyatsiz: {xato}")

    token = (natija.get('data') or {}).get('token')
    if not token:
        raise SmsXato('Eskiz tokeni olinmadi')
    cache.set(TOKEN_KESH_KALITI, token, TOKEN_MUDDATI)
    return token


def _eskiz_yubor(telefon, matn, qayta=True):
    token = _eskiz_token()
    malumot = urllib.parse.urlencode({
        # Eskiz raqamni 998XXXXXXXXX ko'rinishida kutadi
        'mobile_phone': telefon.lstrip('+'),
        'message': matn,
        'from': _sozlama('ESKIZ_FROM', '4546'),
    }).encode()
    so_rov = urllib.request.Request(
        ESKIZ_BAZA + '/message/sms/send', data=malumot, method='POST',
        headers={'Authorization': 'Bearer ' + token},
    )
    try:
        with urllib.request.urlopen(so_rov, timeout=10) as javob:
            return json.loads(javob.read())
    except urllib.error.HTTPError as xato:
        # Token eskirgan bo'lsa bir marta yangilab qayta urinamiz
        if xato.code == 401 and qayta:
            _eskiz_token(yangila=True)
            return _eskiz_yubor(telefon, matn, qayta=False)
        raise SmsXato(f"Eskiz xatosi {xato.code}: {xato.read()[:200]}")
    except urllib.error.URLError as xato:
        raise SmsXato(f"Eskiz bilan aloqa yo'q: {xato}")


def sms_yubor(telefon, matn):
    """SMS yuboradi. Muvaffaqiyatli bo'lsa True qaytaradi.

    Xatolik yuz bersa log'ga yozadi va False qaytaradi — chaqiruvchi kod
    (masalan OTP) shu asosda mijozga tushunarli xabar ko'rsatadi.
    """
    provayder = _sozlama('SMS_PROVAYDER', 'konsol')

    if provayder == 'eskiz' and _sozlama('ESKIZ_EMAIL') and _sozlama('ESKIZ_PAROL'):
        try:
            _eskiz_yubor(telefon, matn)
            logger.info('SMS yuborildi: %s', telefon)
            return True
        except SmsXato as xato:
            logger.error('SMS yuborilmadi (%s): %s', telefon, xato)
            return False

    if provayder != 'konsol':
        logger.warning("SMS_PROVAYDER='%s', lekin kalitlar to'liq emas — konsol rejimi", provayder)

    # Produksiyada konsol rejimi — bu SMS yuborilmagani. Ilgari bu yerda ham
    # `True` qaytardi va `otp_yuborish` mijozga "kod yuborildi" deb javob
    # berardi; mijoz esa hech qachon SMS olmasdi va tizimga kira olmasdi,
    # hech qanday xato ham ko'rinmasdi. Endi rostini qaytaramiz: chaqiruvchi
    # 502 bilan tushunarli xabar ko'rsatadi.
    #
    # `sms_app.checks.E001` bunday serverni umuman ishga tushirmaydi; bu yer
    # esa tekshiruv chetlab o'tilgan holat uchun (`--skip-checks`) himoya.
    if not settings.DEBUG:
        logger.error(
            'SMS provayder sozlanmagan (DEBUG=False) — %s raqamiga xabar YUBORILMADI',
            telefon,
        )
        return False

    # `print` EMAS: stdout TTY bo'lmaganda (runserver log faylga yo'naltirilgan,
    # xizmat sifatida ishlayotgan gunicorn/systemd) Python uni buferlaydi va
    # xabar log'ga umuman yetib bormaydi — dev rejimda OTP kod jimgina
    # yo'qolardi va kirib bo'lmasdi. `logger` esa darhol yoziladi.
    logger.warning('[SMS -> %s] %s', telefon, matn)
    return True


def sozlanganmi():
    """Haqiqiy provayder ulanganmi (dev konsol rejimi emasmi)."""
    return (_sozlama('SMS_PROVAYDER', 'konsol') == 'eskiz'
            and bool(_sozlama('ESKIZ_EMAIL')) and bool(_sozlama('ESKIZ_PAROL')))
