"""Buyurtmadagi mijoz aloqasi (ism, telefon, manzil): saqlanishi va ko'rinishi."""
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from apps.auth_app.models import Foydalanuvchi
from .models import Buyurtma
from .serializers import telefon_tozala

URL = '/api/buyurtmalar/'


def klient(user):
    c = APIClient()
    c.credentials(HTTP_AUTHORIZATION='Bearer ' + str(RefreshToken.for_user(user).access_token))
    return c


class MijozAloqaTestlari(TestCase):
    def setUp(self):
        self.mijoz = Foydalanuvchi.objects.create(
            telefon='+998901112233', ism='Karim', rol='mijoz',
            manzil='Chilonzor 5', tuman='Chilonzor tumani')
        self.xodim = Foydalanuvchi.objects.create(
            telefon='+998900000041', ism='Ali', rol='xodim', holat='faol')
        self.admin = Foydalanuvchi.objects.create(
            telefon='+998900000042', ism='Admin', rol='admin', holat='faol', is_superuser=True)
        self.m = klient(self.mijoz)

    def test_profil_ism_va_telefoni_buyurtmaga_yoziladi(self):
        r = self.m.post(URL, {'xizmat': 'montaj'}, format='json')
        self.assertEqual(r.status_code, 201, r.content)
        b = Buyurtma.objects.get()
        self.assertEqual((b.mijoz_ism, b.mijoz_telefon, b.manzil),
                         ('Karim', '+998901112233', 'Chilonzor 5'))
        j = r.json()
        self.assertEqual((j['mijoz_ism'], j['mijoz_telefon']), ('Karim', '+998901112233'))

    def test_mijoz_boshqa_aloqa_va_manzil_korsatishi_mumkin(self):
        r = self.m.post(URL, {'xizmat': 'servis', 'mijoz_ism': 'Rahim aka',
                              'mijoz_telefon': '90 123-45-67', 'manzil': 'Yunusobod 3'},
                        format='json')
        self.assertEqual(r.status_code, 201, r.content)
        b = Buyurtma.objects.get()
        self.assertEqual((b.mijoz_ism, b.mijoz_telefon, b.manzil),
                         ('Rahim aka', '+998901234567', 'Yunusobod 3'))
        # profil o'zgarmaydi
        self.mijoz.refresh_from_db()
        self.assertEqual(self.mijoz.telefon, '+998901112233')

    def test_notogri_telefon_rad_etiladi(self):
        for tel in ('abc', '12', '+99890123456789012', '90-12x'):
            r = self.m.post(URL, {'xizmat': 'montaj', 'mijoz_telefon': tel}, format='json')
            self.assertEqual(r.status_code, 400, tel)
        self.assertFalse(Buyurtma.objects.exists())

    def test_profil_ozgarsa_eski_buyurtmadagi_raqam_qoladi(self):
        self.m.post(URL, {'xizmat': 'montaj'}, format='json')
        self.mijoz.telefon = '+998909999999'
        self.mijoz.ism = 'Yangi ism'
        self.mijoz.save()
        b = klient(self.xodim)
        Buyurtma.objects.update(xodim=self.xodim)
        j = b.get(URL).json()[0]
        self.assertEqual(j['mijoz_malumot']['telefon'], '+998901112233')
        self.assertEqual(j['mijoz_malumot']['ism'], 'Karim')

    def test_xodim_va_admin_aloqani_koradi(self):
        self.m.post(URL, {'xizmat': 'montaj'}, format='json')
        Buyurtma.objects.update(xodim=self.xodim)
        for c in (klient(self.xodim), klient(self.admin)):
            mm = c.get(URL).json()[0]['mijoz_malumot']
            self.assertEqual((mm['ism'], mm['telefon'], mm['manzil']),
                             ('Karim', '+998901112233', 'Chilonzor 5'))

    def test_hisobsiz_buyurtmada_aloqa_korinadi(self):
        # Mijoz hisobi bog'lanmagan buyurtma (masalan, operator kiritgan):
        # aloqa buyurtmaning o'zidagi maydonlardan olinadi
        Buyurtma.objects.create(xizmat='servis', mijoz_ism='Mehmon',
                                mijoz_telefon='+998907777777', manzil='Qo\'qon')
        j = klient(self.admin).get(URL).json()
        self.assertEqual(j[0]['mijoz_malumot']['telefon'], '+998907777777')

    def test_boshqa_xodimning_buyurtma_aloqasi_korinmaydi(self):
        self.m.post(URL, {'xizmat': 'montaj'}, format='json')   # xodimga tayinlanmagan
        self.assertEqual(klient(self.xodim).get(URL).json(), [])


class TelefonTozalaTestlari(TestCase):
    def test_shakllar(self):
        for kirish, chiqish in [('901234567', '+998901234567'),
                                ('+998 90 123 45 67', '+998901234567'),
                                ('998901234567', '+998901234567'),
                                ('(90) 123-45-67', '+998901234567'),
                                ('', ''), (None, '')]:
            self.assertEqual(telefon_tozala(kirish), chiqish, kirish)
