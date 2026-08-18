from django.conf import settings
from django.core.cache import cache
from django.db import transaction
from django.db.models import Count, F, Q, Sum
from django.utils import timezone
from django.utils.translation import gettext as _
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from apps.auth_app.models import Foydalanuvchi
from apps.sms_app.gateway import sms_yubor
from apps.sms_app.models import SmsXabar
from apps.tolovlar.models import TolovSorovi
from apps.tolovlar.views import _tolov_url

from .hisob import hisobla, narx_qoidalari, bolib_hisobla
from .models import Xarid, XaridQatori, Promokod, ONLAYN_USULLAR
from .tolov import tolov_sorovi_yarat, tolov_url, sozlanganmi
from .serializers import (XaridSerializer, XaridKirishSerializer,
                          HOLATLAR, TOLOV_USULLARI, MUAMMOLAR)


def _telefon_raqamlari(telefon):
    return ''.join(ch for ch in (telefon or '') if ch.isdigit())


def _sms_yuborish(telefon, matn):
    """Ro'yxatdan o'tgan mijozga SMS saqlaymiz, aks holda faqat log."""
    mijoz = Foydalanuvchi.objects.filter(telefon=telefon).first()
    if mijoz:
        SmsXabar.objects.create(mijoz=mijoz, matn=matn)
    sms_yubor(telefon, matn)


def _admin_mi(user):
    return user.is_authenticated and getattr(user, 'rol', None) == 'admin'


# ──────────────────────────────────────────────────────────────
#  POST /api/xaridlar/   — buyurtma yaratish (ochiq: mehmon xaridi)
#  GET  /api/xaridlar/   — ?telefon= bo'yicha qidiruv (token talab qilinadi:
#                          o'z raqami yoki admin), filtrsiz to'liq ro'yxat
#                          faqat admin uchun
# ──────────────────────────────────────────────────────────────
@api_view(['GET', 'POST'])
@permission_classes([AllowAny])
def xaridlar_list(request):
    if request.method == 'GET':
        telefon = request.query_params.get('telefon')
        qs = Xarid.objects.prefetch_related('qatorlar')

        if telefon:
            # Ilgari bu shox ochiq edi: raqamni bilgan har kim o'sha odamning
            # ismi, manzili va xaridlarini ko'ra olardi. Endi so'rovchi o'zini
            # tanitishi va faqat O'Z raqamini so'rashi kerak.
            if not request.user.is_authenticated:
                return Response(
                    {'detail': _('Buyurtmalarni ko\'rish uchun tizimga kiring')},
                    status=401,
                )
            raqamlar = _telefon_raqamlari(telefon)
            if not raqamlar:
                return Response([])
            if not _admin_mi(request.user) and \
                    raqamlar != _telefon_raqamlari(request.user.telefon):
                return Response({'detail': _("Ruxsat yo'q")}, status=403)
            # Telefon turli formatlarda saqlanishi mumkin — raqamlar bo'yicha solishtiramiz
            qs = [x for x in qs if raqamlar in _telefon_raqamlari(x.telefon)]
        elif _admin_mi(request.user):
            holat = request.query_params.get('holat')
            if holat:
                qs = qs.filter(holat=holat)
        else:
            return Response({'detail': _("Ruxsat yo'q")}, status=403)

        return Response(XaridSerializer(qs, many=True).data)

    # ── POST ──
    ser = XaridKirishSerializer(data=request.data)
    if not ser.is_valid():
        return Response(ser.errors, status=400)
    d = ser.validated_data

    mijoz_d = d['customer']
    yetkazish_d = d.get('delivery') or {}
    tolov_d = d.get('payment') or {}
    ornatish = d.get('installService', False)
    yetkazish = yetkazish_d.get('method', 'kuryer')
    tolov_usuli = tolov_d.get('method', 'naqd')
    bolib_oy = int(tolov_d.get('months') or 0)

    # Summa har doim server tomonda hisoblanadi (mijoz yuborgan `total`ga ishonmaymiz)
    tuman = yetkazish_d.get('region', '') or ''
    summa, promo, promo_xato = hisobla(
        d['items'], yetkazish=yetkazish, ornatish=ornatish,
        kod=d.get('promo', ''), tuman=tuman
    )
    # Promokod yaroqsiz bo'lsa buyurtmani to'xtatamiz — mijoz kutgan narx o'zgarib ketmasin
    if d.get('promo') and promo_xato:
        return Response({'detail': promo_xato, 'maydon': 'promo'}, status=400)

    # ── Bo'lib to'lash: ustama qo'shiladi, oylik to'lov hisoblanadi ──
    oylik_tolov = 0
    if tolov_usuli == 'bolib':
        umumiy, oylik_tolov, bolib_xato = bolib_hisobla(summa['jami'], bolib_oy)
        if bolib_xato:
            return Response({'detail': bolib_xato, 'maydon': 'bolib'}, status=400)
        summa['jami'] = umumiy
    else:
        bolib_oy = 0

    telefon = mijoz_d['phone']
    mijoz = Foydalanuvchi.objects.filter(telefon=telefon).first()

    with transaction.atomic():
        xarid = Xarid.objects.create(
            mijoz=mijoz,
            ism=mijoz_d['name'],
            telefon=telefon,
            manzil=mijoz_d.get('address', '') or '',
            yetkazish=yetkazish,
            yetkazish_izohi=yetkazish_d.get('note', '') or '',
            yetkazish_vaqti=yetkazish_d.get('time', '') or '',
            tuman=tuman or (mijoz.tuman if mijoz else ''),
            yetkazish_muddati=summa['yetkazish_muddati'],
            tolov_usuli=tolov_usuli,
            bolib_oy=bolib_oy,
            oylik_tolov=oylik_tolov,
            tolov_holati='' if tolov_usuli == 'naqd' else 'kutilmoqda',
            ornatish_xizmati=ornatish,
            mahsulotlar_summasi=summa['mahsulotlar'],
            chegirma=summa['chegirma'],
            promokod=summa['promokod'],
            yetkazish_narxi=summa['yetkazish_narxi'],
            ornatish_narxi=summa['ornatish_narxi'],
            jami=summa['jami'],
        )
        XaridQatori.objects.bulk_create([
            XaridQatori(
                xarid=xarid, mahsulot_id=q['productId'], slug=q['slug'],
                nomi=q['name'], narx=q['price'], miqdor=q['qty'],
                rasm=q.get('image', '') or '',
            )
            for q in d['items']
        ])
        if promo:
            # Bir vaqtda kelgan so'rovlarda limit oshib ketmasligi uchun atomik o'sish
            Promokod.objects.filter(pk=promo.pk).update(ishlatilgan=F('ishlatilgan') + 1)

    # Onlayn to'lov yoki bo'lib to'lash uchun TolovSorovi yaratamiz
    if xarid.tolov_usuli != 'naqd':
        tolov_sorovi_yarat(xarid)

    javob = XaridSerializer(xarid).data
    if xarid.tolov_usuli in ONLAYN_USULLAR:
        javob['payment']['url'] = tolov_url(xarid)
        javob['payment']['configured'] = sozlanganmi(xarid.tolov_usuli)

    # Buyurtma qabul qilingani haqidagi SMS signal orqali yuboriladi (signals.py)
    return Response(javob, status=201)


# ──────────────────────────────────────────────────────────────
#  POST /api/xaridlar/promokod/  — savatdagi summa uchun kodni tekshirish (ochiq)
#  Bu faqat oldindan ko'rsatish uchun; yakuniy hisob buyurtma yaratishda qayta bajariladi.
# ──────────────────────────────────────────────────────────────
@api_view(['POST'])
@permission_classes([AllowAny])
def promokod_tekshir(request):
    kod = (request.data.get('kod') or '').strip()
    if not kod:
        return Response({'detail': _('Promokod kiriting')}, status=400)

    qatorlar = request.data.get('items') or []
    try:
        qatorlar = [{'price': int(q.get('price', 0)), 'qty': int(q.get('qty', 0))} for q in qatorlar]
    except (TypeError, ValueError):
        return Response({'detail': _("Savat ma'lumoti noto'g'ri")}, status=400)
    if not qatorlar:
        return Response({'detail': _("Savat bo'sh")}, status=400)

    summa, promo, xato = hisobla(
        qatorlar,
        yetkazish=request.data.get('delivery') or 'kuryer',
        ornatish=bool(request.data.get('installService')),
        kod=kod,
    )
    if xato:
        return Response({'detail': xato}, status=400)

    return Response({
        'kod': promo.kod,
        'tavsif': promo.tavsif,
        'chegirma': summa['chegirma'],
        'totals': {
            'items': summa['mahsulotlar'],
            'discount': summa['chegirma'],
            'delivery': summa['yetkazish_narxi'],
            'install': summa['ornatish_narxi'],
            'grand': summa['jami'],
        },
    })


# ──────────────────────────────────────────────────────────────
#  GET  /api/xaridlar/<raqam>/tolov/  — joriy to'lov holati va havolasi
#  POST /api/xaridlar/<raqam>/tolov/  — qayta urinish yoki boshqa usulga o'tish
#
#  To'lov amalga oshmasa mijoz buyurtmani qaytadan yaratmaydi — shu endpoint
#  yangi to'lov so'rovi ochadi yoki to'lov usulini almashtiradi.
# ──────────────────────────────────────────────────────────────
@api_view(['GET', 'POST'])
@permission_classes([AllowAny])
def tolov_boshqarish(request, raqam):
    try:
        xarid = Xarid.objects.get(raqam=raqam)
    except Xarid.DoesNotExist:
        return Response({'detail': _('Buyurtma topilmadi')}, status=404)

    if request.method == 'GET':
        return Response({
            'method': xarid.tolov_usuli,
            'paid': xarid.tolandi,
            'state': xarid.tolov_holati,
            'attempts': xarid.tolov_urinishlari,
            'amount': xarid.jami,
            'url': tolov_url(xarid),
            'configured': sozlanganmi(xarid.tolov_usuli),
        })

    # ── POST: qayta urinish / usulni almashtirish ──
    if xarid.tolandi:
        return Response({'detail': _("Bu buyurtma allaqachon to'langan")}, status=400)
    if xarid.holat == 'bekor':
        return Response({'detail': _('Bekor qilingan buyurtmani to\'lab bo\'lmaydi')}, status=400)

    yangi_usul = request.data.get('method') or xarid.tolov_usuli
    if yangi_usul not in TOLOV_USULLARI:
        return Response({'detail': _("Bunday to'lov usuli yo'q")}, status=400)

    eski_jami = xarid.jami
    bolib_oy, oylik = 0, 0

    if yangi_usul == 'bolib':
        # Bo'lib to'lashga o'tishda ustama ustidan ustama qo'shilmasligi kerak —
        # har doim ustamasiz asosiy summadan hisoblaymiz
        asos = (xarid.mahsulotlar_summasi - xarid.chegirma
                + xarid.yetkazish_narxi + xarid.ornatish_narxi)
        umumiy, oylik, xato = bolib_hisobla(asos, int(request.data.get('months') or 0))
        if xato:
            return Response({'detail': xato, 'maydon': 'bolib'}, status=400)
        bolib_oy = int(request.data.get('months'))
        xarid.jami = umumiy
    elif xarid.tolov_usuli == 'bolib':
        # Bo'lib to'lashdan qaytishda ustamani olib tashlaymiz
        xarid.jami = (xarid.mahsulotlar_summasi - xarid.chegirma
                      + xarid.yetkazish_narxi + xarid.ornatish_narxi)

    xarid.tolov_usuli = yangi_usul
    xarid.bolib_oy = bolib_oy
    xarid.oylik_tolov = oylik
    xarid.save(update_fields=['tolov_usuli', 'bolib_oy', 'oylik_tolov', 'jami', 'yangilangan'])

    if yangi_usul == 'naqd':
        xarid.tolov_holati = ''
        xarid.save(update_fields=['tolov_holati', 'yangilangan'])
        _sms_yuborish(xarid.telefon,
                      f"SOAR GAZ: {xarid.raqam} buyurtmangiz to'lov usuli naqd (yetkazishda) ga o'zgartirildi.")
    else:
        tolov_sorovi_yarat(xarid)

    javob = {
        'method': xarid.tolov_usuli,
        'amount': xarid.jami,
        'attempts': xarid.tolov_urinishlari,
        'url': tolov_url(xarid),
        'configured': sozlanganmi(xarid.tolov_usuli),
    }
    if xarid.bolib_oy:
        javob['months'] = xarid.bolib_oy
        javob['monthly'] = xarid.oylik_tolov
    if xarid.jami != eski_jami:
        javob['amount_changed'] = True
    return Response(javob)


# ──────────────────────────────────────────────────────────────
#  GET /api/xaridlar/narxlar/  — frontend uchun narx qoidalari (ochiq)
# ──────────────────────────────────────────────────────────────
@api_view(['GET'])
@permission_classes([AllowAny])
def narxlar(request):
    return Response(narx_qoidalari())


# ──────────────────────────────────────────────────────────────
#  GET   /api/xaridlar/<raqam>/  — buyurtma holati (ochiq, raqam bo'yicha)
#  PATCH /api/xaridlar/<raqam>/  — holatni o'zgartirish (admin)
# ──────────────────────────────────────────────────────────────
@api_view(['GET', 'PATCH'])
@permission_classes([AllowAny])
def xarid_detail(request, raqam):
    try:
        xarid = Xarid.objects.prefetch_related('qatorlar').get(raqam=raqam)
    except Xarid.DoesNotExist:
        return Response({'detail': _('Topilmadi')}, status=404)

    if request.method == 'GET':
        return Response(XaridSerializer(xarid).data)

    if not _admin_mi(request.user):
        return Response({'detail': _("Ruxsat yo'q")}, status=403)

    holat = request.data.get('status') or request.data.get('holat')
    if holat not in HOLATLAR:
        return Response({'detail': _("Noto'g'ri holat")}, status=400)

    xarid.holat = holat
    xarid.save(update_fields=['holat', 'yangilangan'])
    # Mijozga SMS signal orqali ketadi (signals.py) — admin panelidan
    # o'zgartirilganda ham bir xil ishlashi uchun
    return Response(XaridSerializer(xarid).data)


# ══════════════════════════════════════════════════════════════
#  KURYER INTERFEYSI (xodim roli)
# ══════════════════════════════════════════════════════════════
def _kuryer_mi(user):
    return user.is_authenticated and getattr(user, 'rol', None) in ('admin', 'xodim')


# ──────────────────────────────────────────────────────────────
#  GET /api/xaridlar/kuryer/  — kuryerning ish ro'yxati
#  ?bosh=1  — hali hech kimga biriktirilmagan, o'z tumanidagi buyurtmalar
# ──────────────────────────────────────────────────────────────
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def kuryer_royxati(request):
    if not _kuryer_mi(request.user):
        return Response({'detail': _("Ruxsat yo'q")}, status=403)

    qs = Xarid.objects.prefetch_related('qatorlar').filter(yetkazish='kuryer')

    if request.query_params.get('bosh'):
        # Bo'sh buyurtmalar: kuryer biriktirilmagan va tayyor/jo'natilgan
        qs = qs.filter(kuryer__isnull=True, holat__in=['tayyorlanmoqda', 'jonatildi'])
        if getattr(request.user, 'tuman', ''):
            qs = qs.filter(tuman=request.user.tuman)
    else:
        # O'ziga biriktirilgan, hali yakunlanmaganlari
        qs = qs.filter(kuryer=request.user).exclude(holat__in=['yetkazildi', 'bekor'])

    return Response(XaridSerializer(qs, many=True).data)


# ──────────────────────────────────────────────────────────────
#  POST /api/xaridlar/<raqam>/qabul/  — kuryer buyurtmani o'ziga oladi
# ──────────────────────────────────────────────────────────────
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def kuryer_qabul(request, raqam):
    if not _kuryer_mi(request.user):
        return Response({'detail': _("Ruxsat yo'q")}, status=403)
    try:
        xarid = Xarid.objects.get(raqam=raqam)
    except Xarid.DoesNotExist:
        return Response({'detail': _('Buyurtma topilmadi')}, status=404)

    if xarid.kuryer and xarid.kuryer_id != request.user.id:
        return Response({'detail': _('Bu buyurtmani boshqa kuryer olgan')}, status=409)
    if xarid.holat in ('yetkazildi', 'bekor'):
        return Response({'detail': _('Buyurtma yakunlangan')}, status=400)

    xarid.kuryer = request.user
    if xarid.holat in ('tasdiqlandi', 'tayyorlanmoqda'):
        xarid.holat = 'jonatildi'
    xarid.save(update_fields=['kuryer', 'holat', 'yangilangan'])
    return Response(XaridSerializer(xarid).data)


# ──────────────────────────────────────────────────────────────
#  POST /api/xaridlar/<raqam>/holat/  — kuryer holatni yangilaydi
#  Kuryer faqat o'z buyurtmasini va faqat ruxsat etilgan holatlarga o'tkazadi
# ──────────────────────────────────────────────────────────────
KURYER_RUXSAT = {'jonatildi', 'yolda', 'yetkazildi'}


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def kuryer_holat(request, raqam):
    if not _kuryer_mi(request.user):
        return Response({'detail': _("Ruxsat yo'q")}, status=403)
    try:
        xarid = Xarid.objects.get(raqam=raqam)
    except Xarid.DoesNotExist:
        return Response({'detail': _('Buyurtma topilmadi')}, status=404)

    if xarid.kuryer_id != request.user.id and getattr(request.user, 'rol', '') != 'admin':
        return Response({'detail': _('Bu buyurtma sizga biriktirilmagan')}, status=403)

    holat = request.data.get('holat')
    if holat not in KURYER_RUXSAT:
        return Response({'detail': _("Kuryer bu holatga o'tkaza olmaydi")}, status=400)

    xarid.holat = holat
    # Yetkazib berilgach muammo belgisi tozalanadi
    if holat == 'yetkazildi':
        xarid.muammo = ''
        # Naqd to'lov yetkazishda qabul qilinadi
        if xarid.tolov_usuli == 'naqd':
            xarid.tolandi = True
            xarid.tolov_holati = 'tolandi'
    xarid.save(update_fields=['holat', 'muammo', 'tolandi', 'tolov_holati', 'yangilangan'])
    return Response(XaridSerializer(xarid).data)


# ──────────────────────────────────────────────────────────────
#  POST /api/xaridlar/<raqam>/muammo/  — yetkazib bo'lmadi
#
#  Kuryer sababni belgilaydi, buyurtma "muammo" holatiga o'tadi va
#  mijozga sababga mos SMS ketadi. Urinishlar soni limitdan oshsa —
#  operator aralashuvi kerakligi qaytariladi.
# ──────────────────────────────────────────────────────────────
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def yetkazish_muammosi(request, raqam):
    if not _kuryer_mi(request.user):
        return Response({'detail': _("Ruxsat yo'q")}, status=403)
    try:
        xarid = Xarid.objects.get(raqam=raqam)
    except Xarid.DoesNotExist:
        return Response({'detail': _('Buyurtma topilmadi')}, status=404)

    if xarid.kuryer_id != request.user.id and getattr(request.user, 'rol', '') != 'admin':
        return Response({'detail': _('Bu buyurtma sizga biriktirilmagan')}, status=403)
    if xarid.holat in ('yetkazildi', 'bekor'):
        return Response({'detail': _('Buyurtma yakunlangan')}, status=400)

    sabab = request.data.get('sabab')
    if sabab not in MUAMMOLAR:
        return Response({'detail': _("Sababni tanlang")}, status=400)

    xarid.muammo = sabab
    xarid.muammo_izohi = (request.data.get('izoh') or '')[:500]
    xarid.muammo_vaqti = timezone.now()
    xarid.urinish_soni = xarid.urinish_soni + 1
    xarid.holat = 'muammo'
    xarid.save(update_fields=['muammo', 'muammo_izohi', 'muammo_vaqti',
                              'urinish_soni', 'holat', 'yangilangan'])

    limit = narx_qoidalari()['urinishlar']
    return Response({
        'raqam': xarid.raqam,
        'holat': xarid.holat,
        'muammo': xarid.muammo,
        'urinish_soni': xarid.urinish_soni,
        'limit': limit,
        # Limit tugasa operator qaror qabul qilishi kerak
        'operator_kerak': xarid.urinish_soni >= limit,
    })


# ──────────────────────────────────────────────────────────────
#  POST /api/xaridlar/<raqam>/qayta/  — qayta yetkazishni so'rash
#  Mijoz ham (ochiq), operator ham chaqira oladi.
# ──────────────────────────────────────────────────────────────
@api_view(['POST'])
@permission_classes([AllowAny])
def qayta_yetkazish(request, raqam):
    try:
        xarid = Xarid.objects.get(raqam=raqam)
    except Xarid.DoesNotExist:
        return Response({'detail': _('Buyurtma topilmadi')}, status=404)

    if xarid.holat != 'muammo':
        return Response({'detail': _("Bu buyurtma qayta yetkazishni kutmayapti")}, status=400)

    limit = narx_qoidalari()['urinishlar']
    if xarid.urinish_soni >= limit and not _admin_mi(request.user):
        return Response({
            'detail': _("%(limit)s marta urinib ko'rildi. Iltimos, operator "
                        "bilan bog'laning.") % {'limit': limit},
            'operator_kerak': True,
        }, status=400)

    # Mijoz yangi vaqt yoki aniqlashtirilgan manzil bergan bo'lsa yozib qo'yamiz
    vaqt = (request.data.get('time') or '').strip()
    manzil = (request.data.get('address') or '').strip()
    maydonlar = ['holat', 'muammo', 'yangilangan']
    if vaqt:
        xarid.yetkazish_vaqti = vaqt
        maydonlar.append('yetkazish_vaqti')
    if manzil:
        xarid.manzil = manzil
        maydonlar.append('manzil')

    xarid.holat = 'jonatildi'
    xarid.muammo = ''
    xarid.save(update_fields=maydonlar)

    _sms_yuborish(xarid.telefon,
                  f"SOAR GAZ: {xarid.raqam} — qayta yetkazish rasmiylashtirildi. "
                  f"Kuryer tez orada yo'lga chiqadi.")
    return Response(XaridSerializer(xarid).data)


# ──────────────────────────────────────────────────────────────
#  POST /api/xaridlar/<raqam>/kuryer/  — kuryer joylashuvini yangilash
#
#  Kuryer telefonidagi ilova (yoki brauzer sahifasi) shu endpointga
#  koordinatalarini yuboradi. Faqat xodim yoki admin chaqira oladi.
# ──────────────────────────────────────────────────────────────
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def kuryer_joylashuvi(request, raqam):
    rol = getattr(request.user, 'rol', None)
    if rol not in ('admin', 'xodim'):
        return Response({'detail': _("Ruxsat yo'q")}, status=403)

    try:
        xarid = Xarid.objects.get(raqam=raqam)
    except Xarid.DoesNotExist:
        return Response({'detail': _('Buyurtma topilmadi')}, status=404)

    try:
        lat = float(request.data.get('lat'))
        lng = float(request.data.get('lng'))
    except (TypeError, ValueError):
        return Response({'detail': _("lat va lng to'g'ri son bo'lishi kerak")}, status=400)
    if not (-90 <= lat <= 90) or not (-180 <= lng <= 180):
        return Response({'detail': _("Koordinata chegaradan tashqarida")}, status=400)

    xarid.kuryer_lat = lat
    xarid.kuryer_lng = lng
    xarid.kuryer_yangilangan = timezone.now()
    if not xarid.kuryer:
        xarid.kuryer = request.user
    # Birinchi joylashuv kelganda buyurtma avtomatik "yo'lda" ga o'tadi
    if xarid.holat == 'jonatildi':
        xarid.holat = 'yolda'
    xarid.save(update_fields=['kuryer_lat', 'kuryer_lng', 'kuryer_yangilangan',
                              'kuryer', 'holat', 'yangilangan'])

    return Response({
        'raqam': xarid.raqam, 'holat': xarid.holat,
        'lat': lat, 'lng': lng, 'yangilangan': xarid.kuryer_yangilangan,
    })


# ──────────────────────────────────────────────────────────────
#  GET /api/xaridlar/statistika/  — admin uchun qisqa hisobot
# ──────────────────────────────────────────────────────────────
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def statistika(request):
    if not _admin_mi(request.user):
        return Response({'detail': _("Ruxsat yo'q")}, status=403)

    # Butun Xarid jadvalini skanerlaydigan hisobot — keshlanadi.
    # Muddat 0 bo'lsa (umumiy kesh sozlanmagan) har safar qaytadan hisoblanadi.
    muddat = getattr(settings, 'STATISTIKA_KESH_SONIYA', 0)
    if muddat:
        keshdan = cache.get('xarid_statistika')
        if keshdan is not None:
            return Response(keshdan)

    # Avval har holat uchun alohida COUNT (8 ta) va tushum uchun barcha
    # qatorlarni Python'ga tortish bor edi — hammasi bitta so'rovga yig'ildi.
    # DIQQAT: taxallus `jami` deb atalmaydi — modelda `jami` degan maydon bor
    # va u holda Sum('jami') maydonni emas, taxallusni ko'rsatib xato beradi.
    stat = Xarid.objects.aggregate(
        buyurtma_soni=Count('id'),
        tolangan=Count('id', filter=Q(tolandi=True)),
        tushum=Sum('jami', filter=Q(holat='yetkazildi')),
        **{f'holat_{kod}': Count('id', filter=Q(holat=kod)) for kod in HOLATLAR},
    )

    natija = {
        'jami': stat['buyurtma_soni'],
        'holatlar': {kod: stat[f'holat_{kod}'] for kod in HOLATLAR},
        'tolangan': stat['tolangan'],
        'tushum': stat['tushum'] or 0,
    }
    if muddat:
        cache.set('xarid_statistika', natija, muddat)
    return Response(natija)
