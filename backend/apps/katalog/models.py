import os

from django.conf import settings
from django.core.files.storage import FileSystemStorage
from django.db import models

# ──────────────────────────────────────────────────────────────
#  Marketing saytidagi (index.html) katalog mahsulotlarining narxi.
#  Mahsulotlar ro'yxati index.html dagi KAT_DATA da turadi — bu yerda
#  faqat narx saqlanadi, admin uni istalgan vaqtda o'zgartira oladi.
#  Bog'lanish `kalit` orqali: KAT_DATA item.kalit === KatalogNarx.kalit
#
#  Diqqat: bu do'kon mahsulotlari (xaridlar.Xarid) bilan aralashmasin —
#  u yerda narx buyurtma qatorida saqlanadi.
# ──────────────────────────────────────────────────────────────

#  Bo'lim kalitlari index.html dagi KAT_DATA kalitlari bilan AYNAN bir xil.
#  Yangi bo'lim qo'shsangiz — ikkala joyda ham bir xil nom bilan qo'shing.
KATEGORIYA_CHOICES = [
    ('quvur',   'Quvurlar va fitinglar'),
    ('hisob',   'Gaz hisoblagichlari'),
    ('ventil',  'Ventillar va kranlar'),
    ('gorelka', 'Gorelkalar va gaz jihozlari'),
]

BOLIMLAR = [k for k, _ in KATEGORIYA_CHOICES]


class KatalogNarx(models.Model):
    kalit = models.SlugField(
        max_length=80, unique=True, db_index=True,
        help_text="index.html dagi KAT_DATA item.kalit bilan bir xil bo'lishi shart"
    )
    kategoriya = models.CharField(max_length=20, choices=KATEGORIYA_CHOICES, db_index=True)
    nomi = models.CharField(max_length=200,
                            help_text="Admin panelda tanish bo'lishi uchun mahsulot nomi")

    narx = models.BigIntegerField(default=0, help_text="So'mda. 0 — narx ko'rsatilmaydi")
    birlik = models.CharField(max_length=20, default='dona',
                              help_text="dona / m/p / to'plam / rulon")
    # Narx o'rniga matn ko'rsatish kerak bo'lsa (masalan "So'rovnoma")
    sorovnoma = models.BooleanField(
        default=False, verbose_name="Narx o'rniga «So'rovnoma» ko'rsatilsin")

    faol = models.BooleanField(default=True, help_text="O'chirilsa saytda eski narx qoladi")
    yangilangan = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Katalog narxi'
        verbose_name_plural = 'Katalog narxlari'
        ordering = ['kategoriya', 'nomi']

    def __str__(self):
        return f"{self.nomi} — {self.narx_matni()}"

    def narx_matni(self):
        """Saytda ko'rinadigan matn: «850 000 so'm» yoki «So'rovnoma»."""
        if self.sorovnoma or not self.narx:
            return "So'rovnoma"
        return f"{self.narx:,}".replace(',', ' ') + " so'm"


# ──────────────────────────────────────────────────────────────
#  Jihoz pasporti va sertifikati
#
#  Fayllar MEDIA_ROOT dan TASHQARIDA — `hujjatlar_maxfiy/` papkasida
#  saqlanadi, ya'ni ularga to'g'ridan-to'g'ri URL orqali kirib bo'lmaydi.
#  Sayt faqat 5 daqiqa amal qiladigan imzolangan havola oladi
#  (apps.katalog.views.hujjat_ochish), rasm esa suv belgisi bilan beriladi.
# ──────────────────────────────────────────────────────────────

HUJJAT_TURI_CHOICES = [
    ('sertifikat', 'Sertifikat'),
    ('pasport', 'Texnik pasport'),
    ('boshqa', 'Boshqa hujjat'),
]

MAXFIY_XOTIRA = FileSystemStorage(
    location=os.path.join(settings.BASE_DIR.parent, 'hujjatlar_maxfiy')
)


class KatalogHujjat(models.Model):
    kalit = models.SlugField(
        max_length=80, db_index=True,
        help_text="Mahsulot kaliti — KatalogNarx.kalit bilan bir xil"
    )
    tur = models.CharField(max_length=20, choices=HUJJAT_TURI_CHOICES, default='sertifikat')
    nom = models.CharField(max_length=200, help_text='Saytda ko\'rinadigan nom')
    fayl = models.FileField(
        storage=MAXFIY_XOTIRA, upload_to='',
        help_text='PDF yoki rasm (JPG/PNG). Fayl maxfiy papkaga saqlanadi.'
    )
    faol = models.BooleanField(default=True)
    yuklangan = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Jihoz hujjati (sertifikat/pasport)'
        verbose_name_plural = 'Jihoz hujjatlari (sertifikat/pasport)'
        ordering = ['kalit', 'tur']

    def __str__(self):
        return f"{self.nom} ({self.get_tur_display()})"

    @property
    def rasmmi(self):
        return self.fayl.name.lower().endswith(('.jpg', '.jpeg', '.png', '.webp'))


# ──────────────────────────────────────────────────────────────
#  Katalog mediasi (mahsulot rasmlari va videolari)
#
#  Fayllar MEDIA_ROOT ga emas, loyiha ildizidagi `images/` papkasiga
#  saqlanadi — index.html allaqachon shu yo'llarga («images/jihozlar/...»)
#  murojaat qiladi va urls.py uni serve qiladi. Shu tufayli admin orqali
#  yuklangan fayl ham, qo'lda qo'yilgan fayl ham bir xil ishlaydi.
#
#  Diqqat: bu marketing sayti katalogi uchun. Do'kon mahsulotlari
#  (xaridlar.Xarid) mediasi bilan aralashmasin.
# ──────────────────────────────────────────────────────────────

RASM_KENGAYTMALARI = ('.jpg', '.jpeg', '.png', '.webp')
VIDEO_KENGAYTMALARI = ('.mp4', '.webm')

RASMLAR_XOTIRASI = FileSystemStorage(
    location=os.path.join(settings.BASE_DIR.parent, 'images'),
    base_url='/images/',
)


class KatalogMedia(models.Model):
    kalit = models.SlugField(
        max_length=80, db_index=True,
        help_text="Mahsulot kaliti — KatalogNarx.kalit va KAT_DATA item.kalit bilan bir xil"
    )
    bolim = models.CharField(
        max_length=20, choices=KATEGORIYA_CHOICES, db_index=True,
        verbose_name="Bo'lim",
        help_text="Mahsulot qaysi katalog bo'limida ko'rinadi"
    )
    fayl = models.FileField(
        storage=RASMLAR_XOTIRASI, upload_to='jihozlar',
        help_text="Rasm (JPG/PNG/WEBP) yoki video (MP4/WEBM). "
                  "Fayl loyihaning images/jihozlar/ papkasiga tushadi."
    )
    tartib = models.PositiveIntegerField(
        default=10,
        help_text="Kichik raqam oldinda turadi. Birinchi rasm — mahsulotning "
                  "eng yaxshi ko'rinishi bo'lsin (grid kartasida o'sha chiqadi)."
    )
    faol = models.BooleanField(default=True, help_text="O'chirilsa saytda ko'rinmaydi")
    yuklangan = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Katalog mediasi (rasm/video)'
        verbose_name_plural = 'Katalog mediasi (rasm/video)'
        # Video har doim oxirida: `videomi` DB da yo'q, shuning uchun
        # saralash view/admin tomonda `tartib_kaliti()` bilan yakunlanadi.
        ordering = ['bolim', 'kalit', 'tartib', 'id']

    def __str__(self):
        return f"{self.kalit} — {os.path.basename(self.fayl.name)}"

    @property
    def videomi(self):
        return self.fayl.name.lower().endswith(VIDEO_KENGAYTMALARI)

    @property
    def rasmmi(self):
        return self.fayl.name.lower().endswith(RASM_KENGAYTMALARI)

    @property
    def yol(self):
        """index.html kutadigan nisbiy yo'l: «images/jihozlar/ugop-16-1.jpg»."""
        return 'images/' + self.fayl.name.replace('\\', '/')

    def tartib_kaliti(self):
        """Saralash kaliti — video har doim rasmlardan keyin turadi."""
        return (1 if self.videomi else 0, self.tartib, self.id or 0)

    def clean(self):
        from django.core.exceptions import ValidationError
        nom = (self.fayl.name or '').lower()
        if not nom.endswith(RASM_KENGAYTMALARI + VIDEO_KENGAYTMALARI):
            raise ValidationError({
                'fayl': "Faqat rasm (JPG/PNG/WEBP) yoki video (MP4/WEBM) yuklash mumkin."
            })
