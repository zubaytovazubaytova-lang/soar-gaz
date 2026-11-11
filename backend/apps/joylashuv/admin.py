from django.contrib import admin

from .models import Nuqta, Rozilik, Smena


class FaqatOqish(admin.ModelAdmin):
    """Joylashuv ma'lumoti Django panelida o'zgartirilmaydi — faqat ko'riladi."""
    def has_add_permission(self, request): return False
    def has_change_permission(self, request, obj=None): return False


@admin.register(Rozilik)
class RozilikAdmin(FaqatOqish):
    list_display = ['xodim', 'versiya', 'vaqt', 'ip']
    search_fields = ['xodim__ism', 'xodim__telefon']


@admin.register(Smena)
class SmenaAdmin(FaqatOqish):
    list_display = ['xodim', 'boshlandi', 'tugadi', 'tugash_sababi']
    list_filter = ['tugash_sababi']
    search_fields = ['xodim__ism', 'xodim__telefon']
    date_hierarchy = 'boshlandi'


@admin.register(Nuqta)
class NuqtaAdmin(FaqatOqish):
    list_display = ['xodim', 'vaqt', 'lat', 'lng', 'aniqlik']
    search_fields = ['xodim__ism', 'xodim__telefon']
    date_hierarchy = 'vaqt'
