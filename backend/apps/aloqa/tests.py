"""Administratordan xodimga xabar: yuborish, o'qish va ruxsatlar."""
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from apps.auth_app.models import AuditYozuv, Foydalanuvchi
from .models import Xabar

URL = '/api/aloqa/'
ADMIN_URL = '/api/aloqa/admin/'


def klient(user):
    c = APIClient()
    c.credentials(HTTP_AUTHORIZATION='Bearer ' + str(RefreshToken.for_user(user).access_token))
    return c


class Asos(TestCase):
    def setUp(self):
        mk = Foydalanuvchi.objects.create
        self.x1 = mk(telefon='+998900000031', ism='Ali', rol='xodim', holat='faol')
        self.x2 = mk(telefon='+998900000032', ism='Vali', rol='xodim', holat='faol')
        self.nofaol = mk(telefon='+998900000033', ism='Eski', rol='xodim', holat='nofaol')
        self.admin = mk(telefon='+998900000034', ism='Admin', rol='admin', holat='faol', is_superuser=True)
        self.mijoz = mk(telefon='+998900000035', rol='mijoz')
        self.c1, self.c2, self.a, self.m = (klient(self.x1), klient(self.x2),
                                            klient(self.admin), klient(self.mijoz))

    def yubor(self, **kw):
        return self.a.post(ADMIN_URL, kw, format='json')


class YuborishTestlari(Asos):
    def test_hammaga_faqat_faol_xodimlarga(self):
        r = self.yubor(matn='Ertaga 8:00 da yig\'ilish', hammasi=True)
        self.assertEqual(r.status_code, 201)
        self.assertEqual(r.json()['yuborildi'], 2)
        self.assertEqual(set(Xabar.objects.values_list('xodim__telefon', flat=True)),
                         {self.x1.telefon, self.x2.telefon})
        self.assertTrue(AuditYozuv.objects.filter(amal='xabar_yuborildi').exists())

    def test_tanlanganlarga(self):
        self.assertEqual(self.yubor(matn='Salom', xodimlar=[self.x1.pk]).status_code, 201)
        self.assertEqual(Xabar.objects.get().xodim, self.x1)

    def test_notogri_qabulchi_hech_narsa_yubormaydi(self):
        for idlar in ([self.nofaol.pk], [self.mijoz.pk], [self.admin.pk], [99999],
                      [self.x1.pk, 99999], ['x'], [], 'abc', None):
            r = self.yubor(matn='Salom', xodimlar=idlar)
            self.assertEqual(r.status_code, 400, idlar)
        self.assertFalse(Xabar.objects.exists())

    def test_matn_tekshiruvi(self):
        for matn in ('', '   ', None, 'x' * 501):
            self.assertEqual(self.yubor(matn=matn, hammasi=True).status_code, 400, repr(matn)[:20])
        self.assertEqual(self.yubor(matn='x' * 500, hammasi=True).status_code, 201)

    def test_hammasi_faqat_true_bolsa(self):
        self.assertEqual(self.yubor(matn='Salom', hammasi='true').status_code, 400)
        self.assertFalse(Xabar.objects.exists())

    def test_xodim_mijoz_tokensiz_yubora_olmaydi(self):
        for c in (self.c1, self.m):
            self.assertEqual(c.post(ADMIN_URL, {'matn': 'x', 'hammasi': True}, format='json').status_code, 403)
            self.assertEqual(c.get(ADMIN_URL).status_code, 403)
        self.assertEqual(APIClient().post(ADMIN_URL, {'matn': 'x', 'hammasi': True}, format='json').status_code, 401)
        self.assertFalse(Xabar.objects.exists())

    def test_admin_tarixi(self):
        self.yubor(matn='Salom', hammasi=True)
        self.assertEqual(len(self.a.get(ADMIN_URL).json()), 2)


class XodimTestlari(Asos):
    def test_xodim_faqat_oz_xabarlarini_koradi(self):
        self.yubor(matn='Hammaga', hammasi=True)
        self.yubor(matn='Faqat Alig\'a', xodimlar=[self.x1.pk])
        r1 = self.c1.get(URL).json()
        r2 = self.c2.get(URL).json()
        self.assertEqual((r1['oqilmagan'], len(r1['xabarlar'])), (2, 2))
        self.assertEqual((r2['oqilmagan'], len(r2['xabarlar'])), (1, 1))

    def test_oqildi_faqat_oziniki(self):
        self.yubor(matn='Hammaga', hammasi=True)
        self.assertEqual(self.c1.post(URL + 'oqildi/').json()['oqilmagan'], 0)
        self.assertEqual(self.c1.get(URL).json()['oqilmagan'], 0)
        self.assertEqual(self.c2.get(URL).json()['oqilmagan'], 1)   # boshqasiniki tegilmadi
        # admin tarixida kim o'qigani ko'rinadi
        oqilgan = {x['xodim_ism']: x['oqilgan'] is not None for x in self.a.get(ADMIN_URL).json()}
        self.assertEqual(oqilgan, {'Ali': True, 'Vali': False})

    def test_mijoz_va_admin_xodim_royxatini_kora_olmaydi(self):
        for c in (self.m, self.a):
            self.assertEqual(c.get(URL).status_code, 403)
            self.assertEqual(c.post(URL + 'oqildi/').status_code, 403)

    def test_nofaol_xodim_koraolmaydi(self):
        self.x1.holat = 'nofaol'
        self.x1.save()
        self.assertEqual(self.c1.get(URL).status_code, 403)

    def test_xabar_limiti(self):
        for i in range(35):
            Xabar.objects.create(xodim=self.x1, matn=str(i))
        r = self.c1.get(URL).json()
        self.assertEqual(len(r['xabarlar']), 30)
        self.assertEqual(r['oqilmagan'], 35)
