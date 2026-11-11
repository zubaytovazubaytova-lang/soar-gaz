"""Administratordan xodimga xabar.

Har qabul qiluvchiga alohida qator yoziladi (hammaga yuborilganda ham): shunda
kim o'qigani va kim o'qimagani aniq ko'rinadi, o'qilgan belgisi esa har xodimda
alohida turadi.
"""
from django.conf import settings
from django.db import models


class Xabar(models.Model):
    xodim = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                              related_name='xabarlar')
    yuboruvchi = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
                                   null=True, blank=True, related_name='+')
    matn = models.CharField(max_length=500)
    yaratilgan = models.DateTimeField(auto_now_add=True, db_index=True)
    oqilgan = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-yaratilgan']
        verbose_name = 'Xabar'
        verbose_name_plural = 'Xabarlar'
        indexes = [models.Index(fields=['xodim', 'oqilgan'])]

    def __str__(self):
        return f"{self.xodim}: {self.matn[:40]}"
