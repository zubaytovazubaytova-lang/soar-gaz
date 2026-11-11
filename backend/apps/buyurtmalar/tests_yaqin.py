"""Ariza joylashuviga eng yaqin xodimni topish va yuborish (smena davomidagi GPS nuqtalari bo'yicha)."""
from datetime import timedelta

from django.utils import timezone

from apps.auth_app.models import AuditYozuv
from apps.buyurtmalar.models import Buyurtma
from apps.buyurtmalar.tests_operator import ARIZALAR, Asos, klient
from apps.joylashuv.models import Nuqta, Smena
from apps.sms_app.models import SmsXabar


class YaqinXodimTestlari(Asos):
    # Buxoro shahri markazi: ariza shu yerda
    LAT, LNG = 39.7747, 64.4286

    def setUp(self):
        super().setUp()
        self.aholi.lat, self.aholi.lng = self.LAT, self.LNG
        self.aholi.save()

    def smenada(self, xodim, lat, lng, daqiqa_oldin=1):
        s = Smena.objects.create(xodim=xodim)
        n = Nuqta.objects.create(smena=s, xodim=xodim, lat=lat, lng=lng)
        Nuqta.objects.filter(pk=n.pk).update(vaqt=timezone.now() - timedelta(minutes=daqiqa_oldin))
        return s

    def yaqin(self, user=None):
        return klient(user or self.call).get(f'{ARIZALAR}{self.aholi.id}/yaqin/')

    def yubor(self, user=None, **data):
        return klient(user or self.call).post(f'{ARIZALAR}{self.aholi.id}/yaqin-yuborish/', data)

    def test_masofa_tartibi_va_masofa(self):
        self.smenada(self.usta, self.LAT + 0.09, self.LNG)       # ~10 km shimolda
        self.smenada(self.usta2, self.LAT + 0.018, self.LNG)     # ~2 km
        j = self.yaqin().json()
        self.assertEqual([n['id'] for n in j['nomzodlar']], [self.usta2.id, self.usta.id])
        self.assertAlmostEqual(j['nomzodlar'][0]['masofa_km'], 2.0, delta=0.1)
        self.assertAlmostEqual(j['nomzodlar'][1]['masofa_km'], 10.0, delta=0.2)

    def test_xodim_koordinatasi_operatorga_berilmaydi(self):
        self.smenada(self.usta, self.LAT + 0.02, self.LNG)
        n = self.yaqin().json()['nomzodlar'][0]
        for yashirin in ('lat', 'lng', '_km'):
            self.assertNotIn(yashirin, n)

    def test_smenada_bolmagan_va_eski_nuqtali_nomalum(self):
        self.smenada(self.usta, self.LAT, self.LNG, daqiqa_oldin=30)       # nuqta 10 daqiqadan eski
        j = self.yaqin().json()                                            # usta2 smena ochmagan
        self.assertEqual(j['nomzodlar'], [])
        sabab = {x['id']: x['sabab'] for x in j['nomalum']}
        self.assertEqual(sabab[self.usta.id], 'Joylashuvi yangilanmagan')
        self.assertEqual(sabab[self.usta2.id], 'Smenada emas')

    def test_yopilgan_smena_hisobga_olinmaydi(self):
        s = self.smenada(self.usta, self.LAT, self.LNG)
        Smena.objects.filter(pk=s.pk).update(tugadi=timezone.now())
        self.assertEqual(self.yaqin().json()['nomzodlar'], [])

    def test_kadr_va_operator_nomzod_bolmaydi(self):
        self.smenada(self.kadr, self.LAT, self.LNG)
        self.smenada(self.call, self.LAT, self.LNG)
        self.assertEqual(self.yaqin().json()['nomzodlar'], [])

    def test_joylashuv_belgilanmagan(self):
        r = klient(self.call).get(f'{ARIZALAR}{self.ulgurji.id}/yaqin/')
        self.assertEqual(r.status_code, 409)
        self.assertTrue(r.json()['joy_yoq'])
        r = klient(self.call).post(f'{ARIZALAR}{self.ulgurji.id}/yaqin-yuborish/')
        self.assertEqual(r.status_code, 409)

    def test_eng_yaqinga_yuborish(self):
        self.smenada(self.usta, self.LAT + 0.09, self.LNG)
        self.smenada(self.usta2, self.LAT + 0.018, self.LNG)
        r = self.yubor()
        self.assertEqual(r.status_code, 200, r.content)
        self.aholi.refresh_from_db()
        self.assertEqual((self.aholi.xodim, self.aholi.holat), (self.usta2, 'yangi'))
        self.assertEqual(r.json()['xodim']['id'], self.usta2.id)
        yozuv = AuditYozuv.objects.filter(amal='buyurtma_tayinlandi').first()
        self.assertIn('eng yaqin xodim', yozuv.tafsilot)
        self.assertTrue(SmsXabar.objects.filter(mijoz=self.usta2).exists())

    def test_band_xodim_otkazib_yuboriladi(self):
        self.smenada(self.usta2, self.LAT + 0.018, self.LNG)         # eng yaqin, lekin band
        self.smenada(self.usta, self.LAT + 0.09, self.LNG)
        for _i in range(5):
            Buyurtma.objects.create(mijoz=self.mijoz, xizmat='montaj', xodim=self.usta2, holat='qabul')
        self.assertEqual(self.yubor().status_code, 200)
        self.aholi.refresh_from_db()
        self.assertEqual(self.aholi.xodim, self.usta)                # band bo'lmagan keyingisi

    def test_hamma_band_yoki_hech_kim_yoq(self):
        self.assertEqual(self.yubor().status_code, 409)              # smenada hech kim yo'q
        self.smenada(self.usta, self.LAT, self.LNG)
        for _i in range(5):
            Buyurtma.objects.create(mijoz=self.mijoz, xizmat='montaj', xodim=self.usta, holat='bajarilmoqda')
        r = self.yubor()
        self.assertEqual(r.status_code, 409)
        self.assertIn('band', r.json()['detail'])
        self.aholi.refresh_from_db()
        self.assertIsNone(self.aholi.xodim)

    def test_royxatdan_aniq_xodimni_tanlash(self):
        self.smenada(self.usta, self.LAT + 0.09, self.LNG)
        self.smenada(self.usta2, self.LAT + 0.018, self.LNG)
        self.assertEqual(self.yubor(xodim_id=self.usta.id).status_code, 200)
        self.aholi.refresh_from_db()
        self.assertEqual(self.aholi.xodim, self.usta)
        self.assertIn('yaqin xodimlar', AuditYozuv.objects.filter(amal='buyurtma_tayinlandi').first().tafsilot)
        # Joylashuvi aniqlanmagan xodimni bu yo'l bilan yuborib bo'lmaydi
        self.aholi.holat, self.aholi.xodim = 'yangi', None
        self.aholi.save()
        self.assertEqual(self.yubor(xodim_id=self.kadr.id).status_code, 409)

    def test_bajarilayotgan_arizani_yuborib_bolmaydi(self):
        self.smenada(self.usta, self.LAT, self.LNG)
        self.aholi.holat, self.aholi.xodim = 'bajarilmoqda', self.usta2
        self.aholi.save()
        self.assertEqual(self.yubor().status_code, 409)

    def test_ruxsatlar_va_ikkalasi_bir_xil(self):
        self.ulgurji.lat, self.ulgurji.lng = self.LAT, self.LNG
        self.ulgurji.save()
        for u in (self.kadr, self.call):                   # Ruxsora ham, Nargiza ham ulgurjiga ham yaqin xodim qidiradi
            self.assertEqual(klient(u).get(f'{ARIZALAR}{self.ulgurji.id}/yaqin/').status_code, 200)
        for u in (self.usta, self.servis, self.mijoz, self.admin):
            self.assertEqual(self.yaqin(u).status_code, 403)
            self.assertEqual(self.yubor(u).status_code, 403)
            self.assertEqual(klient(u).post(f'{ARIZALAR}{self.aholi.id}/joy/', {'lat': 39.7, 'lng': 64.4}).status_code, 403)

    def test_qidiruv_jurnalga_yoziladi(self):
        self.smenada(self.usta, self.LAT, self.LNG)
        self.yaqin()
        self.yaqin()                                                # ikkinchisi 10 daqiqa ichida: qayta yozilmaydi
        self.assertEqual(AuditYozuv.objects.filter(amal='joylashuv_korildi', kim=self.call).count(), 1)


class JoyBelgilashTestlari(Asos):
    def test_joy_belgilash(self):
        r = klient(self.call).post(f'{ARIZALAR}{self.ulgurji.id}/joy/', {'lat': 39.77, 'lng': 64.43})
        self.assertEqual(r.status_code, 200)
        self.ulgurji.refresh_from_db()
        self.assertEqual((self.ulgurji.lat, self.ulgurji.lng), (39.77, 64.43))
        self.assertTrue(r.json()['joy_bor'])

    def test_notogri_koordinata(self):
        c = klient(self.call)
        for d in ({}, {'lat': 39.7}, {'lat': 'abc', 'lng': 64}, {'lat': 0, 'lng': 0}, {'lat': 55.7, 'lng': 37.6},
                  {'lat': 'nan', 'lng': 64.4}, {'lat': True, 'lng': True}):
            self.assertEqual(c.post(f'{ARIZALAR}{self.ulgurji.id}/joy/', d, format='json').status_code, 400, d)
        self.ulgurji.refresh_from_db()
        self.assertIsNone(self.ulgurji.lat)

    def test_ariza_kiritishda_joy_va_avto_yuborish(self):
        s = Smena.objects.create(xodim=self.usta)
        Nuqta.objects.create(smena=s, xodim=self.usta, lat=39.78, lng=64.43)
        r = klient(self.call).post(ARIZALAR, self.ariza(lat=39.7747, lng=64.4286, yaqin_yuborish=True), format='json')
        self.assertEqual(r.status_code, 201, r.content)
        j = r.json()
        self.assertTrue(j['joy_bor'])
        self.assertTrue(j['yaqin']['yuborildi'])
        self.assertEqual(j['xodim_id'], self.usta.id)

    def test_avto_yuborish_xodim_topilmasa_ariza_baribir_saqlanadi(self):
        r = klient(self.call).post(ARIZALAR, self.ariza(lat=39.7747, lng=64.4286, yaqin_yuborish=True), format='json')
        self.assertEqual(r.status_code, 201)
        self.assertFalse(r.json()['yaqin']['yuborildi'])
        self.assertIsNone(r.json()['xodim_id'])
        self.assertEqual(Buyurtma.objects.count(), 3)

    def test_avto_yuborish_joysiz_rad(self):
        r = klient(self.call).post(ARIZALAR, self.ariza(yaqin_yuborish=True), format='json')
        self.assertEqual(r.status_code, 400)
        self.assertEqual(Buyurtma.objects.count(), 2)

    def test_notogri_koordinata_bilan_ariza_yaratilmaydi(self):
        r = klient(self.call).post(ARIZALAR, self.ariza(lat=10, lng=10), format='json')
        self.assertEqual(r.status_code, 400)
        self.assertEqual(Buyurtma.objects.count(), 2)

    def test_mijozga_koordinata_korinmaydi(self):
        self.ulgurji.lat, self.ulgurji.lng = 39.77, 64.43
        self.ulgurji.save()
        d = klient(self.mijoz).get('/api/buyurtmalar/').json()
        self.assertTrue(d)
        for b in d:
            self.assertNotIn('lat', b)
            self.assertNotIn('lng', b)
