"""Xizmatlar narxnomasi (hujjat shaklidagi narxlar ro'yxati).

Katalogdagi mahsulot narxlaridan (apps.katalog.KatalogNarx) farqi: bu yerda
har qatorda IKKI narx ustuni bor (profilaktika va texnik ko'rik/reviziya),
narx esa oraliq bo'lishi mumkin (masalan «210 000 – 330 000») yoki matn
(«ish hajmi va kelishuv asosida»).

Narxlarni administrator boshqaruv panelidan o'zgartiradi, xodimlar portalida
esa faqat ko'rishadi. Har o'zgarish Faoliyat jurnaliga yoziladi.
"""
from django.db import models


#  Xizmat tarmoqlari. Tarmoq narxnomaga TEGISHLI: narxlar tarmoqqa qarab farq qiladi.
#  Buyurtma o'z tarmog'ini oladi (`Buyurtma.tarmoq`) va faqat shu tarmoq
#  narxnomalaridan xizmat tanlanadi; tushum tarmoq va bo'limni tanlangan ish
#  turidan (yoki buyurtmadan) meros qiladi — hisobotlar tarmoq bo'yicha ajraladi.
TARMOQ_CHOICES = [
    ('ulgurji', 'Ulgurji (sanoat, kichik va o\'rta biznes)'),
    ('aholi', 'Aholi'),
]
BOLIM_CHOICES = [
    ('buyurtma', 'Buyurtma asosida'),
    ('profilaktika', "Profilaktika va texnik ko'rik"),
    ('ornatish', "Yangi jihoz o'rnatib ishga tushirish"),
    ('metrologiya', 'Metrologiya xizmatlari'),
]
# Saytdagi Metrologiya bo'limining qaysi xizmatida narx ko'rinishi (qator darajasida)
SAYT_XIZMAT_CHOICES = [
    ('', "Saytda ko'rsatilmaydi"),
    ('kalibrovka', 'Kalibrovka'),
    ('almashtirish', 'Almashtirish'),
    ('qiyoslov', "Davlat qiyoslov ko'rigi"),
]
TARMOQ_NOMI = dict(TARMOQ_CHOICES)
BOLIM_NOMI = dict(BOLIM_CHOICES)


class Narxnoma(models.Model):
    tarmoq = models.CharField(max_length=10, choices=TARMOQ_CHOICES, default='ulgurji', db_index=True)
    bolim = models.CharField(max_length=15, choices=BOLIM_CHOICES, default='profilaktika')
    tartib = models.PositiveSmallIntegerField(default=0, help_text="Ro'yxatdagi o'rni")
    sarlavha = models.CharField(max_length=300)
    tavsif = models.CharField(max_length=300, blank=True)
    amal_qiladi = models.DateField(null=True, blank=True, verbose_name='Amal qilish sanasi')
    # Narx ustunlari. 2-ustun bo'sh bo'lsa, narxnomada faqat bitta narx bor
    # (masalan «Buyurtma asosida» yoki «O'rnatish va ishga tushirish»).
    ustun1 = models.CharField(max_length=200, verbose_name='1-narx ustuni nomi')
    ustun1_qisqa = models.CharField(
        max_length=40, blank=True,
        help_text="Tanlangan xizmat yonida ko'rinadi, masalan «profilaktika». Bo'sh bo'lsa ko'rsatilmaydi")
    ustun2 = models.CharField(max_length=200, blank=True, verbose_name='2-narx ustuni nomi')
    ustun2_qisqa = models.CharField(max_length=40, blank=True)
    eslatma = models.TextField(blank=True)
    faol = models.BooleanField(default=True)
    yangilangan = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Narxnoma'
        verbose_name_plural = 'Narxnomalar'
        ordering = ['tartib', 'id']
        constraints = [models.UniqueConstraint(fields=['tarmoq', 'bolim'], name='narxnoma_tarmoq_bolim_yagona')]

    def __str__(self):
        return f'{self.tarmoq_nomi} — {self.bolim_nomi}'

    @property
    def tarmoq_nomi(self):
        return TARMOQ_NOMI.get(self.tarmoq, self.tarmoq)

    @property
    def bolim_nomi(self):
        return BOLIM_NOMI.get(self.bolim, self.bolim)

    def ustun_qisqa(self, ustun):
        """'p' / 'r' ustunining qisqa nomi (bo'sh bo'lishi mumkin)."""
        return self.ustun1_qisqa if ustun == 'p' else self.ustun2_qisqa

    def ustun_bormi(self, ustun):
        return bool(self.ustun1) if ustun == 'p' else bool(self.ustun2)


class NarxnomaQator(models.Model):
    narxnoma = models.ForeignKey(Narxnoma, on_delete=models.CASCADE, related_name='qatorlar')
    tartib = models.PositiveIntegerField(help_text='Hujjatdagi tartib raqami (№)')
    nomi = models.CharField(max_length=400)
    # 1-ustun (profilaktika). Bitta narx bo'lsa faqat `p_dan`; oraliq bo'lsa `p_dan` va `p_gacha`
    p_dan = models.BigIntegerField(null=True, blank=True)
    p_gacha = models.BigIntegerField(null=True, blank=True)
    # 2-ustun (texnik ko'rik / reviziya)
    r_dan = models.BigIntegerField(null=True, blank=True)
    r_gacha = models.BigIntegerField(null=True, blank=True)
    # Raqam o'rnida matn kerak bo'lsa («ish hajmi va kelishuv asosida»)
    izoh = models.CharField(max_length=255, blank=True)
    # Faqat «Metrologiya» narxnomalari uchun: shu qator saytdagi qaysi xizmat oynasida ko'rinadi.
    # Bo'sh bo'lsa — saytda chiqmaydi (xodimlar portalida esa avvalgidek ko'rinadi).
    sayt_xizmat = models.CharField(
        max_length=20, blank=True, default='', choices=SAYT_XIZMAT_CHOICES,
        verbose_name="Saytdagi xizmat",
        help_text="Metrologiya narxnomasi: narx saytning qaysi xizmat oynasida ko'rinadi")
    faol = models.BooleanField(default=True)
    yangilangan = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Narxnoma qatori'
        verbose_name_plural = 'Narxnoma qatorlari'
        ordering = ['tartib', 'id']

    def __str__(self):
        return f"{self.tartib}. {self.nomi[:60]}"
