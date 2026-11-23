"""Metrolog kabineti: mijozlar hisoblagichlari, tekshiruv muddatlari va qiyoslov natijasini kiritish.

Faqat lavozimida «metrolog» bo'lgan FAOL xodim (va administrator) ko'radi. Natija kiritilganda
hisoblagichning oxirgi/keyingi tekshiruv sanalari yangilanadi, tarix (QiyoslovYozuvi) saqlanadi va
mijoz kabinetiga bildirishnoma boradi.
"""
import datetime

from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from django.utils.translation import gettext as _
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.auth_app.kabinet_turlari import faol_xodimmi
from apps.auth_app.models import audit_yoz
from .models import TEKSHIRUV_ESLATMA_KUN, Bildirishnoma, Hisoblagich, QiyoslovYozuvi

ROYXAT_LIMIT = 300


def metrologmi(user):
    return faol_xodimmi(user) and 'metrolog' in (user.lavozim or '').lower()


def _ruxsat(user):
    return metrologmi(user) or getattr(user, 'rol', '') == 'admin'


def _json(h):
    o, m = h.obyekt, h.obyekt.mijoz
    return {
        'id': h.id, 'seriya_raqam': h.seriya_raqam, 'turi': h.turi, 'turi_nomi': h.get_turi_display(),
        'markasi': h.markasi, 'holat': h.holat, 'holat_nomi': h.get_holat_display(),
        'oxirgi_tekshiruv': h.oxirgi_tekshiruv, 'keyingi_tekshiruv': h.keyingi_tekshiruv,
        'kun_qoldi': h.kun_qoldi, 'muddat_holati': h.muddat_holati,
        'obyekt': {'nom': o.nom, 'tuman': o.tuman, 'manzil': o.manzil, 'moljal': o.moljal},
        'mijoz': {'ism': m.ism, 'telefon': m.telefon},
    }


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def hisoblagichlar(request):
    """GET ?holat=muddatli (standart: o'tgan + yaqin) | otgan | yaqin | nomalum | hammasi &q=qidiruv"""
    if not _ruxsat(request.user):
        return Response({'detail': _("Faqat metrolog uchun")}, status=403)
    bugun = timezone.localdate()
    chegara = bugun + datetime.timedelta(days=TEKSHIRUV_ESLATMA_KUN)
    qs = Hisoblagich.objects.exclude(holat='almashtirildi').select_related('obyekt', 'obyekt__mijoz')
    xulosa = {
        'otgan': qs.filter(keyingi_tekshiruv__lt=bugun).count(),
        'yaqin': qs.filter(keyingi_tekshiruv__gte=bugun, keyingi_tekshiruv__lte=chegara).count(),
        'nomalum': qs.filter(keyingi_tekshiruv__isnull=True).count(),
        'jami': qs.count(),
    }
    holat = request.query_params.get('holat') or 'muddatli'
    if holat == 'otgan':
        qs = qs.filter(keyingi_tekshiruv__lt=bugun)
    elif holat == 'yaqin':
        qs = qs.filter(keyingi_tekshiruv__gte=bugun, keyingi_tekshiruv__lte=chegara)
    elif holat == 'nomalum':
        qs = qs.filter(keyingi_tekshiruv__isnull=True)
    elif holat == 'muddatli':
        qs = qs.filter(keyingi_tekshiruv__lte=chegara)
    q = (request.query_params.get('q') or '').strip()[:60]
    if q:
        qs = qs.filter(Q(seriya_raqam__icontains=q) | Q(obyekt__mijoz__telefon__icontains=q)
                       | Q(obyekt__mijoz__ism__icontains=q) | Q(obyekt__manzil__icontains=q)
                       | Q(obyekt__tuman__icontains=q))
    qs = qs.order_by('keyingi_tekshiruv', 'id')[:ROYXAT_LIMIT]
    return Response({'xulosa': xulosa, 'eslatma_kun': TEKSHIRUV_ESLATMA_KUN,
                     'hisoblagichlar': [_json(h) for h in qs]})


def _sana(qiymat):
    try:
        return datetime.date.fromisoformat(str(qiymat))
    except (TypeError, ValueError):
        return None


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def qiyoslov(request, pk):
    """POST {sana, natija: yaroqli|yaroqsiz, keyingi_tekshiruv (yaroqli bo'lsa majburiy), izoh}"""
    if not _ruxsat(request.user):
        return Response({'detail': _("Faqat metrolog uchun")}, status=403)
    h = Hisoblagich.objects.select_related('obyekt', 'obyekt__mijoz').filter(pk=pk).first()
    if h is None:
        return Response({'detail': _('Hisoblagich topilmadi')}, status=404)
    bugun = timezone.localdate()
    sana = _sana(request.data.get('sana')) or bugun
    if sana > bugun:
        return Response({'detail': _("Qiyoslov sanasi kelajakda bo'lishi mumkin emas")}, status=400)
    natija = request.data.get('natija')
    if natija not in ('yaroqli', 'yaroqsiz'):
        return Response({'detail': _("Natijani tanlang")}, status=400)
    keyingi = _sana(request.data.get('keyingi_tekshiruv'))
    if natija == 'yaroqli' and (keyingi is None or keyingi <= sana):
        return Response({'detail': _("Keyingi tekshiruv sanasini kiriting (qiyoslov sanasidan keyin)")},
                        status=400)
    if natija == 'yaroqsiz':
        keyingi = None
    izoh = str(request.data.get('izoh') or '').strip()[:255]

    with transaction.atomic():
        QiyoslovYozuvi.objects.create(hisoblagich=h, metrolog=request.user, sana=sana, natija=natija,
                                      keyingi_tekshiruv=keyingi, izoh=izoh)
        h.oxirgi_tekshiruv = sana
        h.keyingi_tekshiruv = keyingi
        h.holat = 'faol' if natija == 'yaroqli' else 'nosoz'
        h.save(update_fields=['oxirgi_tekshiruv', 'keyingi_tekshiruv', 'holat'])
        if natija == 'yaroqli':
            matn = (f"{h.obyekt.nom} obyektidagi {h.seriya_raqam} hisoblagichi {sana:%d.%m.%Y} kuni "
                    f"qiyoslovdan o'tdi. Keyingi tekshiruv: {keyingi:%d.%m.%Y}.")
        else:
            matn = (f"{h.obyekt.nom} obyektidagi {h.seriya_raqam} hisoblagichi {sana:%d.%m.%Y} kuni "
                    f"qiyoslovdan o'tmadi — almashtirish kerak. Operator siz bilan bog'lanadi.")
        Bildirishnoma.objects.create(mijoz=h.obyekt.mijoz, turi='texnik', sarlavha='Hisoblagich qiyoslovi',
                                     matn=matn + (f" Izoh: {izoh}" if izoh else ''), bolim='hisoblagichlar')
    audit_yoz(request, 'panel_ozgarish', f"Qiyoslov: hisoblagich #{h.id} {h.seriya_raqam} — {natija}")
    return Response(_json(h), status=201)
