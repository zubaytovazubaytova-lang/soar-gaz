from django.core.cache import cache
from django.db.models import Count, Q, Sum
from django.utils import timezone
from django.utils.translation import gettext as _
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.auth_app.kabinet_turlari import kadrmi
from apps.auth_app.models import audit_yoz
from apps.buyurtmalar.models import Buyurtma
from apps.narxnoma.models import BOLIM_NOMI, Narxnoma, NarxnomaQator, TARMOQ_NOMI
from .hal import ALLAQACHON, TOPILMADI, hal_qil
from .models import Tushum, USUL_CHOICES

# Bir martalik tushum uchun mantiqiy yuqori chegara: tasodifan qo'shimcha nol
# yozib yuborishdan saqlaydi (100 mln so'm).
MAX_SUMMA = 100_000_000
ROYXAT_LIMIT = 100
ADMIN_LIMIT = 300


def _xodimmi(request):
    u = request.user
    return getattr(u, 'rol', None) == 'xodim' and getattr(u, 'holat', '') == 'faol'


def _adminmi(request):
    return getattr(request.user, 'rol', None) == 'admin'


def _kvitansiya(t):
    """Tushumga berilgan kvitansiya (bo'lsa): sahifa havolasi va SMS holati."""
    k = getattr(t, 'kvitansiya', None)           # teskari bog'lanish: yo'q bo'lsa None
    if k is None:
        return None
    return {'id': k.id, 'raqam': k.raqam, 'holat': k.holat, 'sms_holat': k.sms_holat,
            'url': f'/kvitansiya/{k.token}/', 'mijoz_telefon': k.mijoz_telefon}


def _yozuv(t):
    return {
        'kvitansiya': _kvitansiya(t),
        'id': t.id,
        'summa': t.summa,
        'usul': t.usul,
        'usul_nomi': t.get_usul_display(),
        'izoh': t.izoh,
        'ish_turi': t.ish_turi,
        'tarmoq': t.tarmoq, 'tarmoq_nomi': TARMOQ_NOMI.get(t.tarmoq, ''),
        'bolim': t.bolim, 'bolim_nomi': BOLIM_NOMI.get(t.bolim, ''),
        'holat': t.holat,
        'holat_nomi': t.get_holat_display(),
        'buyurtma_id': t.buyurtma_id,
        'buyurtma_nomi': (f"#{t.buyurtma_id} {t.buyurtma.xizmat_nomi or t.buyurtma.xizmat}"
                          if t.buyurtma_id else ''),
        'yaratilgan': t.yaratilgan,
        'hal_vaqti': t.hal_vaqti,
        'rad_sababi': t.rad_sababi,
    }


def _summa(qiymat):
    """Butun so'm. bool, kasr, manfiy va juda katta qiymat rad etiladi."""
    if isinstance(qiymat, bool) or qiymat is None:
        return None
    if isinstance(qiymat, str):
        qiymat = qiymat.replace(' ', '')
        if not qiymat.isdigit():
            return None
    elif isinstance(qiymat, float):
        if qiymat != int(qiymat):
            return None
    try:
        son = int(qiymat)
    except (TypeError, ValueError):
        return None
    return son if 1 <= son <= MAX_SUMMA else None


def _oy_boshi():
    hozir = timezone.localtime()
    return hozir.replace(day=1, hour=0, minute=0, second=0, microsecond=0)


# ───────────── Xodim tomoni ─────────────

@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def tushum_xodim(request):
    if not _xodimmi(request):
        return Response({'detail': _('Faqat xodim uchun')}, status=403)
    xodim = request.user

    if request.method == 'POST':
        summa = _summa(request.data.get('summa'))
        if summa is None:
            return Response({'detail': _("Summa 1 dan %(max)s so'mgacha butun son bo'lishi kerak")
                             % {'max': f'{MAX_SUMMA:,}'.replace(',', ' ')}}, status=400)
        usul = request.data.get('usul') or 'naqd'
        if usul not in dict(USUL_CHOICES):
            return Response({'detail': _("To'lov usuli noto'g'ri")}, status=400)
        izoh = str(request.data.get('izoh') or '').strip()[:255]

        buyurtma = None
        bid = request.data.get('buyurtma')
        if bid not in (None, ''):
            try:
                buyurtma = Buyurtma.objects.get(pk=int(bid), xodim=xodim)
            except (Buyurtma.DoesNotExist, TypeError, ValueError):
                # Boshqa xodimning buyurtmasi ham shu xabarni oladi — mavjudligi sezilmasin
                return Response({'detail': _('Buyurtma topilmadi')}, status=400)

        # Ish turi narxnomadan: nomni mijoz yuborgan matndan emas, serverdagi
        # narxnomadan olamiz (soxtalashtirib bo'lmasin)
        ish_qator, ish_turi = None, ''
        iq = request.data.get('ish_qator')
        if iq not in (None, ''):
            ustun = request.data.get('ish_ustun')
            if ustun not in (None, '', 'p', 'r') or isinstance(iq, bool):
                return Response({'detail': _("Ish turi noto'g'ri")}, status=400)
            try:
                ish_qator = NarxnomaQator.objects.select_related('narxnoma').get(
                    pk=int(iq), faol=True, narxnoma__faol=True)
            except (NarxnomaQator.DoesNotExist, TypeError, ValueError):
                return Response({'detail': _('Ish turi narxnomada topilmadi')}, status=400)
            ish_turi = ish_qator.nomi
            if ustun in ('p', 'r'):
                qisqa = ish_qator.narxnoma.ustun_qisqa(ustun)
                if qisqa:
                    ish_turi += f' ({qisqa})'
            # Buyurtma bo'lsa, ish turi buyurtma tarmog'iga mos bo'lishi kerak
            if buyurtma is not None and ish_qator.narxnoma.tarmoq != buyurtma.tarmoq:
                return Response({'detail': _("Tanlangan ish turi buyurtma tarmog'iga (%(t)s) mos emas")
                                 % {'t': TARMOQ_NOMI.get(buyurtma.tarmoq, '')}}, status=400)

        # Tushum turi (bosqich): "tarmoq:bo'lim", masalan "aholi:ornatish". Xodim uni aniq
        # tanlaydi; tanlanmasa ("Boshqa") turkum ish turidan yoki buyurtmadan olinadi.
        turi = request.data.get('tushum_turi')
        if turi not in (None, ''):
            tarmoq, ajratgich, bolim = str(turi).partition(':')
            if not Narxnoma.objects.filter(tarmoq=tarmoq, bolim=bolim, faol=True).exists():
                return Response({'detail': _("Tushum turi noto'g'ri")}, status=400)
            if ish_qator is not None and (ish_qator.narxnoma.tarmoq, ish_qator.narxnoma.bolim) != (tarmoq, bolim):
                return Response({'detail': _('Tanlangan ish turi bu tushum turiga mos emas')}, status=400)
            if buyurtma is not None and buyurtma.tarmoq != tarmoq:
                return Response({'detail': _("Buyurtma bu tushum turining tarmog'iga mos emas")}, status=400)
            # «Buyurtma asosida»: mavjud buyurtma YOKI narxnomadagi ish turi yetarli (mijoz o'zi
            # murojaat qilgan bo'lsa tizimda buyurtma bo'lmasligi mumkin; kvitansiyada mijoz ro'yxatga olinadi)
            if bolim == 'buyurtma' and buyurtma is None and ish_qator is None:
                return Response({'detail': _("Buyurtma asosidagi tushum uchun buyurtmani yoki narxnomadan ish turini "
                                             "tanlang")}, status=400)
        elif ish_qator is not None:
            tarmoq, bolim = ish_qator.narxnoma.tarmoq, ish_qator.narxnoma.bolim
        elif buyurtma is not None:
            tarmoq, bolim = buyurtma.tarmoq, ''
        else:
            tarmoq, bolim = '', ''

        # Buyurtma asosidagi tushum tasdiqlangan summa bo'yicha olinadi: xodim avval
        # xizmatlarni tanlab narxni tasdiqlaydi, so'ng pul shu summadan oshmaydi.
        if buyurtma is not None:
            if buyurtma.tasdiq_summa is None:
                return Response({'detail': _('Avval buyurtma narxini hisoblab, summani tasdiqlang '
                                             '(Vazifalarim bo\'limida)')}, status=400)
            kiritilgan = (Tushum.objects.filter(buyurtma=buyurtma, holat__in=('kutilmoqda', 'qabul'))
                          .aggregate(s=Sum('summa'))['s'] or 0)
            qoldi = buyurtma.tasdiq_summa - kiritilgan
            if summa > qoldi:
                return Response({'detail': _("Summa buyurtma qoldig'idan oshib ketdi. Qoldiq: %(q)s so'm")
                                 % {'q': f'{max(qoldi, 0):,}'.replace(',', ' ')}}, status=400)

        # Qo'sh bosish yoki tarmoq qayta urinishi pulni ikki marta yozmasin
        belgi = f'tushum:{xodim.pk}:{buyurtma.pk if buyurtma else 0}:{summa}:{usul}'
        if not cache.add(belgi, 1, 30):
            return Response({'detail': _('Bu tushum hozirgina kiritilgan')}, status=409)

        t = Tushum.objects.create(xodim=xodim, buyurtma=buyurtma, summa=summa,
                                  usul=usul, izoh=izoh, ish_qator=ish_qator, ish_turi=ish_turi,
                                  tarmoq=tarmoq, bolim=bolim)
        audit_yoz(request, 'tushum_kiritildi', f'{summa} so\'m ({t.get_usul_display()}), #{t.pk}')
        return Response(_yozuv(t), status=201)

    qs = Tushum.objects.filter(xodim=xodim)
    jami = qs.aggregate(
        kutilmoqda=Sum('summa', filter=Q(holat='kutilmoqda')),
        qabul=Sum('summa', filter=Q(holat='qabul')),
        oy_qabul=Sum('summa', filter=Q(holat='qabul', hal_vaqti__gte=_oy_boshi())),
    )
    yozuvlar = qs.select_related('buyurtma', 'kvitansiya')[:ROYXAT_LIMIT]
    return Response({
        'jami': {k: v or 0 for k, v in jami.items()},
        'yozuvlar': [_yozuv(t) for t in yozuvlar],
    })


# ───────────── Admin tomoni ─────────────

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def tushum_admin(request):
    """Barcha tushumlar va xodimlar bo'yicha qoldiq (topshirmagan summa). Administrator va Kadrlar mutaxassisi."""
    if not (_adminmi(request) or kadrmi(request.user)):
        return Response({'detail': _("Ruxsat yo'q")}, status=403)

    qs = Tushum.objects.select_related('xodim', 'buyurtma', 'kvitansiya')
    holat = request.query_params.get('holat')
    if holat in ('kutilmoqda', 'qabul', 'rad'):
        qs = qs.filter(holat=holat)
    tarmoq_filtr = request.query_params.get('tarmoq')
    if tarmoq_filtr in TARMOQ_NOMI:
        qs = qs.filter(tarmoq=tarmoq_filtr)

    # Tarmoqlar bo'yicha tushum (aholi / ulgurji / turkumsiz) — filtrdan mustaqil
    tarmoq_jami = {}
    for qator in (Tushum.objects.values('tarmoq')
                  .annotate(kutilmoqda=Sum('summa', filter=Q(holat='kutilmoqda')),
                            qabul=Sum('summa', filter=Q(holat='qabul')),
                            oy_qabul=Sum('summa', filter=Q(holat='qabul', hal_vaqti__gte=_oy_boshi())))):
        tarmoq_jami[qator['tarmoq'] or 'boshqa'] = {
            'nomi': TARMOQ_NOMI.get(qator['tarmoq'], 'Turkumsiz'),
            'kutilmoqda': qator['kutilmoqda'] or 0, 'qabul': qator['qabul'] or 0,
            'oy_qabul': qator['oy_qabul'] or 0,
        }

    xodimlar = (Tushum.objects.values('xodim_id', 'xodim__ism', 'xodim__telefon')
                .annotate(
                    kutilmoqda_summa=Sum('summa', filter=Q(holat='kutilmoqda')),
                    kutilmoqda_soni=Count('id', filter=Q(holat='kutilmoqda')),
                    qabul_summa=Sum('summa', filter=Q(holat='qabul')),
                    oy_summa=Sum('summa', filter=Q(holat='qabul', hal_vaqti__gte=_oy_boshi())),
                ).order_by('-kutilmoqda_summa'))

    yozuvlar = []
    for t in qs[:ADMIN_LIMIT]:
        d = _yozuv(t)
        d['xodim_id'] = t.xodim_id
        d['xodim_ism'] = t.xodim.ism or t.xodim.telefon
        yozuvlar.append(d)

    return Response({
        'tarmoq_jami': tarmoq_jami,
        'xodimlar': [{
            'xodim_id': x['xodim_id'],
            'ism': x['xodim__ism'] or x['xodim__telefon'],
            'kutilmoqda_summa': x['kutilmoqda_summa'] or 0,
            'kutilmoqda_soni': x['kutilmoqda_soni'],
            'qabul_summa': x['qabul_summa'] or 0,
            'oy_summa': x['oy_summa'] or 0,
        } for x in xodimlar],
        'yozuvlar': yozuvlar,
    })


def _hal_ruxsati(request, pk):
    """Tushumni administrator yoki Kadrlar mutaxassisi hal qiladi (None = ruxsat bor).
    Kadrlar o'z tushumini o'zi qabul qila olmaydi: pulni topshiruvchi va qabul qiluvchi bir odam bo'lmasin."""
    if _adminmi(request):
        return None
    if kadrmi(request.user):
        if Tushum.objects.filter(pk=pk, xodim=request.user).exists():
            return Response({'detail': _("O'z tushumingizni o'zingiz qabul qila olmaysiz")}, status=403)
        return None
    return Response({'detail': _("Ruxsat yo'q")}, status=403)


def _hal_qil(request, pk, yangi_holat, sabab=''):
    """kutilmoqda -> qabul/rad (mantiq: apps/tushum/hal.py, Django paneli ham shuni ishlatadi)."""
    natija, t = hal_qil(request, pk, yangi_holat, sabab)
    if natija == ALLAQACHON:
        return Response({'detail': _('Bu tushum allaqachon hal qilingan')}, status=409)
    if natija == TOPILMADI:
        return Response({'detail': _('Tushum topilmadi')}, status=404)
    return Response(_yozuv(t))


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def tushum_qabul(request, pk):
    yopiq = _hal_ruxsati(request, pk)
    if yopiq:
        return yopiq
    return _hal_qil(request, pk, 'qabul')


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def tushum_rad(request, pk):
    yopiq = _hal_ruxsati(request, pk)
    if yopiq:
        return yopiq
    sabab = str(request.data.get('sabab') or '').strip()[:255]
    if not sabab:
        return Response({'detail': _('Rad etish sababini yozing')}, status=400)
    return _hal_qil(request, pk, 'rad', sabab)
