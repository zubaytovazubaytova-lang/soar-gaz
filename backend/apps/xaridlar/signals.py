from django.db.models.signals import post_init, post_save
from django.dispatch import receiver

from apps.auth_app.models import Foydalanuvchi
from apps.sms_app.gateway import sms_yubor
from apps.sms_app.models import SmsXabar
from apps.tolovlar.models import TolovSorovi

from .models import Xarid, HOLAT_SMS, MUAMMO_SMS


# ──────────────────────────────────────────────────────────────
#  1. To'lov holati → xarid holati
# ──────────────────────────────────────────────────────────────
@receiver(post_save, sender=TolovSorovi)
def tolov_holati_xaridga(sender, instance, **kwargs):
    """Click/Payme webhooki to'lovni tasdiqlaganda bog'liq xaridni belgilaymiz.

    Bog'lanish `Xarid.tolov_sorovi` orqali — boshqa (xizmat) to'lov
    so'rovlari hech qanday xaridga tegmaydi.
    """
    tolandi = instance.holat == 'tolandi'
    yangi_holat = {'tolandi': 'tolandi', 'bekor': 'xato'}.get(instance.holat, 'kutilmoqda')

    for xarid in Xarid.objects.filter(tolov_sorovi=instance):
        if xarid.tolandi == tolandi and xarid.tolov_holati == yangi_holat:
            continue
        xarid.tolandi = tolandi
        xarid.tolov_holati = yangi_holat
        # To'lov kelgach buyurtma avtomatik tasdiqlanadi
        if tolandi and xarid.holat == 'qabul_qilindi':
            xarid.holat = 'tasdiqlandi'
        xarid.save(update_fields=['tolandi', 'tolov_holati', 'holat', 'yangilangan'])


# ──────────────────────────────────────────────────────────────
#  2. Holat o'zgarganda mijozga SMS
#
#  Signal orqali qilinganining sababi: holat API'dan ham, Django admin
#  panelidan ham, boshqa koddan ham o'zgartirilishi mumkin — SMS hamma
#  yo'lda bir xil ketishi kerak.
# ──────────────────────────────────────────────────────────────
@receiver(post_init, sender=Xarid)
def _holatni_eslab_qol(sender, instance, **kwargs):
    """Bazadan o'qilgan paytdagi holatni saqlab qo'yamiz."""
    instance._eski_holat = instance.holat


@receiver(post_save, sender=Xarid)
def holat_ozgardi_sms(sender, instance, created, **kwargs):
    eski = getattr(instance, '_eski_holat', None)

    if created:
        matn = (f"SOAR GAZ: buyurtmangiz qabul qilindi! {instance.raqam} — "
                f"{instance.jami:,} so'm. Holatni saytda kuzating.".replace(',', ' '))
    elif eski is not None and eski != instance.holat and instance.holat == 'muammo':
        # Yetkazib bo'lmadi — sababga mos matn yuboriladi
        sabab = MUAMMO_SMS.get(instance.muammo, MUAMMO_SMS['boshqa'])
        matn = f"SOAR GAZ: {instance.raqam} — {sabab}"
    elif eski is not None and eski != instance.holat and instance.holat in HOLAT_SMS:
        matn = f"SOAR GAZ: {instance.raqam} — {HOLAT_SMS[instance.holat]}"
    else:
        instance._eski_holat = instance.holat
        return

    _sms_yuborish(instance.telefon, matn)
    instance._eski_holat = instance.holat


def _sms_yuborish(telefon, matn):
    """Ro'yxatdan o'tgan mijozga SMS saqlaymiz, aks holda faqat log.

    SmsXabar yozuvi mijoz profilidagi "Xabarlar" bo'limida ko'rinadi va
    saytda ochiq turgan sahifaga bildirishnoma sifatida yetkaziladi.
    """
    mijoz = Foydalanuvchi.objects.filter(telefon=telefon).first()
    if mijoz:
        SmsXabar.objects.create(mijoz=mijoz, matn=matn)
    sms_yubor(telefon, matn)
