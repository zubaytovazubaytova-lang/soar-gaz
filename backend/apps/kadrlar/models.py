"""Kadrlar bo'limi: kunlik ish hisoboti va xodimlar hujjatlari reestri.

Davomat (kim ishga keldi) alohida jadval emas — u `joylashuv.Smena` dan
hisoblanadi: xodim «Ishni boshlash» bossa, o'sha kuni keldi hisoblanadi.
"""
from django.conf import settings
from django.db import models
from django.utils import timezone

# Har bir xodimda bo'lishi shart bo'lgan hujjatlar (kalit, nomi). «boshqa» — majburiy emas.
# Ro'yxat o'zgarsa — faqat shu yerni tahrirlang (migratsiya kerak emas: `turi` erkin matn).
HUJJAT_TURLARI = [
    ('pasport', 'Pasport / ID nusxasi'),
    ('mehnat_daftarchasi', 'Mehnat daftarchasi'),
    ('mehnat_shartnomasi', 'Mehnat shartnomasi'),
    ('qabul_buyrugi', "Ishga qabul buyrug'i"),
    ('diplom', "Diplom / ma'lumot haqida hujjat"),
    ('tibbiy', "Tibbiy ko'rik"),
    ('yoriqnoma', "Xavfsizlik texnikasi yo'riqnomasi"),
    ('boshqa', 'Boshqa'),
]
HUJJAT_NOMI = dict(HUJJAT_TURLARI)
MAJBURIY_HUJJATLAR = [k for k, _ in HUJJAT_TURLARI if k != 'boshqa']


class KunlikHisobot(models.Model):
    """Xodimning kunlik hisoboti: bugun qayerda ishladi va nima ish qildi.
    Xodim o'z kabinetida kiritadi (shu kunning o'zini tahrirlay oladi);
    Kadrlar mutaxassisi hammaniki bo'yicha ko'radi."""

    xodim = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                              related_name='kunlik_hisobotlar', verbose_name='Xodim')
    sana = models.DateField(db_index=True, verbose_name='Sana')
    joy = models.CharField(max_length=200, verbose_name='Qayerda ishladi')
    ish = models.CharField(max_length=500, verbose_name='Qanday ish qildi')
    yaratilgan = models.DateTimeField(auto_now_add=True)
    yangilangan = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Kunlik hisobot'
        verbose_name_plural = 'Kunlik hisobotlar'
        ordering = ['-sana', 'xodim__ism']
        constraints = [models.UniqueConstraint(fields=['xodim', 'sana'], name='kunlik_hisobot_kuniga_bitta')]

    def __str__(self):
        return f"{self.xodim} — {self.sana:%d.%m.%Y}"


class XodimHujjati(models.Model):
    """Xodimning tayyor hujjati (reestr yozuvi). Faylning o'zi emas — hujjat
    tayyorligi, raqami va amal qilish muddati qayd etiladi."""

    xodim = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                              related_name='kadr_hujjatlari', verbose_name='Xodim')
    turi = models.CharField(max_length=30, choices=HUJJAT_TURLARI, verbose_name='Hujjat turi')
    raqami = models.CharField(max_length=60, blank=True, verbose_name='Raqami')
    sana = models.DateField(default=timezone.localdate, verbose_name='Tayyorlangan sana')
    amal_qiladi = models.DateField(null=True, blank=True, verbose_name='Amal qilish muddati (gacha)',
                                   help_text="Bo'sh qoldirilsa — muddatsiz")
    izoh = models.CharField(max_length=200, blank=True, verbose_name='Izoh')
    kiritgan = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True,
                                 blank=True, related_name='+', verbose_name='Kiritdi')
    yaratilgan = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Xodim hujjati'
        verbose_name_plural = 'Xodimlar hujjatlari'
        ordering = ['xodim__ism', 'turi', '-sana']

    # Muddati tugashiga shuncha kun qolganda «yaqin» deb belgilanadi
    OGOHLANTIRISH_KUN = 30

    @property
    def holat(self):
        """'muddatsiz' | 'amalda' | 'yaqin' | 'tugagan' (Sertifikat bilan bir xil mantiq)."""
        if self.amal_qiladi is None:
            return 'muddatsiz'
        qoldi = (self.amal_qiladi - timezone.localdate()).days
        if qoldi < 0:
            return 'tugagan'
        return 'yaqin' if qoldi <= self.OGOHLANTIRISH_KUN else 'amalda'

    def __str__(self):
        return f"{self.xodim}: {HUJJAT_NOMI.get(self.turi, self.turi)}"


KELMAGAN_SABABLARI = [
    ('sababsiz', 'Sababsiz'),
    ('kasal', 'Kasal'),
    ('tatil', "Ta'tilda"),
    ('ruxsat', 'Ruxsat bilan'),
    ('safar', 'Xizmat safarida'),
]
KELMAGAN_SABAB_NOMI = dict(KELMAGAN_SABABLARI)


class DavomatBelgisi(models.Model):
    """Kadrlar mutaxassisining QO'LDA qo'ygan davomat belgisi (keldi / kelmadi).

    Avtomatik davomat xodimning «Ishni boshlash» tugmasidan (`Smena`) hisoblanadi. Kadrlar mutaxassisi esa
    smenasiz ishlaydigan xodim uchun «keldi» belgilashi, yoki «kelmadi» deb sababini (kasal, ta'til...) yozishi mumkin.
    Qo'lda qo'yilgan belgi avtomatik natijadan USTUN turadi. Kuniga bitta belgi; kim va qachon qo'ygani saqlanadi."""

    xodim = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                              related_name='davomat_belgilari', verbose_name='Xodim')
    sana = models.DateField(db_index=True, verbose_name='Sana')
    holat = models.CharField(max_length=10, choices=[('keldi', 'Keldi'), ('kelmadi', 'Kelmadi')], verbose_name='Holat')
    sabab = models.CharField(max_length=10, choices=KELMAGAN_SABABLARI, blank=True, verbose_name='Kelmagan sababi')
    izoh = models.CharField(max_length=200, blank=True, verbose_name='Izoh')
    belgilagan = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
                                   related_name='+', verbose_name='Belgiladi')
    yangilangan = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Davomat belgisi'
        verbose_name_plural = 'Davomat belgilari'
        ordering = ['-sana', 'xodim__ism']
        constraints = [models.UniqueConstraint(fields=['xodim', 'sana'], name='davomat_belgisi_kuniga_bitta')]

    def __str__(self):
        return f"{self.xodim} — {self.sana:%d.%m.%Y}: {self.get_holat_display()}"
