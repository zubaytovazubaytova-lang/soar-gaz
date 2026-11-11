"""«Uning ko'zi bilan ko'rish»: faqat egasi ochadi, token faqat o'qish uchun,
har ochish va bloklangan urinish jurnalga yoziladi."""
from datetime import timedelta

from django.core.cache import cache
from django.test import TestCase, override_settings
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken, RefreshToken

from apps.auth_app.models import AuditYozuv, Foydalanuvchi

BOSHLASH = '/api/auth/korish/{}/'


def klient(user):
    c = APIClient()
    c.credentials(HTTP_AUTHORIZATION='Bearer ' + str(RefreshToken.for_user(user).access_token))
    return c


def token_bilan(token):
    c = APIClient()
    c.credentials(HTTP_AUTHORIZATION='Bearer ' + token)
    return c


class Asos(TestCase):
    def setUp(self):
        cache.clear()
        self.addCleanup(cache.clear)
        mk = Foydalanuvchi.objects.create
        self.egasi = mk(telefon='+998900000101', ism='Egasi', rol='admin', holat='faol',
                        is_superuser=True, is_staff=True)
        self.admin = mk(telefon='+998900000102', ism='Oddiy admin', rol='admin', holat='faol')
        self.xodim = mk(telefon='+998900000103', ism='Aziz', rol='xodim', holat='faol', lavozim='Usta')
        self.mijoz = mk(telefon='+998900000104', ism='Karim', rol='mijoz')
        self.e = klient(self.egasi)

    def ochish(self, hedaf):
        r = self.e.post(BOSHLASH.format(hedaf.pk))
        self.assertEqual(r.status_code, 200, r.content)
        return r.json()


class BoshlashTestlari(Asos):
    def test_egasi_xodim_nomidan_ochadi(self):
        j = self.ochish(self.xodim)
        self.assertEqual((j['rol'], j['portal'], j['ism']), ('xodim', '/xodimlar/', 'Aziz'))
        self.assertTrue(j['access'])
        self.assertNotIn('refresh', j)            # yangilanmaydi
        self.assertEqual(j['muddat_daqiqa'], 30)

    def test_egasi_mijoz_nomidan_ochadi(self):
        j = self.ochish(self.mijoz)
        self.assertEqual((j['rol'], j['portal']), ('mijoz', '/kabinet/'))

    def test_faqat_egasi_ocha_oladi(self):
        for c in (klient(self.admin), klient(self.xodim), klient(self.mijoz), APIClient()):
            self.assertIn(c.post(BOSHLASH.format(self.xodim.pk)).status_code, (401, 403))
        self.assertFalse(AuditYozuv.objects.filter(amal='korish_boshlandi').exists())

    def test_admin_nomidan_korib_bolmaydi(self):
        for hedaf in (self.admin, self.egasi):
            self.assertEqual(self.e.post(BOSHLASH.format(hedaf.pk)).status_code, 404)
        self.assertEqual(self.e.post(BOSHLASH.format(99999)).status_code, 404)

    def test_har_ochish_jurnalga_yoziladi(self):
        self.ochish(self.xodim)
        y = AuditYozuv.objects.get(amal='korish_boshlandi')
        self.assertEqual(y.kim, self.egasi)                       # kim
        self.assertIn('Aziz', y.tafsilot)                         # kimning nomidan
        self.assertIn(self.xodim.telefon, y.tafsilot)
        self.assertIsNotNone(y.vaqt)                              # qachon
        self.ochish(self.xodim)
        self.assertEqual(AuditYozuv.objects.filter(amal='korish_boshlandi').count(), 2)

    def test_korish_tokeni_bilan_boshqani_ochib_bolmaydi(self):
        j = self.ochish(self.xodim)
        r = token_bilan(j['access']).post(BOSHLASH.format(self.mijoz.pk))
        self.assertEqual(r.status_code, 403)


class OqishRejimiTestlari(Asos):
    def test_token_hedaf_nomidan_oqiydi(self):
        j = self.ochish(self.xodim)
        r = token_bilan(j['access']).get('/api/auth/xodim/profil/')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()['ism'], 'Aziz')
        j = self.ochish(self.mijoz)
        r = token_bilan(j['access']).get('/api/auth/profil/')
        self.assertEqual(r.json()['ism'], 'Karim')

    def test_barcha_ozgartiruvchi_sorovlar_bloklanadi(self):
        c = token_bilan(self.ochish(self.xodim)['access'])
        for usul, yol in [('post', '/api/tushum/'), ('post', '/api/aloqa/oqildi/'),
                          ('post', '/api/joylashuv/smena/boshlash/'), ('patch', '/api/auth/xodim/profil/'),
                          ('put', '/api/auth/xodim/profil/'), ('delete', '/api/auth/xodim/profil/'),
                          ('post', '/api/auth/otp/yuborish/')]:
            r = getattr(c, usul)(yol, {'summa': 1000}, format='json')
            self.assertEqual(r.status_code, 403, (usul, yol))

    def test_hech_narsa_ozgarmaydi(self):
        c = token_bilan(self.ochish(self.xodim)['access'])
        c.patch('/api/auth/xodim/profil/', {'email': 'x@y.uz'}, format='json')
        c.post('/api/tushum/', {'summa': 5000, 'usul': 'naqd'}, format='json')
        self.xodim.refresh_from_db()
        self.assertEqual(self.xodim.email, '')
        from apps.tushum.models import Tushum
        self.assertFalse(Tushum.objects.exists())

    def test_bloklangan_urinish_jurnalga_yoziladi_va_toshib_ketmaydi(self):
        c = token_bilan(self.ochish(self.xodim)['access'])
        for _ in range(4):
            c.post('/api/tushum/', {'summa': 5000}, format='json')
        y = AuditYozuv.objects.filter(amal='korish_rad')
        self.assertEqual(y.count(), 1)
        self.assertEqual(y.get().kim, self.egasi)
        self.assertIn('Aziz', y.get().tafsilot)

    def test_oddiy_token_ishlashda_davom_etadi(self):
        # Ko'rish qoidalari oddiy xodim tokenlariga tegmaydi
        r = klient(self.xodim).patch('/api/auth/xodim/profil/', {'email': 'x@y.uz'}, format='json')
        self.assertEqual(r.status_code, 200)

    @override_settings(KORISH_DAQIQA=-1)
    def test_muddati_tugagan_token_ishlamaydi(self):
        j = self.ochish(self.xodim)
        self.assertEqual(token_bilan(j['access']).get('/api/auth/xodim/profil/').status_code, 401)

    def test_egasi_huquqini_yoqotsa_token_ishlamaydi(self):
        j = self.ochish(self.xodim)
        Foydalanuvchi.objects.filter(pk=self.egasi.pk).update(is_superuser=False)
        self.assertEqual(token_bilan(j['access']).get('/api/auth/xodim/profil/').status_code, 401)

    def test_egasi_nofaol_bolsa_token_ishlamaydi(self):
        j = self.ochish(self.xodim)
        Foydalanuvchi.objects.filter(pk=self.egasi.pk).update(holat='nofaol')
        self.assertEqual(token_bilan(j['access']).get('/api/auth/xodim/profil/').status_code, 401)

    def test_soxta_korish_tokeni_ishlamaydi(self):
        # Oddiy admin o'zi uchun `korish_egasi` ni egasiga qo'yib token yasay olmaydi: imzo kerak
        token = AccessToken.for_user(self.xodim)
        token['korish'] = True
        token['korish_egasi'] = self.admin.pk                   # egasi emas
        self.assertEqual(token_bilan(str(token)).get('/api/auth/xodim/profil/').status_code, 401)
