"""Mijoz bilan hujjatlar: kvitansiya (mijoz telefoni va turar joyi bilan) va SMS orqali tasdiqlanadigan shartnoma."""
import re
from datetime import timedelta
from unittest import mock

from django.core.cache import cache
from django.test import Client, TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from apps.auth_app.models import AuditYozuv, Foydalanuvchi
from apps.buyurtmalar.models import Buyurtma, BuyurtmaXizmat
from apps.narxnoma.models import NarxnomaQator
from apps.tushum.models import Tushum
from .models import Kvitansiya, Shartnoma, Sozlama

KV = '/api/hujjatlar/kvitansiya/'
SH = '/api/hujjatlar/shartnoma/'


def klient(user):
    c = APIClient()
    c.credentials(HTTP_AUTHORIZATION='Bearer ' + str(RefreshToken.for_user(user).access_token))
    return c


class Asos(TestCase):
    def setUp(self):
        cache.clear()
        self.addCleanup(cache.clear)
        yamoq = mock.patch('apps.hujjatlar.xizmat.sms_yubor', return_value=True)
        self.sms = yamoq.start()
        self.addCleanup(yamoq.stop)

        mk = Foydalanuvchi.objects.create
        self.xodim = mk(telefon='+998900000401', ism='Aziz', rol='xodim', holat='faol')
        self.boshqa = mk(telefon='+998900000402', ism='Bobur', rol='xodim', holat='faol')
        self.admin = mk(telefon='+998900000403', ism='Admin', rol='admin', holat='faol', is_superuser=True)
        self.mijoz = mk(telefon='+998900000404', ism='Karim', rol='mijoz')
        self.x, self.v, self.a, self.m = (klient(self.xodim), klient(self.boshqa),
                                          klient(self.admin), klient(self.mijoz))
        self.b = Buyurtma.objects.create(
            mijoz=self.mijoz, xodim=self.xodim, xizmat='servis', tarmoq='aholi', tuman='Chilonzor tumani',
            manzil='Chilonzor 5-mavze, 12-uy', mijoz_ism='Karim Rahimov', mijoz_telefon='+998901234567',
            tasdiq_summa=500000)
        q = NarxnomaQator.objects.get(narxnoma__tarmoq='aholi', narxnoma__bolim='buyurtma', tartib=1)
        BuyurtmaXizmat.objects.create(buyurtma=self.b, qator=q, nomi=q.nomi, ustun='p',
                                      ustun_nomi='profilaktika', narx_dan=30236, soni=2)

    def tushum(self, summa=150000, buyurtma=True, xodim=None, **kw):
        return Tushum.objects.create(xodim=xodim or self.xodim, summa=summa,
                                     buyurtma=self.b if buyurtma else None, **kw)

    def tasdiqla_sozlama(self):
        s = Sozlama.olish()
        s.shartnoma_tasdiqlangan = True
        s.save()


class KvitansiyaTestlari(Asos):
    def test_buyurtmadagi_aloqa_bilan_chiqariladi_va_sms_ketadi(self):
        t = self.tushum()
        r = self.x.post(KV, {'tushum': t.pk}, format='json')
        self.assertEqual(r.status_code, 201, r.content)
        j = r.json()
        self.assertTrue(re.fullmatch(r'KV-\d{4}-000001', j['raqam']))
        self.assertEqual((j['mijoz_ism'], j['mijoz_telefon']), ('Karim Rahimov', '+998901234567'))
        self.assertEqual(j['manzil'], 'Chilonzor tumani, Chilonzor 5-mavze, 12-uy')       # TURAR JOY
        self.assertEqual((j['summa'], j['sms_holat'], j['sms_yuborildi']), (150000, 'yuborildi', True))
        # SMS mijoz telefoniga, raqam va havola bilan
        telefon, matn = self.sms.call_args[0]
        self.assertEqual(telefon, '+998901234567')
        self.assertIn(j['raqam'], matn)
        self.assertIn(f"/kvitansiya/{j['token']}/", matn)
        self.assertIn('150 000', matn)
        self.assertTrue(AuditYozuv.objects.filter(amal='kvitansiya_berildi').exists())

    def test_telefon_va_turar_joy_majburiy_buyurtmasiz_qolda_kiritiladi(self):
        t = self.tushum(buyurtma=False)
        r = self.x.post(KV, {'tushum': t.pk}, format='json')
        self.assertEqual(r.status_code, 400)                     # ma'lumot yo'q
        r = self.x.post(KV, {'tushum': t.pk, 'mijoz_ism': 'Vali', 'mijoz_telefon': '90 123-45-67'}, format='json')
        self.assertEqual(r.status_code, 400)
        self.assertIn('turar joy', r.json()['detail'])           # manzilsiz kvitansiya yo'q
        r = self.x.post(KV, {'tushum': t.pk, 'mijoz_ism': 'Vali', 'mijoz_telefon': '90 123-45-67',
                             'manzil': 'Yunusobod 3'}, format='json')
        self.assertEqual(r.status_code, 201, r.content)
        self.assertEqual((r.json()['mijoz_telefon'], r.json()['manzil']), ('+998901234567', 'Yunusobod 3'))

    def test_notogri_telefon_rad_etiladi(self):
        for tel in ('123', '+12025550123', 'abc', '+99890123456789'):
            t = self.tushum()
            r = self.x.post(KV, {'tushum': t.pk, 'mijoz_telefon': tel}, format='json')
            self.assertEqual(r.status_code, 400, tel)
        self.assertFalse(Kvitansiya.objects.exists())
        self.sms.assert_not_called()

    def test_xodim_kiritgan_telefon_buyurtmadagidan_ustun(self):
        t = self.tushum()
        r = self.x.post(KV, {'tushum': t.pk, 'mijoz_telefon': '+998939998877'}, format='json')
        self.assertEqual(r.json()['mijoz_telefon'], '+998939998877')
        self.assertEqual(self.sms.call_args[0][0], '+998939998877')

    def test_bitta_tushumga_bitta_kvitansiya_sms_takrorlanmaydi(self):
        t = self.tushum()
        self.x.post(KV, {'tushum': t.pk}, format='json')
        r = self.x.post(KV, {'tushum': t.pk}, format='json')
        self.assertEqual((r.status_code, r.json()['yangi']), (200, False))
        self.assertEqual(Kvitansiya.objects.count(), 1)
        self.assertEqual(self.sms.call_count, 1)

    def test_raqamlar_ketma_ket(self):
        n = [self.x.post(KV, {'tushum': self.tushum(summa=1000 * (i + 1)).pk}, format='json').json()['raqam']
             for i in range(3)]
        self.assertEqual([r[-6:] for r in n], ['000001', '000002', '000003'])
        self.assertEqual(len(set(n)), 3)

    def test_rad_etilgan_tushumga_kvitansiya_yoq(self):
        t = self.tushum(holat='rad')
        self.assertEqual(self.x.post(KV, {'tushum': t.pk}, format='json').status_code, 409)

    def test_sms_ixtiyoriy_va_xato_hujjatni_buzmaydi(self):
        r = self.x.post(KV, {'tushum': self.tushum().pk, 'sms': False}, format='json')
        self.assertEqual((r.status_code, r.json()['sms_holat']), (201, 'kutilmoqda'))
        self.sms.assert_not_called()
        self.sms.return_value = False
        r = self.x.post(KV, {'tushum': self.tushum(summa=2000).pk}, format='json')
        self.assertEqual((r.status_code, r.json()['sms_holat'], r.json()['sms_yuborildi']), (201, 'xato', False))

    def test_ruxsatlar(self):
        t = self.tushum()
        self.assertEqual(self.v.post(KV, {'tushum': t.pk}, format='json').status_code, 403)     # boshqa xodim
        self.assertEqual(self.m.post(KV, {'tushum': t.pk}, format='json').status_code, 403)
        self.assertEqual(APIClient().post(KV, {'tushum': t.pk}, format='json').status_code, 401)
        self.assertEqual(self.x.post(KV, {'tushum': 99999}, format='json').status_code, 404)
        self.assertEqual(self.a.post(KV, {'tushum': t.pk}, format='json').status_code, 201)     # admin mumkin
        self.assertFalse(Kvitansiya.objects.exclude(tushum=t).exists())

    def test_hujjat_ozgarmaydi_profil_ozgarsa(self):
        k = self.x.post(KV, {'tushum': self.tushum().pk}, format='json').json()
        Buyurtma.objects.filter(pk=self.b.pk).update(mijoz_telefon='+998909999999', manzil='Boshqa joy')
        Tushum.objects.filter(pk=k['tushum_id']).update(summa=1)
        html = Client().get(f"/kvitansiya/{k['token']}/").content.decode()
        self.assertIn('+998901234567', html)
        self.assertIn('Chilonzor 5-mavze', html)
        self.assertNotIn('Boshqa joy', html)

    def test_qayta_sms(self):
        k = self.x.post(KV, {'tushum': self.tushum().pk, 'sms': False}, format='json').json()
        r = self.x.post(f"{KV}{k['id']}/sms/")
        self.assertEqual((r.status_code, r.json()['sms_holat']), (200, 'yuborildi'))
        self.assertEqual(self.x.post(f"{KV}{k['id']}/sms/").status_code, 429)          # 60 soniya
        self.assertEqual(self.v.post(f"{KV}{k['id']}/sms/").status_code, 403)

    def test_royxat_faqat_oziniki(self):
        self.x.post(KV, {'tushum': self.tushum().pk}, format='json')
        t2 = self.tushum(xodim=self.boshqa)
        self.v.post(KV, {'tushum': t2.pk, 'mijoz_ism': 'X', 'mijoz_telefon': '+998901112233', 'manzil': 'Y'},
                    format='json')
        self.assertEqual(len(self.x.get(KV).json()), 1)
        self.assertEqual(len(self.a.get(KV).json()), 2)
        self.assertEqual(self.m.get(KV).status_code, 403)

    def test_bekor_qilish_faqat_admin_sabab_bilan(self):
        k = self.x.post(KV, {'tushum': self.tushum().pk}, format='json').json()
        self.assertEqual(self.x.post(f"{KV}{k['id']}/bekor/", {'sabab': 'x'}, format='json').status_code, 403)
        self.assertEqual(self.a.post(f"{KV}{k['id']}/bekor/", {}, format='json').status_code, 400)
        r = self.a.post(f"{KV}{k['id']}/bekor/", {'sabab': 'Xato kiritilgan'}, format='json')
        self.assertEqual((r.status_code, r.json()['holat']), (200, 'bekor'))
        self.assertTrue(AuditYozuv.objects.filter(amal='kvitansiya_bekor').exists())
        # bekor qilinganga SMS yuborilmaydi, qayta bekor qilib ham bo'lmaydi
        cache.clear()
        self.assertEqual(self.x.post(f"{KV}{k['id']}/sms/").status_code, 409)
        self.assertEqual(self.a.post(f"{KV}{k['id']}/bekor/", {'sabab': 'x'}, format='json').status_code, 404)

    def test_tushum_royxatida_kvitansiya_korinadi(self):
        t = self.tushum()
        self.assertIsNone(self.x.get('/api/tushum/').json()['yozuvlar'][0]['kvitansiya'])
        k = self.x.post(KV, {'tushum': t.pk}, format='json').json()
        y = self.x.get('/api/tushum/').json()['yozuvlar'][0]
        self.assertEqual(y['kvitansiya']['raqam'], k['raqam'])
        self.assertEqual(y['kvitansiya']['url'], f"/kvitansiya/{k['token']}/")


class KvitansiyaSahifasiTestlari(Asos):
    def ochish(self, **kw):
        k = self.x.post(KV, {'tushum': self.tushum(**kw).pk}, format='json').json()
        return k, Client().get(f"/kvitansiya/{k['token']}/")

    def test_sahifada_mijoz_telefoni_va_turar_joyi(self):
        k, r = self.ochish()
        self.assertEqual(r.status_code, 200)
        html = r.content.decode()
        for qism in (k['raqam'], 'Karim Rahimov', '+998901234567', 'Chilonzor 5-mavze, 12-uy', '150 000', 'Aziz'):
            self.assertIn(qism, html)
        self.assertEqual(r['Cache-Control'], 'no-store')
        self.assertIn('noindex', r['X-Robots-Tag'])

    def test_notogri_kod_404(self):
        self.assertEqual(Client().get('/kvitansiya/yoq-bunday-kod/').status_code, 404)

    def test_bekor_kvitansiyada_belgi(self):
        k, _ = self.ochish()
        self.a.post(f"{KV}{k['id']}/bekor/", {'sabab': 'Xato'}, format='json')
        html = Client().get(f"/kvitansiya/{k['token']}/").content.decode()
        self.assertIn('BEKOR', html)
        self.assertIn('Xato', html)

    def test_ism_html_sifatida_ishlamaydi(self):
        k = self.x.post(KV, {'tushum': self.tushum().pk, 'mijoz_ism': '<script>alert(1)</script>'},
                        format='json').json()
        html = Client().get(f"/kvitansiya/{k['token']}/").content.decode()
        self.assertNotIn('<script>alert(1)', html)
        self.assertIn('&lt;script&gt;', html)


class ShartnomaTestlari(Asos):
    def setUp(self):
        super().setUp()
        self.tasdiqla_sozlama()

    def tuz(self, client=None, **qoshimcha):
        return (client or self.x).post(SH, dict({'buyurtma': self.b.pk}, **qoshimcha), format='json')

    def kod(self):
        """Yuborilgan oxirgi SMS'dagi 6 xonali kod."""
        return re.search(r'kodi: (\d{6})', self.sms.call_args[0][1]).group(1)

    def test_matn_tasdiqlanmaguncha_shartnoma_tuzilmaydi(self):
        s = Sozlama.olish()
        s.shartnoma_tasdiqlangan = False
        s.save()
        r = self.tuz()
        self.assertEqual(r.status_code, 409)
        self.assertIn('tasdiqlanmagan', r.json()['detail'])
        self.assertFalse(Shartnoma.objects.exists())

    def test_summa_tasdiqlanmagan_buyurtmaga_tuzilmaydi(self):
        Buyurtma.objects.filter(pk=self.b.pk).update(tasdiq_summa=None)
        self.assertEqual(self.tuz().status_code, 409)

    def test_tuzish_mijoz_telefoni_turar_joyi_xizmat_va_summa_bilan(self):
        r = self.tuz()
        self.assertEqual(r.status_code, 201, r.content)
        j = r.json()
        self.assertTrue(re.fullmatch(r'SH-\d{4}-000001', j['raqam']))
        self.assertEqual((j['holat'], j['summa']), ('qoralama', 500000))
        s = Shartnoma.objects.get()
        for qism in ('Karim Rahimov', '+998901234567', 'Chilonzor 5-mavze', '500 000', j['raqam'], 'PG-2x',
                     '× 2', 'Aziz'):
            self.assertIn(qism, s.matn, qism)
        self.assertEqual(s.xizmatlar[0]['soni'], 2)
        self.assertTrue(AuditYozuv.objects.filter(amal='shartnoma_tuzildi').exists())

    def test_telefon_va_manzil_majburiy(self):
        Buyurtma.objects.filter(pk=self.b.pk).update(mijoz_telefon='', manzil='', tuman='')
        self.assertEqual(self.tuz().status_code, 400)
        r = self.tuz(mijoz_telefon='+998931112233', manzil='Sergeli 4')
        self.assertEqual(r.status_code, 201, r.content)

    def test_ruxsatlar_va_takroriy_tuzish(self):
        self.assertEqual(self.tuz(self.v).status_code, 403)
        self.assertEqual(self.tuz(self.m).status_code, 403)
        self.assertEqual(self.tuz(APIClient()).status_code, 401)
        self.assertEqual(self.tuz().status_code, 201)
        r = self.tuz()
        self.assertEqual((r.status_code, Shartnoma.objects.count()), (200, 1))      # mavjudi qaytadi

    def test_sms_kod_orqali_tasdiqlash(self):
        sh = self.tuz().json()
        r = self.x.post(f"{SH}{sh['id']}/kod/")
        self.assertEqual((r.status_code, r.json()['holat']), (200, 'tasdiq_kutilmoqda'))
        self.assertEqual(self.sms.call_args[0][0], '+998901234567')          # mijoz telefoniga
        kod = self.kod()
        # xato kod
        r = self.x.post(f"{SH}{sh['id']}/tasdiq/", {'kod': '000000' if kod != '000000' else '111111'}, format='json')
        self.assertEqual(r.status_code, 400)
        self.assertIn('urinish qoldi', r.json()['detail'])
        # to'g'ri kod
        r = self.x.post(f"{SH}{sh['id']}/tasdiq/", {'kod': kod}, format='json')
        self.assertEqual((r.status_code, r.json()['holat']), (200, 'tasdiqlandi'))
        self.assertIsNotNone(Shartnoma.objects.get().tasdiq_vaqti)
        self.assertIn('tasdiqlandi', self.sms.call_args[0][1])               # mijozga tasdiq SMS'i
        self.assertTrue(AuditYozuv.objects.filter(amal='shartnoma_tasdiq').exists())
        # kod bir martalik
        self.assertEqual(self.x.post(f"{SH}{sh['id']}/tasdiq/", {'kod': kod}, format='json').status_code, 409)

    def test_kod_saqlanmaydi_faqat_xesh(self):
        sh = self.tuz().json()
        self.x.post(f"{SH}{sh['id']}/kod/")
        s = Shartnoma.objects.get()
        self.assertNotIn(self.kod(), s.kod_xesh)
        self.assertEqual(len(s.kod_xesh), 40)

    def test_kodni_qayta_yuborish_cheklangan(self):
        sh = self.tuz().json()
        self.assertEqual(self.x.post(f"{SH}{sh['id']}/kod/").status_code, 200)
        self.assertEqual(self.x.post(f"{SH}{sh['id']}/kod/").status_code, 429)        # 60 soniya

    def test_kod_muddati_tugaydi(self):
        sh = self.tuz().json()
        self.x.post(f"{SH}{sh['id']}/kod/")
        kod = self.kod()
        Shartnoma.objects.update(kod_vaqti=timezone.now() - timedelta(minutes=11))
        r = self.x.post(f"{SH}{sh['id']}/tasdiq/", {'kod': kod}, format='json')
        self.assertEqual(r.status_code, 409)
        self.assertEqual(Shartnoma.objects.get().holat, 'tasdiq_kutilmoqda')

    def test_taxmin_qilib_bolmaydi_urinishlar_cheklangan(self):
        sh = self.tuz().json()
        self.x.post(f"{SH}{sh['id']}/kod/")
        kod = self.kod()
        xato = '123456' if kod != '123456' else '654321'
        for _ in range(5):
            self.assertEqual(self.x.post(f"{SH}{sh['id']}/tasdiq/", {'kod': xato}, format='json').status_code, 400)
        # 6-urinish: to'g'ri kod ham o'tmaydi — yangi kod kerak
        r = self.x.post(f"{SH}{sh['id']}/tasdiq/", {'kod': kod}, format='json')
        self.assertEqual(r.status_code, 429)
        self.assertEqual(Shartnoma.objects.get().holat, 'tasdiq_kutilmoqda')

    def test_kodsiz_tasdiqlab_bolmaydi(self):
        sh = self.tuz().json()
        self.assertEqual(self.x.post(f"{SH}{sh['id']}/tasdiq/", {'kod': '123456'}, format='json').status_code, 409)
        self.assertEqual(self.x.post(f"{SH}{sh['id']}/tasdiq/", {}, format='json').status_code, 409)

    def test_sms_ketmasa_kod_yaratilmaydi(self):
        sh = self.tuz().json()
        self.sms.return_value = False
        r = self.x.post(f"{SH}{sh['id']}/kod/")
        self.assertEqual(r.status_code, 502)
        s = Shartnoma.objects.get()
        self.assertEqual((s.holat, s.kod_xesh), ('qoralama', ''))

    def test_boshqa_xodim_kod_yubora_va_tasdiqlay_olmaydi(self):
        sh = self.tuz().json()
        self.assertEqual(self.v.post(f"{SH}{sh['id']}/kod/").status_code, 403)
        self.assertEqual(self.v.post(f"{SH}{sh['id']}/tasdiq/", {'kod': '1'}, format='json').status_code, 403)
        self.assertEqual(self.v.post(f"{SH}{sh['id']}/qogoz/").status_code, 403)

    def test_qogozga_imzolandi(self):
        sh = self.tuz().json()
        r = self.x.post(f"{SH}{sh['id']}/qogoz/")
        self.assertEqual((r.status_code, r.json()['holat']), (200, 'qogoz'))
        self.assertEqual(self.x.post(f"{SH}{sh['id']}/qogoz/").status_code, 409)
        self.assertEqual(self.x.post(f"{SH}{sh['id']}/kod/").status_code, 409)         # kod endi kerak emas

    def test_bekor_qilish_qoidalari(self):
        sh = self.tuz().json()
        self.assertEqual(self.x.post(f"{SH}{sh['id']}/bekor/", {}, format='json').status_code, 400)   # sabab
        self.x.post(f"{SH}{sh['id']}/qogoz/")
        # tasdiqlangan shartnomani xodim bekor qila olmaydi, admin qila oladi
        self.assertEqual(self.x.post(f"{SH}{sh['id']}/bekor/", {'sabab': 'x'}, format='json').status_code, 403)
        r = self.a.post(f"{SH}{sh['id']}/bekor/", {'sabab': 'Mijoz rad etdi'}, format='json')
        self.assertEqual((r.status_code, r.json()['holat']), (200, 'bekor'))
        self.assertTrue(AuditYozuv.objects.filter(amal='shartnoma_bekor').exists())

    def test_bekordan_keyin_yangi_shartnoma_tuzish_mumkin(self):
        sh = self.tuz().json()
        self.x.post(f"{SH}{sh['id']}/bekor/", {'sabab': 'Xato'}, format='json')
        r = self.tuz()
        self.assertEqual(r.status_code, 201)
        self.assertNotEqual(r.json()['raqam'], sh['raqam'])
        self.assertEqual(Shartnoma.objects.exclude(holat='bekor').count(), 1)

    def test_ochiq_sahifa(self):
        sh = self.tuz().json()
        r = Client().get(f"/shartnoma/{sh['token']}/")
        self.assertEqual(r.status_code, 200)
        html = r.content.decode()
        self.assertIn('hali tasdiqlanmagan', html)
        self.x.post(f"{SH}{sh['id']}/kod/")
        kod = self.kod()
        self.x.post(f"{SH}{sh['id']}/tasdiq/", {'kod': kod}, format='json')
        html = Client().get(f"/shartnoma/{sh['token']}/").content.decode()
        self.assertIn('SMS kod orqali tasdiqladi', html)
        self.assertIn('+998 90 *** ** 67', html)                   # telefon niqoblangan
        self.assertNotIn(kod, html)                                # kod sahifada yo'q
        self.assertEqual(r['Cache-Control'], 'no-store')
        self.assertEqual(Client().get('/shartnoma/yoq/').status_code, 404)

    def test_buyurtma_royxatida_shartnoma_faqat_xodim_va_adminga(self):
        sh = self.tuz().json()
        j = self.x.get('/api/buyurtmalar/').json()[0]['shartnoma']
        self.assertEqual((j['raqam'], j['holat']), (sh['raqam'], 'qoralama'))
        self.assertEqual(self.a.get('/api/buyurtmalar/').json()[0]['shartnoma']['raqam'], sh['raqam'])
        self.assertIsNone(self.m.get('/api/buyurtmalar/').json()[0]['shartnoma'])


class DjangoPaneliTestlari(Asos):
    """Direktor (Django paneli) hujjatlarni ko'radi, bekor qiladi va shartnoma matnini tasdiqlaydi."""

    def setUp(self):
        super().setUp()
        import io
        from django.contrib.auth.models import Group
        from django.core.management import call_command
        call_command('direktor_guruhi', stdout=io.StringIO())
        self.direktor = Foydalanuvchi.objects.create_user(
            telefon='+998900000411', password='Parol-12345!', rol='admin', ism='Direktor', holat='faol', is_staff=True)
        self.direktor.groups.add(Group.objects.get(name='Direktor'))
        self.c = Client()
        self.assertTrue(self.c.login(username=self.direktor.telefon, password='Parol-12345!'))

    def test_direktor_hujjatlarni_koradi(self):
        k = self.x.post(KV, {'tushum': self.tushum().pk}, format='json').json()
        r = self.c.get('/admin/hujjatlar/kvitansiya/')
        self.assertEqual(r.status_code, 200)
        html = r.content.decode()
        for qism in (k['raqam'], '+998901234567', 'Chilonzor 5-mavze'):
            self.assertIn(qism, html)
        self.assertEqual(self.c.get('/admin/hujjatlar/shartnoma/').status_code, 200)

    def test_hujjatlarni_ozgartirib_ochirib_bolmaydi(self):
        k = self.x.post(KV, {'tushum': self.tushum().pk}, format='json').json()
        self.assertEqual(self.c.get('/admin/hujjatlar/kvitansiya/add/').status_code, 403)
        self.assertEqual(self.c.get(f"/admin/hujjatlar/kvitansiya/{k['id']}/delete/").status_code, 403)

    def test_direktor_kvitansiyani_bekor_qila_olmaydi_egasi_qiladi(self):
        k = self.x.post(KV, {'tushum': self.tushum().pk}, format='json').json()
        malumot = {'action': 'bekor_qilish', '_selected_action': [k['id']], 'index': '0', 'sabab': 'Xato summa'}
        self.c.post('/admin/hujjatlar/kvitansiya/', malumot)                   # direktor — kuzatuvchi
        self.assertEqual(Kvitansiya.objects.get().holat, 'amal')
        egasi = Foydalanuvchi.objects.create_user(
            telefon='+998900000412', password='Parol-12345!', rol='admin', ism='Egasi', holat='faol',
            is_staff=True, is_superuser=True)
        e = Client()
        self.assertTrue(e.login(username=egasi.telefon, password='Parol-12345!'))
        e.post('/admin/hujjatlar/kvitansiya/', dict(malumot, sabab=''))
        self.assertEqual(Kvitansiya.objects.get().holat, 'amal')               # sababsiz — o'tmaydi
        e.post('/admin/hujjatlar/kvitansiya/', malumot)
        self.assertEqual(Kvitansiya.objects.get().holat, 'bekor')

    def test_direktor_shartnoma_matnini_faqat_koradi(self):
        s = Sozlama.olish()
        self.assertFalse(s.shartnoma_tasdiqlangan)
        r = self.c.get('/admin/hujjatlar/sozlama/')
        self.assertEqual(r.status_code, 200)
        self.assertTrue(self.direktor.has_perm('hujjatlar.view_sozlama'))
        self.assertFalse(self.direktor.has_perm('hujjatlar.change_sozlama'))   # tasdiqlash — faqat egasi
        self.assertFalse(self.direktor.has_perm('hujjatlar.delete_sozlama'))

    def test_shartnomaning_kod_xeshi_panelda_korinmaydi(self):
        self.tasdiqla_sozlama()
        sh = self.x.post(SH, {'buyurtma': self.b.pk}, format='json').json()
        self.x.post(f"{SH}{sh['id']}/kod/")
        html = self.c.get(f"/admin/hujjatlar/shartnoma/{sh['id']}/change/").content.decode()
        self.assertNotIn(Shartnoma.objects.get().kod_xesh, html)
