"""«Rahbariyat» bosh sahifasi uchun umumiy ko'rinish (faqat o'qish).

Yangi ma'lumot saqlanmaydi: hammasi mavjud jadvallardan (tushum, buyurtma, smena,
jurnal) hisoblanadi. Hisobot faqat administratorlar (direktor va egasi) uchun —
xodim va mijoz tokeni bilan 403.
"""
from datetime import timedelta

from django.conf import settings
from django.db.models import Count, Min, Q, Sum
from django.utils import timezone
from django.utils.translation import gettext as _
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import AuditYozuv, Foydalanuvchi

# Topshirilmagan pul shuncha kundan oshsa — "diqqat" ro'yxatiga tushadi
ESKI_TUSHUM_KUN = 3
TARMOQLAR = ('aholi', 'ulgurji')
FAOL_HOLATLAR = ('yangi', 'qabul', 'bajarilmoqda')
# Jurnaldagi shovqinli yozuvlar (xarita har 15 soniyada yangilanadi) "so'nggi faoliyat"ga kirmaydi
JURNAL_SHOVQIN = ('joylashuv_korildi', 'chiqish')


def _oy_boshi():
    return timezone.localtime().replace(day=1, hour=0, minute=0, second=0, microsecond=0)


def yigma():
    """Umumiy ko'rinish (dict). Boshqaruv paneli API'si va Django paneli bosh sahifasi shuni ishlatadi."""
    # Boshqa ilovalar modellari funksiya ichida import qilinadi (ilovalar orasida sikl bo'lmasin)
    from apps.buyurtmalar.models import Buyurtma
    from apps.joylashuv.models import Nuqta, Smena
    from apps.tushum.models import Tushum

    hozir = timezone.now()
    oy = _oy_boshi()

    # ── Tushum: tarmoqlar bo'yicha ──
    tushum = {t: {'oy_qabul': 0, 'qabul': 0, 'kutilmoqda': 0, 'kutilmoqda_soni': 0} for t in TARMOQLAR}
    tushum['boshqa'] = dict(tushum['aholi'])
    for q in (Tushum.objects.values('tarmoq').annotate(
            oy_qabul=Sum('summa', filter=Q(holat='qabul', hal_vaqti__gte=oy)),
            qabul=Sum('summa', filter=Q(holat='qabul')),
            kutilmoqda=Sum('summa', filter=Q(holat='kutilmoqda')),
            kutilmoqda_soni=Count('id', filter=Q(holat='kutilmoqda')))):
        kalit = q['tarmoq'] if q['tarmoq'] in TARMOQLAR else 'boshqa'
        for m in ('oy_qabul', 'qabul', 'kutilmoqda', 'kutilmoqda_soni'):
            tushum[kalit][m] += q[m] or 0

    # Kim qancha pul topshirmagan (eng ko'pi bilan 5 ta) va eng eskisi qancha kun oldin
    chegara = hozir - timedelta(days=ESKI_TUSHUM_KUN)
    qarzdorlar = []
    for x in (Tushum.objects.filter(holat='kutilmoqda')
              .values('xodim_id', 'xodim__ism', 'xodim__telefon')
              .annotate(summa=Sum('summa'), soni=Count('id'), eng_eski=Min('yaratilgan'))
              .order_by('-summa')[:5]):
        qarzdorlar.append({
            'xodim_id': x['xodim_id'], 'ism': x['xodim__ism'] or x['xodim__telefon'],
            'summa': x['summa'], 'soni': x['soni'],
            'kun': (hozir - x['eng_eski']).days, 'eski': x['eng_eski'] < chegara,
        })
    eski = Tushum.objects.filter(holat='kutilmoqda', yaratilgan__lt=chegara).aggregate(
        soni=Count('id'), summa=Sum('summa'))

    # ── Buyurtmalar ──
    holatlar = {h['holat']: h['soni'] for h in Buyurtma.objects.values('holat').annotate(soni=Count('id'))}
    tayinlanmagan = Buyurtma.objects.filter(holat='yangi', xodim__isnull=True).count()
    tasdiqsiz_faol = Buyurtma.objects.filter(holat__in=FAOL_HOLATLAR, tasdiq_summa__isnull=True,
                                             xizmatlar__isnull=False).distinct().count()
    yakunlangan_tasdiqsiz = Buyurtma.objects.filter(holat='bajarildi', tasdiq_summa__isnull=True).count()

    # Bu oy tasdiqlangan summa va hali olinmagan qoldiq (qarz), tarmoqlar bo'yicha
    oy_tasdiq = {t: 0 for t in TARMOQLAR}
    for q in (Buyurtma.objects.filter(tasdiq_vaqt__gte=oy).values('tarmoq')
              .annotate(summa=Sum('tasdiq_summa'))):
        if q['tarmoq'] in oy_tasdiq:
            oy_tasdiq[q['tarmoq']] = q['summa'] or 0
    qoldiq = {t: 0 for t in TARMOQLAR}
    for b in (Buyurtma.objects.filter(tasdiq_summa__isnull=False, tolandi=False)
              .annotate(olingan=Sum('tushumlar__summa', filter=Q(tushumlar__holat='qabul')))
              .values('tarmoq', 'tasdiq_summa', 'olingan')):
        if b['tarmoq'] in qoldiq:
            qoldiq[b['tarmoq']] += max(b['tasdiq_summa'] - (b['olingan'] or 0), 0)

    # ── Xodimlar ──
    faol_xodimlar = Foydalanuvchi.objects.filter(rol='xodim', holat='faol').count()
    ochiq = Smena.objects.filter(
        tugadi__isnull=True, boshlandi__gte=hozir - timedelta(hours=settings.JOYLASHUV_SMENA_MAX_SOAT))
    smenada = ochiq.count()
    aloqada = (Nuqta.objects.filter(smena__in=ochiq,
                                    vaqt__gte=hozir - timedelta(seconds=settings.JOYLASHUV_ALOQA_SONIYA))
               .values('smena').distinct().count())

    # ── Diqqat talab qiladi ──
    diqqat = []
    if eski['soni']:
        diqqat.append({'daraja': 'qizil', 'sahifa': 'cash', 'soni': eski['soni'],
                       'matn': f"{eski['soni']} ta tushum {ESKI_TUSHUM_KUN} kundan beri topshirilmagan"})
    if smenada - aloqada > 0:
        diqqat.append({'daraja': 'sariq', 'sahifa': 'joy', 'soni': smenada - aloqada,
                       'matn': f'{smenada - aloqada} ta xodim smenada, lekin aloqada emas'})
    if tayinlanmagan:
        diqqat.append({'daraja': 'sariq', 'sahifa': 'orders', 'soni': tayinlanmagan,
                       'matn': f'{tayinlanmagan} ta yangi buyurtmaga xodim tayinlanmagan'})
    if yakunlangan_tasdiqsiz:
        diqqat.append({'daraja': 'sariq', 'sahifa': 'orders', 'soni': yakunlangan_tasdiqsiz,
                       'matn': f'{yakunlangan_tasdiqsiz} ta yakunlangan buyurtmaning summasi tasdiqlanmagan'})
    if tasdiqsiz_faol:
        diqqat.append({'daraja': 'info', 'sahifa': 'orders', 'soni': tasdiqsiz_faol,
                       'matn': f'{tasdiqsiz_faol} ta faol buyurtmada xizmat tanlangan, summa hali tasdiqlanmagan'})

    # ── So'nggi faoliyat ──
    nomlar = dict(AuditYozuv._meta.get_field('amal').choices)
    faoliyat = [{
        'kim': y.kim_ism or y.kim_telefon or "Noma'lum",
        'amal': nomlar.get(y.amal, y.amal), 'tafsilot': y.tafsilot, 'vaqt': y.vaqt,
    } for y in AuditYozuv.objects.exclude(amal__in=JURNAL_SHOVQIN)[:8]]

    return {
        'tushum': tushum,
        'qarzdorlar': qarzdorlar,
        'buyurtmalar': {
            'holatlar': holatlar, 'tayinlanmagan': tayinlanmagan,
            'oy_tasdiqlangan': oy_tasdiq, 'qoldiq': qoldiq,
        },
        'xodimlar': {'faol': faol_xodimlar, 'smenada': smenada, 'aloqada': aloqada,
                     'aloqasiz': max(smenada - aloqada, 0)},
        'diqqat': diqqat,
        'faoliyat': faoliyat,
        'eski_tushum_kun': ESKI_TUSHUM_KUN,
    }


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def rahbariyat(request):
    if getattr(request.user, 'rol', None) != 'admin':
        return Response({'detail': _("Ruxsat yo'q")}, status=403)
    return Response(yigma())
