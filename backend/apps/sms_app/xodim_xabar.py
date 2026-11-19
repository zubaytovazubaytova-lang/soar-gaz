"""Yangi ariza yoki buyurtma kelganda mas'ul xodimlarga Telegram bot orqali TEKIN xabar.

Kimga boradi (faqat @soargaz_bot ga raqamini ulagan va faol bo'lganlarga):
  * administrator;
  * qo'ng'iroq vazifasidagilar (Nargiza, Ruxsora: kabinet turi «qongiroq» / «kadrlar») — har bir yangi ariza;
  * hujjat tayyorlovchi (Ferangiz: «hujjat») — metrologiya va loyiha arizalari.

Xodim botga qanday ulanadi: Telegram'da @soargaz_bot → /start → «Raqamni ulashish».
Xabar tranzaksiya muvaffaqiyatli yakunlangandan KEYIN yuboriladi; Telegram xatosi arizani buzmaydi.
"""
import logging

from django.db import transaction

from apps.auth_app.kabinet_turlari import HUJJAT, KADRLAR, QONGIROQ, kabinet_turi
from . import telegram
from .models import TelegramUlanish

logger = logging.getLogger(__name__)

HUJJAT_XIZMATLARI = ('metrologiya', 'loyiha')
XODIM_KABINETI = 'https://soargaz.uz/xodimlar.html'


def qabul_qiluvchilar(xizmat):
    """Shu xizmat bo'yicha yangi ariza xabarini oladigan (botga ulangan) xodimlar telefonlari."""
    from apps.auth_app.models import Foydalanuvchi

    ulangan = list(TelegramUlanish.objects.values_list('telefon', flat=True))
    if not ulangan:
        return []
    turlar = {QONGIROQ, KADRLAR}
    if xizmat in HUJJAT_XIZMATLARI:
        turlar.add(HUJJAT)
    natija = []
    for u in Foydalanuvchi.objects.filter(telefon__in=ulangan, holat='faol', rol__in=('admin', 'xodim')):
        if u.rol == 'admin' or kabinet_turi(u.lavozim) in turlar:
            natija.append(u.telefon)
    return natija


def _yubor(xizmat, matn):
    for telefon in qabul_qiluvchilar(xizmat):
        try:
            telegram.yubor(telefon, matn)
        except Exception:                      # noqa: BLE001 — xabar xatosi ariza ishini to'xtatmasin
            logger.exception('Xodimga Telegram xabari yuborilmadi')


def yangi_ariza(xizmat, sarlavha, mijoz_ism='', telefon='', manzil='', izoh=''):
    """Yangi ariza haqida mas'ul xodimlarga xabar (tranzaksiyadan keyin)."""
    if not telegram.sozlangan():
        return
    qatorlar = [f'🆕 {sarlavha}']
    if mijoz_ism or telefon:
        qatorlar.append(f"👤 {' '.join(x for x in (mijoz_ism, telefon) if x)}")
    if manzil:
        qatorlar.append(f'📍 {manzil}')
    if izoh:
        qatorlar.append(f'📝 {izoh[:200]}')
    qatorlar.append(f'Kabinet: {XODIM_KABINETI}')
    matn = '\n'.join(qatorlar)
    transaction.on_commit(lambda: _yubor(xizmat, matn))
