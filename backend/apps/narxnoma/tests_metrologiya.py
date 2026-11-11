"""Saytdagi Metrologiya narxlari: ochiq endpoint faqat o'qiydi va ichki ma'lumotni chiqarmaydi.

Test bazasi migratsiyalardan quriladi, shuning uchun 0009 dagi narxlar tayyor turadi."""
from django.core.cache import cache
from django.test import TestCase
from rest_framework.test import APIClient

from .models import Narxnoma, NarxnomaQator

URL = '/api/narxnoma/metrologiya/'


class MetrologiyaNarxTest(TestCase):
    def setUp(self):
        cache.clear()                      # throttle hisoblagichi testlar orasida tozalansin
        self.c = APIClient()

    def test_tokensiz_ochiq(self):
        r = self.c.get(URL)
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(set(r.json()), {'ulgurji', 'aholi'})

    def test_notogri_token_401_bermaydi(self):
        self.c.credentials(HTTP_AUTHORIZATION='Bearer yaroqsiz.token.qiymat')
        self.assertEqual(self.c.get(URL).status_code, 200)

    def test_ulgurji_narxlar_xizmatlarga_biriktirilgan(self):
        x = self.c.get(URL).json()['ulgurji']['xizmatlar']
        self.assertEqual([q['narx_dan'] for q in x['qiyoslov']], [1290000, 2780000])
        self.assertEqual(len(x['almashtirish']), 8)
        self.assertEqual(x['kalibrovka'], [])                  # narxnomada kalibrovka bandi yo'q
        for q in x['qiyoslov']:
            self.assertIn('DKQ', q['izoh'])

    def test_aholi_faqat_uchta_narx(self):
        x = self.c.get(URL).json()['aholi']['xizmatlar']
        self.assertEqual([q['narx_dan'] for q in x['almashtirish']], [400000, 750000, 600000])
        self.assertEqual(x['qiyoslov'], [])

    def test_ulgurji_eslatmada_qqs_va_material_bor(self):
        e = self.c.get(URL).json()['ulgurji']['eslatma']
        self.assertIn('QQS', e)
        self.assertIn('material', e)

    def test_ichki_maydonlar_chiqmaydi(self):
        q = self.c.get(URL).json()['ulgurji']['xizmatlar']['almashtirish'][0]
        self.assertEqual(set(q), {'tartib', 'nomi', 'narx_dan', 'narx_gacha', 'izoh'})

    def test_nofaol_qator_va_narxnoma_chiqmaydi(self):
        NarxnomaQator.objects.filter(narxnoma__tarmoq='ulgurji', narxnoma__bolim='metrologiya',
                                     tartib=1).update(faol=False)
        n = self.c.get(URL).json()['ulgurji']['xizmatlar']['almashtirish']
        self.assertNotIn('Aloqaga chiqarish', [q['nomi'] for q in n])
        Narxnoma.objects.filter(tarmoq='aholi', bolim='metrologiya').update(faol=False)
        self.assertNotIn('aholi', self.c.get(URL).json())

    def test_belgilanmagan_qator_chiqmaydi(self):
        NarxnomaQator.objects.filter(narxnoma__tarmoq='ulgurji', narxnoma__bolim='metrologiya',
                                     tartib=2).update(sayt_xizmat='')
        n = self.c.get(URL).json()['ulgurji']['xizmatlar']['almashtirish']
        self.assertNotIn('Modem kabelini almashtirish', [q['nomi'] for q in n])

    def test_boshqa_bolim_narxnomalari_chiqmaydi(self):
        # Aholining profilaktika/o'rnatish narxnomalari saytdagi metrologiya javobiga tushmaydi
        for t in self.c.get(URL).json().values():
            for lst in t['xizmatlar'].values():
                for q in lst:
                    self.assertNotIn('kamparakli', q['nomi'])

    def test_yozish_mumkin_emas(self):
        for metod in ('post', 'put', 'patch', 'delete'):
            r = getattr(self.c, metod)(URL, {'narx_dan': 1}, format='json')
            self.assertEqual(r.status_code, 405, metod)
        self.assertEqual(NarxnomaQator.objects.filter(p_dan=1).count(), 0)

    def test_throttle(self):
        for _ in range(120):
            self.assertEqual(self.c.get(URL).status_code, 200)
        self.assertEqual(self.c.get(URL).status_code, 429)

    def test_migratsiya_ikki_marta_narx_qoshmaydi(self):
        from importlib import import_module
        from django.apps import apps as dj_apps
        m = import_module('apps.narxnoma.migrations.0009_metrologiya_narxlari')
        soni = NarxnomaQator.objects.count()
        m.kirit(dj_apps, None)
        self.assertEqual(NarxnomaQator.objects.count(), soni)
