"""Xodim mijozdan olgan pul va uni administratorga topshirishi.

Oqim: xodim summani kiritadi (`kutilmoqda`) -> pulni administratorga topshiradi
-> administrator qabul qiladi (`qabul`) yoki xato kiritilgan bo'lsa sabab bilan
rad etadi (`rad`).

Yozuv kiritilgach xodim uni o'zgartira ham, o'chira ham olmaydi: xato bo'lsa
administrator rad etadi, xodim to'g'risini qayta kiritadi. Django panelida ham
yozuvlar faqat o'qish uchun — pul hisobi "kim, qachon, qancha" aniq qolishi kerak.
"""
from django.conf import settings
from django.db import models

USUL_CHOICES = [
    ('naqd', 'Naqd'),
    ('karta', 'Karta'),
    ('otkazma', "Pul o'tkazmasi"),
]

HOLAT_CHOICES = [
    ('kutilmoqda', 'Topshirilishi kutilmoqda'),
    ('qabul', 'Administrator qabul qildi'),
    ('rad', 'Rad etildi'),
]


class Tushum(models.Model):
    xodim = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
                              related_name='tushumlar')
    # Buyurtma o'chirilsa ham pul yozuvi qoladi
    buyurtma = models.ForeignKey('buyurtmalar.Buyurtma', on_delete=models.SET_NULL,
                                 null=True, blank=True, related_name='tushumlar')
    # Pul qaysi ish turi uchun olingani (narxnomadan tanlanadi). Nom shu paytdagi
    # qiymatda saqlanadi: narxnoma keyin o'zgarsa ham tushum yozuvi o'zgarmaydi.
    ish_qator = models.ForeignKey('narxnoma.NarxnomaQator', on_delete=models.SET_NULL,
                                  null=True, blank=True, related_name='+')
    ish_turi = models.CharField(max_length=450, blank=True)
    # Tushum turkumi: ish turidan (narxnoma tarmog'i va bo'limi), ish turi bo'lmasa
    # buyurtmaning tarmog'idan olinadi. Hisobotlar shu bo'yicha ajraladi (ulgurji / aholi).
    tarmoq = models.CharField(max_length=10, blank=True, db_index=True)
    bolim = models.CharField(max_length=15, blank=True)
    summa = models.BigIntegerField(help_text="so'm")
    usul = models.CharField(max_length=10, choices=USUL_CHOICES, default='naqd')
    izoh = models.CharField(max_length=255, blank=True)
    holat = models.CharField(max_length=12, choices=HOLAT_CHOICES,
                             default='kutilmoqda', db_index=True)
    yaratilgan = models.DateTimeField(auto_now_add=True, db_index=True)

    hal_qilgan = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
                                   null=True, blank=True, related_name='+')
    hal_vaqti = models.DateTimeField(null=True, blank=True)
    rad_sababi = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ['-yaratilgan']
        verbose_name = 'Tushum'
        verbose_name_plural = 'Tushumlar'
        # Tushumni qabul qilish/rad etish huquqi (Django panelidagi "Direktor" guruhi uchun)
        permissions = [('hal_qilish', 'Tushumni qabul qilish yoki rad etish')]
        indexes = [models.Index(fields=['xodim', 'holat'])]

    def __str__(self):
        return f"{self.xodim} — {self.summa:,} so'm ({self.get_holat_display()})"
