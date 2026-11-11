"""Hujjatlar bilan ishlovchi xodim (kabinet turi «hujjat») uchun API.

Vazifasi: mijozlardan kelgan ishlarni ko'radi (saytning Metrologiya bo'limidan kelgan arizalar va hamma
«Loyihalashtirish» / «Metrologiya» buyurtmalari), QABUL QILINGAN ishlar uchun hujjat tayyorlaydi (fayl yuklaydi)
va tayyor hujjatni mijozga yuboradi — u mijozning kabinetidagi «Hujjatlar»ga tushadi va SMS ketadi.

Boshqa rollar (oddiy xodim, operator, Kadrlar, mijoz, administrator) bu yerga 403 oladi. Narx, summa va
tushum ma'lumoti bu yerda yo'q.
"""
import os
import re
from datetime import timedelta

from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from django.utils.translation import gettext as _
from rest_framework.decorators import api_view, parser_classes, permission_classes
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.auth_app.kabinet_turlari import hujjatchimi
from apps.auth_app.models import audit_yoz
from apps.buyurtmalar.models import Buyurtma
from apps.buyurtmalar.views import _sms_yuborish
from apps.kabinet.models import Bildirishnoma, Hujjat as KabinetHujjat
from apps.tolovlar.models import MetrologiyaArizasi
from .models import HujjatLoyiha
from .xizmat import HujjatXato, mijoz_ochish, mijoz_telefoni, sayt_havolasi

ROYXAT_LIMIT = 200
MAX_FAYL = 30 * 1024 * 1024      # bir martalik yuklash (nginx client_max_body_size shundan katta bo'lishi shart)
FAYL_KENGAYTMALARI = {'.pdf', '.doc', '.docx', '.xls', '.xlsx', '.jpg', '.jpeg', '.png', '.dwg'}
HUJJAT_TURLARI = {'shartnoma': 'Shartnoma', 'sertifikat': 'Metrologik sertifikat', 'hisobot': 'Texnik hisobot',
                  'faktura': 'Hisob-faktura', 'boshqa': 'Boshqa'}

# Qaysi holatda hujjat tayyorlash mumkin ("qabul qilingan ish") va qaysi holat yakuniy
ARIZA_HOLAT = {'yangi': 'Yangi', 'korildi': 'Qabul qilingan', 'boglandi': "Mijoz bilan bog'lanilgan",
               'yakunlandi': 'Yakunlangan', 'bekor': 'Bekor qilingan'}
ARIZA_QABUL = ('korildi', 'boglandi', 'yakunlandi')
ARIZA_YAKUN = ('yakunlandi', 'bekor')
BUYURTMA_HOLAT = {'yangi': 'Yangi', 'qabul': 'Xodim qabul qildi', 'bajarilmoqda': 'Jarayonda',
                  'bajarildi': 'Bajarildi', 'bekor': 'Bekor qilingan'}
BUYURTMA_QABUL = ('qabul', 'bajarilmoqda', 'bajarildi')
BUYURTMA_YAKUN = ('bajarildi', 'bekor')
BUYURTMA_XIZMAT = {'loyiha': 'Loyihalashtirish', 'metrologiya': 'Metrologiya'}
KALIT = re.compile(r'^([ab])(\d+)$')


def _ruxsat_yoq():
    return Response({'detail': _("Bu bo'lim hujjatlar bilan ishlovchi xodim uchun")}, status=403)


def _ism(u):
    return (u.ism or u.telefon) if u else ''


def _hujjat_json(h):
    return {'id': h.id, 'nom': h.nom, 'turi': h.turi, 'turi_nomi': HUJJAT_TURLARI.get(h.turi, h.turi),
            'izoh': h.izoh, 'fayl_nomi': os.path.basename(h.fayl.name) if h.fayl else '',
            'tayyorlagan': _ism(h.tayyorlagan), 'yaratilgan': h.yaratilgan,
            'yuborilgan': h.yuborilgan, 'yuborgan': _ism(h.yuborgan)}


def _ariza_ish(a):
    tafsilot = ' · '.join(x for x in [a.hisoblagich, f'seriya {a.seriya_raqam}' if a.seriya_raqam else '',
                                      f'{a.ornatilgan_yil}-yil' if a.ornatilgan_yil else ''] if x)
    return {
        'kalit': f'a{a.id}', 'tur': 'ariza', 'id': a.id, 'yaratilgan': a.yaratilgan,
        'sarlavha': f'Metrologiya arizasi — {a.xizmat_nomi}', 'tafsilot': tafsilot,
        'mijoz_ism': a.ism, 'mijoz_telefon': a.telefon, 'manzil': a.manzil, 'izoh': a.izoh,
        'holat': a.holat, 'holat_nomi': ARIZA_HOLAT.get(a.holat, a.holat),
        'tayyorlash_mumkin': a.holat in ARIZA_QABUL, 'qabul_qilsa_buladi': a.holat == 'yangi',
        'xodim_ism': '', 'hujjatlar': [_hujjat_json(h) for h in a.hujjat_loyihalari.all()],
    }


def _buyurtma_ish(b):
    return {
        'kalit': f'b{b.id}', 'tur': 'buyurtma', 'id': b.id, 'yaratilgan': b.yaratilgan,
        'sarlavha': f'{BUYURTMA_XIZMAT.get(b.xizmat, b.xizmat)} buyurtmasi', 'tafsilot': '',
        'mijoz_ism': b.mijoz_ism, 'mijoz_telefon': b.mijoz_telefon,
        'manzil': ', '.join(x for x in [b.tuman, b.manzil] if x), 'izoh': b.tavsif,
        'holat': b.holat, 'holat_nomi': BUYURTMA_HOLAT.get(b.holat, b.holat),
        'tayyorlash_mumkin': b.holat in BUYURTMA_QABUL, 'qabul_qilsa_buladi': False,
        'xodim_ism': _ism(b.xodim), 'hujjatlar': [_hujjat_json(h) for h in b.hujjat_loyihalari.all()],
    }


def _bosqich_mosmi(ish, bosqich):
    yangi = ish['holat'] == 'yangi'
    yakun = ish['holat'] in (ARIZA_YAKUN if ish['tur'] == 'ariza' else BUYURTMA_YAKUN)
    if bosqich == 'yangi':
        return yangi
    if bosqich == 'qabul':
        return ish['tayyorlash_mumkin'] and not yakun
    if bosqich == 'tayyor':
        return any(not h['yuborilgan'] for h in ish['hujjatlar'])
    if bosqich == 'yakun':
        return yakun
    if bosqich == 'hammasi':
        return True
    return not yakun                      # 'faol': yangi va qabul qilingan ishlar


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def ishlar(request):
    if not hujjatchimi(request.user):
        return _ruxsat_yoq()

    arizalar = MetrologiyaArizasi.objects.prefetch_related('hujjat_loyihalari__tayyorlagan', 'hujjat_loyihalari__yuborgan')
    buyurtmalar = (Buyurtma.objects.filter(xizmat__in=list(BUYURTMA_XIZMAT))
                   .select_related('xodim').prefetch_related('hujjat_loyihalari__tayyorlagan', 'hujjat_loyihalari__yuborgan'))
    q = (request.query_params.get('q') or '').strip()
    if q:
        son = q.lstrip('#aAbB')
        arizalar = arizalar.filter(Q(ism__icontains=q) | Q(telefon__icontains=q) | Q(manzil__icontains=q)
                                   | (Q(pk=int(son)) if son.isdigit() and q[0] in 'aA#' else Q(pk__in=[])))
        buyurtmalar = buyurtmalar.filter(Q(mijoz_ism__icontains=q) | Q(mijoz_telefon__icontains=q)
                                         | Q(manzil__icontains=q) | Q(tuman__icontains=q)
                                         | (Q(pk=int(son)) if son.isdigit() and q[0] in 'bB#' else Q(pk__in=[])))

    tur = request.query_params.get('tur')
    hammasi = []
    if tur != 'buyurtma':
        hammasi += [_ariza_ish(a) for a in arizalar.order_by('-yaratilgan')[:ROYXAT_LIMIT]]
    if tur != 'ariza':
        hammasi += [_buyurtma_ish(b) for b in buyurtmalar.order_by('-yaratilgan')[:ROYXAT_LIMIT]]

    bosqich = request.query_params.get('bosqich', 'faol')
    royxat = sorted((i for i in hammasi if _bosqich_mosmi(i, bosqich)), key=lambda i: i['yaratilgan'], reverse=True)

    return Response({'xulosa': _xulosa(), 'ishlar': royxat[:ROYXAT_LIMIT],
                     'turlar': [{'kalit': k, 'nomi': n} for k, n in HUJJAT_TURLARI.items()]})


def _xulosa():
    bugun = timezone.localtime().replace(hour=0, minute=0, second=0, microsecond=0)
    return {
        'yangi': MetrologiyaArizasi.objects.filter(holat='yangi').count()
                 + Buyurtma.objects.filter(xizmat__in=list(BUYURTMA_XIZMAT), holat='yangi').count(),
        'qabul': MetrologiyaArizasi.objects.filter(holat__in=('korildi', 'boglandi')).count()
                 + Buyurtma.objects.filter(xizmat__in=list(BUYURTMA_XIZMAT), holat__in=('qabul', 'bajarilmoqda')).count(),
        'tayyor': HujjatLoyiha.objects.filter(yuborilgan__isnull=True).count(),
        'bugun_yuborilgan': HujjatLoyiha.objects.filter(yuborilgan__gte=bugun).count(),
    }


def _tayyor_json(h):
    """Bitta tayyorlangan hujjat + u qaysi ishga va qaysi mijozga tegishli (yuborish bo'limi uchun)."""
    d = _hujjat_json(h)
    if h.ariza_id:
        a = h.ariza
        d.update({'ish_kalit': f'a{a.id}', 'ish_nomi': f'Metrologiya arizasi — {a.xizmat_nomi}',
                  'mijoz_ism': a.ism, 'mijoz_telefon': a.telefon, 'manzil': a.manzil or '',
                  'yuborish_mumkin': True})
    else:
        b = h.buyurtma
        d.update({'ish_kalit': f'b{b.id}', 'ish_nomi': f'{BUYURTMA_XIZMAT.get(b.xizmat, b.xizmat)} buyurtmasi',
                  'mijoz_ism': b.mijoz_ism, 'mijoz_telefon': b.mijoz_telefon,
                  'manzil': ', '.join(x for x in [b.tuman, b.manzil] if x),
                  'yuborish_mumkin': b.mijoz_id is not None})   # mijoz hisobi bo'lmasa kabinetga tushirib bo'lmaydi
    return d


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def tayyor_hujjatlar(request):
    """«Mijozga yuborish» bo'limi: hamma ishlar bo'yicha tayyorlangan hujjatlar ro'yxati.
    ?holat=tayyor (yuborilmagan, standart) | yuborilgan | hammasi; ?q= — hujjat nomi, mijoz ismi yoki telefoni."""
    if not hujjatchimi(request.user):
        return _ruxsat_yoq()
    holat = request.query_params.get('holat', 'tayyor')
    qs = (HujjatLoyiha.objects.select_related('ariza', 'buyurtma', 'tayyorlagan', 'yuborgan')
          .filter(Q(ariza__isnull=False) | Q(buyurtma__xizmat__in=list(BUYURTMA_XIZMAT))))
    if holat == 'tayyor':
        qs = qs.filter(yuborilgan__isnull=True).order_by('yaratilgan')           # eng eskisi birinchi — kutib qolmasin
    elif holat == 'yuborilgan':
        qs = qs.filter(yuborilgan__isnull=False).order_by('-yuborilgan')
    else:
        qs = qs.order_by('-yaratilgan')
    q = (request.query_params.get('q') or '').strip()
    if q:
        qs = qs.filter(Q(nom__icontains=q) | Q(ariza__ism__icontains=q) | Q(ariza__telefon__icontains=q)
                       | Q(buyurtma__mijoz_ism__icontains=q) | Q(buyurtma__mijoz_telefon__icontains=q))
    return Response({'xulosa': _xulosa(), 'hujjatlar': [_tayyor_json(h) for h in qs[:ROYXAT_LIMIT]]})


def _ish_olish(kalit):
    """('ariza'|'buyurtma', obyekt) yoki (None, None)."""
    m = KALIT.match(kalit or '')
    if not m:
        return None, None
    if m.group(1) == 'a':
        return 'ariza', MetrologiyaArizasi.objects.filter(pk=int(m.group(2))).first()
    return 'buyurtma', Buyurtma.objects.filter(pk=int(m.group(2)), xizmat__in=list(BUYURTMA_XIZMAT)).first()


def _ish_javobi(tur, obj):
    if tur == 'ariza':
        obj = MetrologiyaArizasi.objects.prefetch_related('hujjat_loyihalari__tayyorlagan', 'hujjat_loyihalari__yuborgan').get(pk=obj.pk)
        return _ariza_ish(obj)
    obj = (Buyurtma.objects.select_related('xodim')
           .prefetch_related('hujjat_loyihalari__tayyorlagan', 'hujjat_loyihalari__yuborgan').get(pk=obj.pk))
    return _buyurtma_ish(obj)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def ish_holat(request, kalit):
    """Metrologiya arizasi holatini o'zgartirish: qabul qilish, bog'lanildi, yakunlandi, bekor.
    (Buyurtma holatini unga tayinlangan xodim boshqaradi — bu yerda o'zgartirilmaydi.)"""
    if not hujjatchimi(request.user):
        return _ruxsat_yoq()
    tur, obj = _ish_olish(kalit)
    if obj is None:
        return Response({'detail': _('Topilmadi')}, status=404)
    if tur != 'ariza':
        return Response({'detail': _("Buyurtmani unga tayinlangan xodim qabul qiladi va yakunlaydi")}, status=400)
    yangi = request.data.get('holat')
    if yangi not in ('korildi', 'boglandi', 'yakunlandi', 'bekor'):
        return Response({'detail': _("Holat noto'g'ri")}, status=400)
    obj.holat = yangi
    obj.save(update_fields=['holat', 'yangilangan'])
    return Response(_ish_javobi(tur, obj))


@api_view(['POST'])
@permission_classes([IsAuthenticated])
@parser_classes([MultiPartParser, FormParser, JSONParser])
def hujjat_yuklash(request, kalit):
    """Qabul qilingan ish uchun tayyorlangan hujjat faylini yuklash (mijozga hali yuborilmaydi)."""
    if not hujjatchimi(request.user):
        return _ruxsat_yoq()
    tur, obj = _ish_olish(kalit)
    if obj is None:
        return Response({'detail': _('Topilmadi')}, status=404)
    ish = _ish_javobi(tur, obj)
    if not ish['tayyorlash_mumkin']:
        return Response({'detail': _("Hujjat faqat qabul qilingan ish uchun tayyorlanadi. Avval ishni qabul qiling")},
                        status=409)

    fayl = request.FILES.get('fayl')
    if fayl is None:
        return Response({'detail': _('Hujjat faylini tanlang')}, status=400)
    kengaytma = os.path.splitext(fayl.name)[1].lower()
    if kengaytma not in FAYL_KENGAYTMALARI:
        return Response({'detail': _("Fayl turi qabul qilinmaydi. Ruxsat: PDF, Word, Excel, rasm (JPG/PNG), DWG")}, status=400)
    if fayl.size > MAX_FAYL:
        return Response({'detail': _("Fayl juda katta (30 MB dan oshmasin)")}, status=400)
    if fayl.size == 0:
        return Response({'detail': _('Fayl bo\'sh')}, status=400)
    nom = str(request.data.get('nom') or '').strip()[:200] or os.path.splitext(os.path.basename(fayl.name))[0][:200]
    turi = request.data.get('turi')
    turi = turi if turi in HUJJAT_TURLARI else 'boshqa'
    h = HujjatLoyiha.objects.create(
        ariza=obj if tur == 'ariza' else None, buyurtma=obj if tur == 'buyurtma' else None,
        nom=nom, turi=turi, izoh=str(request.data.get('izoh') or '').strip()[:255],
        fayl=fayl, tayyorlagan=request.user)
    return Response({'hujjat': _hujjat_json(h), 'ish': _ish_javobi(tur, obj)}, status=201)


@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def hujjat_ochirish(request, pk):
    """Hali yuborilmagan hujjatni o'chirish (yuborilgan hujjat o'chirilmaydi)."""
    if not hujjatchimi(request.user):
        return _ruxsat_yoq()
    h = HujjatLoyiha.objects.filter(pk=pk).first()
    if h is None:
        return Response({'detail': _('Topilmadi')}, status=404)
    if h.yuborilgan:
        return Response({'detail': _("Mijozga yuborilgan hujjatni o'chirib bo'lmaydi")}, status=409)
    h.fayl.delete(save=False)
    h.delete()
    return Response(status=204)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def hujjat_yuborish(request, pk):
    """Tayyor hujjatni mijozga yuborish: mijoz kabinetidagi «Hujjatlar»ga qo'shiladi, bildirishnoma va SMS ketadi."""
    if not hujjatchimi(request.user):
        return _ruxsat_yoq()
    try:
        with transaction.atomic():
            h = HujjatLoyiha.objects.select_for_update().select_related('ariza', 'buyurtma__mijoz').filter(pk=pk).first()
            if h is None:
                return Response({'detail': _('Topilmadi')}, status=404)
            if h.yuborilgan:
                return Response({'detail': _('Bu hujjat allaqachon mijozga yuborilgan')}, status=409)
            if h.ariza_id:
                a = h.ariza
                mijoz, _yangi = mijoz_ochish(request.user, a.ism, mijoz_telefoni(a.telefon), a.manzil or '')
            else:
                mijoz = h.buyurtma.mijoz
                if mijoz is None:
                    return Response({'detail': _("Buyurtmada mijoz hisobi yo'q — hujjatni yuborib bo'lmaydi")}, status=409)

            kh = KabinetHujjat(mijoz=mijoz, turi=h.turi if h.turi in HUJJAT_TURLARI else 'boshqa', nom=h.nom,
                               izoh=h.izoh, sana=timezone.localdate())
            kh.fayl.name = h.fayl.name             # bir xil fayl; mijoz uni imzolangan havola orqali oladi
            kh.save()
            h.mijoz_hujjati, h.yuborilgan, h.yuborgan = kh, timezone.now(), request.user
            h.save(update_fields=['mijoz_hujjati', 'yuborilgan', 'yuborgan'])
            Bildirishnoma.objects.create(mijoz=mijoz, turi='umumiy', sarlavha=f'Yangi hujjat: {h.nom}',
                                         matn="Hujjatingiz tayyor. Kabinetdagi «Hujjatlar» bo'limidan yuklab oling.")
    except HujjatXato as e:
        return Response({'detail': e.detail}, status=e.status)

    _sms_yuborish(mijoz, f"SOAR GAZ: «{h.nom}» hujjatingiz tayyor. Kabinetda ko'ring: {sayt_havolasi('/kabinet/')}")
    audit_yoz(request, 'hujjat_yuborildi', f'{h.nom} -> {mijoz.ism or mijoz.telefon}')
    tur, obj = ('ariza', h.ariza) if h.ariza_id else ('buyurtma', h.buyurtma)
    return Response({'hujjat': _hujjat_json(h), 'ish': _ish_javobi(tur, obj)})
