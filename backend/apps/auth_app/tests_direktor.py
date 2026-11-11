"""Direktor Django panelida: cheklangan huquqlar, pul qabul qilish, xavfsiz kirish."""
import io

from django.contrib.auth.models import Group, Permission
from django.core.cache import cache
from django.core.management import call_command
from django.test import Client, TestCase

from apps.auth_app.models import AuditYozuv, Foydalanuvchi
from apps.buyurtmalar.models import Buyurtma
from apps.tushum.models import Tushum

PAROL = 'Direktor-Parol-2026!'


class Asos(TestCase):
    def setUp(self):
        cache.clear()
        self.addCleanup(cache.clear)
        call_command('direktor_guruhi', stdout=io.StringIO())
        mk = Foydalanuvchi.objects.create_user
        self.direktor = mk(telefon='+998900000201', password=PAROL, ism='Direktor', rol='admin',
                           holat='faol', is_staff=True)
        self.direktor.groups.add(Group.objects.get(name='Direktor'))
        self.egasi = mk(telefon='+998900000202', password=PAROL, ism='Egasi', rol='admin',
                        holat='faol', is_staff=True, is_superuser=True)
        self.xodim = Foydalanuvchi.objects.create(telefon='+998900000203', ism='Aziz', rol='xodim', holat='faol')
        self.c = Client()
        self.assertTrue(self.c.login(username=self.direktor.telefon, password=PAROL))

    def tushum(self, summa=100000, **kw):
        return Tushum.objects.create(xodim=self.xodim, summa=summa, tarmoq='aholi', **kw)


class GuruhTestlari(Asos):
    def test_guruh_va_huquqlar(self):
        g = Group.objects.get(name='Direktor')
        kodlar = set(g.permissions.values_list('content_type__app_label', 'codename'))
        self.assertIn(('tushum', 'view_tushum'), kodlar)
        self.assertIn(('narxnoma', 'view_narxnomaqator'), kodlar)
        self.assertIn(('auth_app', 'view_xodim'), kodlar)

    def test_direktor_kuzatuvchi_faqat_koradi(self):
        """Direktor kuzatuvchi: guruhdagi HAR BIR huquq faqat «view» — qo'shish/o'zgartirish/o'chirish/maxsus amal yo'q."""
        g = Group.objects.get(name='Direktor')
        ortiqcha = [k for k in g.permissions.values_list('codename', flat=True) if not k.startswith('view_')]
        self.assertEqual(ortiqcha, [])
        self.assertGreater(g.permissions.count(), 15)

    def test_xavfli_huquqlar_berilmaydi(self):
        g = Group.objects.get(name='Direktor')
        kodlar = set(g.permissions.values_list('codename', flat=True))
        for xavfli in ('delete_buyurtma', 'delete_tushum', 'change_tushum', 'add_tushum', 'delete_xodim',
                       'view_foydalanuvchi', 'change_foydalanuvchi', 'delete_foydalanuvchi',
                       'change_audityozuv', 'delete_audityozuv', 'delete_narxnomaqator'):
            self.assertNotIn(xavfli, kodlar, xavfli)
        self.assertFalse(Foydalanuvchi.objects.get(pk=self.direktor.pk).is_superuser)

    def test_buyruq_takrorlanganda_ortiqcha_huquq_olib_tashlanadi(self):
        g = Group.objects.get(name='Direktor')
        g.permissions.add(Permission.objects.get(codename='delete_tushum'))
        call_command('direktor_guruhi', stdout=io.StringIO())
        self.assertFalse(g.permissions.filter(codename='delete_tushum').exists())


class KirishTestlari(Asos):
    def test_direktor_django_paneliga_kiradi(self):
        r = self.c.get('/admin/')
        self.assertEqual(r.status_code, 200)

    def test_xodim_huquqisiz_hisob_kira_olmaydi(self):
        Foydalanuvchi.objects.filter(pk=self.direktor.pk).update(is_staff=False)
        c = Client()
        r = c.post('/admin/login/', {'username': self.direktor.telefon, 'password': PAROL, 'next': '/admin/'})
        self.assertEqual(r.status_code, 200)                  # forma qayta ko'rsatiladi
        self.assertEqual(c.get('/admin/').status_code, 302)   # kirish sahifasiga qaytaradi

    def test_jurnalda_sabab_farqlanadi(self):
        c = Client()
        # Parol to'g'ri, lekin is_staff yo'q
        Foydalanuvchi.objects.filter(pk=self.direktor.pk).update(is_staff=False)
        r = c.post('/admin/login/', {'username': self.direktor.telefon, 'password': PAROL, 'next': '/admin/'})
        self.assertEqual(r.status_code, 200)                    # foydalanuvchiga baribir oddiy forma xatosi
        y = AuditYozuv.objects.filter(amal='kirish_xato').latest('vaqt')
        self.assertIn('parol to\'g\'ri', y.tafsilot)
        self.assertIn('is_staff', y.tafsilot)
        # Haqiqatan ham noto'g'ri parol
        c.post('/admin/login/', {'username': self.direktor.telefon, 'password': 'xato', 'next': '/admin/'})
        y = AuditYozuv.objects.filter(amal='kirish_xato').latest('vaqt')
        self.assertIn("noto'g'ri parol", y.tafsilot)
        self.assertNotIn('is_staff', y.tafsilot)

    def test_togri_parol_kirish_jurnalga_yoziladi(self):
        c = Client()
        r = c.post('/admin/login/', {'username': self.egasi.telefon, 'password': PAROL, 'next': '/admin/'})
        self.assertEqual(r.status_code, 302)
        self.assertTrue(AuditYozuv.objects.filter(amal='kirish', tafsilot__contains='Django').exists())

    def test_notogri_parol_cheklanadi(self):
        c = Client()
        for _ in range(4):
            r = c.post('/admin/login/', {'username': self.egasi.telefon, 'password': 'xato', 'next': '/admin/'})
            self.assertEqual(r.status_code, 200)
        # 5-urinish: to'g'ri parol ham o'tmaydi
        r = c.post('/admin/login/', {'username': self.egasi.telefon, 'password': PAROL, 'next': '/admin/'})
        self.assertEqual(r.status_code, 429)
        self.assertEqual(AuditYozuv.objects.filter(amal='kirish_xato').count(), 4)
        # hisobning o'zi bloklanmaydi: kutish tugagach (kesh tozalanganda) kira oladi
        egasi = Foydalanuvchi.objects.get(pk=self.egasi.pk)
        self.assertEqual(egasi.holat, 'faol')
        cache.clear()
        r = c.post('/admin/login/', {'username': self.egasi.telefon, 'password': PAROL, 'next': '/admin/'})
        self.assertEqual(r.status_code, 302)

    def test_cheklov_boshqa_raqamga_tegmaydi(self):
        c = Client()
        for _ in range(4):
            c.post('/admin/login/', {'username': self.egasi.telefon, 'password': 'xato', 'next': '/admin/'})
        r = Client().post('/admin/login/', {'username': self.direktor.telefon, 'password': PAROL, 'next': '/admin/'})
        self.assertEqual(r.status_code, 302)

    def test_direktor_boshqaruv_paneliga_kiradi(self):
        """Direktor (kuzatuvchi) biznes panelida (/boshqaruv/) ishlaydi — «Direktor» guruhida bo'lsa ham.
        Parol to'g'ri bo'lsa 2FA (SMS kod) bosqichi boshlanadi; token faqat kod tasdiqlangach beriladi."""
        r = Client().post('/api/auth/admin/login/', {'telefon': self.direktor.telefon, 'parol': PAROL},
                          content_type='application/json')
        self.assertEqual(r.status_code, 200, r.content)
        self.assertNotIn('access', r.json())

    def test_egasi_boshqaruv_paneliga_kiraveradi(self):
        # Guruhga kirmagan admin (egasi) uchun bu qoida ishlamaydi (2FA javobi yoki tokenlar qaytadi)
        r = Client().post('/api/auth/admin/login/', {'telefon': self.egasi.telefon, 'parol': PAROL},
                          content_type='application/json')
        self.assertEqual(r.status_code, 200)


class KozchaTestlari(Asos):
    """Parol maydonlarida «ko'zcha» (parolni ko'rib tekshirish) tugmasi."""

    def test_django_kirish_sahifasida(self):
        html = Client().get('/admin/login/').content.decode()
        self.assertIn('parol-kozcha', html)
        self.assertIn('input[type="password"]', html)
        self.assertIn('type="password"', html)            # maydon boshida yashirin

    def test_parol_ozgartirish_sahifalarida(self):
        for yol in ('/admin/password_change/', f'/admin/auth_app/xodim/{self.xodim.pk}/password/'):
            c = Client()
            c.login(username=self.egasi.telefon, password=PAROL)
            self.assertIn('parol-kozcha', c.get(yol).content.decode(), yol)

    def test_standart_admin_shabloni_buzilmagan(self):
        html = Client().get('/admin/login/').content.decode()
        self.assertIn('id="login-form"', html)
        self.assertIn('name="username"', html)


class RahbariyatBoshSahifaTestlari(Asos):
    def test_bosh_sahifada_rahbariyat_korinadi(self):
        self.tushum(summa=250000)
        html = self.c.get('/admin/').content.decode()
        self.assertIn('Diqqat talab qiladi', html)
        self.assertIn('Kim qancha pul topshirmagan', html)
        self.assertIn('250 000', html)                         # topshirilishi kutilayotgan pul

    def test_diqqat_havolasi_faqat_huquq_bolsa(self):
        t = self.tushum()
        Tushum.objects.filter(pk=t.pk).update(yaratilgan=t.yaratilgan.replace(year=2020))
        html = self.c.get('/admin/').content.decode()
        self.assertIn('href="/admin/tushum/tushum/?holat__exact=kutilmoqda"', html)

    def test_xodim_rolidagi_hisobda_rahbariyat_yoq(self):
        s = Foydalanuvchi.objects.create_user(telefon='+998900000204', password=PAROL, rol='xodim',
                                              is_staff=True, ism='Staff')
        s.user_permissions.add(Permission.objects.get(codename='view_audityozuv'))
        c = Client()
        c.login(username=s.telefon, password=PAROL)
        self.assertNotIn('Kim qancha pul topshirmagan', c.get('/admin/').content.decode())


class TushumAmallariTestlari(Asos):
    URL = '/admin/tushum/tushum/'

    def setUp(self):
        super().setUp()
        self.d = self.c                                  # direktor (kuzatuvchi)
        self.c = Client()                                # qabul/rad amallari — tizim egasi
        self.assertTrue(self.c.login(username=self.egasi.telefon, password=PAROL))

    def amal(self, nom, tushumlar, **qoshimcha):
        malumot = {'action': nom, '_selected_action': [t.pk for t in tushumlar], 'index': '0', 'sabab': ''}
        malumot.update(qoshimcha)
        return self.c.post(self.URL, malumot, follow=True)

    def test_direktor_qabul_ham_rad_ham_qila_olmaydi(self):
        t = self.tushum()
        for nom, qosh in (('qabul_qilish', {}), ('rad_etish', {'sabab': 'x'})):
            self.d.post(self.URL, {'action': nom, '_selected_action': [t.pk], 'index': '0', 'sabab': '', **qosh}, follow=True)
            t.refresh_from_db()
            self.assertEqual(t.holat, 'kutilmoqda', nom)

    def test_egasi_qabul_qiladi(self):
        t = self.tushum()
        self.amal('qabul_qilish', [t])
        t.refresh_from_db()
        self.assertEqual((t.holat, t.hal_qilgan), ('qabul', self.egasi))
        self.assertTrue(AuditYozuv.objects.filter(amal='tushum_qabul').exists())

    def test_qabul_buyurtmani_tolandi_qiladi(self):
        b = Buyurtma.objects.create(xodim=self.xodim, xizmat='servis', tasdiq_summa=100000)
        t = self.tushum(buyurtma=b)
        self.amal('qabul_qilish', [t])
        b.refresh_from_db()
        self.assertTrue(b.tolandi)

    def test_rad_etish_sabab_talab_qiladi(self):
        t = self.tushum()
        self.amal('rad_etish', [t])
        t.refresh_from_db()
        self.assertEqual(t.holat, 'kutilmoqda')
        self.amal('rad_etish', [t], sabab="Summa noto'g'ri")
        t.refresh_from_db()
        self.assertEqual((t.holat, t.rad_sababi), ('rad', "Summa noto'g'ri"))
        self.assertTrue(AuditYozuv.objects.filter(amal='tushum_rad').exists())

    def test_hal_qilingan_qayta_hal_bolmaydi(self):
        t = self.tushum()
        self.amal('qabul_qilish', [t])
        self.amal('rad_etish', [t], sabab='x')
        t.refresh_from_db()
        self.assertEqual(t.holat, 'qabul')

    def test_huquqsiz_foydalanuvchi_qabul_qila_olmaydi(self):
        self.direktor.groups.clear()
        self.direktor.user_permissions.add(Permission.objects.get(codename='view_tushum'))
        c = Client()
        c.login(username=self.direktor.telefon, password=PAROL)
        t = self.tushum()
        c.post(self.URL, {'action': 'qabul_qilish', '_selected_action': [t.pk], 'index': '0'})
        t.refresh_from_db()
        self.assertEqual(t.holat, 'kutilmoqda')

    def test_tushumni_ozgartirish_qoshish_ochirish_yoq(self):
        t = self.tushum()
        self.assertEqual(self.d.get(f'{self.URL}{t.pk}/change/').status_code, 200)       # faqat ko'rish
        self.assertEqual(self.d.get(f'{self.URL}add/').status_code, 403)
        self.assertEqual(self.d.get(f'{self.URL}{t.pk}/delete/').status_code, 403)
        r = self.d.post(f'{self.URL}{t.pk}/change/', {'summa': '1'})
        t.refresh_from_db()
        self.assertEqual(t.summa, 100000)


class HuquqChegarasiTestlari(Asos):
    def test_foydalanuvchilar_royxati_yopiq(self):
        self.assertEqual(self.c.get('/admin/auth_app/foydalanuvchi/').status_code, 403)
        self.assertEqual(self.c.get(f'/admin/auth_app/foydalanuvchi/{self.egasi.pk}/change/').status_code, 403)

    def test_xodimni_faqat_koradi(self):
        self.assertEqual(self.c.get('/admin/auth_app/xodim/').status_code, 200)
        self.assertEqual(self.c.get('/admin/auth_app/xodim/add/').status_code, 403)             # qo'sha olmaydi
        self.assertEqual(self.c.get(f'/admin/auth_app/xodim/{self.xodim.pk}/change/').status_code, 200)   # ko'radi
        self.c.post(f'/admin/auth_app/xodim/{self.xodim.pk}/change/',
                    {'telefon': self.xodim.telefon, 'ism': 'Boshqa ism', 'lavozim': 'Usta'})
        self.xodim.refresh_from_db()
        self.assertEqual(self.xodim.ism, 'Aziz')                                                # tahrirlay olmaydi

    def test_xodimni_nofaol_qila_olmaydi(self):
        # holat maydoni direktor uchun faqat o'qish; POST bilan yuborilgan qiymat e'tiborsiz qoladi
        html = self.c.get(f'/admin/auth_app/xodim/{self.xodim.pk}/change/').content.decode()
        self.assertNotIn('name="holat"', html)
        self.c.post(f'/admin/auth_app/xodim/{self.xodim.pk}/change/',
                    {'telefon': self.xodim.telefon, 'ism': 'Aziz', 'holat': 'nofaol', 'lavozim': 'Usta'})
        self.xodim.refresh_from_db()
        self.assertEqual(self.xodim.holat, 'faol')
        # egasiga esa holat maydoni ochiq
        e = Client()
        e.login(username=self.egasi.telefon, password=PAROL)
        self.assertIn('name="holat"', e.get(f'/admin/auth_app/xodim/{self.xodim.pk}/change/').content.decode())

    def test_xodimga_parol_qoya_olmaydi(self):
        url = f'/admin/auth_app/xodim/{self.xodim.pk}/password/'
        self.assertEqual(self.c.get(url).status_code, 403)
        self.assertEqual(self.c.post(url, {'password1': 'Yangi-Parol-1!', 'password2': 'Yangi-Parol-1!'}).status_code, 403)
        self.xodim.refresh_from_db()
        self.assertFalse(self.xodim.has_usable_password() and self.xodim.check_password('Yangi-Parol-1!'))
        e = Client()
        e.login(username=self.egasi.telefon, password=PAROL)
        self.assertEqual(e.get(url).status_code, 200)             # egasi uchun ochiq

    def test_hech_narsani_ochira_olmaydi(self):
        for model in ('buyurtmalar/buyurtma', 'narxnoma/narxnomaqator', 'katalog/katalognarx',
                      'auth_app/audityozuv', 'auth_app/xodim'):
            self.assertIn(self.c.get(f'/admin/{model}/').status_code, (200, 403), model)
        self.assertFalse(self.direktor.has_perm('buyurtmalar.delete_buyurtma'))
        self.assertFalse(self.direktor.has_perm('auth_app.delete_xodim'))

    def test_narxlarni_faqat_koradi(self):
        self.assertFalse(self.direktor.has_perm('narxnoma.change_narxnomaqator'))
        self.assertFalse(self.direktor.has_perm('katalog.change_katalognarx'))
        self.assertTrue(self.direktor.has_perm('narxnoma.view_narxnomaqator'))
        self.assertEqual(self.c.get('/admin/narxnoma/narxnomaqator/').status_code, 200)
        self.assertEqual(self.c.get('/admin/narxnoma/narxnomaqator/add/').status_code, 403)

    def test_jurnalni_ozgartira_olmaydi(self):
        self.assertEqual(self.c.get('/admin/auth_app/audityozuv/').status_code, 200)
        self.assertEqual(self.c.get('/admin/auth_app/audityozuv/add/').status_code, 403)
