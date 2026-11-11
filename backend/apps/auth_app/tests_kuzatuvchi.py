"""Direktor — KUZATUVCHI: API'da hamma narsani ko'radi, hech narsani o'zgartira olmaydi. Egasi (superuser) o'zgartiradi."""
from django.core.cache import cache
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from apps.auth_app.models import AuditYozuv, Foydalanuvchi
from apps.buyurtmalar.models import Buyurtma


def klient(user=None):
    c = APIClient()
    if user:
        c.credentials(HTTP_AUTHORIZATION='Bearer ' + str(RefreshToken.for_user(user).access_token))
    return c


class KuzatuvchiTestlari(TestCase):
    def setUp(self):
        cache.clear()
        mk = Foydalanuvchi.objects.create
        self.direktor = mk(telefon='+998900000801', ism='Direktor', rol='admin', holat='faol')
        self.egasi = mk(telefon='+998900000802', ism='Egasi', rol='admin', holat='faol', is_staff=True,
                        is_superuser=True)
        self.xodim = mk(telefon='+998900000803', ism='Aziz', rol='xodim', holat='faol', lavozim='Montaj ustasi',
                        kirish_kodi='XD-AAAAAA')
        self.mijoz = mk(telefon='+998900000804', ism='Karim', rol='mijoz')
        self.buyurtma = Buyurtma.objects.create(mijoz=self.mijoz, xizmat='servis', manzil='Kogon')

    def test_profilda_kuzatuvchi_belgisi(self):
        self.assertTrue(klient(self.direktor).get('/api/auth/profil/').json()['kuzatuvchi'])
        self.assertFalse(klient(self.egasi).get('/api/auth/profil/').json()['kuzatuvchi'])
        self.assertFalse(klient(self.xodim).get('/api/auth/profil/').json()['kuzatuvchi'])

    def test_direktor_hamma_narsani_koradi(self):
        c = klient(self.direktor)
        for yol in ('/api/auth/xodimlar/', '/api/auth/mijozlar/', '/api/auth/jurnal/', '/api/buyurtmalar/'):
            self.assertEqual(c.get(yol).status_code, 200, yol)

    def test_direktor_hech_narsani_ozgartira_olmaydi(self):
        c = klient(self.direktor)
        r = c.patch(f'/api/auth/xodimlar/{self.xodim.pk}/', {'holat': 'nofaol'}, format='json')
        self.assertEqual(r.status_code, 403)
        self.assertIn('faqat ko', r.json()['detail'])
        self.assertEqual(c.post('/api/auth/xodimlar/', {'telefon': '+998900000899', 'ism': 'Yangi'}, format='json').status_code, 403)
        self.assertEqual(c.patch(f'/api/buyurtmalar/{self.buyurtma.pk}/', {'holat': 'bekor'}, format='json').status_code, 403)
        self.assertEqual(c.delete(f'/api/buyurtmalar/{self.buyurtma.pk}/').status_code, 403)
        self.assertEqual(c.post(f'/api/buyurtmalar/{self.buyurtma.pk}/tayinlash/', {'xodim_id': self.xodim.pk}, format='json').status_code, 403)
        self.xodim.refresh_from_db()
        self.buyurtma.refresh_from_db()
        self.assertEqual((self.xodim.holat, self.buyurtma.holat, self.buyurtma.xodim), ('faol', 'yangi', None))

    def test_egasi_ozgartira_oladi(self):
        r = klient(self.egasi).patch(f'/api/auth/xodimlar/{self.xodim.pk}/', {'holat': 'nofaol'}, format='json')
        self.assertEqual(r.status_code, 200, r.content)
        self.xodim.refresh_from_db()
        self.assertEqual(self.xodim.holat, 'nofaol')

    def test_kirish_va_token_yangilash_bloklanmaydi(self):
        """Kirish bosqichlari hech narsani o'zgartirmaydi — eski token yuborilsa ham kuzatuvchi xabari chiqmasligi kerak."""
        c = klient(self.direktor)
        r = c.post('/api/auth/admin/login/', {'telefon': self.direktor.telefon, 'parol': 'xato'}, format='json')
        self.assertNotIn('Kuzatuvchi', str(r.content))
        refresh = str(RefreshToken.for_user(self.direktor))
        r = c.post('/api/auth/token/yangilash/', {'refresh': refresh}, format='json')
        self.assertEqual(r.status_code, 200, r.content)

    def test_urinish_jurnalga_yoziladi_va_toshib_ketmaydi(self):
        c = klient(self.direktor)
        for _ in range(4):
            c.patch(f'/api/auth/xodimlar/{self.xodim.pk}/', {'holat': 'nofaol'}, format='json')
        y = AuditYozuv.objects.filter(amal='korish_rad', kim=self.direktor)
        self.assertEqual(y.count(), 1)
        self.assertIn('Kuzatuvchi', y.get().tafsilot)

    def test_xodim_va_mijoz_qoidasi_ozgarmagan(self):
        """Kuzatuvchi qoidasi faqat admin roli uchun: xodimlar o'z ishini (masalan smena) bajarishda davom etadi."""
        c = klient(self.xodim)
        self.assertNotEqual(c.post('/api/auth/xodimlar/', {'telefon': '+998900000898'}, format='json').status_code, 200)
        r = klient(self.mijoz).post('/api/buyurtmalar/', {'xizmat': 'servis', 'manzil': 'Kogon'}, format='json')
        self.assertNotIn('Kuzatuvchi', str(r.content))
