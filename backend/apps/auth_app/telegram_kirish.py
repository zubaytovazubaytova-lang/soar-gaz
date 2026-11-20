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
    return JsonResponse({'yoqilgan': sozlangan() or bot_bormi(), 'bot': bot_bormi(),
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

    tg_id = claims.get('id')
    tg_id = int(tg_id) if str(tg_id or '').isdigit() else None      # son yoki raqamli matn
    if not tg_id:
        logger.warning('Telegram kirishda id maydoni yo\'q yoki noodatiy: %s', type(claims.get('id')).__name__)
    user, xato = mijozni_kirit(request, '+' + raqamlar, claims.get('name'), tg_id,
                               claims.get('preferred_username'))
    if xato:
        return _qaytish(xato)
    javob = _qaytish()
    _refresh_cookie_yoz(javob, _tokens_for_user(user)['refresh'], False, doimiy=True)
    javob.delete_cookie(STATE_COOKIE, path=STATE_YOL)
    return javob


def mijozni_kirit(request, telefon, ism=None, tg_id=None, username=None):
    """Telegram tasdiqlagan raqam bo'yicha mijozni topadi yoki ro'yxatdan o'tkazadi va botga bog'laydi.
    Qaytaradi: (user, None) yoki (None, xato_kodi). Xodim/admin bu yo'ldan kira olmaydi."""
    from apps.sms_app.models import TelegramUlanish
    from .models import Foydalanuvchi, audit_yoz
    from .views import OTP_YOPIQ_ROLLAR

    user = Foydalanuvchi.objects.filter(telefon=telefon).first()
    if user is not None and user.rol in OTP_YOPIQ_ROLLAR:
        return None, 'xodim'
    if user is not None and user.holat == 'nofaol':
        return None, 'bloklangan'
    yangi = user is None
    if yangi:
        user = Foydalanuvchi.objects.create_user(telefon=telefon, rol='mijoz', ism=str(ism or '')[:100])
    # Buyurtma va ariza xabarlari shu Telegram hisobiga tekin yuborilishi uchun bog'laymiz
    if tg_id:
        TelegramUlanish.objects.filter(chat_id=tg_id).exclude(telefon=telefon).delete()
        TelegramUlanish.objects.update_or_create(
            telefon=telefon, defaults={'chat_id': tg_id, 'username': str(username or '')[:64]})
    audit_yoz(request, 'kirish', "Telegram orqali ro'yxatdan o'tdi" if yangi else 'Telegram orqali kirdi',
              user=user)
    return user, None


# ──────────────────────────────────────────────────────────────
#  BOT ORQALI KIRISH (tanlov sahifasisiz, to'g'ridan-to'g'ri Telegram ilovasiga)
#
#  1. Sayt: GET /api/auth/telegram/bot/boshlash/ → bir martalik token (10 daqiqa) + shu brauzerga cookie;
#     havola https://t.me/<bot>?start=k_<token> — bosilganda Telegram ilovasi ochiladi.
#  2. Bot: /start k_<token> → mijoz «📱 Raqamni ulashish» (yoki oldin ulangan bo'lsa «✅ Saytga kirish»)
#     ni bosadi → token tasdiqlanadi (raqamni Telegram o'zi beradi — kontakt egasi tekshiriladi).
#  3. Sayt har 2 soniyada GET /api/auth/telegram/bot/holat/?t=<token> so'raydi; tasdiqlangach
#     sessiya cookie'si qo'yiladi. Token faqat uni olgan brauzerda (cookie) ishlaydi va bir martalik.
# ──────────────────────────────────────────────────────────────
BOT_KESH = 'tgbot:{}'
BOT_CHAT = 'tgbot_chat:{}'
BOT_COOKIE = 'sg_tgbot'
BOT_MUDDAT = 600
BOT_KIRISH_TUGMA = '✅ Saytga kirish'
BOT_BEKOR_TUGMA = '❌ Bekor qilish'


def bot_bormi():
    from apps.sms_app import telegram
    return telegram.sozlangan() and bool(telegram.bot_nomi())


@require_GET
def bot_boshlash(request):
    from apps.sms_app import telegram
    if not bot_bormi():
        return JsonResponse({'detail': 'Bot sozlanmagan'}, status=400)
    token = secrets.token_urlsafe(18)                  # Telegram start parametri: A-Z a-z 0-9 _ - (64 gacha)
    cache.set(BOT_KESH.format(token), {'holat': 'kutilmoqda'}, BOT_MUDDAT)
    javob = JsonResponse({'token': token, 'muddat': BOT_MUDDAT,
                          'url': f'https://t.me/{telegram.bot_nomi()}?start=k_{token}'})
    javob.set_cookie(BOT_COOKIE, token, max_age=BOT_MUDDAT, httponly=True,
                     secure=not settings.DEBUG, samesite='Lax', path=STATE_YOL)
    return javob


@require_GET
def bot_holat(request):
    from .views import _refresh_cookie_yoz, _tokens_for_user
    token = request.GET.get('t', '')
    if not token or request.COOKIES.get(BOT_COOKIE) != token:
        return JsonResponse({'holat': 'muddat'})
    d = cache.get(BOT_KESH.format(token))
    if not d:
        return JsonResponse({'holat': 'muddat'})
    if d['holat'] == 'kutilmoqda':
        return JsonResponse({'holat': 'kutilmoqda'})
    cache.delete(BOT_KESH.format(token))              # bir martalik
    if d['holat'] != 'tasdiq':
        return JsonResponse({'holat': 'bekor'})
    user, xato = mijozni_kirit(request, d['telefon'], d.get('ism'), d.get('chat_id'), d.get('username'))
    if xato:
        return JsonResponse({'holat': 'xato', 'sabab': xato})
    javob = JsonResponse({'holat': 'ok'})
    _refresh_cookie_yoz(javob, _tokens_for_user(user)['refresh'], False, doimiy=True)
    javob.delete_cookie(BOT_COOKIE, path=STATE_YOL)
    return javob


def _niqob(telefon):
    return telefon[:6] + '***' + telefon[-2:] if len(telefon) > 8 else telefon


def bot_start(token, chat_id, kimdan):
    """Botga «/start k_<token>» keldi (webhook). Mijozdan raqam yoki bir bosish bilan tasdiq so'raladi."""
    from apps.sms_app import telegram
    from apps.sms_app.models import TelegramUlanish
    d = cache.get(BOT_KESH.format(token))
    if not d or d.get('holat') != 'kutilmoqda':
        telegram._javob(chat_id, "Bu kirish havolasi eskirgan. Saytda «Telegram orqali kirish»ni qayta bosing.",
                        {'remove_keyboard': True})
        return
    cache.set(BOT_CHAT.format(chat_id), token, BOT_MUDDAT)
    ulanish = TelegramUlanish.objects.filter(chat_id=chat_id).first()
    ogoh = "\n\n⚠️ Faqat saytda o'zingiz «Telegram orqali kirish»ni bosgan bo'lsangiz davom eting."
    if ulanish:
        telegram._javob(chat_id, f"SOAR GAZ saytiga {_niqob(ulanish.telefon)} raqami bilan kirasizmi?" + ogoh, {
            'keyboard': [[{'text': BOT_KIRISH_TUGMA}], [{'text': BOT_BEKOR_TUGMA}]],
            'resize_keyboard': True, 'one_time_keyboard': True})
    else:
        telegram._javob(chat_id, "SOAR GAZ saytiga kirish uchun pastdagi «📱 Raqamni ulashish» tugmasini bosing." + ogoh,
                        telegram.RAQAM_TUGMASI)


def bot_tasdiq(chat_id, telefon, kimdan):
    """Mijoz raqamini ulashdi yoki «Saytga kirish»ni bosdi — kutilayotgan kirish tasdiqlanadi. Bo'lsa True."""
    from apps.sms_app import telegram
    token = cache.get(BOT_CHAT.format(chat_id))
    if not token:
        return False
    cache.delete(BOT_CHAT.format(chat_id))
    d = cache.get(BOT_KESH.format(token))
    if not d or d.get('holat') != 'kutilmoqda':
        telegram._javob(chat_id, "Kirish havolasi eskirgan. Saytda qayta bosing.", {'remove_keyboard': True})
        return True
    ism = ' '.join(x for x in ((kimdan or {}).get('first_name'), (kimdan or {}).get('last_name')) if x)
    cache.set(BOT_KESH.format(token), {'holat': 'tasdiq', 'telefon': telefon, 'chat_id': chat_id,
                                       'username': (kimdan or {}).get('username') or '', 'ism': ism}, BOT_MUDDAT)
    telegram._javob(chat_id, "✅ Tasdiqlandi! Brauzerga qayting — kabinetingiz o'zi ochiladi.", {'remove_keyboard': True})
    return True


def bot_bekor(chat_id):
    from apps.sms_app import telegram
    token = cache.get(BOT_CHAT.format(chat_id))
    if not token:
        return False
    cache.delete(BOT_CHAT.format(chat_id))
    if cache.get(BOT_KESH.format(token)):
        cache.set(BOT_KESH.format(token), {'holat': 'bekor'}, BOT_MUDDAT)
    telegram._javob(chat_id, "Kirish bekor qilindi.", {'remove_keyboard': True})
    return True
