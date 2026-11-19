"""Bank (hisob raqam) orqali to'lov: chek yuklash, tasdiqlash va ruxsatlar."""
import shutil
import tempfile
from unittest import mock

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from apps.auth_app.models import Foydalanuvchi
from apps.buyurtmalar.models import Buyurtma
from .models import BankTolovi, Rekvizit, TolovSorovi

MEDIA = tempfile.mkdtemp()
PNG = b'\x89PNG\r\n\x1a\n' + b'0' * 100


def chek(nom='chek.png', mazmun=PNG):
    return SimpleUploadedFile(nom, mazmun, content_type='image/png')


@override_settings(MEDIA_ROOT=MEDIA)
@mock.patch('apps.tolovlar.bank.sms_yubor')
@mock.patch('apps.sms_app.xodim_xabar.tolov_tekshiruvchilarga')
class BankTolovTest(TestCase):
    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(MEDIA, ignore_errors=True)

    def setUp(self):
        self.mijoz = Foydalanuvchi.objects.create(telefon='+998901111111', rol='mijoz', ism='Ali')
        self.begona = Foydalanuvchi.objects.create(telefon='+998902222222', rol='mijoz')
        self.admin = Foydalanuvchi.objects.create(telefon='+998903333333', rol='admin')
        self.ruxsora = Foydalanuvchi.objects.create(telefon='+998904444444', rol='xodim',
                                                    lavozim="Kadrlar bo'yicha mutaxassis")
        self.usta = Foydalanuvchi.objects.create(telefon='+998905555555', rol='xodim', lavozim='Montaj ustasi')
        self.b = Buyurtma.objects.create(mijoz=self.mijoz, xizmat='servis')
        self.montaj = Buyurtma.objects.create(mijoz=self.mijoz, xizmat='montaj')
        Rekvizit.objects.create(yonalish='servis', korxona='SOAR GAZ MChJ', bank='Bank', hisob_raqam='2' * 20,
                                mfo='00001', stir='123456789')
        Rekvizit.objects.create(yonalish='montaj', korxona='SOAR GAZ MChJ', bank='Bank', hisob_raqam='3' * 20,
                                mfo='00001', stir='123456789')

    def _c(self, user):
        c = APIClient()
        c.force_authenticate(user)
        return c

    def _yukla(self, b=None, **tana):
        tana = {'summa': '350 000', 'chek': chek(), **tana}
        return self._c(self.mijoz).post(f'/api/tolovlar/bank/buyurtma/{(b or self.b).id}/', tana, format='multipart')

    def test_rekvizit_yonalish_boyicha(self, *_):
        r = self._c(self.mijoz).get(f'/api/tolovlar/bank/buyurtma/{self.b.id}/').json()
        self.assertEqual(r['rekvizit']['hisob_raqam'], '2' * 20)
        self.assertIn(f'#{self.b.id}', r['maqsad'])
        r = self._c(self.mijoz).get(f'/api/tolovlar/bank/buyurtma/{self.montaj.id}/').json()
        self.assertEqual(r['rekvizit']['hisob_raqam'], '3' * 20)

    def test_chek_yuklanadi_va_tekshiruvchilarga_xabar(self, xabar, _):
        r = self._yukla()
        self.assertEqual(r.status_code, 201, r.content)
        t = BankTolovi.objects.get()
        self.assertEqual((t.summa, t.holat, t.hisob_raqam), (350000, 'tekshirilmoqda', '2' * 20))
        self.assertTrue(t.chek.name.startswith('hujjatlar_maxfiy/bank_cheklar/'))
        self.assertEqual(t.tolov_sorovi.holat, 'kutilmoqda')
        xabar.assert_called_once()

    def test_begona_buyurtmaga_yuklab_bolmaydi(self, *_):
        r = self._c(self.begona).post(f'/api/tolovlar/bank/buyurtma/{self.b.id}/',
                                      {'summa': '1000', 'chek': chek()}, format='multipart')
        self.assertEqual(r.status_code, 404)

    def test_soxta_fayl_rad_etiladi(self, *_):
        self.assertEqual(self._yukla(chek=chek('a.png', b'<html>')).status_code, 400)
        self.assertEqual(self._yukla(chek=chek('a.exe', PNG)).status_code, 400)
        self.assertEqual(self._yukla(summa='0').status_code, 400)
        self.assertFalse(BankTolovi.objects.exists())

    def test_tekshirilayotganda_ikkinchi_chek_yoq(self, *_):
        self._yukla()
        self.assertEqual(self._yukla().status_code, 400)

    def test_rekvizit_yoq_bolsa(self, *_):
        Rekvizit.objects.all().delete()
        self.assertEqual(self._yukla().status_code, 400)

    def test_ruxsora_tasdiqlaydi_mijozga_xabar(self, _, sms):
        self._yukla()
        t = BankTolovi.objects.get()
        with self.captureOnCommitCallbacks(execute=True):
            r = self._c(self.ruxsora).post(f'/api/tolovlar/bank/cheklar/{t.id}/tekshir/', {'natija': 'tasdiq'})
        self.assertEqual(r.status_code, 200, r.content)
        t.refresh_from_db()
        self.assertEqual((t.holat, t.tekshirdi), ('tasdiqlandi', self.ruxsora))
        self.assertEqual(TolovSorovi.objects.get().holat, 'tolandi')
        self.assertIn('qabul qilindi', sms.call_args.args[1])
        # Ikkinchi marta tasdiqlab bo'lmaydi
        r = self._c(self.admin).post(f'/api/tolovlar/bank/cheklar/{t.id}/tekshir/', {'natija': 'rad', 'sabab': 'x'})
        self.assertEqual(r.status_code, 400)

    def test_admin_rad_etadi_sababi_bilan(self, _, sms):
        self._yukla()
        t = BankTolovi.objects.get()
        url = f'/api/tolovlar/bank/cheklar/{t.id}/tekshir/'
        self.assertEqual(self._c(self.admin).post(url, {'natija': 'rad'}).status_code, 400)   # sababsiz
        with self.captureOnCommitCallbacks(execute=True):
            self.assertEqual(self._c(self.admin).post(url, {'natija': 'rad', 'sabab': 'Pul kelmadi'}).status_code, 200)
        self.assertEqual(TolovSorovi.objects.get().holat, 'bekor')
        self.assertIn('Pul kelmadi', sms.call_args.args[1])
        self.assertEqual(self._yukla().status_code, 201)          # rad etilgandan keyin qayta yuborsa bo'ladi

    def test_oddiy_xodim_va_mijoz_tasdiqlay_olmaydi(self, *_):
        self._yukla()
        t = BankTolovi.objects.get()
        for u in (self.usta, self.mijoz):
            self.assertEqual(self._c(u).post(f'/api/tolovlar/bank/cheklar/{t.id}/tekshir/',
                                             {'natija': 'tasdiq'}).status_code, 403)
            self.assertEqual(self._c(u).get('/api/tolovlar/bank/cheklar/').status_code, 403)

    def test_chek_faylini_kim_ochadi(self, *_):
        self._yukla()
        url = f'/api/tolovlar/bank/cheklar/{BankTolovi.objects.get().id}/chek/'
        self.assertEqual(self._c(self.mijoz).get(url).status_code, 200)
        self.assertEqual(self._c(self.ruxsora).get(url).status_code, 200)
        self.assertEqual(self._c(self.begona).get(url).status_code, 404)
        self.assertEqual(self._c(self.usta).get(url).status_code, 404)

    def test_tekshiruvchi_royxati(self, *_):
        self._yukla()
        r = self._c(self.ruxsora).get('/api/tolovlar/bank/cheklar/?holat=tekshirilmoqda').json()
        self.assertEqual(r['kutilmoqda'], 1)
        self.assertEqual(r['royxat'][0]['telefon'], '+998901111111')


@override_settings(MEDIA_ROOT=MEDIA)
@mock.patch('apps.tolovlar.bank.sms_yubor')
@mock.patch('apps.sms_app.xodim_xabar.tolov_tekshiruvchilarga')
class XaridBankTolovTest(TestCase):
    """Do'kon xaridi: mehmon ham telefon oxiri bilan chek yuklaydi; tasdiq xaridni «to'landi» qiladi."""

    def setUp(self):
        from apps.xaridlar.models import Xarid
        from apps.xaridlar.tolov import tolov_sorovi_yarat
        self.ruxsora = Foydalanuvchi.objects.create(telefon='+998904444444', rol='xodim',
                                                    lavozim="Kadrlar bo'yicha mutaxassis")
        self.x = Xarid.objects.create(ism='Vali', telefon='+998907776655', manzil='Buxoro',
                                      jami=480000, tolov_usuli='bank')
        tolov_sorovi_yarat(self.x)
        Rekvizit.objects.create(yonalish='xarid', korxona='SOAR GAZ MChJ', bank='Bank', hisob_raqam='4' * 20,
                                mfo='00001', stir='123456789')
        self.url = f'/api/tolovlar/bank/xarid/{self.x.raqam}/'

    def _yukla(self, telefon='6655'):
        return APIClient().post(self.url, {'chek': chek(), 'telefon': telefon}, format='multipart')

    def test_egaliksiz_korinmaydi(self, *_):
        self.assertEqual(APIClient().get(self.url).status_code, 403)
        self.assertEqual(self._yukla(telefon='0000').status_code, 403)

    def test_rekvizit_va_summa(self, *_):
        r = APIClient().get(self.url, HTTP_X_TELEFON_OXIRI='6655').json()
        self.assertEqual((r['rekvizit']['hisob_raqam'], r['summa']), ('4' * 20, 480000))

    def test_mehmon_yuklaydi_tasdiqdan_keyin_xarid_tolandi(self, xabar, sms):
        r = self._yukla()
        self.assertEqual(r.status_code, 201, r.content)
        t = BankTolovi.objects.get()
        self.assertEqual((t.summa, t.xarid_id, t.mijoz_id), (480000, self.x.id, None))
        self.assertEqual(t.tolov_sorovi_id, self.x.tolov_sorovi_id)
        c = APIClient()
        c.force_authenticate(self.ruxsora)
        with self.captureOnCommitCallbacks(execute=True):
            self.assertEqual(c.post(f'/api/tolovlar/bank/cheklar/{t.id}/tekshir/', {'natija': 'tasdiq'}).status_code, 200)
        self.x.refresh_from_db()
        self.assertTrue(self.x.tolandi)
        self.assertEqual(self.x.tolov_holati, 'tolandi')
        self.assertEqual(sms.call_args.args[0], '+998907776655')
        self.assertIn(self.x.raqam, sms.call_args.args[1])
        royxat = c.get('/api/tolovlar/bank/cheklar/').json()['royxat']
        self.assertIn("Do'kon xaridi", royxat[0]['xizmat'])

    def test_rad_etilsa_qayta_yuklash(self, *_):
        self._yukla()
        t = BankTolovi.objects.get()
        c = APIClient()
        c.force_authenticate(self.ruxsora)
        c.post(f'/api/tolovlar/bank/cheklar/{t.id}/tekshir/', {'natija': 'rad', 'sabab': 'Pul kelmadi'})
        self.x.refresh_from_db()
        self.assertFalse(self.x.tolandi)
        self.assertEqual(self._yukla().status_code, 201)
        self.assertEqual(BankTolovi.objects.count(), 2)
        self.assertEqual(BankTolovi.objects.latest('id').tolov_sorovi.holat, 'kutilmoqda')

    def test_boshqa_usuldagi_xaridga_yuklanmaydi(self, *_):
        self.x.tolov_usuli = 'naqd'
        self.x.save(update_fields=['tolov_usuli'])
        self.assertEqual(self._yukla().status_code, 400)
