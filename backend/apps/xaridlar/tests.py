"""Xarid summasini hisoblash testlari (`apps.xaridlar.hisob`).

Bu yerdagi raqamlar buyurtmaga yoziladi va mijozdan shu summa undiriladi,
shuning uchun har bir qoida alohida sinaladi: chegirma tartibi, bepul
yetkazish chegarasi, hudud narxi va bo'lib to'lash ustamasi.
"""

from django.test import SimpleTestCase, TestCase, override_settings
from django.utils import timezone

from .hisob import bolib_hisobla, hisobla, hudud_yetkazish, muddat_matni
from .models import Promokod

NARXLAR = dict(
    ORNATISH_NARXI=250000,
    YETKAZISH_NARXI=30000,
    BEPUL_YETKAZISH_CHEGARASI=1000000,
    YETKAZISH_HUDUDLAR={
        'Buxoro shahri': {'narx': 20000, 'soat': 4},
        'Jondor tumani': {'narx': 40000, 'soat': 24},
    },
    FILIAL_TAYYOR_SOAT=3,
    BOLIB_TOLASH={3: 0, 6: 10, 12: 20},
    BOLIB_ENG_KAM_SUMMA=1000000,
)


def savat(narx, dona=1):
    return [{'price': narx, 'qty': dona}]


@override_settings(**NARXLAR)
class MuddatMatniTest(SimpleTestCase):
    def test_soat_kun_va_bosh_holat(self):
        self.assertEqual(muddat_matni(0), '')
        self.assertEqual(muddat_matni(4), '4 soat ichida')
        self.assertEqual(muddat_matni(24), '1 kun ichida')
        self.assertEqual(muddat_matni(48), '2 kun ichida')


@override_settings(**NARXLAR)
class HududTest(SimpleTestCase):
    def test_hudud_narxi_va_muddati(self):
        self.assertEqual(hudud_yetkazish('Jondor tumani'), (40000, '1 kun ichida'))

    def test_notanish_tuman_standart_narxda(self):
        """Ro'yxatda yo'q tuman — standart narx, muddat va'da qilinmaydi."""
        self.assertEqual(hudud_yetkazish('Toshkent'), (30000, ''))
        self.assertEqual(hudud_yetkazish(''), (30000, ''))


@override_settings(**NARXLAR)
class HisoblaTest(TestCase):
    def test_oddiy_buyurtma(self):
        natija, promo, xato = hisobla(savat(200000, 2), tuman='Buxoro shahri')
        self.assertEqual(xato, '')
        self.assertIsNone(promo)
        self.assertEqual(natija['mahsulotlar'], 400000)
        self.assertEqual(natija['yetkazish_narxi'], 20000)
        self.assertEqual(natija['jami'], 420000)

    def test_ornatish_qoshiladi(self):
        natija, _, _ = hisobla(savat(200000), ornatish=True, tuman='Buxoro shahri')
        self.assertEqual(natija['ornatish_narxi'], 250000)
        self.assertEqual(natija['jami'], 200000 + 20000 + 250000)

    def test_filialdan_olishda_yetkazish_bepul(self):
        natija, _, _ = hisobla(savat(200000), yetkazish='filialdan')
        self.assertEqual(natija['yetkazish_narxi'], 0)
        self.assertEqual(natija['yetkazish_muddati'], '3 soat ichida')

    def test_chegaradan_oshsa_yetkazish_bepul(self):
        natija, _, _ = hisobla(savat(1000000), tuman='Jondor tumani')
        self.assertEqual(natija['yetkazish_narxi'], 0)

    def test_bepul_chegara_chegirmadan_keyingi_summaga_qaraydi(self):
        """Muhim: promokod summani chegaradan pastga tushirsa, yetkazish pullik."""
        Promokod.objects.create(kod='CHEGIRMA', tur='summa', qiymat=100000)
        natija, _, xato = hisobla(savat(1000000), kod='CHEGIRMA', tuman='Jondor tumani')
        self.assertEqual(xato, '')
        self.assertEqual(natija['chegirma'], 100000)
        self.assertEqual(natija['yetkazish_narxi'], 40000)
        self.assertEqual(natija['jami'], 900000 + 40000)


@override_settings(**NARXLAR)
class PromokodTest(TestCase):
    def test_foizli_chegirma(self):
        Promokod.objects.create(kod='YOZ10', tur='foiz', qiymat=10)
        natija, promo, xato = hisobla(savat(500000), kod='yoz10', tuman='Buxoro shahri')
        self.assertEqual(xato, '')
        self.assertEqual(promo.kod, 'YOZ10')      # kod katta harfga keltiriladi
        self.assertEqual(natija['chegirma'], 50000)
        self.assertEqual(natija['promokod'], 'YOZ10')

    def test_foizli_chegirmaning_yuqori_chegarasi(self):
        Promokod.objects.create(kod='KATTA', tur='foiz', qiymat=50, eng_kop_chegirma=100000)
        natija, _, _ = hisobla(savat(1000000), kod='KATTA')
        self.assertEqual(natija['chegirma'], 100000)

    def test_summali_chegirma_buyurtmadan_oshmaydi(self):
        Promokod.objects.create(kod='KOP', tur='summa', qiymat=900000)
        natija, _, _ = hisobla(savat(100000), kod='KOP', yetkazish='filialdan')
        self.assertEqual(natija['chegirma'], 100000)
        self.assertEqual(natija['jami'], 0)

    def test_topilmagan_kod_xato_beradi(self):
        natija, promo, xato = hisobla(savat(500000), kod='YOQ')
        self.assertIn('topilmadi', xato)
        self.assertIsNone(promo)
        self.assertEqual(natija['chegirma'], 0)

    def test_nofaol_kod_qollanmaydi(self):
        Promokod.objects.create(kod='ESKI', tur='foiz', qiymat=10, faol=False)
        natija, promo, xato = hisobla(savat(500000), kod='ESKI')
        self.assertTrue(xato)
        self.assertIsNone(promo)
        self.assertEqual(natija['chegirma'], 0)

    def test_muddati_tugagan_kod(self):
        Promokod.objects.create(
            kod='TUGAGAN', tur='foiz', qiymat=10,
            tugash=timezone.now() - timezone.timedelta(days=1))
        _, promo, xato = hisobla(savat(500000), kod='TUGAGAN')
        self.assertIn('muddati', xato)
        self.assertIsNone(promo)

    def test_limit_tugagan_kod(self):
        Promokod.objects.create(kod='LIMIT', tur='foiz', qiymat=10, limit=2, ishlatilgan=2)
        _, promo, xato = hisobla(savat(500000), kod='LIMIT')
        self.assertIn('limiti', xato)
        self.assertIsNone(promo)

    def test_eng_kam_summa_talabi(self):
        Promokod.objects.create(kod='KATTAGA', tur='foiz', qiymat=10, eng_kam_summa=1000000)
        _, promo, xato = hisobla(savat(500000), kod='KATTAGA')
        self.assertTrue(xato)
        self.assertIsNone(promo)


@override_settings(**NARXLAR)
class BolibTolashTest(SimpleTestCase):
    def test_ustamasiz_muddat(self):
        umumiy, oylik, xato = bolib_hisobla(1200000, 3)
        self.assertEqual((umumiy, oylik, xato), (1200000, 400000, ''))

    def test_ustama_qoshiladi(self):
        umumiy, oylik, xato = bolib_hisobla(1000000, 12)   # 20% ustama
        self.assertEqual(xato, '')
        self.assertEqual(umumiy, 1200000)
        self.assertEqual(oylik, 100000)

    def test_oylik_tolov_yuqoriga_yaxlitlanadi(self):
        """Yig'indi oylik to'lovlar umumiy summadan kam bo'lib qolmasin."""
        umumiy, oylik, _ = bolib_hisobla(1000001, 3)
        self.assertGreaterEqual(oylik * 3, umumiy)

    def test_notogri_muddat(self):
        _, oylik, xato = bolib_hisobla(2000000, 9)
        self.assertEqual(oylik, 0)
        self.assertTrue(xato)

    def test_eng_kam_summadan_past_buyurtma(self):
        _, oylik, xato = bolib_hisobla(500000, 6)
        self.assertEqual(oylik, 0)
        self.assertIn('1 000 000', xato)
