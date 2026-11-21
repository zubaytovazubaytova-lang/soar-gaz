"""Hisoblagich tekshiruvi muddati yaqinlashganda mijozga eslatma yaratadi.

Kuniga bir marta ishga tushiriladi (Windows Task Scheduler yoki cron):
    python manage.py tekshiruv_eslatma

Bir hisoblagich uchun bir muddat oynasida faqat bitta eslatma yuboriladi.

Mijozning raqami @soargaz_bot ga ulangan bo'lsa eslatma Telegram'ga ham TEKIN boradi
(pullik SMS bu yerdan yuborilmaydi). Serverda `soargaz-eslatma.timer` har kuni ishga tushiradi.
"""

from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.kabinet.models import (
    Hisoblagich, Bildirishnoma, KabinetSozlama, TEKSHIRUV_ESLATMA_KUN,
)
from apps.sms_app import telegram
from apps.sms_app.models import SmsXabar


class Command(BaseCommand):
    help = "Tekshiruv muddati yaqin hisoblagichlar bo'yicha mijozlarga eslatma yaratadi"

    def add_arguments(self, parser):
        parser.add_argument('--kun', type=int, default=TEKSHIRUV_ESLATMA_KUN,
                            help='Necha kun qolganda eslatma yuborilsin')

    def handle(self, *args, **sozlama):
        chegara = timezone.localdate() + timezone.timedelta(days=sozlama['kun'])
        qs = Hisoblagich.objects.filter(
            holat='faol', keyingi_tekshiruv__isnull=False, keyingi_tekshiruv__lte=chegara,
        ).select_related('obyekt', 'obyekt__mijoz')

        # Sozlamalar va mavjud eslatmalar oldindan bitta so'rovda olinadi —
        # ilgari har hisoblagich uchun ikkita qo'shimcha so'rov ketardi.
        mijoz_idlari = {h.obyekt.mijoz_id for h in qs}
        sozlamalar = {
            s.mijoz_id: s
            for s in KabinetSozlama.objects.filter(mijoz_id__in=mijoz_idlari)
        }
        mavjud = set(
            Bildirishnoma.objects
            .filter(mijoz_id__in=mijoz_idlari, turi='texnik', oqildi=False)
            .values_list('mijoz_id', 'matn')
        )

        yangi_bildirishnomalar, yangi_smslar, telegramga = [], [], []
        for h in qs:
            mijoz = h.obyekt.mijoz
            tanlov = sozlamalar.get(mijoz.id)
            if tanlov and not tanlov.tekshiruv_eslatma:
                continue

            kun = h.kun_qoldi
            matn = (
                f"{h.obyekt.nom} — hisoblagich {h.seriya_raqam}. "
                + (f"Muddati {abs(kun)} kun oldin tugagan!" if kun < 0
                   else f"{kun} kundan keyin muddati tugaydi.")
            )
            # Shu hisoblagich uchun ochiq eslatma bormi?
            if (mijoz.id, matn) in mavjud:
                continue
            # Bitta ishga tushishda bir xil matn ikki marta qo'shilmasin
            mavjud.add((mijoz.id, matn))

            yangi_bildirishnomalar.append(Bildirishnoma(
                mijoz=mijoz, turi='texnik', bolim='hisoblagichlar',
                sarlavha="Texnik ko'rik muddati yaqinlashdi", matn=matn,
            ))
            if not tanlov or tanlov.sms_bildirishnoma:
                yangi_smslar.append(SmsXabar(mijoz=mijoz, matn='Soar Gaz: ' + matn))
                telegramga.append((mijoz.telefon,
                                   f"SOAR GAZ: {matn}" + chr(10) + "Tekshiruvga yozilish: https://soargaz.uz/kabinet/"))

        Bildirishnoma.objects.bulk_create(yangi_bildirishnomalar)
        SmsXabar.objects.bulk_create(yangi_smslar)

        # Telegram (tekin): faqat botga ulangan mijozlarga; ulanmaganlarga yubor() jim False qaytaradi
        tg_ketdi = sum(1 for tel, m in telegramga if telegram.yubor(tel, m))

        yaratildi = len(yangi_bildirishnomalar)
        self.stdout.write(self.style.SUCCESS(f'{yaratildi} ta eslatma yaratildi, {tg_ketdi} tasi Telegram orqali ketdi'))
