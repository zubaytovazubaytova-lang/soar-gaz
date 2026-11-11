"""Operatorlar: qo'ng'iroq arizasini qabul qilish, xodimga biriktirish, nazorat va chiquvchi qo'ng'iroqlar."""
from datetime import timedelta

from django.core.cache import cache
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from apps.auth_app.models import AuditYozuv, Foydalanuvchi
from apps.buyurtmalar.models import Buyurtma, Qongiroq
from apps.sms_app.models import SmsXabar

ARIZALAR = '/api/buyurtmalar/operator/arizalar/'
QONGIROQLAR = '/api/buyurtmalar/operator/qongiroqlar/'


def klient(user=None):
    c = APIClient()
    if user:
        c.credentials(HTTP_AUTHORIZATION='Bearer ' + str(RefreshToken.for_user(user).access_token))
    return c


class Asos(TestCase):
    def setUp(self):
        cache.clear()
        mk = Foydalanuvchi.objects.create
        # «Servis operatori» lavozimi endi alohida kabinet emas: oddiy xodim (maxsus huquqsiz)
        self.servis = mk(telefon='+998900000501', ism='Servis Op', rol='xodim', holat='faol', lavozim='Servis operatori')
        self.call = mk(telefon='+998900000502', ism='Nargiza', rol='xodim', holat='faol', lavozim='Call center operatori')
        self.usta = mk(telefon='+998900000503', ism='Aziz', rol='xodim', holat='faol', lavozim='Montaj ustasi')
        self.usta2 = mk(telefon='+998900000504', ism='Vali', rol='xodim', holat='faol', lavozim='Metrolog')
        self.kadr = mk(telefon='+998900000505', ism='Ruxsora', rol='xodim', holat='faol',
                       lavozim="Kadrlar bo'yicha mutaxassis")
        self.nofaol = mk(telefon='+998900000506', ism='Eski', rol='xodim', holat='nofaol', lavozim='Montaj ustasi')
        self.mijoz = mk(telefon='+998901110000', ism='Karim', rol='mijoz')
        self.admin = mk(telefon='+998900000507', ism='Ega', rol='admin', is_staff=True, is_superuser=True)
        self.aholi = Buyurtma.objects.create(mijoz=self.mijoz, xizmat='montaj', tarmoq='aholi', manzil='Kogon')
        self.ulgurji = Buyurtma.objects.create(mijoz=self.mijoz, xizmat='servis', tarmoq='ulgurji', manzil='Zavod')

    def ariza(self, **ustiga):
        d = {'mijoz_ism': 'Anvar', 'mijoz_telefon': '90 777-66-55', 'xizmat': 'montaj',
             'tuman': 'Kogon', 'manzil': 'Navoiy 5'}
        d.update(ustiga)
        return d


class RuxsatTestlari(Asos):
    def test_faqat_qongiroq_vazifasi_borlar(self):
        """Arizalar bilan faqat Ruxsora (Kadrlar) va Nargiza ishlaydi; oddiy xodim (Servis operatori lavozimi ham), mijoz, admin — yo'q."""
        for u in (self.usta, self.servis, self.mijoz, self.admin):
            c = klient(u)
            self.assertEqual(c.get(ARIZALAR).status_code, 403, u.lavozim or u.rol)
            self.assertEqual(c.post(ARIZALAR, self.ariza()).status_code, 403)
            self.assertEqual(c.post(f'{ARIZALAR}{self.aholi.id}/tayinlash/', {'xodim_id': self.usta.id}).status_code, 403)
            self.assertEqual(c.get(QONGIROQLAR).status_code, 403)
        self.assertEqual(klient().get(ARIZALAR).status_code, 401)
        for u in (self.kadr, self.call):
            self.assertEqual(klient(u).get(ARIZALAR).status_code, 200)
            self.assertEqual(klient(u).get(QONGIROQLAR).status_code, 200)

    def test_ruxsora_va_nargiza_bir_xil_vazifani_bajaradi(self):
        """Ikkalasi ham: aholi va ulgurji arizalarni ko'radi, ikkala turini kiritadi, ikkalasini ham biriktiradi."""
        for u, tel in ((self.kadr, '90 111-22-33'), (self.call, '90 444-55-66')):
            c = klient(u)
            j = c.get(ARIZALAR).json()
            self.assertEqual({a['id'] for a in j['arizalar']} >= {self.aholi.id, self.ulgurji.id}, True)
            self.assertEqual(j['tur'], 'qongiroq')
            r = c.post(ARIZALAR, self.ariza(tarmoq='ulgurji', mijoz_telefon=tel))
            self.assertEqual((r.status_code, r.json()['tarmoq']), (201, 'ulgurji'))
            for ariza in (self.aholi, self.ulgurji):
                Buyurtma.objects.filter(pk=ariza.pk).update(xodim=None, holat='yangi')
                self.assertEqual(c.post(f'{ARIZALAR}{ariza.id}/tayinlash/', {'xodim_id': self.usta.id}).status_code, 200)

    def test_nofaol_kadr_arizalarga_kira_olmaydi(self):
        self.kadr.holat = 'nofaol'
        self.kadr.save()
        self.assertEqual(klient(self.kadr).get(ARIZALAR).status_code, 403)

    def test_nofaol_operator_kira_olmaydi(self):
        self.call.holat = 'nofaol'
        self.call.save()
        self.assertEqual(klient(self.call).get(ARIZALAR).status_code, 403)

    def test_qongiroq_jurnali_ikkalasida(self):
        """Chiquvchi qo'ng'iroqlar jurnali: Nargiza ham, Ruxsora ham; boshqalarga yo'q."""
        self.assertEqual(klient(self.servis).get(QONGIROQLAR).status_code, 403)
        for u in (self.call, self.kadr):
            self.assertEqual(klient(u).get(QONGIROQLAR).status_code, 200)


class RoyxatTestlari(Asos):
    def ids(self, user, **q):
        return {a['id'] for a in klient(user).get(ARIZALAR, q).json()['arizalar']}

    def test_ikkalasi_bir_xil_royxatni_koradi(self):
        self.assertEqual(self.ids(self.kadr), self.ids(self.call))
        self.assertEqual(self.ids(self.kadr), {self.aholi.id, self.ulgurji.id})

    def test_call_center_hammasini_koradi(self):
        self.assertEqual(self.ids(self.call), {self.aholi.id, self.ulgurji.id})

    def test_narx_va_summa_yoq(self):
        a = klient(self.call).get(ARIZALAR).json()['arizalar'][0]
        for yashirin in ('tasdiq_summa', 'xizmatlar', 'shartnoma', 'tolandi'):
            self.assertNotIn(yashirin, a)

    def test_xodimlar_royxati_faqat_vazifa_oladiganlar(self):
        ids = {x['id'] for x in klient(self.call).get(ARIZALAR).json()['xodimlar']}
        # Faqat mijoz oldiga boradigan oddiy xodimlar; arizalarni qabul qiluvchilar (Ruxsora, Nargiza) va nofaol xodim yo'q
        self.assertEqual(ids, {self.usta.id, self.usta2.id, self.servis.id})
        self.assertNotIn(self.kadr.id, ids)
        self.assertNotIn(self.call.id, ids)

    def test_filtr_va_qidiruv(self):
        self.aholi.xodim = self.usta
        self.aholi.save()
        self.assertEqual(self.ids(self.call, holat='tayinlanmagan'), {self.ulgurji.id})
        self.assertEqual(self.ids(self.call, q='Zavod'), {self.ulgurji.id})
        self.assertEqual(self.ids(self.call, q=f'#{self.aholi.id}'), {self.aholi.id})
        j = klient(self.call).get(ARIZALAR).json()
        self.assertEqual((j['xulosa']['tayinlanmagan'], j['xulosa']['faol']), (1, 2))


class NazoratTestlari(Asos):
    """Call center bajarilishini nazorat qiladi: xodimga berilgan, lekin 24 soatdan beri turib qolganlar."""

    def _eskirt(self, b, soat):
        Buyurtma.objects.filter(pk=b.pk).update(yangilangan=timezone.now() - timedelta(hours=soat))

    def test_kechikkan(self):
        self.aholi.xodim = self.usta
        self.aholi.save()
        self._eskirt(self.aholi, 30)
        j = klient(self.call).get(ARIZALAR, {'holat': 'kechikkan'}).json()
        self.assertEqual([a['id'] for a in j['arizalar']], [self.aholi.id])
        self.assertTrue(j['arizalar'][0]['kechikkan'])
        self.assertEqual(j['xulosa']['kechikkan'], 1)

    def test_yangi_tayinlangan_kechikmagan(self):
        self.aholi.xodim = self.usta
        self.aholi.save()
        j = klient(self.call).get(ARIZALAR).json()
        self.assertEqual(j['xulosa']['kechikkan'], 0)

    def test_tayinlanmagan_va_bajarilmoqda_kechikkan_emas(self):
        self._eskirt(self.ulgurji, 100)                         # xodimi yo'q - "tayinlanmagan", kechikkan emas
        self.aholi.xodim = self.usta
        self.aholi.holat = 'bajarilmoqda'
        self.aholi.save()
        self._eskirt(self.aholi, 100)
        self.assertEqual(klient(self.call).get(ARIZALAR).json()['xulosa']['kechikkan'], 0)

    def test_natija_korinadi(self):
        self.aholi.holat = 'bajarildi'
        self.aholi.natija = 'Hisoblagich o\'rnatildi'
        self.aholi.save()
        a = klient(self.call).get(ARIZALAR, {'holat': 'bajarildi'}).json()['arizalar'][0]
        self.assertEqual(a['natija'], 'Hisoblagich o\'rnatildi')


class QongiroqArizasiTestlari(Asos):
    def test_yangi_mijoz_va_ariza(self):
        r = klient(self.kadr).post(ARIZALAR, self.ariza())
        self.assertEqual(r.status_code, 201, r.content)
        b = Buyurtma.objects.get(pk=r.json()['id'])
        self.assertEqual((b.tarmoq, b.holat, b.xodim), ('aholi', 'yangi', None))
        self.assertEqual(b.mijoz.telefon, '+998907776655')
        self.assertEqual(b.mijoz.rol, 'mijoz')
        self.assertTrue(SmsXabar.objects.filter(mijoz=b.mijoz).exists())
        self.assertTrue(AuditYozuv.objects.filter(amal='ariza_qongiroq', kim=self.kadr).exists())

    def test_mavjud_mijozga_tegilmaydi(self):
        r = klient(self.kadr).post(ARIZALAR, self.ariza(mijoz_telefon=self.mijoz.telefon, mijoz_ism='Boshqa ism'))
        self.assertEqual(r.status_code, 201)
        self.mijoz.refresh_from_db()
        self.assertEqual(self.mijoz.ism, 'Karim')
        self.assertEqual(Foydalanuvchi.objects.filter(telefon=self.mijoz.telefon).count(), 1)

    def test_ruxsora_ham_ulgurji_kiritadi(self):
        r = klient(self.kadr).post(ARIZALAR, self.ariza(tarmoq='ulgurji'))
        self.assertEqual((r.status_code, r.json()['tarmoq']), (201, 'ulgurji'))

    def test_call_center_ulgurji_kiritadi(self):
        r = klient(self.call).post(ARIZALAR, self.ariza(tarmoq='ulgurji', mijoz_ism='«Zavod» MChJ'))
        self.assertEqual((r.status_code, r.json()['tarmoq']), (201, 'ulgurji'))

    def test_darrov_xodimga_biriktirish(self):
        r = klient(self.call).post(ARIZALAR, self.ariza(xodim_id=self.usta.id))
        self.assertEqual(r.status_code, 201)
        self.assertEqual(r.json()['xodim_id'], self.usta.id)
        self.assertTrue(SmsXabar.objects.filter(mijoz=self.usta).exists())

    def test_xodim_yoki_admin_telefoni_mijoz_bolmaydi(self):
        r = klient(self.call).post(ARIZALAR, self.ariza(mijoz_telefon=self.usta.telefon))
        self.assertEqual(r.status_code, 409)
        self.assertEqual(Buyurtma.objects.count(), 2)

    def test_notogri_malumot(self):
        c = klient(self.call)
        for ustiga in ({'mijoz_ism': ' '}, {'manzil': ''}, {'xizmat': 'xato'}, {'mijoz_telefon': '123'},
                       {'tarmoq': 'xato'}, {'xodim_id': self.kadr.id}, {'xodim_id': self.nofaol.id},
                       {'xodim_id': 99999}):
            self.assertIn(c.post(ARIZALAR, self.ariza(**ustiga)).status_code, (400, 404), ustiga)
        self.assertEqual(Buyurtma.objects.count(), 2)                 # hech narsa yaratilmadi
        self.assertFalse(Foydalanuvchi.objects.filter(telefon='+998907776655').exists())


class TayinlashTestlari(Asos):
    def url(self, b):
        return f'{ARIZALAR}{b.id}/tayinlash/'

    def test_tayinlash(self):
        r = klient(self.kadr).post(self.url(self.aholi), {'xodim_id': self.usta.id})
        self.assertEqual(r.status_code, 200)
        self.aholi.refresh_from_db()
        self.assertEqual((self.aholi.xodim, self.aholi.holat), (self.usta, 'yangi'))
        self.assertTrue(AuditYozuv.objects.filter(amal='buyurtma_tayinlandi', kim=self.kadr).exists())

    def test_ruxsora_ulgurjini_ham_tayinlaydi(self):
        self.assertEqual(klient(self.kadr).post(self.url(self.ulgurji), {'xodim_id': self.usta.id}).status_code, 200)
        self.ulgurji.refresh_from_db()
        self.assertEqual(self.ulgurji.xodim, self.usta)

    def test_call_center_hammaga_tayinlaydi(self):
        for b, x in ((self.aholi, self.usta), (self.ulgurji, self.usta2)):
            self.assertEqual(klient(self.call).post(self.url(b), {'xodim_id': x.id}).status_code, 200)

    def test_kadr_va_nofaol_xodimga_bolmaydi(self):
        c = klient(self.call)
        for x in (self.kadr, self.call, self.nofaol):          # arizalarni qabul qiluvchilarga va nofaolga vazifa berilmaydi
            self.assertIn(c.post(self.url(self.aholi), {'xodim_id': x.id}).status_code, (400, 404))
        self.assertEqual(c.post(self.url(self.aholi), {}).status_code, 404)
        self.aholi.refresh_from_db()
        self.assertIsNone(self.aholi.xodim)

    def test_bajarilayotganni_almashtirib_bolmaydi(self):
        self.aholi.xodim = self.usta
        self.aholi.holat = 'bajarilmoqda'
        self.aholi.save()
        r = klient(self.call).post(self.url(self.aholi), {'xodim_id': self.usta2.id})
        self.assertEqual(r.status_code, 409)
        self.aholi.refresh_from_db()
        self.assertEqual(self.aholi.xodim, self.usta)

    def test_qabul_qilinganni_almashtirsa_buladi(self):
        self.aholi.xodim = self.usta
        self.aholi.holat = 'qabul'
        self.aholi.save()
        self.assertEqual(klient(self.call).post(self.url(self.aholi), {'xodim_id': self.usta2.id}).status_code, 200)

    def test_administrator_tayinlashi_ishlaydi(self):
        r = klient(self.admin).post(f'/api/buyurtmalar/{self.aholi.id}/tayinlash/', {'xodim_id': self.usta.id})
        self.assertEqual(r.status_code, 200)
        self.assertTrue(AuditYozuv.objects.filter(amal='buyurtma_tayinlandi', kim=self.admin).exists())


class ChiquvchiQongiroqTestlari(Asos):
    def royxat(self):
        return klient(self.call).get(QONGIROQLAR).json()

    def yoz(self, **ustiga):
        d = {'shaxs': 'yuridik', 'nomi': '«Buxoro gaz» MChJ', 'telefon': '91 842-00-76', 'natija': 'qiziqdi',
             'izoh': 'Ulgurji narx so\'radi'}
        d.update(ustiga)
        return klient(self.call).post(QONGIROQLAR, d)

    def test_yozish_va_royxat(self):
        r = self.yoz()
        self.assertEqual(r.status_code, 201, r.content)
        j = self.royxat()
        self.assertEqual(j['bugun_soni'], 1)
        q = j['qongiroqlar'][0]
        self.assertEqual((q['telefon'], q['shaxs'], q['natija'], q['operator_ism']),
                         ('+998918420076', 'yuridik', 'qiziqdi', 'Nargiza'))

    def test_jismoniy_shaxs(self):
        self.assertEqual(self.yoz(shaxs='jismoniy', nomi='Karim aka', natija='ariza').status_code, 201)

    def test_notogri_malumot(self):
        for ustiga in ({'shaxs': 'x'}, {'natija': 'x'}, {'nomi': ' '}, {'telefon': 'abc'},
                       {'natija': 'keyinroq'},                                     # sanasiz
                       {'natija': 'keyinroq', 'qayta_sana': '2000-01-01'},         # o'tib ketgan sana
                       {'natija': 'keyinroq', 'qayta_sana': 'ertaga'}):
            self.assertEqual(self.yoz(**ustiga).status_code, 400, ustiga)
        self.assertEqual(Qongiroq.objects.count(), 0)

    def test_qayta_qongiroq_royxati(self):
        bugun = timezone.localdate().isoformat()
        self.assertEqual(self.yoz(natija='keyinroq', qayta_sana=bugun).status_code, 201)
        self.assertEqual(len(self.royxat()['qayta_qilinadigan']), 1)
        # Shu raqamga keyin yangi qayd yozilsa - "qayta qo'ng'iroq" ro'yxatidan tushadi
        self.assertEqual(self.yoz(natija='ariza').status_code, 201)
        self.assertEqual(self.royxat()['qayta_qilinadigan'], [])

    def test_kelajakdagi_qayta_qongiroq_hali_royxatda_yoq(self):
        ertaga = (timezone.localdate() + timedelta(days=1)).isoformat()
        self.assertEqual(self.yoz(natija='keyinroq', qayta_sana=ertaga).status_code, 201)
        self.assertEqual(self.royxat()['qayta_qilinadigan'], [])
