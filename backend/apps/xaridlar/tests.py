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


# ──────────────────────────────────────────────────────────────
#  Narx mijozdan EMAS, serverdagi katalogdan olinishi
# ──────────────────────────────────────────────────────────────
import json
import tempfile
from pathlib import Path

from rest_framework.test import APIClient

from .models import Xarid


class ServerNarxiTest(TestCase):
    """Brauzer `price` ni qanday o'zgartirmasin, buyurtma katalog narxida hisoblanadi."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._papka = tempfile.TemporaryDirectory()
        fayl = Path(cls._papka.name) / 'products.json'
        fayl.write_text(json.dumps([
            {'id': 'p-1', 'slug': 'plita', 'name': 'Plita', 'price': 500000, 'image': 'x'},
            {'id': 'p-2', 'slug': 'kotel', 'name': 'Kotel', 'price': 300000, 'image': 'y'},
        ]), encoding='utf-8')
        cls._override = override_settings(XARID_MAHSULOTLAR_FAYL=str(fayl), **NARXLAR)
        cls._override.enable()

    @classmethod
    def tearDownClass(cls):
        cls._override.disable()
        cls._papka.cleanup()
        super().tearDownClass()

    def buyurtma(self, items, **qoshimcha):
        data = {
            'customer': {'name': 'Ali', 'phone': '+998901234567'},
            'delivery': {'method': 'filialdan'},
            'payment': {'method': 'naqd'},
            'items': items,
        }
        data.update(qoshimcha)
        return APIClient().post('/api/xaridlar/', data, format='json')

    def test_soxta_narx_va_nom_e_tiborsiz_qoldiriladi(self):
        r = self.buyurtma([{'productId': 'p-1', 'qty': 2, 'price': 1, 'name': 'Tekin'}])
        self.assertEqual(r.status_code, 201, r.content)
        xarid = Xarid.objects.get(raqam=r.json()['id'])
        qator = xarid.qatorlar.get()
        self.assertEqual(qator.narx, 500000)
        self.assertEqual(qator.nomi, 'Plita')
        self.assertEqual(xarid.mahsulotlar_summasi, 1000000)
        self.assertEqual(xarid.jami, 1000000)

    def test_total_ham_e_tiborsiz_qoldiriladi(self):
        r = self.buyurtma([{'productId': 'p-2', 'qty': 1}], total=1)
        self.assertEqual(r.status_code, 201, r.content)
        self.assertEqual(Xarid.objects.get(raqam=r.json()['id']).jami, 300000)

    def test_notanish_mahsulot_rad_etiladi(self):
        r = self.buyurtma([{'productId': 'yoq-mahsulot', 'qty': 1}])
        self.assertEqual(r.status_code, 400)
        self.assertEqual(Xarid.objects.count(), 0)

    def test_bir_mahsulot_ikki_marta_kelsa_birlashtiriladi(self):
        r = self.buyurtma([{'productId': 'p-2', 'qty': 1}, {'productId': 'p-2', 'qty': 2}])
        self.assertEqual(r.status_code, 201, r.content)
        xarid = Xarid.objects.get(raqam=r.json()['id'])
        self.assertEqual(xarid.qatorlar.count(), 1)
        self.assertEqual(xarid.mahsulotlar_summasi, 900000)

    def test_nol_miqdor_rad_etiladi(self):
        r = self.buyurtma([{'productId': 'p-1', 'qty': 0}])
        self.assertEqual(r.status_code, 400)

    def test_promokod_tekshiruvi_ham_server_narxida(self):
        Promokod.objects.create(kod='YOZ10', tur='foiz', qiymat=10)
        r = APIClient().post('/api/xaridlar/promokod/', {
            'kod': 'YOZ10', 'delivery': 'filialdan',
            'items': [{'productId': 'p-1', 'qty': 1, 'price': 1}],
        }, format='json')
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(r.json()['chegirma'], 50000)   # 500 000 ning 10%, soxta 1 emas


# ──────────────────────────────────────────────────────────────
#  Marketing sayti katalogi (index.html): narx KatalogNarx dan, `kalit` bo'yicha
# ──────────────────────────────────────────────────────────────
from apps.katalog.models import KatalogNarx


@override_settings(**NARXLAR)
class KatalogQatoriTest(TestCase):
    def setUp(self):
        KatalogNarx.objects.create(kalit='ugop-16', kategoriya='hisob', nomi='Hisoblagich G4',
                                   narx=700000, birlik='dona')
        KatalogNarx.objects.create(kalit='sorov-1', kategoriya='ventil', nomi='Kran', narx=500000,
                                   sorovnoma=True)
        KatalogNarx.objects.create(kalit='gorelka-1', kategoriya='gorelka', nomi='Gorelka',
                                   narx=850000)
        KatalogNarx.objects.create(kalit='nofaol-1', kategoriya='hisob', nomi='Eski', narx=1000,
                                   faol=False)

    def buyurtma(self, items):
        return APIClient().post('/api/xaridlar/', {
            'customer': {'name': 'Ali', 'phone': '+998901234567'},
            'delivery': {'method': 'filialdan'}, 'payment': {'method': 'naqd'},
            'items': items}, format='json')

    def jami(self, items):
        r = self.buyurtma(items)
        self.assertEqual(r.status_code, 201, r.content)
        return Xarid.objects.get(raqam=r.json()['id'])

    def test_narx_bazadan_soxta_narx_e_tiborsiz(self):
        x = self.jami([{'kalit': 'ugop-16', 'name': 'Boshqa nom', 'qty': 2, 'price': 1}])
        q = x.qatorlar.get()
        self.assertEqual((q.narx, q.nomi, q.mahsulot_id), (700000, 'Hisoblagich G4', 'kat:ugop-16'))
        self.assertEqual(x.jami, 1400000)

    def test_sorovnoma_narxsiz_hisoblanadi(self):
        self.assertEqual(self.jami([{'kalit': 'sorov-1', 'name': 'Kran', 'qty': 3}]).jami, 0)

    def test_yopiq_bolim_narxi_hisobga_olinmaydi(self):
        self.assertEqual(self.jami([{'kalit': 'gorelka-1', 'name': 'Gorelka', 'qty': 1}]).jami, 0)

    def test_nofaol_va_notanish_kalit_narxi_nol(self):
        for kalit in ('nofaol-1', 'yoq-kalit'):
            self.assertEqual(self.jami([{'kalit': kalit, 'name': 'X', 'qty': 1, 'price': 99999}]).jami, 0)

    def test_kalitsiz_qator_nomi_bilan_narxi_nol(self):
        x = self.jami([{'name': "Po'lat quvur 57×3.5", 'qty': 2, 'price': 5}])
        self.assertEqual(x.jami, 0)
        self.assertTrue(x.qatorlar.get().mahsulot_id.startswith('kat:'))

    def test_kalitsiz_har_xil_nomlar_alohida_qator(self):
        x = self.jami([{'name': 'Quvur A', 'qty': 1}, {'name': 'Quvur B', 'qty': 1}])
        self.assertEqual(x.qatorlar.count(), 2)

    def test_mahsulotsiz_qator_rad_etiladi(self):
        self.assertEqual(self.buyurtma([{'qty': 1}]).status_code, 400)
        self.assertEqual(Xarid.objects.count(), 0)

    def test_ikona_faqat_fa_nomi_qabul_qilinadi(self):
        x = self.jami([{'kalit': 'ugop-16', 'name': 'x', 'qty': 1, 'image': 'javascript:alert(1)'}])
        self.assertEqual(x.qatorlar.get().rasm, '')
        x = self.jami([{'kalit': 'ugop-16', 'name': 'x', 'qty': 1, 'image': 'fa-fire'}])
        self.assertEqual(x.qatorlar.get().rasm, 'fa-fire')

    def test_aralash_savat_do_kon_va_katalog(self):
        # do'kon mahsuloti (productId) bilan katalog qatori bir buyurtmada — pastdagi sinfdagi fayl
        # bo'lmasa productId topilmaydi va 400 qaytadi (narx baribir mijozdan olinmaydi)
        r = self.buyurtma([{'productId': 'yoq-mahsulot', 'qty': 1}, {'kalit': 'ugop-16', 'name': 'x', 'qty': 1}])
        self.assertEqual(r.status_code, 400)
