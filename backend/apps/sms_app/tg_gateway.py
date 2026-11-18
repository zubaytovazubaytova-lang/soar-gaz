"""Telegram Gateway: tasdiqlash kodini foydalanuvchining Telegram'iga raqam bo'yicha yuboradi.

Bot bilan farqi: foydalanuvchi botni ochishi, Start bosishi yoki raqamini ulashishi SHART EMAS.
Kod Telegram'dagi rasmiy «Verification Codes» chatiga keladi. Foydalanuvchi telefon raqamini
saytga o'zi yozgani Telegram qoidalariga ko'ra rozilik hisoblanadi.

Faqat tasdiqlash kodlari uchun (xabar matnini o'zimiz yozib bo'lmaydi). Oddiy xabarlar
(buyurtma, tayinlash) `telegram.py` boti orqali ketadi.

Hujjat: https://core.telegram.org/gateway/api
Sozlama (`soargaz-gateway-kalit` yozadi):
    TELEGRAM_GATEWAY_TOKEN   gateway hisobi sozlamalaridagi access token
Narx: yetkazilgan kod uchun ~$0.01; yetkazilmasa pul qaytariladi. O'z raqamingizga yuborish tekin.
"""

import json
import logging
import re
import urllib.error
import urllib.request

from django.conf import settings

logger = logging.getLogger(__name__)

API_BAZA = 'https://gatewayapi.telegram.org'


class GatewayXato(Exception):
    """Gateway API xatosi (matnda Telegram bergan sabab: masalan PHONE_NUMBER_NOT_FOUND)."""


def _sozlama(nom, standart=''):
    return getattr(settings, nom, standart) or standart


def sozlangan():
    return bool(_sozlama('TELEGRAM_GATEWAY_TOKEN'))


def e164(telefon):
    """'+998 90 123-45-67' / '998901234567' -> '+998901234567'. Raqam bo'lmasa ''."""
    raqamlar = re.sub(r'\D', '', telefon or '')
    return '+' + raqamlar if raqamlar else ''


def _api(usul, malumot):
    token = _sozlama('TELEGRAM_GATEWAY_TOKEN')
    if not token:
        raise GatewayXato('TELEGRAM_GATEWAY_TOKEN berilmagan')
    so_rov = urllib.request.Request(
        f'{API_BAZA}/{usul}',
        data=json.dumps(malumot).encode(),
        headers={'Content-Type': 'application/json', 'Authorization': f'Bearer {token}'},
        method='POST',
    )
    try:
        with urllib.request.urlopen(so_rov, timeout=10) as javob:
            natija = json.loads(javob.read())
    except urllib.error.HTTPError as xato:
        try:
            sabab = json.loads(xato.read()).get('error', '')
        except (ValueError, OSError):
            sabab = ''
        raise GatewayXato(f'{usul}: HTTP {xato.code} {sabab}'[:200])
    except (urllib.error.URLError, ValueError, OSError) as xato:
        raise GatewayXato(f'{usul}: {type(xato).__name__}')
    if not natija.get('ok'):
        raise GatewayXato(f"{usul}: {natija.get('error', 'xato')}"[:200])
    return natija.get('result') or {}


def kod_yubor(telefon, kod, ttl=None):
    """Tayyor kodni Telegram'ga yuboradi. Muvaffaqiyatli bo'lsa True; raqam Telegram'da yo'q,
    balans tugagan yoki boshqa xato bo'lsa False (chaqiruvchi SMS/botga o'tadi)."""
    if not sozlangan():
        return False
    raqam = e164(telefon)
    if not raqam or not str(kod).isdigit() or not 4 <= len(str(kod)) <= 8:
        return False
    if ttl is None:
        ttl = int(getattr(settings, 'OTP_EXPIRE_MINUTES', 5)) * 60
    try:
        natija = _api('sendVerificationMessage', {
            'phone_number': raqam,
            'code': str(kod),
            # Telegram 30..3600 soniyani qabul qiladi; muddat ichida yetkazilmasa pul qaytariladi
            'ttl': max(30, min(3600, int(ttl))),
        })
    except GatewayXato as xato:
        # Raqam Telegram'da bo'lmasligi oddiy hol (SMS/botga o'tamiz) — ogohlantirish emas, info
        logger.info('Telegram Gateway kodi yuborilmadi (%s): %s', raqam[-4:], xato)
        return False
    logger.info('Telegram Gateway kodi yuborildi: ...%s (narx %s)', raqam[-4:], natija.get('request_cost'))
    return True


def token_yaroqlimi():
    """Tokenni pulsiz tekshiradi: bo'lmagan so'rov id si bilan holat so'raladi.
    Token noto'g'ri bo'lsa ACCESS_TOKEN_INVALID, to'g'ri bo'lsa boshqa xato (REQUEST_ID_INVALID)."""
    try:
        _api('checkVerificationStatus', {'request_id': 'tekshiruv'})
    except GatewayXato as xato:
        return 'ACCESS_TOKEN_INVALID' not in str(xato), str(xato)
    return True, ''
