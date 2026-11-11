"""Narxnomadan tanlangan xizmatlarni buyurtmaga biriktirish va summani tasdiqlash.

Ish jarayoni: xodim narxnomadan xizmatlarni tanlab buyurtmaga biriktiradi ->
narx hisoblanadi (oraliq bo'lsa "eng kam – eng ko'p") -> xodim yakuniy summani
TASDIQLAYDI -> tushum (pul) shu summa bo'yicha qabul qilinadi.
"""
from django.db import transaction
from django.utils import timezone
from django.utils.translation import gettext as _
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.auth_app.models import audit_yoz
from apps.narxnoma.models import NarxnomaQator
from .models import Buyurtma, BuyurtmaXizmat
from .serializers import xizmatlar_malumoti
from .views import _admin_mi, _ruxsat_yoq

MAX_XIZMAT = 50
MAX_SUMMA = 10_000_000_000


def _pul(n):
    return f'{n:,}'.replace(',', ' ')


def _xizmat_ruxsati(request, b, summa_qulfi=True):
    """Admin yoki shu buyurtmaga tayinlangan FAOL xodim. Xodim yakunlangan/bekor
    buyurtmani, shuningdek summasi tasdiqlangan buyurtmaning xizmatlarini
    o'zgartira olmaydi (tasdiqlangan summa keyin 'jimgina' o'zgarmasin)."""
    u = request.user
    if _admin_mi(u):
        return None
    if not (getattr(u, 'rol', None) == 'xodim' and u.holat == 'faol' and b.xodim_id == u.id):
        return _ruxsat_yoq()
    if b.holat in ('bajarildi', 'bekor'):
        return Response({'detail': _("Yakunlangan buyurtmani o'zgartirib bo'lmaydi")}, status=409)
    if summa_qulfi and b.tasdiq_summa is not None:
        return Response({'detail': _("Summa tasdiqlangan. O'zgartirish uchun administratorga murojaat qiling")},
                        status=409)
    return None


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def xizmat_biriktirish(request, pk):
    """Narxnomadan tanlangan xizmatlarni buyurtmaga qo'shadi.

    Tanlov: [{"qator": <narxnoma qatori id>, "ustun": "p"|"r", "soni": 1..999}].
    Mavjud xizmatning soni yangilanadi; ro'yxatda yo'q xizmatlarga tegilmaydi.
    Nom va narx shu paytdagi qiymatda saqlanadi.
    """
    try:
        b = Buyurtma.objects.select_related('tasdiq_kim').get(pk=pk)
    except Buyurtma.DoesNotExist:
        return Response({'detail': _('Buyurtma topilmadi')}, status=404)
    rad = _xizmat_ruxsati(request, b)
    if rad:
        return rad

    royxat = request.data.get('xizmatlar')
    if not isinstance(royxat, list) or not royxat:
        return Response({'detail': _('Xizmatlarni tanlang')}, status=400)
    if len(royxat) > MAX_XIZMAT:
        return Response({'detail': _("Bir martada eng ko'pi %(n)s ta xizmat") % {'n': MAX_XIZMAT}}, status=400)

    tanlov = {}                     # (qator_id, ustun) -> soni; takror bo'lsa oxirgisi
    for el in royxat:
        if not isinstance(el, dict):
            return Response({'detail': _("Tanlov noto'g'ri")}, status=400)
        qid, ustun, soni = el.get('qator'), el.get('ustun'), el.get('soni', 1)
        if (isinstance(qid, bool) or not isinstance(qid, int) or ustun not in ('p', 'r')
                or isinstance(soni, bool) or not isinstance(soni, int) or not (1 <= soni <= 999)):
            return Response({'detail': _("Tanlov noto'g'ri")}, status=400)
        tanlov[(qid, ustun)] = soni

    qatorlar = {q.id: q for q in NarxnomaQator.objects.select_related('narxnoma').filter(
        id__in={k[0] for k in tanlov}, faol=True, narxnoma__faol=True)}
    yozuvlar = []
    for (qid, ustun), soni in tanlov.items():
        q = qatorlar.get(qid)
        if q is None:
            return Response({'detail': _('Tanlangan xizmat narxnomada topilmadi')}, status=400)
        # Narxlar tarmoqqa qarab farq qiladi: ulgurji buyurtmaga aholi narxi (yoki aksincha) qo'yilmaydi
        if q.narxnoma.tarmoq != b.tarmoq:
            return Response({'detail': _("«%(nomi)s» xizmati bu buyurtma tarmog'iga (%(tarmoq)s) mos emas")
                             % {'nomi': q.nomi[:60], 'tarmoq': b.get_tarmoq_display()}}, status=400)
        dan, gacha = (q.p_dan, q.p_gacha) if ustun == 'p' else (q.r_dan, q.r_gacha)
        if dan is None:
            return Response({'detail': _('«%(nomi)s» uchun bu ustunda narx belgilanmagan')
                             % {'nomi': q.nomi[:60]}}, status=400)
        yozuvlar.append((q, ustun, soni, dan, gacha))

    with transaction.atomic():
        for q, ustun, soni, dan, gacha in yozuvlar:
            BuyurtmaXizmat.objects.update_or_create(
                buyurtma=b, qator=q, ustun=ustun,
                defaults={'soni': soni, 'nomi': q.nomi, 'narx_dan': dan, 'narx_gacha': gacha,
                          'ustun_nomi': q.narxnoma.ustun_qisqa(ustun), 'qoshgan': request.user})
    audit_yoz(request, 'buyurtma_xizmat', f'#{b.id}: {len(yozuvlar)} ta xizmat biriktirildi')
    return Response(xizmatlar_malumoti(b), status=201)


@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def xizmat_olib_tashlash(request, xid):
    try:
        x = BuyurtmaXizmat.objects.select_related('buyurtma__tasdiq_kim').get(pk=xid)
    except BuyurtmaXizmat.DoesNotExist:
        return Response({'detail': _('Xizmat topilmadi')}, status=404)
    b = x.buyurtma
    rad = _xizmat_ruxsati(request, b)
    if rad:
        return rad
    nomi = x.nomi
    x.delete()
    audit_yoz(request, 'buyurtma_xizmat', f"#{b.id}: «{nomi[:60]}» olib tashlandi")
    return Response(xizmatlar_malumoti(b))


def _summa_son(qiymat):
    if isinstance(qiymat, bool) or qiymat is None:
        return None
    if isinstance(qiymat, str):
        qiymat = qiymat.replace(' ', '')
        if not qiymat.isdigit():
            return None
    elif isinstance(qiymat, float) and qiymat != int(qiymat):
        return None
    try:
        son = int(qiymat)
    except (TypeError, ValueError):
        return None
    return son if 1 <= son <= MAX_SUMMA else None


@api_view(['POST', 'DELETE'])
@permission_classes([IsAuthenticated])
def summa_tasdiqlash(request, pk):
    """POST — summani tasdiqlaydi. DELETE — tasdiqni bekor qiladi (faqat admin).

    Xodim summani FAQAT tanlangan xizmatlar narxi doirasida kirita oladi
    (jami "dan" ≤ summa ≤ jami "gacha") va bir marta tasdiqlaydi. Administrator
    istalgan summani kirita oladi va tasdiqni qayta o'zgartira oladi.
    """
    try:
        b = Buyurtma.objects.select_related('tasdiq_kim').get(pk=pk)
    except Buyurtma.DoesNotExist:
        return Response({'detail': _('Buyurtma topilmadi')}, status=404)

    if request.method == 'DELETE':
        if not _admin_mi(request.user):
            return _ruxsat_yoq()
        eski = b.tasdiq_summa
        b.tasdiq_summa = b.tasdiq_vaqt = b.tasdiq_kim = None
        b.save(update_fields=['tasdiq_summa', 'tasdiq_vaqt', 'tasdiq_kim', 'yangilangan'])
        audit_yoz(request, 'buyurtma_summa', f'#{b.id}: tasdiq bekor qilindi (edi: {eski})')
        return Response(xizmatlar_malumoti(b))

    rad = _xizmat_ruxsati(request, b)
    if rad:
        return rad

    summa = _summa_son(request.data.get('summa'))
    if summa is None:
        return Response({'detail': _("Summa noto'g'ri")}, status=400)

    if not _admin_mi(request.user):
        h = xizmatlar_malumoti(b)
        if not h['royxat']:
            return Response({'detail': _('Avval narxnomadan xizmatlarni tanlab, buyurtmaga biriktiring')},
                            status=400)
        if not (h['jami_dan'] <= summa <= h['jami_gacha']):
            oraliq = (_pul(h['jami_dan']) if h['jami_dan'] == h['jami_gacha']
                      else f"{_pul(h['jami_dan'])} – {_pul(h['jami_gacha'])}")
            return Response({'detail': _("Summa tanlangan xizmatlar narxi oralig'ida bo'lishi kerak: %(oraliq)s so'm")
                             % {'oraliq': oraliq}}, status=400)

    eski = b.tasdiq_summa
    b.tasdiq_summa = summa
    b.tasdiq_vaqt = timezone.now()
    b.tasdiq_kim = request.user
    b.save(update_fields=['tasdiq_summa', 'tasdiq_vaqt', 'tasdiq_kim', 'yangilangan'])
    audit_yoz(request, 'buyurtma_summa',
              f"#{b.id}: {summa} so'm tasdiqlandi" + (f' (edi: {eski})' if eski is not None else ''))
    return Response(xizmatlar_malumoti(b))
