"""Telegram bot orqali bildirishnomalar: xodimlarga yangi ariza, mijozlarga holat va eslatma."""
from datetime import timedelta
from io import StringIO
from unittest import mock

from django.core.cache import cache
from django.core.management import call_command
from django.test import Client, TestCase, override_settings
from django.utils import timezone

from apps.auth_app.models import Foydalanuvchi
from apps.kabinet.models import Hisoblagich, Obyekt
from .gateway import sms_yubor
from .models import TelegramUlanish
from . import xodim_xabar

TG = dict(TELEGRAM_BOT_TOKEN='123:TEST')


def _chat_idlar(api):
    return sorted(c.args[1]['chat_id'] for c in api.call_args_list if c.args[0] == 'sendMessage')


@override_settings(**TG)
class XodimlargaXabarTest(TestCase):
    def setUp(self):
        cache.clear()
        royxat = [
            ('+998900000001', 'admin', '', 1),
            ('+998900000002', 'xodim', 'Call center operatori', 2),          # Nargiza
            ('+998900000003', 'xodim', 'Kadrlar bo\'yicha mutaxassis', 3),   # Ruxsora
            ('+998900000004', 'xodim', 'Mehnat muhofazasi muhandisi', 4),    # Ferangiz
            ('+998900000005', 'xodim', 'Montaj ustasi', 5),                  # oddiy usta
        ]
        for tel, rol, lavozim, chat in royxat:
            Foydalanuvchi.objects.create(telefon=tel, rol=rol, lavozim=lavozim)
            TelegramUlanish.objects.create(telefon=tel, chat_id=chat)
        # Botga ulanmagan operator: unga xabar bormaydi
        Foydalanuvchi.objects.create(telefon='+998900000006', rol='xodim', lavozim='Call center operatori')

    def test_oddiy_buyurtma_operatorlar_va_adminga(self):
        self.assertEqual(sorted(xodim_xabar.qabul_qiluvchilar('servis')),
                         ['+998900000001', '+998900000002', '+998900000003'])

    def test_metrologiya_hujjatchiga_ham(self):
        self.assertIn('+998900000004', xodim_xabar.qabul_qiluvchilar('metrologiya'))
        self.assertNotIn('+998900000005', xodim_xabar.qabul_qiluvchilar('metrologiya'))

    def test_nofaol_xodimga_bormaydi(self):
        Foydalanuvchi.objects.filter(telefon='+998900000002').update(holat='nofaol')
        self.assertNotIn('+998900000002', xodim_xabar.qabul_qiluvchilar('servis'))

    @mock.patch('apps.sms_app.telegram._api')
    def test_saytdan_metrologiya_arizasi_xabari(self, api):
        with self.captureOnCommitCallbacks(execute=True):
            r = Client().post('/api/tolovlar/metrologiya-ariza/',
                              {'ism': 'Ali', 'telefon': '+998901112233', 'manzil': 'Buxoro', 'hisoblagich': 'G4', 'seriya_raqam': 'SR-9'},
                              content_type='application/json')
        self.assertEqual(r.status_code, 201, r.content)
        self.assertEqual(_chat_idlar(api), [1, 2, 3, 4])
        matn = next(c.args[1]['text'] for c in api.call_args_list if c.args[1]['chat_id'] == 4)
        self.assertIn('metrologiya arizasi', matn)
        self.assertIn('Ali', matn)

    @mock.patch('apps.sms_app.telegram._api', side_effect=Exception('tarmoq'))
    def test_telegram_xatosi_arizani_buzmaydi(self, api):
        with self.captureOnCommitCallbacks(execute=True):
            r = Client().post('/api/tolovlar/metrologiya-ariza/',
                              {'ism': 'Ali', 'telefon': '+998901112233', 'hisoblagich': 'G4', 'seriya_raqam': 'SR-9'}, content_type='application/json')
        self.assertEqual(r.status_code, 201)

    @override_settings(TELEGRAM_BOT_TOKEN='')
    @mock.patch('apps.sms_app.telegram._api')
    def test_bot_sozlanmagan_bolsa_urinmaydi(self, api):
        with self.captureOnCommitCallbacks(execute=True):
            xodim_xabar.yangi_ariza('servis', 'Yangi buyurtma #1')
        api.assert_not_called()


@override_settings(**TG)
class MijozgaTelegramTest(TestCase):
    def setUp(self):
        cache.clear()
        self.mijoz = Foydalanuvchi.objects.create(telefon='+998901234567', rol='mijoz', ism='Vali')
        TelegramUlanish.objects.create(telefon='+998901234567', chat_id=555)

    @mock.patch('apps.sms_app.telegram._api')
    def test_ulangan_mijozga_holat_xabari_telegramdan(self, api):
        self.assertTrue(sms_yubor('+998901234567', 'Buyurtmangiz bajarildi'))
        api.assert_called_once_with('sendMessage', {'chat_id': 555, 'text': 'Buyurtmangiz bajarildi'})

    @mock.patch('apps.sms_app.telegram._api')
    def test_faqat_sms_rejimi(self, api):
        sms_yubor('+998901234567', 'matn', telegram_bot=False)
        api.assert_not_called()

    @mock.patch('apps.sms_app.telegram._api')
    def test_hisoblagich_eslatmasi_telegramga(self, api):
        ob = Obyekt.objects.create(mijoz=self.mijoz, nom='Uy', manzil='Buxoro')
        Hisoblagich.objects.create(obyekt=ob, seriya_raqam='SR-1',
                                   keyingi_tekshiruv=timezone.localdate() + timedelta(days=10))
        chiqish = StringIO()
        call_command('tekshiruv_eslatma', stdout=chiqish)
        self.assertEqual(_chat_idlar(api), [555])
        self.assertIn('SR-1', api.call_args.args[1]['text'])
        self.assertIn('1 tasi Telegram orqali', chiqish.getvalue())
        # Ikkinchi marta ishga tushsa takror yubormaydi (ochiq eslatma bor)
        api.reset_mock()
        call_command('tekshiruv_eslatma', stdout=StringIO())
        api.assert_not_called()
