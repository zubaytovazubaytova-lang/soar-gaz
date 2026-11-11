"""Payme Merchant API (JSON-RPC) webhooki.

Rasmiy hujjat: https://developer.help.paycom.uz  (Merchant API)

Tranzaksiya holatlari (Payme tilida):
     1  yaratildi, to'lov kutilmoqda
     2  to'landi (PerformTransaction bajarilgan)
    -1  to'lovdan OLDIN bekor qilindi
    -2  to'lovdan KEYIN bekor qilindi (qaytarildi)

Bizda holat alohida jadvalda emas, `TolovSorovi` ichida turadi:
    payme_yaratilgan is None            → Payme tranzaksiyasi hali yo'q
    holat == 'tolandi'                  → 2
    holat == 'bekor' va payme_bajarilgan → -2
    holat == 'bekor'                    → -1
    qolgan hollarda                     → 1

Qoida: bitta so'rov — bitta Payme tranzaksiya. Bekor qilingan (yoki muddati
tugagan) so'rov qayta to'lanmaydi; mijoz saytda «qayta urinish» bosib YANGI
so'rov oladi (apps.xaridlar.tolov.tolov_sorovi_yarat).

Eslatma: ichki funksiyalar xatoni `raise` qilmaydi, `_Xato` obyektini QAYTARADI —
aks holda `transaction.atomic` o'zgarishlarni (masalan muddati tugagan
tranzaksiyani bekor qilishni) orqaga qaytarib yuborardi.
"""
import base64
import hmac
import time

from django.conf import settings
from django.db import transaction
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from .models import TolovSorovi

# Yaratilgan tranzaksiya shu muddatda to'lanmasa bekor bo'ladi (Payme: 12 soat)
MUDDAT_MS = 12 * 60 * 60 * 1000

# Xato kodlari (Payme hujjatidan)
SUMMA_NOTOGRI = -31001
TRANZAKSIYA_YOQ = -31003
BEKOR_QILIB_BOLMAYDI = -31007
BAJARIB_BOLMAYDI = -31008
BUYURTMA_YOQ = -31050          # -31050 ... -31099: buyurtma (account) xatolari
BUYURTMA_TOLANMAYDI = -31051
BAND = -31052


class _Xato:
    def __init__(self, kod, uz, ru, en, data=None):
        self.kod = kod
        self.xabar = {'uz': uz, 'ru': ru, 'en': en}
        self.data = data


def _hozir_ms():
    return int(time.time() * 1000)


def _javob(rpc_id, natija):
    return Response({'jsonrpc': '2.0', 'id': rpc_id, 'result': natija})


def _xato_javob(rpc_id, kod, xabar, data=None):
    if isinstance(xabar, str):
        xabar = {'uz': xabar, 'ru': xabar, 'en': xabar}
    err = {'code': kod, 'message': xabar}
    if data is not None:
        err['data'] = data
    return Response({'jsonrpc': '2.0', 'id': rpc_id, 'error': err})


# ── Holat yordamchilari ───────────────────────────────────────
def _state(s):
    if s.payme_yaratilgan is None:
        return None
    if s.holat == 'tolandi':
        return 2
    if s.holat == 'bekor':
        return -2 if s.payme_bajarilgan else -1
    return 1


def _muddati_otgan(s):
    return _hozir_ms() - s.payme_yaratilgan > MUDDAT_MS


def _bekor_vaqti(s):
    """Bekor qilingan vaqt; admin qo'lda bekor qilgan bo'lsa yangilangan vaqt."""
    if s.payme_bekor:
        return s.payme_bekor
    if s.holat == 'bekor':
        return int(s.yangilangan.timestamp() * 1000)
    return 0


def sorovni_bekor_qil(s, sabab=None):
    """So'rovni bekor qiladi (Payme tranzaksiyasi bo'lsa, vaqt va sababi bilan)."""
    s.holat = 'bekor'
    maydonlar = ['holat', 'yangilangan']
    if s.payme_yaratilgan is not None:
        s.payme_bekor = _hozir_ms()
        s.payme_sabab = sabab if isinstance(sabab, int) else None
        maydonlar += ['payme_bekor', 'payme_sabab']
    s.save(update_fields=maydonlar)


def _tranzaksiya_dict(s):
    return {
        'create_time': s.payme_yaratilgan,
        'perform_time': s.payme_bajarilgan or 0,
        'cancel_time': _bekor_vaqti(s) if _state(s) in (-1, -2) else 0,
        'transaction': str(s.id),
        'state': _state(s),
        'reason': s.payme_sabab if _state(s) in (-1, -2) else None,
    }


# ── Qidiruv ───────────────────────────────────────────────────
def _tranzaksiya(params):
    tid = params.get('id')
    if not tid:
        return None
    return (TolovSorovi.objects.select_for_update()
            .filter(tashqi_id=str(tid), payme_yaratilgan__isnull=False).first())


def _buyurtma(params):
    oid = (params.get('account') or {}).get('order_id')
    try:
        oid = int(oid)
    except (TypeError, ValueError):
        return None
    return (TolovSorovi.objects.select_for_update()
            .filter(pk=oid, tolov_tizimi='payme').first())


def _buyurtmani_tekshir(params):
    """Buyurtma topiladimi, summa mosmi, to'lash mumkinmi?

    Qaytadi: (sorov, None) yoki (None, _Xato).
    """
    s = _buyurtma(params)
    if not s:
        return None, _Xato(BUYURTMA_YOQ, 'Buyurtma topilmadi', 'Заказ не найден',
                           'Order not found', 'order_id')
    try:
        summa_mos = int(params.get('amount', 0)) == int(s.summa) * 100
    except (TypeError, ValueError):
        summa_mos = False
    if not summa_mos:
        return None, _Xato(SUMMA_NOTOGRI, "Summa noto'g'ri", 'Неверная сумма', 'Incorrect amount')
    if s.holat not in ('yangi', 'kutilmoqda'):
        return None, _Xato(BUYURTMA_TOLANMAYDI, "Bu buyurtmani to'lab bo'lmaydi",
                           'Этот заказ нельзя оплатить', 'This order cannot be paid', 'order_id')
    return s, None


# ── Metodlar ──────────────────────────────────────────────────
def _check_perform(params):
    s, xato = _buyurtmani_tekshir(params)
    if xato:
        return xato
    return {'allow': True}


def _create(params):
    tr = _tranzaksiya(params)
    if tr:
        # Takroriy chaqiruv: mavjud tranzaksiya qaytariladi, yangisi yaratilmaydi
        if _state(tr) != 1:
            return _Xato(BAJARIB_BOLMAYDI, "Tranzaksiyani bajarib bo'lmaydi",
                         'Невозможно выполнить операцию', 'Unable to perform operation')
        if _muddati_otgan(tr):
            sorovni_bekor_qil(tr, 4)
            return _Xato(BAJARIB_BOLMAYDI, 'Tranzaksiya muddati tugagan',
                         'Время транзакции истекло', 'Transaction timed out')
        return {'create_time': tr.payme_yaratilgan, 'transaction': str(tr.id), 'state': 1}

    if not params.get('id'):
        return _Xato(BAJARIB_BOLMAYDI, 'Tranzaksiya id yo\'q',
                     'Нет id транзакции', 'Transaction id is missing')

    s, xato = _buyurtmani_tekshir(params)
    if xato:
        return xato

    if s.payme_yaratilgan is not None:
        # Bu buyurtmada BOSHQA id bilan faol tranzaksiya bor
        if _muddati_otgan(s):
            sorovni_bekor_qil(s, 4)
            return _Xato(BUYURTMA_TOLANMAYDI, "Bu buyurtmani to'lab bo'lmaydi",
                         'Этот заказ нельзя оплатить', 'This order cannot be paid', 'order_id')
        return _Xato(BAND, "Buyurtma uchun boshqa to'lov jarayoni davom etmoqda",
                     'По заказу уже идёт другая оплата', 'Another payment is in progress',
                     'order_id')

    try:
        yaratilgan = int(params.get('time'))
    except (TypeError, ValueError):
        yaratilgan = _hozir_ms()
    s.tashqi_id = str(params['id'])
    s.payme_yaratilgan = yaratilgan
    s.holat = 'kutilmoqda'
    s.save(update_fields=['tashqi_id', 'payme_yaratilgan', 'holat', 'yangilangan'])
    return {'create_time': s.payme_yaratilgan, 'transaction': str(s.id), 'state': 1}


def _perform(params):
    tr = _tranzaksiya(params)
    if not tr:
        return _Xato(TRANZAKSIYA_YOQ, 'Tranzaksiya topilmadi', 'Транзакция не найдена',
                     'Transaction not found')
    holat = _state(tr)
    if holat == 1:
        if _muddati_otgan(tr):
            sorovni_bekor_qil(tr, 4)
            return _Xato(BAJARIB_BOLMAYDI, 'Tranzaksiya muddati tugagan',
                         'Время транзакции истекло', 'Transaction timed out')
        tr.holat = 'tolandi'
        tr.payme_bajarilgan = _hozir_ms()
        tr.save(update_fields=['holat', 'payme_bajarilgan', 'yangilangan'])
    elif holat != 2:
        # Bekor qilingan tranzaksiyani to'lab bo'lmaydi
        return _Xato(BAJARIB_BOLMAYDI, "Tranzaksiyani bajarib bo'lmaydi",
                     'Невозможно выполнить операцию', 'Unable to perform operation')
    # holat == 2: takroriy chaqiruv — birinchi marta saqlangan vaqt qaytariladi
    return {'transaction': str(tr.id), 'perform_time': tr.payme_bajarilgan, 'state': 2}


def _cancel(params):
    from apps.xaridlar.models import Xarid   # sikl bo'lmasligi uchun shu yerda

    tr = _tranzaksiya(params)
    if not tr:
        return _Xato(TRANZAKSIYA_YOQ, 'Tranzaksiya topilmadi', 'Транзакция не найдена',
                     'Transaction not found')
    holat = _state(tr)
    if holat == 2:
        # Yetkazib berilgan buyurtma uchun to'lovni qaytarib bo'lmaydi
        if Xarid.objects.filter(tolov_sorovi=tr, holat='yetkazildi').exists():
            return _Xato(BEKOR_QILIB_BOLMAYDI, "Buyurtma yetkazilgan, bekor qilib bo'lmaydi",
                         'Заказ доставлен, отмена невозможна', 'Order delivered, cannot cancel')
    if holat in (1, 2):
        sorovni_bekor_qil(tr, params.get('reason'))
    # holat -1 / -2: takroriy chaqiruv — avvalgi bekor vaqti qaytariladi
    return {'transaction': str(tr.id), 'cancel_time': _bekor_vaqti(tr), 'state': _state(tr)}


def _check_transaction(params):
    tr = _tranzaksiya(params)
    if not tr:
        return _Xato(TRANZAKSIYA_YOQ, 'Tranzaksiya topilmadi', 'Транзакция не найдена',
                     'Transaction not found')
    return _tranzaksiya_dict(tr)


def _get_statement(params):
    try:
        dan, gacha = int(params.get('from')), int(params.get('to'))
    except (TypeError, ValueError):
        return _Xato(-32600, "So'rov noto'g'ri", 'Неверный запрос', 'Invalid request')
    qs = TolovSorovi.objects.filter(
        tolov_tizimi='payme', payme_yaratilgan__gte=dan, payme_yaratilgan__lte=gacha
    ).order_by('payme_yaratilgan')
    royxat = []
    for s in qs:
        d = _tranzaksiya_dict(s)
        d.update({
            'id': s.tashqi_id,
            'time': s.payme_yaratilgan,
            'amount': int(s.summa) * 100,
            'account': {'order_id': str(s.id)},
        })
        royxat.append(d)
    return {'transactions': royxat}


METODLAR = {
    'CheckPerformTransaction': _check_perform,
    'CreateTransaction': _create,
    'PerformTransaction': _perform,
    'CancelTransaction': _cancel,
    'CheckTransaction': _check_transaction,
    'GetStatement': _get_statement,
}


def _avtorizatsiya(request, key):
    """Basic auth: «Paycom:<kalit>». Kalit doimiy vaqtda solishtiriladi."""
    auth = request.META.get('HTTP_AUTHORIZATION', '')
    if not auth.startswith('Basic '):
        return False
    try:
        login, _, parol = base64.b64decode(auth[6:]).decode().partition(':')
    except Exception:
        return False
    return login == 'Paycom' and hmac.compare_digest(parol.encode(), key.encode())


@api_view(['POST'])
@permission_classes([AllowAny])
def payme_endpoint(request):
    rpc_id = request.data.get('id')
    key = getattr(settings, 'PAYME_KEY', '')
    if not key:
        return _xato_javob(rpc_id, -32504, 'Payme sozlanmagan')
    if not _avtorizatsiya(request, key):
        return _xato_javob(rpc_id, -32504, 'Avtorizatsiya xato')

    metod = METODLAR.get(request.data.get('method'))
    if not metod:
        return _xato_javob(rpc_id, -32601, 'Metod topilmadi')

    params = request.data.get('params') or {}
    if not isinstance(params, dict):
        return _xato_javob(rpc_id, -32600, "So'rov noto'g'ri")

    with transaction.atomic():
        natija = metod(params)

    if isinstance(natija, _Xato):
        return _xato_javob(rpc_id, natija.kod, natija.xabar, natija.data)
    return _javob(rpc_id, natija)
