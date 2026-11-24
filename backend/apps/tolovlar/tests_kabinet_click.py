"""Mijoz kabineti: xizmat buyurtmasini Click orqali to'lash va to'lov → buyurtma «to'langan»."""
from unittest import mock
from urllib.parse import parse_qs, urlparse

from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from apps.auth_app.models import Foydalanuvchi
from apps.buyurtmalar.models import Buyurtma
from .models import TolovSorovi
from .views import _click_signature

CLICK = dict(CLICK_SERVICE_ID='37118', CLICK_MERCHANT_ID='29100', CLICK_SECRET_KEY='sir', CLICK_YONALISHLAR='servis')


@override_settings(**CLICK)
@mock.patch('apps.sms_app.xodim_xabar.tolov_tekshiruvchilarga')
@mock.patch('apps.sms_app.gateway.sms_yubor')
class KabinetClickTest(TestCase):
    def setUp(self):
        from django.core.cache import cache
        cache.clear()
        self.mijoz = Foydalanuvchi.objects.create(telefon='+998901111111', rol='mijoz', ism='Ali')
        self.b = Buyurtma.objects.create(mijoz=self.mijoz, xizmat='servis', tasdiq_summa=250000)
        self.c = APIClient()
        self.c.force_authenticate(self.mijoz)

    def _url(self, b=None):
        return f'/api/tolovlar/click/buyurtma/{(b or self.b).id}/'

    def test_holat_va_tasdiqlangan_summa(self, *_):
        d = self.c.get(self._url()).json()
        self.assertEqual((d['mumkin'], d['summa']), (True, 250000))

    def test_montaj_hozircha_click_emas(self, *_):
        m = Buyurtma.objects.create(mijoz=self.mijoz, xizmat='montaj', tasdiq_summa=1000)
        self.assertFalse(self.c.get(self._url(m)).json()['mumkin'])
        self.assertEqual(self.c.post(self._url(m), {}, format='json').status_code, 400)

    def test_begona_buyurtma(self, *_):
        u = Foydalanuvchi.objects.create(telefon='+998902222222', rol='mijoz')
        c = APIClient()
        c.force_authenticate(u)
        self.assertEqual(c.post(self._url(), {}, format='json').status_code, 404)

    def test_tasdiqlangan_summa_mijoz_summasidan_ustun(self, *_):
        r = self.c.post(self._url(), {'summa': 1000}, format='json').json()
        q = parse_qs(urlparse(r['url']).query)
        self.assertEqual((q['service_id'][0], q['amount'][0]), ('37118', '250000.00'))
        self.assertEqual(TolovSorovi.objects.get(pk=r['sorov']).buyurtma_id, self.b.id)

    def test_summa_tasdiqlanmagan_bolsa_mijoz_kiritadi(self, *_):
        b = Buyurtma.objects.create(mijoz=self.mijoz, xizmat='servis')
        self.assertEqual(self.c.post(self._url(b), {}, format='json').status_code, 400)
        r = self.c.post(self._url(b), {'summa': '150 000'}, format='json')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()['summa'], 150000)

    def test_yangi_havola_eskisini_bekor_qiladi(self, *_):
        a = self.c.post(self._url(), {}, format='json').json()['sorov']
        self.c.post(self._url(), {}, format='json')
        self.assertEqual(TolovSorovi.objects.get(pk=a).holat, 'bekor')

    def _click(self, sorov_id, complete=False, prepare_id=''):
        d = {'click_trans_id': '777', 'service_id': '37118', 'merchant_trans_id': str(sorov_id),
             'amount': '250000.00', 'action': '1' if complete else '0', 'sign_time': '2026-11-20 12:00:00',
             'error': '0'}
        if complete:
            d['merchant_prepare_id'] = str(prepare_id)
        d['sign_string'] = _click_signature(d, 'sir', complete=complete)
        return APIClient().post(f"/api/tolovlar/click/{'complete' if complete else 'prepare'}/", d).json()

    def test_click_tolovi_buyurtmani_tolangan_qiladi(self, sms, xabar):
        sid = self.c.post(self._url(), {}, format='json').json()['sorov']
        p = self._click(sid)
        self.assertEqual(p['error'], 0, p)
        with self.captureOnCommitCallbacks(execute=True):
            c = self._click(sid, complete=True, prepare_id=p['merchant_prepare_id'])
        self.assertEqual(c['error'], 0, c)
        self.b.refresh_from_db()
        self.assertTrue(self.b.tolandi)
        self.assertIn('Click orqali qabul qilindi', sms.call_args.args[1])
        xabar.assert_called_once()
        # Endi qayta to'lab bo'lmaydi
        self.assertFalse(self.c.get(self._url()).json()['mumkin'])

    def test_mijoz_tolandi_ni_ozi_qoya_olmaydi(self, *_):
        r = self.c.post('/api/buyurtmalar/', {'xizmat': 'servis', 'tolandi': True}, format='json')
        self.assertEqual(r.status_code, 201, r.content)
        self.assertFalse(Buyurtma.objects.get(pk=r.json()['id']).tolandi)
