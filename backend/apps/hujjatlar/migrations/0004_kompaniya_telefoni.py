from django.db import migrations

# Qog'oz kvitansiyaning pastki qismidagi «Servis xizmat ko'rsatish» telefonlari
TELEFON = '(98) 274 62 87, (91) 974 62 87'


def toldir(apps, schema_editor):
    """Kompaniya telefoni bo'sh bo'lsa, qog'oz kvitansiyadagi raqamlar qo'yiladi (admin o'zgartirgan bo'lsa tegilmaydi)."""
    Sozlama = apps.get_model('hujjatlar', 'Sozlama')
    Sozlama.objects.filter(telefon='').update(telefon=TELEFON)


class Migration(migrations.Migration):

    dependencies = [
        ('hujjatlar', '0003_kvitansiya_mijoz_qatorlar'),
    ]

    operations = [
        migrations.RunPython(toldir, migrations.RunPython.noop),
    ]
