"""SMS shlyuzi va ishga tushirish tekshiruvi testlari.

Asosiy maqsad — regressiya: `sms_yubor()` ilgari konsol rejimida HAR DOIM
`True` qaytarardi, shu sababli produksiyada OTP kod hech kimga yetib
bormasa ham tizim "yuborildi" deb javob berardi. Shu xatti-harakat qaytib
kelmasligi uchun quyidagi testlar bor.
"""

import sys
from unittest import mock

from django.test import SimpleTestCase, override_settings

from .checks import sms_sozlangan_mi
from .gateway import sms_yubor, sozlanganmi

# Haqiqiy provayder to'liq sozlangan holat
ESKIZ = dict(
    SMS_PROVAYDER='eskiz',
    ESKIZ_EMAIL='test@soargaz.uz',
    ESKIZ_PAROL='maxfiy',
    ESKIZ_FROM='4546',
)


class SozlanganmiTest(SimpleTestCase):
    @override_settings(SMS_PROVAYDER='konsol')
    def test_konsol_sozlanmagan_hisoblanadi(self):
        self.assertFalse(sozlanganmi())

    @override_settings(**ESKIZ)
    def test_eskiz_kalitlar_bilan_sozlangan(self):
        self.assertTrue(sozlanganmi())

    @override_settings(SMS_PROVAYDER='eskiz', ESKIZ_EMAIL='', ESKIZ_PAROL='')
    def test_kalitsiz_eskiz_sozlanmagan(self):
        """Provayder nomi berilgan, lekin kalitlar yo'q — bu sozlangan emas."""
        self.assertFalse(sozlanganmi())


class SmsYuborTest(SimpleTestCase):
    @override_settings(SMS_PROVAYDER='konsol', DEBUG=True)
    def test_dev_rejimda_true_qaytaradi(self):
        """Dev rejimda kod log'ga chiqadi va bu yetarli deb hisoblanadi."""
        with self.assertLogs('apps.sms_app.gateway', level='WARNING') as jurnal:
            self.assertTrue(sms_yubor('998901234567', 'kod: 123456'))
        self.assertIn('123456', '\n'.join(jurnal.output))

    @override_settings(SMS_PROVAYDER='konsol', DEBUG=False)
    def test_produksiyada_sozlanmagan_provayder_false_qaytaradi(self):
        """Regressiya: ilgari bu yerda ham True qaytardi va xato ko'rinmasdi."""
        with self.assertLogs('apps.sms_app.gateway', level='ERROR'):
            self.assertFalse(sms_yubor('998901234567', 'kod: 123456'))

    @override_settings(DEBUG=False, **ESKIZ)
    def test_provayder_xatosi_false_qaytaradi(self):
        from .gateway import SmsXato

        with mock.patch('apps.sms_app.gateway._eskiz_yubor', side_effect=SmsXato('aloqa yo\'q')):
            with self.assertLogs('apps.sms_app.gateway', level='ERROR'):
                self.assertFalse(sms_yubor('998901234567', 'salom'))

    @override_settings(DEBUG=False, **ESKIZ)
    def test_muvaffaqiyatli_yuborish(self):
        with mock.patch('apps.sms_app.gateway._eskiz_yubor', return_value={'status': 'waiting'}) as yubor:
            self.assertTrue(sms_yubor('998901234567', 'salom'))
        yubor.assert_called_once_with('998901234567', 'salom')


class TekshiruvTest(SimpleTestCase):
    """`sms_app.E001` — noto'g'ri sozlangan server ishga tushmasligi kerak."""

    def setUp(self):
        # Tekshiruv test rejimini `sys.argv` orqali aniqlaydi; bu yerda
        # aynan produksiya xatti-harakatini sinaymiz, shuning uchun argv ni
        # vaqtincha "toza" qilamiz.
        self.argv = sys.argv
        sys.argv = ['gunicorn']

    def tearDown(self):
        sys.argv = self.argv

    @override_settings(DEBUG=False, SMS_PROVAYDER='konsol')
    def test_sozlanmagan_produksiyada_xato(self):
        xatolar = sms_sozlangan_mi(None)
        self.assertEqual([x.id for x in xatolar], ['sms_app.E001'])

    @override_settings(DEBUG=True, SMS_PROVAYDER='konsol')
    def test_dev_rejimda_xato_yoq(self):
        self.assertEqual(sms_sozlangan_mi(None), [])

    @override_settings(DEBUG=False, **ESKIZ)
    def test_sozlangan_provayderda_xato_yoq(self):
        self.assertEqual(sms_sozlangan_mi(None), [])

    @override_settings(DEBUG=False, SMS_PROVAYDER='konsol')
    def test_test_rejimida_xato_yoq(self):
        """Regressiya: tekshiruv `manage.py test` ni to'sib qo'ygan edi."""
        sys.argv = ['manage.py', 'test']
        self.assertEqual(sms_sozlangan_mi(None), [])
