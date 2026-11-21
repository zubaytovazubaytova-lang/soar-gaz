"""Telegram webhook'ni o'rnatadi / o'chiradi / holatini ko'rsatadi.

    manage.py telegram_webhook            # o'rnatadi: <DJANGO_SAYT_MANZIL>/api/sms/telegram/webhook/
    manage.py telegram_webhook --holat    # token va webhook holatini ko'rsatadi (tokenni chop etmaydi)
    manage.py telegram_webhook --ochir    # webhook'ni o'chiradi
"""
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from apps.sms_app import telegram


class Command(BaseCommand):
    help = "Telegram bot webhook'ini boshqaradi"

    def add_arguments(self, parser):
        parser.add_argument('--ochir', action='store_true', help="webhook'ni o'chiradi")
        parser.add_argument('--holat', action='store_true', help="holatni ko'rsatadi (hech narsani o'zgartirmaydi)")

    def handle(self, *args, **opts):
        if not telegram.sozlangan():
            raise CommandError('TELEGRAM_BOT_TOKEN berilmagan')
        try:
            if opts['holat']:
                bot = telegram.bot_malumoti()
                info = telegram._api('getWebhookInfo')
                self.stdout.write(f"Bot: @{bot.get('username')} (id {bot.get('id')})")
                self.stdout.write(f"Webhook: {info.get('url') or 'o`rnatilmagan'}")
                self.stdout.write(f"Kutilayotgan yangilanishlar: {info.get('pending_update_count')}")
                if info.get('last_error_message'):
                    self.stdout.write(self.style.WARNING(f"So'nggi xato: {info['last_error_message']}"))
                return
            if opts['ochir']:
                telegram.webhook_ochir()
                self.stdout.write(self.style.SUCCESS("Webhook o'chirildi"))
                return
            if not settings.TELEGRAM_WEBHOOK_SECRET:
                raise CommandError('TELEGRAM_WEBHOOK_SECRET berilmagan')
            url = settings.SAYT_MANZIL.rstrip('/') + '/api/sms/telegram/webhook/'
            if not url.startswith('https://'):
                raise CommandError(f"Telegram faqat HTTPS webhook qabul qiladi: {url}")
            telegram.webhook_ornat(url)
            self.stdout.write(self.style.SUCCESS(f"Webhook o'rnatildi: {url}"))
        except telegram.TelegramXato as xato:
            raise CommandError(str(xato))
