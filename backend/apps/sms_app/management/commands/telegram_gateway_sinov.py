"""Telegram Gateway orqali sinov kodi yuboradi.

    manage.py telegram_gateway_sinov +998901234567        # kodni o'zi yaratadi
    manage.py telegram_gateway_sinov +998901234567 --kod 123456
    manage.py telegram_gateway_sinov --token-tekshir      # tokenni pulsiz tekshiradi

DIQQAT: o'z (Gateway hisobi egasining) raqamiga yuborish tekin; boshqa raqamga ~$0.01 yechiladi.
"""
import random

from django.core.management.base import BaseCommand, CommandError

from apps.sms_app import tg_gateway


class Command(BaseCommand):
    help = "Telegram Gateway sinovi"

    def add_arguments(self, parser):
        parser.add_argument('telefon', nargs='?', help='+998901234567')
        parser.add_argument('--kod', help="4-8 xonali kod (bo'lmasa tasodifiy)")
        parser.add_argument('--token-tekshir', action='store_true', help='faqat tokenni tekshiradi')

    def handle(self, *args, **opts):
        if not tg_gateway.sozlangan():
            raise CommandError('TELEGRAM_GATEWAY_TOKEN berilmagan')
        if opts['token_tekshir']:
            yaroqli, sabab = tg_gateway.token_yaroqlimi()
            if not yaroqli:
                raise CommandError(f"Token yaroqsiz: {sabab}")
            self.stdout.write(self.style.SUCCESS('Token yaroqli'))
            return
        if not opts['telefon']:
            raise CommandError('Telefon raqamini yozing: +998901234567')
        kod = opts['kod'] or ''.join(random.choices('0123456789', k=6))
        try:
            natija = tg_gateway._api('sendVerificationMessage', {
                'phone_number': tg_gateway.e164(opts['telefon']), 'code': kod, 'ttl': 300})
        except tg_gateway.GatewayXato as xato:
            raise CommandError(str(xato))
        self.stdout.write(self.style.SUCCESS('Yuborildi: Telegram > «Verification Codes» chatini tekshiring'))
        self.stdout.write(f"request_id: {natija.get('request_id')}")
        self.stdout.write(f"narx: {natija.get('request_cost')}  |  qoldiq balans: {natija.get('remaining_balance')}")
