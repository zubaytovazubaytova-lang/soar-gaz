from django.db import models
from django.conf import settings


class SmsXabar(models.Model):
    mijoz = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='sms_xabarlari'
    )
    matn = models.TextField()
    oqildi = models.BooleanField(default=False)
    yuboruvchi = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='yuborilgan_smslar'
    )
    yaratilgan = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'SMS Xabar'
        verbose_name_plural = 'SMS Xabarlar'
        ordering = ['-yaratilgan']

    def __str__(self):
        return f"{self.mijoz.telefon}: {self.matn[:40]}"
