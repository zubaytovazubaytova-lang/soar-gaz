"""Kvitansiya: yo'nalish korxonasi rekvizitlari va mijoz kabineti / Ruxsora / Telegram'ga yetkazish."""
from unittest import mock

from django.core.cache import cache
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from apps.aloqa.models import Xabar
from apps.auth_app.models import Foydalanuvchi
from apps.buyurtmalar.models import Buyurtma
from apps.kabinet.models import Bildirishnoma
from apps.tolovlar.models import Rekvizit
from .models import Kvitansiya


@override_settings(SAYT_MANZIL='https://soargaz.uz')
@mock.patch('apps.hujjatlar.xizmat.sms_yubor', return_value=True)
class KvitansiyaRekvizitTest(TestCase):
    def setUp(self):
        cache.clear()
        Rekvizit.objects.create(yonalish='servis', korxona='"Servis Korxona" MChJ', bank='BRB',
                                manzil='Sinov shahar, Sinov kochasi 1', ruxsatnoma='№000001, reestr R-000001, 01.01.2030 gacha',
                                hisob_raqam='20208000900000000011', mfo='00001', stir='300000011')
        Rekvizit.objects.create(yonalish='montaj', korxona='"Montaj Korxona" MChJ', bank='BRB',
                                hisob_raqam='20208000900000000022', mfo='00001', stir='300000022')
        self.rux = Foydalanuvchi.objects.create(telefon='+998900000003', rol='xodim', ism='Ruxsora',
                                                lavozim="Kadrlar bo'yicha mutaxassis")
        self.usta = Foydalanuvchi.objects.create(telefon='+998900000005', rol='xodim', ism='Akbar', lavozim='Montaj ustasi')
        self.mijoz = Foydalanuvchi.objects.create(telefon='+998901234567', rol='mijoz', ism='Vali', manzil='Buxoro')
        self.c = APIClient()
        self.c.force_authenticate(self.usta)

    def _kvitansiya(self, xizmat):
        b = Buyurtma.objects.create(mijoz=self.mijoz, xizmat=xizmat, manzil='Buxoro, Navoiy 5',
                                    xodim=self.usta, holat='bajarildi', tasdiq_summa=180000)
        t = self.c.post('/api/tushum/', {'summa': 180000, 'usul': 'naqd', 'buyurtma': b.id}, format='json')
        self.assertEqual(t.status_code, 201, t.content)
        with self.captureOnCommitCallbacks(execute=True):
            k = self.c.post('/api/hujjatlar/kvitansiya/', {'tushum': t.json()['id'], 'mijoz_ism': 'Vali',
                                                           'mijoz_telefon': self.mijoz.telefon,
                                                           'manzil': 'Buxoro, Navoiy 5'}, format='json')
        self.assertEqual(k.status_code, 201, k.content)
        return Kvitansiya.objects.get(raqam=k.json()['raqam'])

    def test_servis_kvitansiyasi_lux_servis_rekvizitlari(self, sms):
        kv = self._kvitansiya('servis')
        self.assertEqual((kv.rekvizit['korxona'], kv.rekvizit['stir']), ('"Servis Korxona" MChJ', '300000011'))
        sahifa = self.client.get(f'/kvitansiya/{kv.token}/').content.decode()
        self.assertIn('Servis Korxona', sahifa)
        self.assertIn('20208000900000000011', sahifa)
        self.assertIn('300000011', sahifa)
        self.assertIn('№000001, reestr R-000001', sahifa)          # ruxsatnoma (qonuniy asos)
        self.assertIn('Sinov kochasi 1', sahifa)                          # korxona manzili
        self.assertIn('<svg', sahifa)                              # tekshirish QR-kodi
        self.assertIn(f'https://soargaz.uz/kvitansiya/{kv.token}/', sahifa)

    def test_montaj_kvitansiyasi_soar_gaz_rekvizitlari(self, sms):
        kv = self._kvitansiya('montaj')
        self.assertEqual(kv.rekvizit['hisob_raqam'], '20208000900000000022')

    def test_mijoz_kabineti_ruxsora_va_telegram(self, sms):
        kv = self._kvitansiya('servis')
        # Mijozga Telegram/SMS (sms_yubor Telegram'ni birinchi sinaydi) — havola bilan
        self.assertIn(f'/kvitansiya/{kv.token}/', sms.call_args.args[1])
        # Mijoz kabineti: bildirishnoma va «To'lovlar»dagi ro'yxat
        self.assertTrue(Bildirishnoma.objects.filter(mijoz=self.mijoz, sarlavha__contains=kv.raqam).exists())
        cm = APIClient()
        cm.force_authenticate(self.mijoz)
        royxat = cm.get('/api/kabinet/tolovlar/').json()['kvitansiyalar']
        self.assertEqual(royxat[0]['raqam'], kv.raqam)
        # Ruxsora kabineti (qo'ng'iroqcha)
        self.assertTrue(Xabar.objects.filter(xodim=self.rux, matn__contains=kv.raqam).exists())
        self.assertFalse(Xabar.objects.filter(xodim=self.usta, matn__contains=kv.raqam).exists())
