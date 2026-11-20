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
    # Mijoz kabinetidan xizmat buyurtmasi uchun to'lov (Click yoki bank o'tkazmasi): to'lansa buyurtma «to'langan»
    buyurtma = models.ForeignKey('buyurtmalar.Buyurtma', on_delete=models.SET_NULL, null=True, blank=True,
                                 related_name='tolov_sorovlari')
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


# ──────────────────────────────────────────────────────────────
#  Bank (hisob raqam) orqali to'lov: mijoz chek skrinshotini yuklaydi,
#  admin yoki Kadrlar mutaxassisi bankda pulni ko'rib TASDIQLAYDI.
#  Skrinshot o'zi isbot emas — «to'landi» faqat tasdiqdan keyin.
# ──────────────────────────────────────────────────────────────
YONALISH_CHOICES = [
    ('servis', 'Servis xizmatlari'),
    ('montaj', 'Qurilish-montaj xizmatlari'),
    ('xarid', "Mahsulot xaridlari (do'kon)"),
]

# Buyurtma xizmati → qaysi hisob raqamga to'lanadi
XIZMAT_YONALISH = {'montaj': 'montaj', 'loyiha': 'montaj'}


def xizmat_yonalishi(xizmat):
    return XIZMAT_YONALISH.get(xizmat, 'servis')


class Rekvizit(models.Model):
    """Korxonaning to'lov qabul qiladigan hisob raqami (admin panelida kiritiladi)."""
    yonalish = models.CharField(max_length=10, choices=YONALISH_CHOICES, unique=True, verbose_name="Yo'nalish")
    korxona = models.CharField(max_length=150, verbose_name='Korxona nomi')
    bank = models.CharField(max_length=150, verbose_name='Bank va filial')
    hisob_raqam = models.CharField(max_length=20, verbose_name='Hisob raqam (20 xonali)')
    mfo = models.CharField(max_length=5, verbose_name='MFO (bank kodi)')
    stir = models.CharField(max_length=9, verbose_name='STIR (INN)')
    manzil = models.CharField(max_length=250, blank=True, verbose_name='Yuridik manzil')
    # Kvitansiyada qonuniy asos: faoliyat ruxsatnomasi (litsenziya) — raqami, reestr, amal qilish muddati
    ruxsatnoma = models.CharField(max_length=250, blank=True, verbose_name='Ruxsatnoma (litsenziya)',
                                  help_text="Masalan: №1234567, reestr R-12345678, 01.01.2030 gacha")
    faol = models.BooleanField(default=True)

    class Meta:
        verbose_name = 'To\'lov rekviziti'
        verbose_name_plural = 'To\'lov rekvizitlari'

    def clean(self):
        from django.core.exceptions import ValidationError
        xatolar = {}
        if not (self.hisob_raqam.isdigit() and len(self.hisob_raqam) == 20):
            xatolar['hisob_raqam'] = 'Hisob raqam 20 ta raqamdan iborat bo\'lishi kerak'
        if not (self.mfo.isdigit() and len(self.mfo) == 5):
            xatolar['mfo'] = 'MFO 5 ta raqamdan iborat bo\'lishi kerak'
        if not (self.stir.isdigit() and len(self.stir) == 9):
            xatolar['stir'] = 'STIR 9 ta raqamdan iborat bo\'lishi kerak'
        if xatolar:
            raise ValidationError(xatolar)

    def __str__(self):
        return f"{self.get_yonalish_display()}: {self.hisob_raqam}"


BANK_TOLOV_HOLAT = [
    ('tekshirilmoqda', 'Tekshirilmoqda'),
    ('tasdiqlandi', 'Tasdiqlandi'),
    ('rad', 'Rad etildi'),
]


class BankTolovi(models.Model):
    # Bittasi to'ldiriladi: xizmat buyurtmasi YOKI do'kon xaridi
    buyurtma = models.ForeignKey('buyurtmalar.Buyurtma', on_delete=models.CASCADE, null=True, blank=True,
                                 related_name='bank_tolovlari')
    xarid = models.ForeignKey('xaridlar.Xarid', on_delete=models.CASCADE, null=True, blank=True,
                              related_name='bank_tolovlari')
    # Do'kondan mehmon sifatida (kirmasdan) xarid qilgan mijozda hisob bo'lmasligi mumkin
    mijoz = models.ForeignKey('auth_app.Foydalanuvchi', on_delete=models.CASCADE, null=True, blank=True,
                              related_name='bank_tolovlari')
    summa = models.BigIntegerField(verbose_name="Summa (so'm)")
    hisob_raqam = models.CharField(max_length=20, blank=True, verbose_name="To'langan hisob raqam")
    # nginx `hujjatlar_maxfiy/` ni ochiq bermaydi: chek faqat ruxsatli ko'rinish orqali ochiladi
    chek = models.FileField(upload_to='hujjatlar_maxfiy/bank_cheklar/', verbose_name="To'lov cheki")
    izoh = models.CharField(max_length=300, blank=True)
    holat = models.CharField(max_length=15, choices=BANK_TOLOV_HOLAT, default='tekshirilmoqda', db_index=True)
    rad_sabab = models.CharField(max_length=300, blank=True)
    tekshirdi = models.ForeignKey('auth_app.Foydalanuvchi', on_delete=models.SET_NULL, null=True, blank=True,
                                  related_name='tekshirgan_bank_tolovlari')
    tekshirilgan = models.DateTimeField(null=True, blank=True)
    tolov_sorovi = models.OneToOneField(TolovSorovi, on_delete=models.SET_NULL, null=True, blank=True,
                                        related_name='bank_tolovi')
    yaratilgan = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Bank to\'lovi (chek)'
        verbose_name_plural = 'Bank to\'lovlari (cheklar)'
        ordering = ['-yaratilgan']

    def __str__(self):
        nom = self.xarid.raqam if self.xarid_id else f'#{self.buyurtma_id}'
        return f"{nom} — {self.summa} so'm ({self.get_holat_display()})"
