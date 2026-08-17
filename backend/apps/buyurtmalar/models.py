from django.db import models
from django.conf import settings
from django.utils.translation import gettext_lazy as _

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
