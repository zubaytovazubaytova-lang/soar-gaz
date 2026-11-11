"""Maxfiy amallar (email / qo'shimcha telefon o'zgartirish, hisobni o'chirish) uchun SMS tasdiq."""
from unittest import mock

from django.core.cache import cache
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from .models import Foydalanuvchi, OtpKod

TELEFON = '+998901112233'


class TasdiqKodiTest(TestCase):
    def setUp(self):
        cache.clear()
        self.user = Foydalanuvchi.objects.create(
            telefon=TELEFON, rol='mijoz', ism='Ali', email='eski@mail.uz')
        self.c = APIClient()
        self.c.credentials(
            HTTP_AUTHORIZATION='Bearer ' + str(RefreshToken.for_user(self.user).access_token))

    def kod(self, kod='654321'):
        OtpKod.objects.create(telefon=TELEFON, kod=kod)
        return kod

    def patch(self, **data):
        return self.c.patch('/api/auth/profil/', data, format='json')

    # ── Oddiy maydonlar kod talab qilmaydi ──
    def test_ism_va_manzil_kodsiz_ozgaradi(self):
        r = self.patch(ism='Vali', manzil='Toshkent')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()['ism'], 'Vali')

    def test_email_ozgarmasa_kod_sorlmaydi(self):
        """Forma hamma maydonni qayta yuboradi — qiymat o'zgarmasa kod kerak emas."""
        self.assertEqual(self.patch(ism='Vali', email='eski@mail.uz').status_code, 200)

    # ── Email / qo'shimcha telefon ──
    def test_email_ozgartirish_kodsiz_rad_etiladi(self):
        r = self.patch(email='hujumchi@mail.uz')
        self.assertEqual(r.status_code, 403)
        self.assertTrue(r.json()['kod_kerak'])
        self.user.refresh_from_db()
        self.assertEqual(self.user.email, 'eski@mail.uz')

    def test_qoshimcha_telefon_kodsiz_rad_etiladi(self):
        self.assertEqual(self.patch(qoshimcha_telefon='+998900000000').status_code, 403)

    def test_notogri_kod_rad_etiladi(self):
        self.kod('654321')
        r = self.patch(email='yangi@mail.uz', tasdiq_kodi='111111')
        self.assertEqual(r.status_code, 400)
        self.user.refresh_from_db()
        self.assertEqual(self.user.email, 'eski@mail.uz')

    def test_togri_kod_bilan_ozgaradi_va_bir_martalik(self):
        kod = self.kod()
        r = self.patch(email='yangi@mail.uz', tasdiq_kodi=kod)
        self.assertEqual(r.status_code, 200)
        self.user.refresh_from_db()
        self.assertEqual(self.user.email, 'yangi@mail.uz')
        # Shu kod bilan ikkinchi marta o'zgartirib bo'lmaydi
        self.assertEqual(self.patch(email='yana@mail.uz', tasdiq_kodi=kod).status_code, 400)

    def test_muddati_otgan_kod(self):
        from django.utils import timezone
        kod = self.kod()
        OtpKod.objects.filter(telefon=TELEFON).update(
            yaratilgan=timezone.now() - timezone.timedelta(minutes=30))
        self.assertEqual(self.patch(email='yangi@mail.uz', tasdiq_kodi=kod).status_code, 400)

    def test_kop_notogri_urinishdan_keyin_bloklanadi(self):
        self.kod()
        kodlar = []
        for i in range(12):
            kodlar.append(self.patch(email='yangi@mail.uz', tasdiq_kodi=str(100000 + i)).status_code)
        self.assertIn(429, kodlar)

    def test_begona_telefon_kodi_ishlamaydi(self):
        OtpKod.objects.create(telefon='+998900000099', kod='222222')
        self.assertEqual(self.patch(email='yangi@mail.uz', tasdiq_kodi='222222').status_code, 400)

    def test_kirmagan_foydalanuvchi_kod_so_ray_olmaydi(self):
        self.assertEqual(APIClient().post('/api/auth/tasdiq-kodi/', {}, format='json').status_code, 401)

    # ── Kod yuborish ──
    @mock.patch('apps.auth_app.views._send_otp_sms', return_value=True)
    def test_kod_faqat_oz_telefoniga_yuboriladi(self, sms):
        r = self.c.post('/api/auth/tasdiq-kodi/', {'telefon': '+998900000001'}, format='json')
        self.assertEqual(r.status_code, 200)
        sms.assert_called_once()
        self.assertEqual(sms.call_args[0][0], TELEFON)        # so'rovdagi telefon e'tiborsiz
        self.assertTrue(OtpKod.objects.filter(telefon=TELEFON).exists())
        self.assertFalse(OtpKod.objects.filter(telefon='+998900000001').exists())

    @mock.patch('apps.auth_app.views._send_otp_sms', return_value=True)
    def test_kod_tez_tez_sorab_bolmaydi(self, sms):
        self.assertEqual(self.c.post('/api/auth/tasdiq-kodi/', {}, format='json').status_code, 200)
        self.assertEqual(self.c.post('/api/auth/tasdiq-kodi/', {}, format='json').status_code, 429)

    @mock.patch('apps.auth_app.views._send_otp_sms', return_value=False)
    def test_sms_yuborilmasa_502(self, sms):
        self.assertEqual(self.c.post('/api/auth/tasdiq-kodi/', {}, format='json').status_code, 502)

    # ── Hisobni o'chirish ──
    def test_hisobni_ochirish_kodsiz_rad_etiladi(self):
        r = self.c.post('/api/kabinet/hisob/ochirish/', {'tasdiq': "O'CHIRISH"}, format='json')
        self.assertEqual(r.status_code, 403)
        self.assertTrue(r.json()['kod_kerak'])
        self.user.refresh_from_db()
        self.assertEqual(self.user.holat, 'faol')

    def test_hisobni_ochirish_kod_bilan(self):
        r = self.c.post('/api/kabinet/hisob/ochirish/',
                        {'tasdiq': "O'CHIRISH", 'tasdiq_kodi': self.kod()}, format='json')
        self.assertEqual(r.status_code, 200)
        self.user.refresh_from_db()
        self.assertEqual(self.user.holat, 'nofaol')
