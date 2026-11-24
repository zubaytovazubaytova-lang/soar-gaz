"""Buyurtmaning to'liq yakunlanishi: ish tugagan VA to'lov to'liq qabul qilingan bo'lsa.

Xodim «Ishni tugatdim» desa buyurtma `tolov_kutilmoqda` bo'ladi. To'lov to'liq bo'lgach
(Click Complete, tasdiqlangan bank cheki yoki Ruxsora qabul qilgan naqd/karta tushumi —
hammasi `Buyurtma.tolandi=True` qiladi) shu funksiya buyurtmani `bajarildi` qiladi va xabar beradi.
"""
import logging

from django.db import transaction

from .models import Buyurtma

logger = logging.getLogger(__name__)


def tolov_yakuni(buyurtma_id):
    """To'langan va ishi tugagan buyurtmani yakunlaydi. Yakunlansa True."""
    with transaction.atomic():
        b = (Buyurtma.objects.select_for_update(of=('self',)).select_related('xodim', 'mijoz')
             .filter(pk=buyurtma_id).first())
        if b is None or not b.tolandi or b.holat != 'tolov_kutilmoqda':
            return False
        b.holat = 'bajarildi'
        b.save()                       # kabinet signali mijozga «Buyurtmangiz yakunlandi» bildirishnomasini yaratadi
    _yakun_xabarlari(b)
    return True


def _yakun_xabarlari(b):
    from apps.sms_app import xodim_xabar
    from .views import _ish_matni, _sms_yuborish
    try:
        _sms_yuborish(b.mijoz, f"#{b.id} buyurtmangiz bajarildi va to'liq yakunlandi ✓ To'lov qabul qilindi. Rahmat!")
    except Exception:                  # noqa: BLE001 — xabar xatosi yakunlashni buzmasin
        logger.exception('Yakun xabari mijozga yuborilmadi')
    xodim_xabar.ish_holati(b, _ish_matni(b, "✅ buyurtmasi to'liq yakunlandi (to'lov qabul qilindi)"))
    # Ustaning o'ziga ham: ishi to'liq yopildi
    if b.xodim_id:
        try:
            from apps.aloqa.models import Xabar
            from apps.sms_app import telegram
            matn = f"✅ #{b.id} buyurtma to'liq yakunlandi: to'lov qabul qilindi. Rahmat!"
            Xabar.objects.create(xodim=b.xodim, matn=matn)
            telegram.yubor(b.xodim.telefon, matn)
        except Exception:              # noqa: BLE001
            logger.exception('Yakun xabari ustaga yuborilmadi')
