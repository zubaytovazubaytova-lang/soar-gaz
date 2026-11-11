"""Kadrlar mutaxassisi har bir xodimning topshirgan pulini qabul qiladi (yoki rad etadi)."""
from django.core.cache import cache
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from apps.auth_app.models import AuditYozuv, Foydalanuvchi
from apps.tushum.models import Tushum

ROYXAT = '/api/tushum/admin/'


def klient(user=None):
    c = APIClient()
    if user:
        c.credentials(HTTP_AUTHORIZATION='Bearer ' + str(RefreshToken.for_user(user).access_token))
    return c


class KadrTushumTestlari(TestCase):
    def setUp(self):
        cache.clear()
        mk = Foydalanuvchi.objects.create
        self.kadr = mk(telefon='+998900000401', ism='Ruxsora', rol='xodim', holat='faol',
                       lavozim="Kadrlar bo'yicha mutaxassis")
        self.usta = mk(telefon='+998900000402', ism='Aziz', rol='xodim', holat='faol', lavozim='Montaj ustasi')
        self.operator = mk(telefon='+998900000403', ism='Nargiza', rol='xodim', holat='faol',
                           lavozim='Call center operatori')
        self.admin = mk(telefon='+998900000404', ism='Ega', rol='admin', is_staff=True, is_superuser=True)
        self.t = Tushum.objects.create(xodim=self.usta, summa=150_000, usul='naqd')

    def test_kadr_royxatni_koradi(self):
        r = klient(self.kadr).get(ROYXAT, {'holat': 'kutilmoqda'})
        self.assertEqual(r.status_code, 200)
        self.assertEqual([y['id'] for y in r.json()['yozuvlar']], [self.t.id])
        self.assertEqual(r.json()['xodimlar'][0]['kutilmoqda_summa'], 150_000)

    def test_kadr_qabul_qiladi(self):
        r = klient(self.kadr).post(f'/api/tushum/{self.t.id}/qabul/')
        self.assertEqual(r.status_code, 200)
        self.t.refresh_from_db()
        self.assertEqual((self.t.holat, self.t.hal_qilgan), ('qabul', self.kadr))
        # Jurnalda kim qabul qilgani qayd etiladi
        self.assertEqual(AuditYozuv.objects.filter(amal='tushum_qabul').first().kim, self.kadr)

    def test_kadr_rad_etadi_sabab_bilan(self):
        c = klient(self.kadr)
        self.assertEqual(c.post(f'/api/tushum/{self.t.id}/rad/', {}).status_code, 400)     # sababsiz - yo'q
        r = c.post(f'/api/tushum/{self.t.id}/rad/', {'sabab': 'Summa mos emas'})
        self.assertEqual(r.status_code, 200)
        self.t.refresh_from_db()
        self.assertEqual((self.t.holat, self.t.rad_sababi), ('rad', 'Summa mos emas'))

    def test_ikki_marta_hal_bolmaydi(self):
        c = klient(self.kadr)
        self.assertEqual(c.post(f'/api/tushum/{self.t.id}/qabul/').status_code, 200)
        self.assertEqual(c.post(f'/api/tushum/{self.t.id}/qabul/').status_code, 409)

    def test_ozining_tushumini_ozi_qabul_qilolmaydi(self):
        oz = Tushum.objects.create(xodim=self.kadr, summa=50_000, usul='naqd')
        c = klient(self.kadr)
        self.assertEqual(c.post(f'/api/tushum/{oz.id}/qabul/').status_code, 403)
        self.assertEqual(c.post(f'/api/tushum/{oz.id}/rad/', {'sabab': 'x'}).status_code, 403)
        oz.refresh_from_db()
        self.assertEqual(oz.holat, 'kutilmoqda')

    def test_boshqa_xodimlar_qabul_qilolmaydi(self):
        for u in (self.usta, self.operator):
            c = klient(u)
            self.assertEqual(c.get(ROYXAT).status_code, 403)
            self.assertEqual(c.post(f'/api/tushum/{self.t.id}/qabul/').status_code, 403)
            self.assertEqual(c.post(f'/api/tushum/{self.t.id}/rad/', {'sabab': 'x'}).status_code, 403)
        self.assertEqual(klient().post(f'/api/tushum/{self.t.id}/qabul/').status_code, 401)
        self.t.refresh_from_db()
        self.assertEqual(self.t.holat, 'kutilmoqda')

    def test_nofaol_kadr_qabul_qilolmaydi(self):
        self.kadr.holat = 'nofaol'
        self.kadr.save()
        self.assertEqual(klient(self.kadr).post(f'/api/tushum/{self.t.id}/qabul/').status_code, 403)

    def test_administrator_avvalgidek_qabul_qiladi(self):
        self.assertEqual(klient(self.admin).post(f'/api/tushum/{self.t.id}/qabul/').status_code, 200)
