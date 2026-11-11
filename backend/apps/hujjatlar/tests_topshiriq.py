"""Ichki topshiriqlar: Kadrlar (Ruxsora) va call center (Nargiza) -> hujjatchi (Ferangiz); hujjatchi o'ziga ham yozadi."""
import shutil
import tempfile
from datetime import timedelta

from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from apps.auth_app.models import Foydalanuvchi
from apps.hujjatlar.models import Topshiriq

URL = '/api/hujjatlar/topshiriq/'
MEDIA = tempfile.mkdtemp(prefix='soargaz-test-media-')


def klient(user=None):
    c = APIClient()
    if user:
        c.credentials(HTTP_AUTHORIZATION='Bearer ' + str(RefreshToken.for_user(user).access_token))
    return c


def fayl(nom='hujjat.pdf', mazmun=b'%PDF-1.4 sinov'):
    return SimpleUploadedFile(nom, mazmun, content_type='application/pdf')


@override_settings(MEDIA_ROOT=MEDIA)
class Asos(TestCase):
    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(MEDIA, ignore_errors=True)

    def setUp(self):
        cache.clear()
        mk = Foydalanuvchi.objects.create
        self.ferangiz = mk(telefon='+998900000701', ism='Ferangiz', rol='xodim', holat='faol',
                           lavozim="Mehnat muhofazasi va texnika xavfsizligi bo'yicha muhandis")
        self.ruxsora = mk(telefon='+998900000702', ism='Ruxsora', rol='xodim', holat='faol',
                          lavozim="Kadrlar bo'yicha mutaxassis")
        self.nargiza = mk(telefon='+998900000703', ism='Nargiza', rol='xodim', holat='faol',
                          lavozim='Call center operatori')
        self.usta = mk(telefon='+998900000704', ism='Aziz', rol='xodim', holat='faol', lavozim='Montaj ustasi')
        self.mijoz = mk(telefon='+998900000705', ism='Karim', rol='mijoz')
        self.admin = mk(telefon='+998900000706', ism='Ega', rol='admin', is_staff=True, is_superuser=True)

    def yubor(self, kim, kimga=None, **ustiga):
        d = {'sarlavha': 'Yo\'riqnomani yangilang', 'matn': 'Yangi tahrir bo\'yicha', **ustiga}
        if kimga:
            d['kimga'] = kimga.id
        return klient(kim).post(URL, d, format='multipart')


class RuxsatTestlari(Asos):
    def test_faqat_uch_tur(self):
        for u in (self.usta, self.mijoz, self.admin):
            self.assertEqual(klient(u).get(URL).status_code, 403, u.ism)
            self.assertEqual(self.yubor(u, self.ferangiz).status_code, 403, u.ism)
        self.assertEqual(klient().get(URL).status_code, 401)
        for u in (self.ferangiz, self.ruxsora, self.nargiza):
            self.assertEqual(klient(u).get(URL).status_code, 200, u.ism)

    def test_nofaol_xodim_kira_olmaydi(self):
        Foydalanuvchi.objects.filter(pk=self.nargiza.pk).update(holat='nofaol')
        self.assertEqual(klient(self.nargiza).get(URL).status_code, 403)


class YuborishTestlari(Asos):
    def test_ruxsora_va_nargiza_ferangizga_yuboradi(self):
        for kim in (self.ruxsora, self.nargiza):
            r = self.yubor(kim, self.ferangiz, muddat=str(timezone.localdate() + timedelta(days=2)))
            self.assertEqual(r.status_code, 201, r.content)
            self.assertEqual((r.json()['kim'], r.json()['kimga'], r.json()['oziga']), (kim.ism, 'Ferangiz', False))
        j = klient(self.ferangiz).get(URL).json()
        self.assertEqual(len(j['topshiriqlar']), 2)
        self.assertEqual(j['xulosa']['yangi'], 2)

    def test_ferangiz_ozi_uchun_yozadi(self):
        r = self.yubor(self.ferangiz)                       # kimga berilmasa ham — faqat o'ziga
        self.assertEqual(r.status_code, 201, r.content)
        self.assertTrue(r.json()['oziga'])
        # boshqaga yubora olmaydi: kimga yuborsa ham e'tiborga olinmaydi
        r = self.yubor(self.ferangiz, self.usta)
        self.assertEqual(Topshiriq.objects.get(pk=r.json()['id']).kimga, self.ferangiz)

    def test_ruxsora_kimga_tanlashi_shart_va_faqat_hujjatchi(self):
        self.assertEqual(self.yubor(self.ruxsora).status_code, 400)
        self.assertEqual(self.yubor(self.ruxsora, self.usta).status_code, 400)       # oddiy xodimga topshiriq yo'q
        self.assertEqual(self.yubor(self.ruxsora, self.nargiza).status_code, 400)
        self.assertEqual(Topshiriq.objects.count(), 0)

    def test_kimlar_royxati_faqat_yuboruvchiga(self):
        j = klient(self.ruxsora).get(URL).json()
        self.assertEqual([k['ism'] for k in j['kimlar']], ['Ferangiz'])
        self.assertEqual(klient(self.ferangiz).get(URL).json()['kimlar'], [])

    def test_tekshiruvlar(self):
        self.assertEqual(self.yubor(self.ruxsora, self.ferangiz, sarlavha='  ').status_code, 400)
        self.assertEqual(self.yubor(self.ruxsora, self.ferangiz, muddat='kecha').status_code, 400)
        kecha = str(timezone.localdate() - timedelta(days=1))
        self.assertEqual(self.yubor(self.ruxsora, self.ferangiz, muddat=kecha).status_code, 400)
        self.assertEqual(self.yubor(self.ruxsora, self.ferangiz, matn='x' * 2001).status_code, 400)

    def test_fayl_biriktirish_va_tekshirish(self):
        r = self.yubor(self.ruxsora, self.ferangiz, fayl=fayl())
        self.assertEqual(r.status_code, 201, r.content)
        self.assertEqual(r.json()['fayl_nomi'][:6], 'hujjat')
        for yomon in (fayl('virus.exe'), fayl('bosh.pdf', b''), fayl('katta.pdf', b'x' * (30 * 1024 * 1024 + 1))):
            self.assertEqual(self.yubor(self.ruxsora, self.ferangiz, fayl=yomon).status_code, 400, yomon.name)


class KoRishTestlari(Asos):
    def test_faqat_oz_topshiriqlarini_koradi(self):
        self.yubor(self.ruxsora, self.ferangiz)
        self.yubor(self.nargiza, self.ferangiz, sarlavha='Nargizanikli')
        ruxsora = klient(self.ruxsora).get(URL).json()['topshiriqlar']
        self.assertEqual([t['sarlavha'] for t in ruxsora], ['Yo\'riqnomani yangilang'])      # Nargizanikini ko'rmaydi
        t = Topshiriq.objects.get(sarlavha='Nargizanikli')
        self.assertEqual(klient(self.ruxsora).post(f'{URL}{t.id}/holat/', {'holat': 'bekor'}).status_code, 404)
        self.assertEqual(klient(self.ruxsora).get(f'{URL}{t.id}/fayl/topshiriq/').status_code, 404)

    def test_holat_filtri(self):
        self.yubor(self.ruxsora, self.ferangiz)
        t = Topshiriq.objects.get()
        klient(self.ferangiz).post(f'{URL}{t.id}/bajarildi/', {}, format='multipart')
        f = klient(self.ferangiz)
        self.assertEqual(len(f.get(URL).json()['topshiriqlar']), 0)
        self.assertEqual(len(f.get(URL, {'holat': 'yopiq'}).json()['topshiriqlar']), 1)
        self.assertEqual(len(f.get(URL, {'holat': 'hammasi'}).json()['topshiriqlar']), 1)

    def test_kechikkan(self):
        self.yubor(self.ruxsora, self.ferangiz, muddat=str(timezone.localdate()))
        Topshiriq.objects.update(muddat=timezone.localdate() - timedelta(days=1))
        j = klient(self.ferangiz).get(URL).json()
        self.assertTrue(j['topshiriqlar'][0]['kechikkan'])
        self.assertEqual(j['xulosa']['kechikkan'], 1)


class HolatTestlari(Asos):
    def setUp(self):
        super().setUp()
        self.yubor(self.ruxsora, self.ferangiz, fayl=fayl('topshiriq.pdf'))
        self.t = Topshiriq.objects.get()

    def holat(self, user, h):
        return klient(user).post(f'{URL}{self.t.id}/holat/', {'holat': h})

    def test_oluvchi_boshlaydi(self):
        self.assertEqual(self.holat(self.ruxsora, 'jarayonda').status_code, 403)      # yuboruvchi boshlay olmaydi
        r = self.holat(self.ferangiz, 'jarayonda')
        self.assertEqual((r.status_code, r.json()['holat']), (200, 'jarayonda'))
        self.assertEqual(self.holat(self.ferangiz, 'jarayonda').status_code, 409)

    def test_yuboruvchi_bekor_qiladi(self):
        self.assertEqual(self.holat(self.ferangiz, 'bekor').status_code, 403)         # oluvchi boshqaning topshirig'ini bekor qilmaydi
        r = self.holat(self.ruxsora, 'bekor')
        self.assertEqual((r.status_code, r.json()['holat']), (200, 'bekor'))
        self.assertEqual(self.holat(self.ruxsora, 'bekor').status_code, 409)
        self.assertEqual(klient(self.ferangiz).post(f'{URL}{self.t.id}/bajarildi/', {}).status_code, 409)

    def test_ozining_vazifasini_ozi_bekor_qiladi(self):
        r = self.yubor(self.ferangiz)
        t = Topshiriq.objects.get(pk=r.json()['id'])
        r = klient(self.ferangiz).post(f'{URL}{t.id}/holat/', {'holat': 'bekor'})
        self.assertEqual(r.status_code, 200, r.content)

    def test_notogri_holat(self):
        self.assertEqual(self.holat(self.ferangiz, 'bajarildi').status_code, 400)     # bajarish — alohida endpoint
        self.assertEqual(self.holat(self.ferangiz, 'xxx').status_code, 400)


class BajarishVaFaylTestlari(Asos):
    def setUp(self):
        super().setUp()
        self.yubor(self.ruxsora, self.ferangiz, fayl=fayl('topshiriq.pdf', b'%PDF topshiriq'))
        self.t = Topshiriq.objects.get()

    def bajar(self, user=None, **d):
        return klient(user or self.ferangiz).post(f'{URL}{self.t.id}/bajarildi/', d, format='multipart')

    def test_natija_fayli_bilan_bajarish(self):
        r = self.bajar(natija_fayl=fayl('natija.pdf', b'%PDF natija'), natija_izoh='Tayyor')
        self.assertEqual(r.status_code, 200, r.content)
        j = r.json()
        self.assertEqual((j['holat'], j['natija_izoh'], j['natija_nomi'][:6]), ('bajarildi', 'Tayyor', 'natija'))
        self.t.refresh_from_db()
        self.assertIsNotNone(self.t.bajarilgan)
        self.assertTrue(self.t.natija_fayl.name.startswith('hujjatlar_maxfiy/'))       # nginx ochiq bermaydigan papka

    def test_faylsiz_ham_bajariladi(self):
        self.assertEqual(self.bajar().status_code, 200)

    def test_faqat_oluvchi_bajaradi_va_bir_marta(self):
        self.assertEqual(self.bajar(self.ruxsora).status_code, 403)
        self.assertEqual(self.bajar().status_code, 200)
        self.assertEqual(self.bajar().status_code, 409)

    def test_notogri_natija_fayli(self):
        self.assertEqual(self.bajar(natija_fayl=fayl('virus.exe')).status_code, 400)
        self.t.refresh_from_db()
        self.assertEqual(self.t.holat, 'yangi')

    def test_fayl_olish_faqat_qatnashuvchiga(self):
        self.bajar(natija_fayl=fayl('natija.pdf', b'%PDF natija'))
        for u in (self.ferangiz, self.ruxsora):
            r = klient(u).get(f'{URL}{self.t.id}/fayl/topshiriq/')
            self.assertEqual(r.status_code, 200, u.ism)
            self.assertEqual(b''.join(r.streaming_content), b'%PDF topshiriq')
            self.assertIn('attachment', r['Content-Disposition'])
            self.assertEqual(r['X-Content-Type-Options'], 'nosniff')
        r = klient(self.ruxsora).get(f'{URL}{self.t.id}/fayl/natija/')           # natijani yuboruvchi ham yuklab oladi
        self.assertEqual(b''.join(r.streaming_content), b'%PDF natija')
        for u in (self.nargiza, self.usta, self.mijoz, self.admin):
            self.assertIn(klient(u).get(f'{URL}{self.t.id}/fayl/topshiriq/').status_code, (403, 404), u.ism)
        self.assertEqual(klient().get(f'{URL}{self.t.id}/fayl/topshiriq/').status_code, 401)
        self.assertEqual(klient(self.ferangiz).get(f'{URL}{self.t.id}/fayl/xxx/').status_code, 404)

    def test_natijasiz_fayl_404(self):
        self.assertEqual(klient(self.ferangiz).get(f'{URL}{self.t.id}/fayl/natija/').status_code, 404)
