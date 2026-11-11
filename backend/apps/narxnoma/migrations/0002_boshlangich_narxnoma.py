"""Ulgurji narxnomasi (01.09.2026 dan amal qiladi) — qog'oz hujjatdan ko'chirilgan.

Bu migratsiya narxlarni FAQAT BIR MARTA kiritadi (jadval bo'sh bo'lsa). Keyin
narxlarni administrator boshqaruv panelidan o'zgartiradi; migratsiya qayta
ishga tushirilsa ham ularning ustidan yozmaydi.
"""
import datetime

from django.db import migrations

SARLAVHA = ("Ulgurchi obyektlarining (Sanoat, kichik va o'rta biznes) gaz uskunalarini "
            "ko'zdan kechirish, tekshirish, texnik ko'rikdan o'tkazish xizmatlari NARXNOMASI")
TAVSIF = "Ulgurji. «Soar Gaz Building» MChJ"
USTUN1 = "Bitta gaz jihozini profilaktika o'tkazish narxi (so'm)"
USTUN2 = "Bitta gaz jihozini texnik ko'rikdan (reviziya) o'tkazish narxi (so'm)"
ESLATMA = ("5x kamparakli gaz plitasini ishga tushirish va sozlash xizmatlarining narxi "
           "2x va 3x kamparakli gaz plitalari uchun xizmatlarning yig'indisi sifatida, "
           "6x kamparakli gaz plitasi uchun esa 2x va 4x kamparakli gaz plitasi uchun "
           "xizmatlar yig'indisi sifatida belgilanadi.")

SOATLIK = "Soatlik gaz sarfi me'yoriga asosan hisoblanadi"
KELISHUV = "Ish hajmi va kelishuv asosida"

# (tartib, nomi, p_dan, p_gacha, r_dan, r_gacha, izoh)
QATORLAR = [
    (1, "Gaz plitasi 2 kamparakli", 233500, None, 389200, None, ""),
    (2, "Gaz plitasi 3 yoki 4 kamparakli", 352344, None, 587240, None, ""),
    (3, "Gaz qozon, gaz uchoq", 348180, None, 580300, None, ""),
    (4, "Oqimli suv isitgichlari (suv isitish qozoni), «Issiq» qurilmasi", 293550, None, 489250, None, ""),
    (5, "AGV-80, AGV-120 sig'imli suv isitgichlari va VNIISTO qozonlari, AKGV-11,6, AKGV-20, AKGV-23 va boshqalar", 238590, None, 397650, None, ""),
    (6, "Avtomatik infraqizil yondirgichli pechkalarni isitish uchun", 219420, None, 365700, None, ""),
    (7, "Avtomatikasiz infraqizil yondirgichli pechkalarni (yog'ochli isitgichlar, o'tin yoqish karnaylari) isitish uchun", 210720, None, 351200, None, ""),
    (8, "Restoran plitasi PSHG-2", 411240, None, 685400, None, ""),
    (9, "Restoran plitasi PSG-2", 411240, None, 685400, None, ""),
    (10, "Avtomatik parchalanuvchi kotyol", 444090, None, 740150, None, ""),
    (11, "Laboratoriya gorelkasi", 233520, None, 389200, None, ""),
    (12, "Avtomatik infraqizil burner gorelkasi", 392580, None, 654300, None, ""),
    (13, "Isitish qozoni KOGN rusumlilar", 210000, 330000, 350000, 550000, ""),
    (14, "Isitish qozonlari KOV rusumlilar", 588000, 930000, 980000, 1550000, ""),
    (15, "Isitish qozonlari KVa rusumlilar", 750000, 960000, 1250000, 1600000, ""),
    (16, "Isitish qozonlari KVS rusumlilar", 660000, 900000, 1100000, 1500000, ""),
    (17, "Isitish qozonlari chet elda ishlab chiqarilgan", 780000, 990000, 1300000, 1650000, ""),
    (18, "Ikki konturli suv isitish qozoni", 285360, None, 475600, None, ""),
    (19, "Rotatsion pech", 225000, None, 375000, None, ""),
    (20, "Non va non mahsulotlarini pishirish (duxovkali) pech", 224748, None, 374580, None, ""),
    (21, "Issiqlik (teplo) generatori", 214800, None, 358000, None, ""),
    (22, "Tutun mo'rilarini tozalash", 420000, None, 700000, None, ""),
    (23, "Gaz ballon o'rnatilgan PG-2, PG-3 va PG-4 kamparakli gaz plitalariga xizmat ko'rsatish", 116126, None, 193544, None, ""),
    (24, "MGP-300 rusumli bitum eritish agregati", 1360870, None, 2268117, None, ""),
    (25, "MGP-100 rusumli bitum eritish agregati", 1260600, None, 2101000, None, ""),
    (26, "MGP-25 rusumli bitum eritish agregati", 1142781, None, 1904635, None, ""),
    (27, "MGP-10 rusumli bitum eritish agregati", 890545, None, 1484242, None, ""),
    (28, "Jumraklarga (kranlarga) xizmat ko'rsatish", 346200, None, 577000, None, ""),
    (29, "Standart tejamkor yondirgich o'rnatish", 113400, None, 189000, None, ""),
    (30, "Reduktorlarga xizmat ko'rsatish", 106800, None, 178000, None, ""),
    (31, "Gaz jihozlarini o'rnatish", 238800, None, 398000, None, ""),
    (32, "2 konforkali gaz plitasi", 212400, None, 354000, None, ""),
    (33, "2-3 konforkali gaz plitasi", 212400, None, 354000, None, ""),
    (34, "2-3 konforkali (Brest yoki boshqa chet elda ishlab chiqarilgan) gaz plitasi", 294000, None, 490000, None, ""),
    (35, "VOCK rusumli (1-2 talik) qozon", 213000, None, 355000, None, ""),
    (36, "VOCK rusumli (3-4 talik) qozon", 213300, None, 355500, None, ""),
    (37, "Pishirish qozoni o'choq", 216000, None, 360000, None, ""),
    (38, "Boshqa turdagi isitish qozonlari", None, None, None, None, SOATLIK),
    (39, "Restoran gaz plitasi", 468000, None, 780000, None, ""),
    (40, "Pimak (PG1-PG2-PG3)", 353400, None, 589000, None, ""),
    (41, "Pimak (PG4-PG6-PG8)", 353400, None, 589000, None, ""),
    (42, "Gaz bilan ishlaydigan tandir", 522000, None, 870000, None, ""),
    (43, "Ikki konturli suv isitish qozoni (12-14-24 kv)", 588000, None, 980000, None, ""),
    (44, "Isitish qozoni (24 kv dan yuqori, Clima Rima)", 588000, None, 980000, None, ""),
    (45, "Bug' qozoni", 900000, None, 1500000, None, ""),
    (46, "GMP (плановый ремонт оборудования, шкафной, с 1 ниткой, с 2 нитками)", 876000, None, 1460000, None, ""),
    (47, "GMP (плановый ремонт оборудования, шкафной, с 1 ниткой, с 2 нитками)", 876000, None, 1460000, None, ""),
    (48, "Ichki gaz quvurlarini reviziya qilish", None, None, None, None, KELISHUV),
    (49, "Transport xarajati", 50000, None, 150000, None, ""),
]


def kirit(apps, schema_editor):
    Narxnoma = apps.get_model('narxnoma', 'Narxnoma')
    Qator = apps.get_model('narxnoma', 'NarxnomaQator')
    if Narxnoma.objects.exists():
        return
    n = Narxnoma.objects.create(
        sarlavha=SARLAVHA, tavsif=TAVSIF, amal_qiladi=datetime.date(2026, 9, 1),
        ustun1=USTUN1, ustun2=USTUN2, eslatma=ESLATMA, faol=True)
    Qator.objects.bulk_create([
        Qator(narxnoma=n, tartib=t, nomi=nomi, p_dan=pd, p_gacha=pg,
              r_dan=rd, r_gacha=rg, izoh=izoh)
        for (t, nomi, pd, pg, rd, rg, izoh) in QATORLAR])


class Migration(migrations.Migration):

    dependencies = [
        ('narxnoma', '0001_initial'),
    ]

    operations = [
        # Orqaga qaytarishda narxlar o'chirilmaydi: ularni admin o'zgartirgan bo'lishi mumkin
        migrations.RunPython(kirit, migrations.RunPython.noop),
    ]
