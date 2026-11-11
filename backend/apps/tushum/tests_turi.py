"""Tushum turi (bosqich): tarmoq + bo'lim aniq tanlanadi, qolgan maydonlar unga mos bo'ladi."""
from django.core.cache import cache
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from apps.auth_app.models import Foydalanuvchi
from apps.buyurtmalar.models import Buyurtma
from apps.narxnoma.models import Narxnoma, NarxnomaQator
from .models import Tushum

URL = '/api/tushum/'


def klient(user):
    c = APIClient()
    c.credentials(HTTP_AUTHORIZATION='Bearer ' + str(RefreshToken.for_user(user).access_token))
    return c


class TushumTuriTestlari(TestCase):
    def setUp(self):
        cache.clear()
        self.addCleanup(cache.clear)
        self.xodim = Foydalanuvchi.objects.create(telefon='+998900000095', ism='Ali', rol='xodim', holat='faol')
        self.x = klient(self.xodim)
        # Aholi narxnomalariga bittadan qator (narxlar hujjatdan kiritilmagan, testda qo'lda)
        self.q_buyurtma = NarxnomaQator.objects.create(
            narxnoma=Narxnoma.objects.get(tarmoq='aholi', bolim='buyurtma'),
            tartib=1, nomi='Hisoblagich almashtirish', p_dan=150000)
        self.q_ornatish = NarxnomaQator.objects.create(
            narxnoma=Narxnoma.objects.get(tarmoq='aholi', bolim='ornatish'),
            tartib=1, nomi="Plita o'rnatish", p_dan=300000)
        self.q_ulgurji = NarxnomaQator.objects.get(narxnoma__tarmoq='ulgurji', narxnoma__bolim='profilaktika', tartib=1)
        self.b_aholi = Buyurtma.objects.create(xodim=self.xodim, xizmat='servis', tarmoq='aholi',
                                               tasdiq_summa=1_000_000)
        self.b_ulgurji = Buyurtma.objects.create(xodim=self.xodim, xizmat='servis', tarmoq='ulgurji',
                                                 tasdiq_summa=1_000_000)

    def kirit(self, turi, **kw):
        malumot = {'summa': 100000, 'usul': 'naqd', 'tushum_turi': turi}
        malumot.update(kw)
        return self.x.post(URL, malumot, format='json')

    def test_aholi_buyurtma_asosida_buyurtma_shart(self):
        r = self.kirit('aholi:buyurtma')
        self.assertEqual(r.status_code, 400)
        self.assertIn('buyurtma', r.json()['detail'].lower())
        r = self.kirit('aholi:buyurtma', buyurtma=self.b_aholi.pk, ish_qator=self.q_buyurtma.pk, ish_ustun='p')
        self.assertEqual(r.status_code, 201, r.content)
        t = Tushum.objects.get()
        self.assertEqual((t.tarmoq, t.bolim, t.buyurtma), ('aholi', 'buyurtma', self.b_aholi))

    def test_buyurtma_asosida_buyurtmasiz_ish_turi_bilan_qabul_qilinadi(self):
        """Mijoz o'zi murojaat qilgan bo'lsa tizimda buyurtma yo'q: narxnomadagi ish turi yetarli."""
        r = self.kirit('aholi:buyurtma', ish_qator=self.q_buyurtma.pk, ish_ustun='p', summa=150000)
        self.assertEqual(r.status_code, 201, r.content)
        t = Tushum.objects.get()
        self.assertEqual((t.tarmoq, t.bolim, t.buyurtma, t.ish_qator), ('aholi', 'buyurtma', None, self.q_buyurtma))
        self.assertIn('Hisoblagich almashtirish', t.ish_turi)

    def test_buyurtma_asosida_na_buyurtma_na_ish_turi_bolsa_rad(self):
        r = self.kirit('aholi:buyurtma')
        self.assertEqual(r.status_code, 400)
        self.assertIn('ish turini', r.json()['detail'])
        self.assertFalse(Tushum.objects.exists())

    def test_ornatish_buyurtmasiz_ham_mumkin(self):
        r = self.kirit('aholi:ornatish', ish_qator=self.q_ornatish.pk, ish_ustun='p')
        self.assertEqual(r.status_code, 201, r.content)
        t = Tushum.objects.get()
        self.assertEqual((t.tarmoq, t.bolim, t.buyurtma), ('aholi', 'ornatish', None))
        self.assertEqual(r.json()['bolim_nomi'][:5], "Yangi")

    def test_ulgurji_profilaktika(self):
        r = self.kirit('ulgurji:profilaktika', ish_qator=self.q_ulgurji.pk, ish_ustun='r', summa=389200)
        self.assertEqual(r.status_code, 201, r.content)
        t = Tushum.objects.get()
        self.assertEqual((t.tarmoq, t.bolim), ('ulgurji', 'profilaktika'))

    def test_ish_turi_boshqa_bolimdan_bolsa_rad(self):
        r = self.kirit('aholi:ornatish', ish_qator=self.q_buyurtma.pk, ish_ustun='p')
        self.assertEqual(r.status_code, 400)
        self.assertIn('mos emas', r.json()['detail'])
        r = self.kirit('aholi:ornatish', ish_qator=self.q_ulgurji.pk, ish_ustun='p')
        self.assertEqual(r.status_code, 400)
        self.assertFalse(Tushum.objects.exists())

    def test_buyurtma_boshqa_tarmoqdan_bolsa_rad(self):
        r = self.kirit('aholi:buyurtma', buyurtma=self.b_ulgurji.pk)
        self.assertEqual(r.status_code, 400)
        self.assertIn('tarmog', r.json()['detail'])
        self.assertFalse(Tushum.objects.exists())

    def test_notogri_tushum_turi(self):
        for turi in ('aholi', 'aholi:xx', 'xx:buyurtma', ':', 'ulgurji:ornatish', 'ulgurji:buyurtma'):
            cache.clear()
            self.assertEqual(self.kirit(turi).status_code, 400, turi)
        self.assertFalse(Tushum.objects.exists())

    def test_nofaol_narxnomali_tur_tanlanmaydi(self):
        Narxnoma.objects.filter(tarmoq='aholi', bolim='ornatish').update(faol=False)
        self.assertEqual(self.kirit('aholi:ornatish').status_code, 400)

    def test_tushum_turisiz_eski_yol_ishlaydi(self):
        # Boshqa (turkumsiz): tur ko'rsatilmasa turkum ish turidan / buyurtmadan olinadi
        r = self.x.post(URL, {'summa': 50000, 'usul': 'naqd'}, format='json')
        self.assertEqual(r.status_code, 201)
        self.assertEqual(Tushum.objects.get().tarmoq, '')
