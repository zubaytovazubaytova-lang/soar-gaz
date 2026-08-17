from django.db import models

TOLOV_TURI_CHOICES = [
    ('bank', 'Bank o\'tkazmasi'),
    ('online', 'Onlayn to\'lov'),
    ('shartnoma', 'Shartnoma asosida'),
]

TOLOV_TIZIMI_CHOICES = [
    ('', '—'),
    ('click', 'Click'),
    ('payme', 'Payme'),
    ('apelsin', 'Apelsin'),
]

HOLAT_CHOICES = [
    ('yangi', 'Yangi'),
    ('kutilmoqda', 'To\'lov kutilmoqda'),
    ('tolandi', 'To\'landi'),
    ('bekor', 'Bekor qilindi'),
]

TOLOV_TURI_NOMI = dict(TOLOV_TURI_CHOICES)


class TolovSorovi(models.Model):
    ism = models.CharField(max_length=120)
    telefon = models.CharField(max_length=30)
    tolov_turi = models.CharField(max_length=20, choices=TOLOV_TURI_CHOICES, default='bank')
    tolov_turi_nomi = models.CharField(max_length=60, blank=True)
    tolov_tizimi = models.CharField(max_length=20, choices=TOLOV_TIZIMI_CHOICES, blank=True, default='')
    xizmat_turi = models.CharField(max_length=100, blank=True)
    summa = models.BigIntegerField(default=0)          # so'm
    izoh = models.TextField(blank=True)
    muddat = models.CharField(max_length=60, blank=True)  # shartnoma: bo'lib to'lash muddati
    holat = models.CharField(max_length=20, choices=HOLAT_CHOICES, default='yangi')
    tashqi_id = models.CharField(max_length=120, blank=True)  # Click/Payme tranzaksiya id
    yaratilgan = models.DateTimeField(auto_now_add=True)
    yangilangan = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'To\'lov so\'rovi'
        verbose_name_plural = 'To\'lov so\'rovlari'
        ordering = ['-yaratilgan']

    def save(self, *args, **kwargs):
        if not self.tolov_turi_nomi:
            self.tolov_turi_nomi = TOLOV_TURI_NOMI.get(self.tolov_turi, self.tolov_turi)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"#{self.id} {self.ism} — {self.tolov_turi_nomi} ({self.holat})"


MAHSULOT_HOLAT_CHOICES = [
    ('yangi', 'Yangi'),
    ('korildi', 'Ko\'rib chiqildi'),
    ('boglandi', 'Bog\'lanildi'),
    ('yakunlandi', 'Yakunlandi'),
    ('bekor', 'Bekor qilindi'),
]


class MahsulotSorovi(models.Model):
    """Xaridlar katalogidagi jihozlar bo'yicha narx/xarid so'rovi."""
    ism = models.CharField(max_length=120)
    telefon = models.CharField(max_length=30)
    mahsulot = models.CharField(max_length=200)
    katalog = models.CharField(max_length=60, blank=True)   # quvur/hisob/ventil/jihoz
    miqdor = models.IntegerField(default=1)
    birlik = models.CharField(max_length=20, blank=True)
    izoh = models.TextField(blank=True)
    holat = models.CharField(max_length=20, choices=MAHSULOT_HOLAT_CHOICES, default='yangi')
    yaratilgan = models.DateTimeField(auto_now_add=True)
    yangilangan = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Mahsulot so\'rovi'
        verbose_name_plural = 'Mahsulot so\'rovlari'
        ordering = ['-yaratilgan']

    def __str__(self):
        return f"#{self.id} {self.mahsulot} ×{self.miqdor} — {self.ism}"
