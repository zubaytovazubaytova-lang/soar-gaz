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


def operatorlar():
    """Arizalarni kuzatuvchilar: qo'ng'iroq vazifasidagi faol xodimlar (Ruxsora, Nargiza)."""
    from apps.auth_app.models import Foydalanuvchi
    return [u for u in Foydalanuvchi.objects.filter(rol='xodim', holat='faol')
            if kabinet_turi(u.lavozim) in (QONGIROQ, KADRLAR)]


def _kabinetga(xodimlar, matn):
    """Xodim kabinetidagi qo'ng'iroqcha (bildirishnoma) — botga ulanmagan bo'lsa ham ko'radi."""
    from apps.aloqa.models import Xabar
    Xabar.objects.bulk_create([Xabar(xodim=x, matn=matn[:500]) for x in xodimlar])


def ish_holati(b, matn):
    """Xodim buyurtma bosqichini o'zgartirdi (qabul, yo'lda, boshladi, yakunladi): operatorlar kabinetiga
    va Telegram'iga (Ruxsora, Nargiza), administratorga — Telegram'ga. Tranzaksiyadan keyin."""
    from apps.auth_app.models import Foydalanuvchi

    def _yubor_hammaga():
        ops = operatorlar()
        try:
            _kabinetga(ops, matn)
        except Exception:                      # noqa: BLE001
            logger.exception('Operator kabinet xabari yozilmadi')
        if not telegram.sozlangan():
            return
        ulangan = set(TelegramUlanish.objects.values_list('telefon', flat=True))
        telefonlar = {u.telefon for u in ops} | set(
            Foydalanuvchi.objects.filter(rol='admin', holat='faol').values_list('telefon', flat=True))
        for telefon in telefonlar & ulangan:
            try:
                telegram.yubor(telefon, matn)
            except Exception:                  # noqa: BLE001
                logger.exception('Ish holati Telegram xabari yuborilmadi')
    transaction.on_commit(_yubor_hammaga)


def tolov_tekshiruvchilari():
    """Bank to'lovi cheklarini tasdiqlaydiganlar (botga ulangan): administrator va Kadrlar mutaxassisi."""
    from apps.auth_app.models import Foydalanuvchi

    ulangan = list(TelegramUlanish.objects.values_list('telefon', flat=True))
    return [u.telefon for u in Foydalanuvchi.objects.filter(telefon__in=ulangan, holat='faol',
                                                             rol__in=('admin', 'xodim'))
            if u.rol == 'admin' or kabinet_turi(u.lavozim) == KADRLAR]


def tolov_tekshiruvchilarga(matn):
    """Yangi to'lov (chek yoki Click) haqida tekshiruvchilarga: kabinet + Telegram (tranzaksiyadan keyin)."""

    def _yubor_hammaga():
        try:
            from apps.auth_app.models import Foydalanuvchi
            _kabinetga([u for u in Foydalanuvchi.objects.filter(rol='xodim', holat='faol')
                        if kabinet_turi(u.lavozim) == KADRLAR], matn)
        except Exception:                      # noqa: BLE001
            logger.exception('Tekshiruvchi kabinet xabari yozilmadi')
        if not telegram.sozlangan():
            return
        for telefon in tolov_tekshiruvchilari():
            try:
                telegram.yubor(telefon, matn)
            except Exception:                  # noqa: BLE001
                logger.exception('Tekshiruvchiga Telegram xabari yuborilmadi')
    transaction.on_commit(_yubor_hammaga)


def yangi_ariza(xizmat, sarlavha, mijoz_ism='', telefon='', manzil='', izoh=''):
    """Yangi ariza haqida mas'ul xodimlarga xabar: kabinetdagi qo'ng'iroqcha + Telegram (tranzaksiyadan keyin)."""
    qatorlar = [f'🆕 {sarlavha}']
    if mijoz_ism or telefon:
        qatorlar.append(f"👤 {' '.join(x for x in (mijoz_ism, telefon) if x)}")
    if manzil:
        qatorlar.append(f'📍 {manzil}')
    if izoh:
        qatorlar.append(f'📝 {izoh[:200]}')
    qatorlar.append(f'Kabinet: {XODIM_KABINETI}')
    matn = '\n'.join(qatorlar)

    def _hammasi():
        try:
            _kabinetga(operatorlar(), matn)
        except Exception:                      # noqa: BLE001
            logger.exception('Yangi ariza kabinet xabari yozilmadi')
        if telegram.sozlangan():
            _yubor(xizmat, matn)
    transaction.on_commit(_hammasi)
