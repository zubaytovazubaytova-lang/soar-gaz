"""Direktor kabineti: barcha jarayon bitta joyda (jurnal, mijozlar, xabar, buyurtma sahifasi,
xarita, tezkor havolalar)."""
import json

from django.contrib.auth.models import Permission
from django.test import Client

from apps.aloqa.models import Xabar
from apps.auth_app.models import AuditYozuv, Foydalanuvchi
from apps.buyurtmalar.models import Buyurtma, BuyurtmaXizmat
from apps.joylashuv.models import Nuqta, Smena
from apps.narxnoma.models import NarxnomaQator
from apps.tushum.models import Tushum
from .tests_direktor import PAROL, Asos


def egasi_klienti(test):
    """Direktor kuzatuvchi: o'zgartirish amallarini tizim egasi (superuser) bajaradi."""
    c = Client()
    assert c.login(username=test.egasi.telefon, password=PAROL)
    return c


class JurnalTestlari(Asos):
    def test_panel_ozgarishi_markaziy_jurnalga_yoziladi(self):
        q = NarxnomaQator.objects.get(narxnoma__tarmoq='ulgurji', narxnoma__bolim='profilaktika', tartib=1)
        forma = {'narxnoma': q.narxnoma_id, 'tartib': q.tartib, 'nomi': q.nomi, 'p_dan': 999999,
                 'p_gacha': '', 'r_dan': q.r_dan, 'r_gacha': '', 'izoh': '', 'faol': 'on'}
        # Direktor (kuzatuvchi) o'zgartira olmaydi
        self.c.post(f'/admin/narxnoma/narxnomaqator/{q.pk}/change/', forma)
        q.refresh_from_db()
        self.assertNotEqual(q.p_dan, 999999)
        self.assertFalse(AuditYozuv.objects.filter(amal='panel_ozgarish').exists())
        # Tizim egasi o'zgartiradi — markaziy jurnalga yoziladi
        r = egasi_klienti(self).post(f'/admin/narxnoma/narxnomaqator/{q.pk}/change/', forma)
        self.assertEqual(r.status_code, 302, r.content[:300])
        q.refresh_from_db()
        self.assertEqual(q.p_dan, 999999)
        y = AuditYozuv.objects.get(amal='panel_ozgarish')
        self.assertEqual(y.kim, self.egasi)
        self.assertIn('narxnomaqator', y.tafsilot)
        self.assertIn("o'zgartirdi", y.tafsilot)

    def test_korish_oddiy_sahifalar_jurnalga_yozilmaydi(self):
        # faqat o'zgarish (qo'shish/o'zgartirish/o'chirish) yoziladi; ro'yxat ochish emas
        self.c.get('/admin/buyurtmalar/buyurtma/')
        self.assertFalse(AuditYozuv.objects.filter(amal='panel_ozgarish').exists())


class MijozlarTestlari(Asos):
    def setUp(self):
        super().setUp()
        self.mijoz = Foydalanuvchi.objects.create_user(
            telefon='+998900000301', password='x-Maxfiy-1', ism='Karim', rol='mijoz', tuman='Chilonzor')
        Buyurtma.objects.create(mijoz=self.mijoz, xizmat='servis')
        Buyurtma.objects.create(mijoz=self.mijoz, xizmat='montaj')

    def test_royxat_va_buyurtmalar_soni(self):
        r = self.c.get('/admin/auth_app/mijoz/')
        self.assertEqual(r.status_code, 200)
        html = r.content.decode()
        self.assertIn('+998900000301', html)
        self.assertNotIn('+998900000203', html)          # xodim bu ro'yxatda yo'q

    def test_sahifada_parol_shifri_korinmaydi(self):
        html = self.c.get(f'/admin/auth_app/mijoz/{self.mijoz.pk}/change/').content.decode()
        self.assertIn('Chilonzor', html)
        self.assertNotIn('pbkdf2', html)
        self.assertNotIn('password', html.lower().split('<form')[1] if '<form' in html else '')

    def test_faqat_oqish(self):
        self.assertEqual(self.c.get('/admin/auth_app/mijoz/add/').status_code, 403)
        self.assertEqual(self.c.get(f'/admin/auth_app/mijoz/{self.mijoz.pk}/delete/').status_code, 403)
        self.c.post(f'/admin/auth_app/mijoz/{self.mijoz.pk}/change/', {'ism': 'Boshqa'})
        self.mijoz.refresh_from_db()
        self.assertEqual(self.mijoz.ism, 'Karim')

    def test_huquqsiz_foydalanuvchi_mijozlarni_kora_olmaydi(self):
        s = Foydalanuvchi.objects.create_user(telefon='+998900000302', password=PAROL, rol='admin', is_staff=True)
        s.user_permissions.add(Permission.objects.get(codename='view_audityozuv'))
        c = Client()
        c.login(username=s.telefon, password=PAROL)
        self.assertEqual(c.get('/admin/auth_app/mijoz/').status_code, 403)


class XabarAmaliTestlari(Asos):
    URL = '/admin/auth_app/xodim/'

    def setUp(self):
        super().setUp()
        self.nofaol = Foydalanuvchi.objects.create(telefon='+998900000303', ism='Eski', rol='xodim', holat='nofaol')

    def yubor(self, matn, tanlangan=None, client=None):
        tanlangan = tanlangan or [self.xodim, self.nofaol]
        return (client or egasi_klienti(self)).post(self.URL, {
            'action': 'xabar_yuborish', '_selected_action': [x.pk for x in tanlangan],
            'index': '0', 'matn': matn}, follow=True)

    def test_faqat_faol_xodimlarga_boradi_va_jurnalga_yoziladi(self):
        self.yubor("Ertaga 8:00 da yig'ilish")
        self.assertEqual(list(Xabar.objects.values_list('xodim__telefon', flat=True)), [self.xodim.telefon])
        self.assertEqual(Xabar.objects.get().yuboruvchi, self.egasi)
        self.assertTrue(AuditYozuv.objects.filter(amal='xabar_yuborildi').exists())

    def test_direktor_kuzatuvchi_xabar_yubora_olmaydi(self):
        self.yubor("Direktor yozdi", client=self.c)
        self.assertFalse(Xabar.objects.exists())

    def test_bosh_yoki_uzun_matn_yuborilmaydi(self):
        self.yubor('   ')
        self.yubor('x' * 501)
        self.assertFalse(Xabar.objects.exists())

    def test_nofaol_xodimlarga_hech_narsa_ketmaydi(self):
        self.yubor('Salom', tanlangan=[self.nofaol])
        self.assertFalse(Xabar.objects.exists())

    def test_huquqsiz_foydalanuvchi_yubora_olmaydi(self):
        s = Foydalanuvchi.objects.create_user(telefon='+998900000304', password=PAROL, rol='admin', is_staff=True)
        s.user_permissions.add(Permission.objects.get(codename='view_xodim'))
        c = Client()
        c.login(username=s.telefon, password=PAROL)
        self.yubor('Salom', client=c)
        self.assertFalse(Xabar.objects.exists())

    def test_xodim_portalida_xabar_korinadi(self):
        from rest_framework.test import APIClient
        from rest_framework_simplejwt.tokens import RefreshToken
        self.yubor('Salom jamoa')
        api = APIClient()
        api.credentials(HTTP_AUTHORIZATION='Bearer ' + str(RefreshToken.for_user(self.xodim).access_token))
        self.assertEqual(api.get('/api/aloqa/').json()['xabarlar'][0]['matn'], 'Salom jamoa')


class BuyurtmaSahifasiTestlari(Asos):
    def test_xizmat_va_tolovlar_bir_sahifada(self):
        q = NarxnomaQator.objects.get(narxnoma__tarmoq='ulgurji', narxnoma__bolim='profilaktika', tartib=1)
        b = Buyurtma.objects.create(xodim=self.xodim, xizmat='servis', tarmoq='ulgurji', tasdiq_summa=233500)
        BuyurtmaXizmat.objects.create(buyurtma=b, qator=q, nomi='Gaz plitasi sinov-nom', ustun='p',
                                      ustun_nomi='profilaktika', narx_dan=233500, soni=1)
        Tushum.objects.create(xodim=self.xodim, buyurtma=b, summa=123456, tarmoq='ulgurji')
        r = self.c.get(f'/admin/buyurtmalar/buyurtma/{b.pk}/change/')
        self.assertEqual(r.status_code, 200)
        html = r.content.decode()
        self.assertIn('Gaz plitasi sinov-nom', html)
        self.assertIn('123456', html)
        self.assertIn('Olingan pul', html)

    def test_inline_orqali_ozgartirib_bolmaydi(self):
        b = Buyurtma.objects.create(xodim=self.xodim, xizmat='servis')
        t = Tushum.objects.create(xodim=self.xodim, buyurtma=b, summa=5000)
        html = self.c.get(f'/admin/buyurtmalar/buyurtma/{b.pk}/change/').content.decode()
        self.assertNotIn('tushumlar-0-summa', html)            # tahrirlanadigan maydon yo'q
        self.assertNotIn('id_tushumlar-0-DELETE', html)

    def test_direktor_xodim_tayinlay_olmaydi_egasi_oladi(self):
        b = Buyurtma.objects.create(xizmat='servis')
        malumot = {
            'xizmat': 'servis', 'tarmoq': 'aholi', 'holat': 'qabul', 'xodim': self.xodim.pk,
            'tuman': '', 'manzil': '', 'tavsif': '', 'vaqt_istagi': '', 'mijoz_ism': '', 'mijoz_telefon': '',
            'natija': '', 'material': '', 'xizmat_nomi': '',
            'xizmatlar-TOTAL_FORMS': '0', 'xizmatlar-INITIAL_FORMS': '0',
            'tushumlar-TOTAL_FORMS': '0', 'tushumlar-INITIAL_FORMS': '0'}
        url = f'/admin/buyurtmalar/buyurtma/{b.pk}/change/'
        self.c.post(url, malumot)                                           # direktor — kuzatuvchi
        b.refresh_from_db()
        self.assertIsNone(b.xodim)
        r = egasi_klienti(self).post(url, malumot)                          # tizim egasi
        self.assertEqual(r.status_code, 302, r.content[:400])
        b.refresh_from_db()
        self.assertEqual((b.xodim, b.holat), (self.xodim, 'qabul'))


class XaritaTestlari(Asos):
    def setUp(self):
        super().setUp()
        s = Smena.objects.create(xodim=self.xodim)
        Nuqta.objects.create(smena=s, xodim=self.xodim, lat=41.3111, lng=69.2797)

    def test_sahifa_va_malumot(self):
        self.assertEqual(self.c.get('/admin/xarita/').status_code, 200)
        r = self.c.get('/admin/xarita/malumot/')
        self.assertEqual(r.status_code, 200)
        j = json.loads(r.content)
        self.assertEqual(len(j), 1)
        self.assertEqual((j[0]['ism'], j[0]['lat'], j[0]['aloqada']), ('Aziz', 41.3111, True))

    def test_korish_jurnalga_yoziladi_va_toshib_ketmaydi(self):
        for _ in range(4):
            self.c.get('/admin/xarita/malumot/')
        self.assertEqual(AuditYozuv.objects.filter(amal='joylashuv_korildi').count(), 1)

    def test_huquqsiz_va_tokensiz_kora_olmaydi(self):
        s = Foydalanuvchi.objects.create_user(telefon='+998900000305', password=PAROL, rol='admin', is_staff=True)
        s.user_permissions.add(Permission.objects.get(codename='view_audityozuv'))
        c = Client()
        c.login(username=s.telefon, password=PAROL)
        self.assertEqual(c.get('/admin/xarita/').status_code, 403)
        self.assertEqual(c.get('/admin/xarita/malumot/').status_code, 403)
        anonim = Client()
        self.assertEqual(anonim.get('/admin/xarita/').status_code, 302)           # kirish sahifasiga
        self.assertEqual(anonim.get('/admin/xarita/malumot/').status_code, 302)

    def test_xarita_malumotida_xodim_ismi_xavfsiz_beriladi(self):
        Foydalanuvchi.objects.filter(pk=self.xodim.pk).update(ism='<img src=x onerror=alert(1)>')
        html = self.c.get('/admin/xarita/').content.decode()
        self.assertNotIn('<img src=x', html)          # ism sahifaga HTML sifatida qo'yilmaydi


class HavolalarTestlari(Asos):
    def test_direktor_barcha_tezkor_havolalarni_koradi(self):
        html = self.c.get('/admin/').content.decode()
        for nom in ('Kutilayotgan tushumlar', 'Yangi buyurtmalar', 'Xodimlar xaritasi',
                    'Mijozlar', 'Narxnoma', 'Faoliyat jurnali'):
            self.assertIn(nom, html, nom)
        self.assertIn('href="/admin/xarita/"', html)
        self.assertNotIn('Xodimlarga xabar', html)             # xabar yuborish — kuzatuvchida yo'q
        self.assertIn('Xodimlarga xabar', egasi_klienti(self).get('/admin/').content.decode())

    def test_huquqsiz_foydalanuvchi_havolalarni_kormaydi(self):
        s = Foydalanuvchi.objects.create_user(telefon='+998900000306', password=PAROL, rol='admin', is_staff=True)
        s.user_permissions.add(Permission.objects.get(codename='view_audityozuv'))
        c = Client()
        c.login(username=s.telefon, password=PAROL)
        html = c.get('/admin/').content.decode()
        self.assertIn('Faoliyat jurnali', html)
        for nom in ('Kutilayotgan tushumlar', 'Xodimlar xaritasi', 'Xodimlarga xabar'):
            self.assertNotIn(nom, html, nom)
