"""«Telegram orqali kirish / ro'yxatdan o'tish» (Log In With Telegram, OpenID Connect).

Mijoz saytdagi tugmani bosadi → Telegram'da tasdiqlaydi va telefon raqamini ulashishga ruxsat
beradi → Telegram saytga TASDIQLANGAN telefon raqamini qaytaradi. Kod (SMS/Gateway) kerak emas,
Telegram bu xizmat uchun pul olmaydi.

Oqim (Authorization Code + PKCE, https://core.telegram.org/bots/telegram-login):
  1. GET /api/auth/telegram/boshlash/  → state + PKCE yaratiladi, oauth.telegram.org/auth ga yo'naltiriladi
  2. GET /api/auth/telegram/callback/  → kod SERVERDAN serverga (client secret bilan) id_token ga
     almashtiriladi, id_token imzosi (JWKS) va maydonlari tekshiriladi, mijoz topiladi/yaratiladi,
     sessiya cookie'si qo'yiladi va /kabinet/?tg=ok ga qaytariladi.

Xavfsizlik:
  * id_token brauzerdan EMAS, to'g'ridan-to'g'ri Telegram'ning token endpointidan (TLS) olinadi
    va imzosi Telegram'ning ochiq kalitlari bilan tekshiriladi;
  * state bir martalik, keshda saqlanadi VA shu brauzerdagi cookie bilan solishtiriladi (CSRF);
  * xodim va administrator bu yo'ldan kira olmaydi (ular /xodimlar va /boshqaruv/ dan kiradi).

Sozlama (`soargaz-telegram-login-kalit` yozadi):  TELEGRAM_LOGIN_CLIENT_ID, TELEGRAM_LOGIN_CLIENT_SECRET
@BotFather → bot → Login Widget: ruxsat etilgan manzillar (Allowed URLs) ga sayt va callback qo'shiladi.
"""
import base64
import gzip
import hashlib
import json
import logging
import secrets
import urllib.error
import urllib.parse
import urllib.request

from django.conf import settings
from django.core.cache import cache
from django.http import HttpResponseRedirect, JsonResponse
from django.views.decorators.http import require_GET

logger = logging.getLogger(__name__)

AUTH_URL = 'https://oauth.telegram.org/auth'
TOKEN_URL = 'https://oauth.telegram.org/token'
JWKS_URL = 'https://oauth.telegram.org/.well-known/jwks.json'
ISSUER = 'https://oauth.telegram.org'
SCOPE = 'openid profile phone telegram:bot_access'
STATE_COOKIE = 'sg_tg_state'
STATE_YOL = '/api/auth/telegram/'
STATE_MUDDAT = 600            # 10 daqiqa ichida tasdiqlanishi kerak
QAYTISH = '/kabinet/'


class TelegramKirishXato(Exception):
    def __init__(self, kod):
        super().__init__(kod)
        self.kod = kod


def _sozlama(nom):
    return str(getattr(settings, nom, '') or '')


def sozlangan():
    return bool(_sozlama('TELEGRAM_LOGIN_CLIENT_ID') and _sozlama('TELEGRAM_LOGIN_CLIENT_SECRET'))


def callback_url():
    return settings.SAYT_MANZIL.rstrip('/') + '/api/auth/telegram/callback/'


def _qaytish(xato=None):
    return HttpResponseRedirect(QAYTISH + (f'?tg_xato={xato}' if xato else '?tg=ok'))


def _pkce():
    verifier = secrets.token_urlsafe(64)          # 86 belgi (RFC 7636: 43–128)
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b'=').decode()
    return verifier, challenge


@require_GET
def holat(request):
    """Saytdagi tugma faqat sozlama kiritilgandan keyin ko'rinadi."""
    return JsonResponse({'yoqilgan': sozlangan(),
                         'telefon_kirish': bool(getattr(settings, 'TELEFON_KIRISH_YOQILGAN', False))})


@require_GET
def boshlash(request):
    if not sozlangan():
        return _qaytish('sozlanmagan')
    state = secrets.token_urlsafe(24)
    verifier, challenge = _pkce()
    cache.set(f'tglogin:{state}', {'v': verifier}, STATE_MUDDAT)
    params = {
        'client_id': _sozlama('TELEGRAM_LOGIN_CLIENT_ID'),
        'redirect_uri': callback_url(),
        'response_type': 'code',
        'scope': SCOPE,
        'state': state,
        'code_challenge': challenge,
        'code_challenge_method': 'S256',
    }
    javob = HttpResponseRedirect(AUTH_URL + '?' + urllib.parse.urlencode(params))
    javob.set_cookie(STATE_COOKIE, state, max_age=STATE_MUDDAT, httponly=True,
                     secure=not settings.DEBUG, samesite='Lax', path=STATE_YOL)
    return javob


def _token_almashtir(code, verifier):
    """Kodni id_token ga almashtiradi (server→server, client secret bilan)."""
    cid, sec = _sozlama('TELEGRAM_LOGIN_CLIENT_ID'), _sozlama('TELEGRAM_LOGIN_CLIENT_SECRET')
    malumot = urllib.parse.urlencode({
        'grant_type': 'authorization_code', 'code': code, 'redirect_uri': callback_url(),
        'client_id': cid, 'code_verifier': verifier,
    }).encode()
    basic = base64.b64encode(f'{cid}:{sec}'.encode()).decode()
    so_rov = urllib.request.Request(TOKEN_URL, data=malumot, method='POST', headers={
        'Content-Type': 'application/x-www-form-urlencoded', 'Authorization': f'Basic {basic}'})
    try:
        with urllib.request.urlopen(so_rov, timeout=15) as r:
            return json.loads(_javob_matni(r))
    except urllib.error.HTTPError as xato:
        logger.warning('Telegram token almashinuvi rad etildi: HTTP %s', xato.code)
        raise TelegramKirishXato('rad')
    except (urllib.error.URLError, ValueError, OSError) as xato:
        logger.error('Telegram token almashinuvida tarmoq xatosi: %s', type(xato).__name__)
        raise TelegramKirishXato('tarmoq')


def _javob_matni(r):
    """Javob tanasi. oauth.telegram.org standart Python so'roviga ham gzip bilan javob berishi mumkin
    (so'ramasak ham) — shunda ochib beramiz. Avval PyJWKClient shu sabab UnicodeDecodeError berib,
    Telegram orqali kirish vaqti-vaqti bilan «token» xatosi bilan tugardi."""
    tana = r.read()
    if r.headers.get('Content-Encoding', '').lower() == 'gzip' or tana[:2] == b'\x1f\x8b':
        tana = gzip.decompress(tana)
    return tana


JWKS_KESH = 'tglogin:jwks'


def _jwks(yangila=False):
    """Telegram ochiq kalitlari (JWKS) — 1 soat keshda."""
    if not yangila:
        saqlangan = cache.get(JWKS_KESH)
        if saqlangan:
            return saqlangan
    so_rov = urllib.request.Request(JWKS_URL, headers={'User-Agent': 'soargaz-oidc/1.0', 'Accept': 'application/json'})
    with urllib.request.urlopen(so_rov, timeout=10) as r:
        jwks = json.loads(_javob_matni(r))
    cache.set(JWKS_KESH, jwks, 3600)
    return jwks


def _imzo_kaliti(id_token):
    import jwt                              # cryptography talab qiladi
    kid = jwt.get_unverified_header(id_token).get('kid')
    for yangila in (False, True):           # kalit almashgan bo'lsa — bir marta yangidan yuklaymiz
        for kalit in jwt.PyJWKSet.from_dict(_jwks(yangila)).keys:
            if kalit.key_id == kid:
                return kalit.key
    raise jwt.PyJWKClientError(f'Kalit topilmadi: {kid}')


def id_token_tekshir(id_token):
    """Imzo (Telegram ochiq kalitlari), issuer, audience va muddatni tekshiradi; claims qaytaradi."""
    import jwt
    try:
        kalit = _imzo_kaliti(id_token)
        return jwt.decode(id_token, kalit, algorithms=['RS256', 'ES256'],
                          audience=_sozlama('TELEGRAM_LOGIN_CLIENT_ID'), issuer=ISSUER,
                          options={'require': ['exp', 'iat', 'iss', 'aud']}, leeway=30)
    except Exception as xato:                 # noqa: BLE001 — har qanday tekshiruv xatosi = rad
        logger.warning('Telegram id_token tekshiruvdan o\'tmadi: %s: %s | %s', type(xato).__name__,
                       str(xato)[:200], _token_tuzilishi(id_token), exc_info=True)
        raise TelegramKirishXato('token')


def _token_tuzilishi(id_token):
    """Diagnostika uchun: tokenning o'zini emas, faqat tuzilishi va sarlavhasini qaytaradi."""
    try:
        qismlar = str(id_token).split('.')
        bosh = qismlar[0] + '=' * (-len(qismlar[0]) % 4)
        sarlavha = base64.urlsafe_b64decode(bosh).decode('utf-8', 'replace')[:150]
        return f'tur={type(id_token).__name__} qismlar={len(qismlar)} uzunlik={[len(q) for q in qismlar]} sarlavha={sarlavha}'
    except Exception as x:                    # noqa: BLE001
        return f'tuzilish aniqlanmadi: {type(x).__name__}'


@require_GET
def callback(request):
    from apps.sms_app.models import TelegramUlanish
    from .models import Foydalanuvchi, audit_yoz
    from .views import OTP_YOPIQ_ROLLAR, _refresh_cookie_yoz, _tokens_for_user

    if not sozlangan():
        return _qaytish('sozlanmagan')
    if request.GET.get('error'):
        return _qaytish('bekor')                  # foydalanuvchi Telegram'da rad etdi
    code, state = request.GET.get('code', ''), request.GET.get('state', '')
    saqlangan = cache.get(f'tglogin:{state}') if state else None
    if not code or not saqlangan or request.COOKIES.get(STATE_COOKIE) != state:
        return _qaytish('muddat')
    cache.delete(f'tglogin:{state}')              # bir martalik

    try:
        tokenlar = _token_almashtir(code, saqlangan['v'])
        claims = id_token_tekshir(tokenlar.get('id_token') or '')
    except TelegramKirishXato as xato:
        return _qaytish(xato.kod)

    raqamlar = ''.join(ch for ch in str(claims.get('phone_number') or '') if ch.isdigit())
    if not raqamlar or claims.get('phone_number_verified') is False:
        return _qaytish('telefon')                # raqam ulashilmadi yoki tasdiqlanmagan
    telefon = '+' + raqamlar

    user = Foydalanuvchi.objects.filter(telefon=telefon).first()
    if user is not None and user.rol in OTP_YOPIQ_ROLLAR:
        return _qaytish('xodim')
    if user is not None and user.holat == 'nofaol':
        return _qaytish('bloklangan')
    yangi = user is None
    if yangi:
        user = Foydalanuvchi.objects.create_user(telefon=telefon, rol='mijoz',
                                                 ism=str(claims.get('name') or '')[:100])

    # Kirishda bot xabar yuborishiga ruxsat berildi (telegram:bot_access): buyurtma va ariza
    # xabarlari shu Telegram hisobiga tekin yuborilishi uchun bog'laymiz.
    tg_id = claims.get('id')
    tg_id = int(tg_id) if str(tg_id or '').isdigit() else None      # son yoki raqamli matn
    if not tg_id:
        logger.warning('Telegram kirishda id maydoni yo\'q yoki noodatiy: %s', type(claims.get('id')).__name__)
    if tg_id:
        TelegramUlanish.objects.filter(chat_id=tg_id).exclude(telefon=telefon).delete()
        TelegramUlanish.objects.update_or_create(
            telefon=telefon,
            defaults={'chat_id': tg_id, 'username': str(claims.get('preferred_username') or '')[:64]})

    audit_yoz(request, 'kirish', "Telegram orqali ro'yxatdan o'tdi" if yangi else 'Telegram orqali kirdi',
              user=user)
    javob = _qaytish()
    _refresh_cookie_yoz(javob, _tokens_for_user(user)['refresh'], False, doimiy=True)
    javob.delete_cookie(STATE_COOKIE, path=STATE_YOL)
    return javob
