"""Kadrlar bo'yicha mutaxassis kabineti uchun API.

  * `hisobot/`  — HAR BIR faol xodim o'z bugungi hisobotini kiritadi;
  * `kun/`, `eslatma/`, `hujjatlar/` — faqat Kadrlar mutaxassisi (yozish) va
    administrator (faqat o'qish). Boshqa xodim va mijoz 403 oladi.
"""
from datetime import date, datetime, timedelta

from django.conf import settings
from django.core.cache import cache
from django.utils import timezone
from django.utils.translation import gettext as _
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.aloqa.models import Xabar
from apps.auth_app.kabinet_turlari import KADRLAR, kabinet_turi, kadrmi
from apps.auth_app.kabinet_turlari import faol_xodimmi as _faol_xodim
from apps.auth_app.models import Foydalanuvchi
from apps.joylashuv.models import Smena
from .models import (HUJJAT_TURLARI, KELMAGAN_SABAB_NOMI, MAJBURIY_HUJJATLAR, DavomatBelgisi, KunlikHisobot,
                     XodimHujjati)

JOY_MAX = 200
ISH_MAX = 500
ESLATMA_MATNI = "Eslatma: bugungi ish hisobotini to'ldiring — qayerda ishlayapsiz va qanday ish qildingiz."
ESLATMA_ORALIQ = 3600     # soniya: bir soatda bir marta




def _korish_ruxsati(user, yozish):
    """O'qish: kadrlar yoki administrator. Yozish: faqat kadrlar."""
    if kadrmi(user):
        return True
    return (not yozish) and getattr(user, 'rol', None) == 'admin'


def _ruxsat_yoq():
    return Response({'detail': _("Bu bo'lim faqat Kadrlar bo'limi uchun")}, status=403)


def _kuzatiladigan_xodimlar():
    """Davomat/hisobot nazorati ostidagi xodimlar: faol, Kadrlar mutaxassislaridan tashqari."""
    return [x for x in Foydalanuvchi.objects.filter(rol='xodim', holat='faol').order_by('ism', 'telefon')
            if kabinet_turi(x.lavozim) != KADRLAR]


# ───────────── Xodim: o'z kunlik hisoboti ─────────────

def _hisobot_json(h):
    return None if h is None else {'sana': h.sana, 'joy': h.joy, 'ish': h.ish, 'yangilangan': h.yangilangan}


@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def hisobot_xodim(request):
    """GET — bugungi hisobot (yo'q bo'lsa null). POST {joy, ish} — bugungisini saqlaydi/yangilaydi."""
    if not _faol_xodim(request.user):
        return Response({'detail': _('Faqat xodimlar uchun')}, status=403)
    bugun = timezone.localdate()

    if request.method == 'GET':
        return Response({'sana': bugun, 'hisobot': _hisobot_json(
            KunlikHisobot.objects.filter(xodim=request.user, sana=bugun).first())})

    joy = str(request.data.get('joy') or '').strip()
    ish = str(request.data.get('ish') or '').strip()
    if not joy or not ish:
        return Response({'detail': _('Qayerda ishlaganingiz va qanday ish qilganingizni yozing')}, status=400)
    if len(joy) > JOY_MAX or len(ish) > ISH_MAX:
        return Response({'detail': _('Matn juda uzun (joy %(j)s, ish %(i)s belgigacha)')
                         % {'j': JOY_MAX, 'i': ISH_MAX}}, status=400)
    h, _yangi = KunlikHisobot.objects.update_or_create(
        xodim=request.user, sana=bugun, defaults={'joy': joy, 'ish': ish})
    return Response({'sana': bugun, 'hisobot': _hisobot_json(h)})


# ───────────── Kadrlar: davomat va hisobotlar ─────────────

def _sana_param(request):
    """?sana=YYYY-MM-DD (bo'sh bo'lsa — bugun). Kelajak sana ham, noto'g'ri format ham rad etiladi."""
    xom = request.query_params.get('sana')
    if not xom:
        return timezone.localdate(), None
    try:
        sana = date.fromisoformat(xom)
    except ValueError:
        return None, Response({'detail': _("Sana noto'g'ri (YYYY-MM-DD)")}, status=400)
    if sana > timezone.localdate():
        return None, Response({'detail': _("Kelajak sanasi uchun ma'lumot yo'q")}, status=400)
    return sana, None


def _kun_oraligi(sana):
    boshi = timezone.make_aware(datetime.combine(sana, datetime.min.time()))
    return boshi, boshi + timedelta(days=1)


def _belgi_json(b):
    if b is None:
        return None
    return {'holat': b.holat, 'sabab': b.sabab, 'sabab_nomi': KELMAGAN_SABAB_NOMI.get(b.sabab, ''), 'izoh': b.izoh,
            'belgilagan': (b.belgilagan.ism or b.belgilagan.telefon) if b.belgilagan_id else '',
            'vaqt': b.yangilangan}


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def kun_korinishi(request):
    """Tanlangan kun uchun har bir xodim bo'yicha: keldimi, qachon, necha soat, qanday hisobot berdi."""
    if not _korish_ruxsati(request.user, yozish=False):
        return _ruxsat_yoq()
    sana, xato = _sana_param(request)
    if xato:
        return xato

    xodimlar = _kuzatiladigan_xodimlar()
    boshi, oxiri = _kun_oraligi(sana)
    hozir = timezone.now()
    max_soat = timedelta(hours=settings.JOYLASHUV_SMENA_MAX_SOAT)

    smenalar = {}
    for s in Smena.objects.filter(boshlandi__gte=boshi, boshlandi__lt=oxiri).order_by('boshlandi'):
        smenalar.setdefault(s.xodim_id, []).append(s)
    hisobotlar = {h.xodim_id: h for h in KunlikHisobot.objects.filter(sana=sana)}
    belgilar = {b.xodim_id: b for b in DavomatBelgisi.objects.filter(sana=sana).select_related('belgilagan')}

    qatorlar = []
    keldi = ishda = hisobotli = 0
    for x in xodimlar:
        royxat = smenalar.get(x.id, [])
        ochiq = False
        jami = timedelta()
        oxirgi_tugadi = None
        for s in royxat:
            if s.tugadi is not None:
                tugadi = s.tugadi
            elif s.boshlandi + max_soat <= hozir:
                tugadi = s.boshlandi + max_soat          # unutilgan smena o'zi yopilgan hisoblanadi
            else:
                tugadi, ochiq = hozir, True              # hozir davom etmoqda
            jami += max(tugadi - s.boshlandi, timedelta())
            oxirgi_tugadi = tugadi
        h = hisobotlar.get(x.id)
        b = belgilar.get(x.id)
        avto = 'ishda' if ochiq else ('keldi' if royxat else 'kelmadi')
        # Kadrlar qo'lda qo'ygan belgi avtomatik natijadan ustun turadi
        if b is not None and b.holat == 'kelmadi':
            holat = 'kelmadi'
        elif b is not None and b.holat == 'keldi':
            holat = 'ishda' if ochiq else 'keldi'
        else:
            holat = avto
        if holat in ('keldi', 'ishda'):
            keldi += 1
        if holat == 'ishda':
            ishda += 1
        if h:
            hisobotli += 1
        qatorlar.append({
            'id': x.id, 'ism': x.ism or x.telefon, 'telefon': x.telefon, 'lavozim': x.lavozim,
            'tuman': x.tuman,
            'holat': holat, 'avto_holat': avto,
            'qolda': _belgi_json(b),
            'qarama': bool(b is not None and b.holat == 'kelmadi' and royxat),   # qo'lda «kelmadi», lekin smena ochgan
            'boshlandi': royxat[0].boshlandi if royxat else None,
            'tugadi': None if ochiq else oxirgi_tugadi,
            'soat': round(jami.total_seconds() / 3600, 1),
            'smena_soni': len(royxat),
            'hisobot': _hisobot_json(h),
        })

    return Response({
        'sana': sana,
        'bugun': sana == timezone.localdate(),
        'xulosa': {'jami': len(xodimlar), 'keldi': keldi, 'ishda': ishda,
                   'kelmadi': len(xodimlar) - keldi, 'qolda': len(belgilar), 'hisobotli': hisobotli,
                   'hisobotsiz': len(xodimlar) - hisobotli},
        'xodimlar': qatorlar,
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def davomat_belgilash(request):
    """Kadrlar mutaxassisi xodimni QO'LDA «keldi» yoki «kelmadi» (sababi bilan) deb belgilaydi, yoki belgini olib tashlaydi.

    {xodim_id, holat: 'keldi' | 'kelmadi' | 'tozala', sana?: 'YYYY-MM-DD' (bo'sh = bugun), sabab?, izoh?}"""
    if not kadrmi(request.user):
        return _ruxsat_yoq()
    d = request.data
    holat = d.get('holat')
    if holat not in ('keldi', 'kelmadi', 'tozala'):
        return Response({'detail': _("Holat noto'g'ri")}, status=400)
    sana = timezone.localdate()
    if d.get('sana'):
        try:
            sana = date.fromisoformat(str(d['sana']))
        except ValueError:
            return Response({'detail': _("Sana noto'g'ri (YYYY-MM-DD)")}, status=400)
        if sana > timezone.localdate():
            return Response({'detail': _("Kelajak sanasiga davomat qo'yib bo'lmaydi")}, status=400)
    try:
        xodim_id = int(d.get('xodim_id'))
    except (TypeError, ValueError):
        return Response({'detail': _('Xodim topilmadi')}, status=404)
    xodim = next((x for x in _kuzatiladigan_xodimlar() if x.id == xodim_id), None)
    if xodim is None:
        return Response({'detail': _('Xodim topilmadi')}, status=404)

    if holat == 'tozala':
        DavomatBelgisi.objects.filter(xodim=xodim, sana=sana).delete()
        return Response({'belgi': None})
    sabab = ''
    if holat == 'kelmadi':
        sabab = d.get('sabab') or 'sababsiz'
        if sabab not in KELMAGAN_SABAB_NOMI:
            return Response({'detail': _("Kelmagan sababi noto'g'ri")}, status=400)
    b, _yangi = DavomatBelgisi.objects.update_or_create(
        xodim=xodim, sana=sana,
        defaults={'holat': holat, 'sabab': sabab, 'izoh': str(d.get('izoh') or '').strip()[:200],
                  'belgilagan': request.user})
    return Response({'belgi': _belgi_json(b)})


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def hisobot_eslatma(request):
    """Bugun hisobot topshirmagan xodimlarga ilovadagi xabar yuboradi (soatiga bir marta)."""
    if not kadrmi(request.user):
        return _ruxsat_yoq()
    if not cache.add(f'kadrlar:eslatma:{request.user.pk}', 1, ESLATMA_ORALIQ):
        return Response({'detail': _("Eslatma yaqinda yuborilgan. Keyinroq urinib ko'ring.")}, status=429)

    topshirgan = set(KunlikHisobot.objects.filter(sana=timezone.localdate()).values_list('xodim_id', flat=True))
    qabulchilar = [x for x in _kuzatiladigan_xodimlar() if x.id not in topshirgan]
    Xabar.objects.bulk_create([Xabar(xodim=x, yuboruvchi=request.user, matn=ESLATMA_MATNI)
                               for x in qabulchilar])
    return Response({'yuborildi': len(qabulchilar)}, status=201)


# ───────────── Kadrlar: xodimlar hujjatlari reestri ─────────────

def _hujjat_json(h):
    return {'id': h.id, 'turi': h.turi, 'raqami': h.raqami, 'sana': h.sana,
            'amal_qiladi': h.amal_qiladi, 'holat': h.holat, 'izoh': h.izoh}


def _sana_yoki_xato(qiymat, maydon, majburiy=False):
    if qiymat in (None, ''):
        return (None, f'{maydon}: sanani kiriting') if majburiy else (None, None)
    try:
        return date.fromisoformat(str(qiymat)), None
    except ValueError:
        return None, f"{maydon}: sana noto'g'ri (YYYY-MM-DD)"


@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def hujjatlar(request):
    if not _korish_ruxsati(request.user, yozish=request.method != 'GET'):
        return _ruxsat_yoq()

    if request.method == 'POST':
        try:
            xodim = Foydalanuvchi.objects.get(pk=int(request.data.get('xodim')), rol='xodim')
        except (TypeError, ValueError, Foydalanuvchi.DoesNotExist):
            return Response({'detail': _('Xodim topilmadi')}, status=400)
        turi = request.data.get('turi')
        if turi not in dict(HUJJAT_TURLARI):
            return Response({'detail': _("Hujjat turi noto'g'ri")}, status=400)
        sana, xato = _sana_yoki_xato(request.data.get('sana') or timezone.localdate().isoformat(), 'Sana', True)
        amal, xato2 = _sana_yoki_xato(request.data.get('amal_qiladi'), 'Amal qilish muddati')
        if xato or xato2:
            return Response({'detail': xato or xato2}, status=400)
        raqami = str(request.data.get('raqami') or '').strip()[:60]
        izoh = str(request.data.get('izoh') or '').strip()[:200]
        h = XodimHujjati.objects.create(xodim=xodim, turi=turi, raqami=raqami, sana=sana,
                                        amal_qiladi=amal, izoh=izoh, kiritgan=request.user)
        return Response(_hujjat_json(h), status=201)

    royxat = {}
    for h in XodimHujjati.objects.all():
        royxat.setdefault(h.xodim_id, []).append(h)
    qatorlar = []
    for x in _kuzatiladigan_xodimlar():
        hujjatlari = royxat.get(x.id, [])
        bor = {h.turi for h in hujjatlari}
        qatorlar.append({
            'id': x.id, 'ism': x.ism or x.telefon, 'lavozim': x.lavozim,
            'ishga_kirgan': x.ishga_kirgan,
            'hujjatlar': [_hujjat_json(h) for h in hujjatlari],
            'yetishmaydi': [k for k in MAJBURIY_HUJJATLAR if k not in bor],
        })
    return Response({
        'turlar': [{'kalit': k, 'nomi': n, 'majburiy': k in MAJBURIY_HUJJATLAR} for k, n in HUJJAT_TURLARI],
        'xodimlar': qatorlar,
    })


@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def hujjat_ochir(request, pk):
    if not kadrmi(request.user):
        return _ruxsat_yoq()
    soni, _qoldiq = XodimHujjati.objects.filter(pk=pk).delete()
    if not soni:
        return Response({'detail': _('Topilmadi')}, status=404)
    return Response(status=204)
