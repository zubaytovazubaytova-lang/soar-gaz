from django.utils.translation import gettext as _
from rest_framework.decorators import api_view, authentication_classes, permission_classes, throttle_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from apps.auth_app.models import Foydalanuvchi
from . import telegram
from .gateway import sms_yubor
from .models import SmsXabar
from .serializers import SmsSerializer


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def sms_list(request):
    user = request.user
    if user.rol == 'admin':
        qs = SmsXabar.objects.select_related('mijoz').order_by('-yaratilgan')[:100]
    else:
        qs = SmsXabar.objects.filter(mijoz=user).order_by('-yaratilgan')
    return Response(SmsSerializer(qs, many=True).data)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def sms_yuborish(request):
    # Ommaviy SMS tarqatish — faqat admin
    if getattr(request.user, 'rol', None) != 'admin':
        return Response({'detail': _("Bu amal uchun ruxsat yo'q")}, status=403)

    matn = request.data.get('matn', '').strip()
    target = request.data.get('target', 'hammaga')
    tuman = request.data.get('tuman', '')

    if not matn:
        return Response({'detail': _('Matn kiritilishi shart')}, status=400)

    mijozlar = Foydalanuvchi.objects.filter(rol='mijoz', holat='faol')
    if target == 'tuman' and tuman:
        mijozlar = mijozlar.filter(tuman=tuman)

    xabarlar = [
        SmsXabar(mijoz=m, matn=matn, yuboruvchi=request.user)
        for m in mijozlar
    ]
    SmsXabar.objects.bulk_create(xabarlar)

    for m in mijozlar:
        sms_yubor(m.telefon, matn)

    return Response({'yuborildi': len(xabarlar)})


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def sms_oqildi(request):
    SmsXabar.objects.filter(mijoz=request.user, oqildi=False).update(oqildi=True)
    return Response({'ok': True})


@api_view(['POST'])
@authentication_classes([])
@permission_classes([AllowAny])
@throttle_classes([])
def telegram_webhook(request):
    """Telegram botga yozilgan xabarlar. Faqat Telegram yuboradi: maxfiy sarlavha bilan tekshiriladi.

    Telegram 200 dan boshqa javobni qayta-qayta yuboradi, shuning uchun to'g'ri sarlavhali
    so'rovga har doim 200 qaytaramiz (ichki xato jurnalga yoziladi)."""
    if not telegram.webhook_sarlavhasi_tugrimi(request.META.get('HTTP_X_TELEGRAM_BOT_API_SECRET_TOKEN')):
        return Response({'detail': "Ruxsat yo'q"}, status=403)
    try:
        telegram.yangilanishni_qayta_ishla(request.data if isinstance(request.data, dict) else {})
    except Exception:
        import logging
        logging.getLogger(__name__).exception('Telegram yangilanishini qayta ishlashda xato')
    return Response({'ok': True})
