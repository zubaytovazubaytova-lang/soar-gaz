from datetime import timedelta

from django.conf import settings
from django.core.cache import cache
from django.utils import timezone
from django.utils.translation import gettext as _
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.auth_app.models import Foydalanuvchi, audit_yoz
from .models import Nuqta, Rozilik, Smena, ROZILIK_VERSIYASI


def _xodimmi(request):
    u = request.user
    return getattr(u, 'rol', None) == 'xodim' and getattr(u, 'holat', '') == 'faol'


def _adminmi(request):
    return getattr(request.user, 'rol', None) == 'admin'


def _ip(request):
    return (request.META.get('HTTP_X_FORWARDED_FOR', '').split(',')[0].strip()
            or request.META.get('REMOTE_ADDR') or None)


def _rozilik_bor(xodim):
    return Rozilik.objects.filter(xodim=xodim, versiya=ROZILIK_VERSIYASI).exists()


def _ochiq_smena(xodim):
    """Xodimning ochiq smenasi. Unutilib qolgan smena shu yerda yopiladi —
    kuzatuv hech qachon "abadiy" davom etmasin."""
    smena = Smena.objects.filter(xodim=xodim, tugadi__isnull=True).first()
    if smena is None:
        return None
    chegara = smena.boshlandi + timedelta(hours=settings.JOYLASHUV_SMENA_MAX_SOAT)
    if timezone.now() >= chegara:
        smena.tugadi = chegara
        smena.tugash_sababi = 'avto'
        smena.save(update_fields=['tugadi', 'tugash_sababi'])
        return None
    return smena


def _holat(xodim):
    smena = _ochiq_smena(xodim)
    return {
        'rozilik': _rozilik_bor(xodim),
        'faol': smena is not None,
        'boshlandi': smena.boshlandi if smena else None,
        'oraliq_soniya': settings.JOYLASHUV_MIN_SONIYA,
    }


# ───────────── Xodim tomoni ─────────────

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def smena_holat(request):
    if not _xodimmi(request):
        return Response({'detail': _('Faqat xodim uchun')}, status=403)
    return Response(_holat(request.user))


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def smena_boshlash(request):
    if not _xodimmi(request):
        return Response({'detail': _('Faqat xodim uchun')}, status=403)
    xodim = request.user

    if not _rozilik_bor(xodim):
        if request.data.get('rozilik') is not True:
            return Response(
                {'detail': _('Joylashuvni kuzatishga rozilik berilmagan'),
                 'rozilik_kerak': True}, status=400)
        Rozilik.objects.update_or_create(
            xodim=xodim, defaults={'versiya': ROZILIK_VERSIYASI, 'ip': _ip(request)})
        audit_yoz(request, 'joylashuv_rozilik', f'versiya {ROZILIK_VERSIYASI}')

    if _ochiq_smena(xodim) is None:
        Smena.objects.create(xodim=xodim)
        audit_yoz(request, 'smena_boshlandi')
    return Response(_holat(xodim))


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def smena_tugatish(request):
    if not _xodimmi(request):
        return Response({'detail': _('Faqat xodim uchun')}, status=403)
    smena = _ochiq_smena(request.user)
    if smena is not None:
        smena.tugadi = timezone.now()
        smena.tugash_sababi = 'xodim'
        smena.save(update_fields=['tugadi', 'tugash_sababi'])
        audit_yoz(request, 'smena_tugadi')
    return Response(_holat(request.user))


def _son(qiymat, kichik, katta):
    """float yoki None. bool, NaN va chegaradan tashqari qiymat rad etiladi."""
    if isinstance(qiymat, bool) or qiymat is None:
        return None
    try:
        son = float(qiymat)
    except (TypeError, ValueError):
        return None
    if son != son or not (kichik <= son <= katta):
        return None
    return son


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def nuqta_yubor(request):
    if not _xodimmi(request):
        return Response({'detail': _('Faqat xodim uchun')}, status=403)
    xodim = request.user

    lat = _son(request.data.get('lat'), -90, 90)
    lng = _son(request.data.get('lng'), -180, 180)
    if lat is None or lng is None:
        return Response({'detail': _("Koordinata noto'g'ri")}, status=400)
    aniqlik = _son(request.data.get('aniqlik'), 0, 100000)

    smena = _ochiq_smena(xodim)
    if smena is None:
        # Smena yopiq — joylashuv saqlanmaydi. Mijoz (brauzer) kuzatuvni to'xtatsin.
        return Response({'detail': _('Smena ochiq emas'), 'faol': False}, status=409)

    # Brauzer ko'p nuqta yuborib yubormasin: oraliqdan tezroq kelganini tashlaymiz
    if not cache.add(f'joylashuv:nuqta:{xodim.pk}', 1, settings.JOYLASHUV_MIN_SONIYA):
        return Response({'saqlandi': False}, status=202)

    Nuqta.objects.create(smena=smena, xodim=xodim, lat=lat, lng=lng, aniqlik=aniqlik)
    return Response({'saqlandi': True}, status=201)


# ───────────── Admin tomoni ─────────────

def _korildi_yoz(request, kalit, tafsilot):
    """Kuzatuvni ko'rish jurnalga yoziladi. Xarita har 15 soniyada yangilanadi —
    har so'rovni yozsak jurnal to'lib ketadi, shuning uchun bir admin uchun
    bir xil ko'rish 10 daqiqada bir marta yoziladi."""
    if cache.add(f'joylashuv:korildi:{request.user.pk}:{kalit}', 1, 600):
        audit_yoz(request, 'joylashuv_korildi', tafsilot)


def smenadagilar():
    """Hozir smenada bo'lgan xodimlar va ularning oxirgi nuqtasi (API va Django paneli xaritasi uchun)."""
    hozir = timezone.now()
    aloqa = timedelta(seconds=settings.JOYLASHUV_ALOQA_SONIYA)
    natija = []
    smenalar = (Smena.objects.filter(tugadi__isnull=True).select_related('xodim'))
    for smena in smenalar:
        if _ochiq_smena(smena.xodim) is None:   # muddati o'tgan bo'lsa yopadi
            continue
        oxirgi = smena.nuqtalar.first()
        natija.append({
            'xodim_id': smena.xodim_id,
            'ism': smena.xodim.ism or smena.xodim.telefon,
            'lavozim': smena.xodim.lavozim,
            'telefon': smena.xodim.telefon,
            'smena_boshlandi': smena.boshlandi,
            'lat': oxirgi.lat if oxirgi else None,
            'lng': oxirgi.lng if oxirgi else None,
            'aniqlik': oxirgi.aniqlik if oxirgi else None,
            'oxirgi_vaqt': oxirgi.vaqt if oxirgi else None,
            'aloqada': bool(oxirgi and hozir - oxirgi.vaqt <= aloqa),
        })
    return natija


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def joylashuv_royxat(request):
    """Hozir smenada bo'lgan xodimlar va ularning oxirgi nuqtasi."""
    if not _adminmi(request):
        return Response({'detail': _("Ruxsat yo'q")}, status=403)
    natija = smenadagilar()
    _korildi_yoz(request, 'royxat', 'xarita (smenadagi xodimlar)')
    return Response(natija)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def joylashuv_yol(request, xodim_id):
    """Bitta xodimning so'nggi soatlardagi yo'li (eng ko'pi bilan 24 soat)."""
    if not _adminmi(request):
        return Response({'detail': _("Ruxsat yo'q")}, status=403)

    try:
        xodim = Foydalanuvchi.objects.get(pk=xodim_id, rol='xodim')
    except Foydalanuvchi.DoesNotExist:
        return Response({'detail': _('Xodim topilmadi')}, status=404)

    try:
        soat = int(request.query_params.get('soat', 8))
    except ValueError:
        soat = 8
    soat = max(1, min(soat, 24))

    boshlanish = timezone.now() - timedelta(hours=soat)
    nuqtalar = (Nuqta.objects.filter(xodim=xodim, vaqt__gte=boshlanish)
                .order_by('vaqt').values('lat', 'lng', 'aniqlik', 'vaqt')[:2000])
    _korildi_yoz(request, f'yol{xodim.pk}', f"yo'l: {xodim.ism or xodim.telefon}, {soat} soat")
    return Response({'xodim_id': xodim.pk, 'ism': xodim.ism or xodim.telefon,
                     'nuqtalar': list(nuqtalar)})
