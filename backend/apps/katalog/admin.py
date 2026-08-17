import re

from django import forms
from django.contrib import admin, messages
from django.shortcuts import redirect, render
from django.urls import path, reverse
from django.utils.html import format_html

from .models import (KATEGORIYA_CHOICES, VIDEO_KENGAYTMALARI, KatalogHujjat,
                     KatalogMedia, KatalogNarx)


@admin.register(KatalogNarx)
class KatalogNarxAdmin(admin.ModelAdmin):
    # Narxni ro'yxatning o'zidan tahrirlash mumkin — alohida sahifa ochish shart emas
    list_display = ('nomi', 'kategoriya', 'narx', 'birlik', 'sorovnoma', 'faol', 'yangilangan')
    list_editable = ('narx', 'birlik', 'sorovnoma', 'faol')
    list_filter = ('kategoriya', 'faol', 'sorovnoma')
    search_fields = ('nomi', 'kalit')
    ordering = ('kategoriya', 'nomi')
    readonly_fields = ('yangilangan',)

    fieldsets = (
        ('Mahsulot', {
            'fields': ('kalit', 'kategoriya', 'nomi'),
            'description': "«Kalit» index.html dagi KAT_DATA item.kalit bilan "
                           "aynan bir xil bo'lishi kerak — sayt narxni shu orqali topadi.",
        }),
        ('Narx', {
            'fields': ('narx', 'birlik', 'sorovnoma', 'faol'),
            'description': "Narx so'mda kiritiladi (masalan 850000). "
                           "«So'rovnoma» belgilansa, narx o'rniga shu so'z chiqadi.",
        }),
        ('Xizmat', {'fields': ('yangilangan',)}),
    )


@admin.register(KatalogHujjat)
class KatalogHujjatAdmin(admin.ModelAdmin):
    list_display = ('nom', 'tur', 'kalit', 'faol', 'yuklangan')
    list_editable = ('faol',)
    list_filter = ('tur', 'faol')
    search_fields = ('nom', 'kalit')
    readonly_fields = ('yuklangan',)

    fieldsets = (
        ('Hujjat', {
            'fields': ('kalit', 'tur', 'nom', 'fayl', 'faol', 'yuklangan'),
            'description': "Fayl <b>hujjatlar_maxfiy/</b> papkasiga saqlanadi — unga "
                           "to'g'ridan-to'g'ri URL orqali kirib bo'lmaydi. Saytda hujjat "
                           "faqat 5 daqiqa amal qiladigan imzolangan havola orqali ochiladi, "
                           "rasmlarga esa server suv belgisini singdiradi.",
        }),
    )


# ──────────────────────────────────────────────────────────────
#  Katalog mediasi — 4 bo'lim bo'yicha rasm va videolar
# ──────────────────────────────────────────────────────────────

def _videomi(nom):
    return nom.lower().endswith(VIDEO_KENGAYTMALARI)


def _kalitni_taxmin_qil(fayl_nomi):
    """«ugop-16-video.mp4» yoki «ugop-16-3.jpg» dan «ugop-16» ni ajratadi."""
    asos = re.sub(r'\.[^.]+$', '', fayl_nomi)          # kengaytmani olib tashlash
    asos = re.sub(r'-(video|\d+)$', '', asos)          # -video yoki -3 qo'shimchasi
    return asos


def _keyingi_tartib(kalit, video):
    """Shu mahsulotning oxirgi media raqamidan keyingi tartib."""
    if video:
        return 900
    mavjud = KatalogMedia.objects.filter(kalit=kalit).exclude(
        fayl__iendswith='.mp4').exclude(fayl__iendswith='.webm')
    eng_katta = max([m.tartib for m in mavjud], default=0)
    return eng_katta + 10


class MultiFileInput(forms.ClearableFileInput):
    allow_multiple_selected = True


class MultiFileField(forms.FileField):
    """Bir necha faylni qabul qiladigan maydon.

    Oddiy FileField ro'yxatni tushunmaydi — har bir faylni alohida tekshiramiz.
    """

    def __init__(self, *args, **kwargs):
        kwargs.setdefault('widget', MultiFileInput(attrs={'multiple': True}))
        super().__init__(*args, **kwargs)

    def clean(self, data, initial=None):
        bitta = super().clean
        if isinstance(data, (list, tuple)):
            return [bitta(d, initial) for d in data]
        return bitta(data, initial)


class KoplabYuklashForm(forms.Form):
    kalit = forms.CharField(
        max_length=80, label='Mahsulot kaliti',
        help_text="Bo'sh qoldirilsa — fayl nomidan avtomatik aniqlanadi "
                  "(masalan «ugop-16-3.jpg» → «ugop-16»).",
        required=False)
    bolim = forms.ChoiceField(
        choices=[('', '— kalitdan avtomatik —')] + list(KATEGORIYA_CHOICES),
        label="Bo'lim", required=False,
        help_text="Bo'sh qoldirilsa — shu kalitdagi mavjud mediadan olinadi.")
    fayllar = MultiFileField(
        label='Fayllar', required=False,
        help_text='Bir necha rasm va videoni birdan tanlash mumkin (Ctrl bilan).')

    def clean(self):
        tozalangan = super().clean()
        if not tozalangan.get('bolim') and not tozalangan.get('kalit'):
            # Ikkalasi ham bo'sh — fayl nomiga tayanamiz, bu yerda xato emas
            pass
        return tozalangan


class BolimTuriFiltri(admin.SimpleListFilter):
    """Rasm / video bo'yicha filtr (DB maydoni emas — fayl kengaytmasidan)."""
    title = 'Fayl turi'
    parameter_name = 'tur'

    def lookups(self, request, model_admin):
        return [('rasm', 'Rasm'), ('video', 'Video')]

    def queryset(self, request, queryset):
        if self.value() == 'video':
            return queryset.filter(fayl__iendswith='.mp4') | queryset.filter(fayl__iendswith='.webm')
        if self.value() == 'rasm':
            return queryset.exclude(fayl__iendswith='.mp4').exclude(fayl__iendswith='.webm')
        return queryset


@admin.register(KatalogMedia)
class KatalogMediaAdmin(admin.ModelAdmin):
    list_display = ('korinish', 'kalit', 'bolim', 'fayl_turi', 'tartib', 'faol', 'yuklangan')
    list_display_links = ('kalit',)
    list_editable = ('bolim', 'tartib', 'faol')
    list_filter = ('bolim', BolimTuriFiltri, 'faol')
    search_fields = ('kalit', 'fayl')
    readonly_fields = ('yuklangan', 'katta_korinish', 'yol_matni')
    list_per_page = 40

    fieldsets = (
        ('Mahsulot', {
            'fields': ('kalit', 'bolim'),
            'description': "«Kalit» — index.html dagi KAT_DATA item.kalit bilan aynan bir xil "
                           "(masalan <b>ugop-16-gorelka</b>). Sayt mediani shu orqali topadi.<br>"
                           "«Bo'lim» — mahsulot qaysi katalogda ko'rinsa, o'sha: "
                           "Quvurlar / Hisoblagichlar / Ventillar / Gaz jihozlari (gorelkalar).",
        }),
        ('Fayl', {
            'fields': ('fayl', 'katta_korinish', 'yol_matni', 'tartib', 'faol', 'yuklangan'),
            'description': "Fayl loyihaning <b>images/jihozlar/</b> papkasiga saqlanadi.<br>"
                           "<b>Tartib:</b> kichik raqam oldinda. Birinchi o'rindagi rasm "
                           "katalog kartasida ko'rinadi — mahsulotning eng yaxshi surati bo'lsin.<br>"
                           "<b>Video</b> tartib raqamidan qat'i nazar har doim oxirida turadi.",
        }),
    )

    @admin.display(description='Ko\'rinish')
    def korinish(self, obj):
        if obj.videomi:
            return format_html(
                '<span style="font-size:22px" title="{}">🎬</span>', obj.fayl.name)
        return format_html(
            '<img src="{}" style="height:44px;width:64px;object-fit:cover;'
            'border-radius:4px;border:1px solid #ddd">', obj.fayl.url)

    @admin.display(description='Turi')
    def fayl_turi(self, obj):
        return 'Video' if obj.videomi else 'Rasm'

    @admin.display(description='Ko\'rib chiqish')
    def katta_korinish(self, obj):
        if not obj.pk:
            return '—'
        if obj.videomi:
            return format_html(
                '<video src="{}" controls muted style="max-width:420px;border-radius:6px"></video>',
                obj.fayl.url)
        return format_html(
            '<img src="{}" style="max-width:420px;border-radius:6px">', obj.fayl.url)

    @admin.display(description='Saytdagi yo\'l')
    def yol_matni(self, obj):
        return obj.yol if obj.pk else '—'

    # ── Yangi media qo'shishda tartibni avtomatik qo'yish ──
    def save_model(self, request, obj, form, change):
        if not change and 'tartib' not in form.changed_data:
            obj.tartib = _keyingi_tartib(obj.kalit, obj.videomi)
        super().save_model(request, obj, form, change)

    # ── «Ko'plab yuklash» sahifasi ──
    def get_urls(self):
        return [
            path('koplab-yuklash/', self.admin_site.admin_view(self.koplab_yuklash),
                 name='katalog_katalogmedia_koplab_yuklash'),
        ] + super().get_urls()

    def changelist_view(self, request, extra_context=None):
        extra_context = extra_context or {}
        extra_context['koplab_yuklash_url'] = reverse(
            'admin:katalog_katalogmedia_koplab_yuklash')
        return super().changelist_view(request, extra_context)

    def koplab_yuklash(self, request):
        """Bir necha rasm/videoni birdan yuklash.

        Kalit va bo'lim bo'sh qoldirilsa — fayl nomidan va mavjud mediadan
        aniqlanadi. Tartib avtomatik: rasmlar 10, 20, 30…, video 900
        (ya'ni video har doim oxirida qoladi).
        """
        if request.method == 'POST':
            form = KoplabYuklashForm(request.POST, request.FILES)
            fayllar = request.FILES.getlist('fayllar')
            if form.is_valid() and fayllar:
                natija = self._fayllarni_saqla(
                    request, fayllar,
                    form.cleaned_data['kalit'].strip(),
                    form.cleaned_data['bolim'])
                if natija:
                    return redirect('admin:katalog_katalogmedia_changelist')
            elif not fayllar:
                messages.error(request, 'Hech qanday fayl tanlanmadi.')
        else:
            form = KoplabYuklashForm()

        kalitlar = sorted(set(
            list(KatalogNarx.objects.values_list('kalit', flat=True))
            + list(KatalogMedia.objects.values_list('kalit', flat=True))))

        return render(request, 'admin/katalog/koplab_yuklash.html', {
            **self.admin_site.each_context(request),
            'title': "Ko'plab media yuklash",
            'form': form,
            'kalitlar': kalitlar,
            'opts': self.model._meta,
        })

    def _fayllarni_saqla(self, request, fayllar, kalit_kiritilgan, bolim_kiritilgan):
        # Rasmlar avval, video oxirida — tartib shunga qarab beriladi
        fayllar = sorted(fayllar, key=lambda f: (_videomi(f.name), f.name))
        qoshildi, xato = 0, 0

        for f in fayllar:
            kalit = kalit_kiritilgan or _kalitni_taxmin_qil(f.name)

            bolim = bolim_kiritilgan
            if not bolim:
                qoshni = KatalogMedia.objects.filter(kalit=kalit).first()
                bolim = qoshni.bolim if qoshni else ''
            if not bolim:
                messages.error(
                    request,
                    f'«{f.name}» — bo\'lim aniqlanmadi. «{kalit}» kaliti uchun '
                    f'hali media yo\'q, shuning uchun bo\'limni qo\'lda tanlang.')
                xato += 1
                continue

            obj = KatalogMedia(kalit=kalit, bolim=bolim,
                               tartib=_keyingi_tartib(kalit, _videomi(f.name)))
            obj.fayl.save(f.name, f, save=False)
            try:
                obj.full_clean()
            except forms.ValidationError as e:
                obj.fayl.delete(save=False)
                messages.error(request, f'«{f.name}» — {"; ".join(e.messages)}')
                xato += 1
                continue
            obj.save()
            qoshildi += 1

        if qoshildi:
            messages.success(
                request, f'{qoshildi} ta fayl yuklandi. Rasmlar tartib bilan, '
                         f'video oxirida joylashtirildi.')
        return qoshildi and not xato


