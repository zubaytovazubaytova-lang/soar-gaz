from django.contrib import admin

from .models import (
    Obyekt, Uskuna, Hisoblagich, Hujjat, Bildirishnoma, Sharh,
    Murojaat, MurojaatXabar, QongiroqSorovi, SavolJavob, KabinetSozlama,
)


class UskunaInline(admin.TabularInline):
    model = Uskuna
    extra = 0


class HisoblagichInline(admin.TabularInline):
    model = Hisoblagich
    extra = 0


@admin.register(Obyekt)
class ObyektAdmin(admin.ModelAdmin):
    list_display = ('nom', 'mijoz', 'turi', 'tuman', 'manzil', 'asosiy')
    list_filter = ('turi', 'tuman', 'asosiy')
    search_fields = ('nom', 'manzil', 'mijoz__telefon', 'mijoz__ism')
    list_select_related = ('mijoz',)
    inlines = [UskunaInline, HisoblagichInline]


@admin.register(Hisoblagich)
class HisoblagichAdmin(admin.ModelAdmin):
    list_display = ('seriya_raqam', 'obyekt', 'turi', 'keyingi_tekshiruv', 'holat')
    list_filter = ('turi', 'holat')
    search_fields = ('seriya_raqam', 'markasi', 'obyekt__nom')
    # __str__ ham obyekt.nom ga murojaat qiladi — JOIN'siz har qator so'rov bo'lardi
    list_select_related = ('obyekt',)
    date_hierarchy = 'keyingi_tekshiruv'


@admin.register(Hujjat)
class HujjatAdmin(admin.ModelAdmin):
    """Mijozning kabinetida ko'rinadigan PDF hujjatlar shu yerdan yuklanadi."""
    list_display = ('nom', 'mijoz', 'turi', 'sana')
    list_filter = ('turi', 'sana')
    search_fields = ('nom', 'mijoz__telefon', 'mijoz__ism')
    list_select_related = ('mijoz',)


@admin.register(Bildirishnoma)
class BildirishnomaAdmin(admin.ModelAdmin):
    list_display = ('sarlavha', 'mijoz', 'turi', 'oqildi', 'yaratilgan')
    list_filter = ('turi', 'oqildi')
    search_fields = ('sarlavha', 'matn', 'mijoz__telefon')
    list_select_related = ('mijoz',)


@admin.register(Sharh)
class SharhAdmin(admin.ModelAdmin):
    list_display = ('mijoz', 'baho', 'buyurtma', 'yaratilgan')
    list_filter = ('baho',)
    search_fields = ('matn', 'mijoz__telefon')
    list_select_related = ('mijoz', 'buyurtma')


class MurojaatXabarInline(admin.TabularInline):
    model = MurojaatXabar
    extra = 1


@admin.register(Murojaat)
class MurojaatAdmin(admin.ModelAdmin):
    """Operator shu yerdan javob yozadi — javob mijoz kabinetida ko'rinadi."""
    list_display = ('id', 'mavzu', 'mijoz', 'holat', 'yangilangan')
    list_filter = ('holat',)
    search_fields = ('mavzu', 'mijoz__telefon')
    list_select_related = ('mijoz',)
    inlines = [MurojaatXabarInline]


@admin.register(QongiroqSorovi)
class QongiroqAdmin(admin.ModelAdmin):
    list_display = ('telefon', 'mijoz', 'qulay_vaqt', 'mavzu', 'bajarildi', 'yaratilgan')
    list_filter = ('bajarildi',)
    list_select_related = ('mijoz',)


@admin.register(SavolJavob)
class SavolJavobAdmin(admin.ModelAdmin):
    list_display = ('savol', 'tartib', 'faol')
    list_editable = ('tartib', 'faol')


admin.site.register(KabinetSozlama)
