"""Kadrlar mutaxassisi (Ruxsora): xodimlar ma'lumotlarini kiritadi.

- ishga kirgan sana va tabel raqami;
- sertifikatlar (nomi, raqami, berilgan sana, amal qilish muddati).

Xodim bularni o'z kabinetida («Sertifikatlarim», profil) faqat o'qiydi.
Oylik ish haqini Kadrlar KIRITMAYDI va KO'RMAYDI — uni faqat tizim egasi Django panelida kiritadi
(rahbariyat qarori). Har bir o'zgarish Faoliyat jurnaliga yoziladi.
"""
import datetime

from django.utils.translation import gettext as _
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.auth_app.kabinet_turlari import kadrmi
from apps.auth_app.models import Foydalanuvchi, Sertifikat, audit_yoz

def _ruxsat_yoq():
    return Response({'detail': _("Faqat Kadrlar mutaxassisi uchun")}, status=403)


def _xodim(pk):
    return Foydalanuvchi.objects.filter(pk=pk, rol='xodim', holat='faol').first()


def _sana(qiymat):
    if qiymat in (None, ''):
        return None, None
    try:
        return datetime.date.fromisoformat(str(qiymat)), None
    except ValueError:
        return None, Response({'detail': _("Sana noto'g'ri")}, status=400)


def _sert_json(s):
    return {'id': s.id, 'nomi': s.nomi, 'raqami': s.raqami, 'berilgan': s.berilgan,
            'amal_qiladi': s.amal_qiladi, 'holat': s.holat}



@api_view(['GET'])
@permission_classes([IsAuthenticated])
def xodimlar(request):
    """GET — faol xodimlar ro'yxati va ma'lumotlar to'liqligi."""
    if not kadrmi(request.user):
        return _ruxsat_yoq()
    royxat = (Foydalanuvchi.objects.filter(rol='xodim', holat='faol')
              .prefetch_related('sertifikatlar').order_by('ism', 'telefon'))
    javob = []
    for x in royxat:
        sertlar = list(x.sertifikatlar.all())
        javob.append({
            'id': x.id, 'ism': x.ism or x.telefon, 'telefon': x.telefon, 'lavozim': x.lavozim,
            'ishga_kirgan': x.ishga_kirgan, 'tabel_raqam': x.tabel_raqam,
            'sertifikat_soni': len(sertlar),
            'sertifikat_ogoh': sum(1 for s in sertlar if s.holat in ('yaqin', 'tugagan')),
        })
    return Response(javob)


@api_view(['GET', 'PATCH'])
@permission_classes([IsAuthenticated])
def xodim(request, pk):
    """GET — xodimning kartasi (sertifikatlar). PATCH {ishga_kirgan, tabel_raqam}."""
    if not kadrmi(request.user):
        return _ruxsat_yoq()
    x = _xodim(pk)
    if x is None:
        return Response({'detail': _('Xodim topilmadi')}, status=404)
    if request.method == 'PATCH':
        maydonlar = []
        if 'ishga_kirgan' in request.data:
            sana, xato = _sana(request.data.get('ishga_kirgan'))
            if xato:
                return xato
            x.ishga_kirgan = sana
            maydonlar.append('ishga_kirgan')
        if 'tabel_raqam' in request.data:
            x.tabel_raqam = str(request.data.get('tabel_raqam') or '').strip()[:20]
            maydonlar.append('tabel_raqam')
        if maydonlar:
            x.save(update_fields=maydonlar)
            audit_yoz(request, 'kadr_malumot', f"{x.ism or x.telefon}: ishga kirgan / tabel raqami yangilandi")
    return Response({
        'id': x.id, 'ism': x.ism or x.telefon, 'telefon': x.telefon, 'lavozim': x.lavozim,
        'ishga_kirgan': x.ishga_kirgan, 'tabel_raqam': x.tabel_raqam,
        'sertifikatlar': [_sert_json(s) for s in x.sertifikatlar.all()],
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def sertifikat_qosh(request, pk):
    if not kadrmi(request.user):
        return _ruxsat_yoq()
    x = _xodim(pk)
    if x is None:
        return Response({'detail': _('Xodim topilmadi')}, status=404)
    nomi = str(request.data.get('nomi') or '').strip()[:200]
    if not nomi:
        return Response({'detail': _('Sertifikat nomini kiriting')}, status=400)
    berilgan, xato = _sana(request.data.get('berilgan'))
    if xato:
        return xato
    amal_qiladi, xato = _sana(request.data.get('amal_qiladi'))
    if xato:
        return xato
    if berilgan and amal_qiladi and amal_qiladi < berilgan:
        return Response({'detail': _("Amal qilish muddati berilgan sanadan oldin bo'lishi mumkin emas")}, status=400)
    s = Sertifikat.objects.create(xodim=x, nomi=nomi, raqami=str(request.data.get('raqami') or '').strip()[:60],
                                  berilgan=berilgan, amal_qiladi=amal_qiladi)
    audit_yoz(request, 'kadr_malumot', f"{x.ism or x.telefon}: sertifikat qo'shildi — {nomi}"[:255])
    return Response(_sert_json(s), status=201)


@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def sertifikat_ochir(request, sid):
    if not kadrmi(request.user):
        return _ruxsat_yoq()
    s = Sertifikat.objects.select_related('xodim').filter(pk=sid, xodim__rol='xodim').first()
    if s is None:
        return Response({'detail': _('Sertifikat topilmadi')}, status=404)
    audit_yoz(request, 'kadr_malumot', f"{s.xodim.ism or s.xodim.telefon}: sertifikat o'chirildi — {s.nomi}"[:255])
    s.delete()
    return Response(status=204)
