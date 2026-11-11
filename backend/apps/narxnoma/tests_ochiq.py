"""Saytdagi ochiq "Narxnoma" oynasi: hamma ko'ra oladi, lekin ichki ma'lumot chiqmaydi,
xodimlar uchun yopiq ro'yxat esa avvalgidek yopiq qoladi."""
from django.core.cache import cache
from django.test import TestCase
from rest_framework.test import APIClient

from .models import Narxnoma, NarxnomaQator

URL = '/api/narxnoma/ochiq/'


class OchiqNarxnomaTest(TestCase):
    def setUp(self):
        cache.clear()
        self.c = APIClient()

    def test_tokensiz_ochiq(self):
        r = self.c.get(URL)
        self.assertEqual(r.status_code, 200, r.content)
        self.assertTrue(r.json())

    def test_notogri_token_401_bermaydi(self):
        self.c.credentials(HTTP_AUTHORIZATION='Bearer yaroqsiz.token.qiymat')
        self.assertEqual(self.c.get(URL).status_code, 200)

    def test_ikkala_tarmoq_chiqadi(self):
        tarmoqlar = {n['tarmoq'] for n in self.c.get(URL).json()}
        self.assertEqual(tarmoqlar, {'ulgurji', 'aholi'})

    def test_ichki_maydonlar_chiqmaydi(self):
        n = self.c.get(URL).json()[0]
        self.assertNotIn('id', n)
        self.assertNotIn('yangilangan', n)
        self.assertNotIn('faol', n)
        for q in n['qatorlar']:
            self.assertEqual(set(q), {'tartib', 'nomi', 'p_dan', 'p_gacha', 'r_dan', 'r_gacha', 'izoh'})

    def test_nofaol_narxnoma_va_qator_chiqmaydi(self):
        n = Narxnoma.objects.filter(faol=True).first()
        q = n.qatorlar.filter(faol=True).first()
        q.faol = False
        q.save()
        royxat = self.c.get(URL).json()
        topilgan = next(x for x in royxat if x['tarmoq'] == n.tarmoq and x['bolim'] == n.bolim)
        self.assertNotIn(q.nomi, [r['nomi'] for r in topilgan['qatorlar']])
        Narxnoma.objects.filter(pk=n.pk).update(faol=False)
        royxat = self.c.get(URL).json()
        self.assertFalse([x for x in royxat if x['tarmoq'] == n.tarmoq and x['bolim'] == n.bolim])

    def test_xodimlar_royxati_tokensiz_yopiq_qoladi(self):
        self.assertIn(self.c.get('/api/narxnoma/').status_code, (401, 403))
