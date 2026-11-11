"""Xodimlar joylashuvi — faqat SMENA davomida va xodimning ROZILIGI bilan.

Qoidalar (kod shularni majburlaydi, faqat va'da qilmaydi):
  * nuqta faqat ochiq smena bo'lganda yoziladi — smenadan tashqarida joylashuv
    olinmaydi;
  * rozilik bo'lmasa smena ochilmaydi;
  * smena unutilib qolsa, JOYLASHUV_SMENA_MAX_SOAT dan keyin o'zi yopiladi;
  * nuqtalar JOYLASHUV_SAQLASH_KUN kundan keyin o'chiriladi
    (`manage.py joylashuv_tozala`).
"""
from django.conf import settings
from django.db import models

# Rozilik matni o'zgarsa shu raqamni oshiring — barcha xodimdan qayta rozilik
# so'raladi. Matnning o'zi xodimlar.html da turadi.
ROZILIK_VERSIYASI = 1


class Rozilik(models.Model):
    """Xodim joylashuvi kuzatilishiga bergan roziligi (kim, qachon, qaysi IP)."""
    xodim = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                                 related_name='joylashuv_roziligi')
    versiya = models.PositiveSmallIntegerField(default=ROZILIK_VERSIYASI)
    vaqt = models.DateTimeField(auto_now=True)
    ip = models.GenericIPAddressField(null=True, blank=True)

    class Meta:
        verbose_name = 'Joylashuv roziligi'
        verbose_name_plural = 'Joylashuv roziliklari'

    def __str__(self):
        return f"{self.xodim} — v{self.versiya} ({self.vaqt:%d.%m.%Y})"


class Smena(models.Model):
    xodim = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                              related_name='smenalar')
    boshlandi = models.DateTimeField(auto_now_add=True)
    tugadi = models.DateTimeField(null=True, blank=True)
    # 'xodim' — o'zi tugatdi, 'avto' — vaqt tugab o'zi yopildi
    tugash_sababi = models.CharField(max_length=10, blank=True)

    class Meta:
        ordering = ['-boshlandi']
        verbose_name = 'Smena'
        verbose_name_plural = 'Smenalar'
        indexes = [models.Index(fields=['xodim', 'tugadi'])]

    def __str__(self):
        return f"{self.xodim} — {self.boshlandi:%d.%m.%Y %H:%M}"


class Nuqta(models.Model):
    smena = models.ForeignKey(Smena, on_delete=models.CASCADE, related_name='nuqtalar')
    xodim = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                              related_name='joylashuv_nuqtalari')
    lat = models.FloatField()
    lng = models.FloatField()
    aniqlik = models.FloatField(null=True, blank=True, help_text='metr')
    vaqt = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ['-vaqt']
        verbose_name = 'Joylashuv nuqtasi'
        verbose_name_plural = 'Joylashuv nuqtalari'
        indexes = [models.Index(fields=['xodim', '-vaqt'])]

    def __str__(self):
        return f"{self.xodim} — {self.vaqt:%d.%m %H:%M:%S}"
