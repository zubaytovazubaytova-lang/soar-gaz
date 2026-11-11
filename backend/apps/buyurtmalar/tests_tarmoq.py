"""Buyurtma narx tarmog'i (ulgurji / aholi) va xizmat tanlash qoidalari."""
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from apps.auth_app.models import AuditYozuv, Foydalanuvchi
from apps.narxnoma.models import Narxnoma, NarxnomaQator
from .models import Buyurtma

URL = '/api/buyurtmalar/'


def klient(user):
    c = APIClient()
    c.credentials(HTTP_AUTHORIZATION='Bearer ' + str(RefreshToken.for_user(user).access_token))
    return c


class TarmoqTestlari(TestCase):
    def setUp(self):
        mk = Foydalanuvchi.objects.create
        self.aholi = mk(telefon='+998901110001', ism='Karim', rol='mijoz')
        self.korxona = mk(telefon='+998901110002', ism='Firma', rol='mijoz', mulk_turi='korxona')
        self.xodim = mk(telefon='+998900000091', ism='Ali', rol='xodim', holat='faol')
        self.admin = mk(telefon='+998900000092', ism='Admin', rol='admin', holat='faol', is_superuser=True)
        self.x, self.a = klient(self.xodim), klient(self.admin)
        # Aholi «buyurtma asosida» — hujjatdagi 1-qator (30 236 / 46 254), ikki ustunli narxnoma
        self.n_aholi = Narxnoma.objects.get(tarmoq='aholi', bolim='buyurtma')
        self.q_aholi = NarxnomaQator.objects.get(narxnoma=self.n_aholi, tartib=1)
        # Bitta ustunli narxnoma holatini sinash uchun «o'rnatish» narxnomasining 2-ustuni olib tashlanadi
        # va unga qo'lda bitta qator qo'shiladi (hujjatdagi uchala narxnoma ikki ustunli)
        ornatish = Narxnoma.objects.get(tarmoq='aholi', bolim='ornatish')
        Narxnoma.objects.filter(pk=ornatish.pk).update(ustun1_qisqa='', ustun2='', ustun2_qisqa='')
        self.q_ornatish = NarxnomaQator.objects.create(
            narxnoma=ornatish, tartib=99, nomi="Bitta narxli sinov xizmati", p_dan=300000)
        self.q_ulgurji = NarxnomaQator.objects.get(narxnoma__tarmoq='ulgurji', narxnoma__bolim='profilaktika', tartib=1)

    def buyurtma(self, tarmoq='aholi'):
        return Buyurtma.objects.create(mijoz=self.aholi, xodim=self.xodim, xizmat='servis', tarmoq=tarmoq)

    def biriktir(self, b, qator, ustun='p', client=None):
        return (client or self.x).post(f'{URL}{b.pk}/xizmatlar/',
                                       {'xizmatlar': [{'qator': qator.pk, 'ustun': ustun, 'soni': 1}]},
                                       format='json')

    # ----- tarmoq qanday aniqlanadi -----

    def test_oddiy_mijoz_buyurtmasi_aholi(self):
        r = klient(self.aholi).post(URL, {'xizmat': 'servis'}, format='json')
        self.assertEqual(r.status_code, 201, r.content)
        self.assertEqual(Buyurtma.objects.get().tarmoq, 'aholi')

    def test_korxona_mijoz_buyurtmasi_ulgurji(self):
        r = klient(self.korxona).post(URL, {'xizmat': 'servis'}, format='json')
        self.assertEqual(r.status_code, 201, r.content)
        self.assertEqual(Buyurtma.objects.get().tarmoq, 'ulgurji')

    def test_mijoz_tarmoqni_ozi_tanlay_olmaydi(self):
        r = klient(self.aholi).post(URL, {'xizmat': 'servis', 'tarmoq': 'ulgurji'}, format='json')
        self.assertEqual(r.status_code, 201)
        self.assertEqual(Buyurtma.objects.get().tarmoq, 'aholi')
        # mavjud buyurtmani ham o'zgartira olmaydi
        b = Buyurtma.objects.get()
        r = klient(self.aholi).patch(f'{URL}{b.pk}/', {'tarmoq': 'ulgurji', 'holat': 'bekor'}, format='json')
        self.assertEqual(r.status_code, 403)
        b.refresh_from_db()
        self.assertEqual(b.tarmoq, 'aholi')

    def test_xodim_tarmoqni_ozgartira_olmaydi(self):
        b = self.buyurtma()
        self.assertEqual(self.x.patch(f'{URL}{b.pk}/', {'tarmoq': 'ulgurji'}, format='json').status_code, 403)
        b.refresh_from_db()
        self.assertEqual(b.tarmoq, 'aholi')

    def test_admin_tarmoqni_ozgartiradi_va_jurnalga_yoziladi(self):
        b = self.buyurtma()
        r = self.a.patch(f'{URL}{b.pk}/', {'tarmoq': 'ulgurji'}, format='json')
        self.assertEqual(r.status_code, 200, r.content)
        b.refresh_from_db()
        self.assertEqual(b.tarmoq, 'ulgurji')
        self.assertTrue(AuditYozuv.objects.filter(amal='buyurtma_tarmoq').exists())
        self.assertEqual(self.a.patch(f'{URL}{b.pk}/', {'tarmoq': 'xitoy'}, format='json').status_code, 400)

    def test_xizmatlari_bor_buyurtma_tarmogi_ozgarmaydi(self):
        b = self.buyurtma('aholi')
        self.assertEqual(self.biriktir(b, self.q_aholi).status_code, 201)
        r = self.a.patch(f'{URL}{b.pk}/', {'tarmoq': 'ulgurji'}, format='json')
        self.assertEqual(r.status_code, 409)
        b.refresh_from_db()
        self.assertEqual(b.tarmoq, 'aholi')

    # ----- xizmat faqat o'z tarmog'idan -----

    def test_aholi_buyurtmaga_aholi_xizmati_mumkin(self):
        b = self.buyurtma('aholi')
        r = self.biriktir(b, self.q_aholi)
        self.assertEqual(r.status_code, 201, r.content)
        self.assertEqual(r.json()['jami_dan'], 30236)

    def test_aholi_buyurtmaga_ulgurji_xizmati_mumkin_emas(self):
        b = self.buyurtma('aholi')
        r = self.biriktir(b, self.q_ulgurji)
        self.assertEqual(r.status_code, 400)
        self.assertIn('mos emas', r.json()['detail'])
        self.assertFalse(b.xizmatlar.exists())

    def test_ulgurji_buyurtmaga_aholi_xizmati_mumkin_emas(self):
        b = self.buyurtma('ulgurji')
        self.assertEqual(self.biriktir(b, self.q_aholi).status_code, 400)
        self.assertEqual(self.biriktir(b, self.q_ulgurji).status_code, 201)

    def test_aralash_tanlovda_hech_narsa_saqlanmaydi(self):
        b = self.buyurtma('aholi')
        r = self.x.post(f'{URL}{b.pk}/xizmatlar/', {'xizmatlar': [
            {'qator': self.q_aholi.pk, 'ustun': 'p', 'soni': 1},
            {'qator': self.q_ulgurji.pk, 'ustun': 'p', 'soni': 1}]}, format='json')
        self.assertEqual(r.status_code, 400)
        self.assertFalse(b.xizmatlar.exists())

    def test_ustun_nomi_narxnomadan_saqlanadi(self):
        b = self.buyurtma('ulgurji')
        r = self.biriktir(b, self.q_ulgurji, 'r')
        self.assertEqual(r.json()['royxat'][0]['ustun_nomi'], 'reviziya')
        # aholi «buyurtma asosida»: ikki ustun, qisqa nomlari narxnomadan
        b2 = self.buyurtma('aholi')
        r = self.biriktir(b2, self.q_aholi, 'r')
        self.assertEqual(r.json()['royxat'][0]['ustun_nomi'], "texnik ko'rik")
        self.assertEqual(r.json()['jami_dan'], 46254)
        # bitta ustunli narxnomada (o'rnatish) qisqa nom bo'sh
        b3 = self.buyurtma('aholi')
        r = self.biriktir(b3, self.q_ornatish)
        self.assertEqual(r.json()['royxat'][0]['ustun_nomi'], '')

    def test_bitta_ustunli_narxnomada_ikkinchi_ustun_tanlanmaydi(self):
        b = self.buyurtma('aholi')
        self.assertEqual(self.biriktir(b, self.q_ornatish, 'r').status_code, 400)

    def test_matnli_narxga_xizmat_biriktirilmaydi(self):
        # 25-qator: ikkala narx ham «kelishuv asosida» — hisoblash uchun raqam yo'q
        q25 = NarxnomaQator.objects.get(narxnoma=self.n_aholi, tartib=25)
        b = self.buyurtma('aholi')
        self.assertEqual(self.biriktir(b, q25).status_code, 400)
        # 26-qator: profilaktika narxli (57 300), texnik ko'rik kelishuv asosida
        q26 = NarxnomaQator.objects.get(narxnoma=self.n_aholi, tartib=26)
        self.assertEqual(self.biriktir(b, q26, 'p').status_code, 201)
        self.assertEqual(self.biriktir(b, q26, 'r').status_code, 400)

    def test_royxatda_tarmoq_korinadi(self):
        self.buyurtma('aholi')
        j = self.x.get(URL).json()[0]
        self.assertEqual((j['tarmoq'], j['tarmoq_nomi']), ('aholi', 'Aholi'))
