"""Yordam markazi uchun boshlang'ich savol-javoblar."""

from django.db import migrations


SAVOLLAR = [
    ("Hisoblagichning davlat tekshiruvi qanchada bir marta o'tkaziladi?",
     "Maishiy gaz hisoblagichlari uchun tekshiruv oralig'i odatda 5 yil, elektron "
     "hisoblagichlar uchun 2–4 yil. Aniq muddat pasportda ko'rsatiladi va kabinetdagi "
     "«Hisoblagichlarim» bo'limida kuzatib boriladi — muddat tugashiga 30 kun qolganda "
     "eslatma olasiz."),
    ("Buyurtma bergandan keyin xodim qachon keladi?",
     "Ariza qabul qilingach operator 1 ish kuni ichida bog'lanadi va vaqtni "
     "kelishadi. Xodim tayinlangach uning ismi va telefoni «Mening buyurtmalarim» "
     "bo'limida ko'rinadi."),
    ("To'lovni qanday amalga oshirsam bo'ladi?",
     "Click yoki Payme orqali onlayn (Uzcard/Humo), bank o'tkazmasi bilan yoki "
     "shartnoma asosida bo'lib to'lash mumkin. Karta ma'lumotlari saytda saqlanmaydi — "
     "to'lov to'lov tizimining himoyalangan sahifasida bajariladi."),
    ("Bir nechta manzilda xizmat olsam nima qilaman?",
     "«Mening obyektlarim» bo'limiga har bir manzilni alohida qo'shing (uy, dala hovli, "
     "ofis). Ariza berayotganda kerakli obyektni tanlaysiz, xodim aynan o'sha manzilga boradi."),
    ("Gaz hidi sezsam nima qilishim kerak?",
     "Darhol gaz ventilini yoping, elektr uskunalarini yoqmang va o'chirmang, xonani "
     "shamollatib, ko'chaga chiqing. So'ng 104 raqamiga va bizning navbatchi "
     "operatorimizga qo'ng'iroq qiling."),
    ("Shartnoma va sertifikatlarni qayerdan olaman?",
     "Barcha hujjatlar «Hujjatlarim» bo'limida PDF ko'rinishida saqlanadi va istalgan "
     "vaqtda yuklab olinadi."),
]


def qoshish(apps, schema_editor):
    SavolJavob = apps.get_model('kabinet', 'SavolJavob')
    for tartib, (savol, javob) in enumerate(SAVOLLAR, start=1):
        SavolJavob.objects.get_or_create(savol=savol, defaults={'javob': javob, 'tartib': tartib})


def ochirish(apps, schema_editor):
    SavolJavob = apps.get_model('kabinet', 'SavolJavob')
    SavolJavob.objects.filter(savol__in=[s for s, _ in SAVOLLAR]).delete()


class Migration(migrations.Migration):

    dependencies = [('kabinet', '0001_initial')]

    operations = [migrations.RunPython(qoshish, ochirish)]
