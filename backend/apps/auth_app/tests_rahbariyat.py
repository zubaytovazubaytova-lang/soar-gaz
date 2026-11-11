"""«Rahbariyat» bosh sahifasi: faqat adminlarga, raqamlar to'g'ri hisoblanadi."""
from datetime import timedelta

from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from apps.auth_app.models import AuditYozuv, Foydalanuvchi
from apps.buyurtmalar.models import Buyurtma, BuyurtmaXizmat
from apps.joylashuv.models import Nuqta, Smena
from apps.narxnoma.models import NarxnomaQator
from apps.tushum.models import Tushum

URL = '/api/auth/rahbariyat/'


def klient(user):
    c = APIClient()
    c.credentials(HTTP_AUTHORIZATION='Bearer ' + str(RefreshToken.for_user(user).access_token))
    return c


class Asos(TestCase):
    def setUp(self):
        mk = Foydalanuvchi.objects.create
        self.direktor = mk(telefon='+998900000111', ism='Direktor', rol='admin', holat='faol')
        self.egasi = mk(telefon='+998900000112', ism='Egasi', rol='admin', holat='faol', is_superuser=True)
        self.xodim = mk(telefon='+998900000113', ism='Aziz', rol='xodim', holat='faol')
        self.xodim2 = mk(telefon='+998900000114', ism='Bobur', rol='xodim', holat='faol')
        self.mijoz = mk(telefon='+998900000115', rol='mijoz')
        self.d = klient(self.direktor)

    def tushum(self, xodim, summa, holat='kutilmoqda', tarmoq='aholi', kun_oldin=0):
        t = Tushum.objects.create(xodim=xodim, summa=summa, tarmoq=tarmoq, holat=holat,
                                  hal_vaqti=timezone.now() if holat == 'qabul' else None)
        if kun_oldin:
            Tushum.objects.filter(pk=t.pk).update(yaratilgan=timezone.now() - timedelta(days=kun_oldin))
        return t


class RuxsatTestlari(Asos):
    def test_direktor_va_egasi_koradi(self):
        self.assertEqual(self.d.get(URL).status_code, 200)
        self.assertEqual(klient(self.egasi).get(URL).status_code, 200)

    def test_xodim_mijoz_va_tokensiz_kora_olmaydi(self):
        self.assertEqual(klient(self.xodim).get(URL).status_code, 403)
        self.assertEqual(klient(self.mijoz).get(URL).status_code, 403)
        self.assertEqual(APIClient().get(URL).status_code, 401)

    def test_faqat_oqish(self):
        for usul in ('post', 'put', 'patch', 'delete'):
            # Direktor kuzatuvchi: o'zgartiruvchi so'rov view'ga yetmasdan 403 oladi (autentifikatsiya bosqichida)
            self.assertIn(getattr(self.d, usul)(URL).status_code, (403, 405), usul)

    def test_bosh_bazada_xatosiz_ishlaydi(self):
        j = self.d.get(URL).json()
        self.assertEqual(j['tushum']['aholi']['oy_qabul'], 0)
        self.assertEqual(j['diqqat'], [])
        self.assertEqual(j['qarzdorlar'], [])
        self.assertEqual(j['xodimlar']['faol'], 2)


class TushumTestlari(Asos):
    def test_tarmoqlar_boyicha_summalar(self):
        self.tushum(self.xodim, 300000, 'qabul', 'aholi')
        self.tushum(self.xodim, 100000, 'kutilmoqda', 'aholi')
        self.tushum(self.xodim, 500000, 'qabul', 'ulgurji')
        self.tushum(self.xodim, 70000, 'rad', 'ulgurji')              # rad etilgan hisobga kirmaydi
        self.tushum(self.xodim, 5000, 'kutilmoqda', '')               # turkumsiz
        t = self.d.get(URL).json()['tushum']
        self.assertEqual((t['aholi']['oy_qabul'], t['aholi']['kutilmoqda'], t['aholi']['kutilmoqda_soni']),
                         (300000, 100000, 1))
        self.assertEqual((t['ulgurji']['oy_qabul'], t['ulgurji']['kutilmoqda']), (500000, 0))
        self.assertEqual(t['boshqa']['kutilmoqda'], 5000)

    def test_oldingi_oy_qabuli_oy_summasiga_kirmaydi(self):
        t = self.tushum(self.xodim, 200000, 'qabul', 'aholi')
        Tushum.objects.filter(pk=t.pk).update(hal_vaqti=timezone.now() - timedelta(days=45))
        r = self.d.get(URL).json()['tushum']['aholi']
        self.assertEqual((r['oy_qabul'], r['qabul']), (0, 200000))

    def test_qarzdorlar_va_eski_tushum_ogohlantirishi(self):
        self.tushum(self.xodim, 400000, kun_oldin=5)
        self.tushum(self.xodim, 100000, kun_oldin=1)
        self.tushum(self.xodim2, 50000, kun_oldin=1)
        j = self.d.get(URL).json()
        q = j['qarzdorlar']
        self.assertEqual([x['ism'] for x in q], ['Aziz', 'Bobur'])          # eng ko'p topshirmagani birinchi
        self.assertEqual((q[0]['summa'], q[0]['soni'], q[0]['kun'], q[0]['eski']), (500000, 2, 5, True))
        self.assertFalse(q[1]['eski'])
        eski = [d for d in j['diqqat'] if d['sahifa'] == 'cash']
        self.assertEqual(len(eski), 1)
        self.assertEqual((eski[0]['daraja'], eski[0]['soni']), ('qizil', 1))   # faqat 5 kunlik bittasi


class BuyurtmaTestlari(Asos):
    def test_holatlar_va_tayinlanmagan(self):
        Buyurtma.objects.create(mijoz=self.mijoz, xizmat='servis', holat='yangi')                    # tayinlanmagan
        Buyurtma.objects.create(mijoz=self.mijoz, xizmat='servis', holat='yangi', xodim=self.xodim)
        Buyurtma.objects.create(mijoz=self.mijoz, xizmat='servis', holat='bajarildi', xodim=self.xodim,
                                tasdiq_summa=100000)
        j = self.d.get(URL).json()
        self.assertEqual(j['buyurtmalar']['holatlar'], {'yangi': 2, 'bajarildi': 1})
        self.assertEqual(j['buyurtmalar']['tayinlanmagan'], 1)
        self.assertTrue(any('xodim tayinlanmagan' in d['matn'] for d in j['diqqat']))

    def test_tasdiqsiz_yakunlangan_buyurtma_ogohlantirishi(self):
        Buyurtma.objects.create(mijoz=self.mijoz, xizmat='servis', holat='bajarildi', xodim=self.xodim)
        d = self.d.get(URL).json()['diqqat']
        self.assertTrue(any('yakunlangan' in x['matn'] and x['soni'] == 1 for x in d))

    def test_faol_buyurtmada_xizmat_bor_summa_yoq(self):
        b = Buyurtma.objects.create(mijoz=self.mijoz, xizmat='servis', holat='qabul', xodim=self.xodim,
                                    tarmoq='ulgurji')
        q = NarxnomaQator.objects.get(narxnoma__tarmoq='ulgurji', narxnoma__bolim='profilaktika', tartib=1)
        BuyurtmaXizmat.objects.create(buyurtma=b, qator=q, nomi=q.nomi, ustun='p', narx_dan=q.p_dan)
        BuyurtmaXizmat.objects.create(buyurtma=b, qator=q, nomi=q.nomi, ustun='r', narx_dan=q.r_dan)
        d = self.d.get(URL).json()['diqqat']
        info = [x for x in d if x['daraja'] == 'info']
        self.assertEqual(len(info), 1)
        self.assertEqual(info[0]['soni'], 1)          # ikki xizmat, lekin bitta buyurtma

    def test_oy_tasdiqi_va_qoldiq_tarmoq_boyicha(self):
        a = Buyurtma.objects.create(mijoz=self.mijoz, xizmat='servis', xodim=self.xodim, tarmoq='aholi',
                                    tasdiq_summa=1_000_000, tasdiq_vaqt=timezone.now())
        Buyurtma.objects.create(mijoz=self.mijoz, xizmat='servis', xodim=self.xodim, tarmoq='ulgurji',
                                tasdiq_summa=2_000_000, tasdiq_vaqt=timezone.now(), tolandi=True)
        Tushum.objects.create(xodim=self.xodim, buyurtma=a, summa=400000, holat='qabul', tarmoq='aholi',
                              hal_vaqti=timezone.now())
        Tushum.objects.create(xodim=self.xodim, buyurtma=a, summa=100000, holat='kutilmoqda', tarmoq='aholi')
        b = self.d.get(URL).json()['buyurtmalar']
        self.assertEqual(b['oy_tasdiqlangan'], {'aholi': 1_000_000, 'ulgurji': 2_000_000})
        # Qoldiq faqat QABUL qilingan pul bo'yicha: 1 000 000 - 400 000; to'langan buyurtma hisobga kirmaydi
        self.assertEqual(b['qoldiq'], {'aholi': 600000, 'ulgurji': 0})


class XodimTestlari(Asos):
    def test_smenada_va_aloqada(self):
        s1 = Smena.objects.create(xodim=self.xodim)
        s2 = Smena.objects.create(xodim=self.xodim2)
        Nuqta.objects.create(smena=s1, xodim=self.xodim, lat=41.3, lng=69.2)             # hozir — aloqada
        n = Nuqta.objects.create(smena=s2, xodim=self.xodim2, lat=41.3, lng=69.2)
        Nuqta.objects.filter(pk=n.pk).update(vaqt=timezone.now() - timedelta(minutes=10))  # eski — aloqasiz
        x = self.d.get(URL).json()['xodimlar']
        self.assertEqual((x['faol'], x['smenada'], x['aloqada'], x['aloqasiz']), (2, 2, 1, 1))
        d = self.d.get(URL).json()['diqqat']
        self.assertTrue(any(i['sahifa'] == 'joy' and i['soni'] == 1 for i in d))

    def test_yopilgan_va_unutilgan_smena_hisobga_kirmaydi(self):
        Smena.objects.create(xodim=self.xodim, tugadi=timezone.now())
        eski = Smena.objects.create(xodim=self.xodim2)
        Smena.objects.filter(pk=eski.pk).update(boshlandi=timezone.now() - timedelta(hours=30))
        self.assertEqual(self.d.get(URL).json()['xodimlar']['smenada'], 0)


class FaoliyatTestlari(Asos):
    def test_shovqinli_yozuvlar_kirmaydi(self):
        AuditYozuv.objects.create(kim=self.direktor, kim_ism='Direktor', amal='joylashuv_korildi')
        AuditYozuv.objects.create(kim=self.direktor, kim_ism='Direktor', amal='tushum_qabul', tafsilot='x')
        f = self.d.get(URL).json()['faoliyat']
        self.assertEqual(len(f), 1)
        self.assertEqual(f[0]['kim'], 'Direktor')

    def test_faoliyat_8_ta_bilan_cheklanadi(self):
        for i in range(12):
            AuditYozuv.objects.create(kim=self.direktor, kim_ism='D', amal='tushum_qabul', tafsilot=str(i))
        self.assertEqual(len(self.d.get(URL).json()['faoliyat']), 8)
