"""Xizmatlar narxnomasi: boshlang'ich ma'lumot, ko'rish ruxsati, admin tahriri.

Test bazasi migratsiyalardan quriladi, shuning uchun boshlang'ich narxnoma
(49 qator) har testda tayyor turadi.
"""
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from apps.auth_app.models import AuditYozuv, Foydalanuvchi
from .models import Narxnoma, NarxnomaQator

URL = '/api/narxnoma/'


def klient(user):
    c = APIClient()
    c.credentials(HTTP_AUTHORIZATION='Bearer ' + str(RefreshToken.for_user(user).access_token))
    return c


class Asos(TestCase):
    def setUp(self):
        mk = Foydalanuvchi.objects.create
        self.xodim = mk(telefon='+998900000051', ism='Ali', rol='xodim', holat='faol')
        self.nofaol = mk(telefon='+998900000052', ism='Eski', rol='xodim', holat='nofaol')
        self.admin = mk(telefon='+998900000053', ism='Admin', rol='admin', holat='faol', is_superuser=True)
        self.mijoz = mk(telefon='+998900000054', rol='mijoz')
        self.x, self.a, self.m, self.nf = (klient(self.xodim), klient(self.admin),
                                           klient(self.mijoz), klient(self.nofaol))
        self.n = Narxnoma.objects.get(tarmoq='ulgurji', bolim='profilaktika')

    def qator(self, tartib):
        return NarxnomaQator.objects.get(narxnoma=self.n, tartib=tartib)


class BoshlangichMalumotTestlari(Asos):
    def test_49_qator_va_sarlavha(self):
        self.assertEqual(self.n.qatorlar.count(), 49)
        self.assertEqual(str(self.n.amal_qiladi), '2026-09-01')
        self.assertEqual(list(self.n.qatorlar.values_list('tartib', flat=True)), list(range(1, 50)))

    def test_ayrim_narxlar_hujjatga_mos(self):
        q = self.qator(1)
        self.assertEqual((q.p_dan, q.r_dan), (233500, 389200))
        q = self.qator(13)   # oraliq
        self.assertEqual((q.p_dan, q.p_gacha, q.r_dan, q.r_gacha), (210000, 330000, 350000, 550000))
        q = self.qator(24)
        self.assertEqual((q.p_dan, q.r_dan), (1360870, 2268117))
        q = self.qator(49)
        self.assertEqual((q.p_dan, q.r_dan), (50000, 150000))

    def test_matnli_qatorlarda_narx_yoq_izoh_bor(self):
        for tartib in (38, 48):
            q = self.qator(tartib)
            self.assertEqual((q.p_dan, q.r_dan), (None, None))
            self.assertTrue(q.izoh)

    def test_har_qatorda_reviziya_profilaktikadan_qimmat(self):
        for q in self.n.qatorlar.exclude(p_dan=None):
            self.assertGreater(q.r_dan, q.p_dan, q.tartib)


class KorishTestlari(Asos):
    def test_faol_xodim_koradi(self):
        r = self.x.get(URL).json()
        self.assertEqual(len(r), 6)          # ulgurji + aholining 3 bo'limi + ikkalasining metrologiyasi
        ulgurji = [n for n in r if n['tarmoq'] == 'ulgurji' and n['bolim'] == 'profilaktika']
        self.assertEqual(len(ulgurji), 1)
        self.assertEqual(len(ulgurji[0]['qatorlar']), 49)

    def test_admin_koradi(self):
        self.assertEqual(self.a.get(URL).status_code, 200)

    def test_mijoz_nofaol_xodim_va_tokensiz_kora_olmaydi(self):
        self.assertEqual(self.m.get(URL).status_code, 403)
        self.assertEqual(self.nf.get(URL).status_code, 403)
        self.assertEqual(APIClient().get(URL).status_code, 401)

    def test_nofaol_qator_xodimga_korinmaydi_adminga_korinadi(self):
        q = self.qator(5)
        q.faol = False
        q.save()
        self.assertEqual(len(self.x.get(URL).json()[0]['qatorlar']), 48)
        self.assertEqual(len(self.a.get(URL + 'admin/').json()[0]['qatorlar']), 49)

    def test_nofaol_narxnoma_xodimga_korinmaydi(self):
        self.n.faol = False
        self.n.save()
        # ulgurji profilaktika narxnomasi yashirildi; qolgani (aholi 3 ta + ikkala metrologiya) ko'rinadi
        royxat = [(n['tarmoq'], n['bolim']) for n in self.x.get(URL).json()]
        self.assertNotIn(('ulgurji', 'profilaktika'), royxat)
        self.assertEqual(len(royxat), 5)

    def test_admin_royxati_xodimga_yopiq(self):
        self.assertEqual(self.x.get(URL + 'admin/').status_code, 403)
        self.assertEqual(self.m.get(URL + 'admin/').status_code, 403)


class TahrirTestlari(Asos):
    def test_admin_narxni_ozgartiradi_va_jurnalga_yoziladi(self):
        q = self.qator(1)
        r = self.a.patch(f'{URL}qator/{q.pk}/', {'p_dan': 250000, 'r_dan': '420 000'}, format='json')
        self.assertEqual(r.status_code, 200, r.content)
        q.refresh_from_db()
        self.assertEqual((q.p_dan, q.r_dan), (250000, 420000))
        yozuv = AuditYozuv.objects.get(amal='narx_ozgardi')
        self.assertIn('233500 → 250000', yozuv.tafsilot)

    def test_ozgarmagan_narx_jurnalga_yozilmaydi(self):
        q = self.qator(1)
        self.a.patch(f'{URL}qator/{q.pk}/', {'p_dan': q.p_dan}, format='json')
        self.assertFalse(AuditYozuv.objects.filter(amal='narx_ozgardi').exists())

    def test_notogri_narxlar_rad_etiladi(self):
        q = self.qator(1)
        for qiymat in (-1, 'abc', 1.5, True, 10**11, [1]):
            r = self.a.patch(f'{URL}qator/{q.pk}/', {'p_dan': qiymat}, format='json')
            self.assertEqual(r.status_code, 400, repr(qiymat))
        q.refresh_from_db()
        self.assertEqual(q.p_dan, 233500)

    def test_oraliq_tekshiruvi(self):
        q = self.qator(1)
        r = self.a.patch(f'{URL}qator/{q.pk}/', {'p_dan': 300000, 'p_gacha': 200000}, format='json')
        self.assertEqual(r.status_code, 400)
        r = self.a.patch(f'{URL}qator/{q.pk}/', {'p_dan': None, 'p_gacha': 200000}, format='json')
        self.assertEqual(r.status_code, 400)
        r = self.a.patch(f'{URL}qator/{q.pk}/', {'p_gacha': 300000}, format='json')
        self.assertEqual(r.status_code, 200)

    def test_narxni_bosh_qoldirish_mumkin(self):
        q = self.qator(1)
        r = self.a.patch(f'{URL}qator/{q.pk}/', {'p_dan': '', 'r_dan': None, 'izoh': 'Kelishuv asosida'},
                         format='json')
        self.assertEqual(r.status_code, 200)
        q.refresh_from_db()
        self.assertEqual((q.p_dan, q.r_dan, q.izoh), (None, None, 'Kelishuv asosida'))

    def test_nomi_bosh_bolmaydi(self):
        q = self.qator(1)
        self.assertEqual(self.a.patch(f'{URL}qator/{q.pk}/', {'nomi': '  '}, format='json').status_code, 400)
        self.assertEqual(self.a.patch(f'{URL}qator/{q.pk}/', {'nomi': 'x' * 401}, format='json').status_code, 400)

    def test_qator_ochirish_ornida_nofaol_qilinadi(self):
        q = self.qator(2)
        r = self.a.patch(f'{URL}qator/{q.pk}/', {'faol': False}, format='json')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(self.a.patch(f'{URL}qator/{q.pk}/', {'faol': 'yoq'}, format='json').status_code, 400)

    def test_yangi_qator_qoshish(self):
        r = self.a.post(f'{URL}{self.n.pk}/qator/', {'nomi': 'Yangi xizmat', 'p_dan': 100000, 'r_dan': 150000},
                        format='json')
        self.assertEqual(r.status_code, 201, r.content)
        self.assertEqual(r.json()['tartib'], 50)
        self.assertTrue(AuditYozuv.objects.filter(amal='narx_qoshildi').exists())
        self.assertEqual(self.a.post(f'{URL}{self.n.pk}/qator/', {'p_dan': 1}, format='json').status_code, 400)

    def test_sarlavhani_yangilash(self):
        r = self.a.patch(f'{URL}{self.n.pk}/', {'amal_qiladi': '2027-01-01', 'eslatma': 'Yangi eslatma'},
                         format='json')
        self.assertEqual(r.status_code, 200, r.content)
        self.n.refresh_from_db()
        self.assertEqual((str(self.n.amal_qiladi), self.n.eslatma), ('2027-01-01', 'Yangi eslatma'))
        self.assertEqual(self.a.patch(f'{URL}{self.n.pk}/', {'amal_qiladi': 'kecha'}, format='json').status_code, 400)

    def test_xodim_mijoz_va_tokensiz_ozgartira_olmaydi(self):
        q = self.qator(1)
        for c in (self.x, self.m, self.nf):
            self.assertEqual(c.patch(f'{URL}qator/{q.pk}/', {'p_dan': 1}, format='json').status_code, 403)
            self.assertEqual(c.post(f'{URL}{self.n.pk}/qator/', {'nomi': 'x'}, format='json').status_code, 403)
            self.assertEqual(c.patch(f'{URL}{self.n.pk}/', {'eslatma': 'x'}, format='json').status_code, 403)
        self.assertEqual(APIClient().patch(f'{URL}qator/{q.pk}/', {'p_dan': 1}, format='json').status_code, 401)
        q.refresh_from_db()
        self.assertEqual(q.p_dan, 233500)

    def test_mavjud_bolmagan(self):
        self.assertEqual(self.a.patch(f'{URL}qator/99999/', {'p_dan': 1}, format='json').status_code, 404)
        self.assertEqual(self.a.post(f'{URL}99999/qator/', {'nomi': 'x'}, format='json').status_code, 404)
        self.assertEqual(self.a.patch(f'{URL}99999/', {'eslatma': 'x'}, format='json').status_code, 404)
