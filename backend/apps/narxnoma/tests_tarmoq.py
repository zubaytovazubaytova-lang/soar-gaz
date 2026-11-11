"""Narxnoma tarmoqlari: ulgurji va aholi (3 bo'lim)."""
from django.db import IntegrityError, transaction
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from apps.auth_app.models import Foydalanuvchi
from .models import Narxnoma, NarxnomaQator

URL = '/api/narxnoma/'


def klient(user):
    c = APIClient()
    c.credentials(HTTP_AUTHORIZATION='Bearer ' + str(RefreshToken.for_user(user).access_token))
    return c


class TarmoqTestlari(TestCase):
    def setUp(self):
        mk = Foydalanuvchi.objects.create
        self.xodim = mk(telefon='+998900000081', ism='Ali', rol='xodim', holat='faol')
        self.admin = mk(telefon='+998900000082', ism='Admin', rol='admin', holat='faol', is_superuser=True)
        self.x, self.a = klient(self.xodim), klient(self.admin)

    def test_tarmoq_va_bolimlar_yaratilgan(self):
        royxat = list(Narxnoma.objects.values_list('tarmoq', 'bolim'))
        self.assertEqual(royxat, [('ulgurji', 'profilaktika'), ('aholi', 'buyurtma'),
                                  ('aholi', 'profilaktika'), ('aholi', 'ornatish'),
                                  ('ulgurji', 'metrologiya'), ('aholi', 'metrologiya')])

    def test_mavjud_narxnoma_ulgurji_va_narxlari_saqlangan(self):
        n = Narxnoma.objects.get(tarmoq='ulgurji', bolim='profilaktika')
        self.assertEqual(n.qatorlar.count(), 49)
        self.assertEqual((n.ustun1_qisqa, n.ustun2_qisqa), ('profilaktika', 'reviziya'))

    def test_aholining_uch_bolimi_hujjatdan_kiritilgan(self):
        self.assertEqual(Narxnoma.objects.get(tarmoq='aholi', bolim='buyurtma').qatorlar.count(), 27)
        self.assertEqual(Narxnoma.objects.get(tarmoq='aholi', bolim='profilaktika').qatorlar.count(), 26)
        self.assertEqual(Narxnoma.objects.get(tarmoq='aholi', bolim='ornatish').qatorlar.count(), 25)

    def test_aholi_ornatish_hujjat_qiymatlari(self):
        n = Narxnoma.objects.get(tarmoq='aholi', bolim='ornatish')
        q = lambda t: NarxnomaQator.objects.get(narxnoma=n, tartib=t)
        self.assertEqual(list(n.qatorlar.values_list('tartib', flat=True)), list(range(1, 26)))
        self.assertEqual((q(1).p_dan, q(1).r_dan), (80628, 123344))
        self.assertEqual((q(9).p_dan, q(9).r_dan), (482000, 754000))
        self.assertEqual((q(10).p_dan, q(10).r_dan), (200000, 600000))      # bu qatorda 2 baravar
        self.assertEqual((q(18).p_dan, q(18).r_dan), (640000, 780000))
        self.assertEqual((q(16).p_dan, q(16).r_dan), (None, None))           # ro'yxatga kirmagan: kelishuv
        self.assertIn('kelishuv', q(16).izoh)
        self.assertEqual((q(25).p_dan, q(25).r_dan), (16250, 32500))         # transport

    def test_aholi_ornatish_oddiy_narxlarning_4_baravari(self):
        """Uchinchi hujjat raqamlari ham boshqalar bilan mos: o'rnatish narxi oddiy profilaktika
        narxining 4 baravari (faqat 10-qator boshlang'ich narxi 2 baravar). Migratsiyalardagi
        boshlang'ich ma'lumotni tekshiradi (admin keyin o'zgartirsa, bu qoidaga bog'lanmaydi)."""
        from importlib import import_module
        oddiy = {q[0]: q for q in import_module('apps.narxnoma.migrations.0006_aholi_profilaktika_narxlari').QATORLAR}
        ornatish = {q[0]: q for q in import_module('apps.narxnoma.migrations.0007_aholi_ornatish_narxlari').QATORLAR}
        # tartib raqamlari mos kelmaydigan yagona qator: o'rnatishdagi 16 ↔ oddiydagi 26
        moslik = {t: t for t in list(range(1, 16)) + list(range(17, 25))}
        moslik[16] = 26
        for t_o, t_a in moslik.items():
            nom_o, nom_a = ornatish[t_o], oddiy[t_a]
            if nom_o[2] is None:
                self.assertEqual((nom_o[2], nom_o[3], nom_a[2], nom_a[3]), (None, None, None, None), t_o)
                continue
            koeff = 2 if t_o == 10 else 4
            self.assertAlmostEqual(nom_a[2] * koeff, nom_o[2], delta=2, msg=f'{t_o}: boshlang\'ich')
            self.assertAlmostEqual(nom_a[3] * 4, nom_o[3], delta=2, msg=f'{t_o}: o\'rtacha')

    def test_eslatma_aholi_narxnomalarida(self):
        n = Narxnoma.objects.get(tarmoq='aholi', bolim='ornatish')
        self.assertIn('PG-5x', n.eslatma)
        self.assertIn("iste'molchi", n.eslatma)                  # 3-band: material va ehtiyot qismlar alohida to'lanadi
        for bolim in ('buyurtma', 'profilaktika'):
            self.assertIn('PG-5x', Narxnoma.objects.get(tarmoq='aholi', bolim=bolim).eslatma, bolim)

    def test_aholi_profilaktika_hujjat_qiymatlari(self):
        n = Narxnoma.objects.get(tarmoq='aholi', bolim='profilaktika')
        q = lambda t: NarxnomaQator.objects.get(narxnoma=n, tartib=t)
        self.assertEqual(list(n.qatorlar.values_list('tartib', flat=True)), list(range(1, 27)))
        self.assertEqual((q(1).p_dan, q(1).r_dan), (20157, 30836))
        self.assertEqual((q(9).p_dan, q(9).r_dan), (120500, 188500))
        self.assertEqual((q(18).p_dan, q(18).r_dan), (160000, 195000))
        self.assertEqual((q(24).p_dan, q(24).r_dan), (31420, 54290))
        # Bu hujjatda tartib boshqacha: 25 — ichki gaz quvurlari, 26 — ro'yxatga kirmagan jihozlar
        self.assertEqual((q(25).nomi, q(25).p_dan, q(25).r_dan), ('Ichki gaz quvurlari', 38200, None))
        self.assertIn('kelishuv', q(25).izoh)
        self.assertEqual((q(26).p_dan, q(26).r_dan), (None, None))
        self.assertTrue(q(26).izoh)
        # Transport xarajati bu hujjatda yo'q (u faqat «buyurtma asosida» da)
        self.assertFalse(n.qatorlar.filter(nomi__startswith='Transport').exists())

    def test_ikki_hujjat_bir_biri_bilan_mos_buyurtma_asosida_1_5_baravar(self):
        """Ikkala qog'oz hujjatdan ko'chirilgan raqamlar bir-birini tekshiradi: «buyurtma asosida»
        narxlar oddiy profilaktika narxlarining 1,5 baravari. Bu migratsiyalardagi boshlang'ich
        ma'lumotni tekshiradi (admin keyin narxni o'zgartirsa, bu qoidaga bog'lanmaydi)."""
        from importlib import import_module
        oddiy = {q[1]: q for q in import_module('apps.narxnoma.migrations.0006_aholi_profilaktika_narxlari').QATORLAR}
        buyurtma = {q[1]: q for q in import_module('apps.narxnoma.migrations.0005_aholi_buyurtma_narxlari').QATORLAR}
        umumiy = set(oddiy) & set(buyurtma)
        self.assertEqual(len(umumiy), 26)                       # barcha 26 qator ikkala hujjatda bor
        for nom in umumiy:
            for ustun in (2, 3):                                # 2 — profilaktika, 3 — texnik ko'rik
                a, b = oddiy[nom][ustun], buyurtma[nom][ustun]
                if a is None or b is None:
                    self.assertEqual((a, b), (None, None), nom)  # kelishuv ikkalasida ham bir xil
                else:
                    self.assertAlmostEqual(a * 1.5, b, delta=1, msg=f'{nom} ustun {ustun}: {a} × 1,5 ≠ {b}')

    def test_aholi_ustunlari(self):
        buyurtma = Narxnoma.objects.get(tarmoq='aholi', bolim='buyurtma')
        profil = Narxnoma.objects.get(tarmoq='aholi', bolim='profilaktika')
        ornat = Narxnoma.objects.get(tarmoq='aholi', bolim='ornatish')
        for n in (buyurtma, profil, ornat):
            self.assertTrue(n.ustun1 and n.ustun2, n)            # uchala hujjatda ham ikki narx ustuni
        self.assertEqual((buyurtma.ustun1_qisqa, buyurtma.ustun2_qisqa), ('profilaktika', "texnik ko'rik"))
        self.assertEqual((profil.ustun1_qisqa, profil.ustun2_qisqa), ('profilaktika', "texnik ko'rik"))
        self.assertEqual((ornat.ustun1_qisqa, ornat.ustun2_qisqa), ("boshlang'ich", "o'rtacha"))

    def test_aholi_buyurtma_asosida_hujjat_qiymatlari(self):
        n = Narxnoma.objects.get(tarmoq='aholi', bolim='buyurtma')
        q = lambda t: NarxnomaQator.objects.get(narxnoma=n, tartib=t)
        self.assertEqual(list(n.qatorlar.values_list('tartib', flat=True)), list(range(1, 28)))
        self.assertEqual((q(1).p_dan, q(1).r_dan), (30236, 46254))
        self.assertEqual((q(9).p_dan, q(9).r_dan), (180750, 282750))
        self.assertEqual((q(18).p_dan, q(18).r_dan), (240000, 292500))
        self.assertEqual((q(27).p_dan, q(27).r_dan), (16250, 32500))
        # narx o'rnida matn: 25 — ikkalasi ham kelishuv; 26 — profilaktika narxli, texnik ko'rik kelishuv
        self.assertEqual((q(25).p_dan, q(25).r_dan), (None, None))
        self.assertTrue(q(25).izoh)
        self.assertEqual((q(26).p_dan, q(26).r_dan), (57300, None))
        self.assertIn('kelishuv', q(26).izoh)

    def test_aholi_texnik_korik_profilaktikadan_qimmat(self):
        n = Narxnoma.objects.get(tarmoq='aholi', bolim='buyurtma')
        for q in n.qatorlar.exclude(p_dan=None).exclude(r_dan=None):
            self.assertGreater(q.r_dan, q.p_dan, q.tartib)

    def test_ulgurji_narxlari_aholi_bilan_aralashmagan(self):
        ulgurji = Narxnoma.objects.get(tarmoq='ulgurji', bolim='profilaktika')
        self.assertEqual(ulgurji.qatorlar.count(), 49)
        self.assertEqual(NarxnomaQator.objects.get(narxnoma=ulgurji, tartib=1).p_dan, 233500)

    def test_tarmoq_va_bolim_takrorlanmaydi(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            Narxnoma.objects.create(tarmoq='aholi', bolim='buyurtma', sarlavha='x', ustun1='y')

    def test_api_tarmoq_maydonlarini_beradi(self):
        r = {(n['tarmoq'], n['bolim']): n for n in self.x.get(URL).json()}
        n = r[('aholi', 'ornatish')]
        self.assertEqual(n['tarmoq_nomi'], 'Aholi')
        self.assertIn("o'rnatib", n['bolim_nomi'])
        self.assertEqual(n['ustun2'], "O'rtacha bir xizmat narxi (so'm)")
        self.assertEqual(len(n['qatorlar']), 25)

    def test_admin_aholi_xizmati_qosha_oladi(self):
        n = Narxnoma.objects.get(tarmoq='aholi', bolim='buyurtma')
        r = self.a.post(f'{URL}{n.pk}/qator/', {'nomi': "Hisoblagich almashtirish", 'p_dan': 150000}, format='json')
        self.assertEqual(r.status_code, 201, r.content)
        self.assertEqual(r.json()['tartib'], 28)                  # hujjatdagi 27 qatordan keyin
        self.assertEqual(n.qatorlar.get(nomi='Hisoblagich almashtirish').p_dan, 150000)

    def test_bitta_narxli_narxnomada_ikkinchi_narx_kiritilmaydi(self):
        # Hujjatlarning uchalasi ham ikki ustunli, shuning uchun bitta ustunli narxnoma alohida yaratiladi
        n = Narxnoma.objects.create(tarmoq='ulgurji', bolim='ornatish', sarlavha='Bitta narxli', ustun1='Narx')
        r = self.a.post(f'{URL}{n.pk}/qator/', {'nomi': 'X', 'p_dan': 1000, 'r_dan': 2000}, format='json')
        self.assertEqual(r.status_code, 400)
        self.assertFalse(n.qatorlar.exists())
        # ikki ustunli narxnomada mumkin
        p = Narxnoma.objects.get(tarmoq='aholi', bolim='profilaktika')
        r = self.a.post(f'{URL}{p.pk}/qator/', {'nomi': 'Y', 'p_dan': 1000, 'r_dan': 2000}, format='json')
        self.assertEqual(r.status_code, 201)

    def test_ustunni_olib_tashlash_qoidasi(self):
        # Hujjatdan kiritilgan narxnomalarga tegmaslik uchun alohida (bo'sh) narxnoma
        p = Narxnoma.objects.create(tarmoq='ulgurji', bolim='buyurtma', sarlavha='Sinov',
                                    ustun1='1-narx', ustun2='2-narx')
        self.a.post(f'{URL}{p.pk}/qator/', {'nomi': 'Y', 'p_dan': 1000, 'r_dan': 2000}, format='json')
        # 2-ustunda narx bor — olib tashlab bo'lmaydi
        self.assertEqual(self.a.patch(f'{URL}{p.pk}/', {'ustun2': ''}, format='json').status_code, 400)
        q = NarxnomaQator.objects.get(narxnoma=p)
        self.a.patch(f'{URL}qator/{q.pk}/', {'r_dan': None}, format='json')
        self.assertEqual(self.a.patch(f'{URL}{p.pk}/', {'ustun2': ''}, format='json').status_code, 200)

    def test_qisqa_nomlarni_ozgartirish(self):
        n = Narxnoma.objects.get(tarmoq='aholi', bolim='ornatish')
        r = self.a.patch(f'{URL}{n.pk}/', {'ustun1_qisqa': "o'rnatish"}, format='json')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()['ustun1_qisqa'], "o'rnatish")

    def test_tarmoqni_api_orqali_ozgartirib_bolmaydi(self):
        n = Narxnoma.objects.get(tarmoq='aholi', bolim='buyurtma')
        self.a.patch(f'{URL}{n.pk}/', {'tarmoq': 'ulgurji', 'bolim': 'ornatish'}, format='json')
        n.refresh_from_db()
        self.assertEqual((n.tarmoq, n.bolim), ('aholi', 'buyurtma'))
