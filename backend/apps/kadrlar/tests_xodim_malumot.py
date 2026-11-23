"""Kadrlar: xodimlar ma'lumotlari (ishga kirgan sana, tabel, sertifikatlar). Ish haqi Kadrlarda yo'q."""
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from apps.auth_app.kabinet_turlari import BOLIMLAR
from apps.auth_app.models import AuditYozuv, Foydalanuvchi, Sertifikat

URL = '/api/kadrlar/xodimlar/'


def klient(user):
    c = APIClient()
    c.credentials(HTTP_AUTHORIZATION='Bearer ' + str(RefreshToken.for_user(user).access_token))
    return c


class XodimMalumotTestlari(TestCase):
    def setUp(self):
        mk = Foydalanuvchi.objects.create
        self.kadr = mk(telefon='+998900001001', ism='Ruxsora', rol='xodim', holat='faol',
                       lavozim="Kadrlar bo'yicha mutaxassis")
        self.usta = mk(telefon='+998900001002', ism='Aziz', rol='xodim', holat='faol', lavozim='Chilangar')
        self.k = klient(self.kadr)

    def test_bolim_kadrlarda(self):
        self.assertIn('kadr-xodimlar', BOLIMLAR['kadrlar'])
        self.assertNotIn('kadr-xodimlar', BOLIMLAR['oddiy'])

    def test_royxat_va_asosiy_malumot(self):
        r = self.k.patch(f'{URL}{self.usta.pk}/', {'ishga_kirgan': '2024-03-01', 'tabel_raqam': ' T-17 '}, format='json')
        self.assertEqual(r.status_code, 200, r.content)
        self.usta.refresh_from_db()
        self.assertEqual((str(self.usta.ishga_kirgan), self.usta.tabel_raqam), ('2024-03-01', 'T-17'))
        qator = next(x for x in self.k.get(URL).json() if x['id'] == self.usta.pk)
        self.assertEqual(qator['tabel_raqam'], 'T-17')
        self.assertNotIn('oxirgi_oy', qator)
        self.assertTrue(AuditYozuv.objects.filter(amal='kadr_malumot').exists())
        # Xodim o'z kabinetida ko'radi
        self.assertEqual(klient(self.usta).get('/api/auth/xodim/profil/').json()['ishga_kirgan'], '2024-03-01')

    def test_sertifikat_qoshish_va_ochirish(self):
        r = self.k.post(f'{URL}{self.usta.pk}/sertifikat/', {'nomi': 'Gaz xavfsizligi', 'raqami': '12',
                                                             'berilgan': '2025-01-10', 'amal_qiladi': '2027-01-10'},
                        format='json')
        self.assertEqual(r.status_code, 201, r.content)
        self.assertEqual(klient(self.usta).get('/api/auth/xodim/sertifikatlar/').json()[0]['nomi'], 'Gaz xavfsizligi')
        self.assertEqual(self.k.post(f'{URL}{self.usta.pk}/sertifikat/', {'nomi': ''}, format='json').status_code, 400)
        self.assertEqual(self.k.post(f'{URL}{self.usta.pk}/sertifikat/', {'nomi': 'X', 'berilgan': '2025-05-01',
                                                                          'amal_qiladi': '2025-01-01'}, format='json').status_code, 400)
        self.assertEqual(self.k.delete(f"/api/kadrlar/sertifikat/{r.json()['id']}/").status_code, 204)
        self.assertFalse(Sertifikat.objects.exists())

    def test_ish_haqi_kadrlarda_yoq(self):
        d = self.k.get(f'{URL}{self.usta.pk}/').json()
        self.assertNotIn('ish_haqi', d)
        self.assertEqual(self.k.post(f'{URL}{self.usta.pk}/ish-haqi/', {'oy': '2026-11'}, format='json').status_code, 404)

    def test_ruxsat(self):
        u = klient(self.usta)
        self.assertEqual(u.get(URL).status_code, 403)
        self.assertEqual(u.patch(f'{URL}{self.usta.pk}/', {'tabel_raqam': '1'}, format='json').status_code, 403)
        self.assertEqual(u.post(f'{URL}{self.usta.pk}/sertifikat/', {'nomi': 'X'}, format='json').status_code, 403)
