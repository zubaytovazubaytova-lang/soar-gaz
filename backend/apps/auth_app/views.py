import random
import secrets
import string
import time
from django.conf import settings
from django.core.cache import cache
from django.db.models import Count
from django.utils import timezone
from django.utils.translation import gettext as _
from rest_framework import status, generics
from rest_framework.decorators import api_view, permission_classes, throttle_classes
from rest_framework.permissions import IsAuthenticated, AllowAny, SAFE_METHODS
from rest_framework.response import Response
from rest_framework.exceptions import ValidationError
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.serializers import TokenRefreshSerializer
from rest_framework_simplejwt.tokens import AccessToken, RefreshToken

from apps.sms_app.gateway import sms_yubor, sozlanganmi as sms_sozlanganmi
from .hududlar import HUDUDLAR_XARITASI
from .kabinet_turlari import kabinet_malumoti
from .throttles import (
    KirishThrottle, OtpYuborishThrottle, OtpTasdiqThrottle, RoyxatThrottle,
    TokenYangilashThrottle, TasdiqKodiThrottle,
)
from .models import Foydalanuvchi, IshHaqi, Sertifikat, OtpKod, AuditYozuv, audit_yoz, kirish_kodi_yasa
from .serializers import (
    FoydalanuvchiSerializer, XodimSerializer, XodimJamoaSerializer, ProfilSerializer, RoyxatSerializer,
    XodimProfilSerializer, XodimYaratishSerializer, XodimHolatSerializer,
)


# Django paneliga kiradigan, cheklangan huquqli rahbar guruhi (manage.py direktor_guruhi)


# Refresh token brauzerda httpOnly cookie'da turadi: JavaScript (demak XSS ham) uni
# o'qiy olmaydi. Cookie faqat /api/auth/ ga yuboriladi. Mobil ilova cookie ishlatmaydi —
# u `X-Klient: mobil` sarlavhasi bilan refresh'ni javob tanasida oladi.
# Mijoz va xodim sessiyalari ALOHIDA cookie'larda: bitta brauzerda ham mijoz, ham xodim
# sifatida kirilsa, bir sessiya ikkinchisining tokenini almashtirib yubormasin.
REFRESH_COOKIE = 'sg_refresh'
REFRESH_COOKIE_XODIM = 'sg_refresh_xodim'
REFRESH_COOKIE_YOL = '/api/auth/'
XODIM_REFRESH_KUN = 14       # xodim sessiyasi mijozniki (90 kun) kabi uzun bo'lmasin


def _tokens_for_user(user):
    refresh = RefreshToken.for_user(user)
    if user.rol == 'xodim':
        refresh.set_exp(lifetime=timezone.timedelta(days=XODIM_REFRESH_KUN))
    return {
        'access': str(refresh.access_token),
        'refresh': str(refresh),
        'xodim': user.rol == 'xodim',
    }


def _cookie_nomi(xodim):
    return REFRESH_COOKIE_XODIM if xodim else REFRESH_COOKIE


def _mobil(request):
    return request.headers.get('X-Klient', '').lower() == 'mobil'


def _refresh_cookie_yoz(javob, refresh_matn, xodim=False, doimiy=True):
    """doimiy=False — «meni eslab qolma»: cookie brauzer yopilganda o'chadi (muddatsiz)."""
    muddat = max(int(RefreshToken(refresh_matn)['exp'] - time.time()), 0)
    javob.set_cookie(
        _cookie_nomi(xodim), refresh_matn, max_age=muddat if doimiy else None, httponly=True,
        secure=not settings.DEBUG, samesite='Lax', path=REFRESH_COOKIE_YOL,
    )


def _refresh_cookie_ochir(javob, xodim=False):
    javob.delete_cookie(_cookie_nomi(xodim), path=REFRESH_COOKIE_YOL, samesite='Lax')


def _xodim_sessiya(request):
    """Mijoz va xodim sahifalari o'z sessiyasini `sessiya: "xodim"` bilan ajratadi."""
    return request.data.get('sessiya') == "xodim"


def _tokenli_javob(request, tokens, qoshimcha=None, status_kodi=200):
    """Kirish javobi: access tanada, refresh — cookie'da (mobil ilovada tanada)."""
    tana = {'access': tokens['access'], **(qoshimcha or {})}
    mobil = _mobil(request)
    if mobil:
        tana['refresh'] = tokens['refresh']
    javob = Response(tana, status=status_kodi)
    if not mobil:
        _refresh_cookie_yoz(javob, tokens['refresh'], tokens.get('xodim', False),
                            doimiy=request.data.get('eslab') is not False)
    return javob


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


@api_view(['POST'])
@permission_classes([AllowAny])
@throttle_classes([TokenYangilashThrottle])
def token_yangilash(request):
    """POST /api/auth/token/yangilash/ — jimgina yangi access token olish.

    Refresh token cookie'dan olinadi (eski mijozlar — tanadan: bir martalik ko'chish).
    Har safar refresh ham yangilanadi, eskisi esa bekor qilinadi.
    """
    xodim = _xodim_sessiya(request)

    def rad():
        javob = Response({'detail': _('Sessiya tugagan. Qaytadan kiring.')}, status=401)
        _refresh_cookie_ochir(javob, xodim)
        return javob

    xom = request.COOKIES.get(_cookie_nomi(xodim)) or request.data.get('refresh')
    if not xom:
        return rad()
    try:
        token = RefreshToken(xom)
    except TokenError:
        return rad()

    # Bloklangan hisob (xodim bo'shatilgan, mijoz o'chirilgan) yangi token ololmaydi;
    # mijoz tokeni xodim sessiyasida (yoki aksincha) ishlamaydi
    egasi = Foydalanuvchi.objects.filter(pk=token.get('user_id')).first()
    if not egasi or egasi.holat != 'faol' or (egasi.rol == 'xodim') != xodim:
        try:
            token.blacklist()
        except TokenError:
            pass
        return rad()

    ser = TokenRefreshSerializer(data={'refresh': xom})
    try:
        ser.is_valid(raise_exception=True)
    except (TokenError, ValidationError):
        return rad()

    yangi = ser.validated_data
    tana = {'access': yangi['access']}
    mobil = _mobil(request)
    if mobil and yangi.get('refresh'):
        tana['refresh'] = yangi['refresh']
    javob = Response(tana)
    if not mobil and yangi.get('refresh'):
        _refresh_cookie_yoz(javob, yangi['refresh'], xodim,
                            doimiy=request.data.get('eslab') is not False)
    return javob


@api_view(['POST'])
@permission_classes([AllowAny])
def chiqish(request):
    """POST /api/auth/chiqish/ — refresh tokenni bekor qiladi va cookie'ni o'chiradi (logout).

    Token o'zi egalik dalili, shuning uchun kirish talab qilinmaydi. Yaroqsiz yoki
    allaqachon bekor qilingan token ham xato bermaydi: mijoz baribir chiqib ketadi.
    Access token muddati tugaguncha (30 daqiqa) ishlaydi — refresh esa endi yangi
    access bera olmaydi.
    """
    xodim = _xodim_sessiya(request)
    for xom in {request.COOKIES.get(_cookie_nomi(xodim)), request.data.get('refresh')}:
        if xom:
            try:
                RefreshToken(xom).blacklist()
            except TokenError:
                pass
    javob = Response({'detail': _('Tizimdan chiqildi')})
    _refresh_cookie_ochir(javob, xodim)
    return javob


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
        # Direktor — kuzatuvchi: hamma narsani ko'radi, hech narsani o'zgartira olmaydi (apps/auth_app/korish.py)
        'kuzatuvchi': user.rol == 'admin' and not user.is_superuser,
        'holat': user.holat,
        'qoshimcha_telefon': user.qoshimcha_telefon,
        'email': user.email,
        'mulk_turi': user.mulk_turi,
        'moljal': user.moljal,
    }


@api_view(['POST'])
@permission_classes([AllowAny])
@throttle_classes([KirishThrottle])
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
        return Response({'detail': _('Telefon va parol kiritilishi shart')}, status=400)

    BLOK_XABAR = _("Hisob bloklandi: juda ko'p noto'g'ri urinish. "
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
            {'detail': _("Telefon yoki parol noto'g'ri! Yana %(qoldi)s ta urinish qoldi.")
                       % {'qoldi': qoldi}},
            status=401)

    cache.delete(f'admin:urinish:{telefon}')

    # Direktor ham /boshqaruv/ da ishlaydi (kuzatuvchi: faqat ko'radi — apps/auth_app/korish.py).
    # Django paneli (/admin/) esa faqat tizim egasi uchun.

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
@throttle_classes([OtpTasdiqThrottle])
def admin_otp_tasdiqlash(request):
    """Boshqaruv paneliga kirishning ikkinchi bosqichi — SMS kod.

    Token faqat shu yerdan beriladi: parol bosqichi hech qachon token
    qaytarmaydi (2FA yoqilgan bo'lsa).
    """
    chipta = (request.data.get('chipta') or '').strip()
    kod = (request.data.get('kod') or '').strip()

    if not chipta or not kod:
        return Response({'detail': _('Kod kiritilishi shart')}, status=400)

    kalit = f'admin:2fa:{chipta}'
    holat = cache.get(kalit)
    if not holat:
        return Response(
            {'detail': _('Kod muddati tugadi. Qaytadan kiring.'), 'qaytadan': True},
            status=401)

    user = Foydalanuvchi.objects.filter(telefon=holat['telefon'], rol='admin').first()
    if user is None or user.holat == 'nofaol':
        cache.delete(kalit)
        return Response({'detail': _('Hisob mavjud emas yoki bloklangan'), 'qaytadan': True}, status=403)

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
                {'detail': _("Kod bir necha marta xato kiritildi. Qaytadan kiring."), 'qaytadan': True},
                status=401)
        cache.set(kalit, holat, settings.ADMIN_2FA_DAQIQA * 60)
        qoldi = settings.ADMIN_2FA_URINISH - holat['urinish']
        audit_yoz(request, 'kirish_xato', "Noto'g'ri SMS kod", user=user)
        return Response({'detail': _("Kod noto'g'ri. Yana %(qoldi)s ta urinish qoldi.")
                         % {'qoldi': qoldi}}, status=401)

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
@throttle_classes([RoyxatThrottle])
def royxatdan_otish(request):
    """Mijoz ro'yxatdan o'tadi va darhol tizimga kiradi.
    Yaratilgan hisob Django admin panelida (rol='mijoz') ko'rinadi."""
    ser = RoyxatSerializer(data=request.data)
    if not ser.is_valid():
        return Response(ser.errors, status=400)

    user = ser.save()
    return _tokenli_javob(request, _tokens_for_user(user), {'user': _user_data(user)},
                          status.HTTP_201_CREATED)


def _send_otp_sms(telefon, kod):
    """OTP kodni SMS orqali yuboradi (provayder sozlanmagan bo'lsa — log)."""
    return sms_yubor(telefon, f"SOAR GAZ tasdiqlash kodi: {kod}. Hech kimga aytmang.")


def _kesh_kaliti(nom, telefon):
    return f'otp:{nom}:{telefon}'


def _otp_cheklov(telefon):
    """Kod so'rash cheklovlari. Muammo bo'lsa (matn, soniya) qaytaradi."""
    if cache.get(_kesh_kaliti('blok', telefon)):
        return _("Juda ko'p urinish. Birozdan keyin qayta urinib ko'ring."), 429

    oxirgi = cache.get(_kesh_kaliti('oxirgi', telefon))
    if oxirgi:
        return _('Yangi kod %(soniya)s soniyada bir marta yuboriladi.') % {
            'soniya': settings.OTP_QAYTA_SONIYA}, 429

    soatlik = cache.get(_kesh_kaliti('soatlik', telefon), 0)
    if soatlik >= settings.OTP_SOATLIK_LIMIT:
        cache.set(_kesh_kaliti('blok', telefon), 1, settings.OTP_BLOK_DAQIQA * 60)
        return _("Bu raqamga kod yuborish chegarasi tugadi. Keyinroq urinib ko'ring."), 429

    return None, 0


@api_view(['POST'])
@permission_classes([AllowAny])
@throttle_classes([OtpYuborishThrottle])
def otp_yuborish(request):
    telefon = request.data.get('telefon', '').replace(' ', '')
    if not telefon:
        return Response({'detail': _('Telefon raqam kiritilishi shart')}, status=400)

    xato, kod_holat = _otp_cheklov(telefon)
    if xato:
        return Response({'detail': xato}, status=kod_holat)

    # Xodim bloklangan tekshiruvi
    try:
        mavjud = Foydalanuvchi.objects.get(telefon=telefon)
        if mavjud.holat == 'nofaol':
            return Response({'detail': _('Hisobingiz bloklangan. Admin bilan bog\'laning.')}, status=403)
        yangi_mijoz = False
        rol = mavjud.rol
    except Foydalanuvchi.DoesNotExist:
        yangi_mijoz = True
        rol = 'mijoz'

    # Sinov raqami (faqat DEBUG=1): SMS yuborilmaydi, kod doim bir xil. Serverda ro'yxat bo'sh.
    sinov_kod = (getattr(settings, 'SINOV_MIJOZ', None) or {}).get(telefon) if settings.DEBUG else None
    kod = sinov_kod or ''.join(random.choices(string.digits, k=6))
    OtpKod.objects.create(telefon=telefon, kod=kod)

    if not sinov_kod and not _send_otp_sms(telefon, kod):
        return Response(
            {'detail': _("SMS yuborilmadi. Birozdan keyin urinib ko'ring yoki operatorga murojaat qiling.")},
            status=502,
        )

    # Cheklov hisoblagichlari
    cache.set(_kesh_kaliti('oxirgi', telefon), 1, settings.OTP_QAYTA_SONIYA)
    soatlik = cache.get(_kesh_kaliti('soatlik', telefon), 0)
    cache.set(_kesh_kaliti('soatlik', telefon), soatlik + 1, 3600)

    return Response({'yuborildi': True, 'yangi_mijoz': yangi_mijoz, 'rol': rol})


@api_view(['POST'])
@permission_classes([AllowAny])
@throttle_classes([OtpTasdiqThrottle])
def otp_tasdiqlash(request):
    telefon = request.data.get('telefon', '').replace(' ', '')
    kod = request.data.get('kod', '').strip()

    if not telefon or not kod:
        return Response({'detail': _('Telefon va kod kiritilishi shart')}, status=400)

    if cache.get(_kesh_kaliti('blok', telefon)):
        return Response(
            {'detail': _("Juda ko'p noto'g'ri urinish. Birozdan keyin qayta urinib ko'ring.")},
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
                {'detail': _("Juda ko'p noto'g'ri urinish. Hisobingiz vaqtincha bloklandi.")},
                status=429,
            )
        return Response({'detail': _('Kod noto\'g\'ri!')}, status=400)

    if otp.muddati_utganmi():
        return Response({'detail': _('Kod muddati tugagan. Qayta yuboring.')}, status=400)

    otp.ishlatildi = True
    otp.save()
    cache.delete(_kesh_kaliti('urinish', telefon))

    user, created = Foydalanuvchi.objects.get_or_create(
        telefon=telefon,
        defaults={'rol': 'mijoz'}
    )

    return _tokenli_javob(request, _tokens_for_user(user), {'user': _user_data(user)})


# ──────────────────────────────────────────────────────────────
#  Maxfiy amallar uchun SMS bilan qayta tasdiqlash (step-up)
#
#  Token o'g'irlangan bo'lsa ham hujumchi egasining TELEFONIGA kelgan kodni
#  ola olmaydi, shuning uchun email / qo'shimcha telefon almashtirish yoki
#  hisobni o'chirish uning qo'lidan kelmaydi.
# ──────────────────────────────────────────────────────────────
TASDIQ_MAYDONLARI = ('email', 'qoshimcha_telefon')


def tasdiq_kodini_sarfla(user, kod):
    """Maxfiy amal uchun SMS kodni tekshiradi va sarflaydi.

    Muvaffaqiyatda None, aks holda tayyor `Response` (view uni shundayligicha qaytaradi).
    """
    kod = str(kod or '').strip()
    if not kod:
        return Response({
            'detail': _("Bu amal uchun telefoningizga yuborilgan SMS kodni kiriting"),
            'kod_kerak': True,
        }, status=403)

    telefon = user.telefon
    if cache.get(_kesh_kaliti('blok', telefon)):
        return Response(
            {'detail': _("Juda ko'p noto'g'ri urinish. Birozdan keyin qayta urinib ko'ring.")},
            status=429)

    otp = OtpKod.objects.filter(
        telefon=telefon, kod=kod, ishlatildi=False).order_by('-yaratilgan').first()
    if not otp or otp.muddati_utganmi():
        urinish = cache.get(_kesh_kaliti('urinish', telefon), 0) + 1
        cache.set(_kesh_kaliti('urinish', telefon), urinish, settings.OTP_EXPIRE_MINUTES * 60)
        if urinish >= settings.OTP_URINISH_LIMIT:
            cache.set(_kesh_kaliti('blok', telefon), 1, settings.OTP_BLOK_DAQIQA * 60)
            return Response(
                {'detail': _("Juda ko'p noto'g'ri urinish. Hisobingiz vaqtincha bloklandi.")},
                status=429)
        return Response({'detail': _("Kod noto'g'ri yoki muddati tugagan"), 'kod_kerak': True},
                        status=400)

    otp.ishlatildi = True
    otp.save()
    cache.delete(_kesh_kaliti('urinish', telefon))
    return None


@api_view(['POST'])
@permission_classes([IsAuthenticated])
@throttle_classes([TasdiqKodiThrottle])
def tasdiq_kodi_yuborish(request):
    """POST /api/auth/tasdiq-kodi/ — kirgan foydalanuvchining O'Z telefoniga SMS kod yuboradi."""
    telefon = request.user.telefon
    xato, kod_holat = _otp_cheklov(telefon)
    if xato:
        return Response({'detail': xato}, status=kod_holat)

    sinov_kod = (getattr(settings, 'SINOV_MIJOZ', None) or {}).get(telefon) if settings.DEBUG else None
    kod = sinov_kod or ''.join(random.choices(string.digits, k=6))
    OtpKod.objects.create(telefon=telefon, kod=kod)
    if not sinov_kod and not _send_otp_sms(telefon, kod):
        return Response(
            {'detail': _("SMS yuborilmadi. Birozdan keyin urinib ko'ring.")}, status=502)

    cache.set(_kesh_kaliti('oxirgi', telefon), 1, settings.OTP_QAYTA_SONIYA)
    soatlik = cache.get(_kesh_kaliti('soatlik', telefon), 0)
    cache.set(_kesh_kaliti('soatlik', telefon), soatlik + 1, 3600)
    return Response({'yuborildi': True})


@api_view(['PATCH', 'GET'])
@permission_classes([IsAuthenticated])
def profil(request):
    user = request.user
    if request.method == 'GET':
        return Response(_user_data(user))

    # Email / qo'shimcha telefon ENDI O'ZGARSA SMS kod talab qilinadi. Qiymat
    # o'zgarmasa (forma hamma maydonni qayta yuboradi) kod so'ralmaydi.
    ozgardi = [
        f for f in TASDIQ_MAYDONLARI
        if f in request.data
        and str(request.data.get(f) or '').strip() != str(getattr(user, f) or '').strip()
    ]
    if ozgardi:
        rad = tasdiq_kodini_sarfla(user, request.data.get('tasdiq_kodi'))
        if rad:
            return rad

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
        # Lavozimga qarab kabinet menyusi (kirish hamma uchun bir xil)
        'kabinet': kabinet_malumoti(user.lavozim),
    }


@api_view(['POST'])
@permission_classes([AllowAny])
@throttle_classes([KirishThrottle])
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
        return Response({'detail': _('Telefon va kirish kodi kiritilishi shart')},
                        status=400)

    # Kod parolning o'rnini bosadi, shuning uchun taxmin qilishga cheklov
    # qo'yamiz — aks holda 6 belgili kodni avtomat tanlab olish mumkin.
    blok_kalit = f'xodim:blok:{telefon}'
    if cache.get(blok_kalit):
        return Response(
            {'detail': _("Juda ko'p noto'g'ri urinish. %(daqiqa)s daqiqadan "
                         "keyin urinib ko'ring.")
                       % {'daqiqa': settings.OTP_BLOK_DAQIQA}},
            status=429)

    try:
        user = Foydalanuvchi.objects.get(telefon=telefon, rol='xodim')
    except Foydalanuvchi.DoesNotExist:
        # Aniq xabar: xodim qaysi tomonda xato qilganini bilsin. Bu ichki
        # portal — raqamning ro'yxatda borligi maxfiy ma'lumot emas.
        return Response(
            {'detail': _('Bu telefon raqam xodim sifatida ro\'yxatda yo\'q. '
                       'Administrator bilan bog\'laning.')}, status=401)

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
                {'detail': _("Juda ko'p noto'g'ri urinish. %(daqiqa)s daqiqadan "
                             "keyin urinib ko'ring.")
                           % {'daqiqa': settings.OTP_BLOK_DAQIQA}},
                status=429)
        qoldi = settings.OTP_URINISH_LIMIT - urinish
        return Response(
            {'detail': _("Kirish kodi noto'g'ri. Administratordan kodni "
                         "tekshirib oling. Yana %(qoldi)s ta urinish qoldi.")
                       % {'qoldi': qoldi}},
            status=401)

    cache.delete(f'xodim:urinish:{telefon}')

    if user.holat == 'nofaol':
        return Response({'detail': _('Hisobingiz bloklangan. Admin bilan bog\'laning.')}, status=403)

    return _tokenli_javob(request, _tokens_for_user(user), {'xodim': _xodim_data(user)})


@api_view(['GET', 'PATCH'])
@permission_classes([IsAuthenticated])
def xodim_profil(request):
    """Xodim o'z profilini ko'radi va aloqa ma'lumotlarini yangilaydi.
    Ism/lavozim/tabel raqam admin panelidan boshqariladi — bu yerda o'zgarmaydi."""
    user = request.user
    if user.rol != 'xodim':
        return Response({'detail': _('Faqat xodimlar uchun')}, status=403)

    if request.method == 'GET':
        return Response(_xodim_data(user))

    ser = XodimProfilSerializer(user, data=request.data, partial=True)
    if not ser.is_valid():
        return Response(ser.errors, status=400)
    ser.save()
    return Response(_xodim_data(user))


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def xodim_sertifikatlar(request):
    """Xodimning O'Z sertifikatlari (faqat o'qish). Muddati tez tugaydiganlari `yaqin` holatida."""
    if request.user.rol != 'xodim':
        return Response({'detail': _('Faqat xodimlar uchun')}, status=403)
    return Response([{
        'id': s.id, 'nomi': s.nomi, 'raqami': s.raqami,
        'berilgan': s.berilgan, 'amal_qiladi': s.amal_qiladi, 'holat': s.holat,
    } for s in Sertifikat.objects.filter(xodim=request.user)])


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def xodim_ish_haqi(request):
    """Xodimning O'Z ish haqi tarixi (so'nggi 12 oy, faqat o'qish). Boshqa xodimniki hech qachon ko'rinmaydi."""
    if request.user.rol != 'xodim':
        return Response({'detail': _('Faqat xodimlar uchun')}, status=403)
    return Response([{
        'id': y.id, 'oy': y.oy, 'asosiy': y.asosiy, 'bonus': y.bonus,
        'jami': y.jami, 'izoh': y.izoh,
    } for y in IshHaqi.objects.filter(xodim=request.user)[:12]])


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def audit_list(request):
    """Faoliyat jurnali — kim, qachon, nima qilgani.

    Faqat o'qish uchun: yozuvni o'zgartirish ham, o'chirish ham mumkin emas.
    Oxirgi 200 ta yozuv beriladi — jurnal cheksiz o'smasin.
    """
    if getattr(request.user, 'rol', None) != 'admin':
        return Response({'detail': _('Ruxsat yo\'q')}, status=403)

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
        return Response({'detail': _('Ruxsat yo\'q')}, status=403)

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
        rol = getattr(request.user, 'rol', '')
        if request.method in SAFE_METHODS:
            return rol in ('admin', 'xodim')          # MIJOZ xodimlar ro'yxatini ko'ra olmaydi
        return rol == 'admin'


def xodim_serializeri(user):
    """Administrator — to'liq (kirish kodi bilan), oddiy xodim — kodsiz.
    Kirish kodi xodimning parolini bosib turadi: uni boshqa xodim ko'rsa, uning nomidan kira oladi."""
    return XodimSerializer if getattr(user, 'rol', '') == 'admin' else XodimJamoaSerializer


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
        return xodim_serializeri(self.request.user)

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
def korish_boshlash(request, pk):
    """Egasi xodim yoki mijoz portalini o'sha foydalanuvchi nomidan FAQAT O'QISH
    rejimida ochadi (apps/auth_app/korish.py). Qisqa muddatli, yangilanmaydigan token
    qaytadi; har ochish Faoliyat jurnaliga yoziladi.

    Faqat tizim egasi (superuser) uchun. Admin hisoblari nomidan ko'rib bo'lmaydi.
    """
    if not (getattr(request.user, 'rol', '') == 'admin' and request.user.is_superuser):
        return Response({'detail': _("Bu amal faqat tizim egasi uchun")}, status=403)

    try:
        hedaf = Foydalanuvchi.objects.get(pk=pk, rol__in=('xodim', 'mijoz'))
    except Foydalanuvchi.DoesNotExist:
        return Response({'detail': _('Foydalanuvchi topilmadi')}, status=404)

    token = AccessToken.for_user(hedaf)
    token.set_exp(lifetime=timezone.timedelta(minutes=settings.KORISH_DAQIQA))
    token['korish'] = True
    token['korish_egasi'] = request.user.pk

    nom = hedaf.ism or hedaf.telefon
    audit_yoz(request, 'korish_boshlandi', f"{nom} ({hedaf.rol}, {hedaf.telefon}) nomidan")
    return Response({
        'access': str(token),
        'ism': nom,
        'rol': hedaf.rol,
        'portal': '/xodimlar/' if hedaf.rol == 'xodim' else '/kabinet/',
        'muddat_daqiqa': settings.KORISH_DAQIQA,
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def xodim_kod_yangila(request, pk):
    """Xodimga yangi kirish kodi beradi (kod unutilsa/oshkor bo'lsa).

    Eski kod darhol ishlamay qoladi. Faqat admin chaqira oladi.
    """
    if getattr(request.user, 'rol', '') != 'admin':
        return Response({'detail': _('Faqat admin uchun')}, status=403)

    try:
        xodim = Foydalanuvchi.objects.get(pk=pk, rol='xodim')
    except Foydalanuvchi.DoesNotExist:
        return Response({'detail': _('Xodim topilmadi')}, status=404)

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
        return xodim_serializeri(self.request.user)

    def update(self, request, *args, **kwargs):
        # Xodimni NOFAOL qilish — qaytarib bo'lmaydigan darajadagi amal:
        # xodim portalga kira olmay qoladi. Uni faqat tizim egasi
        # (is_superuser) bajaradi. Qolgan adminlar, jumladan direktor,
        # xodimni ko'radi va qayta faollashtira oladi, lekin o'chira olmaydi.
        if request.data.get('holat') == 'nofaol' and not request.user.is_superuser:
            audit_yoz(request, 'ruxsat_rad',
                      f'Xodimni nofaol qilishga urinish (id={kwargs.get("pk")})')
            return Response(
                {'detail': _("Xodimni nofaol qilish huquqi yo'q — tizim egasiga murojaat qiling.")},
                status=403,
            )
        javob = super().update(request, *args, **kwargs)
        xodim = self.get_object()
        audit_yoz(request, 'xodim_holat',
                  f'{xodim.ism or xodim.telefon} → {xodim.holat}')
        return javob
