from django.conf import settings
from django.core.cache import cache
from django.utils import timezone
from django.db.models import Count, Q
from django.utils.translation import gettext as _
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.auth_app.models import Foydalanuvchi
from apps.sms_app.gateway import sms_yubor
from apps.sms_app.models import SmsXabar
from .models import Buyurtma, BuyurtmaFoto
from .serializers import BuyurtmaSerializer


def _sms_yuborish(mijoz, matn):
    if mijoz:
        SmsXabar.objects.create(mijoz=mijoz, matn=matn)
        sms_yubor(mijoz.telefon, matn)


def _admin_mi(user):
    return getattr(user, 'rol', None) == 'admin'


def _ruxsat_yoq():
    return Response({'detail': _("Bu amal uchun ruxsat yo'q")}, status=403)


@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def buyurtmalar_list(request):
    user = request.user

    if request.method == 'GET':
        qs = Buyurtma.objects.select_related('mijoz', 'xodim')

        if user.rol == 'admin':
            holat = request.query_params.get('holat')
            tuman = request.query_params.get('tuman')
            if holat:
                qs = qs.filter(holat=holat)
            if tuman:
                qs = qs.filter(tuman=tuman)
        elif user.rol == 'xodim':
            holat = request.query_params.get('holat')
            qs = qs.filter(xodim=user)
            if holat:
                qs = qs.filter(holat=holat)
        else:
            qs = qs.filter(mijoz=user)

        ser = BuyurtmaSerializer(qs, many=True)
        return Response(ser.data)

    # POST — mijoz buyurtma beradi
    data = request.data.copy()
    ser = BuyurtmaSerializer(data=data)
    if ser.is_valid():
        obyekt = ser.validated_data.get('obyekt')
        if obyekt and obyekt.mijoz_id != user.id:
            return Response({'detail': _('Obyekt sizga tegishli emas')}, status=403)
        # Manzil/tumanni `Buyurtma.save()` o'zi to'ldiradi: mijoz kiritgan
        # qiymat → obyektniki → profildagisi. Bu yerda ularni MAJBURAN
        # profildagiga tenglash mumkin emas edi: `save(**kwargs)` argumentlari
        # validated_data ustidan yozilib, mijoz ariza uchun kiritgan boshqa
        # manzil jimgina yo'qolardi (ilovadagi manzil maydoni ishlamasdi).
        b = ser.save(mijoz=user)
        _sms_yuborish(user, f"Buyurtmangiz qabul qilindi! #{b.id} — {b.xizmat_nomi}. Tez orada bog'lanamiz.")
        return Response(BuyurtmaSerializer(b).data, status=201)
    return Response(ser.errors, status=400)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def statistika(request):
    # Umumiy biznes statistikasi — faqat admin uchun
    if not _admin_mi(request.user):
        return _ruxsat_yoq()

    # Bu hisobot butun Buyurtma jadvalini skanerlaydi. Raqamlar bir necha
    # daqiqa eskirsa muammo emas, shuning uchun keshlanadi. Kesh muddati
    # settings.STATISTIKA_KESH_SONIYA — umumiy (Redis) kesh yo'q bo'lsa 0,
    # ya'ni keshlash o'chiq (LocMemCache har workerda alohida bo'lgani uchun
    # aks holda har worker turlicha eski raqam ko'rsatardi).
    muddat = getattr(settings, 'STATISTIKA_KESH_SONIYA', 0)
    if muddat:
        keshdan = cache.get('buyurtma_statistika')
        if keshdan is not None:
            return Response(keshdan)

    qs = Buyurtma.objects.all()

    # Beshta son bitta so'rovda (avval 5 ta alohida COUNT edi)
    b_stat = qs.aggregate(
        jami=Count('id'),
        yangi=Count('id', filter=Q(holat='yangi')),
        qabul=Count('id', filter=Q(holat='qabul')),
        jarayonda=Count('id', filter=Q(holat='bajarilmoqda')),
        bajarildi=Count('id', filter=Q(holat='bajarildi')),
    )
    foydalanuvchi_stat = Foydalanuvchi.objects.aggregate(
        xodimlar=Count('id', filter=Q(rol='xodim', holat='faol')),
        mijozlar=Count('id', filter=Q(rol='mijoz')),
    )

    tuman_stat = list(
        qs.values('tuman').annotate(
            jami=Count('id'),
            bajarildi=Count('id', filter=Q(holat='bajarildi'))
        ).order_by('-jami')
    )

    # Har xodim uchun alohida COUNT o'rniga bitta annotate'li so'rov
    xodim_stat = [
        {
            'id': x['id'],
            'ism': x['ism'] or x['telefon'],
            'tuman': x['tuman'],
            'ishlari': x['ishlari'],
        }
        for x in Foydalanuvchi.objects.filter(rol='xodim').annotate(
            ishlari=Count('xodim_buyurtmalari',
                          filter=Q(xodim_buyurtmalari__holat='bajarildi'))
        ).order_by('-ishlari').values('id', 'ism', 'telefon', 'tuman', 'ishlari')
    ]

    natija = {
        'jami': b_stat['jami'],
        'yangi': b_stat['yangi'],
        'qabul': b_stat['qabul'],
        'jarayonda': b_stat['jarayonda'],
        'bajarildi': b_stat['bajarildi'],
        'xodimlar_soni': foydalanuvchi_stat['xodimlar'],
        'mijozlar_soni': foydalanuvchi_stat['mijozlar'],
        'tuman_stat': tuman_stat,
        'xodim_stat': xodim_stat,
    }
    if muddat:
        cache.set('buyurtma_statistika', natija, muddat)
    return Response(natija)


@api_view(['POST', 'PATCH'])
@permission_classes([IsAuthenticated])
def buyurtma_update(request, pk):
    try:
        b = Buyurtma.objects.get(pk=pk)
    except Buyurtma.DoesNotExist:
        return Response({'detail': _('Topilmadi')}, status=404)

    # Holatni admin yoki shu buyurtmaga tayinlangan xodim o'zgartiradi.
    # Mijoz faqat o'z buyurtmasini bekor qila oladi.
    user = request.user
    holat = request.data.get('holat')
    if not (_admin_mi(user) or b.xodim_id == user.id):
        if not (b.mijoz_id == user.id and holat == 'bekor'):
            return _ruxsat_yoq()
        if b.holat in ('bajarildi', 'bekor'):
            return Response({'detail': _('Bu buyurtmani bekor qilib bo\'lmaydi')}, status=400)

    if holat:
        b.holat = holat
        b.save()
    return Response(BuyurtmaSerializer(b).data)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def tayinlash(request, pk):
    # Xodim tayinlash — faqat admin
    if not _admin_mi(request.user):
        return _ruxsat_yoq()
    try:
        b = Buyurtma.objects.get(pk=pk)
    except Buyurtma.DoesNotExist:
        return Response({'detail': _('Buyurtma topilmadi')}, status=404)

    xodim_id = request.data.get('xodim_id')
    try:
        xodim = Foydalanuvchi.objects.get(pk=xodim_id, rol='xodim')
    except Foydalanuvchi.DoesNotExist:
        return Response({'detail': _('Xodim topilmadi')}, status=404)

    b.xodim = xodim
    b.holat = 'yangi'
    b.save()

    _sms_yuborish(xodim, f"Sizga yangi buyurtma tayinlandi! #{b.id} — {b.xizmat_nomi}. Manzil: {b.manzil or b.tuman}")
    _sms_yuborish(b.mijoz, f"#{b.id} buyurtmangizga xodim tayinlandi: {xodim.ism}. Tez orada siz bilan bog'lanadi.")

    return Response(BuyurtmaSerializer(b).data)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def qabul(request, pk):
    try:
        b = Buyurtma.objects.get(pk=pk, xodim=request.user)
    except Buyurtma.DoesNotExist:
        return Response({'detail': _('Buyurtma topilmadi')}, status=404)

    b.holat = 'qabul'
    b.save()
    _sms_yuborish(b.mijoz, f"#{b.id} buyurtmangiz xodim tomonidan qabul qilindi. Tez orada borishadi.")
    return Response(BuyurtmaSerializer(b).data)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def natija(request, pk):
    try:
        b = Buyurtma.objects.get(pk=pk, xodim=request.user)
    except Buyurtma.DoesNotExist:
        return Response({'detail': _('Buyurtma topilmadi')}, status=404)

    b.natija = request.data.get('natija', '')
    b.natija_soat = request.data.get('natija_soat') or None
    b.material = request.data.get('material', '')
    holat = request.data.get('holat', 'bajarildi')
    b.holat = holat
    b.natija_sana = timezone.now()
    b.save()

    if holat == 'bajarildi':
        _sms_yuborish(b.mijoz, f"#{b.id} buyurtmangiz bajarildi! ✓ Natija: {b.natija[:80] if b.natija else '—'}")

    return Response(BuyurtmaSerializer(b).data)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def foto_yuklash(request, pk):
    try:
        b = Buyurtma.objects.get(pk=pk)
    except Buyurtma.DoesNotExist:
        return Response({'detail': _('Buyurtma topilmadi')}, status=404)

    # Rasmni admin, tayinlangan xodim yoki buyurtma egasi yuklaydi
    user = request.user
    if not (_admin_mi(user) or b.xodim_id == user.id or b.mijoz_id == user.id):
        return _ruxsat_yoq()

    rasmlar = request.FILES.getlist('rasmlar')
    if not rasmlar:
        return Response({'detail': _('Rasm tanlanmadi')}, status=400)

    tur = request.data.get('tur', 'ish')
    fotolar = [BuyurtmaFoto(buyurtma=b, rasm=r, tur=tur) for r in rasmlar]
    BuyurtmaFoto.objects.bulk_create(fotolar)
    return Response({'yuklandi': len(rasmlar)})
