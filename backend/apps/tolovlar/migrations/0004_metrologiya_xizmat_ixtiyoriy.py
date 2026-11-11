from django.db import migrations, models


class Migration(migrations.Migration):
    """Metrologiya arizasida xizmat turi ixtiyoriy: tanlanmasa ham ariza qabul qilinadi."""

    dependencies = [
        ('tolovlar', '0003_metrologiyaarizasi'),
    ]

    operations = [
        migrations.AlterField(
            model_name='metrologiyaarizasi',
            name='xizmat',
            field=models.CharField(
                blank=True, default='', max_length=20,
                choices=[('kalibrovka', 'Kalibrovka'), ('almashtirish', 'Almashtirish'),
                         ('qiyoslov', "Davlat qiyoslov ko'rigi")]),
        ),
    ]
