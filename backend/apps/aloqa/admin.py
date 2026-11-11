from django.contrib import admin

from .models import Xabar


@admin.register(Xabar)
class XabarAdmin(admin.ModelAdmin):
    """Yuborilgan xabarlar Django panelida faqat o'qish uchun."""
    list_display = ['yaratilgan', 'xodim', 'matn', 'yuboruvchi', 'oqilgan']
    list_filter = ['oqilgan']
    search_fields = ['xodim__ism', 'xodim__telefon', 'matn']
    date_hierarchy = 'yaratilgan'

    def has_add_permission(self, request): return False
    def has_change_permission(self, request, obj=None): return False
