"""Lavozimga qarab kabinet va Kadrlar mutaxassisi bo'limi."""
from datetime import timedelta

from django.core.cache import cache
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from apps.aloqa.models import Xabar
from apps.auth_app.kabinet_turlari import BOLIMLAR, kabinet_malumoti, kabinet_turi
from apps.auth_app.models import Foydalanuvchi
from apps.joylashuv.models import Smena
from apps.kadrlar.models import KunlikHisobot, XodimHujjati

HISOBOT = '/api/kadrlar/hisobot/'
KUN = '/api/kadrlar/kun/'
ESLATMA = '/api/kadrlar/eslatma/'
HUJJATLAR = '/api/kadrlar/hujjatlar/'


def klient(user=None):
    c = APIClient()
    if user:
        c.credentials(HTTP_AUTHORIZATION='Bearer ' + str(RefreshToken.for_user(user).access_token))
    return c


class Asos(TestCase):
    def setUp(self):
        cache.clear()
        mk = Foydalanuvchi.objects.create
        self.kadr = mk(telefon='+998900000301', ism='Kadr Mutaxassis', rol='xodim', holat='faol',
                       lavozim="Kadrlar bo'yicha mutaxassis")
        self.usta = mk(telefon='+998900000302', ism='Aziz', rol='xodim', holat='faol', lavozim='Montaj ustasi')
        self.usta2 = mk(telefon='+998900000303', ism='Vali', rol='xodim', holat='faol', lavozim='Metrolog')
        self.nofaol = mk(telefon='+998900000304', ism='Eski', rol='xodim', holat='nofaol', lavozim='Montaj ustasi')
        self.mijoz = mk(telefon='+998900000305', ism='Karim', rol='mijoz')
        self.admin = mk(telefon='+998900000306', ism='Ega', rol='admin', is_staff=True, is_superuser=True)


class KabinetTuriTestlari(TestCase):
    def test_lavozimdan_tur(self):
        for lavozim, tur in [
            ("Kadrlar bo'yicha mutaxassis", 'kadrlar'), ("  KADRLAR bo'limi boshlig'i ", 'kadrlar'),
            ('Call center operatori', 'qongiroq'), ('Call-center operator', 'qongiroq'),
            ('Servis operatori', 'oddiy'), ('  SERVIS OPERATORI', 'oddiy'),     # alohida kabinet emas
            ('Servis ustasi', 'oddiy'), ('Menejer', 'oddiy'),
            ('Montaj ustasi', 'oddiy'), ('Katta montaj ustasi', 'oddiy'),
            ('Metrolog', 'oddiy'), ('Loyihachi muhandis', 'oddiy'),
            ('', 'oddiy'), (None, 'oddiy'), ("Yangi noma'lum lavozim", 'oddiy'),
        ]:
            self.assertEqual(kabinet_turi(lavozim), tur, lavozim)

    def test_dala_kabineti_ozgarmagan(self):
        """Tanilmagan lavozim - hozirgi to'liq kabinet (10 bo'lim)."""
        self.assertEqual(len(kabinet_malumoti('Montaj ustasi')['bolimlar']), 10)

    def test_kadrlar_menyusi_boshqacha(self):
        k = kabinet_malumoti("Kadrlar bo'yicha mutaxassis")['bolimlar']
        for kerak in ('overview', 'kadr-davomat', 'kadr-hisobot', 'kadr-tushum', 'kadr-hujjat', 'settings'):
            self.assertIn(kerak, k)
        for ortiqcha in ('tasks', 'history', 'docs', 'price'):
            self.assertNotIn(ortiqcha, k)

    def test_kadrlar_pul_olmaydi_balki_qabul_qiladi(self):
        """Kadrlarda "Pul tushumi" (kiritish) o'rniga "kadr-tushum" (qabul qilish) bor."""
        k = BOLIMLAR['kadrlar']
        self.assertNotIn('cash', k)
        self.assertIn('kadr-tushum', k)

    def test_qongiroq_vazifasi_ikkalasida_bir_xil(self):
        """Alohida Call center / Servis operatori kabineti yo'q: «Arizalar» va «Chiquvchi qo'ng'iroqlar» Ruxsora
        (Kadrlar) va Nargizaning (qo'ng'iroq) kabinetida bir xil."""
        for tur in ('kadrlar', 'qongiroq'):
            self.assertIn('op-arizalar', BOLIMLAR[tur])
            self.assertIn('op-qongiroq', BOLIMLAR[tur])
        self.assertEqual(set(BOLIMLAR), {'oddiy', 'qongiroq', 'hujjat', 'kadrlar'})

    def test_nargiza_oddiy_xodim_kabineti_ustiga_vazifa(self):
        # «topshiriq» — ichki topshiriqlar (Kadrlar, call center va hujjatchida bor, oddiy xodimda yo'q)
        self.assertEqual(set(BOLIMLAR['qongiroq']), set(BOLIMLAR['oddiy']) | {'op-arizalar', 'op-qongiroq', 'topshiriq'})
        self.assertNotIn('topshiriq', BOLIMLAR['oddiy'])
        for tur in ('kadrlar', 'qongiroq', 'hujjat'):
            self.assertIn('topshiriq', BOLIMLAR[tur])

    def test_maxsus_bolimlar_boshqalarda_yoq(self):
        for tur in ('oddiy', 'hujjat'):
            self.assertFalse([x for x in BOLIMLAR[tur] if x.startswith(('kadr-', 'op-'))], tur)
        self.assertFalse([x for x in BOLIMLAR['qongiroq'] if x.startswith('kadr-')])        # Kadrlar bo'limlari Nargizada yo'q

    def test_arizalarni_qabul_qiluvchilarga_vazifa_berilmaydi(self):
        from apps.auth_app.kabinet_turlari import vazifa_olishi_mumkin
        self.assertTrue(vazifa_olishi_mumkin('Montaj ustasi'))
        self.assertTrue(vazifa_olishi_mumkin("Mehnat muhofazasi va texnika xavfsizligi bo'yicha muhandis"))
        self.assertFalse(vazifa_olishi_mumkin("Kadrlar bo'yicha mutaxassis"))
        self.assertFalse(vazifa_olishi_mumkin('Call center operatori'))


class ProfilTestlari(Asos):
    def test_profilda_kabinet_bor(self):
        j = klient(self.kadr).get('/api/auth/xodim/profil/').json()
        self.assertEqual(j['kabinet']['tur'], 'kadrlar')
        j = klient(self.usta).get('/api/auth/xodim/profil/').json()
        self.assertEqual(j['kabinet']['tur'], 'oddiy')

    def test_kirishda_ham_keladi(self):
        self.usta.kirish_kodi = 'XD-ABC234'
        self.usta.save()
        r = klient().post('/api/auth/xodim/login/', {'telefon': self.usta.telefon, 'kod': 'XD-ABC234'})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()['xodim']['kabinet']['tur'], 'oddiy')


class HisobotXodimTestlari(Asos):
    def test_bosh_keyin_saqlash_va_yangilash(self):
        c = klient(self.usta)
        self.assertIsNone(c.get(HISOBOT).json()['hisobot'])
        r = c.post(HISOBOT, {'joy': 'Kogon, Navoiy ko\'chasi 5', 'ish': 'Hisoblagich o\'rnatildi'})
        self.assertEqual(r.status_code, 200)
        c.post(HISOBOT, {'joy': 'Kogon', 'ish': 'Tuzatildi'})
        self.assertEqual(KunlikHisobot.objects.filter(xodim=self.usta).count(), 1)     # kuniga bitta
        self.assertEqual(c.get(HISOBOT).json()['hisobot']['ish'], 'Tuzatildi')

    def test_bosh_matn_va_uzun_matn_rad(self):
        c = klient(self.usta)
        self.assertEqual(c.post(HISOBOT, {'joy': ' ', 'ish': 'x'}).status_code, 400)
        self.assertEqual(c.post(HISOBOT, {'joy': 'x', 'ish': ''}).status_code, 400)
        self.assertEqual(c.post(HISOBOT, {'joy': 'x' * 201, 'ish': 'x'}).status_code, 400)
        self.assertEqual(c.post(HISOBOT, {'joy': 'x', 'ish': 'x' * 501}).status_code, 400)

    def test_faqat_faol_xodim(self):
        self.assertEqual(klient(self.mijoz).get(HISOBOT).status_code, 403)
        self.assertEqual(klient(self.nofaol).get(HISOBOT).status_code, 403)
        self.assertEqual(klient().get(HISOBOT).status_code, 401)

    def test_boshqaning_hisoboti_korinmaydi(self):
        KunlikHisobot.objects.create(xodim=self.usta2, sana=timezone.localdate(), joy='A', ish='B')
        self.assertIsNone(klient(self.usta).get(HISOBOT).json()['hisobot'])


class KunKorinishiTestlari(Asos):
    def _smena(self, xodim, boshlandi, tugadi=None):
        s = Smena.objects.create(xodim=xodim)
        Smena.objects.filter(pk=s.pk).update(boshlandi=boshlandi, tugadi=tugadi)
        return s

    def test_faqat_kadr_va_admin(self):
        self.assertEqual(klient(self.usta).get(KUN).status_code, 403)
        self.assertEqual(klient(self.mijoz).get(KUN).status_code, 403)
        self.assertEqual(klient().get(KUN).status_code, 401)
        self.assertEqual(klient(self.kadr).get(KUN).status_code, 200)
        self.assertEqual(klient(self.admin).get(KUN).status_code, 200)

    def test_royxatda_kadr_ozi_va_nofaol_yoq(self):
        ids = {x['id'] for x in klient(self.kadr).get(KUN).json()['xodimlar']}
        self.assertEqual(ids, {self.usta.id, self.usta2.id})

    def test_keldi_ishda_kelmadi(self):
        hozir = timezone.now()
        self._smena(self.usta, hozir - timedelta(minutes=30))                             # hozir ishda
        # usta2 — smena ochmagan
        j = klient(self.kadr).get(KUN).json()
        holat = {x['id']: x['holat'] for x in j['xodimlar']}
        self.assertEqual(holat[self.usta.id], 'ishda')
        self.assertEqual(holat[self.usta2.id], 'kelmadi')
        self.assertEqual((j['xulosa']['keldi'], j['xulosa']['ishda'], j['xulosa']['kelmadi']), (1, 1, 1))

    def test_yopilgan_smena_soati(self):
        bugun_boshi = timezone.make_aware(
            timezone.datetime.combine(timezone.localdate(), timezone.datetime.min.time()))
        self._smena(self.usta, bugun_boshi + timedelta(minutes=1), bugun_boshi + timedelta(hours=2, minutes=1))
        x = next(x for x in klient(self.kadr).get(KUN).json()['xodimlar'] if x['id'] == self.usta.id)
        self.assertEqual(x['holat'], 'keldi')
        self.assertEqual(x['soat'], 2.0)
        self.assertIsNotNone(x['tugadi'])

    def test_otgan_kun_va_hisobot(self):
        kecha = timezone.localdate() - timedelta(days=1)
        kecha_boshi = timezone.make_aware(timezone.datetime.combine(kecha, timezone.datetime.min.time()))
        self._smena(self.usta2, kecha_boshi + timedelta(hours=9), kecha_boshi + timedelta(hours=17))
        KunlikHisobot.objects.create(xodim=self.usta2, sana=kecha, joy='Peshku', ish='Servis')
        j = klient(self.kadr).get(KUN, {'sana': kecha.isoformat()}).json()
        self.assertFalse(j['bugun'])
        x = next(x for x in j['xodimlar'] if x['id'] == self.usta2.id)
        self.assertEqual((x['holat'], x['soat'], x['hisobot']['joy']), ('keldi', 8.0, 'Peshku'))
        self.assertEqual(j['xulosa']['hisobotli'], 1)
        # Bugunning o'zida o'sha hisobot ko'rinmaydi
        bugun = klient(self.kadr).get(KUN).json()
        self.assertIsNone(next(x for x in bugun['xodimlar'] if x['id'] == self.usta2.id)['hisobot'])

    def test_unutilgan_smena_yopilgan_hisoblanadi(self):
        from django.conf import settings
        kecha = timezone.now() - timedelta(days=1)
        self._smena(self.usta, kecha)                       # hech qachon yopilmagan
        kun = timezone.localtime(kecha).date()
        j = klient(self.kadr).get(KUN, {'sana': kun.isoformat()}).json()
        x = next(x for x in j['xodimlar'] if x['id'] == self.usta.id)
        self.assertEqual(x['holat'], 'keldi')               # «ishda» emas
        self.assertEqual(x['soat'], float(settings.JOYLASHUV_SMENA_MAX_SOAT))

    def test_notogri_va_kelajak_sana(self):
        c = klient(self.kadr)
        self.assertEqual(c.get(KUN, {'sana': 'kecha'}).status_code, 400)
        kelajak = (timezone.localdate() + timedelta(days=1)).isoformat()
        self.assertEqual(c.get(KUN, {'sana': kelajak}).status_code, 400)


class EslatmaTestlari(Asos):
    def test_faqat_hisobotsizlarga(self):
        KunlikHisobot.objects.create(xodim=self.usta, sana=timezone.localdate(), joy='A', ish='B')
        r = klient(self.kadr).post(ESLATMA)
        self.assertEqual((r.status_code, r.json()['yuborildi']), (201, 1))
        self.assertTrue(Xabar.objects.filter(xodim=self.usta2).exists())
        self.assertFalse(Xabar.objects.filter(xodim=self.usta).exists())
        self.assertFalse(Xabar.objects.filter(xodim=self.kadr).exists())
        self.assertFalse(Xabar.objects.filter(xodim=self.nofaol).exists())

    def test_soatiga_bir_marta(self):
        c = klient(self.kadr)
        self.assertEqual(c.post(ESLATMA).status_code, 201)
        self.assertEqual(c.post(ESLATMA).status_code, 429)

    def test_boshqalar_yubora_olmaydi(self):
        self.assertEqual(klient(self.usta).post(ESLATMA).status_code, 403)
        self.assertEqual(klient(self.admin).post(ESLATMA).status_code, 403)    # admin faqat o'qiydi
        self.assertEqual(klient(self.mijoz).post(ESLATMA).status_code, 403)


class HujjatTestlari(Asos):
    def test_royxat_va_yetishmaydi(self):
        XodimHujjati.objects.create(xodim=self.usta, turi='pasport')
        XodimHujjati.objects.create(xodim=self.usta, turi='boshqa')
        j = klient(self.kadr).get(HUJJATLAR).json()
        usta = next(x for x in j['xodimlar'] if x['id'] == self.usta.id)
        self.assertNotIn('pasport', usta['yetishmaydi'])
        self.assertNotIn('boshqa', usta['yetishmaydi'])          # «boshqa» majburiy emas
        self.assertIn('tibbiy', usta['yetishmaydi'])
        self.assertEqual(len(usta['hujjatlar']), 2)
        self.assertEqual(len(j['turlar']), 8)

    def test_qoshish_va_ochirish(self):
        c = klient(self.kadr)
        r = c.post(HUJJATLAR, {'xodim': self.usta.id, 'turi': 'tibbiy', 'raqami': 'T-12',
                               'amal_qiladi': (timezone.localdate() + timedelta(days=10)).isoformat()})
        self.assertEqual(r.status_code, 201)
        self.assertEqual(r.json()['holat'], 'yaqin')
        h = XodimHujjati.objects.get()
        self.assertEqual(h.kiritgan, self.kadr)
        self.assertEqual(c.delete(f'{HUJJATLAR}{h.id}/').status_code, 204)
        self.assertEqual(c.delete(f'{HUJJATLAR}{h.id}/').status_code, 404)

    def test_notogri_kiritish(self):
        c = klient(self.kadr)
        self.assertEqual(c.post(HUJJATLAR, {'xodim': 99999, 'turi': 'pasport'}).status_code, 400)
        self.assertEqual(c.post(HUJJATLAR, {'xodim': self.usta.id, 'turi': 'qalbaki'}).status_code, 400)
        self.assertEqual(c.post(HUJJATLAR, {'xodim': self.usta.id, 'turi': 'pasport',
                                            'amal_qiladi': '31-12-2030'}).status_code, 400)
        self.assertEqual(c.post(HUJJATLAR, {'xodim': self.mijoz.id, 'turi': 'pasport'}).status_code, 400)

    def test_ruxsatlar(self):
        self.assertEqual(klient(self.usta).get(HUJJATLAR).status_code, 403)
        self.assertEqual(klient(self.mijoz).get(HUJJATLAR).status_code, 403)
        self.assertEqual(klient().get(HUJJATLAR).status_code, 401)
        # Admin o'qiydi, yozmaydi
        self.assertEqual(klient(self.admin).get(HUJJATLAR).status_code, 200)
        self.assertEqual(klient(self.admin).post(HUJJATLAR, {'xodim': self.usta.id, 'turi': 'pasport'}).status_code, 403)
        self.assertEqual(klient(self.usta).post(HUJJATLAR, {'xodim': self.usta.id, 'turi': 'pasport'}).status_code, 403)
        h = XodimHujjati.objects.create(xodim=self.usta, turi='pasport')
        self.assertEqual(klient(self.usta).delete(f'{HUJJATLAR}{h.id}/').status_code, 403)
        self.assertTrue(XodimHujjati.objects.filter(pk=h.pk).exists())

    def test_nofaol_kadr_kira_olmaydi(self):
        self.kadr.holat = 'nofaol'
        self.kadr.save()
        self.assertEqual(klient(self.kadr).get(HUJJATLAR).status_code, 403)
