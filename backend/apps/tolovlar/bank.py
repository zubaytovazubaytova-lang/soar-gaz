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
from rest_framework.permissions import AllowAny, IsAuthenticated
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


def _nomi(t):
    """Chek nimaga tegishli: «#12 buyurtma» yoki «XA-0001 xarid»."""
    return f"{t.xarid.raqam} xarid" if t.xarid_id else f"#{t.buyurtma_id} buyurtma"


def _tolov_json(t, tekshiruvchi=False):
    d = {'id': t.id, 'buyurtma': t.buyurtma_id, 'xarid': t.xarid.raqam if t.xarid_id else None,
         'summa': t.summa, 'holat': t.holat,
         'holat_nomi': t.get_holat_display(), 'rad_sabab': t.rad_sabab, 'izoh': t.izoh,
         'yaratilgan': t.yaratilgan, 'tekshirilgan': t.tekshirilgan,
         'chek_url': f'/api/tolovlar/bank/cheklar/{t.id}/chek/'}
    if tekshiruvchi:
        if t.xarid_id:
            x = t.xarid
            d.update({'mijoz': x.ism, 'telefon': x.telefon, 'xizmat': f"Do'kon xaridi {x.raqam}",
                      'tasdiq_summa': x.jami})
        else:
            b = t.buyurtma
            d.update({'mijoz': t.mijoz.ism if t.mijoz else '', 'telefon': t.mijoz.telefon if t.mijoz else '',
                      'xizmat': f"Buyurtma #{b.id} — {xizmat_uz(b)}", 'tasdiq_summa': b.tasdiq_summa})
        d.update({'hisob_raqam': t.hisob_raqam, 'tekshirdi': t.tekshirdi.ism if t.tekshirdi else ''})
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
            buyurtma=b, ism=user.ism or user.telefon, telefon=user.telefon, tolov_turi='bank',
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


@api_view(['GET', 'POST'])
@permission_classes([AllowAny])
@throttle_classes([ChekThrottle])
def xarid_bank_tolovi(request, raqam):
    """Do'kon xaridi uchun hisob raqamga to'lov. Mehmon xaridi ham: egalik telefon oxiri bilan
    (apps.xaridlar.views._egalik_tekshir — boshqa xarid amallari bilan bir xil qoida)."""
    from apps.xaridlar.models import Xarid
    from apps.xaridlar.tolov import tolov_sorovi_yarat
    from apps.xaridlar.views import _egalik_tekshir

    x = Xarid.objects.filter(raqam=raqam).first()
    if not x:
        return Response({'detail': 'Buyurtma topilmadi'}, status=404)
    rad = _egalik_tekshir(request, x)
    if rad:
        return rad
    rekvizit = Rekvizit.objects.filter(yonalish='xarid', faol=True).first()
    maqsad = f"{x.raqam} buyurtma bo'yicha mahsulot xaridi uchun"

    if request.method == 'GET':
        return Response({'rekvizit': _rekvizit_json(rekvizit), 'maqsad': maqsad, 'summa': x.jami,
                         'tolandi': x.tolandi,
                         'tolovlar': [_tolov_json(t) for t in x.bank_tolovlari.all()]})

    if x.tolov_usuli != 'bank':
        return Response({'detail': "Avval to'lov usulini «Hisob raqamga o'tkazma» ga o'zgartiring"}, status=400)
    if x.tolandi:
        return Response({'detail': "Bu buyurtma allaqachon to'langan"}, status=400)
    if x.holat == 'bekor':
        return Response({'detail': "Bekor qilingan buyurtmani to'lab bo'lmaydi"}, status=400)
    if not rekvizit:
        return Response({'detail': "Hisob raqam hali kiritilmagan. Iltimos, keyinroq urinib ko'ring"}, status=400)
    if x.bank_tolovlari.filter(holat='tekshirilmoqda').exists():
        return Response({'detail': "Bu buyurtma bo'yicha yuborilgan chek hali tekshirilmoqda"}, status=400)
    fayl = request.FILES.get('chek')
    xato = _chek_tekshir(fayl)
    if xato:
        return Response({'detail': xato}, status=400)

    user = request.user if request.user.is_authenticated else None
    with transaction.atomic():
        # Joriy so'rov to'lanmagan «bank» so'rovi bo'lmasa (masalan, oldingi chek rad etilgan) — yangisi
        s = x.tolov_sorovi
        if not s or s.tolov_turi != 'bank' or s.holat != 'kutilmoqda' or BankTolovi.objects.filter(tolov_sorovi=s).exists():
            s = tolov_sorovi_yarat(x)
        t = BankTolovi.objects.create(
            xarid=x, mijoz=x.mijoz or (user if user and user.rol == 'mijoz' else None), summa=x.jami,
            hisob_raqam=rekvizit.hisob_raqam, chek=fayl, izoh=str(request.data.get('izoh') or '')[:300],
            tolov_sorovi=s)
        audit_yoz(request, 'bank_chek', f"Bank to'lovi cheki yuklandi: xarid {x.raqam}, {x.jami} so'm",
                  user=x.mijoz or user)
    summa_matn = f"{x.jami:,}".replace(',', ' ')
    xodim_xabar.tolov_tekshiruvchilarga(
        f"💳 Yangi to'lov cheki: do'kon xaridi {x.raqam}\n"
        f"👤 {x.ism} {x.telefon}\n💰 {summa_matn} so'm\n"
        f"Bankda tushumni tekshirib tasdiqlang: {xodim_xabar.XODIM_KABINETI}")
    return Response(_tolov_json(t), status=201)


def click_yonalishlari():
    """Click (37118 — «SOAR GAZ LUX SERVIS») qaysi yo'nalish pulini qabul qiladi. Montaj uchun alohida
    korxona xizmati ochilmaguncha faqat servis: montaj puli boshqa korxona hisobiga tushmasin."""
    from django.conf import settings
    return [y.strip() for y in str(getattr(settings, 'CLICK_YONALISHLAR', 'servis')).split(',') if y.strip()]


class ClickHavolaThrottle(UserRateThrottle):
    scope = 'kabinet_click'
    rate = '30/hour'


@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
@throttle_classes([ClickHavolaThrottle])
def buyurtma_click(request, pk):
    """Mijoz kabineti: xizmat buyurtmasini Click orqali to'lash (Click sahifasiga havola)."""
    from django.conf import settings
    from .views import click_url

    b = Buyurtma.objects.filter(pk=pk, mijoz=request.user).first()
    if not b:
        return Response({'detail': 'Buyurtma topilmadi'}, status=404)
    sozlangan = bool(getattr(settings, 'CLICK_SERVICE_ID', '') and getattr(settings, 'CLICK_SECRET_KEY', ''))
    yonalish = xizmat_yonalishi(b.xizmat)
    sabab = ''
    if not sozlangan:
        sabab = "Click to'lovi hozircha sozlanmagan"
    elif yonalish not in click_yonalishlari():
        sabab = ("Bu xizmat uchun Click orqali to'lov tez orada ishga tushadi. "
                 "Hozircha «Hisob raqamga to'lash» orqali to'lashingiz mumkin")
    elif b.tolandi:
        sabab = "Bu buyurtma allaqachon to'langan"
    elif b.holat == 'bekor':
        sabab = "Bekor qilingan buyurtma uchun to'lov qabul qilinmaydi"

    if request.method == 'GET':
        return Response({'mumkin': not sabab, 'sabab': sabab, 'summa': b.tasdiq_summa,
                         'tolandi': b.tolandi, 'xizmat': xizmat_uz(b)})
    if sabab:
        return Response({'detail': sabab}, status=400)

    # Xodim tasdiqlagan summa bo'lsa — aynan shu; bo'lmasa mijoz kiritgani
    summa = b.tasdiq_summa
    if not summa:
        try:
            summa = int(str(request.data.get('summa', '')).replace(' ', ''))
        except ValueError:
            summa = 0
    if not MIN_SUMMA <= int(summa or 0) <= MAX_SUMMA:
        return Response({'detail': "To'lov summasini to'g'ri kiriting (kamida 1 000 so'm)"}, status=400)

    user = request.user
    with transaction.atomic():
        # Shu buyurtma uchun boshlanmagan eski Click so'rovlari bekor — bir buyurtma ikki marta to'lanmasin
        TolovSorovi.objects.filter(buyurtma=b, tolov_tizimi='click', holat='yangi').update(holat='bekor')
        s = TolovSorovi.objects.create(
            buyurtma=b, ism=user.ism or user.telefon, telefon=user.telefon, tolov_turi='online',
            tolov_tizimi='click', xizmat_turi=f"Buyurtma #{b.id} — {xizmat_uz(b)}", summa=int(summa), holat='yangi')
    qaytish = str(getattr(settings, 'SAYT_MANZIL', '')).rstrip('/') + '/kabinet/?click=1'
    return Response({'url': click_url(s, qaytish=qaytish), 'summa': s.summa, 'sorov': s.id})


@api_view(['GET'])
@permission_classes([AllowAny])
def rekvizitlar_ochiq(request):
    """Saytdagi «Bank o'tkazmasi» sahifasi uchun haqiqiy rekvizitlar (hisob-fakturadagi ochiq ma'lumot)."""
    return Response({'royxat': [_rekvizit_json(r) for r in Rekvizit.objects.filter(faol=True).order_by('yonalish')]})


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def cheklar(request):
    if not tekshiruvchimi(request.user):
        return Response({'detail': 'Ruxsat yo\'q'}, status=403)
    qs = BankTolovi.objects.select_related('buyurtma', 'xarid', 'mijoz', 'tekshirdi')
    holat = request.query_params.get('holat')
    if holat:
        qs = qs.filter(holat=holat)
    return Response({'royxat': [_tolov_json(t, True) for t in qs[:200]],
                     'kutilmoqda': BankTolovi.objects.filter(holat='tekshirilmoqda').count()})


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def chek_fayli(request, pk):
    t = BankTolovi.objects.filter(pk=pk).first()
    if not t or not ((t.mijoz_id and t.mijoz_id == request.user.id) or tekshiruvchimi(request.user)):
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
        t = BankTolovi.objects.select_for_update(of=('self',)).get(pk=t.pk)
        if t.holat != 'tekshirilmoqda':
            return 'Bu chek allaqachon ko\'rib chiqilgan'
        t.holat = 'tasdiqlandi' if natija == 'tasdiq' else 'rad'
        t.rad_sabab = sabab.strip()[:300] if natija == 'rad' else ''
        t.tekshirdi, t.tekshirilgan = user, timezone.now()
        t.save(update_fields=['holat', 'rad_sabab', 'tekshirdi', 'tekshirilgan'])
        if t.tolov_sorovi_id:
            # save() — signal (apps.xaridlar.signals) xaridni ham «to'landi» / «xato» qiladi
            s = TolovSorovi.objects.select_for_update().get(pk=t.tolov_sorovi_id)
            s.holat = 'tolandi' if natija == 'tasdiq' else 'bekor'
            s.save(update_fields=['holat', 'yangilangan'])
        if request is not None:
            audit_yoz(request, 'bank_tekshir', f"Bank to'lovi #{t.id} ({_nomi(t)}) "
                      + ('tasdiqlandi' if natija == 'tasdiq' else f'rad etildi: {t.rad_sabab}'))
    summa = f"{t.summa:,}".replace(',', ' ')
    if natija == 'tasdiq':
        matn = f"SOAR GAZ: {_nomi(t)} bo'yicha {summa} so'm to'lovingiz qabul qilindi. Rahmat!"
    else:
        matn = (f"SOAR GAZ: {_nomi(t)} bo'yicha {summa} so'm to'lov tasdiqlanmadi. "
                f"Sabab: {t.rad_sabab}. Chekni qayta yuborishingiz mumkin.")
    telefon = t.xarid.telefon if t.xarid_id else (t.mijoz.telefon if t.mijoz else '')
    if telefon:
        transaction.on_commit(lambda: sms_yubor(telefon, matn))
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
