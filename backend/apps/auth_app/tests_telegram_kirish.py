"""«Telegram orqali kirish / ro'yxatdan o'tish» (OpenID Connect) testlari."""
import time
import urllib.parse
from unittest import mock, skipUnless

from django.core.cache import cache
from django.test import Client, TestCase, override_settings

from apps.sms_app.models import TelegramUlanish
from . import telegram_kirish as tk
from .models import Foydalanuvchi
from .views import REFRESH_COOKIE

try:
    import cryptography  # noqa: F401
    CRYPTO = True
except ImportError:
    CRYPTO = False

SOZ = dict(TELEGRAM_LOGIN_CLIENT_ID='123456', TELEGRAM_LOGIN_CLIENT_SECRET='sir-123',
           SAYT_MANZIL='https://soargaz.uz')
TEL = '+998901234567'


def claims(**ozgar):
    hozir = int(time.time())
    d = {'iss': tk.ISSUER, 'aud': '123456', 'iat': hozir, 'exp': hozir + 3600, 'sub': 'abc',
         'id': 777, 'name': 'Ali Valiyev', 'preferred_username': 'ali',
         'phone_number': '998901234567', 'phone_number_verified': True}
    d.update(ozgar)
    return d


@override_settings(**SOZ)
class TelegramKirishTest(TestCase):
    def setUp(self):
        cache.clear()
        self.c = Client()

    def _boshlash(self):
        r = self.c.get('/api/auth/telegram/boshlash/')
        self.assertEqual(r.status_code, 302)
        return urllib.parse.parse_qs(urllib.parse.urlparse(r['Location']).query)['state'][0]

    def _callback(self, cl=None, state=None, tokenlar=None, **qoshimcha):
        state = state if state is not None else self._boshlash()
        with mock.patch.object(tk, '_token_almashtir', return_value=tokenlar or {'id_token': 'jwt'}) as alm, \
                mock.patch.object(tk, 'id_token_tekshir', return_value=cl or claims()) as tek:
            r = self.c.get('/api/auth/telegram/callback/', {'code': 'KOD', 'state': state, **qoshimcha})
        return r, alm, tek

    # ── holat va boshlash ──
    def test_holat(self):
        self.assertTrue(self.c.get('/api/auth/telegram/holat/').json()['yoqilgan'])
        with override_settings(TELEGRAM_LOGIN_CLIENT_SECRET=''):
            self.assertFalse(self.c.get('/api/auth/telegram/holat/').json()['yoqilgan'])

    @override_settings(TELEGRAM_LOGIN_CLIENT_ID='')
    def test_sozlanmagan_bolsa_boshlanmaydi(self):
        r = self.c.get('/api/auth/telegram/boshlash/')
        self.assertEqual(r['Location'], '/kabinet/?tg_xato=sozlanmagan')

    def test_boshlash_telegramga_togri_yonaltiradi(self):
        r = self.c.get('/api/auth/telegram/boshlash/')
        url = urllib.parse.urlparse(r['Location'])
        q = urllib.parse.parse_qs(url.query)
        self.assertEqual(f'{url.scheme}://{url.netloc}{url.path}', tk.AUTH_URL)
        self.assertEqual(q['client_id'], ['123456'])
        self.assertEqual(q['redirect_uri'], ['https://soargaz.uz/api/auth/telegram/callback/'])
        self.assertEqual(q['response_type'], ['code'])
        self.assertEqual(q['code_challenge_method'], ['S256'])
        self.assertIn('phone', q['scope'][0].split())
        self.assertIn('telegram:bot_access', q['scope'][0].split())
        state = q['state'][0]
        self.assertEqual(r.cookies[tk.STATE_COOKIE].value, state)
        self.assertTrue(r.cookies[tk.STATE_COOKIE]['httponly'])
        self.assertIsNotNone(cache.get(f'tglogin:{state}'))

    # ── muvaffaqiyatli ro'yxatdan o'tish / kirish ──
    def test_yangi_mijoz_royxatdan_otadi_telefon_bazaga_saqlanadi(self):
        r, alm, _ = self._callback()
        self.assertEqual(r['Location'], '/kabinet/?tg=ok')
        u = Foydalanuvchi.objects.get(telefon=TEL)
        self.assertEqual((u.rol, u.ism, u.holat), ('mijoz', 'Ali Valiyev', 'faol'))
        self.assertIn(REFRESH_COOKIE, r.cookies)                     # sessiya ochildi
        self.assertEqual(TelegramUlanish.objects.get(telefon=TEL).chat_id, 777)  # bot xabar yubora oladi
        self.assertTrue(43 <= len(alm.call_args[0][1]) <= 128)       # PKCE verifier (RFC 7636) serverda saqlangan

    def test_id_matn_korinishida_kelsa_ham_bot_boglanadi(self):
        self._callback(cl=claims(id='777'))
        self.assertEqual(TelegramUlanish.objects.get(telefon=TEL).chat_id, 777)

    def test_kirgandan_keyin_sessiya_ishlaydi(self):
        self._callback()
        ya = self.c.post('/api/auth/token/yangilash/', {}, content_type='application/json')
        self.assertEqual(ya.status_code, 200)
        p = self.c.get('/api/auth/profil/', HTTP_AUTHORIZATION='Bearer ' + ya.json()['access'])
        self.assertEqual(p.json()['telefon'], TEL)

    def test_mavjud_mijoz_kiradi_dublikat_yoq(self):
        Foydalanuvchi.objects.create(telefon=TEL, rol='mijoz', ism='Eski Ism')
        r, _, _ = self._callback()
        self.assertEqual(r['Location'], '/kabinet/?tg=ok')
        self.assertEqual(Foydalanuvchi.objects.filter(telefon=TEL).count(), 1)
        self.assertEqual(Foydalanuvchi.objects.get(telefon=TEL).ism, 'Eski Ism')   # ismi o'zgarmaydi

    # ── rad etilishi kerak bo'lgan holatlar ──
    def test_xodim_va_admin_kira_olmaydi(self):
        for rol in ('xodim', 'admin'):
            Foydalanuvchi.objects.filter(telefon=TEL).delete()
            Foydalanuvchi.objects.create(telefon=TEL, rol=rol)
            r, _, _ = self._callback()
            self.assertEqual(r['Location'], '/kabinet/?tg_xato=xodim', rol)
            self.assertNotIn(REFRESH_COOKIE, r.cookies)

    def test_bloklangan_mijoz(self):
        Foydalanuvchi.objects.create(telefon=TEL, rol='mijoz', holat='nofaol')
        r, _, _ = self._callback()
        self.assertEqual(r['Location'], '/kabinet/?tg_xato=bloklangan')
        self.assertNotIn(REFRESH_COOKIE, r.cookies)

    def test_state_bir_martalik(self):
        state = self._boshlash()
        self._callback(state=state)
        r, alm, _ = self._callback(state=state)
        self.assertEqual(r['Location'], '/kabinet/?tg_xato=muddat')
        alm.assert_not_called()

    def test_boshqa_brauzerdagi_state_rad_etiladi(self):
        state = self._boshlash()
        self.c.cookies.pop(tk.STATE_COOKIE)              # boshqa brauzer: cookie yo'q
        r, alm, _ = self._callback(state=state)
        self.assertEqual(r['Location'], '/kabinet/?tg_xato=muddat')
        alm.assert_not_called()

    def test_soxta_state(self):
        self._boshlash()
        r, alm, _ = self._callback(state='soxta')
        self.assertEqual(r['Location'], '/kabinet/?tg_xato=muddat')
        alm.assert_not_called()

    def test_foydalanuvchi_rad_etdi(self):
        r = self.c.get('/api/auth/telegram/callback/', {'error': 'access_denied', 'state': self._boshlash()})
        self.assertEqual(r['Location'], '/kabinet/?tg_xato=bekor')

    def test_tasdiqlanmagan_yoki_yoq_telefon(self):
        for cl in (claims(phone_number_verified=False), claims(phone_number='')):
            r, _, _ = self._callback(cl=cl)
            self.assertEqual(r['Location'], '/kabinet/?tg_xato=telefon')
        self.assertFalse(Foydalanuvchi.objects.exists())

    def test_token_almashinuvi_xatosi(self):
        state = self._boshlash()
        with mock.patch.object(tk, '_token_almashtir', side_effect=tk.TelegramKirishXato('rad')):
            r = self.c.get('/api/auth/telegram/callback/', {'code': 'K', 'state': state})
        self.assertEqual(r['Location'], '/kabinet/?tg_xato=rad')
        self.assertFalse(Foydalanuvchi.objects.exists())


@skipUnless(CRYPTO, 'cryptography o\'rnatilmagan')
@override_settings(**SOZ)
class IdTokenImzoTest(TestCase):
    """id_token imzosi Telegram kaliti bilan haqiqatan tekshiriladi."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        from cryptography.hazmat.primitives.asymmetric import rsa
        cls.kalit = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        cls.begona = rsa.generate_private_key(public_exponent=65537, key_size=2048)

    def _token(self, kalit=None, **ozgar):
        import jwt
        return jwt.encode(claims(**ozgar), kalit or self.kalit, algorithm='RS256', headers={'kid': 'k1'})

    def _tekshir(self, token):
        with mock.patch.object(tk, '_imzo_kaliti', return_value=self.kalit.public_key()):
            return tk.id_token_tekshir(token)

    def test_togri_token(self):
        self.assertEqual(self._tekshir(self._token())['phone_number'], '998901234567')

    def test_boshqa_kalit_bilan_imzolangan(self):
        with self.assertRaises(tk.TelegramKirishXato):
            self._tekshir(self._token(kalit=self.begona))

    def test_boshqa_bot_uchun_token(self):
        with self.assertRaises(tk.TelegramKirishXato):
            self._tekshir(self._token(aud='999'))

    def test_muddati_otgan(self):
        with self.assertRaises(tk.TelegramKirishXato):
            self._tekshir(self._token(iat=int(time.time()) - 7200, exp=int(time.time()) - 3600))

    def test_boshqa_issuer(self):
        with self.assertRaises(tk.TelegramKirishXato):
            self._tekshir(self._token(iss='https://soxta.example'))
