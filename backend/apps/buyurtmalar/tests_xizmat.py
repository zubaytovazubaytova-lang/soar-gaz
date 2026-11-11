"""Narxnomadan xizmat tanlash, narxni hisoblash va summani tasdiqlash."""
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from apps.auth_app.models import AuditYozuv, Foydalanuvchi
from apps.narxnoma.models import NarxnomaQator
from .models import Buyurtma

URL = '/api/buyurtmalar/'


def klient(user):
    c = APIClient()
    c.credentials(HTTP_AUTHORIZATION='Bearer ' + str(RefreshToken.for_user(user).access_token))
    return c


class XizmatVaSummaTestlari(TestCase):
    def setUp(self):
        mk = Foydalanuvchi.objects.create
        self.mijoz = mk(telefon='+998901112233', ism='Karim', rol='mijoz')
        self.xodim = mk(telefon='+998900000061', ism='Ali', rol='xodim', holat='faol')
        self.boshqa = mk(telefon='+998900000062', ism='Vali', rol='xodim', holat='faol')
        self.admin = mk(telefon='+998900000063', ism='Admin', rol='admin', holat='faol', is_superuser=True)
        # Testdagi narxnoma qatorlari ulgurji narxnomadan, shuning uchun buyurtma ham ulgurji
        self.b = Buyurtma.objects.create(mijoz=self.mijoz, xodim=self.xodim, xizmat='servis',
                                         tarmoq='ulgurji')
        self.x, self.v, self.a, self.m = (klient(self.xodim), klient(self.boshqa),
                                          klient(self.admin), klient(self.mijoz))
        self.q1 = NarxnomaQator.objects.get(narxnoma__tarmoq='ulgurji', narxnoma__bolim='profilaktika', tartib=1)     # 233 500 / 389 200
        self.q13 = NarxnomaQator.objects.get(narxnoma__tarmoq='ulgurji', narxnoma__bolim='profilaktika', tartib=13)   # 210 000–330 000 / 350 000–550 000
        self.q38 = NarxnomaQator.objects.get(narxnoma__tarmoq='ulgurji', narxnoma__bolim='profilaktika', tartib=38)   # narxsiz (matn)
        self.url = f'{URL}{self.b.pk}/xizmatlar/'
        self.summa_url = f'{URL}{self.b.pk}/summa/'

    def biriktir(self, *elementlar, client=None):
        return (client or self.x).post(self.url, {'xizmatlar': list(elementlar)}, format='json')

    def test_biriktirish_va_jami(self):
        r = self.biriktir({'qator': self.q1.pk, 'ustun': 'p', 'soni': 2},
                          {'qator': self.q13.pk, 'ustun': 'r', 'soni': 1})
        self.assertEqual(r.status_code, 201, r.content)
        j = r.json()
        self.assertEqual(j['jami_dan'], 233500 * 2 + 350000)
        self.assertEqual(j['jami_gacha'], 233500 * 2 + 550000)
        self.assertEqual(len(j['royxat']), 2)
        self.assertIsNone(j['tasdiq_summa'])

    def test_qayta_biriktirish_sonni_yangilaydi(self):
        self.biriktir({'qator': self.q1.pk, 'ustun': 'p', 'soni': 1})
        r = self.biriktir({'qator': self.q1.pk, 'ustun': 'p', 'soni': 3})
        self.assertEqual(len(r.json()['royxat']), 1)
        self.assertEqual(r.json()['royxat'][0]['soni'], 3)

    def test_narx_biriktirilgan_paytdagi_qiymatda_qoladi(self):
        self.biriktir({'qator': self.q1.pk, 'ustun': 'p', 'soni': 1})
        self.q1.p_dan = 999999
        self.q1.save()
        royxat = self.x.get(URL).json()[0]['xizmatlar']
        self.assertEqual(royxat['jami_dan'], 233500)

    def test_notogri_tanlov(self):
        yaroqsiz = [
            {'qator': self.q1.pk, 'ustun': 'x', 'soni': 1},
            {'qator': self.q1.pk, 'ustun': 'p', 'soni': 0},
            {'qator': self.q1.pk, 'ustun': 'p', 'soni': 1000},
            {'qator': self.q1.pk, 'ustun': 'p', 'soni': True},
            {'qator': self.q1.pk, 'ustun': 'p', 'soni': '2'},
            {'qator': 'abc', 'ustun': 'p', 'soni': 1},
            {'qator': 99999, 'ustun': 'p', 'soni': 1},
            {'qator': self.q38.pk, 'ustun': 'p', 'soni': 1},     # narxi yo'q (matn)
            'matn',
        ]
        for el in yaroqsiz:
            self.assertEqual(self.biriktir(el).status_code, 400, el)
        self.assertEqual(self.x.post(self.url, {'xizmatlar': []}, format='json').status_code, 400)
        self.assertEqual(self.x.post(self.url, {}, format='json').status_code, 400)
        self.assertFalse(self.b.xizmatlar.exists())

    def test_nofaol_qator_biriktirilmaydi(self):
        self.q1.faol = False
        self.q1.save()
        self.assertEqual(self.biriktir({'qator': self.q1.pk, 'ustun': 'p', 'soni': 1}).status_code, 400)

    def test_boshqa_xodim_va_mijoz_biriktira_olmaydi(self):
        el = {'qator': self.q1.pk, 'ustun': 'p', 'soni': 1}
        self.assertEqual(self.biriktir(el, client=self.v).status_code, 403)
        self.assertEqual(self.biriktir(el, client=self.m).status_code, 403)
        self.assertEqual(self.biriktir(el, client=APIClient()).status_code, 401)
        self.assertFalse(self.b.xizmatlar.exists())

    def test_admin_biriktira_oladi(self):
        self.assertEqual(
            self.biriktir({'qator': self.q1.pk, 'ustun': 'r', 'soni': 1}, client=self.a).status_code, 201)

    def test_yakunlangan_buyurtmaga_xodim_biriktira_olmaydi(self):
        Buyurtma.objects.filter(pk=self.b.pk).update(holat='bajarildi')
        self.assertEqual(self.biriktir({'qator': self.q1.pk, 'ustun': 'p', 'soni': 1}).status_code, 409)

    def test_olib_tashlash(self):
        self.biriktir({'qator': self.q1.pk, 'ustun': 'p', 'soni': 1})
        xid = self.b.xizmatlar.get().pk
        self.assertEqual(self.v.delete(f'{URL}xizmatlar/{xid}/').status_code, 403)
        r = self.x.delete(f'{URL}xizmatlar/{xid}/')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()['royxat'], [])
        self.assertEqual(self.x.delete(f'{URL}xizmatlar/{xid}/').status_code, 404)

    # ----- summani tasdiqlash -----

    def test_xizmatsiz_summa_tasdiqlanmaydi(self):
        r = self.x.post(self.summa_url, {'summa': 100000}, format='json')
        self.assertEqual(r.status_code, 400)
        self.assertIn('xizmatlarni', r.json()['detail'])

    def test_aniq_narxda_faqat_shu_summa(self):
        self.biriktir({'qator': self.q1.pk, 'ustun': 'p', 'soni': 2})       # 467 000
        for noto in (466999, 467001, 0, -5, 'abc', 1.5, True, None):
            self.assertEqual(self.x.post(self.summa_url, {'summa': noto}, format='json').status_code, 400, noto)
        r = self.x.post(self.summa_url, {'summa': '467 000'}, format='json')
        self.assertEqual(r.status_code, 200, r.content)
        self.b.refresh_from_db()
        self.assertEqual((self.b.tasdiq_summa, self.b.tasdiq_kim), (467000, self.xodim))
        self.assertIsNotNone(self.b.tasdiq_vaqt)

    def test_oraliq_narxda_summa_oraliqda(self):
        self.biriktir({'qator': self.q13.pk, 'ustun': 'p', 'soni': 1})      # 210 000–330 000
        self.assertEqual(self.x.post(self.summa_url, {'summa': 209999}, format='json').status_code, 400)
        self.assertEqual(self.x.post(self.summa_url, {'summa': 330001}, format='json').status_code, 400)
        self.assertEqual(self.x.post(self.summa_url, {'summa': 275000}, format='json').status_code, 200)

    def test_tasdiqlangandan_keyin_xodim_ozgartira_olmaydi(self):
        self.biriktir({'qator': self.q1.pk, 'ustun': 'p', 'soni': 1})
        self.x.post(self.summa_url, {'summa': 233500}, format='json')
        self.assertEqual(self.x.post(self.summa_url, {'summa': 233500}, format='json').status_code, 409)
        self.assertEqual(self.biriktir({'qator': self.q13.pk, 'ustun': 'p', 'soni': 1}).status_code, 409)
        xid = self.b.xizmatlar.get().pk
        self.assertEqual(self.x.delete(f'{URL}xizmatlar/{xid}/').status_code, 409)

    def test_admin_summani_ozgartira_va_bekor_qila_oladi(self):
        self.biriktir({'qator': self.q1.pk, 'ustun': 'p', 'soni': 1})
        self.x.post(self.summa_url, {'summa': 233500}, format='json')
        self.assertEqual(self.a.post(self.summa_url, {'summa': 200000}, format='json').status_code, 200)
        self.b.refresh_from_db()
        self.assertEqual((self.b.tasdiq_summa, self.b.tasdiq_kim), (200000, self.admin))
        # admin xizmatsiz buyurtmaga ham summa kirita oladi
        b2 = Buyurtma.objects.create(mijoz=self.mijoz, xodim=self.xodim, xizmat='montaj')
        self.assertEqual(self.a.post(f'{URL}{b2.pk}/summa/', {'summa': 50000}, format='json').status_code, 200)
        # xodim bekor qila olmaydi, admin qila oladi
        self.assertEqual(self.x.delete(self.summa_url).status_code, 403)
        self.assertEqual(self.a.delete(self.summa_url).status_code, 200)
        self.b.refresh_from_db()
        self.assertIsNone(self.b.tasdiq_summa)

    def test_boshqa_xodim_va_mijoz_summa_tasdiqlay_olmaydi(self):
        self.biriktir({'qator': self.q1.pk, 'ustun': 'p', 'soni': 1})
        for c in (self.v, self.m):
            self.assertEqual(c.post(self.summa_url, {'summa': 233500}, format='json').status_code, 403)
        self.b.refresh_from_db()
        self.assertIsNone(self.b.tasdiq_summa)

    def test_jurnalga_yoziladi(self):
        self.biriktir({'qator': self.q1.pk, 'ustun': 'p', 'soni': 1})
        self.x.post(self.summa_url, {'summa': 233500}, format='json')
        self.assertEqual(AuditYozuv.objects.filter(amal='buyurtma_xizmat').count(), 1)
        self.assertEqual(AuditYozuv.objects.filter(amal='buyurtma_summa').count(), 1)

    # ----- ichki narxlar kimga ko'rinadi -----

    def test_royxatda_xodim_va_admin_xizmatlarni_koradi_mijoz_yoq(self):
        self.biriktir({'qator': self.q1.pk, 'ustun': 'p', 'soni': 1})
        self.assertEqual(self.x.get(URL).json()[0]['xizmatlar']['jami_dan'], 233500)
        self.assertEqual(self.a.get(URL).json()[0]['xizmatlar']['jami_dan'], 233500)
        mijoz_royxati = self.m.get(URL).json()
        self.assertEqual(len(mijoz_royxati), 1)
        self.assertIsNone(mijoz_royxati[0]['xizmatlar'])
        self.assertNotIn('233500', str(mijoz_royxati[0]))
