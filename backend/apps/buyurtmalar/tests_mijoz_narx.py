"""Mijoz ariza berishda: narxnomadan xizmat tanlash, taxminiy narx va to'lov usuli."""
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from apps.auth_app.models import Foydalanuvchi
from apps.narxnoma.models import NarxnomaQator
from .models import Buyurtma, BuyurtmaXizmat

URL = '/api/buyurtmalar/'
NARX_URL = '/api/narxnoma/mijoz/'


def klient(user):
    c = APIClient()
    c.credentials(HTTP_AUTHORIZATION='Bearer ' + str(RefreshToken.for_user(user).access_token))
    return c


class MijozNarxTestlari(TestCase):
    def setUp(self):
        mk = Foydalanuvchi.objects.create
        self.mijoz = mk(telefon='+998901112244', ism='Karim', rol='mijoz')
        self.korxona = mk(telefon='+998901112255', ism='MChJ', rol='mijoz', mulk_turi='korxona')
        self.xodim = mk(telefon='+998900000071', ism='Ali', rol='xodim', holat='faol')
        self.m, self.k, self.x = klient(self.mijoz), klient(self.korxona), klient(self.xodim)
        self.aholi_q = NarxnomaQator.objects.filter(narxnoma__tarmoq='aholi', narxnoma__bolim='profilaktika',
                                                    faol=True, p_dan__isnull=False).order_by('tartib').first()
        self.ulgurji_q = NarxnomaQator.objects.filter(narxnoma__tarmoq='ulgurji', narxnoma__bolim='profilaktika',
                                                      faol=True, p_dan__isnull=False).order_by('tartib').first()

    def test_narxlar_mijoz_tarmogida(self):
        r = self.m.get(NARX_URL, {'xizmat': 'servis'})
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(r.json()['tarmoq'], 'aholi')
        idlar = {q['id'] for n in r.json()['narxnomalar'] for q in n['qatorlar']}
        self.assertIn(self.aholi_q.pk, idlar)
        self.assertNotIn(self.ulgurji_q.pk, idlar)
        r = self.k.get(NARX_URL, {'xizmat': 'servis'})
        self.assertEqual(r.json()['tarmoq'], 'ulgurji')

    def test_narxlar_kirishsiz_va_notogri_xizmat(self):
        self.assertEqual(APIClient().get(NARX_URL, {'xizmat': 'servis'}).status_code, 401)
        self.assertEqual(self.m.get(NARX_URL, {'xizmat': 'xyz'}).status_code, 400)

    def test_ariza_xizmat_va_tolov_usuli_bilan(self):
        r = self.m.post(URL, {'xizmat': 'servis', 'tolov_usuli': 'naqd',
                              'xizmatlar': [{'qator': self.aholi_q.pk, 'ustun': 'p', 'soni': 2}]}, format='json')
        self.assertEqual(r.status_code, 201, r.content)
        b = Buyurtma.objects.get()
        self.assertEqual(b.tolov_usuli, 'naqd')
        x = BuyurtmaXizmat.objects.get(buyurtma=b)
        self.assertEqual((x.soni, x.narx_dan, x.qoshgan_id), (2, self.aholi_q.p_dan, self.mijoz.pk))
        # Mijoz o'z buyurtmasida tanlagan xizmatlar va taxminiy narxni ko'radi
        t = r.json()['tanlangan']
        self.assertEqual(t['jami_dan'], self.aholi_q.p_dan * 2)
        # Usta ham shu xizmatlarni o'z vazifasida ko'radi
        b.xodim = self.xodim
        b.save()
        v = self.x.get(URL).json()[0]
        self.assertEqual(len(v['xizmatlar']['royxat']), 1)
        self.assertEqual(v['tolov_usuli'], 'naqd')

    def test_boshqa_tarmoq_narxi_rad_va_buyurtma_yaratilmaydi(self):
        r = self.m.post(URL, {'xizmat': 'servis',
                              'xizmatlar': [{'qator': self.ulgurji_q.pk, 'ustun': 'p', 'soni': 1}]}, format='json')
        self.assertEqual(r.status_code, 400, r.content)
        self.assertFalse(Buyurtma.objects.exists())

    def test_notogri_tolov_usuli(self):
        r = self.m.post(URL, {'xizmat': 'servis', 'tolov_usuli': 'kripto'}, format='json')
        self.assertEqual(r.status_code, 400)
        self.assertFalse(Buyurtma.objects.exists())

    def test_xizmatsiz_ariza_avvalgidek(self):
        r = self.m.post(URL, {'xizmat': 'montaj'}, format='json')
        self.assertEqual(r.status_code, 201, r.content)
        self.assertIsNone(r.json()['tanlangan'])
        self.assertEqual(r.json()['tolov_usuli'], '')

    def test_usta_qoshgan_xizmat_mijozning_tanlovida_chiqmaydi(self):
        r = self.m.post(URL, {'xizmat': 'servis',
                              'xizmatlar': [{'qator': self.aholi_q.pk, 'ustun': 'p', 'soni': 1}]}, format='json')
        b = Buyurtma.objects.get(pk=r.json()['id'])
        b.xodim = self.xodim
        b.save()
        boshqa = NarxnomaQator.objects.filter(narxnoma__tarmoq='aholi', faol=True, p_dan__isnull=False
                                              ).exclude(pk=self.aholi_q.pk).first()
        r = self.x.post(f'{URL}{b.pk}/xizmatlar/', {'xizmatlar': [{'qator': boshqa.pk, 'ustun': 'p', 'soni': 1}]},
                        format='json')
        self.assertEqual(r.status_code, 201, r.content)
        t = self.m.get(f'/api/kabinet/buyurtmalar/{b.pk}/').json()['tanlangan']
        self.assertEqual([x['nomi'] for x in t['royxat']], [self.aholi_q.nomi])
