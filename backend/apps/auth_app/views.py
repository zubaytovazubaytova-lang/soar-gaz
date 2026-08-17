import random
import secrets
import string
from django.conf import settings
from django.core.cache import cache
from django.db.models import Count
from django.utils import timezone
from rest_framework import status, generics
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, AllowAny, SAFE_METHODS
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken

from apps.sms_app.gateway import sms_yubor, sozlanganmi as sms_sozlanganmi
from .hududlar import HUDUDLAR_XARITASI
from .models import Foydalanuvchi, OtpKod, AuditYozuv, audit_yoz, kirish_kodi_yasa
from .serializers import (
    FoydalanuvchiSerializer, XodimSerializer, ProfilSerializer, RoyxatSerializer,
    XodimProfilSerializer, XodimYaratishSerializer, XodimHolatSerializer,
)


def _tokens_for_user(user):
    refresh = RefreshToken.for_user(user)
    return {
        'access': str(refresh.access_token),
        'refresh': str(refresh),
    }


def _admin_tokens(user):
    """Boshqaruv paneli uchun QISQA muddatli token.

    Mijoz sessiyasi bir yil yashaydi (SIMPLE_JWT) — bu ilova qulayligi uchun
    to'g'ri. Admin uchun esa xavfli: o'g'irlangan token uzoq ishlaydi va
    ochiq qolgan kompyuterdan kirish mumkin. Shuning uchun admin tokeni
    ADMIN_SESSIYA_DAQIQA dan keyin kuchini yo'qotadi va uzaytirilmaydi.
    """
    muddat = timezone.timedelta(minutes=settings.ADMIN_SESSIYA_DAQIQA)
    refresh = RefreshToken.for_user(user)
    refresh.set_exp(lifetime=muddat)
    access = refresh.access_token
    access.set_exp(lifetime=muddat)
    return {'access': str(access), 'refresh': str(refresh)}


def _user_data(user):
    return {
        'id': user.id,
        'telefon': user.telefon,
        'ism': user.ism,
        'manzil': user.manzil,
        'viloyat': user.viloyat,
        'tuman': user.tuman,
        'mahalla': user.mahalla,
        'rol': user.rol,
        # Tizim egasi (superuser) va oddiy admin farqi: egasi xodimni nofaol
        # qila oladi, boshqa adminlar (masalan direktor) — yo'q.
        'egasi': bool(user.is_superuser),
        'holat': user.holat,
        'qoshimcha_telefon': user.qoshimcha_telefon,
        'email': user.email,
        'mulk_turi': user.mulk_turi,
        'moljal': user.moljal,
    }


@api_view(['POST'])
@permission_classes([AllowAny])
def admin_login(request):
    """Boshqaruv paneliga kirish — telefon + parol.

    Bu tizimdagi eng yuqori huquqli kirish nuqtasi, shuning uchun cheklov
    qattiq: ADMIN_URINISH_LIMIT ta noto'g'ri parolda hisob 'nofaol' qilinadi
    va O'ZI OCHILMAYDI. Uni faqat tizim egasi Django admin panelidan
    (/admin/auth_app/foydalanuvchi/) qayta faollashtiradi va yangi parol
    beradi. Xabar matni ataylab umumiy ("telefon yoki parol") — qaysi raqam
    admin ekanini oshkor qilmaslik uchun.
    """
    telefon = request.data.get('telefon', '').replace(' ', '')
    parol = request.data.get('parol', '')

    if not telefon or not parol:
        return Response({'detail': 'Telefon va parol kiritilishi shart'}, status=400)

    BLOK_XABAR = ("Hisob bloklandi: juda ko'p noto'g'ri urinish. "
                  "Tizim egasi uni qayta faollashtirib, yangi parol berishi kerak.")

    user = Foydalanuvchi.objects.filter(telefon=telefon, rol='admin').first()

    # Bloklangan hisob — parol to'g'ri bo'lsa ham kiritmaymiz
    if user is not None and user.holat == 'nofaol':
        audit_yoz(request, 'ruxsat_rad', f'Bloklangan hisobga kirishga urinish: {telefon}', user=user)
        return Response({'detail': BLOK_XABAR}, status=403)

    # Hisob topilmasa ham, parol xato bo'lsa ham — bir xil yo'l va bir xil xabar
    if user is None or not user.check_password(parol):
        urinish_kalit = f'admin:urinish:{telefon}'
        urinish = cache.get(urinish_kalit, 0) + 1
        # Kesh o'chib qolsa ham hisoblagich yo'qolmasin — uzoq muddat
        cache.set(urinish_kalit, urinish, 24 * 60 * 60)

        if urinish >= settings.ADMIN_URINISH_LIMIT:
            if user is not None:
                # Haqiqiy hisob — bloklaymiz. Mavjud bo'lmagan raqam uchun
                # bloklaydigan narsa yo'q, shunchaki xabar qaytadi.
                user.holat = 'nofaol'
                user.save(update_fields=['holat'])
            audit_yoz(request, 'kirish_blok',
                      f'{telefon} — {urinish} ta noto\'g\'ri urinish, hisob bloklandi', user=user)
            return Response({'detail': BLOK_XABAR}, status=403)

        qoldi = settings.ADMIN_URINISH_LIMIT - urinish
        audit_yoz(request, 'kirish_xato',
                  f'{telefon} — noto\'g\'ri parol ({urinish}-urinish)', user=user)
        return Response(
            {'detail': f"Telefon yoki parol noto'g'ri! Yana {qoldi} ta urinish qoldi."},
            status=401)

    cache.delete(f'admin:urinish:{telefon}')

    # ── Parol to'g'ri. Ikkinchi bosqich: telefonga SMS kod ──
    if settings.ADMIN_2FA:
        return _admin_2fa_boshla(request, user)

    audit_yoz(request, 'kirish', 'Boshqaruv paneliga kirdi', user=user)
    return Response({
        **_admin_tokens(user),
        'user': _user_data(user),
        'sessiya_daqiqa': settings.ADMIN_SESSIYA_DAQIQA,
    })


def _admin_2fa_boshla(request, user):
    """Parol tekshiruvidan keyin SMS kod yuboradi va vaqtinchalik chipta beradi.

    Chipta (`chipta`) muhim: uholsiz OTP bosqichiga o'tib bo'lmaydi. Ya'ni
    kimdir parolni bilmasdan turib faqat kodni topishga urinolmaydi —
    ikkala bosqich ham majburiy.
    """
    kod = ''.join(random.choices(string.digits, k=6))
    OtpKod.objects.create(telefon=user.telefon, kod=kod)
    yuborildi = _send_otp_sms(user.telefon, kod)

    chipta = secrets.token_urlsafe(24)
    cache.set(f'admin:2fa:{chipta}',
              {'telefon': user.telefon, 'urinish': 0},
              settings.ADMIN_2FA_DAQIQA * 60)

    audit_yoz(request, 'kirish', 'Parol tasdiqlandi, SMS kod yuborildi', user=user)

    javob = {
        'otp_kerak': True,
        'chipta': chipta,
        'telefon_maskasi': _telefon_maskasi(user.telefon),
        'muddat_daqiqa': settings.ADMIN_2FA_DAQIQA,
    }
    # Dev rejimda (SMS provayder ulanmagan) kodni qaytaramiz — aks holda
    # lokal ishlab chiqishda panelga umuman kirib bo'lmaydi. Serverda
    # (DEBUG=False yoki haqiqiy provayder) bu maydon HECH QACHON chiqmaydi.
    if settings.DEBUG and not sms_sozlanganmi():
        javob['dev_kod'] = kod
    if not yuborildi:
        javob['ogohlantirish'] = "SMS yuborilmadi — kodni administratordan so'rang."
    return Response(javob)


def _telefon_maskasi(telefon):
    """+998912466346 -> +998 ** *** 63 46 — qaysi raqamga kod ketganini
    eslatadi, lekin raqamni to'liq oshkor qilmaydi."""
    t = telefon.replace(' ', '')
    return f"{t[:4]} ** *** {t[-4:-2]} {t[-2:]}" if len(t) >= 9 else t


@api_view(['POST'])
@permission_classes([AllowAny])
def admin_otp_tasdiqlash(request):
    """Boshqaruv paneliga kirishning ikkinchi bosqichi — SMS kod.

    Token faqat shu yerdan beriladi: parol bosqichi hech qachon token
    qaytarmaydi (2FA yoqilgan bo'lsa).
    """
    chipta = (request.data.get('chipta') or '').strip()
    kod = (request.data.get('kod') or '').strip()

    if not chipta or not kod:
        return Response({'detail': 'Kod kiritilishi shart'}, status=400)

    kalit = f'admin:2fa:{chipta}'
    holat = cache.get(kalit)
    if not holat:
        return Response(
            {'detail': 'Kod muddati tugadi. Qaytadan kiring.', 'qaytadan': True},
            status=401)

    user = Foydalanuvchi.objects.filter(telefon=holat['telefon'], rol='admin').first()
    if user is None or user.holat == 'nofaol':
        cache.delete(kalit)
        return Response({'detail': 'Hisob mavjud emas yoki bloklangan', 'qaytadan': True}, status=403)

    muddat = timezone.now() - timezone.timedelta(minutes=settings.ADMIN_2FA_DAQIQA)
    otp = (OtpKod.objects
           .filter(telefon=holat['telefon'], ishlatildi=False, yaratilgan__gte=muddat)
           .order_by('-yaratilgan').first())

    if otp is None or not secrets.compare_digest(otp.kod, kod):
        holat['urinish'] += 1
        if holat['urinish'] >= settings.ADMIN_2FA_URINISH:
            cache.delete(kalit)
            audit_yoz(request, 'kirish_blok',
                      'SMS kod bir necha marta xato — kirish bekor qilindi', user=user)
            return Response(
                {'detail': "Kod bir necha marta xato kiritildi. Qaytadan kiring.", 'qaytadan': True},
                status=401)
        cache.set(kalit, holat, settings.ADMIN_2FA_DAQIQA * 60)
        qoldi = settings.ADMIN_2FA_URINISH - holat['urinish']
        audit_yoz(request, 'kirish_xato', "Noto'g'ri SMS kod", user=user)
        return Response({'detail': f"Kod noto'g'ri. Yana {qoldi} ta urinish qoldi."}, status=401)

    # Kod to'g'ri — bir martalik, darhol kuchsizlantiramiz
    otp.ishlatildi = True
    otp.save(update_fields=['ishlatildi'])
    cache.delete(kalit)

    audit_yoz(request, 'kirish', 'Boshqaruv paneliga kirdi (SMS tasdiqlandi)', user=user)
    return Response({
        **_admin_tokens(user),
        'user': _user_data(user),
        'sessiya_daqiqa': settings.ADMIN_SESSIYA_DAQIQA,
    })


@api_view(['POST'])
@permission_classes([AllowAny])
def royxatdan_otish(request):
    """Mijoz ro'yxatdan o'tadi va darhol tizimga kiradi.
    Yaratilgan hisob Django admin panelida (rol='mijoz') ko'rinadi."""
    ser = RoyxatSerializer(data=request.data)
    if not ser.is_valid():
        return Response(ser.errors, status=400)

    user = ser.save()
    tokens = _tokens_for_user(user)
    return Response({**tokens, 'user': _user_data(user)}, status=status.HTTP_201_CREATED)


def _send_otp_sms(telefon, kod):
    """OTP kodni SMS orqali yuboradi (provayder sozlanmagan bo'lsa — log)."""
    return sms_yubor(telefon, f"SOAR GAZ tasdiqlash kodi: {kod}. Hech kimga aytmang.")


def _kesh_kaliti(nom, telefon):
    return f'otp:{nom}:{telefon}'


def _otp_cheklov(telefon):
    """Kod so'rash cheklovlari. Muammo bo'lsa (matn, soniya) qaytaradi."""
    if cache.get(_kesh_kaliti('blok', telefon)):
        return "Juda ko'p urinish. Birozdan keyin qayta urinib ko'ring.", 429

    oxirgi = cache.get(_kesh_kaliti('oxirgi', telefon))
    if oxirgi:
        return f"Yangi kod {settings.OTP_QAYTA_SONIYA} soniyada bir marta yuboriladi.", 429

    soatlik = cache.get(_kesh_kaliti('soatlik', telefon), 0)
    if soatlik >= settings.OTP_SOATLIK_LIMIT:
        cache.set(_kesh_kaliti('blok', telefon), 1, settings.OTP_BLOK_DAQIQA * 60)
        return "Bu raqamga kod yuborish chegarasi tugadi. Keyinroq urinib ko'ring.", 429

    return None, 0


@api_view(['POST'])
@permission_classes([AllowAny])
def otp_yuborish(request):
    telefon = request.data.get('telefon', '').replace(' ', '')
    if not telefon:
        return Response({'detail': 'Telefon raqam kiritilishi shart'}, status=400)

    xato, kod_holat = _otp_cheklov(telefon)
    if xato:
        return Response({'detail': xato}, status=kod_holat)

    # Xodim bloklangan tekshiruvi
    try:
        mavjud = Foydalanuvchi.objects.get(telefon=telefon)
        if mavjud.holat == 'nofaol':
            return Response({'detail': 'Hisobingiz bloklangan. Admin bilan bog\'laning.'}, status=403)
        yangi_mijoz = False
        rol = mavjud.rol
    except Foydalanuvchi.DoesNotExist:
        yangi_mijoz = True
        rol = 'mijoz'

    kod = ''.join(random.choices(string.digits, k=6))
    OtpKod.objects.create(telefon=telefon, kod=kod)

    if not _send_otp_sms(telefon, kod):
        return Response(
            {'detail': "SMS yuborilmadi. Birozdan keyin urinib ko'ring yoki operatorga murojaat qiling."},
            status=502,
        )

    # Cheklov hisoblagichlari
    cache.set(_kesh_kaliti('oxirgi', telefon), 1, settings.OTP_QAYTA_SONIYA)
    soatlik = cache.get(_kesh_kaliti('soatlik', telefon), 0)
    cache.set(_kesh_kaliti('soatlik', telefon), soatlik + 1, 3600)

    return Response({'yuborildi': True, 'yangi_mijoz': yangi_mijoz, 'rol': rol})


@api_view(['POST'])
@permission_classes([AllowAny])
def otp_tasdiqlash(request):
    telefon = request.data.get('telefon', '').replace(' ', '')
    kod = request.data.get('kod', '').strip()

    if not telefon or not kod:
        return Response({'detail': 'Telefon va kod kiritilishi shart'}, status=400)

    if cache.get(_kesh_kaliti('blok', telefon)):
        return Response(
            {'detail': "Juda ko'p noto'g'ri urinish. Birozdan keyin qayta urinib ko'ring."},
            status=429,
        )

    otp = OtpKod.objects.filter(
        telefon=telefon, kod=kod, ishlatildi=False
    ).order_by('-yaratilgan').first()

    if not otp:
        # Noto'g'ri kod — urinishlarni sanaymiz, limitdan oshsa bloklaymiz
        urinish = cache.get(_kesh_kaliti('urinish', telefon), 0) + 1
        cache.set(_kesh_kaliti('urinish', telefon), urinish, settings.OTP_EXPIRE_MINUTES * 60)
        if urinish >= settings.OTP_URINISH_LIMIT:
            cache.set(_kesh_kaliti('blok', telefon), 1, settings.OTP_BLOK_DAQIQA * 60)
            return Response(
                {'detail': "Juda ko'p noto'g'ri urinish. Hisobingiz vaqtincha bloklandi."},
                status=429,
            )
        return Response({'detail': 'Kod noto\'g\'ri!'}, status=400)

    if otp.muddati_utganmi():
        return Response({'detail': 'Kod muddati tugagan. Qayta yuboring.'}, status=400)

    otp.ishlatildi = True
    otp.save()
    cache.delete(_kesh_kaliti('urinish', telefon))

    user, created = Foydalanuvchi.objects.get_or_create(
        telefon=telefon,
        defaults={'rol': 'mijoz'}
    )

    tokens = _tokens_for_user(user)
    return Response({**tokens, 'user': _user_data(user)})


@api_view(['PATCH', 'GET'])
@permission_classes([IsAuthenticated])
def profil(request):
    user = request.user
    if request.method == 'GET':
        return Response(_user_data(user))

    ser = ProfilSerializer(user, data=request.data, partial=True)
    if ser.is_valid():
        ser.save()
        return Response(_user_data(user))
    return Response(ser.errors, status=400)


@api_view(['GET'])
@permission_classes([AllowAny])
def hududlar(request):
    """Viloyat -> tuman/shahar ro'yxati.

    Mobil ilova uchun — veb sahifalarga ro'yxat `hududlar_yangila` buyrug'i
    bilan yoziladi, lekin Flutter ilovasi alohida repoda, shuning uchun u
    ro'yxatni shu yerdan bir marta yuklab oladi. `viloyat`/`tuman` maydonlari
    `ProfilSerializer` da shu ro'yxatga qarab tekshiriladi.
    """
    return Response([
        {'viloyat': viloyat, 'tumanlar': list(tumanlar)}
        for viloyat, tumanlar in HUDUDLAR_XARITASI
    ])


def _xodim_data(user):
    """Xodim portali uchun profil ma'lumotlari."""
    return {
        'id': user.id,
        'telefon': user.telefon,
        'ism': user.ism,
        'lavozim': user.lavozim,
        'viloyat': user.viloyat,
        'tuman': user.tuman,
        'mahalla': user.mahalla,
        'email': user.email,
        'qoshimcha_telefon': user.qoshimcha_telefon,
        'ishga_kirgan': user.ishga_kirgan,
        'holat': user.holat,
    }


@api_view(['POST'])
@permission_classes([AllowAny])
def xodim_login(request):
    """Xodimlar portaliga kirish — telefon + admin bergan KIRISH KODI.

    Xodimda parol yo'q: hisobni admin ochadi va kodni xodimga aytadi. Eski
    parolli hisoblar buzilmasligi uchun parol ham qabul qilinadi — kodi
    berilmagan xodim avvalgidek kira oladi.

    Mijozlardan farqi: xodimga SMS yuborilmaydi, kod doimiy.
    """
    telefon = request.data.get('telefon', '').replace(' ', '')
    # Frontend `kod` yuboradi; `parol` — eski hisoblar uchun zaxira yo'l
    kod = (request.data.get('kod') or '').strip()
    parol = request.data.get('parol', '')

    if not telefon or not (kod or parol):
        return Response({'detail': 'Telefon va kirish kodi kiritilishi shart'},
                        status=400)

    # Kod parolning o'rnini bosadi, shuning uchun taxmin qilishga cheklov
    # qo'yamiz — aks holda 6 belgili kodni avtomat tanlab olish mumkin.
    blok_kalit = f'xodim:blok:{telefon}'
    if cache.get(blok_kalit):
        return Response(
            {'detail': "Juda ko'p noto'g'ri urinish. "
                       f"{settings.OTP_BLOK_DAQIQA} daqiqadan keyin urinib ko'ring."},
            status=429)

    try:
        user = Foydalanuvchi.objects.get(telefon=telefon, rol='xodim')
    except Foydalanuvchi.DoesNotExist:
        # Aniq xabar: xodim qaysi tomonda xato qilganini bilsin. Bu ichki
        # portal — raqamning ro'yxatda borligi maxfiy ma'lumot emas.
        return Response(
            {'detail': 'Bu telefon raqam xodim sifatida ro\'yxatda yo\'q. '
                       'Administrator bilan bog\'laning.'}, status=401)

    # Kodni katta-kichik harfga qaramay solishtiramiz — u og'zaki aytiladi
    kod_togri = bool(user.kirish_kodi) and kod and \
        secrets.compare_digest(kod.upper(), user.kirish_kodi.upper())
    parol_togri = bool(parol) and user.check_password(parol)

    if not (kod_togri or parol_togri):
        urinish_kalit = f'xodim:urinish:{telefon}'
        urinish = cache.get(urinish_kalit, 0) + 1
        cache.set(urinish_kalit, urinish, settings.OTP_BLOK_DAQIQA * 60)
        if urinish >= settings.OTP_URINISH_LIMIT:
            cache.set(blok_kalit, 1, settings.OTP_BLOK_DAQIQA * 60)
            return Response(
                {'detail': "Juda ko'p noto'g'ri urinish. "
                           f"{settings.OTP_BLOK_DAQIQA} daqiqadan keyin urinib ko'ring."},
                status=429)
        qoldi = settings.OTP_URINISH_LIMIT - urinish
        return Response(
            {'detail': f'Kirish kodi noto\'g\'ri. Administratordan kodni '
                       f'tekshirib oling. Yana {qoldi} ta urinish qoldi.'},
            status=401)

    cache.delete(f'xodim:urinish:{telefon}')

    if user.holat == 'nofaol':
        return Response({'detail': 'Hisobingiz bloklangan. Admin bilan bog\'laning.'}, status=403)

    return Response({**_tokens_for_user(user), 'xodim': _xodim_data(user)})


@api_view(['GET', 'PATCH'])
@permission_classes([IsAuthenticated])
def xodim_profil(request):
    """Xodim o'z profilini ko'radi va aloqa ma'lumotlarini yangilaydi.
    Ism/lavozim/tabel raqam admin panelidan boshqariladi — bu yerda o'zgarmaydi."""
    user = request.user
    if user.rol != 'xodim':
        return Response({'detail': 'Faqat xodimlar uchun'}, status=403)

    if request.method == 'GET':
        return Response(_xodim_data(user))

    ser = XodimProfilSerializer(user, data=request.data, partial=True)
    if not ser.is_valid():
        return Response(ser.errors, status=400)
    ser.save()
    return Response(_xodim_data(user))


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def audit_list(request):
    """Faoliyat jurnali — kim, qachon, nima qilgani.

    Faqat o'qish uchun: yozuvni o'zgartirish ham, o'chirish ham mumkin emas.
    Oxirgi 200 ta yozuv beriladi — jurnal cheksiz o'smasin.
    """
    if getattr(request.user, 'rol', None) != 'admin':
        return Response({'detail': 'Ruxsat yo\'q'}, status=403)

    qs = AuditYozuv.objects.select_related('kim')[:200]
    nomlar = dict(AuditYozuv._meta.get_field('amal').choices)
    return Response([{
        'id': y.id,
        'kim': y.kim_ism or y.kim_telefon or 'Noma\'lum',
        'amal': y.amal,
        'amal_nomi': nomlar.get(y.amal, y.amal),
        'tafsilot': y.tafsilot,
        'ip': y.ip,
        'vaqt': y.vaqt,
    } for y in qs])


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def mijozlar_list(request):
    """Boshqaruv paneli uchun mijozlar bazasi (CRM).

    Mijoz saytda ro'yxatdan o'tganda avtomatik paydo bo'ladi — bu ro'yxatga
    qo'lda hech kim yozmaydi. Har bir mijoz uchun buyurtmalar soni ham
    beriladi, panel uni alohida so'rov qilmasin.
    """
    if getattr(request.user, 'rol', None) != 'admin':
        return Response({'detail': 'Ruxsat yo\'q'}, status=403)

    qs = (Foydalanuvchi.objects
          .filter(rol='mijoz')
          .annotate(buyurtmalar_soni=Count('buyurtmalar'))
          .order_by('-yaratilgan'))

    return Response([{
        'id': m.id,
        'ism': m.ism,
        'telefon': m.telefon,
        'viloyat': m.viloyat,
        'tuman': m.tuman,
        'holat': m.holat,
        'yaratilgan': m.yaratilgan,
        'buyurtmalar_soni': m.buyurtmalar_soni,
    } for m in qs])


class FaqatAdminYozadi(IsAuthenticated):
    """O'qishni har qanday tizimga kirgan foydalanuvchi, yozishni faqat admin.

    Jamoa ro'yxatini xodimlar portali ham o'qiydi (xodimlar.html), shuning
    uchun GET hammaga ochiq qoladi. Yangi xodim kiritish esa faqat adminga.
    """

    def has_permission(self, request, view):
        if not super().has_permission(request, view):
            return False
        if request.method in SAFE_METHODS:
            return True
        return getattr(request.user, 'rol', '') == 'admin'


class XodimlarView(generics.ListCreateAPIView):
    """Jamoa ro'yxati (GET) va yangi xodim kiritish (POST — faqat admin).

    Xodim o'zi ro'yxatdan o'ta olmaydi: hisobni admin ochib, telefon va
    parolni xodimga aytadi. Django admin paneli (/admin/auth_app/xodim/)
    ham ishlashda davom etadi — bu unga qo'shimcha, o'rniga emas.
    """
    permission_classes = [FaqatAdminYozadi]

    def get_serializer_class(self):
        if self.request.method == 'POST':
            return XodimYaratishSerializer
        return XodimSerializer

    def get_queryset(self):
        return Foydalanuvchi.objects.filter(rol='xodim').order_by('ism')

    def create(self, request, *args, **kwargs):
        ser = self.get_serializer(data=request.data)
        ser.is_valid(raise_exception=True)
        xodim = ser.save()
        audit_yoz(request, 'xodim_qoshildi', f'{xodim.ism or xodim.telefon} ({xodim.lavozim})')
        # Ro'yxatdagi kabi to'liq ma'lumot qaytaramiz — panel uni darrov chizadi
        return Response(XodimSerializer(xodim).data, status=status.HTTP_201_CREATED)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def xodim_kod_yangila(request, pk):
    """Xodimga yangi kirish kodi beradi (kod unutilsa/oshkor bo'lsa).

    Eski kod darhol ishlamay qoladi. Faqat admin chaqira oladi.
    """
    if getattr(request.user, 'rol', '') != 'admin':
        return Response({'detail': 'Faqat admin uchun'}, status=403)

    try:
        xodim = Foydalanuvchi.objects.get(pk=pk, rol='xodim')
    except Foydalanuvchi.DoesNotExist:
        return Response({'detail': 'Xodim topilmadi'}, status=404)

    while True:
        kod = kirish_kodi_yasa()
        if not Foydalanuvchi.objects.filter(kirish_kodi=kod).exists():
            break
    xodim.kirish_kodi = kod
    xodim.save(update_fields=['kirish_kodi'])
    return Response({'id': xodim.id, 'kirish_kodi': kod})


class XodimDetailView(generics.RetrieveUpdateAPIView):
    """Bitta xodim: ko'rish (GET) va faol/nofaol qilish (PATCH — faqat admin).

    O'chirish yo'q — xodim eski buyurtmalarga bog'langan, uni bazadan
    yo'qotish o'sha yozuvlarni buzadi. Nofaol xodim portalga kira olmaydi.
    """
    permission_classes = [FaqatAdminYozadi]
    queryset = Foydalanuvchi.objects.filter(rol='xodim')

    def get_serializer_class(self):
        if self.request.method in ('PATCH', 'PUT'):
            return XodimHolatSerializer
        return XodimSerializer

    def update(self, request, *args, **kwargs):
        # Xodimni NOFAOL qilish — qaytarib bo'lmaydigan darajadagi amal:
        # xodim portalga kira olmay qoladi. Uni faqat tizim egasi
        # (is_superuser) bajaradi. Qolgan adminlar, jumladan direktor,
        # xodimni ko'radi va qayta faollashtira oladi, lekin o'chira olmaydi.
        if request.data.get('holat') == 'nofaol' and not request.user.is_superuser:
            audit_yoz(request, 'ruxsat_rad',
                      f'Xodimni nofaol qilishga urinish (id={kwargs.get("pk")})')
            return Response(
                {'detail': "Xodimni nofaol qilish huquqi yo'q — tizim egasiga murojaat qiling."},
                status=403,
            )
        javob = super().update(request, *args, **kwargs)
        xodim = self.get_object()
        audit_yoz(request, 'xodim_holat',
                  f'{xodim.ism or xodim.telefon} → {xodim.holat}')
        return javob
