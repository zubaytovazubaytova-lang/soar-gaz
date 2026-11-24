from django.contrib import admin

from .models import Narxnoma, NarxnomaQator, SeshanbaAksiya, keyingi_seshanba, seshanba_aksiyasi


class QatorInline(admin.TabularInline):
    model = NarxnomaQator
    extra = 0
    fields = ('tartib', 'nomi', 'p_dan', 'p_gacha', 'r_dan', 'r_gacha', 'izoh', 'sayt_xizmat', 'faol')


@admin.register(Narxnoma)
class NarxnomaAdmin(admin.ModelAdmin):
    list_display = ('sarlavha', 'tarmoq', 'bolim', 'amal_qiladi', 'faol', 'yangilangan')
    inlines = [QatorInline]


@admin.register(NarxnomaQator)
class NarxnomaQatorAdmin(admin.ModelAdmin):
    list_display = ('tartib', 'nomi', 'p_dan', 'p_gacha', 'r_dan', 'r_gacha', 'izoh', 'sayt_xizmat', 'faol')
    list_editable = ('p_dan', 'p_gacha', 'r_dan', 'r_gacha', 'faol')
    list_filter = ('narxnoma', 'sayt_xizmat', 'faol')
    search_fields = ('nomi',)


@admin.register(SeshanbaAksiya)
class SeshanbaAksiyaAdmin(admin.ModelAdmin):
    """Har seshanba navbat bo'yicha bitta juftlik amal qiladi (oxiridan keyin yana boshidan)."""
    list_display = ('tartib', 'xizmat1', 'xizmat2', 'faol', 'qaysi_seshanbalar')
    list_editable = ('faol',)

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        # Ro'yxatda qaysi narxnomadan ekani ham ko'rinsin (bir xil nomli xizmat bir necha narxnomada bor)
        if db_field.name in ('xizmat1', 'xizmat2'):
            tarmoq = 'aholi' if db_field.name == 'xizmat1' else 'ulgurji'
            kwargs['queryset'] = (NarxnomaQator.objects.filter(faol=True, narxnoma__tarmoq=tarmoq,
                                                               narxnoma__bolim__in=('profilaktika', 'buyurtma'))
                                  .select_related('narxnoma').order_by('narxnoma_id', 'tartib'))
            maydon = super().formfield_for_foreignkey(db_field, request, **kwargs)
            maydon.label_from_instance = lambda q: f'{q.narxnoma.tarmoq_nomi} · {q.narxnoma.bolim_nomi} — {q.tartib}. {q.nomi[:80]}'
            return maydon
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    @admin.display(description='Yaqin 8 hafta ichida')
    def qaysi_seshanbalar(self, obj):
        import datetime
        from django.utils import timezone
        boshi = keyingi_seshanba(timezone.localdate())
        sanalar = []
        for i in range(8):
            sana = boshi + datetime.timedelta(weeks=i)
            a = seshanba_aksiyasi(sana)
            if a and a.pk == obj.pk:
                sanalar.append(sana.strftime('%d.%m'))
        return ', '.join(sanalar) or '—'
