"""Xodim ish bosqichlari: qabul → yo'lda → ishni boshladi → yakunladi; har birida operatorga xabar."""
from unittest import mock

from django.core.cache import cache
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from apps.aloqa.models import Xabar
from apps.auth_app.models import Foydalanuvchi
from apps.sms_app.models import TelegramUlanish
from apps.tolovlar.models import TolovSorovi
from .models import Buyurtma


@override_settings(TELEGRAM_BOT_TOKEN='123:TEST')
@mock.patch('apps.buyurtmalar.views.sms_yubor', return_value=True)
@mock.patch('apps.sms_app.telegram._api')
class IshBosqichlariTest(TestCase):
    def setUp(self):
        cache.clear()
        self.rux = Foydalanuvchi.objects.create(telefon='+998900000003', rol='xodim', ism='Ruxsora',
                                                lavozim="Kadrlar bo'yicha mutaxassis")
        self.nargiza = Foydalanuvchi.objects.create(telefon='+998900000002', rol='xodim', ism='Nargiza',
                                                    lavozim='Call center operatori')
        self.usta = Foydalanuvchi.objects.create(telefon='+998900000005', rol='xodim', ism='Akbar', lavozim='Montaj ustasi')
        self.boshqa = Foydalanuvchi.objects.create(telefon='+998900000006', rol='xodim', lavozim='Montaj ustasi')
        self.mijoz = Foydalanuvchi.objects.create(telefon='+998901234567', rol='mijoz', ism='Vali')
        TelegramUlanish.objects.create(telefon=self.rux.telefon, chat_id=3)
        self.b = Buyurtma.objects.create(mijoz=self.mijoz, xizmat='servis', manzil='Buxoro, Navoiy 5', xodim=self.usta)

    def _c(self, u):
        c = APIClient()
        c.force_authenticate(u)
        return c

    def _bosqich(self, holat, u=None):
        with self.captureOnCommitCallbacks(execute=True):
            return self._c(u or self.usta).post(f'/api/buyurtmalar/{self.b.id}/bosqich/', {'holat': holat}, format='json')

    def test_toliq_jarayon_har_bosqichda_operatorga_xabar(self, api, sms):
        with self.captureOnCommitCallbacks(execute=True):
            self.assertEqual(self._c(self.usta).post(f'/api/buyurtmalar/{self.b.id}/qabul/').status_code, 200)
        self.assertEqual(self._bosqich('yolda').json()['holat'], 'yolda')
        self.assertEqual(self._bosqich('bajarilmoqda').json()['holat'], 'bajarilmoqda')
        with self.captureOnCommitCallbacks(execute=True):
            r = self._c(self.usta).post(f'/api/buyurtmalar/{self.b.id}/natija/', {'natija': 'Qozon tozalandi'}, format='json')
        self.assertEqual(r.json()['holat'], 'bajarildi')

        rux_xabarlari = list(Xabar.objects.filter(xodim=self.rux).order_by('id').values_list('matn', flat=True))
        self.assertEqual(len(rux_xabarlari), 4)
        for kalit in ('qabul qildi', "yo'lga chiqdi", 'ishni boshladi', 'ishni yakunladi'):
            self.assertTrue(any(kalit in m for m in rux_xabarlari), kalit)
        self.assertIn('Servis', rux_xabarlari[0])
        self.assertIn('Qozon tozalandi', rux_xabarlari[-1])
        self.assertEqual(Xabar.objects.filter(xodim=self.nargiza).count(), 4)   # Nargiza ham ko'radi
        self.assertFalse(Xabar.objects.filter(xodim=self.usta).exists())
        # Telegram: faqat botga ulangan operator (Ruxsora) — 4 ta xabar
        self.assertEqual(sum(1 for c in api.call_args_list if c.args[1]['chat_id'] == 3), 4)
        # Mijozga ham har bosqich haqida
        mijozga = [c.args[1] for c in sms.call_args_list if c.args[0] == self.mijoz.telefon]
        self.assertTrue(any("yo'lga chiqdi" in m for m in mijozga))
        self.assertTrue(any('ishni boshladi' in m for m in mijozga))

    def test_bosqich_tartibi(self, *_):
        self.assertEqual(self._bosqich('yolda').status_code, 409)          # avval qabul
        self.assertEqual(self._bosqich('bajarilmoqda').status_code, 409)
        Buyurtma.objects.filter(pk=self.b.pk).update(holat='qabul')
        self.assertEqual(self._bosqich('bajarilmoqda').status_code, 200)   # yo'lda bosqichini o'tkazib yuborsa ham bo'ladi
        self.assertEqual(self._bosqich('bekor').status_code, 400)

    def test_boshqa_xodim_bosqich_qoya_olmaydi(self, *_):
        Buyurtma.objects.filter(pk=self.b.pk).update(holat='qabul')
        self.assertEqual(self._bosqich('yolda', u=self.boshqa).status_code, 404)

    def test_yolda_operator_royxatida_faol(self, *_):
        Buyurtma.objects.filter(pk=self.b.pk).update(holat='yolda')
        d = self._c(self.rux).get('/api/buyurtmalar/operator/arizalar/?holat=faol').json()
        self.assertEqual([a['holat'] for a in d['arizalar']], ['yolda'])

    def test_click_tolovlari_ruxsora_oynasida(self, *_):
        TolovSorovi.objects.create(ism='Vali', telefon=self.mijoz.telefon, tolov_turi='online', tolov_tizimi='click',
                                   summa=50000, holat='tolandi', buyurtma=self.b, xizmat_turi='Buyurtma')
        TolovSorovi.objects.create(ism='X', telefon='1', tolov_turi='online', tolov_tizimi='click', summa=1, holat='yangi')
        r = self._c(self.rux).get('/api/tolovlar/bank/click-tolovlar/')
        self.assertEqual([x['summa'] for x in r.json()['royxat']], [50000])
        self.assertEqual(self._c(self.usta).get('/api/tolovlar/bank/click-tolovlar/').status_code, 403)
