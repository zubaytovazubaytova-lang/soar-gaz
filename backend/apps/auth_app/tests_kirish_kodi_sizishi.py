"""XAVFSIZLIK: xodimning kirish kodi (parol o'rnini bosadi) faqat administratorga ko'rinadi.

Ilgari jamoa ro'yxati (GET /api/auth/xodimlar/) har qanday tizimga kirgan foydalanuvchiga — mijozga ham —
HAMMA xodimning kirish kodini berardi."""
from django.core.cache import cache
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from apps.auth_app.models import Foydalanuvchi

ROYXAT = '/api/auth/xodimlar/'


def klient(user=None):
    c = APIClient()
    if user:
        c.credentials(HTTP_AUTHORIZATION='Bearer ' + str(RefreshToken.for_user(user).access_token))
    return c


class KirishKodiSizishiTestlari(TestCase):
    def setUp(self):
        cache.clear()
        mk = Foydalanuvchi.objects.create
        self.usta = mk(telefon='+998900000801', ism='Aziz', rol='xodim', holat='faol', lavozim='Montaj ustasi',
                       kirish_kodi='XD-USTA11')
        self.kadr = mk(telefon='+998900000802', ism='Ruxsora', rol='xodim', holat='faol',
                       lavozim="Kadrlar bo'yicha mutaxassis", kirish_kodi='XD-KADR11')
        self.mijoz = mk(telefon='+998900000803', ism='Karim', rol='mijoz')
        self.admin = mk(telefon='+998900000804', ism='Ega', rol='admin', is_staff=True, is_superuser=True)

    def royxat(self, user):
        r = klient(user).get(ROYXAT)
        return r, (r.json() if r.status_code == 200 else None)

    def test_mijoz_xodimlar_royxatini_kora_olmaydi(self):
        for yol in (ROYXAT, f'{ROYXAT}{self.kadr.pk}/'):
            r = klient(self.mijoz).get(yol)
            self.assertEqual(r.status_code, 403, yol)
            self.assertNotIn('XD-', r.content.decode())

    def test_anonim_kira_olmaydi(self):
        self.assertEqual(klient().get(ROYXAT).status_code, 401)

    def test_oddiy_xodim_royxatni_koradi_lekin_kodsiz(self):
        r, j = self.royxat(self.usta)
        self.assertEqual(r.status_code, 200)
        royxat = j if isinstance(j, list) else j['results']
        self.assertTrue(royxat)
        self.assertNotIn('kirish_kodi', royxat[0])
        self.assertNotIn('XD-', r.content.decode())          # hech qayerda, hech qaysi xodimniki ham
        # Jamoa sahifasi uchun kerakli maydonlar saqlangan
        for maydon in ('id', 'ism', 'lavozim', 'holat'):
            self.assertIn(maydon, royxat[0])

    def test_oddiy_xodim_boshqa_xodim_tafsilotida_kod_yoq(self):
        r = klient(self.usta).get(f'{ROYXAT}{self.kadr.pk}/')
        self.assertEqual(r.status_code, 200)
        self.assertNotIn('kirish_kodi', r.json())
        self.assertNotIn('XD-KADR11', r.content.decode())

    def test_administrator_kodni_koradi(self):
        r, j = self.royxat(self.admin)
        royxat = j if isinstance(j, list) else j['results']
        kodlar = {x['ism']: x['kirish_kodi'] for x in royxat}
        self.assertEqual(kodlar['Ruxsora'], 'XD-KADR11')
        r = klient(self.admin).get(f'{ROYXAT}{self.usta.pk}/')
        self.assertEqual(r.json()['kirish_kodi'], 'XD-USTA11')

    def test_yozish_faqat_admin(self):
        for u in (self.usta, self.mijoz):
            self.assertEqual(klient(u).post(ROYXAT, {'telefon': '+998900000899', 'ism': 'X'}).status_code, 403)
            self.assertEqual(klient(u).patch(f'{ROYXAT}{self.kadr.pk}/', {'holat': 'nofaol'}).status_code, 403)
        self.kadr.refresh_from_db()
        self.assertEqual(self.kadr.holat, 'faol')

    def test_admin_yangi_xodim_kodini_oladi(self):
        r = klient(self.admin).post(ROYXAT, {'telefon': '+998900000898', 'ism': 'Yangi', 'lavozim': 'Montaj ustasi'})
        self.assertEqual(r.status_code, 201, r.content)
        self.assertTrue(r.json()['kirish_kodi'].startswith('XD-'))

    def test_xodim_profili_va_mijoz_profili_kodsiz(self):
        """Boshqa profil endpointlari ham kodni bermaydi."""
        j = klient(self.usta).get('/api/auth/xodim/profil/').json()
        self.assertNotIn('kirish_kodi', j)
        self.assertNotIn('XD-', klient(self.mijoz).get('/api/auth/profil/').content.decode())
