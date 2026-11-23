"""Seshanba aksiyasi: navbatdagi 2 ta xizmatga promokod bilan 5% chegirma (faqat seshanba)."""
import datetime
from unittest import mock

from django.test import TestCase, override_settings
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from apps.auth_app.models import Foydalanuvchi
from apps.narxnoma.models import NarxnomaQator, SeshanbaAksiya, seshanba_aksiyasi
from .models import Buyurtma

URL = '/api/buyurtmalar/'
SESHANBA = datetime.date(2026, 11, 24)        # navbat shu kundan boshlanadi


def klient(user):
    c = APIClient()
    c.credentials(HTTP_AUTHORIZATION='Bearer ' + str(RefreshToken.for_user(user).access_token))
    return c


def vaqt(sana, soat=12, daqiqa=0):
    from django.utils import timezone
    t = timezone.make_aware(datetime.datetime.combine(sana, datetime.time(soat, daqiqa)))
    return mock.patch('django.utils.timezone.now', return_value=t)


def kun(sana):
    return vaqt(sana)


@override_settings(SESHANBA_PROMOKOD='SESHANBA', SESHANBA_FOIZ=5)
class SeshanbaTestlari(TestCase):
    def setUp(self):
        self.mijoz = Foydalanuvchi.objects.create(telefon='+998901112266', ism='Karim', rol='mijoz')
        self.xodim = Foydalanuvchi.objects.create(telefon='+998900000081', ism='Ali', rol='xodim', holat='faol')
        self.m, self.x = klient(self.mijoz), klient(self.xodim)
        q = list(NarxnomaQator.objects.filter(narxnoma__tarmoq='aholi', narxnoma__bolim='profilaktika',
                                              faol=True, p_dan__isnull=False).order_by('tartib')[:4])
        self.q1, self.q2, self.q3, self.q4 = q
        self.a1 = SeshanbaAksiya.objects.create(tartib=1, xizmat1=self.q1, xizmat2=self.q2)
        self.a2 = SeshanbaAksiya.objects.create(tartib=2, xizmat1=self.q3, xizmat2=self.q4)

    def ariza(self, promokod, *qatorlar):
        return self.m.post(URL, {'xizmat': 'servis', 'promokod': promokod,
                                 'xizmatlar': [{'qator': q.pk, 'ustun': 'p', 'soni': 1} for q in qatorlar]},
                           format='json')

    def test_navbat_haftama_hafta_almashadi(self):
        self.assertEqual(seshanba_aksiyasi(SESHANBA), self.a1)
        self.assertEqual(seshanba_aksiyasi(SESHANBA + datetime.timedelta(weeks=1)), self.a2)
        self.assertEqual(seshanba_aksiyasi(SESHANBA + datetime.timedelta(weeks=2)), self.a1)
        self.assertIsNone(seshanba_aksiyasi(SESHANBA + datetime.timedelta(days=1)))   # chorshanba

    def test_seshanba_promokod_faqat_aksiya_xizmatiga_chegirma(self):
        with kun(SESHANBA):
            r = self.ariza('seshanba', self.q1, self.q3)
        self.assertEqual(r.status_code, 201, r.content)
        b = Buyurtma.objects.get()
        self.assertEqual((b.promokod, b.chegirma_foiz), ('SESHANBA', 5))
        x1 = b.xizmatlar.get(qator=self.q1)
        x3 = b.xizmatlar.get(qator=self.q3)
        self.assertEqual(x1.narx_dan, (self.q1.p_dan * 95 + 50) // 100)
        self.assertEqual(x1.chegirma_foiz, 5)
        self.assertEqual((x3.narx_dan, x3.chegirma_foiz), (self.q3.p_dan, 0))   # bu hafta aksiyada emas

    def test_usta_keyin_qoshgan_aksiya_xizmatiga_ham_chegirma(self):
        with kun(SESHANBA):
            b = Buyurtma.objects.get(pk=self.ariza('SESHANBA').json()['id'])
        b.xodim = self.xodim
        b.save()
        r = self.x.post(f'{URL}{b.pk}/xizmatlar/', {'xizmatlar': [{'qator': self.q2.pk, 'ustun': 'p', 'soni': 2}]},
                        format='json')
        self.assertEqual(r.status_code, 201, r.content)
        self.assertEqual(r.json()['jami_dan'], (self.q2.p_dan * 95 + 50) // 100 * 2)

    def test_50_soat_payshanba_0200_gacha(self):
        with vaqt(SESHANBA + datetime.timedelta(days=1), 23, 30):          # chorshanba kechqurun — amalda
            self.assertEqual(self.ariza('SESHANBA', self.q1).status_code, 201)
        with vaqt(SESHANBA + datetime.timedelta(days=2), 1, 59):           # payshanba 01:59 — amalda
            self.assertEqual(self.ariza('SESHANBA', self.q1).status_code, 201)
        with vaqt(SESHANBA + datetime.timedelta(days=2), 2, 0):            # payshanba 02:00 — tugagan
            self.assertEqual(self.ariza('SESHANBA', self.q1).status_code, 400)
        with vaqt(SESHANBA - datetime.timedelta(days=1), 23, 59):          # dushanba — hali boshlanmagan
            self.assertEqual(self.ariza('SESHANBA', self.q1).status_code, 400)
        with vaqt(SESHANBA + datetime.timedelta(days=1)):
            d = APIClient().get('/api/narxnoma/seshanba/').json()
        self.assertEqual((d['bugun'], d['promokod']), (True, 'SESHANBA'))
        self.assertTrue(d['tugash'].startswith('2026-11-26T02:00:00'))

    def test_boshqa_kunda_yoki_notogri_kod_rad(self):
        with kun(SESHANBA + datetime.timedelta(days=3)):                   # juma
            self.assertEqual(self.ariza('SESHANBA', self.q1).status_code, 400)
        with kun(SESHANBA):
            self.assertEqual(self.ariza('BOSHQA', self.q1).status_code, 400)
        self.assertFalse(Buyurtma.objects.exists())

    def test_promokodsiz_chegirma_yoq(self):
        with kun(SESHANBA):
            r = self.ariza('', self.q1)
        self.assertEqual(r.status_code, 201, r.content)
        self.assertEqual(Buyurtma.objects.get().xizmatlar.get().narx_dan, self.q1.p_dan)

    def test_ochiq_malumot_promokod_faqat_seshanba(self):
        with kun(SESHANBA - datetime.timedelta(days=2)):        # yakshanba
            d = APIClient().get('/api/narxnoma/seshanba/').json()
        self.assertTrue(d['bor'])
        self.assertFalse(d['bugun'])
        self.assertIsNone(d['promokod'])
        self.assertEqual([x['id'] for x in d['xizmatlar']], [self.q1.pk, self.q2.pk])
        self.assertIn(self.q1.pk, d['idlar'])
        with kun(SESHANBA):
            d = APIClient().get('/api/narxnoma/seshanba/').json()
        self.assertEqual((d['bugun'], d['promokod'], d['foiz']), (True, 'SESHANBA', 5))

    def test_shu_nomdagi_boshqa_narxnoma_qatoriga_ham_chegirma(self):
        egizak = NarxnomaQator.objects.filter(nomi__iexact=self.q1.nomi, faol=True, p_dan__isnull=False,
                                              narxnoma__tarmoq='aholi').exclude(pk=self.q1.pk).first()
        if egizak is None:
            self.skipTest("Narxnomada bir xil nomli qator yo'q")
        with kun(SESHANBA):
            r = self.ariza('SESHANBA', egizak)
        self.assertEqual(r.status_code, 201, r.content)
        self.assertEqual(Buyurtma.objects.get().xizmatlar.get().chegirma_foiz, 5)

    def test_ornatish_narxnomasidagi_shu_nomli_qatorga_chegirma_yoq(self):
        ornatish = NarxnomaQator.objects.filter(narxnoma__bolim='ornatish', faol=True).first()
        if ornatish is None:
            self.skipTest("O'rnatish narxnomasi yo'q")
        a = SeshanbaAksiya.objects.create(tartib=9, xizmat1=self.q1, xizmat2=self.q2)
        ornatish.nomi = self.q1.nomi
        ornatish.save()
        self.assertNotIn(ornatish.pk, a.qator_idlari())
        self.assertIn(self.q1.pk, a.qator_idlari())

    def test_navbat_bosh_bolsa_aksiya_yoq(self):
        SeshanbaAksiya.objects.all().delete()
        with kun(SESHANBA):
            self.assertFalse(APIClient().get('/api/narxnoma/seshanba/').json()['bor'])
            self.assertEqual(self.ariza('SESHANBA', self.q1).status_code, 400)
