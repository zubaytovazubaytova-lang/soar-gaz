"""Manzil matnidan xaritadagi joyni topish (OpenStreetMap Nominatim; testda tarmoqqa chiqilmaydi)."""
from unittest import mock

from apps.buyurtmalar import operator as op
from apps.buyurtmalar.tests_operator import Asos, klient

GEOKOD = '/api/buyurtmalar/operator/geokod/'
TOPILDI = [{'nomi': "Turdi Farog'iy ko'chasi, Buxoro shahri", 'lat': 39.737, 'lng': 64.4269}]


class GeokodTestlari(Asos):
    def so_ra(self, user=None, manzil="Turdi Farog'iy", tuman='Buxoro shahar'):
        return klient(user or self.call).get(GEOKOD, {'manzil': manzil, 'tuman': tuman})

    def test_topildi(self):
        with mock.patch.object(op, '_nominatim', return_value=TOPILDI) as m:
            r = self.so_ra()
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()['aniqlik'], 'manzil')
        self.assertEqual(r.json()['natijalar'][0]['lat'], 39.737)
        # Qidiruvga viloyat qo'shiladi, boshqa hech narsa (ism, telefon) ketmaydi
        m.assert_called_once_with("Turdi Farog'iy, Buxoro, Buxoro viloyati")

    def test_yozilish_farqi_apostrof(self):
        with mock.patch.object(op, '_nominatim', return_value=TOPILDI) as m:
            self.so_ra(manzil="Turdi Farogʻiy")                   # ʻ — boshqa apostrof
        self.assertIn("Farog'iy", m.call_args[0][0])

    def test_ketma_ket_urinishlar(self):
        """To'liq manzil topilmasa — birinchi so'z (taxminiy); u ham topilmasa — tuman markazi."""
        with mock.patch.object(op, '_nominatim', side_effect=[[], TOPILDI]) as m:
            j = self.so_ra(manzil='Turdi farobiy').json()
        self.assertEqual(j['aniqlik'], 'taxminiy')
        self.assertEqual([c[0][0] for c in m.call_args_list],
                         ['Turdi farobiy, Buxoro, Buxoro viloyati', 'Turdi, Buxoro, Buxoro viloyati'])

        with mock.patch.object(op, '_nominatim', side_effect=[[], [], TOPILDI]) as m:
            j = self.so_ra(manzil='Noma lum kocha 5').json()
        self.assertEqual(j['aniqlik'], 'hudud')
        self.assertEqual(m.call_args_list[-1][0][0], 'Buxoro, Buxoro viloyati')

    def test_hech_narsa_topilmasa(self):
        with mock.patch.object(op, '_nominatim', return_value=[]):
            j = self.so_ra(manzil='qqqq wwww').json()
        self.assertEqual((j['aniqlik'], j['natijalar']), ('yoq', []))

    def test_viloyat_yozilgan_bolsa_qoshilmaydi(self):
        with mock.patch.object(op, '_nominatim', return_value=TOPILDI) as m:
            self.so_ra(tuman='Samarqand viloyati, Urgut')
        self.assertEqual(m.call_args[0][0], "Turdi Farog'iy, Samarqand viloyati, Urgut")

    def test_kesh_bir_xil_manzilga_ikkinchi_marta_chiqmaydi(self):
        with mock.patch.object(op, '_nominatim', return_value=TOPILDI) as m:
            self.so_ra()
            self.so_ra()
            self.so_ra(user=self.kadr)             # ikkinchi xodim (Ruxsora) ham keshdan oladi
        self.assertEqual(m.call_count, 1)

    def test_xizmat_ishlamasa_502(self):
        with mock.patch.object(op, '_nominatim', side_effect=op.GeokodXato('timeout')):
            r = self.so_ra()
        self.assertEqual(r.status_code, 502)
        self.assertIn('xaritadan', r.json()['detail'])

    def test_notogri_kiritish(self):
        with mock.patch.object(op, '_nominatim', return_value=TOPILDI) as m:
            self.assertEqual(self.so_ra(manzil='ab').status_code, 400)
            self.assertEqual(klient(self.call).get(GEOKOD).status_code, 400)
        m.assert_not_called()

    def test_daqiqalik_limit(self):
        with mock.patch.object(op, '_nominatim', return_value=TOPILDI):
            for i in range(op.GEOKOD_DAQIQALIK_LIMIT):
                self.assertEqual(self.so_ra(manzil=f'Kocha {i}').status_code, 200)
            self.assertEqual(self.so_ra(manzil='Yangi kocha').status_code, 429)
            self.assertEqual(self.so_ra(manzil='Kocha 1').status_code, 200)     # keshdagi hali ishlaydi

    def test_ruxsatlar(self):
        with mock.patch.object(op, '_nominatim', return_value=TOPILDI) as m:
            for u in (self.usta, self.servis, self.mijoz, self.admin):
                self.assertEqual(self.so_ra(u).status_code, 403)
            self.assertEqual(klient().get(GEOKOD).status_code, 401)
            self.assertEqual(self.so_ra(self.kadr).status_code, 200)             # Ruxsora ham, Nargiza ham
        self.assertEqual(m.call_count, 1)

    def test_nominatim_javobini_tozalash(self):
        """Haqiqiy so'rov kodi: noto'g'ri javob va O'zbekistondan tashqari nuqtalar tashlanadi."""
        class Javob:
            def __enter__(self): return self
            def __exit__(self, *a): return False
            def read(self):
                return (b'[{"display_name":"A","lat":"39.7","lon":"64.4"},'
                        b'{"display_name":"Moskva","lat":"55.7","lon":"37.6"},'
                        b'{"display_name":"Buzuq","lat":"x","lon":"y"},{"display_name":"Yo\'q"}]')
        with mock.patch('urllib.request.urlopen', return_value=Javob()) as u, \
                mock.patch('time.sleep'):
            natija = op._nominatim('sinov')
        self.assertEqual([n['nomi'] for n in natija], ['A'])
        sorov = u.call_args[0][0]
        self.assertIn('countrycodes=uz', sorov.full_url)
        self.assertIn('SoarGaz', sorov.get_header('User-agent'))

    def test_umumiy_sozlar_va_uy_raqami_tashlanadi(self):
        """«shahar», «tumani» va uy raqami qidiruvni buzadi — tashlab yuboriladi."""
        with mock.patch.object(op, '_nominatim', return_value=TOPILDI) as m:
            self.so_ra(manzil="Navoiy ko'chasi 12-uy", tuman='Kogon tumani')
        self.assertEqual(m.call_args[0][0], "Navoiy ko'chasi, Kogon, Buxoro viloyati")

    def test_tuman_bosh_bolsa_viloyat_markazi(self):
        with mock.patch.object(op, '_nominatim', side_effect=[[], [], TOPILDI]) as m:
            j = self.so_ra(manzil='Noma lum kocha', tuman='').json()
        self.assertEqual(j['aniqlik'], 'hudud')
        self.assertEqual(m.call_args_list[-1][0][0], 'Buxoro viloyati')
