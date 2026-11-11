"""Sessiya tokenlari: refresh httpOnly cookie'da, rotatsiya, blacklist, logout.

Mijoz brauzeri refresh tokenni FAQAT cookie orqali oladi (JavaScript o'qiy olmaydi);
mobil ilova esa `X-Klient: mobil` sarlavhasi bilan uni javob tanasida oladi.
"""
import time

from django.core.cache import cache
from django.test import TestCase, override_settings
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken, RefreshToken

from .models import Foydalanuvchi, OtpKod
from .views import REFRESH_COOKIE, REFRESH_COOKIE_XODIM, XODIM_REFRESH_KUN

MOBIL = {'HTTP_X_KLIENT': 'mobil'}
TELEFON = '+998901112233'


def kirish(client, telefon=TELEFON, **extra):
    OtpKod.objects.create(telefon=telefon, kod='123456')
    return client.post('/api/auth/otp/tasdiqlash/', {'telefon': telefon, 'kod': '123456'},
                       format='json', **extra)


class RefreshCookieTest(TestCase):
    def setUp(self):
        cache.clear()      # IP cheklovlari (15/daqiqa) testlar orasida to'planib qolmasin
        self.c = APIClient()
        self.user = Foydalanuvchi.objects.create(telefon=TELEFON, rol='mijoz')

    def test_kirishda_refresh_tanada_emas_cookieda(self):
        r = kirish(self.c)
        self.assertEqual(r.status_code, 200)
        self.assertIn('access', r.json())
        self.assertNotIn('refresh', r.json())            # JavaScript ko'ra olmaydi
        cookie = r.cookies[REFRESH_COOKIE]
        self.assertTrue(cookie['httponly'])
        self.assertEqual(cookie['samesite'], 'Lax')
        self.assertEqual(cookie['path'], '/api/auth/')

    @override_settings(DEBUG=False)
    def test_productionda_cookie_secure(self):
        """Jonli serverda (DEBUG=0) cookie faqat HTTPS orqali yuboriladi."""
        self.assertTrue(kirish(self.c).cookies[REFRESH_COOKIE]['secure'])

    @override_settings(DEBUG=True)
    def test_lokalda_cookie_http_da_ishlaydi(self):
        self.assertFalse(kirish(self.c).cookies[REFRESH_COOKIE]['secure'])

    def test_cookie_90_kunga_yaqin(self):
        cookie = kirish(self.c).cookies[REFRESH_COOKIE]
        self.assertAlmostEqual(int(cookie['max-age']), 90 * 86400, delta=60)

    def test_access_30_daqiqa(self):
        access = AccessToken(kirish(self.c).json()['access'])
        self.assertAlmostEqual(access['exp'] - access['iat'], 30 * 60, delta=5)

    def test_xodim_refresh_qisqaroq(self):
        xodim = Foydalanuvchi.objects.create(telefon='+998909998877', rol='xodim')
        from .views import _tokens_for_user
        token = RefreshToken(_tokens_for_user(xodim)['refresh'])
        self.assertAlmostEqual(token['exp'] - time.time(), XODIM_REFRESH_KUN * 86400, delta=60)

    def test_xodim_alohida_cookie_oladi_va_mijoz_sessiyasiga_tegmaydi(self):
        mijoz = APIClient()
        kirish(mijoz)
        mijoz_cookie = mijoz.cookies[REFRESH_COOKIE].value
        Foydalanuvchi.objects.create(telefon='+998909998877', rol='xodim')
        r = kirish(mijoz, telefon='+998909998877')
        self.assertIn(REFRESH_COOKIE_XODIM, r.cookies)
        self.assertNotIn(REFRESH_COOKIE, r.cookies)
        self.assertEqual(mijoz.cookies[REFRESH_COOKIE].value, mijoz_cookie)   # mijoz cookie'si joyida
        # Mijoz sessiyasi yangilansa — hamon MIJOZ tokeni chiqadi
        ya = mijoz.post('/api/auth/token/yangilash/', {}, format='json')
        self.assertEqual(ya.status_code, 200)
        self.assertEqual(AccessToken(ya.json()['access'])['user_id'], self.user.pk)

    def test_xodim_sessiyasi_faqat_xodim_cookiesi_bilan_yangilanadi(self):
        xodim = APIClient()
        Foydalanuvchi.objects.create(telefon='+998909998877', rol='xodim')
        kirish(xodim, telefon='+998909998877')
        self.assertEqual(xodim.post('/api/auth/token/yangilash/', {'sessiya': 'xodim'},
                                    format='json').status_code, 200)
        # sessiya ko'rsatilmasa mijoz cookie'si qidiriladi — xodimniki ishlatilmaydi
        self.assertEqual(xodim.post('/api/auth/token/yangilash/', {}, format='json').status_code, 401)

    def test_mijoz_tokeni_xodim_sessiyasida_ishlamaydi(self):
        refresh = str(RefreshToken.for_user(self.user))
        r = APIClient().post('/api/auth/token/yangilash/', {'refresh': refresh, 'sessiya': 'xodim'},
                             format='json')
        self.assertEqual(r.status_code, 401)

    def test_mobil_ilova_refreshni_tanada_oladi_cookie_yoq(self):
        r = kirish(self.c, **MOBIL)
        self.assertIn('refresh', r.json())
        self.assertNotIn(REFRESH_COOKIE, r.cookies)

    def test_cookie_bilan_yangilash_va_rotatsiya(self):
        kirish(self.c)
        eski = self.c.cookies[REFRESH_COOKIE].value
        r = self.c.post('/api/auth/token/yangilash/', {}, format='json')
        self.assertEqual(r.status_code, 200)
        self.assertIn('access', r.json())
        self.assertNotIn('refresh', r.json())
        yangi = r.cookies[REFRESH_COOKIE].value
        self.assertNotEqual(eski, yangi)
        # O'g'irlangan eski nusxa endi ishlamaydi (alohida mijoz, cookie'siz, tanada yuboradi)
        boshqa = APIClient()
        self.assertEqual(boshqa.post('/api/auth/token/yangilash/', {'refresh': eski},
                                     format='json').status_code, 401)
        # Yangisi ishlayveradi
        self.assertEqual(self.c.post('/api/auth/token/yangilash/', {}, format='json').status_code, 200)

    def test_eski_mijoz_tanadagi_refreshni_cookiega_kochiradi(self):
        eski = str(RefreshToken.for_user(self.user))
        r = APIClient().post('/api/auth/token/yangilash/', {'refresh': eski}, format='json')
        self.assertEqual(r.status_code, 200)
        self.assertNotIn('refresh', r.json())
        self.assertIn(REFRESH_COOKIE, r.cookies)

    def test_refreshsiz_401(self):
        r = APIClient().post('/api/auth/token/yangilash/', {}, format='json')
        self.assertEqual(r.status_code, 401)

    def test_yaroqsiz_refresh_401_va_cookie_ochadi(self):
        c = APIClient()
        c.cookies[REFRESH_COOKIE] = 'axlat'
        r = c.post('/api/auth/token/yangilash/', {}, format='json')
        self.assertEqual(r.status_code, 401)
        self.assertEqual(r.cookies[REFRESH_COOKIE].value, '')

    def test_bloklangan_hisob_yangilay_olmaydi(self):
        kirish(self.c)
        Foydalanuvchi.objects.filter(pk=self.user.pk).update(holat='nofaol')
        self.assertEqual(self.c.post('/api/auth/token/yangilash/', {}, format='json').status_code, 401)

    def test_mobil_yangilash_refreshni_tanada_qaytaradi(self):
        refresh = kirish(APIClient(), **MOBIL).json()['refresh']
        r = APIClient().post('/api/auth/token/yangilash/', {'refresh': refresh}, format='json', **MOBIL)
        self.assertEqual(r.status_code, 200)
        self.assertIn('refresh', r.json())
        self.assertNotIn(REFRESH_COOKIE, r.cookies)


class ChiqishTest(TestCase):
    def setUp(self):
        cache.clear()      # IP cheklovlari (15/daqiqa) testlar orasida to'planib qolmasin
        self.c = APIClient()
        self.user = Foydalanuvchi.objects.create(telefon=TELEFON, rol='mijoz')

    def test_chiqishdan_keyin_cookie_ishlamaydi(self):
        kirish(self.c)
        nusxa = self.c.cookies[REFRESH_COOKIE].value        # hujumchi o'g'irlagan nusxa
        r = self.c.post('/api/auth/chiqish/', {}, format='json')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.cookies[REFRESH_COOKIE].value, '')   # cookie o'chirildi
        self.assertEqual(APIClient().post('/api/auth/token/yangilash/', {'refresh': nusxa},
                                          format='json').status_code, 401)

    def test_tanadagi_refresh_bilan_chiqish(self):
        refresh = str(RefreshToken.for_user(self.user))
        APIClient().post('/api/auth/chiqish/', {'refresh': refresh}, format='json')
        self.assertEqual(APIClient().post('/api/auth/token/yangilash/', {'refresh': refresh},
                                          format='json').status_code, 401)

    def test_yaroqsiz_va_bosh_chiqish_xato_bermaydi(self):
        self.assertEqual(self.c.post('/api/auth/chiqish/', {'refresh': 'axlat'}, format='json').status_code, 200)
        self.assertEqual(self.c.post('/api/auth/chiqish/', {}, format='json').status_code, 200)

    def test_ikki_marta_chiqish_xato_bermaydi(self):
        kirish(self.c)
        for _ in range(2):
            self.assertEqual(self.c.post('/api/auth/chiqish/', {}, format='json').status_code, 200)

    def test_blacklistdan_oldin_berilgan_token_ham_yangilanadi(self):
        """OutstandingToken yozuvi yo'q (blacklist yoqilishidan oldin berilgan) token ham ishlaydi."""
        from rest_framework_simplejwt.token_blacklist.models import OutstandingToken
        refresh = str(RefreshToken.for_user(self.user))
        OutstandingToken.objects.all().delete()
        r = APIClient().post('/api/auth/token/yangilash/', {'refresh': refresh}, format='json')
        self.assertEqual(r.status_code, 200)


class EslabQolmaTest(TestCase):
    """«Meni eslab qolma» — refresh cookie brauzer yopilganda o'chadi (muddatsiz)."""

    def setUp(self):
        cache.clear()
        Foydalanuvchi.objects.create(telefon=TELEFON, rol='mijoz')

    def test_eslab_qolma_sessiya_cookiesi(self):
        OtpKod.objects.create(telefon=TELEFON, kod='123456')
        r = APIClient().post('/api/auth/otp/tasdiqlash/',
                             {'telefon': TELEFON, 'kod': '123456', 'eslab': False}, format='json')
        self.assertEqual(r.cookies[REFRESH_COOKIE]['max-age'], '')

    def test_odatda_doimiy_cookie(self):
        r = kirish(APIClient())
        self.assertNotEqual(r.cookies[REFRESH_COOKIE]['max-age'], '')

    def test_yangilashda_ham_saqlanadi(self):
        c = APIClient()
        OtpKod.objects.create(telefon=TELEFON, kod='123456')
        c.post('/api/auth/otp/tasdiqlash/', {'telefon': TELEFON, 'kod': '123456', 'eslab': False}, format='json')
        r = c.post('/api/auth/token/yangilash/', {'eslab': False}, format='json')
        self.assertEqual(r.cookies[REFRESH_COOKIE]['max-age'], '')
