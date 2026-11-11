from datetime import timedelta

from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.joylashuv.models import Nuqta


class Command(BaseCommand):
    help = ("Saqlash muddati (JOYLASHUV_SAQLASH_KUN) o'tgan joylashuv nuqtalarini "
            "o'chiradi. Serverda kuniga bir marta ishga tushiring (cron).")

    def handle(self, *args, **opts):
        chegara = timezone.now() - timedelta(days=settings.JOYLASHUV_SAQLASH_KUN)
        soni, _ = Nuqta.objects.filter(vaqt__lt=chegara).delete()
        self.stdout.write(f"{soni} ta eski nuqta o'chirildi "
                          f"({settings.JOYLASHUV_SAQLASH_KUN} kundan eski).")
