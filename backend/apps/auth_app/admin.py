from django import forms
from django.contrib import admin, messages
from django.core.exceptions import PermissionDenied
from django.contrib.admin import AllValuesFieldListFilter
from django.contrib.admin.helpers import ActionForm
from django.contrib.auth.admin import UserAdmin
from django.core.cache import cache
from django.utils.html import format_html, format_html_join

from .hududlar import (HUDUDLAR, viloyatlar, viloyat_tumanlari,
                       tuman_viloyati)
from .models import (Foydalanuvchi, Mijoz, Xodim, Sertifikat, IshHaqi, OtpKod, AuditYozuv, LAVOZIM_CHOICES,
                     audit_yoz, kirish_kodi_yasa)


class TaklifliMatnWidget(forms.TextInput):
    """Klaviaturada yozish mumkin bo'lgan maydon + tayyor takliflar ro'yxati.

    Oddiy <select> dan farqi: foydalanuvchi ro'yxatda yo'q qiymatni ham
    yoza oladi. <datalist> esa yozayotganda mos variantlarni taklif qiladi,
    ya'ni ro'yxatdagi qiymatni tanlash ham qulay bo'lib qoladi.
    """

    def __init__(self, takliflar, royxat_id, attrs=None):
        self.takliflar = list(takliflar)
        self.royxat_id = royxat_id
        super().__init__({'list': royxat_id, 'autocomplete': 'off',
                          'size': '40', **(attrs or {})})

    def render(self, name, value, attrs=None, renderer=None):
        maydon = super().render(name, value, attrs, renderer)
        variantlar = format_html_join(
            '', '<option value="{}"></option>', ((t,) for t in self.takliflar))
        return format_html('{}<datalist id="{}">{}</datalist>',
                           maydon, self.royxat_id, variantlar)


class BogliqTumanWidget(forms.Select):
    """Tuman ro'yxati — tanlangan viloyatga qarab filtrlanadi.

    Barcha 203 ta tuman <optgroup> bo'lib chiqadi (viloyat nomi — guruh
    sarlavhasi). Yonidagi kichik skript viloyat maydonini kuzatadi va faqat
    o'sha viloyatning guruhini ko'rsatadi. Guruh sarlavhalari mos-kelishni
    o'zi hujjatlaydi — alohida ma'lumot ro'yxati kerak emas.
    """

    class Media:
        pass

    def render(self, name, value, attrs=None, renderer=None):
        tanlov = super().render(name, value, attrs, renderer)
        maydon_id = (attrs or {}).get('id', f'id_{name}')
        skript = format_html(
            '<script>(function(){{'
            'var t=document.getElementById("{}");'
            'var v=document.getElementById("id_viloyat");'
            'if(!t||!v)return;'
            'function f(tozala){{'
            '  var bor=false;'
            '  Array.prototype.forEach.call(t.getElementsByTagName("optgroup"),'
            '    function(g){{'
            '      var mos=!v.value||g.label===v.value;'
            '      g.style.display=mos?"":"none";'
            '      if(mos)bor=true;'
            '      if(!mos&&tozala&&t.selectedOptions[0]&&'
            '         t.selectedOptions[0].parentNode===g)t.value="";'
            '    }});'
            '  t.disabled=!bor&&!!v.value;'
            '}}'
            'v.addEventListener("change",function(){{f(true);}});'
            'f(false);'
            '}})();</script>', maydon_id)
        return format_html('{}{}', tanlov, skript)


class JoylashuvMixin:
    """Admin formasidagi joylashuv maydonlarini sozlaydi.

    Viloyat va tuman — TANLANADI (ro'yxatdan), chunki ular hisobot va
    filtrlash uchun ishlatiladi. Mahalla/ko'cha esa oddiy matn maydoni:
    ularni ro'yxatga sig'dirib bo'lmaydi.

    Lavozim taklifli matn maydoni bo'lib qoladi — yangi lavozim paydo
    bo'lishi mumkin.
    """

    def formfield_for_dbfield(self, db_field, request, **kwargs):
        if db_field.name == 'viloyat':
            return forms.ChoiceField(
                required=False, label='Viloyat',
                choices=[('', '— tanlang —')] + [(v, v) for v in viloyatlar()],
                help_text='Avval viloyatni tanlang — tuman ro\'yxati shunga '
                          'qarab filtrlanadi',
            )
        if db_field.name == 'tuman':
            return forms.ChoiceField(
                required=False, label='Tuman / shahar',
                choices=[('', '— tanlang —')] + list(HUDUDLAR),
                widget=BogliqTumanWidget,
            )
        if db_field.name == 'lavozim':
            return forms.CharField(
                required=False, max_length=db_field.max_length,
                label='Lavozim',
                help_text="Ro'yxatdan tanlang yoki klaviaturada o'zingiz yozing",
                widget=TaklifliMatnWidget(
                    [nom for nom, _ in LAVOZIM_CHOICES], 'taklif-lavozim'),
            )
        return super().formfield_for_dbfield(db_field, request, **kwargs)

    def get_form(self, request, obj=None, **kwargs):
        """Viloyat va tuman mos kelishini tekshiradi.

        Har bir maydon alohida to'g'ri bo'lishi yetarli emas: "Samarqand
        viloyati" + "Chilonzor tumani" juftligi ikkalasi ham ro'yxatda
        bo'lgani uchun maydon darajasida o'tib ketadi. Shuning uchun
        tekshiruv forma darajasida.
        """
        Asosiy = super().get_form(request, obj, **kwargs)

        class JoylashuvTekshiruvli(Asosiy):
            def clean(self):
                tozalangan = super().clean()
                viloyat = tozalangan.get('viloyat') or ''
                tuman = tozalangan.get('tuman') or ''
                if tuman:
                    if not viloyat:
                        # Viloyat tanlanmagan bo'lsa, tumandan aniqlaymiz
                        tozalangan['viloyat'] = tuman_viloyati(tuman)
                    elif tuman not in viloyat_tumanlari(viloyat):
                        self.add_error(
                            'tuman',
                            f'"{tuman}" — {viloyat} tarkibida bunday tuman yo\'q')
                return tozalangan

        return JoylashuvTekshiruvli


# Eski nom bilan ishlatilgan joylar buzilmasin
YozilaOladiganTanlovMixin = JoylashuvMixin


class XodimQoshishForm(forms.ModelForm):
    """Yangi xodim qo'shish formasi — parolsiz.

    Django'ning standart `UserCreationForm` i parol maydonlarini majburiy
    qiladi. Xodimda parol yo'q: u telefon + kirish kodi bilan kiradi, kodni
    esa tizim o'zi yaratadi. Shuning uchun alohida forma.
    """

    class Meta:
        model = Foydalanuvchi
        fields = ('telefon', 'ism', 'lavozim', 'viloyat', 'tuman', 'mahalla',
                  'ishga_kirgan')


@admin.register(Foydalanuvchi)
class FoydalanuvchiAdmin(YozilaOladiganTanlovMixin, UserAdmin):
    list_display = ['telefon', 'ism', 'rol', 'viloyat', 'tuman', 'holat', 'yaratilgan']
    # `tuman` uchun AllValues: bazada HAQIQATAN uchraydigan qiymatlar
    # ko'rsatiladi. Standart filtr modeldagi `choices` ni olardi — u holda
    # yon panelda 203 ta hudud chiqib ketardi, qo'lda yozilganlari esa
    # umuman ko'rinmasdi.
    list_filter = ['rol', 'holat', ('viloyat', AllValuesFieldListFilter),
                   ('tuman', AllValuesFieldListFilter)]
    search_fields = ['telefon', 'ism']
    ordering = ['-yaratilgan']
    fieldsets = (
        (None, {'fields': ('telefon', 'password')}),
        ('Ma\'lumotlar', {'fields': ('ism', 'viloyat', 'tuman', 'mahalla', 'manzil', 'rol', 'holat')}),
        ('Mijoz profili', {'fields': ('qoshimcha_telefon', 'email', 'mulk_turi', 'moljal')}),
        ('Xodim profili', {'fields': ('lavozim', 'ishga_kirgan')}),
        ('Ruxsatlar', {'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
    )
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('telefon', 'password1', 'password2', 'ism', 'rol',
                       'viloyat', 'tuman', 'mahalla'),
        }),
    )

    def save_model(self, request, obj, form, change):
        """Hisob qayta faollashtirilganda urinishlar hisoblagichini tozalaydi.

        Boshqaruv paneliga 4 marta noto'g'ri parol kiritilsa, hisob 'nofaol'
        bo'ladi (auth_app.views.admin_login). Bu yerdan 'faol' ga qaytarilsa
        hisoblagich ham nolga tushishi kerak — aks holda birinchi xatoda
        darhol qayta bloklanardi.
        """
        super().save_model(request, obj, form, change)
        if obj.holat == 'faol':
            cache.delete(f'admin:urinish:{obj.telefon}')


class XabarForm(ActionForm):
    """Amallar satri yonida xabar matni uchun maydon."""
    matn = forms.CharField(required=False, max_length=500, label='Xabar matni',
                           widget=forms.TextInput(attrs={'size': 50, 'placeholder': 'Faqat "Xabar yuborish" uchun'}))


class SertifikatInline(admin.TabularInline):
    """Xodim sahifasida uning sertifikatlari — xodim kabinetidagi «Sertifikatlarim» shundan to'ladi."""
    model = Sertifikat
    extra = 0
    fields = ('nomi', 'raqami', 'berilgan', 'amal_qiladi')


class IshHaqiInline(admin.TabularInline):
    """Oylik ish haqi — FAQAT tizim egasi ko'radi va kiritadi (direktorga ko'rinmaydi)."""
    model = IshHaqi
    extra = 0
    fields = ('oy', 'asosiy', 'bonus', 'izoh')

    def has_view_permission(self, request, obj=None):
        return request.user.is_superuser

    def has_add_permission(self, request, obj=None):
        return request.user.is_superuser

    def has_change_permission(self, request, obj=None):
        return request.user.is_superuser

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser


@admin.register(Xodim)
class XodimAdmin(YozilaOladiganTanlovMixin, UserAdmin):
    """Xodimlar ro'yxati — yangi xodim faqat shu yerdan qo'shiladi.
    Portalda ro'yxatdan o'tish yo'q, xodim faqat kirish (telefon + parol) qiladi."""
    action_form = XabarForm
    actions = ['xabar_yuborish']
    inlines = [SertifikatInline, IshHaqiInline]

    def has_xabar_permission(self, request):
        return request.user.has_perm('aloqa.add_xabar')

    @admin.action(description='Tanlangan xodimlarga XABAR yuborish (matnni yuqoridagi maydonga yozing)',
                  permissions=['xabar'])
    def xabar_yuborish(self, request, queryset):
        """Xabar xodimning portalida qo'ng'iroqcha belgisida ko'rinadi (faqat FAOL xodimlarga)."""
        from apps.aloqa.models import Xabar

        matn = (request.POST.get('matn') or '').strip()
        if not matn:
            self.message_user(request, 'Xabar matnini yozing (amallar satridagi maydon).', messages.ERROR)
            return
        if len(matn) > 500:
            self.message_user(request, 'Xabar 500 belgidan oshmasligi kerak.', messages.ERROR)
            return
        qabulchilar = list(queryset.filter(rol='xodim', holat='faol'))
        if not qabulchilar:
            self.message_user(request, 'Tanlanganlar orasida faol xodim yo\'q.', messages.WARNING)
            return
        Xabar.objects.bulk_create([Xabar(xodim=x, yuboruvchi=request.user, matn=matn) for x in qabulchilar])
        audit_yoz(request, 'xabar_yuborildi', f'{len(qabulchilar)} ta xodimga: {matn[:120]}')
        self.message_user(request, f'{len(qabulchilar)} ta xodimga xabar yuborildi.', messages.SUCCESS)

    list_display = ['telefon', 'ism', 'lavozim', 'kirish_kodi', 'viloyat', 'tuman', 'holat']
    list_filter = [('lavozim', AllValuesFieldListFilter), 'holat',
                   ('viloyat', AllValuesFieldListFilter),
                   ('tuman', AllValuesFieldListFilter)]
    search_fields = ['telefon', 'ism']
    ordering = ['ism']
    add_form = XodimQoshishForm
    fieldsets = (
        ('Kirish ma\'lumotlari', {
            'fields': ('telefon', 'password'),
            'description': 'Xodim portalga shu telefon raqam va parol bilan kiradi.',
        }),
        ('Shaxsiy ma\'lumotlar', {'fields': ('ism', 'email', 'qoshimcha_telefon')}),
        ('Ish ma\'lumotlari', {'fields': ('lavozim', 'ishga_kirgan', 'holat')}),
        ('Joylashuv', {
            'fields': ('viloyat', 'tuman', 'mahalla'),
            'description': 'Viloyat va tuman ro\'yxatdan tanlanadi. '
                           'Mahalla yoki ko\'chani o\'zingiz yozasiz.',
        }),
    )
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('telefon', 'ism', 'lavozim',
                       'viloyat', 'tuman', 'mahalla', 'ishga_kirgan'),
        }),
    )

    def get_queryset(self, request):
        return Foydalanuvchi.objects.filter(rol='xodim')

    # Direktor ("Direktor" guruhi) xodim qo'shadi va ma'lumotini tahrirlaydi, lekin xodimni
    # nofaol/faol qila olmaydi va unga parol qo'ya olmaydi (parol orqali xodim hisobiga kirish
    # mumkin bo'lardi) — bu boshqaruv paneli API'sidagi qoida bilan bir xil: faqat tizim egasi.
    def get_readonly_fields(self, request, obj=None):
        yozilmas = list(super().get_readonly_fields(request, obj))
        if obj is not None and not request.user.is_superuser:
            yozilmas.append('holat')
        return yozilmas

    def user_change_password(self, request, id, form_url=''):
        if not request.user.is_superuser:
            raise PermissionDenied
        return super().user_change_password(request, id, form_url)

    def save_model(self, request, obj, form, change):
        obj.rol = 'xodim'
        # Xodimda parol yo'q — u telefon + kirish kodi bilan kiradi
        if not obj.kirish_kodi:
            while True:
                kod = kirish_kodi_yasa()
                if not Foydalanuvchi.objects.filter(kirish_kodi=kod).exists():
                    break
            obj.kirish_kodi = kod
        if not change:
            obj.set_unusable_password()
        super().save_model(request, obj, form, change)
        self.message_user(
            request, f'{obj.ism or obj.telefon} — kirish kodi: {obj.kirish_kodi}')


@admin.register(Mijoz)
class MijozAdmin(admin.ModelAdmin):
    """Mijozlar bazasi (CRM) — FAQAT O'QISH. Parol shifri ko'rinmaydi: sahifada faqat
    quyidagi maydonlar bor."""
    list_display = ['telefon', 'ism', 'viloyat', 'tuman', 'mulk_turi', 'buyurtmalar_soni', 'yaratilgan']
    list_filter = ['mulk_turi', ('viloyat', AllValuesFieldListFilter), ('tuman', AllValuesFieldListFilter)]
    search_fields = ['telefon', 'ism', 'qoshimcha_telefon']
    ordering = ['-yaratilgan']
    date_hierarchy = 'yaratilgan'
    fields = ['telefon', 'ism', 'viloyat', 'tuman', 'mahalla', 'manzil', 'moljal', 'qoshimcha_telefon',
              'email', 'mulk_turi', 'yaratilgan']
    readonly_fields = fields

    def get_queryset(self, request):
        from django.db.models import Count
        return super().get_queryset(request).annotate(_buyurtmalar=Count('buyurtmalar'))

    @admin.display(description='Buyurtmalar', ordering='_buyurtmalar')
    def buyurtmalar_soni(self, obj):
        return obj._buyurtmalar

    def has_add_permission(self, request): return False
    def has_change_permission(self, request, obj=None): return False
    def has_delete_permission(self, request, obj=None): return False


@admin.register(AuditYozuv)
class AuditYozuvAdmin(admin.ModelAdmin):
    """Faoliyat jurnali — FAQAT O'QISH uchun.

    Qo'shish, tahrirlash va o'chirish o'chirilgan: jurnalni tahrirlash mumkin
    bo'lsa, u dalil sifatida hech qanday qiymatga ega bo'lmaydi.
    """
    list_display = ['vaqt', 'kim_ism', 'kim_telefon', 'amal', 'tafsilot', 'ip']
    list_filter = ['amal', 'vaqt']
    search_fields = ['kim_ism', 'kim_telefon', 'tafsilot']
    date_hierarchy = 'vaqt'

    def has_add_permission(self, request): return False
    def has_change_permission(self, request, obj=None): return False
    def has_delete_permission(self, request, obj=None): return False


@admin.register(OtpKod)
class OtpKodAdmin(admin.ModelAdmin):
    list_display = ['telefon', 'kod', 'ishlatildi', 'yaratilgan']
    list_filter = ['ishlatildi']
