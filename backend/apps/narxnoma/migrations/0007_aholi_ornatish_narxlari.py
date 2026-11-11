"""Aholi uchun «Yangi jihoz o'rnatib ishga tushirish» narxnomasi: qog'oz hujjatdan 25 qator.

Hujjat: «Uy ichi gaz jihozlarini (KKS bilan) bitta gaz jihozini ishga tushirish NARXNOMASI
(Aholi bo'yicha)», 01.06.2025 dan. Ikki narx ustuni: «Boshlang'ich» va «O'rtacha» bir xizmat narxi.

Migratsiya narxlarni FAQAT BIR MARTA kiritadi: narxnomada qator bo'lsa (administrator allaqachon
narx kiritgan yoki o'zgartirgan), hech narsa ustidan yozilmaydi.

Eslatmaning 1-bandi (PG-5x va PG-6x plitalar narxi) aholining barcha narxnomalarida bir xil
boshlanadi — qolgan ikki aholi narxnomasida eslatma bo'sh bo'lsa, shu band qo'yiladi.
"""
import datetime

from django.db import migrations

SARLAVHA = ("Uy ichi gaz jihozlarini (KKS bilan) bitta gaz jihozini ishga tushirish "
            "NARXNOMASI (Aholi bo'yicha)")

ESLATMA_1 = ("1. PG-5x kamparakli gaz plitasini ishga tushirish va sozlash xizmatlarining narxi PG-2x va PG-3x "
             "kamparakli gaz plitalari uchun xizmatlarning yig'indisi sifatida, PG-6x kamparakli gaz plitasi "
             "uchun esa PG-2x va PG-4x kamparakli gaz plitalari uchun xizmatlar yig'indisi sifatida belgilanadi.")
# 4-band suratda aniq o'qilmadi, shuning uchun kiritilmadi
ESLATMA = "\n".join([
    ESLATMA_1,
    "2. Mazkur narxlar «O'zkommunyo'quvtashkiloti» Respublika o'quv-uslubiy, me'yoriy-huquqiy va muhandislik "
    "markazi tomonidan ishlab chiqilgan hisob-kitoblar asosida ishlab chiqilgan.",
    "3. Xodimning oylik ish haqi hamda eng kam mehnatga haq to'lash miqdori ko'tarilganda narxnoma "
    "o'zgartiriladi. Narxnomada gaz jihoziga qo'yiladigan material va ehtiyot qismlar inobatga olinmagan. "
    "Jihozga qo'yiladigan material xarajati va ehtiyot qism buyurtmachi, ya'ni iste'molchi tomonidan "
    "qo'shimcha tarzda to'lab beriladi.",
])

KELISHUV = "Ish hajmiga ko'ra (kelishuv asosida)"

# (tartib, nomi, boshlang'ich narx, o'rtacha narx, izoh — narx o'rniga matn bo'lsa)
QATORLAR = [
    (1, "PG-2x kamparakli maishiy gaz plitasi", 80628, 123344, ""),
    (2, "PG-3x va PG-4x kamparakli maishiy gaz plitasi", 100784, 143048, ""),
    (3, "Avtomatik infraqizil yondirgichli pechlarni (yog'ochli isitgichlar) isitish uchun", 109536, 151848, ""),
    (4, "Avtomatiksiz infraqizil yondirgichli pechlarni (yog'ochli isitgichlar, o'tin yoqish karnaylari) isitish uchun", 80628, 123344, ""),
    (5, "Oqimli suv isitgichlari (suv isitish qozoni), «Issiq» qurilmasi", 175056, 275088, ""),
    (6, "AGV-80, AGV-120 sig'imli suv isitgichlari va AKGV-11,6; AKGV-20, AKGV-23 rusumli suv qizdirgichli qozonlar va boshqalar", 227576, 300104, ""),
    (7, "Gaz qozon, gaz uchoq", 77528, 112504, ""),
    (8, "Uzluksiz qozon", 107536, 155048, ""),
    (9, "Ikki konturli isitish qozoni (12-14-24 KV)", 482000, 754000, ""),
    (10, "Gaz hisoblash uskunasida gaz sizib chiqish holatini bartaraf etish", 200000, 600000, ""),
    (11, "Standart tejamkor gaz yondirgich (gorelka), tandir va boshqalar", 366600, 482000, ""),
    (12, "Jumraklar (kranlar)ga xizmat ko'rsatish", 91640, 140800, ""),
    (13, "Reduktorlarga xizmat ko'rsatish", 260800, 364000, ""),
    (14, "Gaz jihozlarini o'rnatish", 314600, 443400, ""),
    (15, "PG-3x yoki PG-4x kamparakli, boshqa chet elda ishlab chiqarilgan gaz plitasi", 256400, 340600, ""),
    (16, "Ro'yxatga kirmagan boshqa gaz jihozlari", None, None, KELISHUV),
    (17, "PIMAK (PG-1, PG-2 va PG-3)", 237800, 314000, ""),
    (18, "Isitish qozoni (24 KV yuqori Climit Rima ...) o'rnatish", 640000, 780000, ""),
    (19, "27 yoki 50 litrli hajmdagi maishiy gaz ballonga xizmat ko'rsatish", 39888, 62088, ""),
    (20, "Reduktor bog'lamali ikkita maishiy gaz balloni", 117536, 375128, ""),
    (21, "Binoda reduktorli maishiy gaz balloni", 100032, 347400, ""),
    (22, "Metal shkafda reduktorli maishiy gaz balloni", 80024, 271400, ""),
    (23, "Gaz ballon reduktoriga xizmat ko'rsatish", 211320, 315600, ""),
    (24, "Gaz ballonga o'rnatilgan PG-2x, PG-3x va PG-4x gaz komforkalariga xizmat ko'rsatish", 125680, 217160, ""),
    (25, "Transport xarajati (shahar ichida, shahardan tashqarida tumanlar bo'yicha)", 16250, 32500, ""),
]


def kirit(apps, schema_editor):
    Narxnoma = apps.get_model('narxnoma', 'Narxnoma')
    Qator = apps.get_model('narxnoma', 'NarxnomaQator')

    n = Narxnoma.objects.filter(tarmoq='aholi', bolim='ornatish').first()
    if n is not None and not n.qatorlar.exists():
        n.sarlavha = SARLAVHA
        n.tavsif = "Aholi bo'yicha"
        n.amal_qiladi = datetime.date(2025, 6, 1)
        n.ustun1, n.ustun1_qisqa = "Boshlang'ich bir xizmat narxi (so'm)", "boshlang'ich"
        n.ustun2, n.ustun2_qisqa = "O'rtacha bir xizmat narxi (so'm)", "o'rtacha"
        n.eslatma = ESLATMA
        n.save()
        Qator.objects.bulk_create([
            Qator(narxnoma=n, tartib=t, nomi=nomi, p_dan=p, r_dan=r, izoh=izoh)
            for (t, nomi, p, r, izoh) in QATORLAR])

    # PG-5x/PG-6x eslatmasi aholining qolgan narxnomalarida ham (faqat bo'sh bo'lsa)
    Narxnoma.objects.filter(tarmoq='aholi', bolim__in=['buyurtma', 'profilaktika'], eslatma='').update(
        eslatma=ESLATMA_1)


class Migration(migrations.Migration):

    dependencies = [
        ('narxnoma', '0006_aholi_profilaktika_narxlari'),
    ]

    operations = [
        # Orqaga qaytarishda narxlar o'chirilmaydi (admin o'zgartirgan bo'lishi mumkin)
        migrations.RunPython(kirit, migrations.RunPython.noop),
    ]
