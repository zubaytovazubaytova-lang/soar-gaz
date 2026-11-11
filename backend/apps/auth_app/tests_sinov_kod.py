"""Sinov (test) kodi: faqat DEBUG=1 da va faqat ro'yxatdagi raqamga ishlaydi.

Serverda (DEBUG=0) u HECH QACHON ishlamasligi — eng muhim xavfsizlik sharti."""
from django.test import override_settings

from .models import OtpKod
from .tests import OtpTestAsosi

SINOV_TEL = '+998900000002'
SINOV = {SINOV_TEL: '123456'}


class SinovKodiTest(OtpTestAsosi):
    @override_settings(DEBUG=True, SINOV_MIJOZ=SINOV)
    def test_sinov_raqamiga_kod_doim_bir_xil_va_sms_yuborilmaydi(self):
        r = self.kod_sora(SINOV_TEL)
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(self.oxirgi_kod(SINOV_TEL).kod, '123456')
        self.sms.assert_not_called()

    @override_settings(DEBUG=True, SINOV_MIJOZ=SINOV)
    def test_sinov_kodi_bilan_kirish_ishlaydi(self):
        self.kod_sora(SINOV_TEL)
        r = self.tasdiqla('123456', SINOV_TEL)
        self.assertEqual(r.status_code, 200, r.content)
        self.assertIn('access', r.json())

    @override_settings(DEBUG=True, SINOV_MIJOZ=SINOV)
    def test_boshqa_raqamga_oddiy_tasodifiy_kod_va_sms(self):
        r = self.kod_sora('+998911111111')
        self.assertEqual(r.status_code, 200)
        self.sms.assert_called_once()
        self.assertEqual(len(self.oxirgi_kod('+998911111111').kod), 6)

    @override_settings(DEBUG=True, SINOV_MIJOZ=SINOV)
    def test_sinov_kodi_boshqa_raqamda_ishlamaydi(self):
        self.kod_sora(SINOV_TEL)
        self.kod_sora('+998911111111')
        r = self.tasdiqla('123456', '+998911111111')
        # tasodifiy kod 123456 bo'lib qolish ehtimoli 1/10^6 — shuning uchun faqat sinov raqamining kodi tekshiriladi
        self.assertEqual(OtpKod.objects.filter(telefon='+998911111111', kod='123456').exists(), r.status_code == 200)

    @override_settings(DEBUG=False, SINOV_MIJOZ=SINOV)
    def test_serverda_debug_o_chiq_bolsa_sinov_kodi_ishlamaydi(self):
        # Ro'yxat nechog'li berilgan bo'lmasin, DEBUG=0 da oddiy tasodifiy kod va haqiqiy SMS yo'li ishlaydi
        r = self.kod_sora(SINOV_TEL)
        self.assertEqual(r.status_code, 200)
        self.sms.assert_called_once()
        kod = self.oxirgi_kod(SINOV_TEL).kod
        self.assertEqual(len(kod), 6)
        # (1/10^6 ehtimol bilan kod 123456 chiqsa ham test mantiqi to'g'ri: asosiy tekshiruv — SMS chaqirilgani)

    @override_settings(DEBUG=True, SINOV_MIJOZ={})
    def test_royxat_bosh_bolsa_hech_narsa_ozgarmaydi(self):
        self.kod_sora(SINOV_TEL)
        self.sms.assert_called_once()
