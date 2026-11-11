"""Hujjatlar bilan ishlovchi xodim: mijozdan kelgan ishlar, hujjat tayyorlash va mijozga yuborish."""
import shutil
import tempfile

from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from apps.auth_app.models import AuditYozuv, Foydalanuvchi
from apps.buyurtmalar.models import Buyurtma
from apps.hujjatlar.models import HujjatLoyiha
from apps.kabinet.models import Bildirishnoma, Hujjat as KabinetHujjat
from apps.sms_app.models import SmsXabar
from apps.tolovlar.models import MetrologiyaArizasi

ISH = '/api/hujjatlar/ish/'
MEDIA = tempfile.mkdtemp(prefix='soargaz-test-media-')


def klient(user=None):
    c = APIClient()
    if user:
        c.credentials(HTTP_AUTHORIZATION='Bearer ' + str(RefreshToken.for_user(user).access_token))
    return c


def fayl(nom='loyiha.pdf', mazmun=b'%PDF-1.4 sinov'):
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
        self.ferangiz = mk(telefon='+998900000601', ism='Ferangiz', rol='xodim', holat='faol',
                           lavozim="Mehnat muhofazasi va texnika xavfsizligi bo'yicha muhandis")
        self.usta = mk(telefon='+998900000602', ism='Aziz', rol='xodim', holat='faol', lavozim='Montaj ustasi')
        self.kadr = mk(telefon='+998900000603', ism='Ruxsora', rol='xodim', holat='faol',
                       lavozim="Kadrlar bo'yicha mutaxassis")
        self.call = mk(telefon='+998900000604', ism='Nargiza', rol='xodim', holat='faol',
                       lavozim='Call center operatori')
        self.mijoz = mk(telefon='+998901110000', ism='Karim', rol='mijoz')
        self.admin = mk(telefon='+998900000605', ism='Ega', rol='admin', is_staff=True, is_superuser=True)
        self.ariza = MetrologiyaArizasi.objects.create(
            ism='Anvar', telefon='90 777-66-55', xizmat='kalibrovka', hisoblagich='G4', seriya_raqam='123',
            manzil='Kogon')
        self.loyiha = Buyurtma.objects.create(mijoz=self.mijoz, xizmat='loyiha', manzil='Zavod', tuman='Buxoro')
        self.metr = Buyurtma.objects.create(mijoz=self.mijoz, xizmat='metrologiya', manzil='Olot')
        self.montaj = Buyurtma.objects.create(mijoz=self.mijoz, xizmat='montaj', manzil='Kogon')


class KabinetTuriTestlari(TestCase):
    def test_tur(self):
        from apps.auth_app.kabinet_turlari import BOLIMLAR, kabinet_malumoti, kabinet_turi
        for lavozim in ("Mehnat muhofazasi va texnika xavfsizligi bo'yicha muhandis", 'Hujjatlar mutaxassisi'):
            self.assertEqual(kabinet_turi(lavozim), 'hujjat', lavozim)
        for lavozim in ('Montaj ustasi', 'Metrolog', 'Loyihachi muhandis', 'Muhandis'):
            self.assertEqual(kabinet_turi(lavozim), 'oddiy', lavozim)
        m = kabinet_malumoti("Mehnat muhofazasi va texnika xavfsizligi bo'yicha muhandis")['bolimlar']
        # Oddiy xodim kabineti + yangi bo'lim
        # (lekin «Pul tushumi» — cash — yo'q: hujjatchi mijozdan pul olmaydi)
        self.assertEqual(set(m), (set(BOLIMLAR['oddiy']) | {'hj-ishlar', 'hj-yuborish', 'topshiriq'}) - {'cash'})
        for tur in ('oddiy', 'qongiroq', 'kadrlar'):
            self.assertNotIn('hj-ishlar', BOLIMLAR[tur])


class RuxsatTestlari(Asos):
    def test_faqat_hujjat_xodimi(self):
        for u in (self.usta, self.kadr, self.call, self.mijoz, self.admin):
            c = klient(u)
            self.assertEqual(c.get(ISH).status_code, 403, u.lavozim or u.rol)
            self.assertEqual(c.post(f'{ISH}a{self.ariza.id}/holat/', {'holat': 'korildi'}).status_code, 403)
            self.assertEqual(c.post(f'{ISH}a{self.ariza.id}/hujjat/', {'fayl': fayl()}, format='multipart').status_code, 403)
            self.assertEqual(c.post(f'{ISH}hujjat/1/yuborish/').status_code, 403)
            self.assertEqual(c.delete(f'{ISH}hujjat/1/').status_code, 403)
        self.assertEqual(klient().get(ISH).status_code, 401)
        self.assertEqual(klient(self.ferangiz).get(ISH).status_code, 200)

    def test_nofaol_kira_olmaydi(self):
        self.ferangiz.holat = 'nofaol'
        self.ferangiz.save()
        self.assertEqual(klient(self.ferangiz).get(ISH).status_code, 403)


class RoyxatTestlari(Asos):
    def royxat(self, **q):
        return klient(self.ferangiz).get(ISH, q).json()

    def test_faqat_metrologiya_loyiha(self):
        j = self.royxat(bosqich='hammasi')
        kalitlar = {i['kalit'] for i in j['ishlar']}
        self.assertEqual(kalitlar, {f'a{self.ariza.id}', f'b{self.loyiha.id}', f'b{self.metr.id}'})   # montaj yo'q

    def test_narx_va_summa_yoq(self):
        for i in self.royxat(bosqich='hammasi')['ishlar']:
            for yashirin in ('tasdiq_summa', 'summa', 'xizmatlar', 'shartnoma'):
                self.assertNotIn(yashirin, i)

    def test_bosqichlar(self):
        self.ariza.holat = 'korildi'
        self.ariza.save()
        Buyurtma.objects.filter(pk=self.loyiha.pk).update(holat='bajarildi')
        self.assertEqual({i['kalit'] for i in self.royxat(bosqich='yangi')['ishlar']}, {f'b{self.metr.id}'})
        self.assertEqual({i['kalit'] for i in self.royxat(bosqich='qabul')['ishlar']}, {f'a{self.ariza.id}'})
        self.assertEqual({i['kalit'] for i in self.royxat(bosqich='yakun')['ishlar']}, {f'b{self.loyiha.id}'})
        faol = {i['kalit'] for i in self.royxat()['ishlar']}                       # standart = faol
        self.assertEqual(faol, {f'a{self.ariza.id}', f'b{self.metr.id}'})
        self.assertEqual(self.royxat(tur='ariza', bosqich='hammasi')['xulosa']['yangi'], 1)

    def test_qidiruv(self):
        self.assertEqual({i['kalit'] for i in self.royxat(q='Anvar', bosqich='hammasi')['ishlar']}, {f'a{self.ariza.id}'})
        self.assertEqual({i['kalit'] for i in self.royxat(q='Zavod', bosqich='hammasi')['ishlar']}, {f'b{self.loyiha.id}'})
        self.assertEqual({i['kalit'] for i in self.royxat(q=f'b{self.metr.id}', bosqich='hammasi')['ishlar']},
                         {f'b{self.metr.id}'})


class HolatTestlari(Asos):
    def test_ariza_qabul_qilish(self):
        r = klient(self.ferangiz).post(f'{ISH}a{self.ariza.id}/holat/', {'holat': 'korildi'})
        self.assertEqual(r.status_code, 200)
        self.ariza.refresh_from_db()
        self.assertEqual(self.ariza.holat, 'korildi')
        self.assertTrue(r.json()['tayyorlash_mumkin'])

    def test_notogri_holat_va_buyurtma(self):
        c = klient(self.ferangiz)
        self.assertEqual(c.post(f'{ISH}a{self.ariza.id}/holat/', {'holat': 'yangi'}).status_code, 400)
        self.assertEqual(c.post(f'{ISH}a{self.ariza.id}/holat/', {'holat': 'xato'}).status_code, 400)
        self.assertEqual(c.post(f'{ISH}b{self.loyiha.id}/holat/', {'holat': 'qabul'}).status_code, 400)   # buyurtmani xodimi boshqaradi
        self.assertEqual(c.post(f'{ISH}b{self.montaj.id}/holat/', {'holat': 'qabul'}).status_code, 404)   # montaj bu yerga tegishli emas
        self.assertEqual(c.post(f'{ISH}x1/holat/', {'holat': 'korildi'}).status_code, 404)


class YuklashTestlari(Asos):
    def yukla(self, kalit, f=None, **ustiga):
        d = {'fayl': f or fayl(), 'nom': 'Loyiha hujjati', 'turi': 'hisobot'}
        d.update(ustiga)
        return klient(self.ferangiz).post(f'{ISH}{kalit}/hujjat/', d, format='multipart')

    def qabul(self):
        MetrologiyaArizasi.objects.filter(pk=self.ariza.pk).update(holat='korildi')
        Buyurtma.objects.filter(pk=self.loyiha.pk).update(holat='qabul')

    def test_qabul_qilinmagan_ish_uchun_yuklab_bolmaydi(self):
        self.assertEqual(self.yukla(f'a{self.ariza.id}').status_code, 409)
        self.assertEqual(self.yukla(f'b{self.loyiha.id}').status_code, 409)
        self.assertEqual(HujjatLoyiha.objects.count(), 0)

    def test_yuklash(self):
        self.qabul()
        r = self.yukla(f'a{self.ariza.id}')
        self.assertEqual(r.status_code, 201, r.content)
        h = HujjatLoyiha.objects.get()
        self.assertEqual((h.ariza, h.buyurtma, h.nom, h.turi, h.tayyorlagan), (self.ariza, None, 'Loyiha hujjati', 'hisobot', self.ferangiz))
        self.assertIsNone(h.yuborilgan)
        self.assertEqual(len(r.json()['ish']['hujjatlar']), 1)
        r = self.yukla(f'b{self.loyiha.id}', fayl('chizma.dwg', b'DWG'))
        self.assertEqual(r.status_code, 201)
        self.assertEqual(HujjatLoyiha.objects.filter(buyurtma=self.loyiha).count(), 1)

    def test_nom_bosh_bolsa_fayl_nomi(self):
        self.qabul()
        self.yukla(f'a{self.ariza.id}', fayl('Akt-12.pdf'), nom='')
        self.assertEqual(HujjatLoyiha.objects.get().nom, 'Akt-12')

    def test_notogri_fayllar(self):
        self.qabul()
        k = f'a{self.ariza.id}'
        self.assertEqual(self.yukla(k, fayl('virus.exe', b'MZ')).status_code, 400)
        self.assertEqual(self.yukla(k, fayl('x.html', b'<script>')).status_code, 400)
        self.assertEqual(self.yukla(k, fayl('bosh.pdf', b'')).status_code, 400)
        self.assertEqual(self.yukla(k, fayl('katta.pdf', b'x' * (30 * 1024 * 1024 + 1))).status_code, 400)
        r = klient(self.ferangiz).post(f'{ISH}{k}/hujjat/', {'nom': 'faylsiz'}, format='multipart')
        self.assertEqual(r.status_code, 400)
        self.assertEqual(HujjatLoyiha.objects.count(), 0)

    def test_notogri_tur_boshqaga_tushadi(self):
        self.qabul()
        self.yukla(f'a{self.ariza.id}', turi='qalbaki')
        self.assertEqual(HujjatLoyiha.objects.get().turi, 'boshqa')

    def test_ochirish(self):
        self.qabul()
        self.yukla(f'a{self.ariza.id}')
        h = HujjatLoyiha.objects.get()
        c = klient(self.ferangiz)
        self.assertEqual(c.delete(f'{ISH}hujjat/{h.id}/').status_code, 204)
        self.assertEqual(HujjatLoyiha.objects.count(), 0)
        self.assertEqual(c.delete(f'{ISH}hujjat/{h.id}/').status_code, 404)


class YuborishTestlari(Asos):
    def tayyor(self, ob):
        MetrologiyaArizasi.objects.filter(pk=self.ariza.pk).update(holat='korildi')
        Buyurtma.objects.filter(pk=self.loyiha.pk).update(holat='qabul')
        d = {'fayl': fayl(), 'nom': 'Metrologiya dalolatnomasi', 'turi': 'sertifikat'}
        r = klient(self.ferangiz).post(f'{ISH}{ob}/hujjat/', d, format='multipart')
        self.assertEqual(r.status_code, 201, r.content)
        return HujjatLoyiha.objects.latest('id')

    def yubor(self, h):
        return klient(self.ferangiz).post(f'{ISH}hujjat/{h.id}/yuborish/')

    def test_buyurtma_mijoziga_yuborish(self):
        h = self.tayyor(f'b{self.loyiha.id}')
        r = self.yubor(h)
        self.assertEqual(r.status_code, 200, r.content)
        h.refresh_from_db()
        self.assertIsNotNone(h.yuborilgan)
        self.assertEqual(h.yuborgan, self.ferangiz)
        kh = KabinetHujjat.objects.get(mijoz=self.mijoz)
        self.assertEqual((kh.nom, kh.turi, kh.fayl.name), ('Metrologiya dalolatnomasi', 'sertifikat', h.fayl.name))
        self.assertTrue(Bildirishnoma.objects.filter(mijoz=self.mijoz, sarlavha__contains='Yangi hujjat').exists())
        self.assertTrue(SmsXabar.objects.filter(mijoz=self.mijoz, matn__contains='tayyor').exists())
        self.assertTrue(AuditYozuv.objects.filter(amal='hujjat_yuborildi', kim=self.ferangiz).exists())

    def test_mijoz_kabinetida_koradi_qoralama_korinmaydi(self):
        h1 = self.tayyor(f'b{self.loyiha.id}')
        self.tayyor(f'b{self.loyiha.id}')                          # ikkinchisi yuborilmaydi (qoralama)
        self.yubor(h1)
        j = klient(self.mijoz).get('/api/kabinet/hujjatlar/').json()
        self.assertEqual(len(j), 1)
        self.assertEqual(j[0]['nom'], 'Metrologiya dalolatnomasi')

    def test_saytdan_kelgan_arizaga_mijoz_ochiladi(self):
        h = self.tayyor(f'a{self.ariza.id}')
        self.assertFalse(Foydalanuvchi.objects.filter(telefon='+998907776655').exists())
        r = self.yubor(h)
        self.assertEqual(r.status_code, 200, r.content)
        mijoz = Foydalanuvchi.objects.get(telefon='+998907776655')
        self.assertEqual((mijoz.rol, mijoz.ism), ('mijoz', 'Anvar'))
        self.assertTrue(KabinetHujjat.objects.filter(mijoz=mijoz).exists())

    def test_ikki_marta_yuborilmaydi(self):
        h = self.tayyor(f'b{self.loyiha.id}')
        self.assertEqual(self.yubor(h).status_code, 200)
        self.assertEqual(self.yubor(h).status_code, 409)
        self.assertEqual(KabinetHujjat.objects.count(), 1)

    def test_yuborilganni_ochirib_bolmaydi(self):
        h = self.tayyor(f'b{self.loyiha.id}')
        self.yubor(h)
        self.assertEqual(klient(self.ferangiz).delete(f'{ISH}hujjat/{h.id}/').status_code, 409)
        self.assertTrue(HujjatLoyiha.objects.filter(pk=h.pk).exists())

    def test_mijozsiz_buyurtma(self):
        h = self.tayyor(f'b{self.loyiha.id}')
        Buyurtma.objects.filter(pk=self.loyiha.pk).update(mijoz=None)
        self.assertEqual(self.yubor(h).status_code, 409)
        h.refresh_from_db()
        self.assertIsNone(h.yuborilgan)

    def test_xodim_telefoniga_yuborib_bolmaydi(self):
        h = self.tayyor(f'a{self.ariza.id}')
        MetrologiyaArizasi.objects.filter(pk=self.ariza.pk).update(telefon=self.usta.telefon)
        r = self.yubor(h)
        self.assertEqual(r.status_code, 409)
        h.refresh_from_db()
        self.assertIsNone(h.yuborilgan)
        self.assertEqual(KabinetHujjat.objects.count(), 0)


@override_settings(MEDIA_ROOT=MEDIA)
class YuborishBolimiTestlari(YuborishTestlari):
    """«Mijozga yuborish» bo'limi: hamma ishlar bo'yicha tayyor/yuborilgan hujjatlar ro'yxati."""

    def royxat(self, user=None, **q):
        return klient(user or self.ferangiz).get(ISH + 'hujjatlar/', q)

    def test_faqat_hujjat_xodimi(self):
        for u in (self.usta, self.kadr, self.call, self.mijoz, self.admin):
            self.assertEqual(self.royxat(u).status_code, 403, u.ism)
        self.assertEqual(klient().get(ISH + 'hujjatlar/').status_code, 401)

    def test_tayyor_va_yuborilgan(self):
        h1 = self.tayyor(f'b{self.loyiha.id}')
        h2 = self.tayyor(f'a{self.ariza.id}')
        j = self.royxat().json()
        self.assertEqual({d['id'] for d in j['hujjatlar']}, {h1.id, h2.id})
        self.assertEqual(j['xulosa']['tayyor'], 2)
        d1 = next(d for d in j['hujjatlar'] if d['id'] == h1.id)
        self.assertEqual((d1['ish_kalit'], d1['mijoz_ism'], d1['yuborish_mumkin']), (f'b{self.loyiha.id}', 'Karim', True))
        d2 = next(d for d in j['hujjatlar'] if d['id'] == h2.id)
        self.assertEqual((d2['ish_kalit'], d2['mijoz_ism']), (f'a{self.ariza.id}', 'Anvar'))

        self.assertEqual(self.yubor(h1).status_code, 200)
        self.assertEqual([d['id'] for d in self.royxat().json()['hujjatlar']], [h2.id])
        yuborilgan = self.royxat(holat='yuborilgan').json()
        self.assertEqual([d['id'] for d in yuborilgan['hujjatlar']], [h1.id])
        self.assertEqual(yuborilgan['xulosa']['bugun_yuborilgan'], 1)
        self.assertEqual(len(self.royxat(holat='hammasi').json()['hujjatlar']), 2)

    def test_qidiruv(self):
        self.tayyor(f'b{self.loyiha.id}')
        self.assertEqual(len(self.royxat(q='Karim').json()['hujjatlar']), 1)
        self.assertEqual(len(self.royxat(q='Anvar').json()['hujjatlar']), 0)
        self.assertEqual(len(self.royxat(q='dalolatnoma').json()['hujjatlar']), 1)

    def test_mijozsiz_buyurtma_yuborib_bolmaydi_deb_belgilanadi(self):
        self.tayyor(f'b{self.loyiha.id}')
        Buyurtma.objects.filter(pk=self.loyiha.pk).update(mijoz=None)
        self.assertFalse(self.royxat().json()['hujjatlar'][0]['yuborish_mumkin'])

    def test_narx_va_summa_yoq(self):
        self.tayyor(f'b{self.loyiha.id}')
        matn = self.royxat().content.decode().lower()
        for soz in ('narx', 'summa', 'tushum', 'kirish_kodi'):
            self.assertNotIn(soz, matn)
