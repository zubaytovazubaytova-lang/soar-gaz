"""Xarid uchun to'lov havolasini yaratish va qayta urinish mantiqi.

Provayder integratsiyalarining o'zi apps.tolovlar da (Click Merchant API va
Payme JSON-RPC webhooklari). Bu yerda faqat xaridni to'lov so'roviga bog'lash.

3D-Secure: karta ma'lumotlari hech qachon bu saytga kiritilmaydi — mijoz
provayder (Click/Payme) checkout sahifasiga o'tadi va bank tasdiqlashni
(3-D Secure / OTP) o'sha yerda o'taydi. Shu sababli PCI DSS talablari ham
provayder zimmasida qoladi.
"""
from django.conf import settings

from apps.tolovlar.models import TolovSorovi
from apps.tolovlar.views import _tolov_url

from .models import ONLAYN_USULLAR


def _tizim(tolov_usuli):
    """Xarid to'lov usulidan provayder tizimini aniqlaydi."""
    if tolov_usuli == 'karta':
        # Uzcard/Humo — sozlangan provayder checkouti orqali
        return getattr(settings, 'KARTA_PROVAYDER', 'click')
    return tolov_usuli


def tolov_sorovi_yarat(xarid):
    """Xarid uchun yangi TolovSorovi yaratadi va uni xaridga bog'laydi.

    Har bir urinish uchun yangi so'rov yaratiladi — provayderda eski
    tranzaksiya "muvaffaqiyatsiz" holatda qolib ketishi mumkin.
    """
    if xarid.tolov_usuli == 'bolib':
        sorov = TolovSorovi.objects.create(
            ism=xarid.ism,
            telefon=xarid.telefon,
            tolov_turi='shartnoma',
            xizmat_turi=f'Xarid {xarid.raqam}',
            summa=xarid.jami,
            muddat=f'{xarid.bolib_oy} oy',
            izoh=f"Oylik to'lov: {xarid.oylik_tolov:,} so'm".replace(',', ' '),
            holat='yangi',
        )
    else:
        sorov = TolovSorovi.objects.create(
            ism=xarid.ism,
            telefon=xarid.telefon,
            tolov_turi='online',
            tolov_tizimi=_tizim(xarid.tolov_usuli),
            xizmat_turi=f'Xarid {xarid.raqam}',
            summa=xarid.jami,
            holat='kutilmoqda',
        )

    xarid.tolov_sorovi = sorov
    xarid.tolov_urinishlari = xarid.tolov_urinishlari + 1
    xarid.tolov_holati = 'kutilmoqda'
    xarid.save(update_fields=['tolov_sorovi', 'tolov_urinishlari',
                              'tolov_holati', 'yangilangan'])
    return sorov


def tolov_url(xarid):
    """Xaridning joriy to'lov havolasi (yo'q bo'lsa — bo'sh satr)."""
    if xarid.tolov_usuli not in ONLAYN_USULLAR or not xarid.tolov_sorovi:
        return ''
    return _tolov_url(xarid.tolov_sorovi)


def sozlanganmi(tolov_usuli):
    """Provayder kalitlari sozlanganmi — sozlanmagan bo'lsa mijozga aytamiz."""
    tizim = _tizim(tolov_usuli)
    if tizim == 'click':
        return bool(getattr(settings, 'CLICK_SERVICE_ID', '') and
                    getattr(settings, 'CLICK_MERCHANT_ID', ''))
    if tizim == 'payme':
        return bool(getattr(settings, 'PAYME_MERCHANT_ID', ''))
    return True
