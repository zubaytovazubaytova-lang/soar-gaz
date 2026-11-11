"""Mijoz kabineti API.

Barcha endpointlar faqat o'z ma'lumotini qaytaradi — queryset har doim
`request.user` bo'yicha filtrlanadi.
"""

import os

from django.core import signing
from django.db.models import Count, Exists, OuterRef, Q, Sum
from django.http import FileResponse, HttpResponseForbidden, HttpResponseGone
from django.utils import timezone
from django.utils.translation import gettext as _
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.buyurtmalar.models import Buyurtma
from apps.buyurtmalar.serializers import BuyurtmaSerializer
from apps.sms_app.models import SmsXabar
from apps.tolovlar.models import TolovSorovi
from apps.xaridlar.models import Xarid
from apps.xaridlar.serializers import XaridSerializer

from .models import (
    Obyekt, Uskuna, Hisoblagich, Hujjat, Bildirishnoma, Sharh,
    Murojaat, MurojaatXabar, QongiroqSorovi, SavolJavob, KabinetSozlama,
    TEKSHIRUV_ESLATMA_KUN,
)
from .serializers import (
    ObyektSerializer, UskunaSerializer, HisoblagichSerializer, HujjatSerializer,
    BildirishnomaSerializer, SharhSerializer, MurojaatSerializer,
    MurojaatXabarSerializer, QongiroqSerializer, SavolJavobSerializer,
    SozlamaSerializer,
)


def _obyekt_olish(user, pk):
    return Obyekt.objects.filter(mijoz=user, pk=pk).first()


def _bildirishnoma(mijoz, sarlavha, matn='', turi='umumiy', bolim=''):
    return Bildirishnoma.objects.create(
        mijoz=mijoz, sarlavha=sarlavha, matn=matn, turi=turi, bolim=bolim
    )


# ──────────────────────────────────────────────────────────────
#  1. BOSH SAHIFA — umumiy ko'rinish
# ──────────────────────────────────────────────────────────────

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def obzor(request):
    user = request.user
    buyurtmalar = Buyurtma.objects.filter(mijoz=user)

    # Buyurtmalar bo'yicha to'rtta son — bitta so'rovda (avval 4 ta COUNT edi)
    b_stat = buyurtmalar.aggregate(
        jami=Count('id'),
        faol=Count('id', filter=~Q(holat__in=['bajarildi', 'bekor'])),
        bajarilgan=Count('id', filter=Q(holat='bajarildi')),
        baholanmagan=Count('id', filter=Q(holat='bajarildi', sharh__isnull=True)),
    )

    keyingi = Hisoblagich.objects.filter(
        obyekt__mijoz=user, holat='faol', keyingi_tekshiruv__isnull=False
    ).select_related('obyekt').order_by('keyingi_tekshiruv').first()

    # Soni va summasi bitta so'rovda — avval barcha so'rov obyektlari
    # faqat `summa` maydoni uchun Python'ga yuklanardi
    tolov_stat = TolovSorovi.objects.filter(
        telefon=user.telefon, holat__in=['yangi', 'kutilmoqda']
    ).aggregate(soni=Count('id'), summa=Sum('summa'))

    # Obyekt va undagi hisoblagichlar soni — bitta JOIN'li so'rovda.
    # distinct=True bo'lmasa obyekt har hisoblagichi uchun qayta sanalardi.
    obyekt_stat = Obyekt.objects.filter(mijoz=user).aggregate(
        obyekt=Count('id', distinct=True),
        hisoblagich=Count('hisoblagichlar'),
    )

    return Response({
        'mijoz': {
            'id': user.id,
            'ism': user.ism,
            'telefon': user.telefon,
            'manzil': user.manzil,
            'tuman': user.tuman,
            'email': user.email,
            'profil_toliq': bool(user.ism and user.manzil and user.tuman),
        },
        'faol_buyurtma': b_stat['faol'],
        'jami_buyurtma': b_stat['jami'],
        'bajarilgan_buyurtma': b_stat['bajarilgan'],
        'obyekt_soni': obyekt_stat['obyekt'],
        'hisoblagich_soni': obyekt_stat['hisoblagich'],
        'oqilmagan_bildirishnoma': Bildirishnoma.objects.filter(mijoz=user, oqildi=False).count(),
        'kutilayotgan_tolov': tolov_stat['soni'],
        'kutilayotgan_summa': tolov_stat['summa'] or 0,
        'hujjat_soni': Hujjat.objects.filter(mijoz=user).count(),
        'baholanmagan': b_stat['baholanmagan'],
        'keyingi_xizmat': (
            {
                'sana': keyingi.keyingi_tekshiruv,
                'kun_qoldi': keyingi.kun_qoldi,
                'hisoblagich': keyingi.seriya_raqam,
                'obyekt': keyingi.obyekt.nom,
                'matn': f"Keyingi metrologik tekshiruv — {keyingi.obyekt.nom}",
            } if keyingi else None
        ),
        'oxirgi_buyurtmalar': BuyurtmaSerializer(
            buyurtmalar.select_related('mijoz', 'xodim').order_by('-yaratilgan')[:3],
            many=True,
        ).data,
    })


# ──────────────────────────────────────────────────────────────
#  2. MENING BUYURTMALARIM
# ──────────────────────────────────────────────────────────────

# Mijozga ko'rsatiladigan bosqichlar: model holati + xodim tayinlanganiga qarab
BOSQICHLAR = ['yangi', 'korilmoqda', 'tayinlandi', 'bajarilmoqda', 'yakunlandi']


def _bosqich(b):
    if b.holat == 'bekor':
        return 'bekor'
    if b.holat == 'bajarildi':
        return 'yakunlandi'
    if b.holat == 'bajarilmoqda':
        return 'bajarilmoqda'
    if b.holat == 'qabul':
        return 'tayinlandi'
    return 'tayinlandi' if b.xodim_id else 'yangi'


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def buyurtmalarim(request):
    # `mijoz` ham select_related'da: BuyurtmaSerializer.get_mijoz_malumot
    # unga murojaat qiladi va bo'lmasa har qator uchun alohida so'rov ketardi.
    # `baholangan` esa Exists bilan — avval siklda .exists() chaqirilardi.
    qs = (
        Buyurtma.objects
        .filter(mijoz=request.user)
        .select_related('mijoz', 'xodim', 'obyekt')
        .annotate(baholangan_bayroq=Exists(
            Sharh.objects.filter(buyurtma=OuterRef('pk'))
        ))
    )

    holat = request.query_params.get('holat')
    if holat == 'faol':
        qs = qs.exclude(holat__in=['bajarildi', 'bekor'])
    elif holat == 'yakunlangan':
        qs = qs.filter(holat='bajarildi')
    elif holat:
        qs = qs.filter(holat=holat)

    xizmat = request.query_params.get('xizmat')
    if xizmat:
        qs = qs.filter(xizmat=xizmat)

    natija = []
    for b in qs:
        malumot = BuyurtmaSerializer(b).data
        malumot['bosqich'] = _bosqich(b)
        malumot['obyekt_nomi'] = b.obyekt.nom if b.obyekt else ''
        malumot['baholangan'] = b.baholangan_bayroq
        natija.append(malumot)
    return Response(natija)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def buyurtma_detal(request, pk):
    b = Buyurtma.objects.filter(mijoz=request.user, pk=pk).select_related(
        'mijoz', 'xodim', 'obyekt').first()
    if not b:
        return Response({'detail': _('Buyurtma topilmadi')}, status=404)
    malumot = BuyurtmaSerializer(b).data
    malumot['bosqich'] = _bosqich(b)
    malumot['obyekt_nomi'] = b.obyekt.nom if b.obyekt else ''
    sharh = Sharh.objects.filter(buyurtma=b).first()
    malumot['sharh'] = SharhSerializer(sharh).data if sharh else None
    return Response(malumot)


# ──────────────────────────────────────────────────────────────
#  3. MENING OBYEKTLARIM
# ──────────────────────────────────────────────────────────────

@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def obyektlar(request):
    if request.method == 'GET':
        qs = Obyekt.objects.filter(mijoz=request.user).prefetch_related(
            'uskunalar', 'hisoblagichlar'
        ).annotate(buyurtma_soni_db=Count('buyurtmalar'))
        return Response(ObyektSerializer(qs, many=True).data)

    ser = ObyektSerializer(data=request.data)
    if not ser.is_valid():
        return Response(ser.errors, status=400)
    # Birinchi obyekt avtomatik asosiy bo'ladi
    birinchi = not Obyekt.objects.filter(mijoz=request.user).exists()
    obj = ser.save(mijoz=request.user, asosiy=ser.validated_data.get('asosiy') or birinchi)
    return Response(ObyektSerializer(obj).data, status=201)


@api_view(['GET', 'PATCH', 'DELETE'])
@permission_classes([IsAuthenticated])
def obyekt_detal(request, pk):
    obj = _obyekt_olish(request.user, pk)
    if not obj:
        return Response({'detail': _('Obyekt topilmadi')}, status=404)

    if request.method == 'GET':
        return Response(ObyektSerializer(obj).data)

    if request.method == 'DELETE':
        obj.delete()
        return Response({'ochirildi': True})

    ser = ObyektSerializer(obj, data=request.data, partial=True)
    if not ser.is_valid():
        return Response(ser.errors, status=400)
    ser.save()
    return Response(ser.data)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def uskunalar(request):
    obyekt = _obyekt_olish(request.user, request.data.get('obyekt'))
    if not obyekt:
        return Response({'detail': _('Obyekt topilmadi')}, status=404)
    ser = UskunaSerializer(data=request.data)
    if not ser.is_valid():
        return Response(ser.errors, status=400)
    ser.save(obyekt=obyekt)
    return Response(ser.data, status=201)


@api_view(['PATCH', 'DELETE'])
@permission_classes([IsAuthenticated])
def uskuna_detal(request, pk):
    u = Uskuna.objects.filter(pk=pk, obyekt__mijoz=request.user).first()
    if not u:
        return Response({'detail': _('Uskuna topilmadi')}, status=404)
    if request.method == 'DELETE':
        u.delete()
        return Response({'ochirildi': True})
    ser = UskunaSerializer(u, data=request.data, partial=True)
    if not ser.is_valid():
        return Response(ser.errors, status=400)
    ser.save()
    return Response(ser.data)


# ──────────────────────────────────────────────────────────────
#  4. HISOBLAGICHLARIM VA TEXNIK KO'RIK
# ──────────────────────────────────────────────────────────────

@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def hisoblagichlar(request):
    if request.method == 'GET':
        qs = Hisoblagich.objects.filter(obyekt__mijoz=request.user).select_related('obyekt')
        return Response({
            'eslatma_kun': TEKSHIRUV_ESLATMA_KUN,
            'royxat': HisoblagichSerializer(qs, many=True).data,
        })

    obyekt = _obyekt_olish(request.user, request.data.get('obyekt'))
    if not obyekt:
        return Response({'detail': _('Obyekt topilmadi')}, status=404)
    ser = HisoblagichSerializer(data=request.data)
    if not ser.is_valid():
        return Response(ser.errors, status=400)
    ser.save(obyekt=obyekt)
    return Response(ser.data, status=201)


@api_view(['PATCH', 'DELETE'])
@permission_classes([IsAuthenticated])
def hisoblagich_detal(request, pk):
    h = Hisoblagich.objects.filter(pk=pk, obyekt__mijoz=request.user).first()
    if not h:
        return Response({'detail': _('Hisoblagich topilmadi')}, status=404)
    if request.method == 'DELETE':
        h.delete()
        return Response({'ochirildi': True})
    ser = HisoblagichSerializer(h, data=request.data, partial=True)
    if not ser.is_valid():
        return Response(ser.errors, status=400)
    ser.save()
    return Response(ser.data)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def tekshiruvga_yozilish(request, pk):
    """Bir tugma bilan metrologiya buyurtmasi ochiladi."""
    h = Hisoblagich.objects.filter(pk=pk, obyekt__mijoz=request.user).select_related('obyekt').first()
    if not h:
        return Response({'detail': _('Hisoblagich topilmadi')}, status=404)

    ochiq = Buyurtma.objects.filter(
        mijoz=request.user, xizmat='metrologiya', obyekt=h.obyekt
    ).exclude(holat__in=['bajarildi', 'bekor']).first()
    if ochiq:
        return Response({
            'detail': _("Bu obyekt uchun metrologiya buyurtmasi allaqachon "
                        "ochiq (#%(id)s)") % {'id': ochiq.id},
            'buyurtma_id': ochiq.id,
        }, status=400)

    b = Buyurtma.objects.create(
        mijoz=request.user,
        obyekt=h.obyekt,
        xizmat='metrologiya',
        tavsif=f"Hisoblagich {h.seriya_raqam} ({h.markasi or h.get_turi_display()}) — davlat tekshiruvi.",
        # Modelda max_length=100: uzun matn bazani buzmasligi uchun qirqiladi
        vaqt_istagi=str(request.data.get('vaqt_istagi') or "Operator bog'lansin")[:100],
    )
    _bildirishnoma(
        request.user,
        'Tekshiruvga yozildingiz',
        f"#{b.id} — {h.obyekt.nom} obyektidagi {h.seriya_raqam} hisoblagichi uchun ariza qabul qilindi.",
        turi='texnik', bolim='buyurtmalar',
    )
    return Response(BuyurtmaSerializer(b).data, status=201)


# ──────────────────────────────────────────────────────────────
#  5. TO'LOVLAR VA HISOB-FAKTURALAR
# ──────────────────────────────────────────────────────────────

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def tolovlarim(request):
    user = request.user
    # Faqat javobda ishlatiladigan maydonlar olinadi. Xarid'da ~40 ta ustun
    # bor (koordinatalar, muammo izohi, summa tafsiloti) — ular bu yerda
    # kerak emas, lekin ilgari har qatorda baribir o'qilardi.
    sorovlar = TolovSorovi.objects.filter(telefon=user.telefon).only(
        'id', 'xizmat_turi', 'tolov_turi_nomi', 'summa',
        'tolov_tizimi', 'tolov_turi', 'holat', 'yaratilgan',
    )
    # Telefon `_xaridlarim()` dagi kabi barcha yozilishlari bo'yicha qidiriladi
    # — aks holda bo'shliqli raqam bilan qilingan mehmon xaridi "Xaridlarim"da
    # ko'rinib, "To'lovlar" ro'yxatidan tushib qolardi.
    xaridlar = Xarid.objects.filter(
        Q(mijoz=user) | Q(telefon__in=_telefon_variantlari(user.telefon))
    ).only(
        'id', 'raqam', 'jami', 'tolov_usuli', 'tolov_holati', 'tolandi', 'yaratilgan',
        # `holat` javobda ishlatilmaydi, lekin xaridlar.signals dagi post_init
        # uni o'qiydi — defer qilinsa har qator uchun qo'shimcha so'rov ketadi.
        'holat',
    )

    royxat = [{
        'manba': 'xizmat',
        'id': t.id,
        'nom': t.xizmat_turi or t.tolov_turi_nomi,
        'summa': t.summa,
        'usul': t.tolov_tizimi or t.tolov_turi,
        'holat': t.holat,
        'tolandi': t.holat == 'tolandi',
        'sana': t.yaratilgan,
    } for t in sorovlar]

    royxat += [{
        'manba': 'xarid',
        'id': x.id,
        'raqam': x.raqam,
        'nom': f"Do'kon buyurtmasi {x.raqam}",
        'summa': x.jami,
        'usul': x.tolov_usuli,
        'holat': x.tolov_holati,
        'tolandi': x.tolandi,
        'sana': x.yaratilgan,
    } for x in xaridlar]

    royxat.sort(key=lambda r: r['sana'], reverse=True)
    kutilayotgan = [r for r in royxat if not r['tolandi']]

    return Response({
        'royxat': royxat,
        'kutilayotgan_soni': len(kutilayotgan),
        'kutilayotgan_summa': sum(r['summa'] for r in kutilayotgan),
        'tolangan_summa': sum(r['summa'] for r in royxat if r['tolandi']),
        'fakturalar': HujjatSerializer(
            Hujjat.objects.filter(mijoz=user, turi='faktura'),
            many=True, context={'request': request},
        ).data,
    })


# ──────────────────────────────────────────────────────────────
#  5b. DO'KON XARIDLARIM
#
#  `/api/xaridlar/` mehmon xaridi uchun mo'ljallangan — u yerda egalik
#  buyurtma raqami bilan tasdiqlanadi. Ilova esa tokenli, shuning uchun
#  kabinet o'z shoxini beradi: queryset har doim `request.user` bo'yicha
#  filtrlanadi va begona raqam so'rash imkoni yo'q.
# ──────────────────────────────────────────────────────────────

def _telefon_variantlari(telefon):
    """Bir raqamning bazada uchraydigan yozilishlari.

    Hisob telefoni normallashgan (`+998901112233`), do'kon buyurtmasi esa
    saytdagi maskadan kelib bo'shliqli bo'lishi mumkin
    (`+998 90 111 22 33`). Ikkalasini ham qidiramiz — bu `telefon`
    ustunidagi indeksdan foydalanadi, butun jadvalni o'qimaydi.
    """
    raqamlar = ''.join(ch for ch in (telefon or '') if ch.isdigit())
    if len(raqamlar) != 12:      # 998 + 9 xonali raqam
        return [telefon] if telefon else []
    zich = f'+{raqamlar}'
    bosh = (f'+{raqamlar[:3]} {raqamlar[3:5]} {raqamlar[5:8]} '
            f'{raqamlar[8:10]} {raqamlar[10:]}')
    return [zich, bosh]


def _xaridlarim(user):
    """Foydalanuvchining do'kon buyurtmalari.

    Mehmon sifatida qilingan xaridda `mijoz` bog'lanmagan bo'lishi mumkin —
    u holda telefon bo'yicha topiladi.
    """
    return list(
        Xarid.objects
        .filter(Q(mijoz=user) | Q(telefon__in=_telefon_variantlari(user.telefon)))
        .prefetch_related('qatorlar')
        .distinct()
    )


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def xaridlarim(request):
    royxat = _xaridlarim(request.user)
    royxat.sort(key=lambda x: x.yaratilgan, reverse=True)

    holat = request.query_params.get('holat')
    if holat == 'faol':
        royxat = [x for x in royxat if x.holat not in ('yetkazildi', 'bekor')]
    elif holat == 'yakunlangan':
        royxat = [x for x in royxat if x.holat == 'yetkazildi']
    elif holat:
        royxat = [x for x in royxat if x.holat == holat]

    return Response(XaridSerializer(royxat, many=True).data)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def xarid_detal(request, raqam):
    for x in _xaridlarim(request.user):
        if x.raqam == raqam:
            return Response(XaridSerializer(x).data)
    return Response({'detail': _('Buyurtma topilmadi')}, status=404)


# ──────────────────────────────────────────────────────────────
#  6. HUJJATLARIM
# ──────────────────────────────────────────────────────────────

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def hujjatlar(request):
    qs = Hujjat.objects.filter(mijoz=request.user).select_related('obyekt')
    turi = request.query_params.get('turi')
    if turi:
        qs = qs.filter(turi=turi)
    return Response(HujjatSerializer(qs, many=True, context={'request': request}).data)


# Hujjat havolasi imzolanadi va qisqa muddat amal qiladi — /media/ ostidagi
# fayl manzili mijozga hech qachon berilmaydi (katalog hujjatlaridagi kabi).
HUJJAT_IMZO_TUZI = 'kabinet-hujjat'
HUJJAT_HAVOLA_MUDDATI = 300   # soniya


def hujjat_ochish(request, token):
    """Imzolangan havola bo'yicha hujjatni beradi.

    Token 5 daqiqa amal qiladi, boshqaga uzatilsa ham foydasiz. Fayl faqat
    hujjat egasiga tegishli bo'lgani uchun token o'zi ruxsat vazifasini bajaradi.
    """
    try:
        malumot = signing.loads(token, salt=HUJJAT_IMZO_TUZI, max_age=HUJJAT_HAVOLA_MUDDATI)
    except signing.SignatureExpired:
        return HttpResponseGone('Havola muddati tugagan. Kabinetni yangilang.')
    except signing.BadSignature:
        return HttpResponseForbidden('Havola yaroqsiz.')

    hujjat = Hujjat.objects.filter(id=malumot['id']).first()
    if not hujjat or not hujjat.fayl:
        return HttpResponseForbidden('Hujjat topilmadi.')

    javob = FileResponse(hujjat.fayl.open('rb'), as_attachment=True,
                         filename=os.path.basename(hujjat.fayl.name))
    javob['Cache-Control'] = 'no-store, no-cache, must-revalidate, private, max-age=0'
    javob['X-Robots-Tag'] = 'noindex, nofollow'
    return javob


# ──────────────────────────────────────────────────────────────
#  7. BILDIRISHNOMALAR
# ──────────────────────────────────────────────────────────────

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def bildirishnomalar(request):
    qs = Bildirishnoma.objects.filter(mijoz=request.user)[:100]
    return Response({
        'oqilmagan': Bildirishnoma.objects.filter(mijoz=request.user, oqildi=False).count(),
        'royxat': BildirishnomaSerializer(qs, many=True).data,
        # SMS tarixi ham shu bo'limda ko'rsatiladi
        'sms': [
            {'id': s.id, 'matn': s.matn, 'yaratilgan': s.yaratilgan, 'oqildi': s.oqildi}
            for s in SmsXabar.objects.filter(mijoz=request.user)[:50]
        ],
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def bildirishnoma_oqildi(request):
    pk = request.data.get('id')
    qs = Bildirishnoma.objects.filter(mijoz=request.user, oqildi=False)
    if pk:
        qs = qs.filter(pk=pk)
    soni = qs.update(oqildi=True)
    SmsXabar.objects.filter(mijoz=request.user, oqildi=False).update(oqildi=True)
    return Response({'belgilandi': soni})


# ──────────────────────────────────────────────────────────────
#  8. SHARHLARIM
# ──────────────────────────────────────────────────────────────

@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def sharhlar(request):
    if request.method == 'GET':
        qs = Sharh.objects.filter(mijoz=request.user).select_related('buyurtma')
        baholanmagan = Buyurtma.objects.filter(
            mijoz=request.user, holat='bajarildi', sharh__isnull=True
        )
        return Response({
            'royxat': SharhSerializer(qs, many=True).data,
            'baholanmagan': [
                {'id': b.id, 'xizmat_nomi': b.xizmat_nomi, 'sana': b.natija_sana or b.yaratilgan}
                for b in baholanmagan
            ],
        })

    buyurtma_id = request.data.get('buyurtma')
    b = Buyurtma.objects.filter(mijoz=request.user, pk=buyurtma_id, holat='bajarildi').first()
    if not b:
        return Response({'detail': _('Faqat yakunlangan buyurtmaga sharh qoldiriladi')}, status=400)
    if Sharh.objects.filter(buyurtma=b).exists():
        return Response({'detail': _('Bu buyurtmaga sharh allaqachon qoldirilgan')}, status=400)

    ser = SharhSerializer(data=request.data)
    if not ser.is_valid():
        return Response(ser.errors, status=400)
    ser.save(mijoz=request.user, buyurtma=b)
    return Response(ser.data, status=201)


@api_view(['PATCH', 'DELETE'])
@permission_classes([IsAuthenticated])
def sharh_detal(request, pk):
    s = Sharh.objects.filter(pk=pk, mijoz=request.user).first()
    if not s:
        return Response({'detail': _('Sharh topilmadi')}, status=404)
    if request.method == 'DELETE':
        s.delete()
        return Response({'ochirildi': True})
    ser = SharhSerializer(s, data=request.data, partial=True)
    if not ser.is_valid():
        return Response(ser.errors, status=400)
    ser.save()
    return Response(ser.data)


# ──────────────────────────────────────────────────────────────
#  9. YORDAM MARKAZI
# ──────────────────────────────────────────────────────────────

@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def murojaatlar(request):
    if request.method == 'GET':
        qs = Murojaat.objects.filter(mijoz=request.user).prefetch_related('xabarlar')
        return Response(MurojaatSerializer(qs, many=True).data)

    mavzu = (request.data.get('mavzu') or '').strip()
    matn = (request.data.get('matn') or '').strip()
    if not mavzu or not matn:
        return Response({'detail': _('Mavzu va xabar matni kiritilishi shart')}, status=400)

    m = Murojaat.objects.create(mijoz=request.user, mavzu=mavzu)
    MurojaatXabar.objects.create(murojaat=m, kim='mijoz', matn=matn)
    return Response(MurojaatSerializer(m).data, status=201)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def murojaat_xabar(request, pk):
    m = Murojaat.objects.filter(pk=pk, mijoz=request.user).first()
    if not m:
        return Response({'detail': _('Murojaat topilmadi')}, status=404)
    if m.holat == 'yopiq':
        return Response({'detail': _('Murojaat yopilgan. Yangi murojaat oching.')}, status=400)

    matn = (request.data.get('matn') or '').strip()
    if not matn:
        return Response({'detail': _('Xabar matni bo\'sh')}, status=400)

    x = MurojaatXabar.objects.create(murojaat=m, kim='mijoz', matn=matn)
    m.holat = 'ochiq'
    m.save(update_fields=['holat', 'yangilangan'])
    return Response(MurojaatXabarSerializer(x).data, status=201)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def murojaat_yopish(request, pk):
    m = Murojaat.objects.filter(pk=pk, mijoz=request.user).first()
    if not m:
        return Response({'detail': _('Murojaat topilmadi')}, status=404)
    m.holat = 'yopiq'
    m.save(update_fields=['holat', 'yangilangan'])
    return Response(MurojaatSerializer(m).data)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def faq(request):
    return Response(SavolJavobSerializer(
        SavolJavob.objects.filter(faol=True), many=True
    ).data)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def qongiroq_sorovi(request):
    ser = QongiroqSerializer(data={
        'telefon': request.data.get('telefon') or request.user.telefon,
        'qulay_vaqt': request.data.get('qulay_vaqt', ''),
        'mavzu': request.data.get('mavzu', ''),
    })
    if not ser.is_valid():
        return Response(ser.errors, status=400)
    ser.save(mijoz=request.user)
    _bildirishnoma(
        request.user, "Qo'ng'iroq so'rovi qabul qilindi",
        'Operator ko\'rsatilgan vaqtda siz bilan bog\'lanadi.', bolim='yordam',
    )
    return Response(ser.data, status=201)


# ──────────────────────────────────────────────────────────────
#  10. PROFIL SOZLAMALARI
# ──────────────────────────────────────────────────────────────

@api_view(['GET', 'PATCH'])
@permission_classes([IsAuthenticated])
def sozlamalar(request):
    sozlama, _ = KabinetSozlama.objects.get_or_create(mijoz=request.user)
    if request.method == 'GET':
        return Response(SozlamaSerializer(sozlama).data)
    ser = SozlamaSerializer(sozlama, data=request.data, partial=True)
    if not ser.is_valid():
        return Response(ser.errors, status=400)
    ser.save()
    return Response(ser.data)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def hisobni_ochirish(request):
    """Mijoz o'z hisobini o'chiradi.

    Buyurtma va to'lov tarixi hisobot uchun saqlanadi — shuning uchun yozuv
    o'chirilmaydi, balki hisob nofaol qilinadi va shaxsiy ma'lumot tozalanadi.
    """
    user = request.user
    if user.rol != 'mijoz':
        return Response({'detail': _('Faqat mijoz hisobi uchun')}, status=403)

    tasdiq = (request.data.get('tasdiq') or '').strip().upper()
    if tasdiq != "O'CHIRISH":
        return Response({'detail': _("Tasdiqlash uchun O'CHIRISH so'zini kiriting")}, status=400)

    # Qaytarib bo'lmaydigan amal: faqat so'z emas, telefonga kelgan SMS kod ham kerak
    from apps.auth_app.views import tasdiq_kodini_sarfla
    rad = tasdiq_kodini_sarfla(user, request.data.get('tasdiq_kodi'))
    if rad:
        return rad

    user.holat = 'nofaol'
    user.is_active = False
    user.ism = ''
    user.email = ''
    user.qoshimcha_telefon = ''
    user.manzil = ''
    user.moljal = ''
    user.telefon = f"ochirilgan_{user.id}_{int(timezone.now().timestamp())}"
    user.save()
    return Response({'ochirildi': True})
