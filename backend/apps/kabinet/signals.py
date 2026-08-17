"""Buyurtma holati o'zgarganda mijozga kabinet bildirishnomasi yaratiladi."""

from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver

from apps.buyurtmalar.models import Buyurtma
from .models import Bildirishnoma, MurojaatXabar


HOLAT_MATNI = {
    'yangi': 'Buyurtmangiz qabul qilindi',
    'qabul': 'Buyurtmangizga xodim tayinlandi',
    'bajarilmoqda': 'Buyurtmangiz bajarilmoqda',
    'bajarildi': 'Buyurtmangiz yakunlandi',
    'bekor': 'Buyurtmangiz bekor qilindi',
}


@receiver(pre_save, sender=Buyurtma)
def _oldingi_holatni_eslab_qol(sender, instance, **kwargs):
    if not instance.pk:
        instance._oldingi_holat = None
        return
    eski = Buyurtma.objects.filter(pk=instance.pk).values('holat', 'xodim_id').first()
    instance._oldingi_holat = eski['holat'] if eski else None
    instance._oldingi_xodim = eski['xodim_id'] if eski else None


@receiver(post_save, sender=Buyurtma)
def buyurtma_bildirishnomasi(sender, instance, created, **kwargs):
    if not instance.mijoz_id:
        return

    oldingi = getattr(instance, '_oldingi_holat', None)
    oldingi_xodim = getattr(instance, '_oldingi_xodim', None)

    if created:
        sarlavha = HOLAT_MATNI['yangi']
    elif oldingi != instance.holat:
        sarlavha = HOLAT_MATNI.get(instance.holat, 'Buyurtma holati yangilandi')
    elif oldingi_xodim != instance.xodim_id and instance.xodim_id:
        sarlavha = HOLAT_MATNI['qabul']
    else:
        return

    matn = f"#{instance.id} — {instance.xizmat_nomi}"
    if instance.xodim_id and instance.xodim:
        matn += f". Xodim: {instance.xodim.ism or instance.xodim.telefon}"
    if instance.holat == 'bajarildi' and instance.natija:
        matn += f". Natija: {instance.natija[:100]}"

    Bildirishnoma.objects.create(
        mijoz_id=instance.mijoz_id,
        turi='buyurtma',
        sarlavha=sarlavha,
        matn=matn,
        bolim='buyurtmalar',
    )


@receiver(post_save, sender=MurojaatXabar)
def operator_javobi(sender, instance, created, **kwargs):
    """Operator admin panelidan javob yozsa — mijozga bildirishnoma."""
    if not created or instance.kim != 'operator':
        return
    murojaat = instance.murojaat
    Bildirishnoma.objects.create(
        mijoz_id=murojaat.mijoz_id,
        turi='umumiy',
        sarlavha='Yordam markazidan javob keldi',
        matn=f"{murojaat.mavzu}: {instance.matn[:120]}",
        bolim='yordam',
    )
    if murojaat.holat != 'yopiq':
        murojaat.holat = 'javob'
        murojaat.save(update_fields=['holat', 'yangilangan'])
