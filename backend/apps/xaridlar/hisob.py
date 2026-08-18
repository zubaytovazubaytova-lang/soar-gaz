"""Xarid summasini hisoblash — yagona manba.

Frontend ham xuddi shu qoidalarni ko'rsatadi (index.html: XARID_NARX),
lekin buyurtmaga yoziladigan raqamlar faqat shu yerdan chiqadi.
"""
from django.conf import settings
from django.utils.translation import gettext as _

from .models import Promokod


def hududlar():
    return getattr(settings, 'YETKAZISH_HUDUDLAR', {}) or {}


def muddat_matni(soat):
    """Soatni mijozga tushunarli matnga o'giradi."""
    if soat <= 0:
        return ''
    if soat < 24:
        return f"{soat} soat ichida"
    kun = soat // 24
    return "1 kun ichida" if kun == 1 else f"{kun} kun ichida"


def hudud_yetkazish(tuman):
    """Tuman bo'yicha (narx, muddat_matni) qaytaradi.

    Tuman ko'rsatilmagan yoki ro'yxatda bo'lmasa — standart narx ishlatiladi.
    """
    h = hududlar().get(tuman)
    if not h:
        return getattr(settings, 'YETKAZISH_NARXI', 30000), ''
    return h['narx'], muddat_matni(h['soat'])


def narx_qoidalari():
    bolib = getattr(settings, 'BOLIB_TOLASH', {}) or {}
    return {
        'ornatish': getattr(settings, 'ORNATISH_NARXI', 250000),
        'yetkazish': getattr(settings, 'YETKAZISH_NARXI', 30000),
        'bepul_chegara': getattr(settings, 'BEPUL_YETKAZISH_CHEGARASI', 1000000),
        # Bo'lib to'lash shartlari — frontend shu ro'yxatdan variantlarni chizadi
        'bolib': [{'oy': oy, 'ustama': ustama} for oy, ustama in sorted(bolib.items())],
        'bolib_eng_kam': getattr(settings, 'BOLIB_ENG_KAM_SUMMA', 0),
        # Hudud jadvali — checkoutda tuman tanlanganda narx/muddat darhol ko'rinadi
        'hududlar': [
            {'tuman': t, 'narx': v['narx'], 'soat': v['soat'], 'muddat': muddat_matni(v['soat'])}
            for t, v in hududlar().items()
        ],
        'filial': {
            'manzil': getattr(settings, 'FILIAL_MANZILI', ''),
            'soat': getattr(settings, 'FILIAL_TAYYOR_SOAT', 0),
            'muddat': muddat_matni(getattr(settings, 'FILIAL_TAYYOR_SOAT', 0)),
        },
        'urinishlar': getattr(settings, 'YETKAZISH_URINISHLAR', 3),
    }


def bolib_hisobla(jami, oy):
    """Bo'lib to'lash: (umumiy_summa, oylik_tolov, xato) qaytaradi."""
    bolib = getattr(settings, 'BOLIB_TOLASH', {}) or {}
    eng_kam = getattr(settings, 'BOLIB_ENG_KAM_SUMMA', 0)

    if oy not in bolib:
        return jami, 0, _("Bunday bo'lib to'lash muddati mavjud emas")
    if eng_kam and jami < eng_kam:
        kerak = f"{eng_kam:,}".replace(',', ' ')
        return jami, 0, _("Bo'lib to'lash %(summa)s so'mdan yuqori "
                              "buyurtmalarga beriladi") % {'summa': kerak}

    umumiy = jami + jami * bolib[oy] // 100
    # Oylik to'lovni yuqoriga yaxlitlaymiz, oxirgi oy qolgan farqni yopadi
    oylik = -(-umumiy // oy)
    return umumiy, oylik, ''


def promokod_topish(kod):
    if not kod:
        return None
    return Promokod.objects.filter(kod=kod.strip().upper()).first()


def hisobla(qatorlar, yetkazish='kuryer', ornatish=False, kod='', tuman=''):
    """Buyurtma summasini hisoblaydi.

    qatorlar — [{'price': int, 'qty': int}, ...]

    Tartib: mahsulotlar → chegirma → yetkazish (chegirmadan keyingi
    summaga qarab bepul bo'lishi mumkin) → o'rnatish.

    Qaytadi: (natija_dict, promokod_obyekti_yoki_None, xato_matni)
    """
    q = narx_qoidalari()
    mahsulotlar = sum(int(x['price']) * int(x['qty']) for x in qatorlar)

    # ── Chegirma ──
    chegirma, promo, xato = 0, None, ''
    if kod:
        promo = promokod_topish(kod)
        if not promo:
            xato = _('Bunday promokod topilmadi')
        else:
            chegirma, xato = promo.tekshir(mahsulotlar)
            if xato:
                promo = None

    oraliq = mahsulotlar - chegirma

    # ── Yetkazish: narx va muddat hududga qarab ──
    if yetkazish == 'kuryer':
        hudud_narxi, muddat = hudud_yetkazish(tuman)
        bepul = q['bepul_chegara'] and oraliq >= q['bepul_chegara']
        yetkazish_narxi = 0 if bepul else hudud_narxi
    else:
        yetkazish_narxi = 0  # filialdan olib ketish
        muddat = q['filial']['muddat']

    ornatish_narxi = q['ornatish'] if ornatish else 0

    return {
        'mahsulotlar': mahsulotlar,
        'chegirma': chegirma,
        'promokod': promo.kod if promo else '',
        'yetkazish_narxi': yetkazish_narxi,
        'yetkazish_muddati': muddat,
        'ornatish_narxi': ornatish_narxi,
        'jami': oraliq + yetkazish_narxi + ornatish_narxi,
    }, promo, xato
