"""To'lov so'rovi → xizmat buyurtmasi: to'lov tasdiqlansa buyurtma «to'langan» bo'ladi.

Click (Complete webhook) ham, bank o'tkazmasi (chek tasdiqlanishi) ham `TolovSorovi.holat='tolandi'` qiladi —
shu yerda bog'liq `Buyurtma.tolandi` belgilanadi. (Do'kon xaridlari uchun xuddi shu ish
apps.xaridlar.signals da.)
"""
import logging

from django.db import transaction
from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import TolovSorovi

logger = logging.getLogger(__name__)


@receiver(post_save, sender=TolovSorovi)
def tolov_buyurtmaga(sender, instance, **kwargs):
    if instance.holat != 'tolandi' or not instance.buyurtma_id:
        return
    from apps.buyurtmalar.models import Buyurtma
    yangilandi = Buyurtma.objects.filter(pk=instance.buyurtma_id, tolandi=False).update(tolandi=True)
    if yangilandi:
        # Ish tugagan («to'lov kutilmoqda») bo'lsa — buyurtma to'liq yakunlanadi
        from apps.buyurtmalar.yakun import tolov_yakuni
        transaction.on_commit(lambda: tolov_yakuni(instance.buyurtma_id))
    if not yangilandi or instance.tolov_tizimi != 'click':
        return          # bank o'tkazmasida xabarni chek tasdig'i (bank.tekshir) o'zi yuboradi

    summa = f"{instance.summa:,}".replace(',', ' ')
    bid, telefon = instance.buyurtma_id, instance.telefon

    def _xabarlar():
        from apps.sms_app import xodim_xabar
        from apps.sms_app.gateway import sms_yubor
        try:
            sms_yubor(telefon, f"SOAR GAZ: #{bid} buyurtma bo'yicha {summa} so'm Click orqali qabul qilindi. Rahmat!")
        except Exception:                      # noqa: BLE001 — xabar xatosi to'lovni buzmasin
            logger.exception('Click to\'lovi xabari yuborilmadi')
        xodim_xabar.tolov_tekshiruvchilarga(
            f"✅ Click orqali to'lov: buyurtma #{bid}\n💰 {summa} so'm\n👤 {instance.ism} {telefon}")
    transaction.on_commit(_xabarlar)
