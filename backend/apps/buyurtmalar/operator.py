"""Qo'ng'iroq vazifasi uchun API: ariza qabul qilish, xodimga yo'naltirish, nazorat, chiquvchi qo'ng'iroqlar.

Alohida «Call center» yoki «Servis operatori» kabineti yo'q: bu vazifani ikki kishi bajaradi — Kadrlar
mutaxassisi (Ruxsora) va Nargiza (`auth_app/kabinet_turlari.py`, `qongiroq_huquqi`). Ikkalasida IMKONIYAT BIR XIL:
aholi va tashkilot (ulgurji) arizalarini ko'radi, kiritadi, istalgan oddiy xodimga yo'naltiradi, chiquvchi
qo'ng'iroqlar jurnalini yuritadi.

Ular narxlarni, summani, tushumni va hujjatlarni KO'RMAYDI (Kadrlar tushumni o'z bo'limida alohida, o'z huquqi bilan ko'radi).
Boshqa rol (oddiy xodim, Ferangiz, mijoz, administrator) bu yerga 403 oladi.
"""
import math
from datetime import date, timedelta

from django.conf import settings
from django.core.cache import cache
from django.db.models import Count, Q
from django.utils import timezone
from django.utils.translation import gettext as _
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.auth_app.kabinet_turlari import QONGIROQ, qongiroq_huquqi, vazifa_olishi_mumkin
from apps.auth_app.models import Foydalanuvchi, audit_yoz
from apps.hujjatlar.xizmat import HujjatXato, mijoz_ochish, mijoz_telefoni
from apps.joylashuv.models import Smena
from apps.narxnoma.models import TARMOQ_CHOICES, TARMOQ_NOMI
from .models import QONGIROQ_NATIJALARI, SHAXS_CHOICES, Buyurtma, Qongiroq
from .views import _sms_yuborish, xodim_tayinla

FAOL_HOLATLAR = ('yangi', 'qabul', 'bajarilmoqda')
TAYINLASH_MUMKIN = ('yangi', 'qabul')        # bajarilayotgan/yakunlangan ishni operator boshqaga o'tkaza olmaydi
ROYXAT_LIMIT = 200
# Xodimga biriktirilgan, lekin shuncha soat o'tsa ham qabul qilinmagan/boshlanmagan ariza nazoratda «kechikkan»
KECHIKISH_SOAT = 24
# Operator kabinetida nomlar brauzer tiliga qarab o'zgarmasin (XIZMAT_CHOICES tarjima qilinadi)
XIZMAT_NOMLARI = {'loyiha': 'Loyihalashtirish', 'montaj': 'Montaj', 'servis': 'Servis',
                  'uskunalar': 'Uskunalar', 'metrologiya': 'Metrologiya'}
TARMOQLAR = dict(TARMOQ_CHOICES)


def _ruxsat_yoq():
    return Response({'detail': _("Bu bo'lim faqat operatorlar uchun")}, status=403)


def operator_turi(user):
    """Qo'ng'iroq vazifasi bor xodim (Ruxsora, Nargiza) — 'qongiroq'; aks holda None."""
    return QONGIROQ if qongiroq_huquqi(user) else None


def _doira(tur):
    """Operator qaysi arizalarni ko'radi."""
    return Q()             # ikkalasi ham hamma arizani (aholi va ulgurji) ko'radi


def _kechikkan_sharti():
    chegara = timezone.now() - timedelta(hours=KECHIKISH_SOAT)
    return Q(xodim__isnull=False, holat__in=('yangi', 'qabul'), yangilangan__lt=chegara)


def _kechikkanmi(b):
    chegara = timezone.now() - timedelta(hours=KECHIKISH_SOAT)
    return bool(b.xodim_id and b.holat in ('yangi', 'qabul') and b.yangilangan < chegara)


def _ariza_json(b):
    return {
        'id': b.id, 'yaratilgan': b.yaratilgan,
        'xizmat': b.xizmat, 'xizmat_nomi': XIZMAT_NOMLARI.get(b.xizmat, b.xizmat),
        'tarmoq': b.tarmoq, 'tarmoq_nomi': TARMOQ_NOMI.get(b.tarmoq, b.tarmoq),
        'mijoz_ism': b.mijoz_ism, 'mijoz_telefon': b.mijoz_telefon,
        'tuman': b.tuman, 'manzil': b.manzil, 'tavsif': b.tavsif,
        'holat': b.holat, 'holat_nomi': b.get_holat_display(),
        'natija': b.natija, 'yangilangan': b.yangilangan, 'kechikkan': _kechikkanmi(b),
        'lat': b.lat, 'lng': b.lng, 'joy_bor': b.lat is not None and b.lng is not None,
        'xodim_id': b.xodim_id,
        'xodim_ism': (b.xodim.ism or b.xodim.telefon) if b.xodim_id else '',
    }


def _faol_yuk():
    """{xodim_id: hozirgi faol vazifalari soni}"""
    return {r['xodim_id']: r['n'] for r in (
        Buyurtma.objects.filter(holat__in=FAOL_HOLATLAR, xodim__isnull=False)
        .values('xodim_id').annotate(n=Count('id')))}


def _tayinlanadigan_xodimlar():
    """Vazifa biriktirsa bo'ladigan faol xodimlar + ularning hozirgi faol vazifalari soni."""
    soni = _faol_yuk()
    return [{
        'id': x.id, 'ism': x.ism or x.telefon, 'lavozim': x.lavozim, 'tuman': x.tuman,
        'faol_soni': soni.get(x.id, 0),
    } for x in Foydalanuvchi.objects.filter(rol='xodim', holat='faol').order_by('ism', 'telefon')
        if vazifa_olishi_mumkin(x.lavozim)]


@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def arizalar(request):
    tur = operator_turi(request.user)
    if tur is None:
        return _ruxsat_yoq()
    if request.method == 'POST':
        return _ariza_qabul(request, tur)

    qs = (Buyurtma.objects.filter(_doira(tur)).select_related('xodim'))
    # Xulosa filtrdan mustaqil: operator "nechta ariza tayinlanmagan" ni doim ko'rsin
    bugun_boshi = timezone.localtime().replace(hour=0, minute=0, second=0, microsecond=0)
    xulosa = qs.aggregate(
        tayinlanmagan=Count('id', filter=Q(holat='yangi', xodim__isnull=True)),
        faol=Count('id', filter=Q(holat__in=FAOL_HOLATLAR)),
        bugun=Count('id', filter=Q(yaratilgan__gte=bugun_boshi)),
        kechikkan=Count('id', filter=_kechikkan_sharti()),
    )

    filtr = request.query_params.get('holat', 'faol')
    if filtr == 'tayinlanmagan':
        qs = qs.filter(holat='yangi', xodim__isnull=True)
    elif filtr == 'kechikkan':
        qs = qs.filter(_kechikkan_sharti())
    elif filtr == 'faol':
        qs = qs.filter(holat__in=FAOL_HOLATLAR)
    elif filtr in dict(Buyurtma._meta.get_field('holat').choices):
        qs = qs.filter(holat=filtr)
    q = (request.query_params.get('q') or '').strip()
    if q:
        sharti = (Q(mijoz_ism__icontains=q) | Q(mijoz_telefon__icontains=q) | Q(manzil__icontains=q)
                  | Q(tuman__icontains=q))
        if q.lstrip('#').isdigit():
            sharti |= Q(pk=int(q.lstrip('#')))
        qs = qs.filter(sharti)

    return Response({
        'tur': tur,
        'xulosa': xulosa,
        'arizalar': [_ariza_json(b) for b in qs.order_by('-yaratilgan')[:ROYXAT_LIMIT]],
        'xodimlar': _tayinlanadigan_xodimlar(),
    })


def _ariza_qabul(request, tur_operator):
    """Qo'ng'iroq bilan kelgan arizani kiritish (mijoz telefon bo'yicha topiladi yoki ro'yxatga olinadi)."""
    d = request.data
    xizmat = d.get('xizmat')
    if xizmat not in XIZMAT_NOMLARI:
        return Response({'detail': _('Xizmat turini tanlang')}, status=400)
    ism = str(d.get('mijoz_ism') or '').strip()[:100]
    manzil = str(d.get('manzil') or '').strip()[:255]
    tuman = str(d.get('tuman') or '').strip()[:50]
    tavsif = str(d.get('tavsif') or '').strip()[:2000]
    if not ism:
        return Response({'detail': _('Mijoz (yoki tashkilot) nomini kiriting')}, status=400)
    if not manzil:
        return Response({'detail': _('Manzilni kiriting')}, status=400)

    tarmoq = d.get('tarmoq') or 'aholi'
    if tarmoq not in TARMOQLAR:
        return Response({'detail': _("Tarmoq noto'g'ri")}, status=400)

    lat, lng, xato = _koordinata(d)
    if xato:
        return Response({'detail': xato}, status=400)
    yaqin_yuborish = d.get('yaqin_yuborish') is True
    if yaqin_yuborish and lat is None:
        return Response({'detail': _("Eng yaqin xodimni topish uchun xaritadan joyni belgilang")}, status=400)

    xodim = None
    if d.get('xodim_id') not in (None, ''):
        xodim, xato = _xodim_topish(d.get('xodim_id'))
        if xato:
            return xato

    try:
        telefon = mijoz_telefoni(d.get('mijoz_telefon'))
        mijoz, _yangi = mijoz_ochish(request.user, ism, telefon, manzil)
    except HujjatXato as e:
        return Response({'detail': e.detail}, status=e.status)

    b = Buyurtma.objects.create(
        mijoz=mijoz, xizmat=xizmat, tarmoq=tarmoq, mijoz_ism=ism, mijoz_telefon=telefon,
        tuman=tuman, manzil=manzil, tavsif=tavsif, lat=lat, lng=lng)
    audit_yoz(request, 'ariza_qongiroq',
              f"#{b.id} {XIZMAT_NOMLARI[xizmat]}, {TARMOQ_NOMI.get(tarmoq, tarmoq)}: {ism}, {telefon}")
    _sms_yuborish(mijoz, f"Arizangiz qabul qilindi! #{b.id} — {XIZMAT_NOMLARI[xizmat]}. Tez orada bog'lanamiz.")
    yaqin = None
    if xodim is not None:
        xodim_tayinla(request, b, xodim)
    elif yaqin_yuborish:
        yaqin = _eng_yaqinga_yubor(request, b)
    b = Buyurtma.objects.select_related('xodim').get(pk=b.pk)
    javob = _ariza_json(b)
    if yaqin_yuborish:
        javob['yaqin'] = yaqin          # {'yuborildi': bool, 'xodim': ..., 'masofa_km': ...} yoki sabab
    return Response(javob, status=201)


def _xodim_topish(xodim_id):
    """Vazifa biriktirsa bo'ladigan faol xodim. Qaytaradi: (xodim, None) yoki (None, Response)."""
    try:
        x = Foydalanuvchi.objects.get(pk=int(xodim_id), rol='xodim', holat='faol')
    except (TypeError, ValueError, Foydalanuvchi.DoesNotExist):
        return None, Response({'detail': _('Xodim topilmadi yoki faol emas')}, status=404)
    if not vazifa_olishi_mumkin(x.lavozim):
        return None, Response({'detail': _("Bu xodimga vazifa biriktirib bo'lmaydi")}, status=400)
    return x, None


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def ariza_tayinlash(request, pk):
    tur = operator_turi(request.user)
    if tur is None:
        return _ruxsat_yoq()
    try:
        b = Buyurtma.objects.filter(_doira(tur)).get(pk=pk)
    except Buyurtma.DoesNotExist:
        return Response({'detail': _('Ariza topilmadi')}, status=404)
    if b.holat not in TAYINLASH_MUMKIN:
        return Response({'detail': _("Bu ariza allaqachon bajarilmoqda yoki yakunlangan — xodimni almashtirib bo'lmaydi")},
                        status=409)
    xodim, xato = _xodim_topish(request.data.get('xodim_id'))
    if xato:
        return xato
    xodim_tayinla(request, b, xodim)
    return Response(_ariza_json(Buyurtma.objects.select_related('xodim').get(pk=b.pk)))


# ───────────── Chiquvchi qo'ng'iroqlar jurnali ─────────────

QONGIROQ_LIMIT = 100


def _qongiroq_json(q):
    return {
        'id': q.id, 'yaratilgan': q.yaratilgan, 'shaxs': q.shaxs, 'shaxs_nomi': q.get_shaxs_display(),
        'nomi': q.nomi, 'telefon': q.telefon, 'natija': q.natija, 'natija_nomi': q.get_natija_display(),
        'izoh': q.izoh, 'qayta_sana': q.qayta_sana,
        'operator_ism': (q.operator.ism or q.operator.telefon) if q.operator_id else '',
    }


def _qongiroq_yozish(request):
    d = request.data
    shaxs, natija = d.get('shaxs'), d.get('natija')
    nomi = str(d.get('nomi') or '').strip()[:150]
    if shaxs not in dict(SHAXS_CHOICES):
        return Response({'detail': _('Kim bilan gaplashganingizni tanlang (tashkilot yoki shaxs)')}, status=400)
    if natija not in dict(QONGIROQ_NATIJALARI):
        return Response({'detail': _("Qo'ng'iroq natijasini tanlang")}, status=400)
    if not nomi:
        return Response({'detail': _('Tashkilot yoki shaxs nomini kiriting')}, status=400)
    try:
        telefon = mijoz_telefoni(d.get('telefon'))
    except HujjatXato as e:
        return Response({'detail': e.detail}, status=e.status)
    qayta = None
    if d.get('qayta_sana'):
        try:
            qayta = date.fromisoformat(str(d['qayta_sana']))
        except ValueError:
            return Response({'detail': _("Qayta qo'ng'iroq sanasi noto'g'ri")}, status=400)
        if qayta < timezone.localdate():
            return Response({'detail': _("Qayta qo'ng'iroq sanasi o'tib ketgan bo'lmasligi kerak")}, status=400)
    elif natija == 'keyinroq':
        return Response({'detail': _("Qachon qayta qo'ng'iroq qilishni belgilang")}, status=400)
    q = Qongiroq.objects.create(
        operator=request.user, shaxs=shaxs, nomi=nomi, telefon=telefon, natija=natija,
        izoh=str(d.get('izoh') or '').strip()[:300], qayta_sana=qayta)
    return Response(_qongiroq_json(q), status=201)


@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def qongiroqlar(request):
    """Tashkilotlar va fuqarolarga qilingan qo'ng'iroqlar (xizmat taklif qilish). Qo'ng'iroq vazifasi bor xodimlar."""
    if operator_turi(request.user) is None:
        return _ruxsat_yoq()
    if request.method == 'POST':
        return _qongiroq_yozish(request)

    bugun = timezone.localdate()
    qs = Qongiroq.objects.select_related('operator')
    # Qayta qo'ng'iroq kerak bo'lganlar: muddati kelgan va shu raqamga undan keyin yangi qayd yo'q
    qayta = [q for q in qs.filter(natija='keyinroq', qayta_sana__lte=bugun).order_by('qayta_sana')[:50]
             if not Qongiroq.objects.filter(telefon=q.telefon, yaratilgan__gt=q.yaratilgan).exists()]
    return Response({
        'bugun_soni': qs.filter(yaratilgan__date=bugun, operator=request.user).count(),
        'qayta_qilinadigan': [_qongiroq_json(q) for q in qayta],
        'qongiroqlar': [_qongiroq_json(q) for q in qs[:QONGIROQ_LIMIT]],
    })


# ───────────── Eng yaqin xodimni topish va yuborish ─────────────
#
# Ariza joylashuvi (operator xaritadan belgilaydi) va xodimlarning SMENA davomida yuborgan oxirgi nuqtasi
# solishtiriladi. Operatorga xodimning koordinatasi BERILMAYDI — faqat masofa (km) va qachon aniqlangani.
# Har bir qidiruv jurnalga yoziladi (xodimlar joylashuvi kim ko'rgani qayd etiladi — joylashuv/models.py qoidasi).

# O'zbekiston hududi (taxminiy chegara): xaritada tasodifan boshqa mamlakatga bosib yuborishdan saqlaydi
LAT_ORALIQ = (36.0, 46.5)
LNG_ORALIQ = (55.0, 74.5)


def _koordinata(d):
    """(lat, lng, xato). Ikkalasi ham bo'sh bo'lsa — (None, None, None)."""
    lat, lng = d.get('lat'), d.get('lng')
    if lat in (None, '') and lng in (None, ''):
        return None, None, None
    if isinstance(lat, bool) or isinstance(lng, bool):
        return None, None, _("Koordinata noto'g'ri")
    try:
        lat, lng = float(lat), float(lng)
    except (TypeError, ValueError):
        return None, None, _("Koordinata noto'g'ri")
    if not (LAT_ORALIQ[0] <= lat <= LAT_ORALIQ[1] and LNG_ORALIQ[0] <= lng <= LNG_ORALIQ[1]):   # NaN ham shu yerda rad etiladi
        return None, None, _("Belgilangan nuqta O'zbekiston hududidan tashqarida")
    return lat, lng, None


def _masofa_km(lat1, lng1, lat2, lng2):
    """Ikki nuqta orasidagi to'g'ri chiziq masofasi (Haversine), km. Yo'l masofasi emas — taxminiy."""
    r = 6371.0088
    f1, f2 = math.radians(lat1), math.radians(lat2)
    df, dl = f2 - f1, math.radians(lng2 - lng1)
    a = math.sin(df / 2) ** 2 + math.cos(f1) * math.cos(f2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def _yaqin_nomzodlar(b):
    """(nomzodlar, nomalum): masofa bo'yicha tartiblangan va joylashuvi noma'lum xodimlar."""
    hozir = timezone.now()
    yangilik = timedelta(minutes=settings.JOYLASHUV_YAQIN_DAQIQA)
    max_smena = timedelta(hours=settings.JOYLASHUV_SMENA_MAX_SOAT)
    yuk = _faol_yuk()
    chegara = settings.YAQIN_MAX_VAZIFA

    smenada = {}
    for sm in Smena.objects.filter(tugadi__isnull=True, xodim__rol='xodim', xodim__holat='faol'):
        if hozir - sm.boshlandi < max_smena:           # unutilgan (16 soatdan oshgan) smena hisobga olinmaydi
            smenada[sm.xodim_id] = sm

    nomzodlar, nomalum = [], []
    for x in Foydalanuvchi.objects.filter(rol='xodim', holat='faol').order_by('ism', 'telefon'):
        if not vazifa_olishi_mumkin(x.lavozim):
            continue
        asos = {'id': x.id, 'ism': x.ism or x.telefon, 'lavozim': x.lavozim}
        sm = smenada.get(x.id)
        if sm is None:
            nomalum.append({**asos, 'sabab': 'Smenada emas'})
            continue
        n = sm.nuqtalar.first()                          # eng so'nggi nuqta (ordering = -vaqt)
        if n is None or hozir - n.vaqt > yangilik:
            nomalum.append({**asos, 'sabab': "Joylashuvi yangilanmagan"})
            continue
        km = _masofa_km(b.lat, b.lng, n.lat, n.lng)
        faol = yuk.get(x.id, 0)
        nomzodlar.append({**asos, '_km': km, 'masofa_km': round(km, 1), 'faol_soni': faol,
                          'band': faol >= chegara, 'oxirgi_soniya': int((hozir - n.vaqt).total_seconds())})
    nomzodlar.sort(key=lambda r: r['_km'])
    return nomzodlar, nomalum


def _toza(nomzod):
    return {k: v for k, v in nomzod.items() if not k.startswith('_')}


def _eng_yaqinga_yubor(request, b, xodim_id=None):
    """Arizani eng yaqin (yoki ro'yxatdan tanlangan) xodimga biriktiradi. Qaytaradi: natija lug'ati."""
    nomzodlar, _nomalum = _yaqin_nomzodlar(b)
    if xodim_id is not None:
        tanlangan = next((n for n in nomzodlar if n['id'] == xodim_id), None)
        if tanlangan is None:
            return {'yuborildi': False, 'sabab': _("Bu xodimning joylashuvi hozir aniqlanmagan")}
        sabab_matni = ' (yaqin xodimlar ro\'yxatidan tanlandi'
    else:
        tanlangan = next((n for n in nomzodlar if not n['band']), None)
        if tanlangan is None:
            return {'yuborildi': False, 'sabab': (
                _("Smenada joylashuvi aniq xodim topilmadi") if not nomzodlar else
                _("Yaqin xodimlarning hammasi band (%(n)s tadan ortiq faol vazifa)") % {'n': settings.YAQIN_MAX_VAZIFA})}
        sabab_matni = ' (eng yaqin xodim'
    xodim = Foydalanuvchi.objects.get(pk=tanlangan['id'])
    xodim_tayinla(request, b, xodim, f"{sabab_matni}, {tanlangan['masofa_km']} km)")
    return {'yuborildi': True, 'xodim': _toza(tanlangan), 'masofa_km': tanlangan['masofa_km']}


def _ariza_olish(request, pk):
    """(buyurtma, None) yoki (None, Response) — operator doirasidagi arizani topadi."""
    tur = operator_turi(request.user)
    if tur is None:
        return None, _ruxsat_yoq()
    try:
        return Buyurtma.objects.filter(_doira(tur)).get(pk=pk), None
    except Buyurtma.DoesNotExist:
        return None, Response({'detail': _('Ariza topilmadi')}, status=404)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def ariza_joy(request, pk):
    """Arizaning joylashuvini xaritadan belgilash (yoki o'zgartirish)."""
    b, xato = _ariza_olish(request, pk)
    if xato:
        return xato
    lat, lng, xato = _koordinata(request.data)
    if xato or lat is None:
        return Response({'detail': xato or _('Xaritadan joyni belgilang')}, status=400)
    b.lat, b.lng = lat, lng
    b.save(update_fields=['lat', 'lng', 'yangilangan'])
    return Response(_ariza_json(Buyurtma.objects.select_related('xodim').get(pk=b.pk)))


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def ariza_yaqin(request, pk):
    """Ariza joylashuviga eng yaqin xodimlar (masofa bo'yicha). Xodim koordinatasi berilmaydi."""
    b, xato = _ariza_olish(request, pk)
    if xato:
        return xato
    if b.lat is None or b.lng is None:
        return Response({'detail': _('Arizaning joylashuvi belgilanmagan. Xaritadan belgilang.'), 'joy_yoq': True},
                        status=409)
    nomzodlar, nomalum = _yaqin_nomzodlar(b)
    if cache.add(f'yaqin:korildi:{request.user.pk}:{b.pk}', 1, 600):         # xarita kabi: 10 daqiqada bir marta yoziladi
        audit_yoz(request, 'joylashuv_korildi', f'yaqin xodim qidirildi: ariza #{b.id}')
    return Response({
        'ariza_id': b.id, 'lat': b.lat, 'lng': b.lng,
        'nomzodlar': [_toza(n) for n in nomzodlar], 'nomalum': nomalum,
        'chegara': settings.YAQIN_MAX_VAZIFA, 'yangilik_daqiqa': settings.JOYLASHUV_YAQIN_DAQIQA,
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def ariza_yaqin_yuborish(request, pk):
    """Arizani eng yaqin xodimga yuboradi. `xodim_id` berilsa — o'sha (yaqin ro'yxatdagi) xodimga."""
    b, xato = _ariza_olish(request, pk)
    if xato:
        return xato
    if b.lat is None or b.lng is None:
        return Response({'detail': _('Arizaning joylashuvi belgilanmagan. Xaritadan belgilang.'), 'joy_yoq': True},
                        status=409)
    if b.holat not in TAYINLASH_MUMKIN:
        return Response({'detail': _("Bu ariza allaqachon bajarilmoqda yoki yakunlangan — xodimni almashtirib bo'lmaydi")},
                        status=409)
    xodim_id = request.data.get('xodim_id')
    if xodim_id in (None, ''):
        xodim_id = None
    else:
        try:
            xodim_id = int(xodim_id)
        except (TypeError, ValueError):
            return Response({'detail': _('Xodim topilmadi')}, status=404)
    natija = _eng_yaqinga_yubor(request, b, xodim_id)
    if not natija['yuborildi']:
        return Response({'detail': natija['sabab']}, status=409)
    return Response({**natija, 'ariza': _ariza_json(Buyurtma.objects.select_related('xodim').get(pk=b.pk))})


# ───────────── Manzildan koordinata (geokodlash) ─────────────
#
# Operator manzil yozganda xarita o'zi joyni topadi. OpenStreetMap Nominatim ishlatiladi: unga FAQAT manzil matni
# ketadi (mijoz ismi, telefoni emas). Nominatim yozilishga sezgir («Farog'iy» topiladi, «Farobiy» topilmaydi),
# shuning uchun bir necha urinish qilinadi: to'liq manzil -> manzilning birinchi so'zi -> tuman/shahar markazi.
# Natijalar keshlanadi, har bir operator uchun daqiqasiga cheklov bor (Nominatim siyosati: soniyasiga 1 so'rov).
import hashlib
import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request

GEOKOD_KESH_SONIYA = 24 * 3600
GEOKOD_BOSH_KESH_SONIYA = 3600
GEOKOD_DAQIQALIK_LIMIT = 20
GEOKOD_ORALIQ = 1.1            # Nominatim so'rovlari orasidagi eng kam vaqt (soniya)


class GeokodXato(Exception):
    pass


def _apostrof(matn):
    """Turli apostroflar (ʻ ʼ ’ ` ´) bitta ' ga keltiriladi: o'ʻ g' yozilishi farq qilmasin."""
    for belgi in ('ʻ', 'ʼ', '’', '‘', '`', '´'):
        matn = matn.replace(belgi, "'")
    return ' '.join(matn.split())


def _nominatim(sorov):
    """Nominatim'dan [{'nomi', 'lat', 'lng'}, ...] (eng ko'pi bilan 5 ta). Xizmat javob bermasa GeokodXato."""
    oraliq = cache.get('geokod:oxirgi')
    if oraliq is not None:
        kutish = GEOKOD_ORALIQ - (time.time() - oraliq)
        if 0 < kutish <= GEOKOD_ORALIQ:
            time.sleep(kutish)
    cache.set('geokod:oxirgi', time.time(), 10)
    url = settings.GEOKOD_URL + '?' + urllib.parse.urlencode({
        'q': sorov, 'format': 'jsonv2', 'limit': 5, 'countrycodes': 'uz', 'accept-language': 'uz'})
    so_rov = urllib.request.Request(url, headers={'User-Agent': settings.GEOKOD_USER_AGENT})
    try:
        with urllib.request.urlopen(so_rov, timeout=settings.GEOKOD_TIMEOUT) as javob:
            malumot = json.loads(javob.read().decode('utf-8'))
    except (urllib.error.URLError, OSError, ValueError) as e:
        raise GeokodXato(str(e))
    natija = []
    for x in malumot if isinstance(malumot, list) else []:
        try:
            lat, lng = float(x['lat']), float(x['lon'])
        except (KeyError, TypeError, ValueError):
            continue
        if LAT_ORALIQ[0] <= lat <= LAT_ORALIQ[1] and LNG_ORALIQ[0] <= lng <= LNG_ORALIQ[1]:
            natija.append({'nomi': str(x.get('display_name', ''))[:200], 'lat': lat, 'lng': lng})
    return natija


# OSM'da «Buxoro shahri», «Kogon tumani» deb yoziladi: operator yozgan «shahar» / «tumani» kabi umumiy so'zlar
# qidiruvni buzadi (so'z hierarxiyada topilmaydi), shuning uchun tashlab yuboriladi. Uy raqami ham (OSM'da kamdan-kam bor).
UMUMIY_SOZLAR = {'shahar', 'shahri', 'shaxar', 'tumani', 'tuman', 'viloyati', 'viloyat', 'sh', 't', 'city', 'district'}
UY_SOZLARI = {'uy', 'uyi', 'xonadon', 'kv', 'kvartira', 'dom', 'house', '№', '#'}


def _hudud_tozala(tuman):
    sozlar = [x for x in re.split(r'[\s,]+', tuman) if x and x.lower().strip('.') not in UMUMIY_SOZLAR]
    return ' '.join(sozlar)


def _kocha_tozala(manzil):
    sozlar = [x for x in re.split(r'[\s,]+', manzil)
              if x and not re.fullmatch(r'\d+[\w\-/]*', x) and x.lower().strip('.') not in UY_SOZLARI]
    return ' '.join(sozlar)


def manzil_topish(manzil, tuman):
    """{'aniqlik': 'manzil'|'taxminiy'|'hudud'|'yoq', 'natijalar': [...]} — ketma-ket urinishlar:
    1) ko'cha + hudud; 2) ko'chaning birinchi so'zi + hudud (yozilish xatosi bo'lsa); 3) faqat hudud markazi."""
    manzil, tuman = _apostrof(manzil), _apostrof(tuman)
    if 'viloyat' in tuman.lower():          # viloyat o'zi yozilgan ("Samarqand viloyati, Urgut") — o'zgartirilmaydi
        hudud = tuman
    else:
        hudud = ', '.join(x for x in [_hudud_tozala(tuman), settings.GEOKOD_STANDART_HUDUD] if x)
    kocha = _kocha_tozala(manzil) or manzil
    urinishlar = []
    if kocha:
        urinishlar.append(('manzil', f'{kocha}, {hudud}'))
        sozlar = kocha.split()
        if len(sozlar) > 1 and len(sozlar[0]) >= 3:
            urinishlar.append(('taxminiy', f'{sozlar[0].strip(",.")}, {hudud}'))
    urinishlar.append(('hudud', hudud))
    korilgan = set()
    for aniqlik, sorov in urinishlar:
        if sorov.lower() in korilgan:
            continue
        korilgan.add(sorov.lower())
        natija = _nominatim(sorov)
        if natija:
            return {'aniqlik': aniqlik, 'natijalar': natija}
    return {'aniqlik': 'yoq', 'natijalar': []}


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def geokod(request):
    """Manzil matni bo'yicha xaritadagi joy(lar). Ariza kiritayotgan operatorlar uchun."""
    if operator_turi(request.user) is None:
        return _ruxsat_yoq()
    manzil = (request.query_params.get('manzil') or '').strip()[:200]
    tuman = (request.query_params.get('tuman') or '').strip()[:100]
    if len(manzil) < 3:
        return Response({'detail': _("Manzilni kiriting")}, status=400)

    kalit = 'geokod:natija:' + hashlib.sha1(_apostrof(f'{manzil}|{tuman}').lower().encode('utf-8')).hexdigest()
    natija = cache.get(kalit)
    if natija is None:
        # Kesh (bir xil manzilni qayta so'rash) limitga kirmaydi; tashqi xizmatga borish kirishi kerak
        urinish = f'geokod:limit:{request.user.pk}'
        cache.add(urinish, 0, 60)
        try:
            son = cache.incr(urinish)
        except ValueError:
            son = 1
        if son > GEOKOD_DAQIQALIK_LIMIT:
            return Response({'detail': _("Juda ko'p so'rov. Bir daqiqadan keyin urinib ko'ring yoki xaritadan belgilang")},
                            status=429)
        try:
            natija = manzil_topish(manzil, tuman)
        except GeokodXato:
            return Response({'detail': _("Manzil qidirish xizmati hozir javob bermayapti. Joyni xaritadan belgilang")},
                            status=502)
        cache.set(kalit, natija, GEOKOD_KESH_SONIYA if natija['natijalar'] else GEOKOD_BOSH_KESH_SONIYA)
    return Response(natija)
