"""Metrolog: muddatli hisoblagichlar ro'yxati va qiyoslov natijasini kiritish."""
import datetime

from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from apps.auth_app.kabinet_turlari import kabinet_malumoti
from apps.auth_app.models import Foydalanuvchi
from .models import Bildirishnoma, Hisoblagich, Obyekt, QiyoslovYozuvi

URL = '/api/kabinet/metrolog/hisoblagichlar/'


def klient(user):
    c = APIClient()
    c.credentials(HTTP_AUTHORIZATION='Bearer ' + str(RefreshToken.for_user(user).access_token))
    return c


class MetrologTestlari(TestCase):
    def setUp(self):
        mk = Foydalanuvchi.objects.create
        self.metrolog = mk(telefon='+998900000901', ism='Vali', rol='xodim', holat='faol', lavozim='Metrolog')
        self.usta = mk(telefon='+998900000902', ism='Aziz', rol='xodim', holat='faol', lavozim='Chilangar')
        self.mijoz = mk(telefon='+998900000903', ism='Karim', rol='mijoz')
        o = Obyekt.objects.create(mijoz=self.mijoz, nom='Uy', manzil='Navoiy 5', tuman='Kogon')
        bugun = timezone.localdate()
        self.otgan = Hisoblagich.objects.create(obyekt=o, seriya_raqam='A-1', keyingi_tekshiruv=bugun - datetime.timedelta(days=5))
        self.yaqin = Hisoblagich.objects.create(obyekt=o, seriya_raqam='B-2', keyingi_tekshiruv=bugun + datetime.timedelta(days=10))
        self.uzoq = Hisoblagich.objects.create(obyekt=o, seriya_raqam='C-3', keyingi_tekshiruv=bugun + datetime.timedelta(days=400))
        self.m = klient(self.metrolog)

    def test_menyu_faqat_metrologda(self):
        self.assertIn('metr-hisob', kabinet_malumoti('Metrolog')['bolimlar'])
        self.assertNotIn('metr-hisob', kabinet_malumoti('Chilangar')['bolimlar'])

    def test_royxat_va_xulosa(self):
        d = self.m.get(URL).json()
        self.assertEqual([h['seriya_raqam'] for h in d['hisoblagichlar']], ['A-1', 'B-2'])
        self.assertEqual((d['xulosa']['otgan'], d['xulosa']['yaqin'], d['xulosa']['jami']), (1, 1, 3))
        self.assertEqual(d['hisoblagichlar'][0]['mijoz']['telefon'], '+998900000903')
        self.assertEqual(len(self.m.get(URL, {'holat': 'hammasi'}).json()['hisoblagichlar']), 3)
        self.assertEqual([h['seriya_raqam'] for h in self.m.get(URL, {'holat': 'hammasi', 'q': 'C-3'}).json()['hisoblagichlar']], ['C-3'])

    def test_ruxsat(self):
        self.assertEqual(klient(self.usta).get(URL).status_code, 403)
        self.assertEqual(klient(self.mijoz).get(URL).status_code, 403)
        self.assertEqual(APIClient().get(URL).status_code, 401)

    def test_qiyoslov_yaroqli(self):
        bugun = timezone.localdate()
        keyingi = bugun + datetime.timedelta(days=365 * 4)
        r = self.m.post(f'{URL}{self.otgan.pk}/qiyoslov/', {'sana': bugun.isoformat(), 'natija': 'yaroqli',
                                                            'keyingi_tekshiruv': keyingi.isoformat()}, format='json')
        self.assertEqual(r.status_code, 201, r.content)
        self.otgan.refresh_from_db()
        self.assertEqual((self.otgan.oxirgi_tekshiruv, self.otgan.keyingi_tekshiruv, self.otgan.holat), (bugun, keyingi, 'faol'))
        self.assertEqual(QiyoslovYozuvi.objects.get().metrolog, self.metrolog)
        self.assertTrue(Bildirishnoma.objects.filter(mijoz=self.mijoz, matn__contains="qiyoslovdan o'tdi").exists())

    def test_qiyoslov_yaroqsiz_va_xatolar(self):
        r = self.m.post(f'{URL}{self.yaqin.pk}/qiyoslov/', {'natija': 'yaroqsiz'}, format='json')
        self.assertEqual(r.status_code, 201, r.content)
        self.yaqin.refresh_from_db()
        self.assertEqual((self.yaqin.holat, self.yaqin.keyingi_tekshiruv), ('nosoz', None))
        self.assertEqual(self.m.post(f'{URL}{self.otgan.pk}/qiyoslov/', {'natija': 'yaroqli'}, format='json').status_code, 400)
        ertaga = (timezone.localdate() + datetime.timedelta(days=1)).isoformat()
        self.assertEqual(self.m.post(f'{URL}{self.otgan.pk}/qiyoslov/', {'natija': 'yaroqsiz', 'sana': ertaga}, format='json').status_code, 400)
        self.assertEqual(klient(self.usta).post(f'{URL}{self.otgan.pk}/qiyoslov/', {'natija': 'yaroqsiz'}, format='json').status_code, 403)
