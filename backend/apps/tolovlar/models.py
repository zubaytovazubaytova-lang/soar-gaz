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
    # Payme holat mashinasi (millisekundda, Payme o'zi shu formatda kutadi).
    # Bitta so'rov — bitta Payme tranzaksiya: bekor qilingan so'rov qayta
    # to'lanmaydi, mijoz yangi so'rov oladi (apps.xaridlar.tolov).
    payme_yaratilgan = models.BigIntegerField(null=True, blank=True)
    payme_bajarilgan = models.BigIntegerField(null=True, blank=True)
    payme_bekor = models.BigIntegerField(null=True, blank=True)
    payme_sabab = models.IntegerField(null=True, blank=True)
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


METROLOGIYA_XIZMAT_CHOICES = [
    ('kalibrovka', 'Kalibrovka'),
    ('almashtirish', 'Almashtirish'),
    ('qiyoslov', "Davlat qiyoslov ko'rigi"),
]


class MetrologiyaArizasi(models.Model):
    """Saytning Metrologiya bo'limidan kelgan ariza (kalibrovka, almashtirish,
    davlat qiyoslov ko'rigi). Mijoz tizimga kirmagan bo'lishi mumkin, shuning
    uchun `Buyurtma` emas, `MahsulotSorovi` kabi alohida jadval."""
    ism = models.CharField(max_length=120)
    telefon = models.CharField(max_length=30)
    # Ixtiyoriy: mijoz xizmat turini bilmasligi mumkin — ariza baribir qabul qilinadi,
    # xizmat turini mutaxassis telefon orqali aniqlaydi.
    xizmat = models.CharField(max_length=20, choices=METROLOGIYA_XIZMAT_CHOICES, blank=True, default='')
    hisoblagich = models.CharField(max_length=30, blank=True)       # G4, G6, ...
    seriya_raqam = models.CharField(max_length=60, blank=True)
    ornatilgan_yil = models.PositiveSmallIntegerField(null=True, blank=True)
    manzil = models.CharField(max_length=250, blank=True)
    izoh = models.TextField(blank=True)
    holat = models.CharField(max_length=20, choices=MAHSULOT_HOLAT_CHOICES, default='yangi')
    yaratilgan = models.DateTimeField(auto_now_add=True)
    yangilangan = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Metrologiya arizasi'
        verbose_name_plural = 'Metrologiya arizalari'
        ordering = ['-yaratilgan']

    def __str__(self):
        return f"#{self.id} {self.xizmat_nomi} — {self.ism}"

    @property
    def xizmat_nomi(self):
        return self.get_xizmat_display() if self.xizmat else "Xizmat turi tanlanmagan"
