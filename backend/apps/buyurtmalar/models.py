from django.db import models
from django.conf import settings
from django.utils.translation import gettext_lazy as _

from apps.narxnoma.models import TARMOQ_CHOICES

XIZMAT_CHOICES = [
    ('loyiha', _('Loyihalashtirish')),
    ('montaj', _('Montaj')),
    ('servis', _('Servis')),
    ('uskunalar', _('Uskunalar')),
    ('metrologiya', _('Metrologiya')),
]

HOLAT_CHOICES = [
    ('yangi', _('Yangi')),
    ('qabul', _('Qabul qilindi')),
    ('bajarilmoqda', _('Bajarilmoqda')),
    ('bajarildi', _('Bajarildi')),
    ('bekor', _('Bekor qilindi')),
]

XIZMAT_NOMI = {
    'loyiha': _('Loyihalashtirish'),
    'montaj': _('Montaj'),
    'servis': _('Servis'),
    'uskunalar': _('Uskunalar'),
    'metrologiya': _('Metrologiya'),
}


class Buyurtma(models.Model):
    mijoz = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='buyurtmalar', null=True, blank=True
    )
    xodim = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        related_name='xodim_buyurtmalari', null=True, blank=True
    )
    # Mijoz kabinetida ro'yxatdan o'tgan obyekt (uy / dala hovli / ofis).
    # Bo'sh bo'lsa — manzil profildan olinadi.
    obyekt = models.ForeignKey(
        'kabinet.Obyekt', on_delete=models.SET_NULL,
        related_name='buyurtmalar', null=True, blank=True
    )
    xizmat = models.CharField(max_length=20, choices=XIZMAT_CHOICES)
    xizmat_nomi = models.CharField(max_length=100, blank=True)
    # Qaysi narx tarmog'i: shunga qarab xodim FAQAT shu tarmoq narxnomalaridan xizmat
    # tanlay oladi. Mijoz buni o'zi tanlay olmaydi (ulgurji narxdan foydalanib ketmasin):
    # korxona mijozlar uchun avtomatik 'ulgurji', qolganlariga 'aholi'; administrator o'zgartiradi.
    tarmoq = models.CharField(max_length=10, choices=TARMOQ_CHOICES, default='aholi', db_index=True)
    # Buyurtma bergan paytdagi mijoz aloqasi — shu buyurtmaning o'zida saqlanadi.
    # Mijoz keyin profilidagi raqamni o'zgartirsa ham, eski buyurtmada o'sha
    # paytda xodim bog'lanishi kerak bo'lgan raqam qoladi. Mijoz boshqa raqam
    # (masalan manzildagi odamniki) ko'rsatsa, shu yerga yoziladi; ko'rsatmasa
    # `save()` profildagisini qo'yadi.
    mijoz_ism = models.CharField(max_length=100, blank=True, verbose_name='Mijoz ismi')
    mijoz_telefon = models.CharField(max_length=20, blank=True, verbose_name='Mijoz telefoni')
    tuman = models.CharField(max_length=50, blank=True)
    manzil = models.CharField(max_length=255, blank=True)
    tavsif = models.TextField(blank=True)
    vaqt_istagi = models.CharField(max_length=100, blank=True)
    holat = models.CharField(max_length=20, choices=HOLAT_CHOICES, default='yangi')
    natija = models.TextField(blank=True)
    natija_soat = models.FloatField(null=True, blank=True)
    natija_sana = models.DateTimeField(null=True, blank=True)
    material = models.CharField(max_length=255, blank=True)
    tolandi = models.BooleanField(default=False)
    # Ariza joylashuvi: operator qo'ng'iroq paytida xaritadan belgilaydi (eng yaqin xodimni topish uchun)
    lat = models.FloatField(null=True, blank=True)
    lng = models.FloatField(null=True, blank=True)
    # Ish jarayonida xodim narxnomadan xizmatlarni tanlaydi, narx hisoblanadi va
    # xodim yakuniy summani TASDIQLAYDI. Tushum (pul) shu summa bo'yicha qabul qilinadi.
    tasdiq_summa = models.BigIntegerField(null=True, blank=True, verbose_name='Tasdiqlangan summa (so\'m)')
    tasdiq_vaqt = models.DateTimeField(null=True, blank=True)
    tasdiq_kim = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        related_name='+', null=True, blank=True
    )
    yaratilgan = models.DateTimeField(auto_now_add=True)
    yangilangan = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Buyurtma'
        verbose_name_plural = 'Buyurtmalar'
        ordering = ['-yaratilgan']

    def save(self, *args, **kwargs):
        # `xizmat_nomi` bazaga YOZILMAYDI: u tilga bog'liq va serializer uni
        # har so'rovda `get_xizmat_display()` orqali joriy tilda beradi.
        # Eski yozuvlarda saqlangan qiymat qolishi mumkin — u e'tiborsiz.
        if self.obyekt:
            self.tuman = self.tuman or self.obyekt.tuman
            self.manzil = self.manzil or self.obyekt.manzil
        if self.mijoz and not self.tuman:
            self.tuman = self.mijoz.tuman
        if self.mijoz and not self.manzil:
            self.manzil = self.mijoz.manzil
        if self.mijoz:
            self.mijoz_ism = self.mijoz_ism or self.mijoz.ism
            self.mijoz_telefon = self.mijoz_telefon or self.mijoz.telefon
        super().save(*args, **kwargs)

    def __str__(self):
        return f"#{self.id} {self.xizmat_nomi} — {self.holat}"


class BuyurtmaFoto(models.Model):
    buyurtma = models.ForeignKey(Buyurtma, on_delete=models.CASCADE, related_name='fotolar')
    rasm = models.ImageField(upload_to='buyurtma_fotolar/')
    tur = models.CharField(max_length=20, default='ish')
    yaratilgan = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Buyurtma Foto'
        ordering = ['-yaratilgan']


class BuyurtmaXizmat(models.Model):
    """Buyurtmaga biriktirilgan narxnoma xizmati (xodim narxnomadan tanlagan).

    Nom va narx biriktirilgan paytdagi qiymatda SAQLANADI: keyin narxnoma
    o'zgarsa yoki qator o'chirilsa ham, bajarilgan buyurtmadagi summa o'zgarmaydi.
    """
    USTUN_CHOICES = [('p', 'Profilaktika'), ('r', "Texnik ko'rik (reviziya)")]

    buyurtma = models.ForeignKey(Buyurtma, on_delete=models.CASCADE, related_name='xizmatlar')
    qator = models.ForeignKey('narxnoma.NarxnomaQator', on_delete=models.SET_NULL,
                              null=True, blank=True, related_name='+')
    nomi = models.CharField(max_length=400)
    ustun = models.CharField(max_length=1, choices=USTUN_CHOICES)
    # Ustunning shu paytdagi qisqa nomi (narxnomadan): «profilaktika», «reviziya» yoki bo'sh
    ustun_nomi = models.CharField(max_length=40, blank=True)
    soni = models.PositiveSmallIntegerField(default=1)
    narx_dan = models.BigIntegerField()
    narx_gacha = models.BigIntegerField(null=True, blank=True)
    qoshgan = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
                                null=True, blank=True, related_name='+')
    yaratilgan = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['id']
        verbose_name = 'Buyurtma xizmati'
        verbose_name_plural = 'Buyurtma xizmatlari'
        constraints = [models.UniqueConstraint(fields=['buyurtma', 'qator', 'ustun'],
                                               name='buyurtma_xizmat_yagona')]

    def __str__(self):
        return f"#{self.buyurtma_id} {self.nomi[:40]} × {self.soni}"


QONGIROQ_NATIJALARI = [
    ('qiziqdi', 'Qiziqish bildirdi'),
    ('ariza', 'Ariza olindi'),
    ('keyinroq', "Keyinroq qo'ng'iroq qilish"),
    ('rad', 'Rad etdi'),
    ('javob_yoq', 'Javob bermadi'),
]
SHAXS_CHOICES = [
    ('yuridik', 'Yuridik shaxs / tashkilot'),
    ('jismoniy', 'Jismoniy shaxs'),
]


class Qongiroq(models.Model):
    """Call center xodimining chiquvchi qo'ng'irog'i: kompaniya xizmatlarini taklif qilish.

    Faqat qayd (jurnal): kim bilan gaplashildi, natija nima, qachon qayta qo'ng'iroq qilinadi.
    Ariza olingan bo'lsa, u alohida `Buyurtma` sifatida kiritiladi."""

    operator = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True,
                                 blank=True, related_name='qongiroqlar', verbose_name='Operator')
    shaxs = models.CharField(max_length=10, choices=SHAXS_CHOICES, verbose_name='Kim')
    nomi = models.CharField(max_length=150, verbose_name='Tashkilot yoki shaxs nomi')
    telefon = models.CharField(max_length=20, verbose_name='Telefon')
    natija = models.CharField(max_length=10, choices=QONGIROQ_NATIJALARI, verbose_name='Natija')
    izoh = models.CharField(max_length=300, blank=True, verbose_name='Izoh')
    qayta_sana = models.DateField(null=True, blank=True, verbose_name="Qayta qo'ng'iroq sanasi")
    yaratilgan = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        verbose_name = "Chiquvchi qo'ng'iroq"
        verbose_name_plural = "Chiquvchi qo'ng'iroqlar"
        ordering = ['-yaratilgan']

    def __str__(self):
        return f"{self.nomi} — {self.get_natija_display()}"
