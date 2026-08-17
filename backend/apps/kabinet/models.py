"""Mijoz kabineti modellari.

Bu yerda mijozning o'z ma'lumotlari saqlanadi: obyektlari (uy, dala hovli,
ofis), ulardagi uskunalar va hisoblagichlar, hujjatlar, bildirishnomalar,
sharhlar va yordam markazi murojaatlari.

Diqqat: xizmat buyurtmasi — `buyurtmalar.Buyurtma`, do'kon xaridi esa
`xaridlar.Xarid`. Bu ikkisi bu yerda takrorlanmaydi, faqat bog'lanadi.
"""

from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _
from django.utils import timezone


OBYEKT_TURI_CHOICES = [
    ('uy', _('Xususiy uy')),
    ('kvartira', _('Kvartira')),
    ('dala_hovli', _('Dala hovli')),
    ('ofis', _('Ofis')),
    ('korxona', _('Korxona / tashkilot')),
]

USKUNA_TURI_CHOICES = [
    ('rezervuar', _('Rezervuar')),
    ('hisoblagich', _('Hisoblagich')),
    ('qozon', _('Qozon')),
    ('gorelka', _('Gorelka')),
    ('ventil', _('Ventil / reduktor')),
    ('boshqa', _('Boshqa')),
]


class Obyekt(models.Model):
    """Mijozning xizmat ko'rsatiladigan manzili (uy, dala hovli, ofis...)."""
    mijoz = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='obyektlar'
    )
    nom = models.CharField(max_length=120, verbose_name='Obyekt nomi')
    turi = models.CharField(max_length=20, choices=OBYEKT_TURI_CHOICES, default='uy')
    # Viloyat/tuman ro'yxatdan tanlanadi, mahalla qo'lda yoziladi —
    # apps/auth_app/hududlar.py ga qarang.
    viloyat = models.CharField(max_length=50, blank=True)
    tuman = models.CharField(max_length=50, blank=True)
    mahalla = models.CharField(max_length=120, blank=True,
                               verbose_name="Mahalla / ko'cha")
    manzil = models.CharField(max_length=255)
    moljal = models.CharField(max_length=255, blank=True, verbose_name="Mo'ljal")
    rezervuar_hajmi = models.IntegerField(
        null=True, blank=True, verbose_name='Rezervuar hajmi (litr)'
    )
    izoh = models.TextField(blank=True)
    asosiy = models.BooleanField(default=False, verbose_name='Asosiy obyekt')
    yaratilgan = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Obyekt'
        verbose_name_plural = 'Obyektlar'
        ordering = ['-asosiy', 'nom']

    def __str__(self):
        return f"{self.nom} — {self.manzil}"

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        # Bitta mijozda faqat bitta asosiy obyekt bo'ladi
        if self.asosiy:
            Obyekt.objects.filter(mijoz=self.mijoz).exclude(pk=self.pk).update(asosiy=False)


class Uskuna(models.Model):
    """Obyektga o'rnatilgan jihoz — rezervuar, qozon, gorelka va h.k."""
    obyekt = models.ForeignKey(Obyekt, on_delete=models.CASCADE, related_name='uskunalar')
    turi = models.CharField(max_length=20, choices=USKUNA_TURI_CHOICES, default='boshqa')
    nom = models.CharField(max_length=120)
    model = models.CharField(max_length=120, blank=True)
    seriya_raqam = models.CharField(max_length=80, blank=True)
    hajm = models.CharField(max_length=60, blank=True, verbose_name="Hajm / quvvat")
    ornatilgan_sana = models.DateField(null=True, blank=True)

    class Meta:
        verbose_name = 'Uskuna'
        verbose_name_plural = 'Uskunalar'
        ordering = ['turi', 'nom']

    def __str__(self):
        return f"{self.nom} ({self.obyekt.nom})"


HISOBLAGICH_TURI_CHOICES = [
    ('mexanik', _('Mexanik')),
    ('elektron', _('Elektron')),
    ('smart', _('Smart (masofadan)')),
]

HISOBLAGICH_HOLAT_CHOICES = [
    ('faol', _('Faol')),
    ('nosoz', _('Nosoz')),
    ('almashtirildi', _('Almashtirildi')),
]

# Keyingi tekshiruvgacha shu kundan kam qolsa — mijozga eslatma yuboriladi
TEKSHIRUV_ESLATMA_KUN = 30


class Hisoblagich(models.Model):
    """Gaz hisoblagichi va uning davlat tekshiruvi (kalibrovka) muddati."""
    obyekt = models.ForeignKey(
        Obyekt, on_delete=models.CASCADE, related_name='hisoblagichlar'
    )
    turi = models.CharField(max_length=20, choices=HISOBLAGICH_TURI_CHOICES, default='mexanik')
    markasi = models.CharField(max_length=120, blank=True)
    seriya_raqam = models.CharField(max_length=80)
    ornatilgan_sana = models.DateField(null=True, blank=True)
    oxirgi_tekshiruv = models.DateField(null=True, blank=True)
    keyingi_tekshiruv = models.DateField(
        null=True, blank=True, verbose_name='Keyingi davlat tekshiruvi'
    )
    oxirgi_korsatkich = models.IntegerField(null=True, blank=True, verbose_name="Oxirgi ko'rsatkich, m³")
    holat = models.CharField(max_length=20, choices=HISOBLAGICH_HOLAT_CHOICES, default='faol')

    class Meta:
        verbose_name = 'Hisoblagich'
        verbose_name_plural = 'Hisoblagichlar'
        ordering = ['keyingi_tekshiruv']

    def __str__(self):
        return f"{self.seriya_raqam} — {self.obyekt.nom}"

    @property
    def kun_qoldi(self):
        """Keyingi tekshiruvgacha necha kun qolgani. Manfiy — muddati o'tgan."""
        if not self.keyingi_tekshiruv:
            return None
        return (self.keyingi_tekshiruv - timezone.localdate()).days

    @property
    def muddat_holati(self):
        kun = self.kun_qoldi
        if kun is None:
            return 'nomalum'
        if kun < 0:
            return 'otgan'
        if kun <= TEKSHIRUV_ESLATMA_KUN:
            return 'yaqin'
        return 'yaxshi'


HUJJAT_TURI_CHOICES = [
    ('shartnoma', _('Shartnoma')),
    ('sertifikat', _('Metrologik sertifikat')),
    ('hisobot', _('Texnik hisobot')),
    ('faktura', _('Hisob-faktura')),
    ('boshqa', _('Boshqa')),
]


class Hujjat(models.Model):
    """Mijozga tegishli hujjat — kabinetdan yuklab olinadi.
    Odatda admin panelidan yuklanadi, mijoz faqat ko'radi."""
    mijoz = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='hujjatlar'
    )
    obyekt = models.ForeignKey(
        Obyekt, on_delete=models.SET_NULL, null=True, blank=True, related_name='hujjatlar'
    )
    turi = models.CharField(max_length=20, choices=HUJJAT_TURI_CHOICES, default='boshqa')
    nom = models.CharField(max_length=200)
    fayl = models.FileField(upload_to='kabinet_hujjatlar/')
    sana = models.DateField(default=timezone.localdate)
    izoh = models.CharField(max_length=255, blank=True)
    yaratilgan = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Hujjat'
        verbose_name_plural = 'Hujjatlar'
        ordering = ['-sana', '-id']

    def __str__(self):
        return f"{self.nom} — {self.mijoz}"


BILDIRISHNOMA_TURI_CHOICES = [
    ('buyurtma', _('Buyurtma holati')),
    ('tolov', _("To'lov")),
    ('texnik', _("Texnik ko'rik")),
    ('umumiy', _('Umumiy')),
]


class Bildirishnoma(models.Model):
    """Kabinetdagi bildirishnomalar — buyurtma holati, to'lov muddati,
    texnik ko'rik eslatmasi. SMS xabarlardan alohida (SmsXabar — SMS tarixi)."""
    mijoz = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='bildirishnomalar'
    )
    turi = models.CharField(max_length=20, choices=BILDIRISHNOMA_TURI_CHOICES, default='umumiy')
    sarlavha = models.CharField(max_length=200)
    matn = models.TextField(blank=True)
    bolim = models.CharField(
        max_length=40, blank=True,
        verbose_name="Kabinet bo'limi", help_text='Bosilganda ochiladigan bo\'lim kodi'
    )
    oqildi = models.BooleanField(default=False)
    yaratilgan = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Bildirishnoma'
        verbose_name_plural = 'Bildirishnomalar'
        ordering = ['-yaratilgan']

    def __str__(self):
        return f"{self.sarlavha} — {self.mijoz}"


class Sharh(models.Model):
    """Yakunlangan xizmatga qoldirilgan baho va sharh."""
    mijoz = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='sharhlar'
    )
    buyurtma = models.OneToOneField(
        'buyurtmalar.Buyurtma', on_delete=models.CASCADE,
        related_name='sharh', null=True, blank=True
    )
    baho = models.PositiveSmallIntegerField(default=5, verbose_name='Baho (1–5)')
    matn = models.TextField(blank=True)
    yaratilgan = models.DateTimeField(auto_now_add=True)
    yangilangan = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Sharh'
        verbose_name_plural = 'Sharhlar'
        ordering = ['-yaratilgan']

    def __str__(self):
        return f"{self.baho}★ — {self.mijoz}"


MUROJAAT_HOLAT_CHOICES = [
    ('ochiq', _('Ochiq')),
    ('javob', _('Javob berildi')),
    ('yopiq', _('Yopilgan')),
]


class Murojaat(models.Model):
    """Yordam markazi — operator bilan yozishma."""
    mijoz = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='murojaatlar'
    )
    mavzu = models.CharField(max_length=200)
    holat = models.CharField(max_length=20, choices=MUROJAAT_HOLAT_CHOICES, default='ochiq')
    yaratilgan = models.DateTimeField(auto_now_add=True)
    yangilangan = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Murojaat'
        verbose_name_plural = 'Murojaatlar (yordam markazi)'
        ordering = ['-yangilangan']

    def __str__(self):
        return f"#{self.id} {self.mavzu} — {self.holat}"


class MurojaatXabar(models.Model):
    murojaat = models.ForeignKey(Murojaat, on_delete=models.CASCADE, related_name='xabarlar')
    kim = models.CharField(
        max_length=10, default='mijoz',
        choices=[('mijoz', 'Mijoz'), ('operator', 'Operator')]
    )
    matn = models.TextField()
    yaratilgan = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Murojaat xabari'
        verbose_name_plural = 'Murojaat xabarlari'
        ordering = ['yaratilgan']

    def __str__(self):
        return f"{self.kim}: {self.matn[:40]}"


class QongiroqSorovi(models.Model):
    """"Menga qo'ng'iroq qiling" so'rovi."""
    mijoz = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='qongiroq_sorovlari'
    )
    telefon = models.CharField(max_length=30)
    qulay_vaqt = models.CharField(max_length=100, blank=True)
    mavzu = models.CharField(max_length=200, blank=True)
    bajarildi = models.BooleanField(default=False)
    yaratilgan = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Qo'ng'iroq so'rovi"
        verbose_name_plural = "Qo'ng'iroq so'rovlari"
        ordering = ['-yaratilgan']

    def __str__(self):
        return f"{self.telefon} — {self.mavzu or 'umumiy'}"


class SavolJavob(models.Model):
    """Tez-tez so'raladigan savollar — kabinetning yordam bo'limida chiqadi."""
    savol = models.CharField(max_length=255)
    javob = models.TextField()
    tartib = models.IntegerField(default=0)
    faol = models.BooleanField(default=True)

    class Meta:
        verbose_name = 'Savol-javob (FAQ)'
        verbose_name_plural = 'Savol-javoblar (FAQ)'
        ordering = ['tartib', 'id']

    def __str__(self):
        return self.savol


class KabinetSozlama(models.Model):
    """Mijozning bildirishnoma tanlovlari."""
    mijoz = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='kabinet_sozlama'
    )
    sms_bildirishnoma = models.BooleanField(default=True)
    email_bildirishnoma = models.BooleanField(default=False)
    push_bildirishnoma = models.BooleanField(default=True)
    tekshiruv_eslatma = models.BooleanField(default=True, verbose_name="Texnik ko'rik eslatmasi")

    class Meta:
        verbose_name = 'Kabinet sozlamasi'
        verbose_name_plural = 'Kabinet sozlamalari'

    def __str__(self):
        return f"Sozlamalar — {self.mijoz}"
