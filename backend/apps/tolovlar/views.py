import base64
import hashlib
from urllib.parse import urlencode

from django.conf import settings
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from apps.auth_app.models import Foydalanuvchi
from apps.sms_app.gateway import sms_yubor
from apps.sms_app.models import SmsXabar
from .models import TolovSorovi, MahsulotSorovi
from .serializers import TolovSoroviSerializer, MahsulotSoroviSerializer


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
        return Response({'detail': 'Ruxsat yo\'q'}, status=403)
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
        return Response({'detail': 'Ruxsat yo\'q'}, status=403)
    try:
        sorov = TolovSorovi.objects.get(pk=pk)
    except TolovSorovi.DoesNotExist:
        return Response({'detail': 'Topilmadi'}, status=404)
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
        return Response({'detail': 'Ruxsat yo\'q'}, status=403)
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
        return Response({'detail': 'Ruxsat yo\'q'}, status=403)
    try:
        sorov = MahsulotSorovi.objects.get(pk=pk)
    except MahsulotSorovi.DoesNotExist:
        return Response({'detail': 'Topilmadi'}, status=404)
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


@api_view(['POST'])
@permission_classes([AllowAny])
def click_prepare(request):
    secret = getattr(settings, 'CLICK_SECRET_KEY', '')
    if not secret:
        return _click_error(-9, 'Click sozlanmagan')
    d = request.data
    if d.get('sign_string') != _click_signature(d, secret):
        return _click_error(-1, 'Imzo xato')
    try:
        sorov = TolovSorovi.objects.get(pk=d.get('merchant_trans_id'))
    except (TolovSorovi.DoesNotExist, ValueError, TypeError):
        return _click_error(-5, 'So\'rov topilmadi')
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
    secret = getattr(settings, 'CLICK_SECRET_KEY', '')
    if not secret:
        return _click_error(-9, 'Click sozlanmagan')
    d = request.data
    if d.get('sign_string') != _click_signature(d, secret, complete=True):
        return _click_error(-1, 'Imzo xato')
    try:
        sorov = TolovSorovi.objects.get(pk=d.get('merchant_trans_id'))
    except (TolovSorovi.DoesNotExist, ValueError, TypeError):
        return _click_error(-5, 'So\'rov topilmadi')
    # To'langan summa so'rov summasiga mos kelishi shart
    try:
        summa_mos = abs(float(d.get('amount', 0)) - float(sorov.summa)) < 1
    except (TypeError, ValueError):
        summa_mos = False
    if not summa_mos:
        return _click_error(-2, "Summa noto'g'ri")

    if str(d.get('error')) == '0':
        sorov.holat = 'tolandi'
        sorov.tashqi_id = str(d.get('click_trans_id', ''))
        sorov.save(update_fields=['holat', 'tashqi_id', 'yangilangan'])
    return Response({
        'click_trans_id': d.get('click_trans_id'),
        'merchant_trans_id': d.get('merchant_trans_id'),
        'merchant_confirm_id': sorov.id,
        'error': 0,
        'error_note': 'Success',
    })


# ──────────────────────────────────────────────────────────────
#  Payme JSON-RPC webhook
#  Kalitlar sozlangach to'liq ishlaydi.  https://developer.help.paycom.uz
# ──────────────────────────────────────────────────────────────
def _payme_result(rpc_id, result):
    return Response({'jsonrpc': '2.0', 'id': rpc_id, 'result': result})


def _payme_error(rpc_id, code, message):
    return Response({'jsonrpc': '2.0', 'id': rpc_id,
                     'error': {'code': code, 'message': message}})


@api_view(['POST'])
@permission_classes([AllowAny])
def payme_endpoint(request):
    key = getattr(settings, 'PAYME_KEY', '')
    rpc_id = request.data.get('id')
    if not key:
        return _payme_error(rpc_id, -32504, 'Payme sozlanmagan')

    # Basic auth: "Paycom:<PAYME_KEY>"
    auth = request.META.get('HTTP_AUTHORIZATION', '')
    ok = False
    if auth.startswith('Basic '):
        try:
            dec = base64.b64decode(auth[6:]).decode()
            ok = dec.split(':', 1)[-1] == key
        except Exception:
            ok = False
    if not ok:
        return _payme_error(rpc_id, -32504, 'Avtorizatsiya xato')

    method = request.data.get('method')
    params = request.data.get('params', {})

    def _sorov():
        oid = (params.get('account') or {}).get('order_id')
        return TolovSorovi.objects.filter(pk=oid).first()

    def _summa_mos(s):
        """Payme summani tiyinda yuboradi — so'rov summasi bilan solishtiramiz."""
        try:
            return int(params.get('amount', 0)) == int(s.summa) * 100
        except (TypeError, ValueError):
            return False

    if method == 'CheckPerformTransaction':
        s = _sorov()
        if not s:
            return _payme_error(rpc_id, -31050, 'Buyurtma topilmadi')
        if not _summa_mos(s):
            return _payme_error(rpc_id, -31001, "Summa noto'g'ri")
        return _payme_result(rpc_id, {'allow': True})

    if method == 'CreateTransaction':
        s = _sorov()
        if not s:
            return _payme_error(rpc_id, -31050, 'Buyurtma topilmadi')
        if not _summa_mos(s):
            return _payme_error(rpc_id, -31001, "Summa noto'g'ri")
        s.holat = 'kutilmoqda'
        s.tashqi_id = params.get('id', '')
        s.save(update_fields=['holat', 'tashqi_id', 'yangilangan'])
        return _payme_result(rpc_id, {
            'create_time': params.get('time'),
            'transaction': str(s.id),
            'state': 1,
        })

    if method == 'PerformTransaction':
        s = TolovSorovi.objects.filter(tashqi_id=params.get('id')).first()
        if not s:
            return _payme_error(rpc_id, -31003, 'Tranzaksiya topilmadi')
        s.holat = 'tolandi'
        s.save(update_fields=['holat', 'yangilangan'])
        return _payme_result(rpc_id, {
            'transaction': str(s.id), 'perform_time': params.get('time', 0), 'state': 2,
        })

    if method == 'CancelTransaction':
        s = TolovSorovi.objects.filter(tashqi_id=params.get('id')).first()
        if s:
            s.holat = 'bekor'
            s.save(update_fields=['holat', 'yangilangan'])
        return _payme_result(rpc_id, {
            'transaction': str(s.id) if s else '', 'cancel_time': params.get('time', 0), 'state': -1,
        })

    if method == 'CheckTransaction':
        s = TolovSorovi.objects.filter(tashqi_id=params.get('id')).first()
        if not s:
            return _payme_error(rpc_id, -31003, 'Tranzaksiya topilmadi')
        state = 2 if s.holat == 'tolandi' else (-1 if s.holat == 'bekor' else 1)
        return _payme_result(rpc_id, {'transaction': str(s.id), 'state': state})

    return _payme_error(rpc_id, -32601, 'Metod topilmadi')
