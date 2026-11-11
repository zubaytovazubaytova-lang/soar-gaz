"""TO'LIQ AYLANMA: ariza mijozdan boshlanib, hamma xodim rollari orqali o'tib, mijozga qaytadi.

Rollar:  mijoz · Nargiza (qo'ng'iroq vazifasi) · Ruxsora (Kadrlar + qo'ng'iroq vazifasi) · Ferangiz (hujjatlar) ·
         Aziz va Vali (oddiy xodimlar, mijoz oldiga boradi) · administrator.

Har bir qadamda ikki tomon tekshiriladi: xodim nima ko'radi va MIJOZ o'z kabinetida nima ko'radi.
Oxirida «rol × endpoint» ruxsat matritsasi: kim qaysi bo'limga kira oladi.
"""
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
from apps.buyurtmalar.models import Buyurtma
from apps.joylashuv.models import Nuqta, Smena
from apps.kabinet.models import Hujjat
from apps.kadrlar.models import KunlikHisobot
from apps.narxnoma.models import Narxnoma, NarxnomaQator
from apps.sms_app.models import SmsXabar
from apps.tushum.models import Tushum

MEDIA = tempfile.mkdtemp(prefix='soargaz-aylanma-media-')
BUXORO = (39.7747, 64.4286)


def klient(user=None):
    c = APIClient()
    if user:
        c.credentials(HTTP_AUTHORIZATION='Bearer ' + str(RefreshToken.for_user(user).access_token))
    return c


@override_settings(MEDIA_ROOT=MEDIA)
class Asos(TestCase):
    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(MEDIA, ignore_errors=True)

    def setUp(self):
        cache.clear()
        mk = Foydalanuvchi.objects.create
        self.mijoz = mk(telefon='+998901110001', ism='Karim Aka', rol='mijoz', viloyat='Buxoro viloyati',
                        tuman='Buxoro shahri', manzil='Turdi Farobiy 5', mulk_turi='uy')
        self.nargiza = mk(telefon='+998900001001', ism='Nargiza Abdulloyevna', rol='xodim', holat='faol',
                          lavozim='Call center operatori')
        self.ruxsora = mk(telefon='+998900001002', ism='Ruxsora Asqarovna', rol='xodim', holat='faol',
                          lavozim="Kadrlar bo'yicha mutaxassis")
        self.ferangiz = mk(telefon='+998900001003', ism='Ferangiz', rol='xodim', holat='faol',
                           lavozim="Mehnat muhofazasi va texnika xavfsizligi bo'yicha muhandis")
        self.aziz = mk(telefon='+998900001004', ism='Aziz Karimov', rol='xodim', holat='faol', lavozim='Montaj ustasi')
        self.vali = mk(telefon='+998900001005', ism='Vali Metrolog', rol='xodim', holat='faol', lavozim='Metrolog')
        self.admin = mk(telefon='+998900001006', ism='Egasi', rol='admin', is_staff=True, is_superuser=True)
        n, _ = Narxnoma.objects.get_or_create(tarmoq="aholi", bolim="ornatish", defaults={"sarlavha": "O'rnatish", "ustun1": "Narx"})
        self.qator = NarxnomaQator.objects.create(narxnoma=n, tartib=9999, nomi="Sinov: gaz plitasini o'rnatish", p_dan=100_000, p_gacha=100_000)

    def smenada(self, xodim, lat, lng):
        s = Smena.objects.filter(xodim=xodim, tugadi__isnull=True).first() or Smena.objects.create(xodim=xodim)
        Nuqta.objects.create(smena=s, xodim=xodim, lat=lat, lng=lng)
        return s

    def ariza_royxati(self, user, **q):
        r = klient(user).get('/api/buyurtmalar/operator/arizalar/', q)
        self.assertEqual(r.status_code, 200, r.content)
        return r.json()

    def mijoz_buyurtmasi(self, mijoz, bid):
        j = klient(mijoz).get('/api/kabinet/buyurtmalar/').json()
        return next(b for b in j if b['id'] == bid)


class AholiArizasiAylanmasi(Asos):
    """Mijoz o'z kabinetidan ariza beradi -> qo'ng'iroq vazifasi -> eng yaqin xodim -> bajarish -> to'lov -> sharh."""

    def test_toliq_aylanma(self):
        # 1) MIJOZ ariza beradi
        r = klient(self.mijoz).post('/api/buyurtmalar/', {'xizmat': 'montaj', 'tavsif': 'Gaz plitasi', 'vaqt_istagi': 'Bugun'})
        self.assertEqual(r.status_code, 201, r.content)
        bid = r.json()['id']
        b = self.mijoz_buyurtmasi(self.mijoz, bid)
        self.assertEqual((b['holat'], b['bosqich'], b['tarmoq']), ('yangi', 'yangi', 'aholi'))

        # 2) Ariza HAR IKKI qo'ng'iroq xodimiga bir xil ko'rinadi; Ferangiz va oddiy xodim ko'rmaydi
        for u in (self.nargiza, self.ruxsora):
            j = self.ariza_royxati(u)
            ariza = next(a for a in j['arizalar'] if a['id'] == bid)
            self.assertEqual((ariza['holat'], ariza['xodim_id'], ariza['mijoz_ism']), ('yangi', None, 'Karim Aka'))
            self.assertGreaterEqual(j['xulosa']['tayinlanmagan'], 1)
        self.assertEqual(klient(self.aziz).get('/api/buyurtmalar/').json(), [])             # hali hech kimga tegishli emas
        ferangiz = klient(self.ferangiz).get('/api/hujjatlar/ish/', {'bosqich': 'hammasi'}).json()
        self.assertNotIn(f'b{bid}', [i['kalit'] for i in ferangiz['ishlar']])                # montaj hujjat ishi emas

        # 3) NARGIZA joyni belgilaydi; eng yaqin xodim — Aziz (Vali uzoqroq). Ruxsora/Nargiza/Ferangiz nomzod emas
        self.smenada(self.aziz, BUXORO[0] + 0.02, BUXORO[1])
        self.smenada(self.vali, BUXORO[0] + 0.12, BUXORO[1])
        self.smenada(self.ruxsora, *BUXORO)           # ofis xodimi smena ochgan bo'lsa ham vazifa olmaydi
        r = klient(self.nargiza).post(f'/api/buyurtmalar/operator/arizalar/{bid}/joy/', {'lat': BUXORO[0], 'lng': BUXORO[1]}, format='json')
        self.assertEqual(r.status_code, 200)
        yaqin = klient(self.nargiza).get(f'/api/buyurtmalar/operator/arizalar/{bid}/yaqin/').json()
        self.assertEqual([n['ism'] for n in yaqin['nomzodlar']], ['Aziz Karimov', 'Vali Metrolog'])
        r = klient(self.nargiza).post(f'/api/buyurtmalar/operator/arizalar/{bid}/yaqin-yuborish/')
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(r.json()['xodim']['id'], self.aziz.id)

        # 4) Ikki tomon yangilandi: xodim vazifa oldi, MIJOZ xodim ismini ko'radi, ikkalasiga SMS ketdi
        self.assertEqual([x['id'] for x in klient(self.aziz).get('/api/buyurtmalar/').json()], [bid])
        b = self.mijoz_buyurtmasi(self.mijoz, bid)
        self.assertEqual(b['bosqich'], 'tayinlandi')
        self.assertEqual(b['xodim_malumot']['ism'], 'Aziz Karimov')
        self.assertTrue(SmsXabar.objects.filter(mijoz=self.aziz, matn__contains=f'#{bid}').exists())
        self.assertTrue(SmsXabar.objects.filter(mijoz=self.mijoz, matn__contains='xodim tayinlandi').exists())
        self.assertEqual(klient(self.vali).get('/api/buyurtmalar/').json(), [])             # boshqa xodim ko'rmaydi

        # 5) AZIZ qabul qiladi -> mijoz va nazoratchi ko'radi
        self.assertEqual(klient(self.aziz).post(f'/api/buyurtmalar/{bid}/qabul/').status_code, 200)
        self.assertEqual(self.mijoz_buyurtmasi(self.mijoz, bid)['holat'], 'qabul')
        for u in (self.nargiza, self.ruxsora):
            ariza = next(a for a in self.ariza_royxati(u, holat='faol')['arizalar'] if a['id'] == bid)
            self.assertEqual((ariza['holat'], ariza['xodim_ism'], ariza['kechikkan']), ('qabul', 'Aziz Karimov', False))
        # Qabul qilingan arizani boshqa xodimga o'tkazsa bo'ladi (hali boshlanmagan)
        self.assertEqual(klient(self.ruxsora).post(f'/api/buyurtmalar/operator/arizalar/{bid}/tayinlash/', {'xodim_id': self.vali.id}).status_code, 200)
        self.assertEqual(klient(self.aziz).get('/api/buyurtmalar/').json(), [])
        self.assertEqual(self.mijoz_buyurtmasi(self.mijoz, bid)['xodim_malumot']['ism'], 'Vali Metrolog')
        self.assertEqual(klient(self.nargiza).post(f'/api/buyurtmalar/operator/arizalar/{bid}/tayinlash/', {'xodim_id': self.aziz.id}).status_code, 200)

        # 6) AZIZ xizmat tanlaydi va summani tasdiqlaydi; MIJOZ narxni ko'rmaydi
        c = klient(self.aziz)
        self.assertEqual(c.post(f'/api/buyurtmalar/{bid}/qabul/').status_code, 200)
        r = c.post(f'/api/buyurtmalar/{bid}/xizmatlar/', {'xizmatlar': [{'qator': self.qator.id, 'ustun': 'p', 'soni': 1}]}, format='json')
        self.assertEqual(r.status_code, 201, r.content)
        self.assertEqual(c.post(f'/api/buyurtmalar/{bid}/summa/', {'summa': 100_000}, format='json').status_code, 200)
        b = self.mijoz_buyurtmasi(self.mijoz, bid)
        self.assertNotIn('tasdiq_summa', str(b))
        self.assertFalse(b.get('xizmatlar'))
        for yashirin in ('lat', 'lng'):
            self.assertNotIn(yashirin, b)

        # 7) AZIZ mijozdan pul oldi -> RUXSORA qabul qiladi -> buyurtma «to'langan»
        r = c.post('/api/tushum/', {'summa': 100_000, 'usul': 'naqd', 'buyurtma': bid}, format='json')
        self.assertEqual(r.status_code, 201, r.content)
        tid = r.json()['id']
        kutil = klient(self.ruxsora).get('/api/tushum/admin/', {'holat': 'kutilmoqda'}).json()
        self.assertIn(tid, [t['id'] for t in kutil['yozuvlar']])
        self.assertEqual(klient(self.nargiza).post(f'/api/tushum/{tid}/qabul/').status_code, 403)    # Nargiza pul qabul qila olmaydi
        self.assertEqual(klient(self.ruxsora).post(f'/api/tushum/{tid}/qabul/').status_code, 200)
        self.assertTrue(Buyurtma.objects.get(pk=bid).tolandi)
        self.assertTrue(self.mijoz_buyurtmasi(self.mijoz, bid)['tolandi'])
        self.assertEqual(Tushum.objects.get(pk=tid).hal_qilgan, self.ruxsora)

        # 8) AZIZ yakunlaydi -> MIJOZ natijani ko'radi va SMS oladi; nazoratda «bajarildi»
        r = c.post(f'/api/buyurtmalar/{bid}/natija/', {'natija': "Plita o'rnatildi", 'natija_soat': 2, 'holat': 'bajarildi'}, format='json')
        self.assertEqual(r.status_code, 200, r.content)
        b = self.mijoz_buyurtmasi(self.mijoz, bid)
        self.assertEqual((b['holat'], b['bosqich'], b['natija']), ('bajarildi', 'yakunlandi', "Plita o'rnatildi"))
        self.assertTrue(SmsXabar.objects.filter(mijoz=self.mijoz, matn__contains='bajarildi').exists())
        for u in (self.nargiza, self.ruxsora):
            ariza = next(a for a in self.ariza_royxati(u, holat='bajarildi')['arizalar'] if a['id'] == bid)
            self.assertEqual(ariza['natija'], "Plita o'rnatildi")
        # Yakunlangan ariza qayta biriktirilmaydi
        self.assertEqual(klient(self.nargiza).post(f'/api/buyurtmalar/operator/arizalar/{bid}/tayinlash/', {'xodim_id': self.vali.id}).status_code, 409)

        # 9) MIJOZ sharh qoldiradi (faqat yakunlangan buyurtmaga, bir marta)
        r = klient(self.mijoz).post('/api/kabinet/sharhlar/', {'buyurtma': bid, 'baho': 5, 'matn': 'Rahmat'}, format='json')
        self.assertEqual(r.status_code, 201, r.content)
        self.assertEqual(klient(self.mijoz).post('/api/kabinet/sharhlar/', {'buyurtma': bid, 'baho': 4}, format='json').status_code, 400)

    def test_mijoz_bekor_qiladi(self):
        r = klient(self.mijoz).post('/api/buyurtmalar/', {'xizmat': 'servis', 'tavsif': 'x', 'vaqt_istagi': 'Ertaga'})
        bid = r.json()['id']
        self.smenada(self.aziz, *BUXORO)
        klient(self.nargiza).post(f'/api/buyurtmalar/operator/arizalar/{bid}/joy/', {'lat': BUXORO[0], 'lng': BUXORO[1]}, format='json')
        self.assertEqual(klient(self.mijoz).post(f'/api/buyurtmalar/{bid}/', {'holat': 'bekor'}).status_code, 200)
        self.assertEqual(self.mijoz_buyurtmasi(self.mijoz, bid)['bosqich'], 'bekor')
        # Bekor qilingan arizaga xodim yuborib bo'lmaydi (qo'lda ham, eng yaqiniga ham)
        self.assertEqual(klient(self.nargiza).post(f'/api/buyurtmalar/operator/arizalar/{bid}/yaqin-yuborish/').status_code, 409)
        self.assertEqual(klient(self.ruxsora).post(f'/api/buyurtmalar/operator/arizalar/{bid}/tayinlash/', {'xodim_id': self.aziz.id}).status_code, 409)
        # va nazoratda «faol» ro'yxatdan chiqadi
        self.assertNotIn(bid, [a['id'] for a in self.ariza_royxati(self.nargiza, holat='faol')['arizalar']])

    def test_boshqa_mijoz_begona_arizani_kormaydi_va_ozgartirmaydi(self):
        bid = klient(self.mijoz).post('/api/buyurtmalar/', {'xizmat': 'montaj', 'tavsif': 'x', 'vaqt_istagi': 'Bugun'}).json()['id']
        boshqa = Foydalanuvchi.objects.create(telefon='+998901110002', ism='Boshqa', rol='mijoz')
        self.assertEqual(klient(boshqa).get('/api/kabinet/buyurtmalar/').json(), [])
        self.assertEqual(klient(boshqa).get(f'/api/kabinet/buyurtmalar/{bid}/').status_code, 404)
        self.assertEqual(klient(boshqa).post(f'/api/buyurtmalar/{bid}/', {'holat': 'bekor'}).status_code, 403)
        self.assertEqual(Buyurtma.objects.get(pk=bid).holat, 'yangi')


class UlgurjiArizaAylanmasi(Asos):
    """Tashkilot telefon qiladi: Nargiza ariza kiritadi -> mijoz hisobi o'zi ochiladi -> mijoz kirib ko'radi."""

    def test_telefon_orqali_ulgurji_ariza(self):
        r = klient(self.nargiza).post('/api/buyurtmalar/operator/arizalar/', {
            'mijoz_ism': '«Buxoro Gaz» MChJ', 'mijoz_telefon': '91 842-00-76', 'xizmat': 'servis', 'tarmoq': 'ulgurji',
            'tuman': 'Buxoro', 'manzil': 'Sanoat zonasi 4', 'tavsif': 'Qozonxona servisi'}, format='json')
        self.assertEqual(r.status_code, 201, r.content)
        bid = r.json()['id']
        # Hisob telefon bo'yicha ochildi; tashkilot SMS kod bilan kirib o'z arizasini ko'radi
        tashkilot = Foydalanuvchi.objects.get(telefon='+998918420076')
        self.assertEqual(tashkilot.rol, 'mijoz')
        b = self.mijoz_buyurtmasi(tashkilot, bid)
        self.assertEqual((b['holat'], b['tarmoq'], b['mijoz_ism']), ('yangi', 'ulgurji', '«Buxoro Gaz» MChJ'))
        self.assertTrue(SmsXabar.objects.filter(mijoz=tashkilot, matn__contains='Arizangiz qabul qilindi').exists())
        # Ruxsora ham, Nargiza ham ko'radi; oddiy xodim va boshqa mijoz ko'rmaydi
        for u in (self.nargiza, self.ruxsora):
            self.assertIn(bid, [a['id'] for a in self.ariza_royxati(u)['arizalar']])
        self.assertEqual(klient(self.aziz).get('/api/buyurtmalar/').json(), [])
        self.assertEqual(klient(self.mijoz).get('/api/kabinet/buyurtmalar/').json(), [])
        # Ruxsora (Nargiza emas) yo'naltiradi — ikkalasida ham huquq bir xil
        self.assertEqual(klient(self.ruxsora).post(f'/api/buyurtmalar/operator/arizalar/{bid}/tayinlash/', {'xodim_id': self.vali.id}).status_code, 200)
        self.assertEqual(klient(self.vali).get('/api/buyurtmalar/').json()[0]['id'], bid)
        self.assertEqual(self.mijoz_buyurtmasi(tashkilot, bid)['xodim_malumot']['ism'], 'Vali Metrolog')
        # Ulgurji narx tarmog'idagi buyurtmaga aholi narxi qo'yib bo'lmaydi
        r = klient(self.vali).post(f'/api/buyurtmalar/{bid}/xizmatlar/', {'xizmatlar': [{'qator': self.qator.id, 'ustun': 'p', 'soni': 1}]}, format='json')
        self.assertEqual(r.status_code, 400)

    def test_qongiroq_jurnali_va_qayta_qongiroq(self):
        for u in (self.nargiza, self.ruxsora):
            r = klient(u).post('/api/buyurtmalar/operator/qongiroqlar/', {
                'shaxs': 'yuridik', 'nomi': f'Tashkilot {u.ism[:3]}', 'telefon': '90 123-45-6' + str(u.pk % 10), 'natija': 'keyinroq',
                'qayta_sana': timezone.localdate().isoformat()}, format='json')
            self.assertEqual(r.status_code, 201, r.content)
        j = klient(self.nargiza).get('/api/buyurtmalar/operator/qongiroqlar/').json()
        self.assertEqual(len(j['qongiroqlar']), 2)                                           # jurnal umumiy
        self.assertEqual(len(j['qayta_qilinadigan']), 2)
        self.assertEqual({q['operator_ism'] for q in j['qongiroqlar']}, {'Nargiza Abdulloyevna', 'Ruxsora Asqarovna'})


class HujjatAylanmasi(Asos):
    """Mijozdan kelgan metrologiya/loyiha ishlari: Ferangiz hujjat tayyorlaydi va mijozga yuboradi."""

    def fayl(self, nom='hujjat.pdf'):
        return SimpleUploadedFile(nom, b'%PDF-1.4 sinov', content_type='application/pdf')

    def test_saytdan_kelgan_metrologiya_arizasi(self):
        # Mehmon saytning Metrologiya bo'limidan ariza qoldiradi (kirmasdan)
        r = APIClient().post('/api/tolovlar/metrologiya-ariza/', {
            'ism': 'Dilfuza', 'telefon': '91 222-33-44', 'xizmat': 'kalibrovka', 'hisoblagich': 'G4', 'seriya_raqam': 'A1',
            'manzil': 'Kogon'}, format='json')
        self.assertEqual(r.status_code, 201, r.content)
        kalit = f"a{r.json()['id']}"
        ish = next(i for i in klient(self.ferangiz).get('/api/hujjatlar/ish/').json()['ishlar'] if i['kalit'] == kalit)
        self.assertEqual((ish['holat'], ish['mijoz_telefon']), ('yangi', '+998912223344'))
        c = klient(self.ferangiz)
        # Qabul qilinmaguncha hujjat tayyorlab bo'lmaydi
        self.assertEqual(c.post(f'/api/hujjatlar/ish/{kalit}/hujjat/', {'fayl': self.fayl()}, format='multipart').status_code, 409)
        self.assertEqual(c.post(f'/api/hujjatlar/ish/{kalit}/holat/', {'holat': 'korildi'}).status_code, 200)
        r = c.post(f'/api/hujjatlar/ish/{kalit}/hujjat/', {'fayl': self.fayl(), 'nom': 'Dalolatnoma', 'turi': 'sertifikat'}, format='multipart')
        self.assertEqual(r.status_code, 201, r.content)
        hid = r.json()['hujjat']['id']
        self.assertEqual(c.post(f'/api/hujjatlar/ish/hujjat/{hid}/yuborish/').status_code, 200)
        # Mijoz hisobi telefon bo'yicha ochildi va hujjat unga tushdi
        mijoz = Foydalanuvchi.objects.get(telefon='+998912223344')
        j = klient(mijoz).get('/api/kabinet/hujjatlar/').json()
        self.assertEqual([h['nom'] for h in j], ['Dalolatnoma'])
        self.assertTrue(klient(mijoz).get('/api/kabinet/bildirishnomalar/').json()['royxat'])
        self.assertEqual(klient(self.mijoz).get('/api/kabinet/hujjatlar/').json(), [])      # boshqa mijoz ko'rmaydi

    def test_mijozning_loyiha_buyurtmasi_xodim_orqali_hujjatgacha(self):
        bid = klient(self.mijoz).post('/api/buyurtmalar/', {'xizmat': 'loyiha', 'tavsif': 'Gaz loyihasi', 'vaqt_istagi': 'Operator bog\'lansin'}).json()['id']
        kalit = f'b{bid}'
        c = klient(self.ferangiz)
        ish = next(i for i in c.get('/api/hujjatlar/ish/').json()['ishlar'] if i['kalit'] == kalit)
        self.assertEqual((ish['holat'], ish['tayyorlash_mumkin']), ('yangi', False))
        # Nargiza loyihachi xodimga yo'naltiradi, u qabul qiladi -> endi Ferangiz hujjat tayyorlay oladi
        self.assertEqual(klient(self.nargiza).post(f'/api/buyurtmalar/operator/arizalar/{bid}/tayinlash/', {'xodim_id': self.aziz.id}).status_code, 200)
        self.assertEqual(c.post(f'/api/hujjatlar/ish/{kalit}/hujjat/', {'fayl': self.fayl()}, format='multipart').status_code, 409)
        self.assertEqual(klient(self.aziz).post(f'/api/buyurtmalar/{bid}/qabul/').status_code, 200)
        r = c.post(f'/api/hujjatlar/ish/{kalit}/hujjat/', {'fayl': self.fayl(), 'nom': 'Loyiha'}, format='multipart')
        self.assertEqual(r.status_code, 201, r.content)
        self.assertEqual(c.post(f"/api/hujjatlar/ish/hujjat/{r.json()['hujjat']['id']}/yuborish/").status_code, 200)
        self.assertEqual([h['nom'] for h in klient(self.mijoz).get('/api/kabinet/hujjatlar/').json()], ['Loyiha'])
        # Ferangiz buyurtma holatini o'zgartira olmaydi — buni tayinlangan xodim qiladi
        self.assertEqual(c.post(f'/api/hujjatlar/ish/{kalit}/holat/', {'holat': 'bekor'}).status_code, 400)
        self.assertEqual(Buyurtma.objects.get(pk=bid).holat, 'qabul')


class KadrlarBilanBoglanish(Asos):
    """Xodimning ishi Ruxsoraning nazoratida: davomat, hisobot, eslatma, qo'lda belgi."""

    def test_xodim_harakati_kadrlarda_korinadi(self):
        r = klient(self.ruxsora).get('/api/kadrlar/kun/').json()
        qator = {x['id']: x for x in r['xodimlar']}
        self.assertEqual(qator[self.aziz.id]['holat'], 'kelmadi')
        # Aziz smena ochdi (GPS rozilik bilan) -> «ishda»; Nargiza ham kuzatuvda, Ruxsora o'zi emas
        self.smenada(self.aziz, *BUXORO)
        r = klient(self.ruxsora).get('/api/kadrlar/kun/').json()
        qator = {x['id']: x for x in r['xodimlar']}
        self.assertEqual(qator[self.aziz.id]['holat'], 'ishda')
        self.assertIn(self.nargiza.id, qator)
        self.assertNotIn(self.ruxsora.id, qator)
        # Aziz kunlik hisobot yozdi -> Ruxsora ko'radi; hisobotsiz xodimlarga eslatma ketadi
        self.assertEqual(klient(self.aziz).post('/api/kadrlar/hisobot/', {'joy': 'Kogon', 'ish': 'Plita'}).status_code, 200)
        r = klient(self.ruxsora).get('/api/kadrlar/kun/').json()
        self.assertEqual(next(x for x in r['xodimlar'] if x['id'] == self.aziz.id)['hisobot']['joy'], 'Kogon')
        e = klient(self.ruxsora).post('/api/kadrlar/eslatma/')
        self.assertEqual(e.status_code, 201)
        from apps.aloqa.models import Xabar
        self.assertFalse(Xabar.objects.filter(xodim=self.aziz).exists())            # Aziz hisobot bergan
        self.assertTrue(Xabar.objects.filter(xodim=self.vali).exists())             # Vali bermagan
        self.assertTrue(Xabar.objects.filter(xodim=self.nargiza).exists())
        # Qo'lda belgi: ofis xodimi (smenasiz) «keldi»
        self.assertEqual(klient(self.ruxsora).post('/api/kadrlar/davomat/', {'xodim_id': self.nargiza.id, 'holat': 'keldi'}, format='json').status_code, 200)
        r = klient(self.ruxsora).get('/api/kadrlar/kun/').json()
        self.assertEqual(next(x for x in r['xodimlar'] if x['id'] == self.nargiza.id)['holat'], 'keldi')
        # Nargiza davomat belgilay olmaydi
        self.assertEqual(klient(self.nargiza).post('/api/kadrlar/davomat/', {'xodim_id': self.aziz.id, 'holat': 'keldi'}, format='json').status_code, 403)


class RuxsatMatritsasi(Asos):
    """Rol × endpoint: har bir rol faqat o'ziga tegishli bo'limga kira oladi."""

    ROLLAR = ['mijoz', 'oddiy', 'nargiza', 'ruxsora', 'ferangiz', 'admin', 'mehmon']

    # endpoint -> {rol: kutilgan status}. Ko'rsatilmagan rollar uchun `boshqa` ishlatiladi.
    MATRITSA = [
        ('/api/auth/xodimlar/',                          {'mijoz': 403, 'admin': 200, 'mehmon': 401}, 200),
        ('/api/auth/mijozlar/',                          {'admin': 200, 'mehmon': 401}, 403),
        ('/api/auth/jurnal/',                            {'admin': 200, 'mehmon': 401}, 403),
        ('/api/auth/rahbariyat/',                        {'admin': 200, 'mehmon': 401}, 403),
        ('/api/buyurtmalar/statistika/',                 {'admin': 200, 'mehmon': 401}, 403),
        ('/api/buyurtmalar/operator/arizalar/',          {'nargiza': 200, 'ruxsora': 200, 'mehmon': 401}, 403),
        ('/api/buyurtmalar/operator/qongiroqlar/',       {'nargiza': 200, 'ruxsora': 200, 'mehmon': 401}, 403),
        ('/api/buyurtmalar/operator/geokod/?manzil=abc', {'nargiza': 'xizmat', 'ruxsora': 'xizmat', 'mehmon': 401}, 403),
        ('/api/kadrlar/kun/',                            {'ruxsora': 200, 'admin': 200, 'mehmon': 401}, 403),
        ('/api/kadrlar/hujjatlar/',                      {'ruxsora': 200, 'admin': 200, 'mehmon': 401}, 403),
        ('/api/kadrlar/hisobot/',                        {'mijoz': 403, 'admin': 403, 'mehmon': 401}, 200),
        ('/api/tushum/admin/',                           {'ruxsora': 200, 'admin': 200, 'mehmon': 401}, 403),
        ('/api/tushum/',                                 {'mijoz': 403, 'admin': 403, 'mehmon': 401}, 200),
        ('/api/hujjatlar/ish/',                          {'ferangiz': 200, 'mehmon': 401}, 403),
        ('/api/joylashuv/smena/',                        {'mijoz': 403, 'admin': 403, 'mehmon': 401}, 200),
        ('/api/joylashuv/royxat/',                       {'admin': 200, 'mehmon': 401}, 403),
        ('/api/auth/xodim/profil/',                      {'mijoz': 403, 'admin': 403, 'mehmon': 401}, 200),
        ('/api/kabinet/obzor/',                          {'mehmon': 401}, 200),
        ('/api/narxnoma/',                               {'mijoz': 403, 'mehmon': 401}, 200),     # narxnomani xodim va admin ko'radi
    ]

    def foydalanuvchi(self, rol):
        return {'mijoz': self.mijoz, 'oddiy': self.aziz, 'nargiza': self.nargiza, 'ruxsora': self.ruxsora,
                'ferangiz': self.ferangiz, 'admin': self.admin, 'mehmon': None}[rol]

    def test_matritsa(self):
        from unittest import mock
        from apps.buyurtmalar import operator as op
        xatolar = []
        with mock.patch.object(op, '_nominatim', return_value=[]):
            for yol, istisno, boshqa in self.MATRITSA:
                for rol in self.ROLLAR:
                    kutilgan = istisno.get(rol, boshqa)
                    r = klient(self.foydalanuvchi(rol)).get(yol)
                    if kutilgan == 'xizmat':                     # geokod: ruxsat bor — natija 200 yoki (cheklov) 429/502 emas
                        ok = r.status_code == 200
                    elif yol == '/api/kabinet/obzor/' and rol != 'mehmon':
                        continue                                  # mijoz kabineti: xodimlar uchun mazmuni muhim emas
                    else:
                        ok = r.status_code == kutilgan
                    if not ok:
                        xatolar.append(f'{rol:9} GET {yol}: kutilgan {kutilgan}, keldi {r.status_code}')
        self.assertEqual(xatolar, [], '\n' + '\n'.join(xatolar))
