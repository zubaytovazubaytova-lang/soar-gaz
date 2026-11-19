"""Bank (hisob raqam) orqali to'lov: chek yuklash va tasdiqlash.

Mijoz:  GET  /api/tolovlar/bank/buyurtma/<id>/   — rekvizit, to'lov maqsadi, shu buyurtma cheklari
        POST /api/tolovlar/bank/buyurtma/<id>/   — chek (rasm/PDF) + summa yuklaydi
Tekshiruvchi (administrator va Kadrlar mutaxassisi — Ruxsora):
        GET  /api/tolovlar/bank/cheklar/?holat=tekshirilmoqda
        GET  /api/tolovlar/bank/cheklar/<id>/chek/  — chek fayli (mijozning o'zi ham ochadi)
        POST /api/tolovlar/bank/cheklar/<id>/tekshir/  {natija: tasdiq|rad, sabab}

Skrinshotni soxtalashtirish oson — «to'landi» faqat tekshiruvchi bankda pulni ko'rib tasdiqlagandan keyin.
Xabarlar Telegram bot orqali (tekin): tekshiruvchilarga yangi chek, mijozga natija.
"""
import logging

from django.db import transaction
from django.http import FileResponse, Http404
from django.utils import timezone, translation
from rest_framework.decorators import api_view, permission_classes, throttle_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import UserRateThrottle

from apps.auth_app.kabinet_turlari import kadrmi
from apps.auth_app.models import audit_yoz
from apps.buyurtmalar.models import Buyurtma
from apps.sms_app import xodim_xabar
from apps.sms_app.gateway import sms_yubor
from .models import BankTolovi, Rekvizit, TolovSorovi, xizmat_yonalishi

logger = logging.getLogger(__name__)

CHEK_MAX = 5 * 1024 * 1024                     # 5 MB
CHEK_TURLARI = {                               # kengaytma → fayl boshidagi belgi
    'jpg': (b'\xff\xd8\xff',), 'jpeg': (b'\xff\xd8\xff',), 'png': (b'\x89PNG',),
    'webp': (b'RIFF',), 'pdf': (b'%PDF',),
}
MIN_SUMMA, MAX_SUMMA = 1_000, 10_000_000_000


class ChekThrottle(UserRateThrottle):
    scope = 'bank_chek'
    rate = '20/hour'


def tekshiruvchimi(user):
    """Chekni tasdiqlay oladiganlar: faol administrator va Kadrlar mutaxassisi (Ruxsora)."""
    admin = getattr(user, 'rol', None) == 'admin' and getattr(user, 'holat', 'faol') == 'faol'
    return admin or kadrmi(user)


def xizmat_uz(b):
    """Xizmat nomi doim o'zbekcha (bank to'lov maqsadi va xabarlar brauzer tiliga bog'liq bo'lmasin)."""
    with translation.override('uz'):
        return str(b.get_xizmat_display())


def tolov_maqsadi(b):
    return f"Buyurtma #{b.id} uchun {xizmat_uz(b).lower()} xizmati haqi"


def _rekvizit_json(r):
    if not r:
        return None
    return {'yonalish': r.yonalish, 'yonalish_nomi': r.get_yonalish_display(), 'korxona': r.korxona,
            'bank': r.bank, 'hisob_raqam': r.hisob_raqam, 'mfo': r.mfo, 'stir': r.stir}


def _tolov_json(t, tekshiruvchi=False):
    d = {'id': t.id, 'buyurtma': t.buyurtma_id, 'summa': t.summa, 'holat': t.holat,
         'holat_nomi': t.get_holat_display(), 'rad_sabab': t.rad_sabab, 'izoh': t.izoh,
         'yaratilgan': t.yaratilgan, 'tekshirilgan': t.tekshirilgan,
         'chek_url': f'/api/tolovlar/bank/cheklar/{t.id}/chek/'}
    if tekshiruvchi:
        b = t.buyurtma
        d.update({'mijoz': t.mijoz.ism, 'telefon': t.mijoz.telefon, 'xizmat': xizmat_uz(b),
                  'tasdiq_summa': b.tasdiq_summa, 'hisob_raqam': t.hisob_raqam,
                  'tekshirdi': t.tekshirdi.ism if t.tekshirdi else ''})
    return d


def _chek_tekshir(fayl):
    if not fayl:
        return "Chek faylini yuklang (rasm yoki PDF)"
    if fayl.size > CHEK_MAX:
        return "Fayl 5 MB dan katta bo'lmasin"
    kengaytma = fayl.name.rsplit('.', 1)[-1].lower() if '.' in fayl.name else ''
    if kengaytma not in CHEK_TURLARI:
        return "Faqat JPG, PNG, WEBP rasm yoki PDF yuklang"
    bosh = fayl.read(16)
    fayl.seek(0)
    if not any(bosh.startswith(b) for b in CHEK_TURLARI[kengaytma]) or (kengaytma == 'webp' and b'WEBP' not in bosh):
        return "Fayl buzilgan yoki turi kengaytmasiga mos emas"
    return None


@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
@throttle_classes([ChekThrottle])
def buyurtma_bank_tolovi(request, pk):
    b = Buyurtma.objects.filter(pk=pk, mijoz=request.user).first()
    if not b:
        return Response({'detail': 'Buyurtma topilmadi'}, status=404)
    rekvizit = Rekvizit.objects.filter(yonalish=xizmat_yonalishi(b.xizmat), faol=True).first()

    if request.method == 'GET':
        return Response({
            'rekvizit': _rekvizit_json(rekvizit),
            'maqsad': tolov_maqsadi(b),
            'tolovlar': [_tolov_json(t) for t in b.bank_tolovlari.filter(mijoz=request.user)],
        })

    if b.holat == 'bekor':
        return Response({'detail': 'Bekor qilingan buyurtma uchun to\'lov qabul qilinmaydi'}, status=400)
    if not rekvizit:
        return Response({'detail': 'Hisob raqam hali kiritilmagan. Iltimos, keyinroq urinib ko\'ring'}, status=400)
    if b.bank_tolovlari.filter(holat='tekshirilmoqda').exists():
        return Response({'detail': 'Bu buyurtma bo\'yicha yuborilgan chek hali tekshirilmoqda'}, status=400)
    try:
        summa = int(str(request.data.get('summa', '')).replace(' ', ''))
    except ValueError:
        summa = 0
    if not MIN_SUMMA <= summa <= MAX_SUMMA:
        return Response({'detail': 'To\'langan summani to\'g\'ri kiriting'}, status=400)
    fayl = request.FILES.get('chek')
    xato = _chek_tekshir(fayl)
    if xato:
        return Response({'detail': xato}, status=400)

    user = request.user
    with transaction.atomic():
        sorov = TolovSorovi.objects.create(
            ism=user.ism or user.telefon, telefon=user.telefon, tolov_turi='bank',
            xizmat_turi=f"Buyurtma #{b.id} — {xizmat_uz(b)}", summa=summa, holat='kutilmoqda')
        t = BankTolovi.objects.create(
            buyurtma=b, mijoz=user, summa=summa, hisob_raqam=rekvizit.hisob_raqam, chek=fayl,
            izoh=str(request.data.get('izoh') or '')[:300], tolov_sorovi=sorov)
        audit_yoz(request, 'bank_chek', f"Bank to'lovi cheki yuklandi: buyurtma #{b.id}, {summa} so'm", user=user)
    xodim_xabar.tolov_tekshiruvchilarga(
        f"💳 Yangi to'lov cheki: buyurtma #{b.id} ({xizmat_uz(b)})\n"
        f"👤 {user.ism or ''} {user.telefon}\n💰 {summa:,} so'm".replace(',', ' ')
        + f"\nBankda tushumni tekshirib tasdiqlang: {xodim_xabar.XODIM_KABINETI}")
    return Response(_tolov_json(t), status=201)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def cheklar(request):
    if not tekshiruvchimi(request.user):
        return Response({'detail': 'Ruxsat yo\'q'}, status=403)
    qs = BankTolovi.objects.select_related('buyurtma', 'mijoz', 'tekshirdi')
    holat = request.query_params.get('holat')
    if holat:
        qs = qs.filter(holat=holat)
    return Response({'royxat': [_tolov_json(t, True) for t in qs[:200]],
                     'kutilmoqda': BankTolovi.objects.filter(holat='tekshirilmoqda').count()})


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def chek_fayli(request, pk):
    t = BankTolovi.objects.filter(pk=pk).first()
    if not t or not (t.mijoz_id == request.user.id or tekshiruvchimi(request.user)):
        raise Http404
    try:
        javob = FileResponse(t.chek.open('rb'))
    except FileNotFoundError:
        raise Http404
    javob['Cache-Control'] = 'private, no-store'
    javob['X-Content-Type-Options'] = 'nosniff'
    return javob


def tekshir(t, user, natija, sabab='', request=None):
    """Chekni tasdiqlaydi yoki rad etadi (API va admin panel uchun umumiy). Xato bo'lsa matn qaytaradi."""
    if natija not in ('tasdiq', 'rad'):
        return 'Natija noto\'g\'ri'
    if natija == 'rad' and not sabab.strip():
        return 'Rad etish sababini yozing'
    with transaction.atomic():
        t = BankTolovi.objects.select_for_update(of=('self',)).select_related('buyurtma', 'mijoz').get(pk=t.pk)
        if t.holat != 'tekshirilmoqda':
            return 'Bu chek allaqachon ko\'rib chiqilgan'
        t.holat = 'tasdiqlandi' if natija == 'tasdiq' else 'rad'
        t.rad_sabab = sabab.strip()[:300] if natija == 'rad' else ''
        t.tekshirdi, t.tekshirilgan = user, timezone.now()
        t.save(update_fields=['holat', 'rad_sabab', 'tekshirdi', 'tekshirilgan'])
        if t.tolov_sorovi_id:
            TolovSorovi.objects.filter(pk=t.tolov_sorovi_id).update(
                holat='tolandi' if natija == 'tasdiq' else 'bekor')
        if request is not None:
            audit_yoz(request, 'bank_tekshir', f"Bank to'lovi #{t.id} (buyurtma #{t.buyurtma_id}) "
                      + ('tasdiqlandi' if natija == 'tasdiq' else f'rad etildi: {t.rad_sabab}'))
    summa = f"{t.summa:,}".replace(',', ' ')
    if natija == 'tasdiq':
        matn = f"SOAR GAZ: #{t.buyurtma_id} buyurtma bo'yicha {summa} so'm to'lovingiz qabul qilindi. Rahmat!"
    else:
        matn = (f"SOAR GAZ: #{t.buyurtma_id} buyurtma bo'yicha {summa} so'm to'lov tasdiqlanmadi. "
                f"Sabab: {t.rad_sabab}. Kabinetda chekni qayta yuborishingiz mumkin.")
    transaction.on_commit(lambda: sms_yubor(t.mijoz.telefon, matn))
    return None


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def chek_tekshir(request, pk):
    if not tekshiruvchimi(request.user):
        return Response({'detail': 'Ruxsat yo\'q'}, status=403)
    t = BankTolovi.objects.filter(pk=pk).first()
    if not t:
        return Response({'detail': 'Topilmadi'}, status=404)
    xato = tekshir(t, request.user, request.data.get('natija'), str(request.data.get('sabab') or ''), request)
    if xato:
        return Response({'detail': xato}, status=400)
    t.refresh_from_db()
    return Response(_tolov_json(t, True))
