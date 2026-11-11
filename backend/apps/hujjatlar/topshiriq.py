"""Ichki topshiriqlar: Ruxsora (Kadrlar) va Nargiza (call center) hujjatlar bilan ishlovchi xodimga (Ferangiz)
topshiriq yuboradi, hujjatchi o'ziga ham vazifa qo'sha oladi va bajargach natija faylini yuklaydi.

Ruxsat: faqat shu uchta kabinet turi (kadrlar / qongiroq / hujjat). Boshqalar 403. Har kim faqat o'zi yuborgan yoki
o'ziga yuborilgan topshiriqni ko'radi. Fayllar tekshiruvli endpoint orqali beriladi (ochiq havola yo'q).
"""
import os
from datetime import date

from django.db.models import Q
from django.http import FileResponse
from django.utils import timezone
from django.utils.translation import gettext as _
from rest_framework.decorators import api_view, parser_classes, permission_classes
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.auth_app.kabinet_turlari import hujjatchimi, qongiroq_huquqi
from apps.auth_app.models import Foydalanuvchi
from .ish import FAYL_KENGAYTMALARI, MAX_FAYL, ROYXAT_LIMIT
from .models import Topshiriq


def _ruxsat_yoq():
    return Response({'detail': _("Bu bo'lim Kadrlar, call center va hujjatlar bilan ishlovchi xodim uchun")}, status=403)


def _qatnashchimi(u):
    return hujjatchimi(u) or qongiroq_huquqi(u)


def _ism(u):
    return (u.ism or u.telefon) if u else ''


def _hujjatchilar():
    return [x for x in Foydalanuvchi.objects.filter(rol='xodim', holat='faol').order_by('ism') if hujjatchimi(x)]


def _json(t, u):
    faol = t.holat in Topshiriq.FAOL
    menga, men_yaratdim = t.kimga_id == u.id, t.kim_id == u.id
    return {
        'id': t.id, 'sarlavha': t.sarlavha, 'matn': t.matn, 'muddat': t.muddat,
        'holat': t.holat, 'holat_nomi': t.get_holat_display(),
        'kim': _ism(t.kim), 'kimga': _ism(t.kimga), 'oziga': t.kim_id == t.kimga_id,
        'menga': menga, 'men_yaratdim': men_yaratdim,
        'kechikkan': bool(faol and t.muddat and t.muddat < timezone.localdate()),
        'fayl_nomi': os.path.basename(t.fayl.name) if t.fayl else '',
        'natija_nomi': os.path.basename(t.natija_fayl.name) if t.natija_fayl else '',
        'natija_izoh': t.natija_izoh, 'yaratilgan': t.yaratilgan, 'bajarilgan': t.bajarilgan,
        'boshlash_mumkin': menga and t.holat == 'yangi',
        'bajarish_mumkin': menga and faol,
        'bekor_mumkin': men_yaratdim and faol,
    }


def _fayl_xatosi(fayl):
    """Yuklanayotgan fayl yaroqsiz bo'lsa — xato Response, aks holda None."""
    if os.path.splitext(fayl.name)[1].lower() not in FAYL_KENGAYTMALARI:
        return Response({'detail': _("Fayl turi qabul qilinmaydi. Ruxsat: PDF, Word, Excel, rasm (JPG/PNG), DWG")}, status=400)
    if fayl.size > MAX_FAYL:
        return Response({'detail': _("Fayl juda katta (30 MB dan oshmasin)")}, status=400)
    if fayl.size == 0:
        return Response({'detail': _("Fayl bo'sh")}, status=400)
    return None


@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
@parser_classes([MultiPartParser, FormParser, JSONParser])
def topshiriqlar(request):
    """GET — o'zi yuborgan va o'ziga yuborilgan topshiriqlar (?holat=faol|yopiq|hammasi);
    POST — yangi topshiriq: Kadrlar/call center hujjatchiga (`kimga`), hujjatchi esa o'ziga."""
    u = request.user
    if not _qatnashchimi(u):
        return _ruxsat_yoq()

    if request.method == 'POST':
        return _yaratish(request)

    holat = request.query_params.get('holat', 'faol')
    qs = Topshiriq.objects.filter(Q(kimga=u) | Q(kim=u)).select_related('kim', 'kimga')
    if holat == 'faol':
        qs = qs.filter(holat__in=Topshiriq.FAOL)
    elif holat == 'yopiq':
        qs = qs.exclude(holat__in=Topshiriq.FAOL)
    royxat = [_json(t, u) for t in qs[:ROYXAT_LIMIT]]
    mening = Topshiriq.objects.filter(kimga=u)
    xulosa = {
        'yangi': mening.filter(holat='yangi').count(),
        'jarayonda': mening.filter(holat='jarayonda').count(),
        'kechikkan': mening.filter(holat__in=Topshiriq.FAOL, muddat__lt=timezone.localdate()).count(),
        'yuborganlarim_faol': Topshiriq.objects.filter(kim=u, holat__in=Topshiriq.FAOL).exclude(kimga=u).count(),
    }
    kimlar = [{'id': x.id, 'ism': _ism(x), 'lavozim': x.lavozim} for x in _hujjatchilar()] if qongiroq_huquqi(u) else []
    return Response({'xulosa': xulosa, 'topshiriqlar': royxat, 'kimlar': kimlar, 'oziga_yozadi': hujjatchimi(u)})


def _yaratish(request):
    u = request.user
    sarlavha = str(request.data.get('sarlavha') or '').strip()[:200]
    if not sarlavha:
        return Response({'detail': _('Topshiriq nomini yozing')}, status=400)
    matn = str(request.data.get('matn') or '').strip()
    if len(matn) > 2000:
        return Response({'detail': _("Tafsilot 2000 belgidan oshmasin")}, status=400)

    muddat = None
    m = str(request.data.get('muddat') or '').strip()
    if m:
        try:
            muddat = date.fromisoformat(m)
        except ValueError:
            return Response({'detail': _("Muddat sanasi noto'g'ri")}, status=400)
        if muddat < timezone.localdate():
            return Response({'detail': _("Muddat o'tib ketgan sana bo'lmasin")}, status=400)

    if hujjatchimi(u):
        kimga = u                                   # hujjatchi faqat o'ziga vazifa yozadi
    else:
        tanlangan = str(request.data.get('kimga') or '')
        kimga = next((x for x in _hujjatchilar() if str(x.id) == tanlangan), None)
        if kimga is None:
            return Response({'detail': _("Topshiriq kimga yuborilishini tanlang")}, status=400)

    fayl = request.FILES.get('fayl')
    if fayl is not None:
        xato = _fayl_xatosi(fayl)
        if xato:
            return xato
    t = Topshiriq.objects.create(sarlavha=sarlavha, matn=matn, muddat=muddat, kim=u, kimga=kimga,
                                 **({'fayl': fayl} if fayl is not None else {}))
    return Response(_json(t, u), status=201)


def _olish(request, pk):
    """(topshiriq, None) yoki (None, xato Response): faqat qatnashuvchi (yuborgan yoki oluvchi) ko'radi."""
    if not _qatnashchimi(request.user):
        return None, _ruxsat_yoq()
    t = (Topshiriq.objects.select_related('kim', 'kimga')
         .filter(Q(kimga=request.user) | Q(kim=request.user), pk=pk).first())
    if t is None:
        return None, Response({'detail': _('Topilmadi')}, status=404)
    return t, None


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def holat(request, pk):
    """'jarayonda' — oluvchi boshladi; 'bekor' — topshiriqni yuboruvchi bekor qildi (bajarilmagan bo'lsa)."""
    t, xato = _olish(request, pk)
    if xato:
        return xato
    yangi = request.data.get('holat')
    if yangi == 'jarayonda':
        if t.kimga_id != request.user.id:
            return Response({'detail': _("Topshiriqni faqat oluvchi boshlaydi")}, status=403)
        if t.holat != 'yangi':
            return Response({'detail': _("Topshiriq allaqachon boshlangan yoki yopilgan")}, status=409)
    elif yangi == 'bekor':
        if t.kim_id != request.user.id:
            return Response({'detail': _("Topshiriqni faqat yuborgan kishi bekor qiladi")}, status=403)
        if t.holat not in Topshiriq.FAOL:
            return Response({'detail': _("Yopilgan topshiriqni bekor qilib bo'lmaydi")}, status=409)
    else:
        return Response({'detail': _("Holat noto'g'ri")}, status=400)
    t.holat = yangi
    t.save(update_fields=['holat'])
    return Response(_json(t, request.user))


@api_view(['POST'])
@permission_classes([IsAuthenticated])
@parser_classes([MultiPartParser, FormParser, JSONParser])
def bajarildi(request, pk):
    """Oluvchi topshiriqni bajardi: ixtiyoriy natija fayli va izoh bilan."""
    t, xato = _olish(request, pk)
    if xato:
        return xato
    if t.kimga_id != request.user.id:
        return Response({'detail': _("Topshiriqni faqat oluvchi bajaradi")}, status=403)
    if t.holat not in Topshiriq.FAOL:
        return Response({'detail': _("Bu topshiriq allaqachon yopilgan")}, status=409)
    fayl = request.FILES.get('natija_fayl')
    if fayl is not None:
        xato = _fayl_xatosi(fayl)
        if xato:
            return xato
        t.natija_fayl = fayl
    t.natija_izoh = str(request.data.get('natija_izoh') or '').strip()[:255]
    t.holat, t.bajarilgan = 'bajarildi', timezone.now()
    t.save()
    return Response(_json(t, request.user))


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def fayl_olish(request, pk, tur):
    """Biriktirilgan fayl (`tur=topshiriq`) yoki natija fayli (`tur=natija`) — faqat yuborgan va oluvchi."""
    t, xato = _olish(request, pk)
    if xato:
        return xato
    fayl = {'topshiriq': t.fayl, 'natija': t.natija_fayl}.get(tur)
    if not fayl:
        return Response({'detail': _('Fayl topilmadi')}, status=404)
    javob = FileResponse(fayl.open('rb'), as_attachment=True, filename=os.path.basename(fayl.name))
    javob['X-Content-Type-Options'] = 'nosniff'
    javob['Cache-Control'] = 'private, no-store'
    return javob
