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
