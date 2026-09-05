"""Boshqaruv paneliga kirish testlari — parol + SMS (2FA).

Bu tizimdagi eng yuqori huquqli kirish nuqtasi, shuning uchun sinaladigan
narsa faqat "to'g'ri parol bilan kiradi" emas, balki himoya ham:

* parol bosqichi HECH QACHON token bermaydi (2FA yoqilganda);
* chiptasiz OTP bosqichiga o'tib bo'lmaydi;
* noto'g'ri parol ADMIN_URINISH_LIMIT dan keyin hisobni bloklaydi va u
  o'zi ochilmaydi;
* bloklangan hisob to'g'ri parol bilan ham kirmaydi.

SMS chinakam yuborilmaydi — `sms_yubor` mock qilinadi, kod esa bazadagi
`OtpKod` dan olinadi.
"""

from unittest import mock

from django.core.cache import cache
from django.test import TestCase, override_settings

from .models import Foydalanuvchi, OtpKod

LOGIN = '/api/auth/admin/login/'
OTP = '/api/auth/admin/otp/'
TELEFON = '998911111111'
PAROL = 'juda-maxfiy-parol-1'

CHEKLOVLAR = dict(
    ADMIN_2FA=True,
    ADMIN_2FA_DAQIQA=5,
    ADMIN_2FA_URINISH=3,
    ADMIN_URINISH_LIMIT=4,
    ADMIN_SESSIYA_DAQIQA=30,
    DEBUG=False,          # dev_kod javobda chiqmasligi kerak
)


@override_settings(**CHEKLOVLAR)
class AdminKirishAsosi(TestCase):
    def setUp(self):
        cache.clear()
        self.addCleanup(cache.clear)
        yamoq = mock.patch('apps.auth_app.views.sms_yubor', return_value=True)
        self.sms = yamoq.start()
        self.addCleanup(yamoq.stop)
        self.admin = Foydalanuvchi.objects.create_user(
            telefon=TELEFON, password=PAROL, rol='admin', ism='Direktor')

    def parol_yubor(self, parol=PAROL, telefon=TELEFON):
        return self.client.post(LOGIN, {'telefon': telefon, 'parol': parol},
                                content_type='application/json')

    def kod_yubor(self, chipta, kod):
        return self.client.post(OTP, {'chipta': chipta, 'kod': kod},
                                content_type='application/json')

    def oxirgi_kod(self):
        return OtpKod.objects.filter(telefon=TELEFON).order_by('-yaratilgan').first()


class ParolBosqichiTest(AdminKirishAsosi):
    def test_togri_parol_token_bermaydi_balki_chipta_beradi(self):
        javob = self.parol_yubor()
        self.assertEqual(javob.status_code, 200)
        malumot = javob.json()
        self.assertTrue(malumot['otp_kerak'])
        self.assertTrue(malumot['chipta'])
        self.assertNotIn('access', malumot)
        self.assertNotIn('refresh', malumot)
        self.sms.assert_called_once()

    def test_dev_kod_serverda_chiqmaydi(self):
        # DEBUG=False — kod javobda hech qachon ko'rinmasligi kerak
        self.assertNotIn('dev_kod', self.parol_yubor().json())

    def test_telefon_maskasi_raqamni_ochib_bermaydi(self):
        maska = self.parol_yubor().json()['telefon_maskasi']
        self.assertNotIn(TELEFON, maska)
        self.assertTrue(maska.endswith('11 11'))

    def test_notogri_parolda_urinish_qoldi_deyiladi(self):
        javob = self.parol_yubor(parol='xato')
        self.assertEqual(javob.status_code, 401)
        self.assertIn('3', javob.json()['detail'])   # 4 - 1 = 3 ta qoldi
        self.assertEqual(OtpKod.objects.count(), 0)

    def test_mijoz_boshqaruv_paneliga_kira_olmaydi(self):
        Foydalanuvchi.objects.create_user(telefon='998900000000', password=PAROL,
                                          rol='mijoz')
        javob = self.client.post(LOGIN, {'telefon': '998900000000', 'parol': PAROL},
                                 content_type='application/json')
        self.assertEqual(javob.status_code, 401)


class BlokTest(AdminKirishAsosi):
    def test_limitdan_keyin_hisob_bloklanadi_va_ozi_ochilmaydi(self):
        for _ in range(3):
            self.assertEqual(self.parol_yubor(parol='xato').status_code, 401)
        self.assertEqual(self.parol_yubor(parol='xato').status_code, 403)

        self.admin.refresh_from_db()
        self.assertEqual(self.admin.holat, 'nofaol')

        # Endi TO'G'RI parol ham o'tmaydi — faqat egasi qo'lda ochadi
        javob = self.parol_yubor()
        self.assertEqual(javob.status_code, 403)
        self.assertEqual(OtpKod.objects.count(), 0)

    def test_mavjud_bolmagan_raqam_ham_bir_xil_javob_beradi(self):
        # Qaysi raqam admin ekani javobdan bilinmasligi kerak
        javob = self.client.post(LOGIN, {'telefon': '998999999999', 'parol': 'xato'},
                                 content_type='application/json')
        self.assertEqual(javob.status_code, 401)


class OtpBosqichiTest(AdminKirishAsosi):
    def chipta_ol(self):
        return self.parol_yubor().json()['chipta']

    def test_togri_kod_token_beradi(self):
        chipta = self.chipta_ol()
        javob = self.kod_yubor(chipta, self.oxirgi_kod().kod)
        self.assertEqual(javob.status_code, 200)
        malumot = javob.json()
        self.assertTrue(malumot['access'])
        self.assertEqual(malumot['user']['telefon'], TELEFON)
        self.assertEqual(malumot['sessiya_daqiqa'], 30)

    def test_kod_bir_martalik(self):
        chipta = self.chipta_ol()
        kod = self.oxirgi_kod().kod
        self.assertEqual(self.kod_yubor(chipta, kod).status_code, 200)
        # Chipta ham, kod ham ishlatilgan — takroriy urinish o'tmaydi
        self.assertEqual(self.kod_yubor(chipta, kod).status_code, 401)

    def test_notogri_chipta_bilan_kirib_bolmaydi(self):
        self.chipta_ol()
        javob = self.kod_yubor('soxta-chipta', self.oxirgi_kod().kod)
        self.assertEqual(javob.status_code, 401)
        self.assertTrue(javob.json()['qaytadan'])

    def test_kod_bir_necha_marta_xato_bolsa_chipta_bekor_qilinadi(self):
        chipta = self.chipta_ol()
        for _ in range(2):
            self.assertEqual(self.kod_yubor(chipta, '000000').status_code, 401)
        javob = self.kod_yubor(chipta, '000000')
        self.assertEqual(javob.status_code, 401)
        self.assertTrue(javob.json()['qaytadan'])
        # Chipta o'lgan — endi to'g'ri kod ham yordam bermaydi
        self.assertEqual(self.kod_yubor(chipta, self.oxirgi_kod().kod).status_code, 401)

    def test_parol_bosqichidan_keyin_bloklangan_hisob_token_olmaydi(self):
        chipta = self.chipta_ol()
        Foydalanuvchi.objects.filter(pk=self.admin.pk).update(holat='nofaol')
        javob = self.kod_yubor(chipta, self.oxirgi_kod().kod)
        self.assertEqual(javob.status_code, 403)


@override_settings(**{**CHEKLOVLAR, 'ADMIN_2FA': False})
class IkkiBosqichOchirilganTest(AdminKirishAsosi):
    def test_2fa_ochirilganda_parolning_ozi_yetadi(self):
        javob = self.parol_yubor()
        self.assertEqual(javob.status_code, 200)
        self.assertTrue(javob.json()['access'])
        self.sms.assert_not_called()
