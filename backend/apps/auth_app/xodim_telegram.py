"""Xodimni Telegram botga ulash — shaxsiy havola orqali (raqam ulashishsiz).

Muammo: xodim botga «📱 Raqamni ulashish» bilan ulanardi. Telegram'dagi raqami kabinetdagi
raqamdan farq qilsa (eski SIM, ikkinchi raqam), ulanish kabinet raqamiga bog'lanmasdi va
yangi vazifa xabarlari xodimga yetmasdi.

Endi: kabinetdagi «Botga ulanish» tugmasi bir martalik havola beradi
(`t.me/<bot>?start=x_<token>`). Botda «Start» bosilishi bilan shu Telegram hisobi
KABINETDAGI raqamga bog'lanadi — Telegram'dagi raqam qanday bo'lishidan qat'i nazar.
Token 30 daqiqa amal qiladi va bir marta ishlatiladi; uni faqat tizimga kirgan faol xodim oladi.
"""
import secrets

from django.core.cache import cache
from django.db import transaction
from django.utils.translation import gettext as _
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.sms_app import telegram as telegram_bot
from apps.sms_app.models import TelegramUlanish
from .kabinet_turlari import faol_xodimmi
from .models import Foydalanuvchi

MUDDAT = 30 * 60
PREFIKS = 'x_'


def _kalit(token):
    return f'tgxodim:{token}'


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def havola(request):
    """POST /api/auth/xodim/telegram-havola/ — botga ulanish uchun shaxsiy bir martalik havola."""
    if not faol_xodimmi(request.user):
        return Response({'detail': _("Faqat faol xodimlar uchun")}, status=403)
    if not telegram_bot.sozlangan():
        return Response({'detail': _("Telegram bot sozlanmagan")}, status=503)
    token = secrets.token_urlsafe(16)                    # 22 belgi: Telegram start parametri chegarasida
    cache.set(_kalit(token), request.user.pk, MUDDAT)
    return Response({'url': f'https://t.me/{telegram_bot.bot_nomi()}?start={PREFIKS}{token}',
                     'muddat': MUDDAT, 'ulangan': telegram_bot.ulangan(request.user.telefon)})


ULANDI = ("✅ {ism}, siz SOAR GAZ xodimi sifatida botga ulandingiz.\n\n"
          "Endi yangi vazifalar, arizalar va ish bo'yicha xabarlar shu yerga keladi.")
ESKIRGAN = ("Havola eskirgan yoki allaqachon ishlatilgan.\n"
            "Xodimlar kabinetidagi «Botga ulanish» tugmasini qayta bosing.")


def bot_start(token, chat_id, kimdan):
    """Webhook: `/start x_<token>` keldi — tokenni egasi bo'lgan xodimni shu chatga bog'laydi."""
    token = (token or '')[:64]
    uid = cache.get(_kalit(token)) if token else None
    if uid is None:
        telegram_bot._javob(chat_id, ESKIRGAN, {'remove_keyboard': True})
        return
    cache.delete(_kalit(token))                          # bir martalik
    xodim = Foydalanuvchi.objects.filter(pk=uid).first()
    if xodim is None or not faol_xodimmi(xodim):
        telegram_bot._javob(chat_id, ESKIRGAN, {'remove_keyboard': True})
        return
    telefon = telegram_bot.telefon_normallash(xodim.telefon) or xodim.telefon
    with transaction.atomic():
        oldin_ulangan = TelegramUlanish.objects.filter(telefon=telefon).exists()
        # Bir Telegram hisobi — bitta raqam; bir raqam — bitta hisob (oxirgi ulangani)
        TelegramUlanish.objects.filter(chat_id=chat_id).exclude(telefon=telefon).delete()
        TelegramUlanish.objects.update_or_create(
            telefon=telefon,
            defaults={'chat_id': chat_id, 'username': ((kimdan or {}).get('username') or '')[:64]})
        if not oldin_ulangan:
            from apps.sms_app import xodim_xabar
            xodim_xabar.xodim_botga_ulandi(telefon)
    telegram_bot._javob(chat_id, ULANDI.format(ism=xodim.ism or 'Hurmatli xodim'), {'remove_keyboard': True})
