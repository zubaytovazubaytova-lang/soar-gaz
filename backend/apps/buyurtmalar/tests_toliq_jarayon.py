"""To'liq ish kuni (oxirigacha): mijoz arizasi → Ruxsora biriktiradi → usta bosqichlari → narx →
«ishni tugatdim» → pul → kvitansiya → kunlik hisobot → Ruxsora pulni qabul qiladi → buyurtma yakunlanadi.

Har qadamda Ruxsoraga (Kadrlar) nima yetib borgani tekshiriladi: kabinet qo'ng'iroqchasi (aloqa.Xabar),
Telegram, «Arizalar» ro'yxatidagi holat va «Davomat / Kunlik hisobotlar».
"""
from unittest import mock

from django.core.cache import cache
from django.test import TestCase, override_settings
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from apps.aloqa.models import Xabar
from apps.auth_app.models import Foydalanuvchi
from apps.narxnoma.models import NarxnomaQator
from apps.sms_app.models import TelegramUlanish
from .models import Buyurtma


def klient(user):
    c = APIClient()
    c.credentials(HTTP_AUTHORIZATION='Bearer ' + str(RefreshToken.for_user(user).access_token))
    return c


@override_settings(TELEGRAM_BOT_TOKEN='123:sinov', TELEGRAM_BOT_USERNAME='soargaz_bot')
class ToliqIshKuniTesti(TestCase):
    def setUp(self):
        cache.clear()
        mk = Foydalanuvchi.objects.create
        self.ruxsora = mk(telefon='+998900002001', ism='Ruxsora', rol='xodim', holat='faol',
                          lavozim="Kadrlar bo'yicha mutaxassis")
        self.usta = mk(telefon='+998900002002', ism='Aziz', rol='xodim', holat='faol', lavozim='Chilangar',
                       tuman='Kogon')
        self.mijoz = mk(telefon='+998900002003', ism='Karim', rol='mijoz', tuman='Kogon', manzil='Navoiy 5')
        TelegramUlanish.objects.create(telefon=self.ruxsora.telefon, chat_id=7001)
        TelegramUlanish.objects.create(telefon=self.usta.telefon, chat_id=7002)
        TelegramUlanish.objects.create(telefon=self.mijoz.telefon, chat_id=7003)
        self.r, self.u, self.m = klient(self.ruxsora), klient(self.usta), klient(self.mijoz)
        self.tg = []
        p = mock.patch('apps.sms_app.telegram._api', side_effect=self._api)
        p.start()
        self.addCleanup(p.stop)
        # Saytda xabarlar tranzaksiya yakunlangach yuboriladi (on_commit) — testda darhol bajariladi
        p2 = mock.patch('django.db.transaction.on_commit', side_effect=lambda f, *a, **k: f())
        p2.start()
        self.addCleanup(p2.stop)

    def _api(self, metod, malumot=None, *a, **k):
        if metod == 'sendMessage':
            self.tg.append((malumot or {}).get('chat_id'))
        return {'ok': True, 'result': {}}

    def ruxsoraga(self):
        """Oxirgi qadamdan beri Ruxsoraga kelganlar: (kabinet xabarlari soni, Telegram xabarlari soni)."""
        kab = Xabar.objects.filter(xodim=self.ruxsora).count() - self._kab
        tg = self.tg.count(7001) - self._tg
        self._kab, self._tg = Xabar.objects.filter(xodim=self.ruxsora).count(), self.tg.count(7001)
        return kab, tg

    def test_toliq_ish_kuni(self):
        self._kab = self._tg = 0
        q = NarxnomaQator.objects.filter(narxnoma__tarmoq='aholi', narxnoma__bolim='profilaktika',
                                         faol=True, p_dan__isnull=False).order_by('tartib').first()

        # 1. Mijoz ariza beradi (narxnomadan xizmat, naqd)
        r = self.m.post('/api/buyurtmalar/', {'xizmat': 'servis', 'tolov_usuli': 'naqd',
                                              'xizmatlar': [{'qator': q.pk, 'ustun': 'p', 'soni': 1}]}, format='json')
        self.assertEqual(r.status_code, 201, r.content)
        bid = r.json()['id']
        self.assertGreaterEqual(sum(self.ruxsoraga()), 1, "1: Ruxsoraga yangi ariza xabari bormadi")

        # 2. Ruxsora «Arizalar»da ko'radi va ustaga biriktiradi
        arizalar = self.r.get('/api/buyurtmalar/operator/arizalar/').json()['arizalar']
        self.assertIn(bid, [a['id'] for a in arizalar], "2: ariza Ruxsoraning ro'yxatida yo'q")
        r = self.r.post(f'/api/buyurtmalar/operator/arizalar/{bid}/tayinlash/', {'xodim_id': self.usta.pk}, format='json')
        self.assertIn(r.status_code, (200, 201), r.content)
        self.assertIn(7002, self.tg, "2: ustaga Telegram'da vazifa xabari bormadi")
        self.ruxsoraga()

        # 3. Usta smena ochadi va bosqichlarni belgilaydi — har biri Ruxsoraga yetadi
        self.assertIn(self.u.post('/api/joylashuv/smena/boshlash/', {}, format='json').status_code, (200, 201))
        for nom, url, tana in [('qabul', f'/api/buyurtmalar/{bid}/qabul/', {}),
                               ("yo'lda", f'/api/buyurtmalar/{bid}/bosqich/', {'holat': 'yolda'}),
                               ('ishni boshladi', f'/api/buyurtmalar/{bid}/bosqich/', {'holat': 'bajarilmoqda'})]:
            r = self.u.post(url, tana, format='json')
            self.assertEqual(r.status_code, 200, (nom, r.content))
            self.assertGreaterEqual(sum(self.ruxsoraga()), 1, f"3: «{nom}» Ruxsoraga yetmadi")

        # 4. Narx: mijoz tanlagan xizmat bor — usta summani tasdiqlaydi
        b = Buyurtma.objects.get(pk=bid)
        summa = q.p_dan
        r = self.u.post(f'/api/buyurtmalar/{bid}/summa/', {'summa': summa}, format='json')
        self.assertIn(r.status_code, (200, 201), r.content)

        # 5. «Ishni tugatdim» → to'lov kutilmoqda; Ruxsoraga xabar
        r = self.u.post(f'/api/buyurtmalar/{bid}/natija/', {'natija': 'Plita tozalandi'}, format='json')
        self.assertEqual(r.json()['holat'], 'tolov_kutilmoqda')
        self.assertGreaterEqual(sum(self.ruxsoraga()), 1, "5: «ishni tugatdi» Ruxsoraga yetmadi")

        # 6. Usta naqd pulni kiritadi va kvitansiya chiqaradi → Ruxsoraga
        r = self.u.post('/api/tushum/', {'summa': summa, 'usul': 'naqd', 'buyurtma': bid,
                                         'tushum_turi': 'aholi:profilaktika'}, format='json')
        self.assertEqual(r.status_code, 201, r.content)
        tid = r.json()['id']
        r = self.u.post('/api/hujjatlar/kvitansiya/', {'tushum': tid}, format='json')
        self.assertIn(r.status_code, (200, 201), r.content)
        self.assertGreaterEqual(sum(self.ruxsoraga()), 1, "6: kvitansiya / tushum Ruxsoraga yetmadi")
        kt = self.r.get('/api/tushum/admin/?holat=kutilmoqda').json()
        self.assertIn(tid, [t['id'] for t in kt['yozuvlar']], "6: tushum Ruxsoraning «Tushumlarni qabul qilish»ida yo'q")

        # 7. Kunlik hisobot → Ruxsoraning «Kunlik hisobotlar» va «Davomat»ida
        self.assertIn(self.u.post('/api/kadrlar/hisobot/', {'joy': 'Kogon', 'ish': f'#{bid} plita'},
                                  format='json').status_code, (200, 201))
        kun = self.r.get('/api/kadrlar/kun/').json()
        qator = next(x for x in kun['xodimlar'] if x['id'] == self.usta.pk)
        self.assertEqual(qator['holat'], 'ishda', "7: davomatda usta smenada ko'rinmadi")
        self.assertIsNotNone(qator['hisobot'], "7: kunlik hisobot Ruxsoraga ko'rinmadi")

        # 8. Ruxsora pulni qabul qiladi → buyurtma yakunlanadi
        r = self.r.post(f'/api/tushum/{tid}/qabul/', {}, format='json')
        self.assertEqual(r.status_code, 200, r.content)
        b.refresh_from_db()
        self.assertEqual((b.holat, b.tolandi), ('bajarildi', True), "8: pul qabul qilingach buyurtma yakunlanmadi")
        holat = next(a for a in self.r.get('/api/buyurtmalar/operator/arizalar/?holat=hammasi').json()['arizalar']
                     if a['id'] == bid)['holat']
        self.assertEqual(holat, 'bajarildi')
        # Usta bildi: puli qabul qilindi va buyurtma to'liq yakunlandi (kabinet + Telegram)
        ustaga = list(Xabar.objects.filter(xodim=self.usta).values_list('matn', flat=True))
        self.assertTrue(any('qabul qilindi' in m for m in ustaga), ustaga)
        self.assertTrue(any("to'liq yakunlandi" in m for m in ustaga), ustaga)

    def test_rad_etilgan_tushum_ustaga_sababi_bilan(self):
        b = Buyurtma.objects.create(mijoz=self.mijoz, xodim=self.usta, xizmat='servis', holat='bajarilmoqda',
                                    tasdiq_summa=100000)
        tid = self.u.post('/api/tushum/', {'summa': 100000, 'usul': 'naqd', 'buyurtma': b.pk,
                                           'tushum_turi': 'aholi:profilaktika'}, format='json').json()['id']
        self.assertEqual(self.r.post(f'/api/tushum/{tid}/rad/', {'sabab': 'Summa mos emas'}, format='json').status_code, 200)
        m = Xabar.objects.filter(xodim=self.usta).latest('id').matn
        self.assertIn('rad etildi', m)
        self.assertIn('Summa mos emas', m)
        self.assertIn(7002, self.tg)

    def test_ishni_tugatdim_holatni_buzmaydi(self):
        """«Ishni tugatdim» faqat ish boshlangandan keyin; ixtiyoriy holat (bekor, yangi) yuborib bo'lmaydi."""
        b = Buyurtma.objects.create(mijoz=self.mijoz, xodim=self.usta, xizmat='servis', holat='qabul')
        r = self.u.post(f'/api/buyurtmalar/{b.pk}/natija/', {'holat': 'bekor'}, format='json')
        b.refresh_from_db()
        self.assertNotEqual(b.holat, 'bekor', "usta buyurtmani «natija» orqali bekor qila oldi")
        self.u.post(f'/api/buyurtmalar/{b.pk}/natija/', {'holat': 'xyz', 'natija': 'yarim'}, format='json')
        b.refresh_from_db()
        self.assertEqual((b.holat, b.natija), ('bajarilmoqda', 'yarim'))
        # Yangi (qabul qilinmagan), bekor yoki yakunlangan buyurtmaga natija kiritilmaydi
        for h in ('yangi', 'bekor', 'bajarildi'):
            Buyurtma.objects.filter(pk=b.pk).update(holat=h)
            self.assertEqual(self.u.post(f'/api/buyurtmalar/{b.pk}/natija/', {}, format='json').status_code, 400, h)
            b.refresh_from_db()
            self.assertEqual(b.holat, h)
