"""Payme va Click webhooklarining holat mashinasi testlari.

Bu yerda real pul harakati bor, shuning uchun har bir holat sinaladi: ikki
marta chaqirish (idempotentlik), noto'g'ri tartib (Perform — Create dan oldin),
bekor qilingan to'lovni qayta bajarish, muddat tugashi va eski havola.
"""
import base64
import time

from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from apps.xaridlar.models import Xarid
from apps.xaridlar.tolov import tolov_sorovi_yarat

from .models import TolovSorovi
from .views import _click_signature

SOZLAMA = dict(
    PAYME_KEY='payme-kalit', PAYME_MERCHANT_ID='m1',
    CLICK_SECRET_KEY='click-sir', CLICK_SERVICE_ID='11', CLICK_MERCHANT_ID='22',
)
SUMMA = 100000


def _sorov(tizim='payme', **kw):
    d = dict(ism='Ali', telefon='+998901234567', tolov_turi='online',
             tolov_tizimi=tizim, summa=SUMMA, holat='kutilmoqda')
    d.update(kw)
    return TolovSorovi.objects.create(**d)


@override_settings(**SOZLAMA)
class PaymeTest(TestCase):
    def setUp(self):
        self.c = APIClient()
        self.s = _sorov()
        self.c.credentials(HTTP_AUTHORIZATION='Basic ' + base64.b64encode(b'Paycom:payme-kalit').decode())

    def rpc(self, metod, **params):
        r = self.c.post('/api/tolovlar/payme/', {'jsonrpc': '2.0', 'id': 1, 'method': metod,
                                                 'params': params}, format='json')
        self.assertEqual(r.status_code, 200)
        return r.json()

    def hisob(self):
        return {'order_id': str(self.s.id)}

    def yarat(self, tid='tr-1', vaqt=None, **ustiga):
        return self.rpc('CreateTransaction', id=tid, time=vaqt or int(time.time() * 1000),
                        amount=SUMMA * 100, account=self.hisob(), **ustiga)

    # ── Avtorizatsiya ──
    def test_notogri_kalit(self):
        self.c.credentials(HTTP_AUTHORIZATION='Basic ' + base64.b64encode(b'Paycom:boshqa').decode())
        self.assertEqual(self.rpc('CheckTransaction', id='x')['error']['code'], -32504)

    def test_notogri_login(self):
        self.c.credentials(HTTP_AUTHORIZATION='Basic ' + base64.b64encode(b'Hacker:payme-kalit').decode())
        self.assertEqual(self.rpc('CheckTransaction', id='x')['error']['code'], -32504)

    def test_avtorizatsiyasiz(self):
        self.c.credentials()
        self.assertEqual(self.rpc('CheckTransaction', id='x')['error']['code'], -32504)

    # ── CheckPerformTransaction ──
    def test_check_perform_ok(self):
        r = self.rpc('CheckPerformTransaction', amount=SUMMA * 100, account=self.hisob())
        self.assertEqual(r['result'], {'allow': True})

    def test_check_perform_notogri_summa(self):
        r = self.rpc('CheckPerformTransaction', amount=5, account=self.hisob())
        self.assertEqual(r['error']['code'], -31001)

    def test_check_perform_buyurtma_yoq(self):
        r = self.rpc('CheckPerformTransaction', amount=SUMMA * 100, account={'order_id': '99999'})
        self.assertEqual(r['error']['code'], -31050)

    def test_check_perform_boshqa_tizim_sorovi_payme_dan_tolanmaydi(self):
        click = _sorov('click')
        r = self.rpc('CheckPerformTransaction', amount=SUMMA * 100,
                     account={'order_id': str(click.id)})
        self.assertEqual(r['error']['code'], -31050)

    def test_check_perform_tolangan_buyurtma_rad_etiladi(self):
        self.s.holat = 'tolandi'
        self.s.save()
        r = self.rpc('CheckPerformTransaction', amount=SUMMA * 100, account=self.hisob())
        self.assertEqual(r['error']['code'], -31051)

    # ── CreateTransaction ──
    def test_create_vaqtni_saqlaydi(self):
        r = self.yarat(vaqt=1700000000000)
        self.assertEqual(r['result']['create_time'], 1700000000000)
        self.assertEqual(r['result']['state'], 1)

    def test_create_takroriy_chaqiruv_birinchi_vaqtni_qaytaradi(self):
        vaqt = int(time.time() * 1000) - 5000
        birinchi = self.yarat(vaqt=vaqt)['result']
        ikkinchi = self.yarat(vaqt=vaqt + 3000)['result']
        self.assertEqual(ikkinchi['create_time'], vaqt)
        self.assertEqual(ikkinchi['transaction'], birinchi['transaction'])
        self.assertEqual(TolovSorovi.objects.filter(tashqi_id='tr-1').count(), 1)

    def test_create_boshqa_id_bilan_band_buyurtma(self):
        self.yarat('tr-1')
        r = self.yarat('tr-2')
        self.assertEqual(r['error']['code'], -31052)
        self.s.refresh_from_db()
        self.assertEqual(self.s.tashqi_id, 'tr-1')   # eskisi ustidan yozilmadi

    def test_create_notogri_summa(self):
        r = self.rpc('CreateTransaction', id='t', time=1, amount=1, account=self.hisob())
        self.assertEqual(r['error']['code'], -31001)

    def test_create_muddati_otgan_tranzaksiya(self):
        self.yarat()
        TolovSorovi.objects.filter(pk=self.s.pk).update(
            payme_yaratilgan=int(time.time() * 1000) - 13 * 3600 * 1000)
        r = self.yarat()
        self.assertEqual(r['error']['code'], -31008)
        self.s.refresh_from_db()
        self.assertEqual((self.s.holat, self.s.payme_sabab), ('bekor', 4))

    # ── PerformTransaction ──
    def test_perform_create_siz_rad_etiladi(self):
        r = self.rpc('PerformTransaction', id='yoq')
        self.assertEqual(r['error']['code'], -31003)

    def test_perform_va_takroriy_perform_bir_xil_vaqt(self):
        self.yarat()
        a = self.rpc('PerformTransaction', id='tr-1')['result']
        time.sleep(0.01)
        b = self.rpc('PerformTransaction', id='tr-1')['result']
        self.assertEqual(a['state'], 2)
        self.assertEqual(a['perform_time'], b['perform_time'])
        self.assertGreater(a['perform_time'], 0)
        self.s.refresh_from_db()
        self.assertEqual(self.s.holat, 'tolandi')

    def test_perform_bekor_qilingan_tranzaksiyani_tiklamaydi(self):
        self.yarat()
        self.rpc('CancelTransaction', id='tr-1', reason=2)
        r = self.rpc('PerformTransaction', id='tr-1')
        self.assertEqual(r['error']['code'], -31008)
        self.s.refresh_from_db()
        self.assertEqual(self.s.holat, 'bekor')

    def test_perform_muddati_otgan(self):
        self.yarat()
        TolovSorovi.objects.filter(pk=self.s.pk).update(
            payme_yaratilgan=int(time.time() * 1000) - 13 * 3600 * 1000)
        r = self.rpc('PerformTransaction', id='tr-1')
        self.assertEqual(r['error']['code'], -31008)
        self.s.refresh_from_db()
        self.assertEqual(self.s.holat, 'bekor')      # bekor qilish saqlanib qoldi
        self.assertEqual(self.s.payme_sabab, 4)

    # ── CancelTransaction ──
    def test_cancel_tolovdan_oldin(self):
        self.yarat()
        r = self.rpc('CancelTransaction', id='tr-1', reason=1)['result']
        self.assertEqual(r['state'], -1)
        t = self.rpc('CheckTransaction', id='tr-1')['result']
        self.assertEqual((t['state'], t['reason']), (-1, 1))

    def test_cancel_tolovdan_keyin_minus_2(self):
        self.yarat()
        self.rpc('PerformTransaction', id='tr-1')
        r = self.rpc('CancelTransaction', id='tr-1', reason=5)['result']
        self.assertEqual(r['state'], -2)

    def test_cancel_takroriy_chaqiruv_vaqt_ozgarmaydi(self):
        self.yarat()
        a = self.rpc('CancelTransaction', id='tr-1', reason=1)['result']
        time.sleep(0.01)
        b = self.rpc('CancelTransaction', id='tr-1', reason=1)['result']
        self.assertEqual(a['cancel_time'], b['cancel_time'])
        self.assertEqual(b['state'], -1)

    def test_cancel_mavjud_bolmagan_tranzaksiya(self):
        r = self.rpc('CancelTransaction', id='yoq', reason=1)
        self.assertEqual(r['error']['code'], -31003)

    def test_yetkazilgan_buyurtma_tolovini_qaytarib_bolmaydi(self):
        Xarid.objects.create(ism='A', telefon='+998901111111', tolov_usuli='payme',
                             jami=SUMMA, tolov_sorovi=self.s, holat='yetkazildi')
        self.yarat()
        self.rpc('PerformTransaction', id='tr-1')
        r = self.rpc('CancelTransaction', id='tr-1', reason=5)
        self.assertEqual(r['error']['code'], -31007)
        self.s.refresh_from_db()
        self.assertEqual(self.s.holat, 'tolandi')

    # ── CheckTransaction / GetStatement ──
    def test_check_transaction_toliq_malumot(self):
        vaqt = int(time.time() * 1000) - 1000
        self.yarat(vaqt=vaqt)
        self.rpc('PerformTransaction', id='tr-1')
        t = self.rpc('CheckTransaction', id='tr-1')['result']
        self.assertEqual(t['create_time'], vaqt)
        self.assertGreater(t['perform_time'], 0)
        self.assertEqual((t['cancel_time'], t['state'], t['reason']), (0, 2, None))

    def test_get_statement(self):
        self.yarat(vaqt=1700000000000)
        r = self.rpc('GetStatement', **{'from': 1700000000000 - 5, 'to': 1700000000000 + 5})
        t = r['result']['transactions']
        self.assertEqual(len(t), 1)
        self.assertEqual((t[0]['id'], t[0]['amount']), ('tr-1', SUMMA * 100))
        bosh = self.rpc('GetStatement', **{'from': 1, 'to': 2})['result']['transactions']
        self.assertEqual(bosh, [])

    def test_notanish_metod(self):
        self.assertEqual(self.rpc('Yoq')['error']['code'], -32601)

    # ── Xaridga ta'siri ──
    def test_tolov_xaridni_tolangan_qiladi(self):
        xarid = Xarid.objects.create(ism='A', telefon='+998901111111', tolov_usuli='payme',
                                     jami=SUMMA, tolov_sorovi=self.s)
        self.yarat()
        self.rpc('PerformTransaction', id='tr-1')
        xarid.refresh_from_db()
        self.assertTrue(xarid.tolandi)
        self.assertEqual(xarid.holat, 'tasdiqlandi')
        self.rpc('CancelTransaction', id='tr-1', reason=5)
        xarid.refresh_from_db()
        self.assertFalse(xarid.tolandi)


@override_settings(**SOZLAMA)
class ClickTest(TestCase):
    def setUp(self):
        self.c = APIClient()
        self.s = _sorov('click')

    def post(self, yol, complete=False, **ustiga):
        d = {'click_trans_id': '555', 'service_id': '11', 'merchant_trans_id': str(self.s.id),
             'amount': str(SUMMA), 'action': '1' if complete else '0', 'sign_time': '2026-01-01 10:00:00'}
        if complete:
            d['merchant_prepare_id'] = str(self.s.id)
            d['error'] = '0'
        d.update(ustiga)
        d['sign_string'] = ustiga.get('sign_string') or _click_signature(d, 'click-sir', complete=complete)
        return self.c.post(f'/api/tolovlar/click/{yol}/', d, format='json').json()

    def test_prepare_va_complete(self):
        self.assertEqual(self.post('prepare')['error'], 0)
        self.assertEqual(self.post('complete', complete=True)['error'], 0)
        self.s.refresh_from_db()
        self.assertEqual((self.s.holat, self.s.tashqi_id), ('tolandi', '555'))

    def test_notogri_imzo(self):
        self.assertEqual(self.post('prepare', sign_string='x')['error'], -1)

    def test_imzosiz_sorov_500_bermaydi(self):
        r = self.c.post('/api/tolovlar/click/prepare/', {'merchant_trans_id': '1'}, format='json')
        self.assertEqual(r.json()['error'], -1)

    def test_notogri_summa(self):
        self.assertEqual(self.post('prepare', amount='5')['error'], -2)

    def test_prepare_siz_complete_rad_etiladi(self):
        self.assertEqual(self.post('complete', complete=True)['error'], -6)
        self.s.refresh_from_db()
        self.assertEqual(self.s.holat, 'kutilmoqda')

    def test_boshqa_click_id_bilan_complete_rad_etiladi(self):
        self.post('prepare')
        self.assertEqual(self.post('complete', complete=True, click_trans_id='999')['error'], -6)

    def test_takroriy_complete_allaqachon_tolangan(self):
        self.post('prepare')
        self.post('complete', complete=True)
        self.assertEqual(self.post('complete', complete=True)['error'], -4)
        self.assertEqual(self.post('prepare')['error'], -4)

    def test_click_xato_xabar_qilsa_bekor_qilinadi(self):
        self.post('prepare')
        r = self.post('complete', complete=True, error='-5017')
        self.assertEqual(r['error'], -9)
        self.s.refresh_from_db()
        self.assertEqual(self.s.holat, 'bekor')
        self.assertEqual(self.post('prepare')['error'], -9)

    def test_payme_sorovi_click_dan_tolanmaydi(self):
        self.s.tolov_tizimi = 'payme'
        self.s.save()
        self.assertEqual(self.post('prepare')['error'], -5)


@override_settings(**SOZLAMA)
class QaytaUrinishTest(TestCase):
    """Mijoz to'lovni qayta boshlasa, ESKI havola orqali to'lab bo'lmaydi."""

    def setUp(self):
        self.xarid = Xarid.objects.create(ism='A', telefon='+998901111111',
                                          tolov_usuli='payme', jami=SUMMA)

    def test_eski_sorov_bekor_qilinadi_va_tolanmaydi(self):
        birinchi = tolov_sorovi_yarat(self.xarid)
        ikkinchi = tolov_sorovi_yarat(self.xarid)
        birinchi.refresh_from_db()
        self.xarid.refresh_from_db()
        self.assertEqual(birinchi.holat, 'bekor')
        self.assertEqual(self.xarid.tolov_sorovi_id, ikkinchi.id)
        self.assertEqual(self.xarid.tolov_holati, 'kutilmoqda')

        c = APIClient()
        c.credentials(HTTP_AUTHORIZATION='Basic ' + base64.b64encode(b'Paycom:payme-kalit').decode())
        r = c.post('/api/tolovlar/payme/', {'id': 1, 'method': 'CheckPerformTransaction', 'params': {
            'amount': SUMMA * 100, 'account': {'order_id': str(birinchi.id)}}}, format='json').json()
        self.assertEqual(r['error']['code'], -31051)

    def test_tolangan_sorov_qayta_urinishda_bekor_qilinmaydi(self):
        birinchi = tolov_sorovi_yarat(self.xarid)
        TolovSorovi.objects.filter(pk=birinchi.pk).update(holat='tolandi')
        birinchi.refresh_from_db()
        tolov_sorovi_yarat(self.xarid)
        birinchi.refresh_from_db()
        self.assertEqual(birinchi.holat, 'tolandi')
