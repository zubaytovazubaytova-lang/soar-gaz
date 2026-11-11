"""Tushumni qabul qilish yoki rad etish — API va Django panelida bir xil qoida.

`request` — Django HttpRequest yoki DRF Request bo'lishi mumkin (faqat `.user` va
jurnal uchun `.META` kerak).
"""
from django.db.models import Sum
from django.utils import timezone

from apps.auth_app.models import audit_yoz
from .models import Tushum

OK, TOPILMADI, ALLAQACHON = 'ok', 'topilmadi', 'allaqachon'


def hal_qil(request, pk, yangi_holat, sabab=''):
    """kutilmoqda -> qabul/rad. O'tish bitta UPDATE bilan qilinadi: ikki admin bir
    paytda bossa ham yozuv faqat bir marta hal bo'ladi.

    Qaytaradi: (OK | TOPILMADI | ALLAQACHON, tushum yoki None).
    """
    soni = Tushum.objects.filter(pk=pk, holat='kutilmoqda').update(
        holat=yangi_holat, hal_qilgan=request.user, hal_vaqti=timezone.now(),
        rad_sababi=sabab)
    if soni == 0:
        return (ALLAQACHON, None) if Tushum.objects.filter(pk=pk).exists() else (TOPILMADI, None)

    t = Tushum.objects.select_related('xodim', 'buyurtma').get(pk=pk)
    if yangi_holat == 'qabul' and t.buyurtma_id and t.buyurtma.tasdiq_summa is not None:
        # Qabul qilingan pul tasdiqlangan summaga yetsa — buyurtma to'langan
        qabul = (Tushum.objects.filter(buyurtma_id=t.buyurtma_id, holat='qabul')
                 .aggregate(s=Sum('summa'))['s'] or 0)
        if qabul >= t.buyurtma.tasdiq_summa and not t.buyurtma.tolandi:
            t.buyurtma.tolandi = True
            t.buyurtma.save(update_fields=['tolandi', 'yangilangan'])
    amal = 'tushum_qabul' if yangi_holat == 'qabul' else 'tushum_rad'
    tafsilot = f"{t.xodim.ism or t.xodim.telefon}: {t.summa} so'm, #{t.pk}"
    if sabab:
        tafsilot += f' — {sabab}'
    audit_yoz(request, amal, tafsilot)
    return OK, t
