"""Aholi uchun «Buyurtma asosida» narxnomasi: qog'oz hujjatdan ko'chirilgan 27 qator.

Hujjat: «Ichki gaz jihozlaridagi (KKS bilan) buyurtma asosida bitta gaz jihozini profilaktika
va texnik ko'rik (reviziya)dan o'tkazish NARXNOMASI (Aholi bo'yicha)», 01.06.2025 dan.
Har qatorda IKKI narx (profilaktika va texnik ko'rik), shuning uchun bu narxnoma bitta ustunli
emas, ikki ustunli qilinadi.

Migratsiya narxlarni FAQAT BIR MARTA kiritadi: narxnomada qator bo'lsa, ya'ni administrator
allaqachon narx kiritgan yoki o'zgartirgan bo'lsa, hech narsa ustidan yozilmaydi.
"""
import datetime

from django.db import migrations

SARLAVHA = ("Ichki gaz jihozlaridagi (KKS bilan) buyurtma asosida bitta gaz jihozini profilaktika va "
            "texnik ko'rik (reviziya)dan o'tkazish NARXNOMASI (Aholi bo'yicha)")

KELISHUV = "Ish hajmiga ko'ra (kelishuv asosida)"

# (tartib, nomi, profilaktika, texnik ko'rik, izoh — narx o'rniga matn bo'lsa)
QATORLAR = [
    (1, "PG-2x kamparakli maishiy gaz plitasi", 30236, 46254, ""),
    (2, "PG-3x va PG-4x kamparakli maishiy gaz plitasi", 37794, 53643, ""),
    (3, "Avtomatik infraqizil yondirgichli pechlarni (yog'ochli isitgichlar) isitish uchun", 41076, 56943, ""),
    (4, "Avtomatiksiz infraqizil yondirgichli pechlarni (yog'ochli isitgichlar, o'tin yoqish karnaylari) isitish uchun", 30236, 46254, ""),
    (5, "Oqimli suv isitgichlari (suv isitish qozoni), «Issiq» qurilmasi", 65646, 103158, ""),
    (6, "AGV-80, AGV-120 sig'imli suv isitgichlari va AKGV-11,6; AKGV-20, AKGV-23 rusumli suv qizdirgichli qozonlar va boshqalar", 85341, 112539, ""),
    (7, "Gaz qozon, gaz uchoq", 29073, 42189, ""),
    (8, "Uzluksiz qozon", 40326, 58143, ""),
    (9, "Ikki konturli isitish qozoni (12-14-24 KV)", 180750, 282750, ""),
    (10, "Gaz hisoblash uskunasida gaz sizib chiqish holatini bartaraf etish", 150000, 225000, ""),
    (11, "Standart tejamkor gaz yondirgich (gorelka)larni o'rnatish", 137475, 180750, ""),
    (12, "Jumraklar (kranlar)ga xizmat ko'rsatish", 34365, 52800, ""),
    (13, "Reduktorlarga xizmat ko'rsatish", 97800, 136500, ""),
    (14, "Gaz jihozlarini o'rnatish", 117975, 166275, ""),
    (15, "PG-3x yoki PG-4x kamparakli, boshqa chet elda ishlab chiqarilgan gaz plitasi", 96150, 127725, ""),
    (16, "PIMAK PG-4, PG-6 va PG-8", 99810, 140100, ""),
    (17, "PIMAK (PG-1, PG-2 va PG-3)", 89175, 117750, ""),
    (18, "Isitish qozoni (24 KV yuqori Climit Rima ...) o'rnatish", 240000, 292500, ""),
    (19, "27 yoki 50 litrli hajmdagi maishiy gaz ballonga xizmat ko'rsatish", 14958, 23283, ""),
    (20, "Reduktor bog'lamali ikkita maishiy gaz balloni", 44076, 140673, ""),
    (21, "Binoda reduktorli maishiy gaz balloni", 37512, 130275, ""),
    (22, "Metal shkafda reduktorli maishiy gaz balloni", 30009, 101775, ""),
    (23, "Gaz ballon reduktoriga xizmat ko'rsatish", 79245, 118350, ""),
    (24, "Gaz ballonga o'rnatilgan PG-2x, PG-3x va PG-4x gaz komforkalariga xizmat ko'rsatish", 47130, 81435, ""),
    (25, "Ro'yxatga kirmagan boshqa gaz jihozlari", None, None, KELISHUV),
    (26, "Ichki gaz quvurlari", 57300, None, KELISHUV),          # profilaktika — narx, texnik ko'rik — kelishuv
    (27, "Transport xarajati (shahar ichida, shahardan tashqarida tumanlar bo'yicha)", 16250, 32500, ""),
]


def kirit(apps, schema_editor):
    Narxnoma = apps.get_model('narxnoma', 'Narxnoma')
    Qator = apps.get_model('narxnoma', 'NarxnomaQator')
    n = Narxnoma.objects.filter(tarmoq='aholi', bolim='buyurtma').first()
    if n is None or n.qatorlar.exists():
        return                                    # allaqachon to'ldirilgan — ustidan yozmaymiz
    n.sarlavha = SARLAVHA
    n.tavsif = 'Aholi bo\'yicha'
    n.amal_qiladi = datetime.date(2025, 6, 1)
    n.ustun1, n.ustun1_qisqa = "Profilaktika narxi (so'm)", 'profilaktika'
    n.ustun2, n.ustun2_qisqa = "Texnik ko'rik narxi (so'm)", "texnik ko'rik"
    n.save()
    Qator.objects.bulk_create([
        Qator(narxnoma=n, tartib=t, nomi=nomi, p_dan=p, r_dan=r, izoh=izoh)
        for (t, nomi, p, r, izoh) in QATORLAR])


class Migration(migrations.Migration):

    dependencies = [
        ('narxnoma', '0004_aholi_narxnomalari'),
    ]

    operations = [
        # Orqaga qaytarishda narxlar o'chirilmaydi (admin o'zgartirgan bo'lishi mumkin)
        migrations.RunPython(kirit, migrations.RunPython.noop),
    ]
