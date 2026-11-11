from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('narxnoma', '0007_aholi_ornatish_narxlari'),
    ]

    operations = [
        migrations.AlterField(
            model_name='narxnoma',
            name='bolim',
            field=models.CharField(
                choices=[('buyurtma', 'Buyurtma asosida'),
                         ('profilaktika', "Profilaktika va texnik ko'rik"),
                         ('ornatish', "Yangi jihoz o'rnatib ishga tushirish"),
                         ('metrologiya', 'Metrologiya xizmatlari')],
                default='profilaktika', max_length=15),
        ),
        migrations.AddField(
            model_name='narxnomaqator',
            name='sayt_xizmat',
            field=models.CharField(
                blank=True, default='', max_length=20, verbose_name='Saytdagi xizmat',
                help_text="Metrologiya narxnomasi: narx saytning qaysi xizmat oynasida ko'rinadi",
                choices=[('', "Saytda ko'rsatilmaydi"), ('kalibrovka', 'Kalibrovka'),
                         ('almashtirish', 'Almashtirish'), ('qiyoslov', "Davlat qiyoslov ko'rigi")]),
        ),
    ]
