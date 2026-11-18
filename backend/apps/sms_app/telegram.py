"""Telegram bot orqali xabar yuborish (SMS'ga bepul muqobil).

Qanday ishlaydi:
  1. Foydalanuvchi botni ochadi va «Raqamni ulashish» tugmasini bosadi. Telegram
     o'zi tasdiqlagan telefon raqamini yuboradi (soxta raqam yozib bo'lmaydi).
  2. Raqam <-> chat_id juftligi `TelegramUlanish` jadvaliga yoziladi.
  3. `sms_yubor()` shu raqamga xabar yuborilayotganda avval Telegram'ni sinaydi.

Sozlama (muhit o'zgaruvchilari, `soargaz-telegram-kalit` yozadi):
    TELEGRAM_BOT_TOKEN       @BotFather bergan token
    TELEGRAM_WEBHOOK_SECRET  webhook so'rovlarini tasdiqlash uchun tasodifiy satr
    TELEGRAM_BOT_USERNAME    botning nomi (@ siz)
"""

import hmac
import json
import logging
import re
import urllib.error
import urllib.request

from django.conf import settings
from django.db import transaction

from .models import TelegramUlanish

logger = logging.getLogger(__name__)

API_BAZA = 'https://api.telegram.org'


class TelegramXato(Exception):
    """Telegram API xatosi."""


def _sozlama(nom, standart=''):
    return getattr(settings, nom, standart) or standart


def sozlangan():
    return bool(_sozlama('TELEGRAM_BOT_TOKEN'))


def bot_nomi():
    return _sozlama('TELEGRAM_BOT_USERNAME').lstrip('@')


def telefon_normallash(telefon):
    """'998901234567', '+998 90 123-45-67' -> '+998901234567'. Raqam bo'lmasa ''."""
    raqamlar = re.sub(r'\D', '', telefon or '')
    return '+' + raqamlar if raqamlar else ''


def _api(usul, malumot=None):
    token = _sozlama('TELEGRAM_BOT_TOKEN')
    if not token:
        raise TelegramXato('TELEGRAM_BOT_TOKEN berilmagan')
    so_rov = urllib.request.Request(
        f'{API_BAZA}/bot{token}/{usul}',
        data=json.dumps(malumot or {}).encode(),
        headers={'Content-Type': 'application/json'},
        method='POST',
    )
    try:
        with urllib.request.urlopen(so_rov, timeout=10) as javob:
            natija = json.loads(javob.read())
    except urllib.error.HTTPError as xato:
        # Telegram xato sababini JSON ichida beradi (masalan «bot was blocked by the user»)
        try:
            sabab = json.loads(xato.read()).get('description', '')
        except (ValueError, OSError):
            sabab = ''
        raise TelegramXato(f'{usul}: HTTP {xato.code} {sabab}'[:200])
    except (urllib.error.URLError, ValueError, OSError) as xato:
        raise TelegramXato(f'{usul}: {type(xato).__name__}')
    if not natija.get('ok'):
        raise TelegramXato(f"{usul}: {natija.get('description', 'xato')}"[:200])
    return natija.get('result')


def ulangan(telefon):
    """Bu raqam Telegram botga ulanganmi."""
    return TelegramUlanish.objects.filter(telefon=telefon_normallash(telefon)).exists()


def yubor(telefon, matn):
    """Ulangan raqamga Telegram orqali xabar yuboradi. Ulanmagan yoki xato bo'lsa False."""
    if not sozlangan():
        return False
    ulanish = TelegramUlanish.objects.filter(telefon=telefon_normallash(telefon)).first()
    if ulanish is None:
        return False
    try:
        _api('sendMessage', {'chat_id': ulanish.chat_id, 'text': matn})
    except TelegramXato as xato:
        logger.error('Telegram xabari yuborilmadi (%s): %s', telefon, xato)
        return False
    logger.info('Telegram xabari yuborildi: %s', telefon)
    return True


# ──────────────────────────────────────────────────────────────
#  Webhook: foydalanuvchi botga yozgan xabarlar
# ──────────────────────────────────────────────────────────────
SALOMLASHUV = (
    "SOAR GAZ botiga xush kelibsiz!\n\n"
    "Saytdagi kirish kodlari va buyurtma xabarlari shu yerga keladi. "
    "Boshlash uchun pastdagi «📱 Raqamni ulashish» tugmasini bosing."
)
ULANDI = (
    "✅ Raqamingiz ulandi.\n\n"
    "Endi saytga qaytib, kodni qayta so'rang: kod shu yerga keladi."
)
BOSHQA_RAQAM = "Faqat o'zingizning raqamingizni ulashing: «📱 Raqamni ulashish» tugmasidan foydalaning."
UZILDI = "Raqamingiz botdan uzildi. Qayta ulash uchun /start bosing."

RAQAM_TUGMASI = {
    'keyboard': [[{'text': '📱 Raqamni ulashish', 'request_contact': True}]],
    'resize_keyboard': True,
    'one_time_keyboard': True,
}


def _javob(chat_id, matn, tugmalar=None):
    malumot = {'chat_id': chat_id, 'text': matn}
    if tugmalar is not None:
        malumot['reply_markup'] = tugmalar
    try:
        _api('sendMessage', malumot)
    except TelegramXato as xato:
        logger.error('Telegram javobi yuborilmadi: %s', xato)


def webhook_sarlavhasi_tugrimi(sarlavha):
    """Telegram har so'rovga `X-Telegram-Bot-Api-Secret-Token` qo'yadi (setWebhook da berilgan)."""
    sir = _sozlama('TELEGRAM_WEBHOOK_SECRET')
    return bool(sir) and hmac.compare_digest(str(sarlavha or ''), sir)


def yangilanishni_qayta_ishla(yangilanish):
    """Bitta Telegram yangilanishini (update) qayta ishlaydi. Xatoliklar tashqariga chiqmaydi."""
    xabar = (yangilanish or {}).get('message') or {}
    kimdan = xabar.get('from') or {}
    chat = xabar.get('chat') or {}
    # Faqat shaxsiy chat: guruhdagi xabarlar e'tiborga olinmaydi
    if chat.get('type') != 'private' or not chat.get('id'):
        return
    chat_id = chat['id']

    kontakt = xabar.get('contact')
    if kontakt:
        # Telegram «Raqamni ulashish» tugmasida kontaktning user_id si yuboruvchiniki bo'ladi.
        # Boshqa odamning kontaktini jo'natib, begona raqamni ulab bo'lmasligi uchun tekshiramiz.
        if kontakt.get('user_id') != kimdan.get('id'):
            _javob(chat_id, BOSHQA_RAQAM, RAQAM_TUGMASI)
            return
        telefon = telefon_normallash(kontakt.get('phone_number'))
        if not telefon:
            _javob(chat_id, BOSHQA_RAQAM, RAQAM_TUGMASI)
            return
        with transaction.atomic():
            # Bir Telegram hisobi — bitta raqam; bir raqam — bitta hisob (oxirgi tasdiqlangani)
            TelegramUlanish.objects.filter(chat_id=chat_id).exclude(telefon=telefon).delete()
            TelegramUlanish.objects.update_or_create(
                telefon=telefon,
                defaults={'chat_id': chat_id, 'username': (kimdan.get('username') or '')[:64]},
            )
        _javob(chat_id, ULANDI, {'remove_keyboard': True})
        return

    matn = (xabar.get('text') or '').strip().lower()
    if matn.startswith('/stop') or matn.startswith('/uzish'):
        TelegramUlanish.objects.filter(chat_id=chat_id).delete()
        _javob(chat_id, UZILDI, {'remove_keyboard': True})
        return
    # /start yoki istalgan boshqa xabar: ulanish tugmasini ko'rsatamiz
    _javob(chat_id, SALOMLASHUV, RAQAM_TUGMASI)


def webhook_ornat(url):
    """Telegram'ga webhook manzilini va maxfiy sarlavhani bildiradi."""
    return _api('setWebhook', {
        'url': url,
        'secret_token': _sozlama('TELEGRAM_WEBHOOK_SECRET'),
        'allowed_updates': ['message'],
        'drop_pending_updates': True,
    })


def webhook_ochir():
    return _api('deleteWebhook', {'drop_pending_updates': True})


def bot_malumoti():
    """getMe: tokenni tekshiradi, botning nomini qaytaradi."""
    return _api('getMe')
