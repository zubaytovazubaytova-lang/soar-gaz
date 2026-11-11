from django.contrib import admin

from .models import Narxnoma, NarxnomaQator


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
