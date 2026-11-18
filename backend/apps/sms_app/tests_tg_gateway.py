"""Telegram Gateway: tasdiqlash kodi raqam bo'yicha (botsiz) yuboriladi; SMS/botga zaxira."""
import io
from unittest import mock

from django.core.cache import cache
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from apps.auth_app.models import OtpKod
from . import tg_gateway
from .gateway import sozlanganmi
from .models import TelegramUlanish

GW = dict(TELEGRAM_GATEWAY_TOKEN='gw-token-TEST', DEBUG=False, SMS_PROVAYDER='konsol',
          TELEGRAM_BOT_TOKEN='', TELEGRAM_BOT_USERNAME='')
TEL = '+998901234567'


@override_settings(**GW)
class KodYuborTest(TestCase):
    @mock.patch('apps.sms_app.tg_gateway._api', return_value={'request_id': 'r1', 'request_cost': 0.01})
    def test_togri_parametrlar(self, api):
        self.assertTrue(tg_gateway.kod_yubor('998 90 123-45-67', '123456'))
        api.assert_called_once_with('sendVerificationMessage', {
            'phone_number': TEL, 'code': '123456', 'ttl': 300})

    @mock.patch('apps.sms_app.tg_gateway._api', return_value={})
    def test_ttl_30_3600_oraliqda(self, api):
        tg_gateway.kod_yubor(TEL, '123456', ttl=5)
        self.assertEqual(api.call_args[0][1]['ttl'], 30)
        tg_gateway.kod_yubor(TEL, '123456', ttl=99999)
        self.assertEqual(api.call_args[0][1]['ttl'], 3600)

    @mock.patch('apps.sms_app.tg_gateway._api', side_effect=tg_gateway.GatewayXato('PHONE_NUMBER_NOT_FOUND'))
    def test_raqam_telegramda_yoq_false(self, api):
        self.assertFalse(tg_gateway.kod_yubor(TEL, '123456'))

    @mock.patch('apps.sms_app.tg_gateway._api')
    def test_notogri_kod_yuborilmaydi(self, api):
        for kod in ('12', '123456789', 'abc123', ''):
            self.assertFalse(tg_gateway.kod_yubor(TEL, kod), kod)
        self.assertFalse(tg_gateway.kod_yubor('', '123456'))
        api.assert_not_called()

    @override_settings(TELEGRAM_GATEWAY_TOKEN='')
    @mock.patch('apps.sms_app.tg_gateway._api')
    def test_token_yoq_bolsa_urinmaydi(self, api):
        self.assertFalse(tg_gateway.kod_yubor(TEL, '123456'))
        api.assert_not_called()
        self.assertFalse(sozlanganmi())

    def test_faqat_gateway_bilan_sozlangan_hisoblanadi(self):
        self.assertTrue(sozlanganmi())     # E001 tekshiruvi o'tadi

    def test_token_tekshiruvi_pulsiz(self):
        with mock.patch('apps.sms_app.tg_gateway._api', side_effect=tg_gateway.GatewayXato('x: ACCESS_TOKEN_INVALID')):
            self.assertFalse(tg_gateway.token_yaroqlimi()[0])
        with mock.patch('apps.sms_app.tg_gateway._api', side_effect=tg_gateway.GatewayXato('x: REQUEST_ID_INVALID')):
            self.assertTrue(tg_gateway.token_yaroqlimi()[0])


@override_settings(**GW)
class KirishKodiGatewayTest(TestCase):
    def setUp(self):
        cache.clear()
        self.c = APIClient()

    @mock.patch('apps.sms_app.tg_gateway._api', return_value={'request_id': 'r1'})
    def test_ulanmagan_mijozga_botsiz_kod_keladi(self, api):
        """Asosiy holat: bot ochilmagan, faqat raqam yozilgan — kod Gateway orqali ketadi."""
        r = self.c.post('/api/auth/otp/yuborish/', {'telefon': TEL}, format='json')
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.json()['yuborildi'])
        kod = OtpKod.objects.get(telefon=TEL).kod
        # Gateway'ga AYNAN bazadagi kod yuborilgan: tasdiqlash o'zgarmagan
        self.assertEqual(api.call_args[0][1]['code'], kod)
        r2 = self.c.post('/api/auth/otp/tasdiqlash/', {'telefon': TEL, 'kod': kod}, format='json')
        self.assertEqual(r2.status_code, 200)
        self.assertIn('access', r2.json())

    @mock.patch('apps.sms_app.tg_gateway._api', side_effect=tg_gateway.GatewayXato('PHONE_NUMBER_NOT_FOUND'))
    def test_gateway_ishlamasa_bot_zaxira(self, api):
        TelegramUlanish.objects.create(telefon=TEL, chat_id=555)
        with override_settings(TELEGRAM_BOT_TOKEN='1:BOT'), \
                mock.patch('apps.sms_app.telegram._api') as bot:
            r = self.c.post('/api/auth/otp/yuborish/', {'telefon': TEL}, format='json')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(bot.call_args[0][1]['chat_id'], 555)

    @mock.patch('apps.sms_app.tg_gateway._api', side_effect=tg_gateway.GatewayXato('BALANCE_NOT_ENOUGH'))
    def test_hech_biri_ishlamasa_xato_qaytadi(self, api):
        r = self.c.post('/api/auth/otp/yuborish/', {'telefon': TEL}, format='json')
        self.assertEqual(r.status_code, 502)

    @mock.patch('apps.sms_app.tg_gateway._api', return_value={'request_id': 'r1'})
    def test_gateway_otpdan_boshqa_xabarga_ishlatilmaydi(self, api):
        """Gateway faqat kod uchun: oddiy xabar (sms_yubor) unga yuborilmaydi."""
        from .gateway import sms_yubor
        self.assertFalse(sms_yubor(TEL, 'Buyurtmangiz qabul qilindi'))
        api.assert_not_called()


@override_settings(**GW)
class SinovBuyrugiTest(TestCase):
    @mock.patch('apps.sms_app.tg_gateway._api', return_value={'request_id': 'r9', 'request_cost': 0, 'remaining_balance': 1.5})
    def test_sinov_kodi_yuboriladi(self, api):
        out = io.StringIO()
        call_command('telegram_gateway_sinov', TEL, '--kod', '654321', stdout=out)
        self.assertEqual(api.call_args[0][1]['code'], '654321')
        self.assertIn('r9', out.getvalue())

    @override_settings(TELEGRAM_GATEWAY_TOKEN='')
    def test_tokensiz_xato(self):
        with self.assertRaises(CommandError):
            call_command('telegram_gateway_sinov', TEL)
