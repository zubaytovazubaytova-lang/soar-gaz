"""Xodimning mijozdan olgan puli: kiritish, qabul/rad va ruxsatlar.

Pul yozuvlari uchun eng muhim va'dalar: xodim faqat o'z nomidan va o'z
buyurtmasiga kiritadi, yozuvni o'zgartira olmaydi, administrator har yozuvni
faqat bir marta hal qiladi va har amal jurnalga tushadi.
"""
from django.core.cache import cache
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from apps.auth_app.models import AuditYozuv, Foydalanuvchi
from apps.buyurtmalar.models import Buyurtma
from .models import Tushum

URL = '/api/tushum/'
ADMIN_URL = '/api/tushum/admin/'


def klient(user):
    c = APIClient()
    c.credentials(HTTP_AUTHORIZATION='Bearer ' + str(RefreshToken.for_user(user).access_token))
    return c


class Asos(TestCase):
    def setUp(self):
        cache.clear()
        self.addCleanup(cache.clear)
        self.xodim = Foydalanuvchi.objects.create(telefon='+998900000021', ism='Ali', rol='xodim', holat='faol')
        self.boshqa = Foydalanuvchi.objects.create(telefon='+998900000022', ism='Vali', rol='xodim', holat='faol')
        self.admin = Foydalanuvchi.objects.create(telefon='+998900000023', ism='Admin', rol='admin', holat='faol', is_superuser=True)
        self.mijoz = Foydalanuvchi.objects.create(telefon='+998900000024', rol='mijoz')
        # Buyurtma asosidagi tushum faqat narxi tasdiqlangan buyurtmaga kiritiladi
        self.b1 = Buyurtma.objects.create(mijoz=self.mijoz, xodim=self.xodim, xizmat='montaj',
                                          tasdiq_summa=1_000_000)
        self.b2 = Buyurtma.objects.create(mijoz=self.mijoz, xodim=self.boshqa, xizmat='servis',
                                          tasdiq_summa=1_000_000)
        self.x, self.v, self.a, self.m = (klient(self.xodim), klient(self.boshqa),
                                          klient(self.admin), klient(self.mijoz))

    def kirit(self, client=None, **kw):
        malumot = {'summa': 150000, 'usul': 'naqd', 'buyurtma': self.b1.pk}
        malumot.update(kw)
        return (client or self.x).post(URL, malumot, format='json')


class KiritishTestlari(Asos):
    def test_xodim_kiritadi_va_jurnalga_yoziladi(self):
        r = self.kirit()
        self.assertEqual(r.status_code, 201, r.content)
        t = Tushum.objects.get()
        self.assertEqual((t.xodim, t.buyurtma, t.summa, t.holat), (self.xodim, self.b1, 150000, 'kutilmoqda'))
        self.assertTrue(AuditYozuv.objects.filter(amal='tushum_kiritildi').exists())

    def test_buyurtmasiz_ham_kiritiladi(self):
        self.assertEqual(self.kirit(buyurtma=None).status_code, 201)
        self.assertIsNone(Tushum.objects.get().buyurtma)

    def test_summa_tekshiruvi(self):
        for summa in (0, -5, 100_000_001, 1.5, 'abc', '', None, True, [], '12.5'):
            cache.clear()
            self.assertEqual(self.kirit(summa=summa).status_code, 400, repr(summa))
        self.assertFalse(Tushum.objects.exists())

    def test_summa_matn_va_bosh_joyli_qabul_qilinadi(self):
        self.assertEqual(self.kirit(summa='150 000').status_code, 201)
        self.assertEqual(Tushum.objects.get().summa, 150000)

    def test_notogri_usul(self):
        self.assertEqual(self.kirit(usul='bitcoin').status_code, 400)

    def test_boshqa_xodim_buyurtmasiga_kiritib_bolmaydi(self):
        self.assertEqual(self.kirit(buyurtma=self.b2.pk).status_code, 400)
        self.assertEqual(self.kirit(buyurtma=99999).status_code, 400)
        self.assertEqual(self.kirit(buyurtma='x').status_code, 400)
        self.assertFalse(Tushum.objects.exists())

    def test_qosh_bosish_ikki_yozuv_yaratmaydi(self):
        self.assertEqual(self.kirit().status_code, 201)
        self.assertEqual(self.kirit().status_code, 409)
        self.assertEqual(Tushum.objects.count(), 1)
        # boshqa summa — alohida to'lov
        self.assertEqual(self.kirit(summa=200000).status_code, 201)

    def test_xodim_nomidan_boshqasi_kiritolmaydi(self):
        # xodim maydoni so'rovdan o'qilmaydi — yozuv doim token egasiniki
        self.kirit(xodim=self.boshqa.pk)
        self.assertEqual(Tushum.objects.get().xodim, self.xodim)

    def test_mijoz_admin_va_tokensiz_kiritolmaydi(self):
        self.assertEqual(self.kirit(client=self.m).status_code, 403)
        self.assertEqual(self.kirit(client=self.a).status_code, 403)
        self.assertEqual(APIClient().post(URL, {'summa': 1000}, format='json').status_code, 401)
        self.assertFalse(Tushum.objects.exists())

    def test_nofaol_xodim_kirita_olmaydi(self):
        self.xodim.holat = 'nofaol'
        self.xodim.save()
        self.assertEqual(self.kirit().status_code, 403)


class BuyurtmaSummasiTestlari(Asos):
    """Tushum tasdiqlangan summa bo'yicha olinadi."""

    def test_narxi_tasdiqlanmagan_buyurtmaga_tushum_kiritib_bolmaydi(self):
        Buyurtma.objects.filter(pk=self.b1.pk).update(tasdiq_summa=None)
        r = self.kirit()
        self.assertEqual(r.status_code, 400)
        self.assertIn('tasdiqlang', r.json()['detail'])
        self.assertFalse(Tushum.objects.exists())

    def test_buyurtmasiz_tushum_tasdiqsiz_ham_mumkin(self):
        Buyurtma.objects.filter(pk=self.b1.pk).update(tasdiq_summa=None)
        self.assertEqual(self.kirit(buyurtma=None).status_code, 201)

    def test_qoldiqdan_oshib_ketmaydi(self):
        self.assertEqual(self.kirit(summa=600000).status_code, 201)
        r = self.kirit(summa=500000)             # qoldiq 400 000
        self.assertEqual(r.status_code, 400)
        self.assertIn('400 000', r.json()['detail'])
        self.assertEqual(self.kirit(summa=400000).status_code, 201)
        self.assertEqual(self.kirit(summa=1).status_code, 400)   # qoldiq 0

    def test_rad_etilgan_summa_qoldiqqa_qaytadi(self):
        self.kirit(summa=900000)
        t = Tushum.objects.get()
        self.assertEqual(self.kirit(summa=200000).status_code, 400)
        self.a.post(f'{URL}{t.pk}/rad/', {'sabab': 'xato'}, format='json')
        self.assertEqual(self.kirit(summa=200000).status_code, 201)

    def test_toliq_qabul_qilinsa_buyurtma_tolandi(self):
        self.kirit(summa=600000)
        self.kirit(summa=400000)
        t1, t2 = Tushum.objects.order_by('id')
        self.a.post(f'{URL}{t1.pk}/qabul/')
        self.b1.refresh_from_db()
        self.assertFalse(self.b1.tolandi)
        self.a.post(f'{URL}{t2.pk}/qabul/')
        self.b1.refresh_from_db()
        self.assertTrue(self.b1.tolandi)


class XodimRoyxatiTestlari(Asos):
    def test_xodim_faqat_oz_yozuvlarini_va_yigindisini_koradi(self):
        self.kirit()
        self.kirit(client=self.v, summa=777000, buyurtma=self.b2.pk)
        r = self.x.get(URL).json()
        self.assertEqual(len(r['yozuvlar']), 1)
        self.assertEqual(r['yozuvlar'][0]['summa'], 150000)
        self.assertEqual(r['jami']['kutilmoqda'], 150000)
        self.assertEqual(r['jami']['qabul'], 0)

    def test_qabul_qilingach_yigindi_otadi(self):
        self.kirit()
        self.a.post(f'{URL}{Tushum.objects.get().pk}/qabul/')
        j = self.x.get(URL).json()['jami']
        self.assertEqual((j['kutilmoqda'], j['qabul'], j['oy_qabul']), (0, 150000, 150000))

    def test_mijoz_royxatni_kora_olmaydi(self):
        self.assertEqual(self.m.get(URL).status_code, 403)


class AdminTestlari(Asos):
    def setUp(self):
        super().setUp()
        self.kirit()
        self.kirit(client=self.v, summa=50000, buyurtma=self.b2.pk)
        self.t = Tushum.objects.get(xodim=self.xodim)

    def test_qabul(self):
        r = self.a.post(f'{URL}{self.t.pk}/qabul/')
        self.assertEqual(r.status_code, 200)
        self.t.refresh_from_db()
        self.assertEqual((self.t.holat, self.t.hal_qilgan), ('qabul', self.admin))
        self.assertIsNotNone(self.t.hal_vaqti)
        self.assertTrue(AuditYozuv.objects.filter(amal='tushum_qabul').exists())

    def test_rad_sabab_bilan(self):
        self.assertEqual(self.a.post(f'{URL}{self.t.pk}/rad/', {}, format='json').status_code, 400)
        self.assertEqual(self.a.post(f'{URL}{self.t.pk}/rad/', {'sabab': '  '}, format='json').status_code, 400)
        r = self.a.post(f'{URL}{self.t.pk}/rad/', {'sabab': "Summa noto'g'ri"}, format='json')
        self.assertEqual(r.status_code, 200)
        self.t.refresh_from_db()
        self.assertEqual((self.t.holat, self.t.rad_sababi), ('rad', "Summa noto'g'ri"))
        self.assertTrue(AuditYozuv.objects.filter(amal='tushum_rad').exists())

    def test_hal_qilingan_yozuv_qayta_hal_bolmaydi(self):
        self.a.post(f'{URL}{self.t.pk}/qabul/')
        self.assertEqual(self.a.post(f'{URL}{self.t.pk}/qabul/').status_code, 409)
        self.assertEqual(self.a.post(f'{URL}{self.t.pk}/rad/', {'sabab': 'x'}, format='json').status_code, 409)
        self.t.refresh_from_db()
        self.assertEqual(self.t.holat, 'qabul')

    def test_mavjud_bolmagan_yozuv(self):
        self.assertEqual(self.a.post(f'{URL}99999/qabul/').status_code, 404)

    def test_xodim_va_mijoz_hal_qila_olmaydi(self):
        for c in (self.x, self.v, self.m):
            self.assertEqual(c.post(f'{URL}{self.t.pk}/qabul/').status_code, 403)
            self.assertEqual(c.post(f'{URL}{self.t.pk}/rad/', {'sabab': 'x'}, format='json').status_code, 403)
            self.assertEqual(c.get(ADMIN_URL).status_code, 403)
        self.t.refresh_from_db()
        self.assertEqual(self.t.holat, 'kutilmoqda')

    def test_admin_royxati_va_xodimlar_boyicha_qoldiq(self):
        r = self.a.get(ADMIN_URL).json()
        self.assertEqual(len(r['yozuvlar']), 2)
        qoldiq = {x['ism']: x['kutilmoqda_summa'] for x in r['xodimlar']}
        self.assertEqual(qoldiq, {'Ali': 150000, 'Vali': 50000})
        self.a.post(f'{URL}{self.t.pk}/qabul/')
        r = self.a.get(ADMIN_URL).json()
        ali = next(x for x in r['xodimlar'] if x['ism'] == 'Ali')
        self.assertEqual((ali['kutilmoqda_summa'], ali['qabul_summa']), (0, 150000))

    def test_holat_filtri(self):
        self.a.post(f'{URL}{self.t.pk}/qabul/')
        self.assertEqual(len(self.a.get(ADMIN_URL + '?holat=qabul').json()['yozuvlar']), 1)
        self.assertEqual(len(self.a.get(ADMIN_URL + '?holat=kutilmoqda').json()['yozuvlar']), 1)
        self.assertEqual(len(self.a.get(ADMIN_URL + '?holat=zzz').json()['yozuvlar']), 2)
