from django.db import migrations


def yarat(apps, schema_editor):
    """Yagona «Hujjat sozlamasi» yozuvi: Django panelida to'g'ridan-to'g'ri tahrirlanadi.
    Shartnoma matni tasdiqlanmagan holda (False) boshlanadi — direktor kiritib tasdiqlamaguncha
    xodimlar shartnoma tuza olmaydi."""
    Sozlama = apps.get_model('hujjatlar', 'Sozlama')
    Sozlama.objects.get_or_create(pk=1)


class Migration(migrations.Migration):

    dependencies = [
        ('hujjatlar', '0001_hujjatlar'),
    ]

    operations = [
        migrations.RunPython(yarat, migrations.RunPython.noop),
    ]
