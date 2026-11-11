from django.utils import timezone
from django.utils.translation import gettext as _
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.auth_app.models import Foydalanuvchi, audit_yoz
from .models import Xabar

MATN_MAX = 500
XODIM_LIMIT = 30      # xodim bildirishnomalarida eng ko'pi bilan shuncha xabar
ADMIN_LIMIT = 100     # admin tarixida eng ko'pi bilan shuncha qator
MAX_QABULCHI = 200


def _xodimmi(request):
    u = request.user
    return getattr(u, 'rol', None) == 'xodim' and getattr(u, 'holat', '') == 'faol'


def _adminmi(request):
    return getattr(request.user, 'rol', None) == 'admin'


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def xabarlar_xodim(request):
    if not _xodimmi(request):
        return Response({'detail': _('Faqat xodim uchun')}, status=403)
    qs = Xabar.objects.filter(xodim=request.user)
    return Response({
        'oqilmagan': qs.filter(oqilgan__isnull=True).count(),
        'xabarlar': [{
            'id': x.id, 'matn': x.matn, 'yaratilgan': x.yaratilgan,
            'oqilgan': x.oqilgan is not None,
        } for x in qs[:XODIM_LIMIT]],
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def xabarlar_oqildi(request):
    """Xodimning o'z xabarlarini o'qilgan deb belgilaydi (boshqalarniki emas)."""
    if not _xodimmi(request):
        return Response({'detail': _('Faqat xodim uchun')}, status=403)
    Xabar.objects.filter(xodim=request.user, oqilgan__isnull=True).update(oqilgan=timezone.now())
    return Response({'oqilmagan': 0})


@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def xabarlar_admin(request):
    if not _adminmi(request):
        return Response({'detail': _("Ruxsat yo'q")}, status=403)

    if request.method == 'POST':
        matn = str(request.data.get('matn') or '').strip()
        if not matn:
            return Response({'detail': _('Xabar matnini yozing')}, status=400)
        if len(matn) > MATN_MAX:
            return Response({'detail': _('Xabar %(n)s belgidan oshmasligi kerak') % {'n': MATN_MAX}},
                            status=400)

        faol = Foydalanuvchi.objects.filter(rol='xodim', holat='faol')
        if request.data.get('hammasi') is True:
            qabulchilar = list(faol)
        else:
            idlar = request.data.get('xodimlar')
            if not isinstance(idlar, list) or not idlar:
                return Response({'detail': _('Kimga yuborilishini tanlang')}, status=400)
            if len(idlar) > MAX_QABULCHI:
                return Response({'detail': _('Juda ko\'p qabul qiluvchi')}, status=400)
            try:
                idlar = [int(i) for i in idlar]
            except (TypeError, ValueError):
                return Response({'detail': _("Qabul qiluvchi noto'g'ri")}, status=400)
            qabulchilar = list(faol.filter(pk__in=idlar))
            if len(qabulchilar) != len(set(idlar)):
                # Mavjud bo'lmagan, nofaol yoki xodim bo'lmagan id — hech narsa yuborilmaydi
                return Response({'detail': _('Tanlangan xodimlardan biri topilmadi yoki nofaol')},
                                status=400)
        if not qabulchilar:
            return Response({'detail': _('Faol xodim yo\'q')}, status=400)

        Xabar.objects.bulk_create([
            Xabar(xodim=x, yuboruvchi=request.user, matn=matn) for x in qabulchilar])
        audit_yoz(request, 'xabar_yuborildi', f'{len(qabulchilar)} ta xodimga: {matn[:120]}')
        return Response({'yuborildi': len(qabulchilar)}, status=201)

    qs = Xabar.objects.select_related('xodim')[:ADMIN_LIMIT]
    return Response([{
        'id': x.id,
        'xodim_ism': x.xodim.ism or x.xodim.telefon,
        'matn': x.matn,
        'yaratilgan': x.yaratilgan,
        'oqilgan': x.oqilgan,
    } for x in qs])
