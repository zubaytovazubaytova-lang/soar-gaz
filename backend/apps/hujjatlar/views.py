from django.http import Http404
from django.shortcuts import render
from django.utils import timezone
from django.utils.translation import gettext as _
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.auth_app.models import audit_yoz
from apps.buyurtmalar.models import Buyurtma
from apps.tushum.models import Tushum
from . import sozlar
from . import xizmat as x
from .models import Kvitansiya, Shartnoma, Sozlama

LIMIT_XODIM = 100
LIMIT_ADMIN = 300


def _xodimmi(request):
    u = request.user
    return getattr(u, 'rol', None) == 'xodim' and getattr(u, 'holat', '') == 'faol'


def _adminmi(request):
    return getattr(request.user, 'rol', None) == 'admin'


def _ruxsat_yoq():
    return Response({'detail': _("Ruxsat yo'q")}, status=403)


def _xato(e):
    return Response({'detail': e.detail}, status=e.status)


def _kv(k, request=None):
    return {
        'id': k.id, 'raqam': k.raqam, 'token': k.token, 'tushum_id': k.tushum_id,
        'url': x.sayt_havolasi(f'/kvitansiya/{k.token}/'),
        'mijoz_id': k.mijoz_id, 'yangi_mijoz': k.yangi_mijoz,
        'mijoz_ism': k.mijoz_ism, 'mijoz_telefon': k.mijoz_telefon, 'manzil': k.manzil,
        'summa': k.summa, 'usul_nomi': k.usul_nomi, 'ish_turi': k.ish_turi, 'buyurtma_id': k.buyurtma_id,
        'holat': k.holat, 'bekor_sababi': k.bekor_sababi,
        'sms_holat': k.sms_holat, 'sms_vaqti': k.sms_vaqti, 'yaratilgan': k.yaratilgan,
    }


def _sh(s):
    return {
        'id': s.id, 'raqam': s.raqam, 'token': s.token, 'buyurtma_id': s.buyurtma_id,
        'url': x.sayt_havolasi(f'/shartnoma/{s.token}/'),
        'mijoz_ism': s.mijoz_ism, 'mijoz_telefon': s.mijoz_telefon, 'manzil': s.manzil,
        'summa': s.summa, 'holat': s.holat, 'holat_nomi': s.get_holat_display(),
        'tasdiq_vaqti': s.tasdiq_vaqti, 'bekor_sababi': s.bekor_sababi, 'yaratilgan': s.yaratilgan,
    }


def _tushum_ruxsati(request, t):
    return _adminmi(request) or (_xodimmi(request) and t.xodim_id == request.user.id)


def _buyurtma_ruxsati(request, b):
    return _adminmi(request) or (_xodimmi(request) and b.xodim_id == request.user.id)


# ───────────── Kvitansiya ─────────────

@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def kvitansiyalar(request):
    if request.method == 'GET':
        if _adminmi(request):
            qs, limit = Kvitansiya.objects.all(), LIMIT_ADMIN
        elif _xodimmi(request):
            qs, limit = Kvitansiya.objects.filter(xodim=request.user), LIMIT_XODIM
        else:
            return _ruxsat_yoq()
        return Response([_kv(k) for k in qs[:limit]])

    # POST — tushum uchun kvitansiya chiqarish va (ixtiyoriy) SMS yuborish
    if not (_adminmi(request) or _xodimmi(request)):
        return _ruxsat_yoq()
    try:
        t = Tushum.objects.select_related('xodim', 'buyurtma').get(pk=int(request.data.get('tushum')))
    except (Tushum.DoesNotExist, TypeError, ValueError):
        return Response({'detail': _('Tushum topilmadi')}, status=404)
    if not _tushum_ruxsati(request, t):
        return _ruxsat_yoq()

    d = request.data
    b = t.buyurtma
    ism = d.get('mijoz_ism') or (b.mijoz_ism if b else '')
    telefon = d.get('mijoz_telefon') or (b.mijoz_telefon if b else '')
    manzil = d.get('manzil') or (x.buyurtma_manzili(b) if b else '')
    try:
        k, yangi = x.kvitansiya_yarat(t, ism, telefon, manzil)
        if yangi:
            audit_yoz(request, 'kvitansiya_berildi',
                      f'{k.raqam}: {k.summa} so\'m, {k.mijoz_ism}, {k.mijoz_telefon}')
        sms = None
        if yangi and d.get('sms', True) is not False:
            sms = x.kvitansiya_sms(k)
    except x.HujjatXato as e:
        return _xato(e)
    javob = _kv(k)
    javob['yangi'] = yangi
    javob['sms_yuborildi'] = sms
    return Response(javob, status=201 if yangi else 200)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def kvitansiya_sms(request, pk):
    """Kvitansiya SMS'ini qayta yuborish (mijoz olmagan bo'lsa). 60 soniyada bir marta."""
    try:
        k = Kvitansiya.objects.get(pk=pk)
    except Kvitansiya.DoesNotExist:
        return Response({'detail': _('Kvitansiya topilmadi')}, status=404)
    if not (_adminmi(request) or (_xodimmi(request) and k.xodim_id == request.user.id)):
        return _ruxsat_yoq()
    from django.core.cache import cache
    if not cache.add(f'kvitansiya:sms:{k.pk}', 1, 60):
        return Response({'detail': _('Qayta yuborish uchun 60 soniya kuting')}, status=429)
    try:
        ok = x.kvitansiya_sms(k)
    except x.HujjatXato as e:
        return _xato(e)
    return Response(dict(_kv(k), sms_yuborildi=ok))


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def kvitansiya_bekor(request, pk):
    """Kvitansiyani bekor qilish (xato kiritilgan bo'lsa). Faqat administrator, sabab bilan."""
    if not _adminmi(request):
        return _ruxsat_yoq()
    sabab = str(request.data.get('sabab') or '').strip()[:255]
    if not sabab:
        return Response({'detail': _('Bekor qilish sababini yozing')}, status=400)
    soni = Kvitansiya.objects.filter(pk=pk, holat='amal').update(
        holat='bekor', bekor_sababi=sabab, bekor_vaqti=timezone.now(), bekor_qilgan=request.user)
    if not soni:
        return Response({'detail': _('Kvitansiya topilmadi yoki allaqachon bekor qilingan')}, status=404)
    k = Kvitansiya.objects.get(pk=pk)
    audit_yoz(request, 'kvitansiya_bekor', f'{k.raqam} — {sabab}')
    return Response(_kv(k))


# ───────────── Shartnoma ─────────────

@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def shartnomalar(request):
    if request.method == 'GET':
        if _adminmi(request):
            qs, limit = Shartnoma.objects.all(), LIMIT_ADMIN
        elif _xodimmi(request):
            qs, limit = Shartnoma.objects.filter(xodim=request.user), LIMIT_XODIM
        else:
            return _ruxsat_yoq()
        return Response([_sh(s) for s in qs[:limit]])

    if not (_adminmi(request) or _xodimmi(request)):
        return _ruxsat_yoq()
    try:
        b = Buyurtma.objects.get(pk=int(request.data.get('buyurtma')))
    except (Buyurtma.DoesNotExist, TypeError, ValueError):
        return Response({'detail': _('Buyurtma topilmadi')}, status=404)
    if not _buyurtma_ruxsati(request, b):
        return _ruxsat_yoq()

    d = request.data
    ism = d.get('mijoz_ism') or b.mijoz_ism
    telefon = d.get('mijoz_telefon') or b.mijoz_telefon
    manzil = d.get('manzil') or x.buyurtma_manzili(b)
    try:
        s, yangi = x.shartnoma_yarat(request.user, b, ism, telefon, manzil)
    except x.HujjatXato as e:
        return _xato(e)
    if yangi:
        audit_yoz(request, 'shartnoma_tuzildi', f'{s.raqam}: buyurtma #{b.pk}, {s.summa} so\'m, {s.mijoz_ism}')
    return Response(_sh(s), status=201 if yangi else 200)


def _shartnoma_olish(request, pk):
    """(shartnoma, xato_javob). Ruxsat: tayinlangan faol xodim yoki administrator."""
    try:
        s = Shartnoma.objects.select_related('buyurtma').get(pk=pk)
    except Shartnoma.DoesNotExist:
        return None, Response({'detail': _('Shartnoma topilmadi')}, status=404)
    if not _buyurtma_ruxsati(request, s.buyurtma):
        return None, _ruxsat_yoq()
    return s, None


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def shartnoma_kod(request, pk):
    s, xato = _shartnoma_olish(request, pk)
    if xato:
        return xato
    try:
        x.kod_yubor(s)
    except x.HujjatXato as e:
        return _xato(e)
    s.refresh_from_db()
    return Response(_sh(s))


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def shartnoma_tasdiq(request, pk):
    s, xato = _shartnoma_olish(request, pk)
    if xato:
        return xato
    try:
        x.kod_tekshir(s, request.data.get('kod'))
    except x.HujjatXato as e:
        return _xato(e)
    audit_yoz(request, 'shartnoma_tasdiq', f'{s.raqam}: mijoz SMS kod bilan tasdiqladi')
    s.refresh_from_db()
    return Response(_sh(s))


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def shartnoma_qogoz(request, pk):
    """Shartnoma qog'ozga imzolangan deb belgilanadi (SMS kodsiz)."""
    s, xato = _shartnoma_olish(request, pk)
    if xato:
        return xato
    if s.tasdiqlanganmi or s.holat == 'bekor':
        return Response({'detail': _('Bu shartnoma allaqachon yakunlangan')}, status=409)
    s.holat = 'qogoz'
    s.tasdiq_vaqti = timezone.now()
    s.kod_xesh = ''
    s.save(update_fields=['holat', 'tasdiq_vaqti', 'kod_xesh'])
    audit_yoz(request, 'shartnoma_tasdiq', f"{s.raqam}: qog'ozga imzolandi")
    return Response(_sh(s))


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def shartnoma_bekor(request, pk):
    """Xodim faqat hali tasdiqlanmagan shartnomani bekor qila oladi; administrator istaganini."""
    s, xato = _shartnoma_olish(request, pk)
    if xato:
        return xato
    if s.holat == 'bekor':
        return Response({'detail': _('Shartnoma allaqachon bekor qilingan')}, status=409)
    if s.tasdiqlanganmi and not _adminmi(request):
        return Response({'detail': _("Tasdiqlangan shartnomani faqat administrator bekor qila oladi")}, status=403)
    sabab = str(request.data.get('sabab') or '').strip()[:255]
    if not sabab:
        return Response({'detail': _('Bekor qilish sababini yozing')}, status=400)
    s.holat, s.bekor_sababi, s.bekor_vaqti, s.kod_xesh = 'bekor', sabab, timezone.now(), ''
    s.save(update_fields=['holat', 'bekor_sababi', 'bekor_vaqti', 'kod_xesh'])
    audit_yoz(request, 'shartnoma_bekor', f'{s.raqam} — {sabab}')
    return Response(_sh(s))


# ───────────── Ochiq sahifalar (mijozga SMS bilan boradigan havola) ─────────────
# Havola tasodifiy 16 belgili maxfiy kod bilan: faqat SMS olgan mijoz va xodim ochadi.
# Qidiruv tizimlariga yopiq va keshlanmaydi.

def _yopiq(javob):
    javob['Cache-Control'] = 'no-store'
    javob['X-Robots-Tag'] = 'noindex, nofollow'
    javob['Referrer-Policy'] = 'no-referrer'
    return javob


def kvitansiya_sahifa(request, token):
    try:
        k = Kvitansiya.objects.select_related('xodim').get(token=token)
    except Kvitansiya.DoesNotExist:
        raise Http404
    mahalliy = timezone.localtime(k.yaratilgan)

    def narx(dan, gacha):
        return x.pul(dan) if gacha in (None, dan) else f'{x.pul(dan)} – {x.pul(gacha)}'

    # Jadval qatorlari (qog'oz kvitansiyadagidek). Eski kvitansiyalarda snapshot yo'q — bitta qator
    qatorlar = k.qatorlar or [{'nomi': k.ish_turi or "Gaz jihozlariga xizmat ko'rsatish", 'ustun_nomi': '',
                               'raqam': '', 'soni': 1, 'narx_dan': k.summa, 'narx_gacha': None,
                               'jami_dan': k.summa, 'jami_gacha': k.summa}]
    jadval = [{
        'n': i, 'nomi': q['nomi'],
        'raqam': ((q['raqam'] or '') + (f" ({q['ustun_nomi']})" if q['ustun_nomi'] else '')).strip() or '—',
        'soni': q['soni'], 'narx': narx(q['narx_dan'], q['narx_gacha']),
        'jami': narx(q['jami_dan'], q['jami_gacha']),
    } for i, q in enumerate(qatorlar, 1)]
    xizmat_turi = k.ish_turi or ', '.join(q['nomi'] for q in qatorlar[:2])
    return _yopiq(render(request, 'hujjatlar/kvitansiya.html', {
        'k': k, 'sozlama': Sozlama.olish(), 'summa_matn': x.pul(k.summa),
        'summa_sozlar': sozlar.summa_sozlar(k.summa),
        'kun': f'{mahalliy.day:02d}', 'oy': f'{mahalliy.month:02d}', 'yil': mahalliy.year,
        'vaqt': mahalliy.strftime('%H:%M'),
        'jadval': jadval, 'xizmat_turi': xizmat_turi,
        'qisman': bool(k.buyurtma_summa and k.buyurtma_summa != k.summa),
        'buyurtma_summa_matn': x.pul(k.buyurtma_summa) if k.buyurtma_summa else '',
        'xodim_ism': k.xodim.ism or k.xodim.telefon}))


def shartnoma_sahifa(request, token):
    try:
        s = Shartnoma.objects.get(token=token)
    except Shartnoma.DoesNotExist:
        raise Http404
    tasdiq = ''
    if s.holat == 'tasdiqlandi':
        tasdiq = (f"Mijoz shartnomani SMS kod orqali tasdiqladi: "
                  f"{timezone.localtime(s.tasdiq_vaqti).strftime('%d.%m.%Y %H:%M')}, "
                  f"telefon {x.niqoblash(s.mijoz_telefon)}")
    elif s.holat == 'qogoz':
        tasdiq = "Shartnoma qog'ozga imzolangan: " + timezone.localtime(s.tasdiq_vaqti).strftime('%d.%m.%Y %H:%M')
    return _yopiq(render(request, 'hujjatlar/shartnoma.html', {
        's': s, 'sozlama': Sozlama.olish(), 'tasdiq': tasdiq}))
