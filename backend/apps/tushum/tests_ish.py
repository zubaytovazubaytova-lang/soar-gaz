"""Tushumda ish turi (narxnomadan tanlanadi)."""
from django.core.cache import cache
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from apps.auth_app.models import Foydalanuvchi
from apps.narxnoma.models import NarxnomaQator
from .models import Tushum

URL = '/api/tushum/'


def klient(user):
    c = APIClient()
    c.credentials(HTTP_AUTHORIZATION='Bearer ' + str(RefreshToken.for_user(user).access_token))
    return c


class IshTuriTestlari(TestCase):
    def setUp(self):
        cache.clear()
        self.addCleanup(cache.clear)
        self.xodim = Foydalanuvchi.objects.create(telefon='+998900000071', ism='Ali', rol='xodim', holat='faol')
        self.admin = Foydalanuvchi.objects.create(telefon='+998900000072', ism='Admin', rol='admin', holat='faol', is_superuser=True)
        self.x, self.a = klient(self.xodim), klient(self.admin)
        self.q1 = NarxnomaQator.objects.get(narxnoma__tarmoq='ulgurji', narxnoma__bolim='profilaktika', tartib=1)

    def kirit(self, **kw):
        malumot = {'summa': 233500, 'usul': 'naqd'}
        malumot.update(kw)
        return self.x.post(URL, malumot, format='json')

    def test_ish_turi_nomi_serverdagi_narxnomadan_olinadi(self):
        r = self.kirit(ish_qator=self.q1.pk, ish_ustun='p', ish_turi='SOXTA NOM')
        self.assertEqual(r.status_code, 201, r.content)
        t = Tushum.objects.get()
        self.assertEqual(t.ish_turi, 'Gaz plitasi 2 kamparakli (profilaktika)')
        self.assertEqual(t.ish_qator, self.q1)
        self.assertEqual(r.json()['ish_turi'], t.ish_turi)

    def test_reviziya_va_ustunsiz(self):
        self.kirit(ish_qator=self.q1.pk, ish_ustun='r')
        self.assertTrue(Tushum.objects.get().ish_turi.endswith('(reviziya)'))
        Tushum.objects.all().delete()
        cache.clear()
        self.kirit(ish_qator=self.q1.pk)
        self.assertEqual(Tushum.objects.get().ish_turi, 'Gaz plitasi 2 kamparakli')

    def test_ish_turisiz_ham_kiritiladi(self):
        self.assertEqual(self.kirit().status_code, 201)
        self.assertEqual(Tushum.objects.get().ish_turi, '')

    def test_notogri_ish_turi_rad_etiladi(self):
        for el in ({'ish_qator': 99999}, {'ish_qator': 'abc'}, {'ish_qator': True},
                   {'ish_qator': self.q1.pk, 'ish_ustun': 'x'}):
            cache.clear()
            self.assertEqual(self.kirit(**el).status_code, 400, el)
        self.assertFalse(Tushum.objects.exists())

    def test_nofaol_ish_turi_tanlanmaydi(self):
        self.q1.faol = False
        self.q1.save()
        self.assertEqual(self.kirit(ish_qator=self.q1.pk).status_code, 400)

    def test_narxnoma_ozgarsa_tushumdagi_nom_qoladi(self):
        self.kirit(ish_qator=self.q1.pk, ish_ustun='p')
        self.q1.nomi = 'Boshqa nom'
        self.q1.save()
        self.assertEqual(Tushum.objects.get().ish_turi, 'Gaz plitasi 2 kamparakli (profilaktika)')
        self.assertEqual(self.x.get(URL).json()['yozuvlar'][0]['ish_turi'],
                         'Gaz plitasi 2 kamparakli (profilaktika)')

    def test_tarmoq_va_bolim_ish_turidan_olinadi(self):
        r = self.kirit(ish_qator=self.q1.pk, ish_ustun='p')
        self.assertEqual(r.status_code, 201, r.content)
        t = Tushum.objects.get()
        self.assertEqual((t.tarmoq, t.bolim), ('ulgurji', 'profilaktika'))
        j = r.json()
        self.assertEqual((j['tarmoq_nomi'][:8], j['bolim_nomi'][:11]), ('Ulgurji ', 'Profilaktik'))

    def test_ish_turisiz_va_buyurtmasiz_tushum_turkumsiz(self):
        self.kirit()
        t = Tushum.objects.get()
        self.assertEqual((t.tarmoq, t.bolim), ('', ''))

    def test_buyurtma_tarmogi_meros_bolinadi(self):
        from apps.buyurtmalar.models import Buyurtma
        b = Buyurtma.objects.create(xodim=self.xodim, xizmat='servis', tarmoq='aholi', tasdiq_summa=500000)
        self.kirit(buyurtma=b.pk, summa=100000)
        t = Tushum.objects.get()
        self.assertEqual((t.tarmoq, t.bolim), ('aholi', ''))

    def test_buyurtma_tarmogiga_mos_kelmagan_ish_turi_rad_etiladi(self):
        from apps.buyurtmalar.models import Buyurtma
        b = Buyurtma.objects.create(xodim=self.xodim, xizmat='servis', tarmoq='aholi', tasdiq_summa=500000)
        r = self.kirit(buyurtma=b.pk, summa=100000, ish_qator=self.q1.pk)     # q1 — ulgurji
        self.assertEqual(r.status_code, 400)
        self.assertIn('mos emas', r.json()['detail'])
        self.assertFalse(Tushum.objects.exists())

    def test_bir_xil_tarmoqdagi_ish_turi_buyurtma_bilan_mumkin(self):
        from apps.buyurtmalar.models import Buyurtma
        b = Buyurtma.objects.create(xodim=self.xodim, xizmat='servis', tarmoq='ulgurji', tasdiq_summa=500000)
        self.assertEqual(self.kirit(buyurtma=b.pk, summa=233500, ish_qator=self.q1.pk).status_code, 201)

    def test_admin_tarmoq_boyicha_jami_va_filtr(self):
        from apps.buyurtmalar.models import Buyurtma
        self.kirit(ish_qator=self.q1.pk, summa=200000)                      # ulgurji
        b = Buyurtma.objects.create(xodim=self.xodim, xizmat='servis', tarmoq='aholi', tasdiq_summa=900000)
        self.kirit(buyurtma=b.pk, summa=300000)                             # aholi
        self.kirit(summa=50000)                                             # turkumsiz
        j = self.a.get(URL + 'admin/').json()
        self.assertEqual(j['tarmoq_jami']['ulgurji']['kutilmoqda'], 200000)
        self.assertEqual(j['tarmoq_jami']['aholi']['kutilmoqda'], 300000)
        self.assertEqual(j['tarmoq_jami']['boshqa']['kutilmoqda'], 50000)
        self.assertEqual(len(j['yozuvlar']), 3)
        f = self.a.get(URL + 'admin/?tarmoq=aholi').json()
        self.assertEqual([y['summa'] for y in f['yozuvlar']], [300000])
        # filtr jami hisobga ta'sir qilmaydi
        self.assertEqual(f['tarmoq_jami']['ulgurji']['kutilmoqda'], 200000)

    def test_admin_royxatida_koriladi(self):
        self.kirit(ish_qator=self.q1.pk, ish_ustun='p')
        self.assertIn('profilaktika', self.a.get(URL + 'admin/').json()['yozuvlar'][0]['ish_turi'])
