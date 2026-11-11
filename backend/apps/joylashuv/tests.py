"""Xodimlar joylashuvi: rozilik, smena, nuqta va admin ko'rishi.

Asosiy va'dalar sinaladi: smenasiz nuqta yozilmaydi, rozilik bo'lmasa smena
ochilmaydi, unutilgan smena o'zi yopiladi, oddiy mijoz/xodim boshqalarning
joylashuvini ko'ra olmaydi, ko'rish jurnalga yoziladi.
"""
from datetime import timedelta

from django.core.cache import cache
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from apps.auth_app.models import AuditYozuv, Foydalanuvchi
from .models import Nuqta, Rozilik, Smena

BOSHLASH = '/api/joylashuv/smena/boshlash/'
TUGATISH = '/api/joylashuv/smena/tugatish/'
HOLAT = '/api/joylashuv/smena/'
NUQTA = '/api/joylashuv/nuqta/'
ROYXAT = '/api/joylashuv/royxat/'


def mijoz_ochish(user):
    c = APIClient()
    c.credentials(HTTP_AUTHORIZATION='Bearer ' + str(RefreshToken.for_user(user).access_token))
    return c


class Asos(TestCase):
    def setUp(self):
        cache.clear()
        self.addCleanup(cache.clear)
        self.xodim = Foydalanuvchi.objects.create(telefon='+998900000011', ism='Sinov',
                                                  rol='xodim', holat='faol')
        self.boshqa = Foydalanuvchi.objects.create(telefon='+998900000012', ism='Boshqa',
                                                   rol='xodim', holat='faol')
        self.admin = Foydalanuvchi.objects.create(telefon='+998900000013', ism='Admin',
                                                  rol='admin', holat='faol')
        self.mijoz = Foydalanuvchi.objects.create(telefon='+998900000014', rol='mijoz')
        self.x = mijoz_ochish(self.xodim)
        self.a = mijoz_ochish(self.admin)

    def smena_och(self, client=None):
        r = (client or self.x).post(BOSHLASH, {'rozilik': True}, format='json')
        self.assertEqual(r.status_code, 200, r.content)
        return r


class SmenaTestlari(Asos):
    def test_rozilik_bolmasa_smena_ochilmaydi(self):
        r = self.x.post(BOSHLASH, {}, format='json')
        self.assertEqual(r.status_code, 400)
        self.assertTrue(r.json()['rozilik_kerak'])
        self.assertFalse(Smena.objects.exists())
        self.assertFalse(Rozilik.objects.exists())

    def test_rozilik_faqat_true_bolsa_qabul_qilinadi(self):
        for qiymat in ('true', 1, 'ha', None):
            r = self.x.post(BOSHLASH, {'rozilik': qiymat}, format='json')
            self.assertEqual(r.status_code, 400, qiymat)
        self.assertFalse(Smena.objects.exists())

    def test_rozilik_bilan_smena_ochiladi_va_jurnalga_yoziladi(self):
        r = self.smena_och().json()
        self.assertTrue(r['faol'])
        self.assertTrue(r['rozilik'])
        amallar = set(AuditYozuv.objects.values_list('amal', flat=True))
        self.assertTrue({'joylashuv_rozilik', 'smena_boshlandi'} <= amallar)

    def test_rozilik_bir_marta_beriladi(self):
        self.smena_och()
        self.x.post(TUGATISH)
        r = self.x.post(BOSHLASH, {}, format='json')   # rozilik qayta kerak emas
        self.assertEqual(r.status_code, 200)
        self.assertEqual(Rozilik.objects.count(), 1)

    def test_ikki_marta_boshlash_ikkinchi_smena_ochmaydi(self):
        self.smena_och()
        self.smena_och()
        self.assertEqual(Smena.objects.count(), 1)

    def test_tugatish(self):
        self.smena_och()
        r = self.x.post(TUGATISH).json()
        self.assertFalse(r['faol'])
        smena = Smena.objects.get()
        self.assertIsNotNone(smena.tugadi)
        self.assertEqual(smena.tugash_sababi, 'xodim')

    def test_mijoz_va_admin_smena_ocha_olmaydi(self):
        for client in (mijoz_ochish(self.mijoz), self.a):
            r = client.post(BOSHLASH, {'rozilik': True}, format='json')
            self.assertEqual(r.status_code, 403)
        self.assertFalse(Smena.objects.exists())

    def test_nofaol_xodim_smena_ocha_olmaydi(self):
        self.xodim.holat = 'nofaol'
        self.xodim.save()
        self.assertEqual(self.x.post(BOSHLASH, {'rozilik': True}, format='json').status_code, 403)

    def test_tokensiz_kirish_yoq(self):
        self.assertEqual(APIClient().post(BOSHLASH, {'rozilik': True}, format='json').status_code, 401)
        self.assertEqual(APIClient().post(NUQTA, {'lat': 41, 'lng': 69}, format='json').status_code, 401)

    @override_settings(JOYLASHUV_SMENA_MAX_SOAT=16)
    def test_unutilgan_smena_ozi_yopiladi(self):
        self.smena_och()
        Smena.objects.update(boshlandi=timezone.now() - timedelta(hours=17))
        r = self.x.get(HOLAT).json()
        self.assertFalse(r['faol'])
        smena = Smena.objects.get()
        self.assertEqual(smena.tugash_sababi, 'avto')
        # yopilgan smenaga nuqta yozilmaydi
        self.assertEqual(self.x.post(NUQTA, {'lat': 41.3, 'lng': 69.2}, format='json').status_code, 409)


class NuqtaTestlari(Asos):
    def test_smenasiz_nuqta_yozilmaydi(self):
        r = self.x.post(NUQTA, {'lat': 41.3, 'lng': 69.2}, format='json')
        self.assertEqual(r.status_code, 409)
        self.assertFalse(Nuqta.objects.exists())

    def test_smena_tugagach_nuqta_yozilmaydi(self):
        self.smena_och()
        self.x.post(TUGATISH)
        self.assertEqual(self.x.post(NUQTA, {'lat': 41.3, 'lng': 69.2}, format='json').status_code, 409)
        self.assertFalse(Nuqta.objects.exists())

    def test_nuqta_yoziladi(self):
        self.smena_och()
        r = self.x.post(NUQTA, {'lat': 41.3111, 'lng': 69.2797, 'aniqlik': 12.5}, format='json')
        self.assertEqual(r.status_code, 201)
        n = Nuqta.objects.get()
        self.assertEqual((n.xodim, n.lat, n.lng, n.aniqlik), (self.xodim, 41.3111, 69.2797, 12.5))

    def test_notogri_koordinata_rad_etiladi(self):
        self.smena_och()
        for lat, lng in [(91, 69), (41, 181), ('abc', 69), (None, 69), (41, None),
                         (True, 69), ('nan', 69), (-91, 0)]:
            cache.clear()
            r = self.x.post(NUQTA, {'lat': lat, 'lng': lng}, format='json')
            self.assertEqual(r.status_code, 400, (lat, lng))
        self.assertFalse(Nuqta.objects.exists())

    def test_tez_kelgan_nuqta_tashlanadi(self):
        self.smena_och()
        self.assertEqual(self.x.post(NUQTA, {'lat': 41.3, 'lng': 69.2}, format='json').status_code, 201)
        self.assertEqual(self.x.post(NUQTA, {'lat': 41.4, 'lng': 69.3}, format='json').status_code, 202)
        self.assertEqual(Nuqta.objects.count(), 1)

    def test_nuqta_faqat_oz_smenasiga_yoziladi(self):
        self.smena_och()
        self.x.post(NUQTA, {'lat': 41.3, 'lng': 69.2}, format='json')
        self.assertEqual(Nuqta.objects.get().smena.xodim, self.xodim)
        # boshqa xodimda smena yo'q — uning nuqtasi yozilmaydi
        b = mijoz_ochish(self.boshqa)
        self.assertEqual(b.post(NUQTA, {'lat': 41.3, 'lng': 69.2}, format='json').status_code, 409)


class AdminKorishiTestlari(Asos):
    def test_admin_smenadagilarni_koradi(self):
        self.smena_och()
        self.x.post(NUQTA, {'lat': 41.3111, 'lng': 69.2797}, format='json')
        r = self.a.get(ROYXAT)
        self.assertEqual(r.status_code, 200)
        qatorlar = r.json()
        self.assertEqual(len(qatorlar), 1)
        self.assertEqual(qatorlar[0]['xodim_id'], self.xodim.pk)
        self.assertTrue(qatorlar[0]['aloqada'])
        self.assertEqual(qatorlar[0]['lat'], 41.3111)

    def test_smenasi_yopiq_xodim_royxatda_yoq(self):
        self.smena_och()
        self.x.post(NUQTA, {'lat': 41.3, 'lng': 69.2}, format='json')
        self.x.post(TUGATISH)
        self.assertEqual(self.a.get(ROYXAT).json(), [])

    @override_settings(JOYLASHUV_ALOQA_SONIYA=120)
    def test_eski_nuqta_aloqada_emas(self):
        self.smena_och()
        self.x.post(NUQTA, {'lat': 41.3, 'lng': 69.2}, format='json')
        Nuqta.objects.update(vaqt=timezone.now() - timedelta(minutes=5))
        self.assertFalse(self.a.get(ROYXAT).json()[0]['aloqada'])

    def test_nuqtasiz_smena_royxatda_koordinatasiz(self):
        self.smena_och()
        q = self.a.get(ROYXAT).json()[0]
        self.assertIsNone(q['lat'])
        self.assertFalse(q['aloqada'])

    def test_xodim_va_mijoz_royxatni_kora_olmaydi(self):
        self.smena_och()
        self.x.post(NUQTA, {'lat': 41.3, 'lng': 69.2}, format='json')
        for client in (self.x, mijoz_ochish(self.boshqa), mijoz_ochish(self.mijoz)):
            self.assertEqual(client.get(ROYXAT).status_code, 403)
            self.assertEqual(client.get(f'/api/joylashuv/yol/{self.xodim.pk}/').status_code, 403)

    def test_korish_jurnalga_yoziladi_va_toshib_ketmaydi(self):
        self.smena_och()
        for _ in range(5):
            self.a.get(ROYXAT)
        self.assertEqual(AuditYozuv.objects.filter(amal='joylashuv_korildi').count(), 1)

    def test_yol(self):
        self.smena_och()
        self.x.post(NUQTA, {'lat': 41.3, 'lng': 69.2}, format='json')
        r = self.a.get(f'/api/joylashuv/yol/{self.xodim.pk}/?soat=2').json()
        self.assertEqual(len(r['nuqtalar']), 1)
        self.assertEqual(self.a.get('/api/joylashuv/yol/99999/').status_code, 404)
        # mijoz id si xodim emas — topilmaydi
        self.assertEqual(self.a.get(f'/api/joylashuv/yol/{self.mijoz.pk}/').status_code, 404)

    def test_yol_soat_chegaralanadi(self):
        self.smena_och()
        Nuqta.objects.create(smena=Smena.objects.get(), xodim=self.xodim, lat=1, lng=1)
        Nuqta.objects.update(vaqt=timezone.now() - timedelta(hours=30))
        # soat=999 → 24 ga tushadi, 30 soat oldingi nuqta chiqmaydi
        self.assertEqual(self.a.get(f'/api/joylashuv/yol/{self.xodim.pk}/?soat=999').json()['nuqtalar'], [])
        self.assertEqual(self.a.get(f'/api/joylashuv/yol/{self.xodim.pk}/?soat=xx').status_code, 200)


class TozalashTestlari(Asos):
    @override_settings(JOYLASHUV_SAQLASH_KUN=30)
    def test_eski_nuqtalar_ochadi_yangilari_qoladi(self):
        self.smena_och()
        smena = Smena.objects.get()
        eski = Nuqta.objects.create(smena=smena, xodim=self.xodim, lat=1, lng=1)
        yangi = Nuqta.objects.create(smena=smena, xodim=self.xodim, lat=2, lng=2)
        Nuqta.objects.filter(pk=eski.pk).update(vaqt=timezone.now() - timedelta(days=31))
        call_command('joylashuv_tozala', verbosity=0)
        self.assertEqual(list(Nuqta.objects.values_list('pk', flat=True)), [yangi.pk])
