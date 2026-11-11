"""Metrologiya bo'limi arizasi (`/api/tolovlar/metrologiya-ariza/`) testlari.

Forma ochiq (login talab qilmaydi), shuning uchun ariza saqlanishi,
noto'g'ri ma'lumotning rad etilishi va spamdan himoya alohida sinaladi.
"""

from django.core.cache import cache
from django.test import TestCase
from rest_framework.test import APIClient

from .models import MetrologiyaArizasi

URL = '/api/tolovlar/metrologiya-ariza/'


class MetrologiyaArizaTest(TestCase):
    def setUp(self):
        cache.clear()  # throttle hisoblagichi testlar orasida tozalansin
        self.client = APIClient()
        self.data = {
            'ism': 'Ali Valiyev', 'telefon': '+998901234567',
            'xizmat': 'qiyoslov', 'hisoblagich': 'G4',
            'seriya_raqam': 'UZ20241234', 'ornatilgan_yil': 2020,
            'manzil': 'Buxoro, Navoiy ko\'chasi', 'izoh': '',
        }

    def test_ariza_saqlanadi(self):
        r = self.client.post(URL, self.data, format='json')
        self.assertEqual(r.status_code, 201, r.content)
        a = MetrologiyaArizasi.objects.get(pk=r.json()['id'])
        self.assertEqual(a.xizmat, 'qiyoslov')
        self.assertEqual(a.holat, 'yangi')
        self.assertEqual(a.seriya_raqam, 'UZ20241234')

    def test_holatni_mijoz_belgilay_olmaydi(self):
        r = self.client.post(URL, {**self.data, 'holat': 'yakunlandi'}, format='json')
        self.assertEqual(r.status_code, 201)
        self.assertEqual(MetrologiyaArizasi.objects.get().holat, 'yangi')

    def test_xizmat_turi_ixtiyoriy_bosh_qoldirilsa_ham_qabul_qilinadi(self):
        r = self.client.post(URL, {**self.data, 'xizmat': ''}, format='json')
        self.assertEqual(r.status_code, 201, r.content)
        a = MetrologiyaArizasi.objects.get(pk=r.json()['id'])
        self.assertEqual(a.xizmat, '')
        self.assertEqual(a.holat, 'yangi')
        self.assertIn('tanlanmagan', str(a))

    def test_xizmat_turi_umuman_yuborilmasa_ham_qabul_qilinadi(self):
        d = dict(self.data)
        d.pop('xizmat')
        r = self.client.post(URL, d, format='json')
        self.assertEqual(r.status_code, 201, r.content)
        self.assertEqual(MetrologiyaArizasi.objects.get().xizmat, '')

    def test_xizmat_tanlanmagan_arizada_sms_matni_toza(self):
        from unittest import mock
        with mock.patch('apps.tolovlar.views._sms_yuborish') as sms:
            self.client.post(URL, {**self.data, 'xizmat': ''}, format='json')
            self.client.post(URL, {**self.data, 'seriya_raqam': 'UZ777', 'xizmat': 'qiyoslov'}, format='json')
        matnlar = [c.args[1] for c in sms.call_args_list]
        self.assertTrue(matnlar[0].startswith('SOAR GAZ: metrologiya arizangiz #'), matnlar[0])
        self.assertIn('metrologiya (Davlat qiyoslov ko\'rigi) arizangiz', matnlar[1])

    def test_tanlanmagan_va_tanlangan_ariza_bir_biriga_xalaqit_bermaydi(self):
        # Bir xil telefon+seriya: xizmati tanlanmagan ariza ochiq tursa ham, tanlangan ariza qabul qilinadi
        self.assertEqual(self.client.post(URL, {**self.data, 'xizmat': ''}, format='json').status_code, 201)
        self.assertEqual(self.client.post(URL, self.data, format='json').status_code, 201)

    def test_notogri_xizmat_rad_etiladi(self):
        r = self.client.post(URL, {**self.data, 'xizmat': 'ekspertiza'}, format='json')
        self.assertEqual(r.status_code, 400)
        self.assertEqual(MetrologiyaArizasi.objects.count(), 0)

    def test_notogri_telefon_rad_etiladi(self):
        r = self.client.post(URL, {**self.data, 'telefon': '12'}, format='json')
        self.assertEqual(r.status_code, 400)
        self.assertIn('telefon', r.json())

    def test_notogri_yil_rad_etiladi(self):
        r = self.client.post(URL, {**self.data, 'ornatilgan_yil': 1800}, format='json')
        self.assertEqual(r.status_code, 400)

    def test_ism_majburiy(self):
        d = dict(self.data)
        d.pop('ism')
        self.assertEqual(self.client.post(URL, d, format='json').status_code, 400)

    def test_spamdan_himoya(self):
        for i in range(10):
            d = {**self.data, 'seriya_raqam': f'UZ{i:04d}'}
            self.assertEqual(self.client.post(URL, d, format='json').status_code, 201)
        d = {**self.data, 'seriya_raqam': 'UZ9999'}
        self.assertEqual(self.client.post(URL, d, format='json').status_code, 429)

    def test_telefon_yagona_korinishga_keltiriladi(self):
        for kiritilgan in ('90 123 45 67', '0901234567', '+998 90 123-45-67', '998901234567'):
            MetrologiyaArizasi.objects.all().delete()
            r = self.client.post(URL, {**self.data, 'telefon': kiritilgan}, format='json')
            self.assertEqual(r.status_code, 201, (kiritilgan, r.content))
            self.assertEqual(r.json()['telefon'], '+998901234567', kiritilgan)

    def test_998_raqam_uzunligi_tekshiriladi(self):
        r = self.client.post(URL, {**self.data, 'telefon': '+99890123'}, format='json')
        self.assertEqual(r.status_code, 400)

    def test_hisoblagich_va_seriya_majburiy(self):
        for kalit in ('hisoblagich', 'seriya_raqam'):
            d = {**self.data, kalit: ''}
            self.assertEqual(self.client.post(URL, d, format='json').status_code, 400, kalit)

    def test_notogri_hisoblagich_modeli_rad_etiladi(self):
        r = self.client.post(URL, {**self.data, 'hisoblagich': 'XYZ'}, format='json')
        self.assertEqual(r.status_code, 400)
        self.assertIn('hisoblagich', r.json())

    def test_seriya_raqam_tozalanadi(self):
        r = self.client.post(URL, {**self.data, 'seriya_raqam': ' uz 2024 1234 '}, format='json')
        self.assertEqual(r.json()['seriya_raqam'], 'UZ20241234')

    def test_takroriy_ariza_rad_etiladi(self):
        self.assertEqual(self.client.post(URL, self.data, format='json').status_code, 201)
        r = self.client.post(URL, self.data, format='json')
        self.assertEqual(r.status_code, 400)
        self.assertEqual(MetrologiyaArizasi.objects.count(), 1)

    def test_yakunlangan_arizadan_keyin_yangisi_mumkin(self):
        self.client.post(URL, self.data, format='json')
        MetrologiyaArizasi.objects.update(holat='yakunlandi')
        self.assertEqual(self.client.post(URL, self.data, format='json').status_code, 201)
