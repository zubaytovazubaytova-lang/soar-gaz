"""Xodimni Telegram botga shaxsiy havola orqali ulash va Kadrlar nazorati."""
from unittest import mock

from django.core.cache import cache
from django.test import TestCase, override_settings
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from apps.aloqa.models import Xabar
from apps.auth_app.models import Foydalanuvchi
from apps.sms_app.models import TelegramUlanish
from apps.sms_app import telegram

HAVOLA = '/api/auth/xodim/telegram-havola/'


def klient(user):
    c = APIClient()
    c.credentials(HTTP_AUTHORIZATION='Bearer ' + str(RefreshToken.for_user(user).access_token))
    return c


def start(matn, chat_id=555001):
    telegram.yangilanishni_qayta_ishla({'message': {'chat': {'id': chat_id, 'type': 'private'},
                                                    'from': {'id': chat_id, 'username': 'usta'}, 'text': matn}})


@override_settings(TELEGRAM_BOT_TOKEN='123:sinov', TELEGRAM_BOT_USERNAME='soargaz_bot')
@mock.patch('apps.sms_app.telegram._api', return_value={'ok': True})
class XodimTelegramTestlari(TestCase):
    def setUp(self):
        cache.clear()
        mk = Foydalanuvchi.objects.create
        self.usta = mk(telefon='+998900000801', ism='Aziz', rol='xodim', holat='faol', lavozim='Chilangar')
        self.kadr = mk(telefon='+998900000802', ism='Ruxsora', rol='xodim', holat='faol',
                       lavozim="Kadrlar bo'yicha mutaxassis")
        self.mijoz = mk(telefon='+998900000803', ism='Karim', rol='mijoz')

    def havola_tokeni(self, user=None):
        r = klient(user or self.usta).post(HAVOLA)
        self.assertEqual(r.status_code, 200, r.content)
        url = r.json()['url']
        self.assertTrue(url.startswith('https://t.me/soargaz_bot?start=x_'))
        return url.split('start=')[1]

    def test_havola_orqali_kabinet_raqamiga_ulanadi(self, _api):
        start('/start ' + self.havola_tokeni())
        u = TelegramUlanish.objects.get(chat_id=555001)
        self.assertEqual(u.telefon, '+998900000801')              # Telegram raqami so'ralmadi
        self.assertTrue(klient(self.usta).get('/api/auth/xodim/profil/').json()['telegram_ulangan'])

    def test_havola_bir_martalik(self, _api):
        token = self.havola_tokeni()
        start('/start ' + token)
        TelegramUlanish.objects.all().delete()
        start('/start ' + token, chat_id=555002)
        self.assertFalse(TelegramUlanish.objects.exists())

    def test_mijoz_havola_ololmaydi(self, _api):
        self.assertEqual(klient(self.mijoz).post(HAVOLA).status_code, 403)

    def test_kadrlar_kunida_telegram_va_eslatma(self, _api):
        start('/start ' + self.havola_tokeni())
        Foydalanuvchi.objects.create(telefon='+998900000804', ism='Vali', rol='xodim', holat='faol',
                                     lavozim='Metrolog')
        j = klient(self.kadr).get('/api/kadrlar/kun/').json()
        qator = {x['telefon']: x['telegram'] for x in j['xodimlar']}
        self.assertEqual(qator, {'+998900000801': True, '+998900000804': False})
        self.assertEqual(j['xulosa']['botsiz'], 1)
        r = klient(self.kadr).post('/api/kadrlar/bot-eslatma/')
        self.assertEqual((r.status_code, r.json()['yuborildi']), (201, 1))
        self.assertEqual(Xabar.objects.filter(xodim__telefon='+998900000804').count(), 1)
        self.assertEqual(klient(self.kadr).post('/api/kadrlar/bot-eslatma/').status_code, 429)   # soatiga bir marta
        self.assertEqual(klient(self.usta).post('/api/kadrlar/bot-eslatma/').status_code, 403)


@override_settings(TELEGRAM_BOT_TOKEN='123:sinov', TELEGRAM_BOT_USERNAME='soargaz_bot')
class AdmingaXabarTestlari(TestCase):
    """Xodim portalga birinchi kirsa va botga ulansa — admin Telegram'iga xabar."""

    def setUp(self):
        cache.clear()
        mk = Foydalanuvchi.objects.create
        self.admin = mk(telefon='+998900000901', ism='Ega', rol='admin', holat='faol')
        self.usta = mk(telefon='+998900000902', ism='Aziz', rol='xodim', holat='faol', lavozim='Chilangar',
                       kirish_kodi='XD-ABC123')
        self.mijoz = mk(telefon='+998900000903', ism='Karim', rol='mijoz')
        TelegramUlanish.objects.create(telefon=self.admin.telefon, chat_id=901)
        self.yuborilgan = []
        for p in (mock.patch('apps.sms_app.telegram._api', side_effect=self._api),
                  mock.patch('django.db.transaction.on_commit', side_effect=lambda f, *a, **k: f())):
            p.start()
            self.addCleanup(p.stop)

    def _api(self, metod, malumot=None, *a, **k):
        if metod == 'sendMessage':
            self.yuborilgan.append(((malumot or {}).get('chat_id'), (malumot or {}).get('text', '')))
        return {'ok': True}

    def admin_xabarlari(self):
        return [m for c, m in self.yuborilgan if c == 901]

    def test_birinchi_kirish_faqat_bir_marta(self):
        kir = lambda: APIClient().post('/api/auth/xodim/login/', {'telefon': self.usta.telefon, 'kod': 'XD-ABC123'},
                                       format='json')
        self.assertEqual(kir().status_code, 200)
        self.assertEqual(len(self.admin_xabarlari()), 1)
        self.assertIn('birinchi marta', self.admin_xabarlari()[0])
        self.assertIn('Aziz', self.admin_xabarlari()[0])
        kir()
        self.assertEqual(len(self.admin_xabarlari()), 1)        # ikkinchi kirishda xabar yo'q

    def test_havola_orqali_botga_ulanish(self):
        token = klient(self.usta).post(HAVOLA).json()['url'].split('start=')[1]
        start('/start ' + token, chat_id=902)
        self.assertTrue(any('botga ulandi' in m and 'Aziz' in m for m in self.admin_xabarlari()))

    def test_raqam_ulashish_xodim_va_mijoz(self):
        def kontakt(telefon, cid):
            telegram.yangilanishni_qayta_ishla({'message': {
                'chat': {'id': cid, 'type': 'private'}, 'from': {'id': cid},
                'contact': {'user_id': cid, 'phone_number': telefon}}})
        kontakt(self.mijoz.telefon, 903)
        self.assertFalse(self.admin_xabarlari())                  # mijoz ulandi — adminga xabar yo'q
        kontakt(self.usta.telefon, 902)
        self.assertTrue(any('botga ulandi' in m for m in self.admin_xabarlari()))
