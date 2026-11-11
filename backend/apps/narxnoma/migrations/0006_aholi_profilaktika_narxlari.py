"""Aholi uchun «Profilaktika va texnik ko'rik» narxnomasi: qog'oz hujjatdan ko'chirilgan 26 qator.

Hujjat: «Uy ichi gaz jihozlaridagi (KKS bilan) bitta gaz jihozini profilaktika va texnik ko'rik
(reviziya)dan o'tkazish NARXNOMASI (Aholi bo'yicha)», 01.06.2025 dan. Bu — oddiy narxlar;
«buyurtma asosida» narxnomasi (0005) shularning 1,5 baravari.

Migratsiya narxlarni FAQAT BIR MARTA kiritadi: narxnomada qator bo'lsa (administrator allaqachon
narx kiritgan yoki o'zgartirgan), hech narsa ustidan yozilmaydi.
"""
import datetime

from django.db import migrations

SARLAVHA = ("Uy ichi gaz jihozlaridagi (KKS bilan) bitta gaz jihozini profilaktika va texnik ko'rik "
            "(reviziya)dan o'tkazish NARXNOMASI (Aholi bo'yicha)")

KELISHUV = "Ish hajmiga ko'ra (kelishuv asosida)"

# (tartib, nomi, profilaktika, texnik ko'rik, izoh — narx o'rniga matn bo'lsa)
QATORLAR = [
    (1, "PG-2x kamparakli maishiy gaz plitasi", 20157, 30836, ""),
    (2, "PG-3x va PG-4x kamparakli maishiy gaz plitasi", 25196, 35762, ""),
    (3, "Avtomatik infraqizil yondirgichli pechlarni (yog'ochli isitgichlar) isitish uchun", 27384, 37962, ""),
    (4, "Avtomatiksiz infraqizil yondirgichli pechlarni (yog'ochli isitgichlar, o'tin yoqish karnaylari) isitish uchun", 20157, 30836, ""),
    (5, "Oqimli suv isitgichlari (suv isitish qozoni), «Issiq» qurilmasi", 43764, 68772, ""),
    (6, "AGV-80, AGV-120 sig'imli suv isitgichlari va AKGV-11,6; AKGV-20, AKGV-23 rusumli suv qizdirgichli qozonlar va boshqalar", 56894, 75026, ""),
    (7, "Gaz qozon, gaz uchoq", 19382, 28126, ""),
    (8, "Uzluksiz qozon", 26884, 38762, ""),
    (9, "Ikki konturli isitish qozoni (12-14-24 KV)", 120500, 188500, ""),
    (10, "Gaz hisoblash uskunasida gaz sizib chiqish holatini bartaraf etish", 100000, 150000, ""),
    (11, "Standart tejamkor gaz yondirgich (gorelka)larni o'rnatish", 91650, 120500, ""),
    (12, "Jumraklar (kranlar)ga xizmat ko'rsatish", 22910, 35200, ""),
    (13, "Reduktorlarga xizmat ko'rsatish", 65200, 91000, ""),
    (14, "Gaz jihozlarini o'rnatish", 78650, 110850, ""),
    (15, "PG-3x yoki PG-4x kamparakli, boshqa chet elda ishlab chiqarilgan gaz plitasi", 64100, 85150, ""),
    (16, "PIMAK PG-4, PG-6 va PG-8", 66540, 93400, ""),
    (17, "PIMAK (PG-1, PG-2 va PG-3)", 59450, 78500, ""),
    (18, "Isitish qozoni (24 KV yuqori Climit Rima ...) o'rnatish", 160000, 195000, ""),
    (19, "27 yoki 50 litrli hajmdagi maishiy gaz ballonga xizmat ko'rsatish", 9972, 15522, ""),
    (20, "Reduktor bog'lamali ikkita maishiy gaz balloni", 29384, 93782, ""),
    (21, "Binoda reduktorli maishiy gaz balloni", 25008, 86850, ""),
    (22, "Metal shkafda reduktorli maishiy gaz balloni", 20006, 67850, ""),
    (23, "Gaz ballon reduktoriga xizmat ko'rsatish", 52830, 78900, ""),
    (24, "Gaz ballonga o'rnatilgan PG-2x, PG-3x va PG-4x gaz komforkalariga xizmat ko'rsatish", 31420, 54290, ""),
    (25, "Ichki gaz quvurlari", 38200, None, KELISHUV),        # profilaktika — narx, texnik ko'rik — kelishuv
    (26, "Ro'yxatga kirmagan boshqa gaz jihozlari", None, None, KELISHUV),
]


def kirit(apps, schema_editor):
    Narxnoma = apps.get_model('narxnoma', 'Narxnoma')
    Qator = apps.get_model('narxnoma', 'NarxnomaQator')
    n = Narxnoma.objects.filter(tarmoq='aholi', bolim='profilaktika').first()
    if n is None or n.qatorlar.exists():
        return                                    # allaqachon to'ldirilgan — ustidan yozmaymiz
    n.sarlavha = SARLAVHA
    n.tavsif = "Aholi bo'yicha"
    n.amal_qiladi = datetime.date(2025, 6, 1)
    n.ustun1, n.ustun1_qisqa = "Profilaktika narxi (so'm)", 'profilaktika'
    n.ustun2, n.ustun2_qisqa = "Texnik ko'rik narxi (so'm)", "texnik ko'rik"
    n.save()
    Qator.objects.bulk_create([
        Qator(narxnoma=n, tartib=t, nomi=nomi, p_dan=p, r_dan=r, izoh=izoh)
        for (t, nomi, p, r, izoh) in QATORLAR])


class Migration(migrations.Migration):

    dependencies = [
        ('narxnoma', '0005_aholi_buyurtma_narxlari'),
    ]

    operations = [
        # Orqaga qaytarishda narxlar o'chirilmaydi (admin o'zgartirgan bo'lishi mumkin)
        migrations.RunPython(kirit, migrations.RunPython.noop),
    ]
