"""Buyurtma raqamini bilish egalik dalili emas: shaxsiy ma'lumot niqoblanadi,
o'zgartiruvchi amallar (to'lov usuli, qayta yetkazish) telefon bilan tasdiqlanadi."""
from django.core.cache import cache
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from apps.auth_app.models import Foydalanuvchi

from .models import Xarid

TELEFON = '+998901234567'


def klient(user=None):
    c = APIClient()
    if user:
        c.credentials(HTTP_AUTHORIZATION='Bearer ' + str(RefreshToken.for_user(user).access_token))
    return c


class EgalikTest(TestCase):
    def setUp(self):
        cache.clear()
        self.xarid = Xarid.objects.create(
            ism='Ali Valiyev', telefon=TELEFON, manzil='Toshkent, Chilonzor 5-kv, 3-uy',
            yetkazish_izohi='3-qavat, eshik kodi 1234', holat='yolda', jami=100000,
            kuryer_lat=41.3, kuryer_lng=69.2, manzil_lat=41.31, manzil_lng=69.28,
            tolov_usuli='naqd')
        self.url = f'/api/xaridlar/{self.xarid.raqam}/'

    # ── GET: niqoblash ──
    def test_mehmon_shaxsiy_malumotni_kormaydi(self):
        d = klient().get(self.url).json()
        self.assertTrue(d['restricted'])
        self.assertEqual(d['customer']['name'], 'Ali V.')
        self.assertEqual(d['customer']['phone'], '+998 ** *** ** 67')
        self.assertEqual(d['customer']['address'], '')
        self.assertEqual(d['delivery']['note'], '')
        self.assertNotIn('courier', d['delivery'])
        self.assertNotIn('destination', d['delivery'])
        matn = str(d)
        for sir in ('Valiyev', '901234567', 'Chilonzor', '1234', '41.31'):
            self.assertNotIn(sir, matn)

    def test_holat_va_summa_mehmonga_ochiq(self):
        d = klient().get(self.url).json()
        self.assertEqual((d['status'], d['total']), ('yolda', 100000))
        self.assertIn('items', d)

    def test_ega_toliq_koradi(self):
        ega = Foydalanuvchi.objects.create(telefon=TELEFON, rol='mijoz')
        d = klient(ega).get(self.url).json()
        self.assertNotIn('restricted', d)
        self.assertEqual(d['customer']['name'], 'Ali Valiyev')
        self.assertIn('Chilonzor', d['customer']['address'])
        self.assertIn('courier', d['delivery'])

    def test_begona_mijoz_niqoblangan_koradi(self):
        begona = Foydalanuvchi.objects.create(telefon='+998909999999', rol='mijoz')
        self.assertTrue(klient(begona).get(self.url).json()['restricted'])

    def test_admin_va_xodim_toliq_koradi(self):
        for rol, tel in (('admin', '+998900000001'), ('xodim', '+998900000002')):
            u = Foydalanuvchi.objects.create(telefon=tel, rol=rol)
            self.assertNotIn('restricted', klient(u).get(self.url).json(), rol)

    def test_xodim_qidiruvi_ishlaydi_oldingi_sinov(self):
        self.assertEqual(klient().get('/api/xaridlar/SG-0000-YOQ/').status_code, 404)

    # ── POST /korish/ ──
    def test_telefon_oxiri_bilan_toliq_malumot(self):
        r = klient().post(self.url + 'korish/', {'telefon': '4567'}, format='json')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()['customer']['name'], 'Ali Valiyev')

    def test_toliq_telefon_ham_ishlaydi(self):
        r = klient().post(self.url + 'korish/', {'telefon': '+998 90 123 45 67'}, format='json')
        self.assertEqual(r.status_code, 200)

    def test_notogri_telefon_rad_etiladi(self):
        r = klient().post(self.url + 'korish/', {'telefon': '0000'}, format='json')
        self.assertEqual(r.status_code, 403)
        self.assertTrue(r.json()['telefon_kerak'])

    def test_telefonsiz_rad_etiladi_va_urinish_hisoblanmaydi(self):
        for _ in range(12):
            self.assertEqual(klient().post(self.url + 'korish/', {}, format='json').status_code, 403)
        # Haqiqiy ega hali ham kira oladi
        self.assertEqual(klient().post(self.url + 'korish/', {'telefon': '4567'}, format='json').status_code, 200)

    def test_taxmin_qilish_buyurtma_boshiga_cheklanadi(self):
        holatlar = [klient().post(self.url + 'korish/', {'telefon': f'{i:04d}'}, format='json').status_code
                    for i in range(12)]
        self.assertIn(429, holatlar)
        # Cheklovdan keyin hatto TO'G'RI telefon ham o'tmaydi (taxmin-bloklash)
        self.assertEqual(klient().post(self.url + 'korish/', {'telefon': '4567'}, format='json').status_code, 429)

    def test_qisqa_telefon_qabul_qilinmaydi(self):
        self.assertEqual(klient().post(self.url + 'korish/', {'telefon': '7'}, format='json').status_code, 403)

    # ── To'lov usuli o'zgartirish ──
    def test_begona_tolov_usulini_ozgartira_olmaydi(self):
        r = klient().post(self.url + 'tolov/', {'method': 'naqd'}, format='json')
        self.assertEqual(r.status_code, 403)
        r = klient().post(self.url + 'tolov/', {'method': 'click', 'telefon': '9999'}, format='json')
        self.assertEqual(r.status_code, 403)
        self.xarid.refresh_from_db()
        self.assertEqual(self.xarid.tolov_usuli, 'naqd')

    def test_tolov_usulini_telefon_bilan_ozgartirish(self):
        r = klient().post(self.url + 'tolov/', {'method': 'click', 'telefon': '4567'}, format='json')
        self.assertEqual(r.status_code, 200, r.content)
        self.xarid.refresh_from_db()
        self.assertEqual(self.xarid.tolov_usuli, 'click')

    def test_ega_tolov_usulini_telefonsiz_ozgartiradi(self):
        ega = Foydalanuvchi.objects.create(telefon=TELEFON, rol='mijoz')
        r = klient(ega).post(self.url + 'tolov/', {'method': 'click'}, format='json')
        self.assertEqual(r.status_code, 200, r.content)

    def test_tolov_holatini_koriish_ochiq(self):
        self.assertEqual(klient().get(self.url + 'tolov/').status_code, 200)

    # ── Qayta yetkazish ──
    def test_begona_manzilni_ozgartira_olmaydi(self):
        Xarid.objects.filter(pk=self.xarid.pk).update(holat='muammo')
        r = klient().post(self.url + 'qayta/', {'address': 'Boshqa joy'}, format='json')
        self.assertEqual(r.status_code, 403)
        self.xarid.refresh_from_db()
        self.assertEqual(self.xarid.holat, 'muammo')
        self.assertIn('Chilonzor', self.xarid.manzil)

    def test_ega_qayta_yetkazishni_telefon_bilan_rasmiylashtiradi(self):
        Xarid.objects.filter(pk=self.xarid.pk).update(holat='muammo')
        r = klient().post(self.url + 'qayta/', {'address': 'Yangi manzil', 'telefon': '4567'}, format='json')
        self.assertEqual(r.status_code, 200, r.content)
        self.xarid.refresh_from_db()
        self.assertEqual((self.xarid.holat, self.xarid.manzil), ('jonatildi', 'Yangi manzil'))
        self.assertEqual(r.json()['customer']['name'], 'Ali Valiyev')   # tasdiqlangan — to'liq
