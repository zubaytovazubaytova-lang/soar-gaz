"""Tarmoqlar: mavjud narxnoma ULGURJI deb belgilanadi, AHOLI uchun uchta bo'sh
narxnoma yaratiladi (narxlarni administrator boshqaruv panelidan kiritadi).

Aholi narxlari bu yerda KIRITILMAYDI: ular hujjatda berilmagan, o'ylab topilgan
narx esa mijozga ko'rinib qolishi mumkin. Migratsiya faqat bir marta, narxnoma
mavjud bo'lmaganda yaratadi — keyin admin o'zgartirganini bosib ketmaydi.
"""
from django.db import migrations


def tarmoqlar(apps, schema_editor):
    Narxnoma = apps.get_model('narxnoma', 'Narxnoma')

    # Mavjud (qog'oz hujjatdan kiritilgan) narxnoma — ulgurji
    Narxnoma.objects.filter(tarmoq='ulgurji', bolim='profilaktika').update(
        tartib=1, ustun1_qisqa='profilaktika', ustun2_qisqa='reviziya')

    aholi = [
        # (bo'lim, tartib, sarlavha, 1-ustun, 1-qisqa, 2-ustun, 2-qisqa)
        ('buyurtma', 2, "Aholi uchun xizmatlar narxnomasi — buyurtma asosida",
         "Xizmat narxi (so'm)", '', '', ''),
        ('profilaktika', 3, "Aholi uchun profilaktika va texnik ko'rik narxlari",
         "Profilaktika narxi (so'm)", 'profilaktika',
         "Texnik ko'rik narxi (so'm)", "texnik ko'rik"),
        ('ornatish', 4, "Aholi uchun yangi jihoz o'rnatib, ishga tushirib berish narxlari",
         "O'rnatish va ishga tushirish narxi (so'm)", '', '', ''),
    ]
    for bolim, tartib, sarlavha, u1, q1, u2, q2 in aholi:
        Narxnoma.objects.get_or_create(
            tarmoq='aholi', bolim=bolim,
            defaults=dict(tartib=tartib, sarlavha=sarlavha, ustun1=u1, ustun1_qisqa=q1,
                          ustun2=u2, ustun2_qisqa=q2, faol=True))


class Migration(migrations.Migration):

    dependencies = [
        ('narxnoma', '0003_tarmoq_bolim'),
    ]

    operations = [
        # Orqaga qaytarishda narxlar o'chirilmaydi (admin kiritgan bo'lishi mumkin)
        migrations.RunPython(tarmoqlar, migrations.RunPython.noop),
    ]
