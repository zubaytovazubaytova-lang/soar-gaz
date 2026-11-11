import base64
import hashlib
from urllib.parse import urlencode

from django.conf import settings
from django.db import transaction
from django.utils.translation import gettext as _
from rest_framework.decorators import api_view, permission_classes, throttle_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from apps.auth_app.models import Foydalanuvchi
from apps.sms_app.gateway import sms_yubor
from apps.sms_app.models import SmsXabar
from rest_framework.throttling import AnonRateThrottle

import hmac

from .models import TolovSorovi, MahsulotSorovi, MetrologiyaArizasi
from .payme import payme_endpoint  # noqa: F401  (urls.py views.payme_endpoint ni ishlatadi)
from .serializers import (TolovSoroviSerializer, MahsulotSoroviSerializer,
                          MetrologiyaArizasiSerializer)


# ──────────────────────────────────────────────────────────────
#  Yordamchi funksiyalar
# ──────────────────────────────────────────────────────────────
def _sms_yuborish(telefon, matn):
    """Telefon raqami ro'yxatdan o'tgan bo'lsa SMS saqlaymiz, aks holda log."""
    mijoz = Foydalanuvchi.objects.filter(telefon=telefon).first()
    if mijoz:
        SmsXabar.objects.create(mijoz=mijoz, matn=matn)
    sms_yubor(telefon, matn)


def click_url(sorov):
    """Click checkout redirect havolasi (merchant kalitlaridan quriladi)."""
    sid = getattr(settings, 'CLICK_SERVICE_ID', '')
    mid = getattr(settings, 'CLICK_MERCHANT_ID', '')
    params = {
        'service_id': sid,
        'merchant_id': mid,
        'amount': sorov.summa,
        'transaction_param': sorov.id,
    }
    ret = getattr(settings, 'TOLOV_RETURN_URL', '')
    if ret:
        params['return_url'] = ret
    return 'https://my.click.uz/services/pay?' + urlencode(params)


def payme_url(sorov):
    """Payme checkout redirect havolasi (base64 kodlangan)."""
    mid = getattr(settings, 'PAYME_MERCHANT_ID', '')
    # Payme summani tiyinda kutadi (1 so'm = 100 tiyin)
    raw = f"m={mid};ac.order_id={sorov.id};a={sorov.summa * 100}"
    b64 = base64.b64encode(raw.encode()).decode()
    return 'https://checkout.paycom.uz/' + b64


def _tolov_url(sorov):
    if sorov.tolov_tizimi == 'click':
        return click_url(sorov)
    if sorov.tolov_tizimi == 'payme':
        return payme_url(sorov)
    if sorov.tolov_tizimi == 'apelsin':
        # Apelsin universal havola (merchant paneli orqali sozlanadi)
        return f"https://apelsin.uz/pay?order_id={sorov.id}&amount={sorov.summa}"
    return ''


# ──────────────────────────────────────────────────────────────
#  Public: to'lov / hisob-faktura so'rovi yaratish
# ──────────────────────────────────────────────────────────────
@api_view(['POST'])
@permission_classes([AllowAny])
def sorov_yaratish(request):
    ser = TolovSoroviSerializer(data=request.data)
    if not ser.is_valid():
        return Response(ser.errors, status=400)
    sorov = ser.save()

    if sorov.tolov_turi == 'online':
        sorov.holat = 'kutilmoqda'
        sorov.save(update_fields=['holat'])

    _sms_yuborish(
        sorov.telefon,
        f"SOAR GAZ: so'rovingiz qabul qilindi! #{sorov.id} — {sorov.tolov_turi_nomi}. "
        f"Tez orada bog'lanamiz."
    )

    data = TolovSoroviSerializer(sorov).data
    data['tolov_url'] = _tolov_url(sorov)
    return Response(data, status=201)


# ──────────────────────────────────────────────────────────────
#  Admin: so'rovlar ro'yxati va holat o'zgartirish
# ──────────────────────────────────────────────────────────────
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def tolovlar_list(request):
    if getattr(request.user, 'rol', None) != 'admin':
        return Response({'detail': _('Ruxsat yo\'q')}, status=403)
    qs = TolovSorovi.objects.all()
    holat = request.query_params.get('holat')
    turi = request.query_params.get('tolov_turi')
    if holat:
        qs = qs.filter(holat=holat)
    if turi:
        qs = qs.filter(tolov_turi=turi)
    return Response(TolovSoroviSerializer(qs, many=True).data)


@api_view(['PATCH'])
@permission_classes([IsAuthenticated])
def sorov_update(request, pk):
    if getattr(request.user, 'rol', None) != 'admin':
        return Response({'detail': _('Ruxsat yo\'q')}, status=403)
    try:
        sorov = TolovSorovi.objects.get(pk=pk)
    except TolovSorovi.DoesNotExist:
        return Response({'detail': _('Topilmadi')}, status=404)
    holat = request.data.get('holat')
    if holat:
        sorov.holat = holat
        sorov.save(update_fields=['holat', 'yangilangan'])
    return Response(TolovSoroviSerializer(sorov).data)


# ──────────────────────────────────────────────────────────────
#  Public: mahsulot (katalog jihozi) bo'yicha so'rov
# ──────────────────────────────────────────────────────────────
@api_view(['POST'])
@permission_classes([AllowAny])
def mahsulot_sorov_yaratish(request):
    ser = MahsulotSoroviSerializer(data=request.data)
    if not ser.is_valid():
        return Response(ser.errors, status=400)
    sorov = ser.save()
    _sms_yuborish(
        sorov.telefon,
        f"SOAR GAZ: '{sorov.mahsulot}' bo'yicha so'rovingiz #{sorov.id} qabul qilindi! "
        f"Tez orada narx va shartlar bilan bog'lanamiz."
    )
    return Response(MahsulotSoroviSerializer(sorov).data, status=201)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def mahsulot_sorovlar_list(request):
    if getattr(request.user, 'rol', None) != 'admin':
        return Response({'detail': _('Ruxsat yo\'q')}, status=403)
    qs = MahsulotSorovi.objects.all()
    holat = request.query_params.get('holat')
    katalog = request.query_params.get('katalog')
    if holat:
        qs = qs.filter(holat=holat)
    if katalog:
        qs = qs.filter(katalog=katalog)
    return Response(MahsulotSoroviSerializer(qs, many=True).data)


@api_view(['PATCH'])
@permission_classes([IsAuthenticated])
def mahsulot_sorov_update(request, pk):
    if getattr(request.user, 'rol', None) != 'admin':
        return Response({'detail': _('Ruxsat yo\'q')}, status=403)
    try:
        sorov = MahsulotSorovi.objects.get(pk=pk)
    except MahsulotSorovi.DoesNotExist:
        return Response({'detail': _('Topilmadi')}, status=404)
    holat = request.data.get('holat')
    if holat:
        sorov.holat = holat
        sorov.save(update_fields=['holat', 'yangilangan'])
    return Response(MahsulotSoroviSerializer(sorov).data)


# ──────────────────────────────────────────────────────────────
#  Click Merchant API webhook (Prepare / Complete)
#  Kalitlar sozlangach to'liq ishlaydi.
#  https://docs.click.uz
# ──────────────────────────────────────────────────────────────
def _click_signature(d, secret, complete=False):
    # MD5(click_trans_id + service_id + SECRET_KEY + merchant_trans_id
    #     [+ merchant_prepare_id] + amount + action + sign_time)
    parts = [
        d.get('click_trans_id', ''),
        d.get('service_id', ''),
        secret,
        d.get('merchant_trans_id', ''),
    ]
    if complete:
        parts.append(d.get('merchant_prepare_id', ''))
    parts += [d.get('amount', ''), d.get('action', ''), d.get('sign_time', '')]
    raw = ''.join(str(p) for p in parts)
    return hashlib.md5(raw.encode()).hexdigest()


def _click_error(code, note):
    return Response({'error': code, 'error_note': note})


def _click_sorov(d, secret, complete=False):
    """Imzo, so'rov va summani tekshiradi. Qaytadi: (sorov, None) yoki (None, javob)."""
    if not secret:
        return None, _click_error(-9, 'Click sozlanmagan')
    imzo = str(d.get('sign_string') or '')
    if not hmac.compare_digest(imzo, _click_signature(d, secret, complete=complete)):
        return None, _click_error(-1, 'Imzo xato')
    try:
        sorov = TolovSorovi.objects.select_for_update().get(
            pk=d.get('merchant_trans_id'), tolov_tizimi='click')
    except (TolovSorovi.DoesNotExist, ValueError, TypeError):
        return None, _click_error(-5, "So'rov topilmadi")
    # To'langan summa so'rov summasiga mos kelishi shart
    try:
        summa_mos = abs(float(d.get('amount', 0)) - float(sorov.summa)) < 1
    except (TypeError, ValueError):
        summa_mos = False
    if not summa_mos:
        return None, _click_error(-2, "Summa noto'g'ri")
    if sorov.holat == 'tolandi':
        return None, _click_error(-4, "Allaqachon to'langan")
    if sorov.holat == 'bekor':
        return None, _click_error(-9, 'Tranzaksiya bekor qilingan')
    return sorov, None


@api_view(['POST'])
@permission_classes([AllowAny])
def click_prepare(request):
    d = request.data
    with transaction.atomic():
        sorov, xato = _click_sorov(d, getattr(settings, 'CLICK_SECRET_KEY', ''))
        if xato:
            return xato
        # Click tranzaksiya id sini eslab qolamiz: Complete shu id bilan kelishi shart
        sorov.tashqi_id = str(d.get('click_trans_id', ''))
        sorov.holat = 'kutilmoqda'
        sorov.save(update_fields=['tashqi_id', 'holat', 'yangilangan'])
    return Response({
        'click_trans_id': d.get('click_trans_id'),
        'merchant_trans_id': d.get('merchant_trans_id'),
        'merchant_prepare_id': sorov.id,
        'error': 0,
        'error_note': 'Success',
    })


@api_view(['POST'])
@permission_classes([AllowAny])
def click_complete(request):
    d = request.data
    with transaction.atomic():
        sorov, xato = _click_sorov(d, getattr(settings, 'CLICK_SECRET_KEY', ''), complete=True)
        if xato:
            return xato
        # Prepare bosqichidan o'tmagan yoki boshqa tranzaksiyaga tegishli Complete
        if (str(d.get('merchant_prepare_id')) != str(sorov.id)
                or not sorov.tashqi_id
                or str(d.get('click_trans_id')) != sorov.tashqi_id):
            return _click_error(-6, 'Tranzaksiya topilmadi')

        if str(d.get('error')) != '0':
            # Click to'lov amalga oshmaganini xabar qildi — so'rov bekor qilinadi
            sorov.holat = 'bekor'
            sorov.save(update_fields=['holat', 'yangilangan'])
            return _click_error(-9, 'Tranzaksiya bekor qilindi')

        sorov.holat = 'tolandi'
        sorov.save(update_fields=['holat', 'yangilangan'])
    return Response({
        'click_trans_id': d.get('click_trans_id'),
        'merchant_trans_id': d.get('merchant_trans_id'),
        'merchant_confirm_id': sorov.id,
        'error': 0,
        'error_note': 'Success',
    })


# Payme JSON-RPC webhook: apps/tolovlar/payme.py (holat mashinasi o'sha yerda)


# ──────────────────────────────────────────────────────────────
#  Public: Metrologiya bo'limidan ariza
# ──────────────────────────────────────────────────────────────
class MetrologiyaArizaThrottle(AnonRateThrottle):
    """Ochiq forma spamdan himoyalangan: bir IP dan soatiga 10 ta ariza."""
    scope = 'metrologiya_ariza'
    rate = '10/hour'


@api_view(['POST'])
@permission_classes([AllowAny])
@throttle_classes([MetrologiyaArizaThrottle])
def metrologiya_ariza_yaratish(request):
    ser = MetrologiyaArizasiSerializer(data=request.data)
    if not ser.is_valid():
        return Response(ser.errors, status=400)
    ariza = ser.save()
    # Xizmat turi ixtiyoriy: tanlanmagan bo'lsa SMS'da qavs ichida bo'sh joy chiqmasin
    tur = f" ({ariza.get_xizmat_display()})" if ariza.xizmat else ""
    _sms_yuborish(
        ariza.telefon,
        f"SOAR GAZ: metrologiya{tur} arizangiz #{ariza.id} qabul qilindi! "
        f"24 soat ichida bog'lanamiz."
    )
    return Response(MetrologiyaArizasiSerializer(ariza).data, status=201)
