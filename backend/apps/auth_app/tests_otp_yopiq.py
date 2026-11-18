"""Mijoz kirish kodi yo'li xodim va admin uchun yopiq."""
from unittest import mock

from django.core.cache import cache
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from .models import Foydalanuvchi, OtpKod

TEL = '+998901234567'
URL_YUBORISH = '/api/auth/otp/yuborish/'
URL_TASDIQ = '/api/auth/otp/tasdiqlash/'


@override_settings(DEBUG=False)
class OtpYopiqTest(TestCase):
    def setUp(self):
        cache.clear()
        self.c = APIClient()

    def _user(self, rol, holat='faol'):
        return Foydalanuvchi.objects.create(telefon=TEL, rol=rol, holat=holat)

    @mock.patch('apps.auth_app.views._send_otp_sms', return_value=True)
    def test_xodim_kod_ololmaydi(self, yubor):
        self._user('xodim')
        r = self.c.post(URL_YUBORISH, {'telefon': TEL}, format='json')
        self.assertEqual(r.status_code, 403)
        self.assertTrue(r.json()['yopiq_rol'])
        self.assertIn('/xodimlar', r.json()['detail'])
        yubor.assert_not_called()                      # SMS/Telegram puli sarflanmaydi
        self.assertFalse(OtpKod.objects.exists())

    @mock.patch('apps.auth_app.views._send_otp_sms', return_value=True)
    def test_admin_kod_ololmaydi(self, yubor):
        self._user('admin')
        r = self.c.post(URL_YUBORISH, {'telefon': TEL}, format='json')
        self.assertEqual(r.status_code, 403)
        yubor.assert_not_called()

    @mock.patch('apps.auth_app.views._send_otp_sms', return_value=True)
    def test_mijoz_va_yangi_raqam_kod_oladi(self, yubor):
        r = self.c.post(URL_YUBORISH, {'telefon': TEL}, format='json')         # yangi
        self.assertEqual(r.status_code, 200)
        cache.clear()
        self._user('mijoz')
        r = self.c.post(URL_YUBORISH, {'telefon': TEL}, format='json')         # mavjud mijoz
        self.assertEqual(r.status_code, 200)
        self.assertEqual(yubor.call_count, 2)

    def test_bloklangan_xodimga_oldingi_xabar(self):
        self._user('xodim', holat='nofaol')
        r = self.c.post(URL_YUBORISH, {'telefon': TEL}, format='json')
        self.assertEqual(r.status_code, 403)
        self.assertNotIn('yopiq_rol', r.json())        # «hisob bloklangan» xabari saqlanadi

    def test_admin_2bosqich_kodi_bilan_mijoz_yolidan_kirib_bolmaydi(self):
        """Asosiy xavf: admin 2-bosqich kodi (OtpKod) mijoz yo'lida parolsiz token bermasin."""
        self._user('admin')
        OtpKod.objects.create(telefon=TEL, kod='123456')
        r = self.c.post(URL_TASDIQ, {'telefon': TEL, 'kod': '123456'}, format='json')
        self.assertEqual(r.status_code, 403)
        self.assertNotIn('access', r.json())
        self.assertFalse(OtpKod.objects.get(telefon=TEL).ishlatildi)   # kod sarflanmagan: 2-bosqich o'z yo'lida ishlaydi

    def test_xodim_kod_bilan_mijoz_yolidan_kirib_bolmaydi(self):
        self._user('xodim')
        OtpKod.objects.create(telefon=TEL, kod='123456')
        r = self.c.post(URL_TASDIQ, {'telefon': TEL, 'kod': '123456'}, format='json')
        self.assertEqual(r.status_code, 403)
        self.assertNotIn('access', r.json())

    def test_mijoz_kirishi_ishlaydi(self):
        self._user('mijoz')
        OtpKod.objects.create(telefon=TEL, kod='123456')
        r = self.c.post(URL_TASDIQ, {'telefon': TEL, 'kod': '123456'}, format='json')
        self.assertEqual(r.status_code, 200)
        self.assertIn('access', r.json())
