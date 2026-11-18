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


class TelegramUlanish(models.Model):
    """Telefon raqami <-> Telegram chat. Raqam botdagi «Raqamni ulashish» tugmasi orqali
    Telegram tomonidan tasdiqlanadi, shuning uchun u SMS kabi ishonchli."""
    telefon = models.CharField(max_length=20, unique=True, help_text="+998901234567 ko'rinishida")
    chat_id = models.BigIntegerField(unique=True)
    username = models.CharField(max_length=64, blank=True)
    yaratilgan = models.DateTimeField(auto_now_add=True)
    yangilangan = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Telegram ulanishi'
        verbose_name_plural = 'Telegram ulanishlari'
        ordering = ['-yangilangan']

    def __str__(self):
        return f"{self.telefon} -> {self.chat_id}"
