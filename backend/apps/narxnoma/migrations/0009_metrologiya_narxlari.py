"""Metrologiya xizmatlari narxnomasi: ulgurji (qog'oz hujjat) va aholi (qo'lyozma yozuv).

Manba 1 — «Ulgurji iste'molchilarning gaz hisoblagichlariga barcha turdagi metrologik xizmatlar
ko'rsatish NARXNOMASI № 3/2025 (QQS bilan)»: 12 band, ulardan 11 va 12 aynan 6 va 7 ning takrori
bo'lgani uchun bir marta kiritildi (10 qator).
Manba 2 — qo'lyozma yozuv: aholi uchun faqat 3 ta narx (aloqaga chiqarish, kabel almashtirish,
modem o'rnatish). Qolgan xizmatlar uchun aholi narxi hujjatda yo'q — o'ylab topilmadi.

Amal qilish sanasi ATAYLAB kiritilmadi (`amal_qiladi` bo'sh).

Migratsiya narxlarni FAQAT BIR MARTA kiritadi: narxnoma allaqachon mavjud bo'lsa (administrator
tahrir qilgan bo'lishi mumkin), hech narsa ustidan yozilmaydi.
"""
from django.db import migrations

ULGURJI_SARLAVHA = ("Ulgurji iste'molchilarning gaz hisoblagichlariga barcha turdagi metrologik "
                    "xizmatlar ko'rsatish NARXNOMASI № 3/2025 (QQS bilan)")
ULGURJI_ESLATMA = "\n".join([
    "Narxlar QQS bilan.",
    "Narxnomada gaz jihoziga qo'yiladigan material va ehtiyot qismlar inobatga olinmagan. "
    "Jihozga qo'yiladigan material xarajati va ehtiyot qism buyurtmachi, ya'ni iste'molchi tomonidan "
    "qo'shimcha tarzda to'lab beriladi.",
    "Xodimning oylik ish haqi hamda eng kam mehnatga haq to'lash miqdori ko'tarilganda narxnoma "
    "o'zgartiriladi.",
])
AHOLI_SARLAVHA = "Gaz hisoblagichlariga metrologik xizmatlar NARXNOMASI (Aholi bo'yicha)"

DKQ = "Agar DKQ davrida qo'shimcha nosoz qismlar aniqlanmasa"

# (tartib, nomi, narx, izoh, saytdagi xizmat)
ULGURJI = [
    (1, "Aloqaga chiqarish", 450000, "", "almashtirish"),
    (2, "Modem kabelini almashtirish", 850000, "", "almashtirish"),
    (3, "Kompleks modem o'rnatish va ishga tushirish (integratsiya)", 750000, "", "almashtirish"),
    (4, "Maishiy hisoblagichni echib olib, qiyoslovdan o'tkazib, qayta o'rnatish", 1290000, DKQ, "qiyoslov"),
    (5, "Sanoat hisoblagichini echib olib, qiyoslovdan o'tkazib, qayta o'rnatish", 2780000, DKQ, "qiyoslov"),
    (6, "Maishiy hisoblagich o'rnatish, filtr tozalash (G-4, G-6, G-10 hisoblagichlar uchun)", 270000, "", "almashtirish"),
    (7, "Maishiy hisoblagich o'rnatish, filtr tozalash (G-16, G-25, G-40, G-65 hisoblagichlar uchun)", 450000, "", "almashtirish"),
    (8, "Sanoat hisoblagichlarini kompleks o'rnatish, ishga tushirish va sozlash (Pusk)", 1950000, "", "almashtirish"),
    (9, "Sanoat hisoblagichlari filtrini tozalash va qayta o'rnatish", 550000, "", "almashtirish"),
    (10, "Sanoat hisoblagichlariga kompleks uzel o'rnatish, sozlash va ishga tushirish", 2450000, "", "almashtirish"),
]
AHOLI = [
    (1, "Aloqaga chiqarish", 400000, "", "almashtirish"),
    (2, "Modem kabelini almashtirish", 750000, "", "almashtirish"),
    (3, "Modem o'rnatish", 600000, "", "almashtirish"),
]


def kirit(apps, schema_editor):
    Narxnoma = apps.get_model('narxnoma', 'Narxnoma')
    Qator = apps.get_model('narxnoma', 'NarxnomaQator')
    keyingi = (Narxnoma.objects.order_by('-tartib').values_list('tartib', flat=True).first() or 0) + 1
    for tarmoq, sarlavha, eslatma, qatorlar in (
            ('ulgurji', ULGURJI_SARLAVHA, ULGURJI_ESLATMA, ULGURJI),
            ('aholi', AHOLI_SARLAVHA, '', AHOLI)):
        n, yaratildi = Narxnoma.objects.get_or_create(
            tarmoq=tarmoq, bolim='metrologiya',
            defaults=dict(tartib=keyingi, sarlavha=sarlavha, ustun1="Bitta gaz hisoblagich hisobida narx (so'm)",
                          eslatma=eslatma, faol=True))
        keyingi += 1
        if not yaratildi or n.qatorlar.exists():
            continue
        Qator.objects.bulk_create([
            Qator(narxnoma=n, tartib=t, nomi=nom, p_dan=narx, izoh=izoh, sayt_xizmat=xz, faol=True)
            for t, nom, narx, izoh, xz in qatorlar])


def olib_tashla(apps, schema_editor):
    # Faqat shu migratsiya kiritgan narxnomalarni olib tashlaydi (qatorlari bilan)
    apps.get_model('narxnoma', 'Narxnoma').objects.filter(bolim='metrologiya').delete()


class Migration(migrations.Migration):

    dependencies = [
        ('narxnoma', '0008_metrologiya_bolim'),
    ]

    operations = [
        migrations.RunPython(kirit, olib_tashla),
    ]
