"""Django panelidagi har bir o'zgarish (qo'shish / o'zgartirish / o'chirish) markaziy
Faoliyat jurnaliga (AuditYozuv) ham yoziladi — direktor va egasi barcha jarayonni bitta
joyda ko'radi. Django'ning o'z tarixi (LogEntry) ham saqlanib qoladi."""
from django.contrib.admin.models import ADDITION, CHANGE, DELETION, LogEntry
from django.db.models.signals import post_save
from django.dispatch import receiver

_HARAKAT = {ADDITION: "qo'shdi", CHANGE: "o'zgartirdi", DELETION: "o'chirdi"}


@receiver(post_save, sender=LogEntry)
def panel_ozgarishini_yoz(sender, instance, created, **kwargs):
    if not created:
        return
    from .models import AuditYozuv

    try:
        model = instance.content_type.model if instance.content_type_id else ''
        qism = f"{model}: {instance.object_repr[:70]} — {_HARAKAT.get(instance.action_flag, '')}"
        xabar = instance.get_change_message()
        if xabar:
            qism += f' ({xabar})'
        kim = instance.user
        AuditYozuv.objects.create(
            kim=kim, kim_ism=getattr(kim, 'ism', '') or '', kim_telefon=getattr(kim, 'telefon', '') or '',
            amal='panel_ozgarish', tafsilot=qism[:255])
    except Exception:
        # Jurnal yozilmagani asosiy amalni buzmasligi kerak
        pass
