"""Telegram bot orqali kod yuborish: ulash, yuborish, webhook himoyasi, kirish kodi oqimi."""
from unittest import mock

from django.core.cache import cache
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from apps.auth_app.models import Foydalanuvchi, OtpKod
from . import telegram
from .gateway import sms_yubor, sozlanganmi
from .models import TelegramUlanish

TG = dict(TELEGRAM_BOT_TOKEN='123:TEST', TELEGRAM_WEBHOOK_SECRET='sir-sir-sir',
          TELEGRAM_BOT_USERNAME='soargaz_test_bot', DEBUG=False, SMS_PROVAYDER='konsol')
TEL = '+998901234567'


def kontakt_xabari(chat_id=555, kimdan=555, kontakt_user=555, telefon='998901234567', turi='private'):
    return {'message': {
        'from': {'id': kimdan, 'username': 'mijoz'},
        'chat': {'id': chat_id, 'type': turi},
        'contact': {'phone_number': telefon, 'user_id': kontakt_user, 'first_name': 'Ali'},
    }}


def matn_xabari(matn, chat_id=555, turi='private'):
    return {'message': {'from': {'id': chat_id}, 'chat': {'id': chat_id, 'type': turi}, 'text': matn}}


@override_settings(**TG)
class UlashTest(TestCase):
    def setUp(self):
        cache.clear()
        p = mock.patch('apps.sms_app.telegram._api')
        self.api = p.start()
        self.addCleanup(p.stop)

    def test_oz_kontakti_ulanadi_va_raqam_normallashadi(self):
        telegram.yangilanishni_qayta_ishla(kontakt_xabari(telefon='998 90 123-45-67'))
        u = TelegramUlanish.objects.get()
        self.assertEqual((u.telefon, u.chat_id), (TEL, 555))
        self.assertTrue(telegram.ulangan('998901234567'))      # + siz ham topiladi
        self.assertTrue(telegram.ulangan(TEL))
        # foydalanuvchiga tasdiq va tugma yashirilishi yuboriladi
        usul, malumot = self.api.call_args[0]
        self.assertEqual(usul, 'sendMessage')
        self.assertIn('ulandi', malumot['text'])
        self.assertEqual(malumot['reply_markup'], {'remove_keyboard': True})

    def test_begona_kontakt_ulanmaydi(self):
        """Boshqa odamning kontaktini yuborib, begona raqamni ulab bo'lmaydi."""
        telegram.yangilanishni_qayta_ishla(kontakt_xabari(kimdan=555, kontakt_user=999))
        self.assertFalse(TelegramUlanish.objects.exists())
        self.assertIn('o\'zingizning', self.api.call_args[0][1]['text'])

    def test_user_idsiz_kontakt_ulanmaydi(self):
        x = kontakt_xabari()
        del x['message']['contact']['user_id']
        telegram.yangilanishni_qayta_ishla(x)
        self.assertFalse(TelegramUlanish.objects.exists())

    def test_guruhdagi_xabar_e_tiborga_olinmaydi(self):
        telegram.yangilanishni_qayta_ishla(kontakt_xabari(turi='group'))
        self.assertFalse(TelegramUlanish.objects.exists())
        self.api.assert_not_called()

    def test_start_raqam_tugmasini_korsatadi(self):
        telegram.yangilanishni_qayta_ishla(matn_xabari('/start'))
        malumot = self.api.call_args[0][1]
        self.assertTrue(malumot['reply_markup']['keyboard'][0][0]['request_contact'])

    def test_qayta_ulash_chat_almashtiradi_va_dublikat_yaratmaydi(self):
        telegram.yangilanishni_qayta_ishla(kontakt_xabari(chat_id=555, kimdan=555, kontakt_user=555))
        telegram.yangilanishni_qayta_ishla(kontakt_xabari(chat_id=777, kimdan=777, kontakt_user=777))
        u = TelegramUlanish.objects.get(telefon=TEL)
        self.assertEqual(u.chat_id, 777)
        self.assertEqual(TelegramUlanish.objects.count(), 1)

    def test_telegram_hisobi_raqam_almashtirsa_eskisi_ochadi(self):
        telegram.yangilanishni_qayta_ishla(kontakt_xabari(telefon='998901234567'))
        telegram.yangilanishni_qayta_ishla(kontakt_xabari(telefon='998909999999'))
        self.assertEqual(list(TelegramUlanish.objects.values_list('telefon', flat=True)), ['+998909999999'])

    def test_stop_uzadi(self):
        telegram.yangilanishni_qayta_ishla(kontakt_xabari())
        telegram.yangilanishni_qayta_ishla(matn_xabari('/stop'))
        self.assertFalse(TelegramUlanish.objects.exists())


@override_settings(**TG)
class YuborishTest(TestCase):
    def setUp(self):
        cache.clear()
        TelegramUlanish.objects.create(telefon=TEL, chat_id=555)

    @mock.patch('apps.sms_app.telegram._api')
    def test_ulangan_raqamga_telegramdan_ketadi(self, api):
        self.assertTrue(sms_yubor('998901234567', 'kod: 123456', telegram_bot=True))
        api.assert_called_once_with('sendMessage', {'chat_id': 555, 'text': 'kod: 123456'})

    @mock.patch('apps.sms_app.telegram._api')
    def test_oddiy_xabar_ulangan_raqamga_telegramdan(self, api):
        """Ariza/buyurtma xabarlari botga ulangan raqamga Telegram'dan (tekin) boradi."""
        self.assertTrue(sms_yubor('998901234567', 'Arizangiz qabul qilindi'))
        api.assert_called_once()

    @mock.patch('apps.sms_app.telegram._api')
    def test_ulanmagan_raqamga_ketmaydi(self, api):
        self.assertFalse(sms_yubor('+998900000000', 'kod: 1', telegram_bot=True))
        api.assert_not_called()

    @mock.patch('apps.sms_app.telegram._api', side_effect=telegram.TelegramXato('bot blocked'))
    def test_telegram_xatosi_false_qaytaradi(self, api):
        self.assertFalse(sms_yubor(TEL, 'kod', telegram_bot=True))

    @override_settings(TELEGRAM_BOT_TOKEN='')
    @mock.patch('apps.sms_app.telegram._api')
    def test_token_bermasa_telegramga_urinmaydi(self, api):
        self.assertFalse(sms_yubor(TEL, 'kod', telegram_bot=True))
        api.assert_not_called()
        self.assertFalse(sozlanganmi())

    def test_sozlanganmi_telegram_bilan_true(self):
        self.assertTrue(sozlanganmi())

    @override_settings(SMS_PROVAYDER='eskiz', ESKIZ_EMAIL='a@b.uz', ESKIZ_PAROL='x')
    @mock.patch('apps.sms_app.telegram._api', side_effect=telegram.TelegramXato('x'))
    @mock.patch('apps.sms_app.gateway._eskiz_yubor')
    def test_telegram_ketmasa_eskiz_sms_zaxira_bo_ladi(self, eskiz, api):
        self.assertTrue(sms_yubor(TEL, 'kod', telegram_bot=True))
        eskiz.assert_called_once()


@override_settings(**TG)
class WebhookTest(TestCase):
    URL = '/api/sms/telegram/webhook/'

    def setUp(self):
        cache.clear()
        self.c = APIClient()
        p = mock.patch('apps.sms_app.telegram._api')
        self.api = p.start()
        self.addCleanup(p.stop)

    def test_sarlavhasiz_rad_etiladi(self):
        r = self.c.post(self.URL, kontakt_xabari(), format='json')
        self.assertEqual(r.status_code, 403)
        self.assertFalse(TelegramUlanish.objects.exists())

    def test_notogri_sir_rad_etiladi(self):
        r = self.c.post(self.URL, kontakt_xabari(), format='json',
                        HTTP_X_TELEGRAM_BOT_API_SECRET_TOKEN='boshqa')
        self.assertEqual(r.status_code, 403)

    @override_settings(TELEGRAM_WEBHOOK_SECRET='')
    def test_sir_berilmagan_bolsa_hech_kim_otmaydi(self):
        r = self.c.post(self.URL, kontakt_xabari(), format='json', HTTP_X_TELEGRAM_BOT_API_SECRET_TOKEN='')
        self.assertEqual(r.status_code, 403)

    def test_togri_sarlavha_ulaydi(self):
        r = self.c.post(self.URL, kontakt_xabari(), format='json',
                        HTTP_X_TELEGRAM_BOT_API_SECRET_TOKEN='sir-sir-sir')
        self.assertEqual(r.status_code, 200)
        self.assertTrue(TelegramUlanish.objects.filter(telefon=TEL).exists())

    def test_ichki_xato_bolsa_ham_200(self):
        with mock.patch('apps.sms_app.telegram.yangilanishni_qayta_ishla', side_effect=RuntimeError('x')):
            r = self.c.post(self.URL, {}, format='json', HTTP_X_TELEGRAM_BOT_API_SECRET_TOKEN='sir-sir-sir')
        self.assertEqual(r.status_code, 200)


@override_settings(**TG)
class KirishKodiTest(TestCase):
    """Mijoz kirish kodi (OTP) Telegram orqali."""

    def setUp(self):
        cache.clear()
        self.c = APIClient()
        p = mock.patch('apps.sms_app.telegram._api')
        self.api = p.start()
        self.addCleanup(p.stop)

    @override_settings(TELEGRAM_BOT_MIJOZLARGA=True)
    def test_ulanmagan_mijozga_yoriqnoma_qaytadi(self):
        r = self.c.post('/api/auth/otp/yuborish/', {'telefon': TEL}, format='json')
        self.assertEqual(r.status_code, 409)
        d = r.json()
        self.assertTrue(d['telegram_kerak'])
        self.assertEqual(d['bot'], 'soargaz_test_bot')
        self.assertEqual(d['havola'], 'https://t.me/soargaz_test_bot')
        self.assertIn('@soargaz_test_bot', d['detail'])
        # urinish hisobi oshmaydi: ulangandan keyin darrov qayta so'rash mumkin
        self.assertIsNone(cache.get('otp:oxirgi:' + TEL))

    def test_ulangan_mijozga_kod_telegramga_keladi_va_kirish_ishlaydi(self):
        TelegramUlanish.objects.create(telefon=TEL, chat_id=555)
        r = self.c.post('/api/auth/otp/yuborish/', {'telefon': TEL}, format='json')
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.json()['yuborildi'])
        usul, malumot = self.api.call_args[0]
        self.assertEqual((usul, malumot['chat_id']), ('sendMessage', 555))
        kod = OtpKod.objects.get(telefon=TEL).kod
        self.assertIn(kod, malumot['text'])
        # Telegram'dan kelgan kod bilan kirish
        r2 = self.c.post('/api/auth/otp/tasdiqlash/', {'telefon': TEL, 'kod': kod}, format='json')
        self.assertEqual(r2.status_code, 200)
        self.assertTrue(Foydalanuvchi.objects.filter(telefon=TEL).exists())

    def test_standart_holatda_mijozga_bot_yoriqnomasi_korsatilmaydi(self):
        """Mijozlar botdan foydalanmaydi: kod ketmasa umumiy xato (502), botni ochish yo'riqnomasi YO'Q."""
        r = self.c.post('/api/auth/otp/yuborish/', {'telefon': TEL}, format='json')
        self.assertEqual(r.status_code, 502)
        self.assertNotIn('telegram_kerak', r.json())
        self.assertNotIn('soargaz_test_bot', r.json()['detail'])

    @override_settings(TELEGRAM_BOT_TOKEN='', TELEGRAM_BOT_MIJOZLARGA=True)
    def test_telegram_ochiq_bolmasa_eski_xulq_502(self):
        r = self.c.post('/api/auth/otp/yuborish/', {'telefon': TEL}, format='json')
        self.assertEqual(r.status_code, 502)
        self.assertNotIn('telegram_kerak', r.json())

    def test_telegram_xato_bergan_ulangan_mijoz_502(self):
        """Ulangan, lekin Telegram yetkaza olmadi (bot bloklangan): yo'riqnoma emas, umumiy xato."""
        TelegramUlanish.objects.create(telefon=TEL, chat_id=555)
        self.api.side_effect = telegram.TelegramXato('blocked')
        r = self.c.post('/api/auth/otp/yuborish/', {'telefon': TEL}, format='json')
        self.assertEqual(r.status_code, 502)
