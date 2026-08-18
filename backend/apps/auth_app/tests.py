"""OTP orqali kirish oqimi testlari.

Bu — tizimga kirishning yagona yo'li, shuning uchun ikki tomoni ham
sinaladi: mijoz normal holatda kira olsin, va kodni taxmin qilib bo'lmasin
(urinishlar soni, qayta yuborish oralig'i, soatlik chegara, muddat).

SMS chinakam yuborilmaydi — `sms_yubor` mock qilinadi. Yuborilgan kodni
bazadagi `OtpKod` dan olamiz.
"""

from unittest import mock

from django.core.cache import cache
from django.test import TestCase, override_settings
from django.utils import timezone

from .models import Foydalanuvchi, OtpKod

YUBORISH = '/api/auth/otp/yuborish/'
TASDIQLASH = '/api/auth/otp/tasdiqlash/'
TELEFON = '998901234567'

CHEKLOVLAR = dict(
    OTP_EXPIRE_MINUTES=5,
    OTP_QAYTA_SONIYA=60,
    OTP_SOATLIK_LIMIT=5,
    OTP_URINISH_LIMIT=5,
    OTP_BLOK_DAQIQA=15,
)


@override_settings(**CHEKLOVLAR)
class OtpTestAsosi(TestCase):
    def setUp(self):
        # Cheklovlar keshda saqlanadi — har bir test toza holatdan boshlansin
        cache.clear()
        yamoq = mock.patch('apps.auth_app.views.sms_yubor', return_value=True)
        self.sms = yamoq.start()
        self.addCleanup(yamoq.stop)
        self.addCleanup(cache.clear)

    def kod_sora(self, telefon=TELEFON):
        return self.client.post(YUBORISH, {'telefon': telefon}, content_type='application/json')

    def oxirgi_kod(self, telefon=TELEFON):
        return OtpKod.objects.filter(telefon=telefon).order_by('-yaratilgan').first()

    def tasdiqla(self, kod, telefon=TELEFON):
        return self.client.post(TASDIQLASH, {'telefon': telefon, 'kod': kod},
                                content_type='application/json')


class KodYuborishTest(OtpTestAsosi):
    def test_yangi_raqamga_kod_yuboriladi(self):
        javob = self.kod_sora()
        self.assertEqual(javob.status_code, 200)
        self.assertTrue(javob.json()['yuborildi'])
        self.assertTrue(javob.json()['yangi_mijoz'])
        self.assertEqual(len(self.oxirgi_kod().kod), 6)
        self.sms.assert_called_once()

    def test_telefonsiz_sorov_rad_etiladi(self):
        javob = self.client.post(YUBORISH, {}, content_type='application/json')
        self.assertEqual(javob.status_code, 400)
        self.assertFalse(OtpKod.objects.exists())

    def test_mavjud_mijoz_yangi_deb_belgilanmaydi(self):
        Foydalanuvchi.objects.create(telefon=TELEFON, rol='mijoz')
        self.assertFalse(self.kod_sora().json()['yangi_mijoz'])

    def test_bloklangan_hisobga_kod_yuborilmaydi(self):
        Foydalanuvchi.objects.create(telefon=TELEFON, rol='mijoz', holat='nofaol')
        javob = self.kod_sora()
        self.assertEqual(javob.status_code, 403)
        self.sms.assert_not_called()

    def test_sms_yuborilmasa_502(self):
        """Regressiya: SMS ketmasa mijozga 'yuborildi' deyilmasligi kerak."""
        self.sms.return_value = False
        javob = self.kod_sora()
        self.assertEqual(javob.status_code, 502)
        self.assertNotIn('yuborildi', javob.json())

    def test_sms_yuborilmasa_cheklov_hisoblanmaydi(self):
        """Muvaffaqiyatsiz urinish mijozni 60 soniya kutishga majburlamasin."""
        self.sms.return_value = False
        self.kod_sora()
        self.sms.return_value = True
        self.assertEqual(self.kod_sora().status_code, 200)


class KodSorashCheklovlariTest(OtpTestAsosi):
    def test_qayta_yuborish_oraligi(self):
        self.assertEqual(self.kod_sora().status_code, 200)
        javob = self.kod_sora()
        self.assertEqual(javob.status_code, 429)
        self.assertIn('60', javob.json()['detail'])

    def test_soatlik_chegara(self):
        for _ in range(5):
            self.assertEqual(self.kod_sora().status_code, 200)
            cache.delete(f'otp:oxirgi:{TELEFON}')   # 60 soniyalik kutishni chetlab o'tamiz
        self.assertEqual(self.kod_sora().status_code, 429)

    def test_soatlik_chegaradan_keyin_blok_qoyiladi(self):
        for _ in range(6):
            self.kod_sora()
            cache.delete(f'otp:oxirgi:{TELEFON}')
        self.assertTrue(cache.get(f'otp:blok:{TELEFON}'))

    def test_cheklov_raqamlar_boyicha_alohida(self):
        self.kod_sora()
        self.assertEqual(self.kod_sora('998901112233').status_code, 200)


class KodTasdiqlashTest(OtpTestAsosi):
    def test_togri_kod_bilan_kirish(self):
        self.kod_sora()
        javob = self.tasdiqla(self.oxirgi_kod().kod)
        self.assertEqual(javob.status_code, 200)
        self.assertIn('access', javob.json())
        self.assertEqual(javob.json()['user']['telefon'], TELEFON)
        # Mijoz avtomatik yaratiladi
        self.assertTrue(Foydalanuvchi.objects.filter(telefon=TELEFON, rol='mijoz').exists())

    def test_kod_bir_martalik(self):
        self.kod_sora()
        kod = self.oxirgi_kod().kod
        self.assertEqual(self.tasdiqla(kod).status_code, 200)
        self.assertEqual(self.tasdiqla(kod).status_code, 400)

    def test_notogri_kod(self):
        self.kod_sora()
        javob = self.tasdiqla('000000')
        self.assertEqual(javob.status_code, 400)

    def test_bosh_sorov(self):
        self.assertEqual(self.tasdiqla('').status_code, 400)

    def test_muddati_otgan_kod(self):
        self.kod_sora()
        otp = self.oxirgi_kod()
        OtpKod.objects.filter(pk=otp.pk).update(
            yaratilgan=timezone.now() - timezone.timedelta(minutes=6))
        javob = self.tasdiqla(otp.kod)
        self.assertEqual(javob.status_code, 400)
        self.assertIn('muddati', javob.json()['detail'])

    def test_boshqa_raqamning_kodi_ishlamaydi(self):
        self.kod_sora()
        kod = self.oxirgi_kod().kod
        self.assertEqual(self.tasdiqla(kod, telefon='998907776655').status_code, 400)

    def test_urinishlar_limitidan_song_bloklanadi(self):
        self.kod_sora()
        for _ in range(4):
            self.assertEqual(self.tasdiqla('000000').status_code, 400)
        # Beshinchi xato urinish — blok
        self.assertEqual(self.tasdiqla('000000').status_code, 429)
        self.assertTrue(cache.get(f'otp:blok:{TELEFON}'))

    def test_blokdan_keyin_togri_kod_ham_otmaydi(self):
        self.kod_sora()
        togri = self.oxirgi_kod().kod
        for _ in range(5):
            self.tasdiqla('000000')
        self.assertEqual(self.tasdiqla(togri).status_code, 429)

    def test_togri_kod_urinishlar_sanogini_tozalaydi(self):
        self.kod_sora()
        self.tasdiqla('000000')
        self.tasdiqla(self.oxirgi_kod().kod)
        self.assertIsNone(cache.get(f'otp:urinish:{TELEFON}'))
