import secrets

from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.db import models
from django.utils import timezone


def kirish_kodi_yasa(uzunlik=6):
    """Xodim uchun takrorlanmaydigan kirish kodi.

    `secrets` ishlatiladi (`random` emas): kod — parolning o'rnini bosadi,
    shuning uchun taxmin qilib bo'lmaydigan bo'lishi kerak. Chalkashadigan
    belgilar (0/O, 1/I) chiqarib tashlangan — kod og'zaki aytiladi.
    """
    ALIFBO = '23456789ABCDEFGHJKLMNPQRSTUVWXYZ'
    return ''.join(secrets.choice(ALIFBO) for _ in range(uzunlik))


# Hududlar ro'yxati alohida faylda — u yerda 14 ta viloyat va 203 ta
# tuman/shahar viloyatlar bo'yicha guruhlangan holda turadi.
from .hududlar import HUDUDLAR, TUMANLAR  # noqa: F401  (eski nom saqlanadi)

ROL_CHOICES = [
    ('admin', 'Admin'),
    ('mijoz', 'Mijoz'),
    ('xodim', 'Xodim'),
]

HOLAT_CHOICES = [
    ('faol', 'Faol'),
    ('nofaol', 'Nofaol'),
]

# Xodim lavozimlari — xodimlar portalida ko'rsatiladi
LAVOZIM_CHOICES = [
    ('Montaj ustasi', 'Montaj ustasi'),
    ('Katta montaj ustasi', 'Katta montaj ustasi'),
    ('Loyihachi muhandis', 'Loyihachi muhandis'),
    ('Metrolog', 'Metrolog'),
    ('Servis operatori', 'Servis operatori'),
    ('Menejer', 'Menejer'),
]


class FoydalanuvchiManager(BaseUserManager):
    def create_user(self, telefon, password=None, **extra_fields):
        if not telefon:
            raise ValueError('Telefon raqam kiritilishi shart')
        user = self.model(telefon=telefon, **extra_fields)
        if password:
            user.set_password(password)
        else:
            user.set_unusable_password()
        user.save(using=self._db)
        return user

    def create_superuser(self, telefon, password=None, **extra_fields):
        extra_fields.setdefault('rol', 'admin')
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        return self.create_user(telefon, password, **extra_fields)


MULK_CHOICES = [
    ('uy', 'Xususiy uy'),
    ('kvartira', 'Kvartira'),
    ('korxona', 'Korxona / tashkilot'),
]


class Foydalanuvchi(AbstractBaseUser, PermissionsMixin):
    telefon = models.CharField(max_length=20, unique=True)
    ism = models.CharField(max_length=100, blank=True)
    manzil = models.CharField(max_length=255, blank=True)
    # ---- Joylashuv ----
    # Viloyat va tuman ro'yxatdan TANLANADI (hududlar.py), mahalla/ko'cha esa
    # qo'lda yoziladi — ular juda ko'p va o'zgaruvchan, ro'yxat tuzib
    # bo'lmaydi. `choices` ataylab qo'yilmagan: tekshiruv forma va serializer
    # darajasida bo'ladi, model esa eski va qo'lda kiritilgan qiymatlarni ham
    # saqlay olishi kerak.
    viloyat = models.CharField(max_length=50, blank=True)
    tuman = models.CharField(max_length=50, blank=True)
    mahalla = models.CharField(max_length=120, blank=True,
                               verbose_name="Mahalla / ko'cha")
    # Mijoz profili — kabinetda to'ldiriladi
    qoshimcha_telefon = models.CharField(max_length=20, blank=True)
    email = models.EmailField(blank=True)
    mulk_turi = models.CharField(max_length=15, choices=MULK_CHOICES, blank=True)
    moljal = models.CharField(max_length=255, blank=True, verbose_name="Mo'ljal")
    # Xodim profili — faqat Django admin panelida to'ldiriladi
    # `choices` yo'q — yuqoridagi `tuman` bilan bir xil sabab: yangi lavozim
    # paydo bo'lishi mumkin, LAVOZIM_CHOICES esa taklif ro'yxati bo'lib qoladi.
    lavozim = models.CharField(max_length=100, blank=True)
    # Xodim portalga TELEFON + shu KOD bilan kiradi (parol emas). Kodni admin
    # beradi va istalgan vaqtda yangilaydi. Mijozlarda bu maydon bo'sh turadi —
    # ular SMS orqali bir martalik kod bilan kiradi.
    kirish_kodi = models.CharField(max_length=12, blank=True, db_index=True,
                                   verbose_name='Kirish kodi')
    tabel_raqam = models.CharField(max_length=20, blank=True, verbose_name='Tabel raqami')
    ishga_kirgan = models.DateField(null=True, blank=True, verbose_name='Ishga kirgan sana')
    rol = models.CharField(max_length=10, choices=ROL_CHOICES, default='mijoz')
    holat = models.CharField(max_length=10, choices=HOLAT_CHOICES, default='faol')
    is_staff = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    yaratilgan = models.DateTimeField(auto_now_add=True)

    USERNAME_FIELD = 'telefon'
    REQUIRED_FIELDS = []

    objects = FoydalanuvchiManager()

    class Meta:
        verbose_name = 'Foydalanuvchi'
        verbose_name_plural = 'Foydalanuvchilar'

    def __str__(self):
        return f"{self.ism or self.telefon} ({self.rol})"

    @property
    def tuman_nomi(self):
        return self.tuman


class XodimManager(FoydalanuvchiManager):
    def get_queryset(self):
        return super().get_queryset().filter(rol='xodim')


class Xodim(Foydalanuvchi):
    """Admin panelida xodimlarni alohida ro'yxat sifatida ko'rsatish uchun.
    Yangi jadval yaratmaydi — Foydalanuvchi jadvalining rol='xodim' qismi.
    Xodimlar faqat shu yerdan kiritiladi, portalda ro'yxatdan o'tish yo'q."""

    objects = XodimManager()

    class Meta:
        proxy = True
        verbose_name = 'Xodim'
        verbose_name_plural = 'Xodimlar'

    def save(self, *args, **kwargs):
        self.rol = 'xodim'
        super().save(*args, **kwargs)


AUDIT_AMAL_CHOICES = [
    ('kirish', 'Tizimga kirdi'),
    ('kirish_xato', 'Noto\'g\'ri parol'),
    ('kirish_blok', 'Hisob bloklandi'),
    ('chiqish', 'Tizimdan chiqdi'),
    ('xodim_qoshildi', 'Yangi xodim qo\'shildi'),
    ('xodim_holat', 'Xodim holati o\'zgardi'),
    ('xodim_kod', 'Xodimga yangi kod berildi'),
    ('ariza_tayinlandi', 'Ariza xodimga tayinlandi'),
    ('ruxsat_rad', 'Ruxsat rad etildi'),
    ('admin_ochildi', 'Bloklangan hisob qayta faollashtirildi'),
]


class AuditYozuv(models.Model):
    """Boshqaruv panelidagi har bir muhim amal shu yerga yoziladi.

    Maqsad — "kim, qachon, nima qildi" savoliga javob. Yozuvlar HECH QACHON
    o'zgartirilmaydi va o'chirilmaydi (Django admin panelida ham faqat
    o'qish uchun), aks holda jurnalning ma'nosi qolmaydi.

    `kim` o'chirilgan foydalanuvchida NULL bo'lib qoladi, shuning uchun ism va
    telefon alohida matn sifatida ham saqlanadi — jurnal o'zi to'liq qoladi.
    """
    kim = models.ForeignKey('Foydalanuvchi', on_delete=models.SET_NULL,
                            null=True, blank=True, related_name='audit_yozuvlar')
    kim_ism = models.CharField(max_length=120, blank=True)
    kim_telefon = models.CharField(max_length=30, blank=True)
    amal = models.CharField(max_length=30, choices=AUDIT_AMAL_CHOICES, db_index=True)
    tafsilot = models.CharField(max_length=255, blank=True)
    ip = models.GenericIPAddressField(null=True, blank=True)
    vaqt = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        verbose_name = 'Audit yozuvi'
        verbose_name_plural = 'Audit jurnali'
        ordering = ['-vaqt']

    def __str__(self):
        return f"{self.vaqt:%d.%m.%Y %H:%M} — {self.kim_ism or self.kim_telefon}: {self.get_amal_display()}"


def audit_yoz(request, amal, tafsilot='', user=None):
    """Audit yozuvini qo'shadi. Jurnal yozilmagani asosiy amalni buzmasligi
    kerak — shuning uchun har qanday xatolik yutiladi."""
    try:
        kim = user if user is not None else getattr(request, 'user', None)
        if kim is not None and not getattr(kim, 'is_authenticated', False):
            kim = None
        ip = None
        if request is not None:
            ip = (request.META.get('HTTP_X_FORWARDED_FOR', '').split(',')[0].strip()
                  or request.META.get('REMOTE_ADDR'))
        AuditYozuv.objects.create(
            kim=kim,
            kim_ism=getattr(kim, 'ism', '') or '',
            kim_telefon=getattr(kim, 'telefon', '') or '',
            amal=amal,
            tafsilot=tafsilot[:255],
            ip=ip or None,
        )
    except Exception:
        pass


class OtpKod(models.Model):
    telefon = models.CharField(max_length=20)
    kod = models.CharField(max_length=6)
    yaratilgan = models.DateTimeField(auto_now_add=True)
    ishlatildi = models.BooleanField(default=False)

    class Meta:
        verbose_name = 'OTP Kod'
        ordering = ['-yaratilgan']

    def __str__(self):
        return f"{self.telefon} — {self.kod}"

    def muddati_utganmi(self):
        from django.conf import settings
        limit = timezone.now() - timezone.timedelta(minutes=getattr(settings, 'OTP_EXPIRE_MINUTES', 5))
        return self.yaratilgan < limit
