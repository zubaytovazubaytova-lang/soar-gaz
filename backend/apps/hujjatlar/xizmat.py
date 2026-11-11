"""Hujjatlar mantig'i: kvitansiya va shartnoma yaratish, SMS yuborish, tasdiqlash kodi."""
import re
from datetime import timedelta

from django.conf import settings
from django.core.cache import cache
from django.db import IntegrityError, transaction
from django.utils import timezone
from django.utils.crypto import constant_time_compare, get_random_string, salted_hmac
from rest_framework import serializers

from apps.sms_app.gateway import sms_yubor
from apps.buyurtmalar.serializers import telefon_tozala
from .models import Kvitansiya, Shartnoma, Sozlama, raqam_ber

KOD_MUDDATI_DAQIQA = 10
KOD_MAX_URINISH = 5
KOD_QAYTA_SONIYA = 60
KOD_SOATLIK_LIMIT = 5


class HujjatXato(Exception):
    """Foydalanuvchiga ko'rsatiladigan xato (view 'detail' va status bilan javob beradi)."""

    def __init__(self, detail, status=400):
        super().__init__(detail)
        self.detail = detail
        self.status = status


def pul(n):
    return f'{int(n or 0):,}'.replace(',', ' ')


def sayt_havolasi(yol):
    return settings.SAYT_MANZIL.rstrip('/') + yol


def mijoz_telefoni(qiymat):
    """Mijoz telefoni SMS yuboriladigan raqam: +998XXXXXXXXX."""
    try:
        t = telefon_tozala(qiymat)
    except serializers.ValidationError:
        raise HujjatXato("Telefon raqam noto'g'ri")
    if not re.fullmatch(r'\+998\d{9}', t):
        raise HujjatXato("Telefon raqam +998 bilan boshlanib, 9 raqamdan iborat bo'lishi kerak")
    return t


def buyurtma_manzili(b):
    """Buyurtmadagi turar joy: «Tuman, manzil»."""
    return ', '.join(x for x in [b.tuman, b.manzil] if x)


def aloqa_malumoti(ism, telefon, manzil):
    """Hujjat uchun mijoz ma'lumoti: ism, telefon va TURAR JOY majburiy."""
    ism = (ism or '').strip()[:120]
    manzil = (manzil or '').strip()[:300]
    if not ism:
        raise HujjatXato('Mijoz ismini kiriting')
    if not manzil:
        raise HujjatXato('Mijozning turar joyini (manzilini) kiriting')
    return ism, mijoz_telefoni(telefon), manzil


# ───────────── Mijozni ro'yxatga olish ─────────────

YANGI_MIJOZ_SOATLIK_LIMIT = 30


def mijoz_ochish(xodim, ism, telefon, manzil):
    """Hujjatga yozilgan mijozni ro'yxatga oladi. Qaytaradi: (mijoz, yangi_ochildimi).

    * Mijoz saytda ro'yxatdan o'tmagan bo'lsa — shu ma'lumot bilan hisob ochiladi (parolsiz; keyin
      kabinetga telefon raqamiga keladigan SMS kod bilan kiradi).
    * Hisob bor bo'lsa — mavjud ma'lumotga TEGILMAYDI (xodim kiritgan ism/manzil mijozning o'zi
      kiritganini almashtirmasin), faqat bo'sh maydonlar to'ldiriladi.
    * Telefon xodim yoki administratorga tegishli bo'lsa — rad etiladi.
    """
    from apps.auth_app.models import Foydalanuvchi

    u = Foydalanuvchi.objects.filter(telefon=telefon).first()
    if u is not None:
        if u.rol != 'mijoz':
            raise HujjatXato("Bu telefon raqam mijozga emas, xodim yoki administratorga tegishli. "
                             "Mijozning shaxsiy raqamini kiriting", 409)
        yangilar = []
        if not u.ism:
            u.ism = ism
            yangilar.append('ism')
        if not u.manzil:
            u.manzil = manzil
            yangilar.append('manzil')
        if yangilar:
            u.save(update_fields=yangilar)
        return u, False

    # Xodim bir soatda cheksiz hisob ocholmaydi (noto'g'ri foydalanishdan himoya)
    kalit = f'hujjat:yangi-mijoz:{xodim.pk}'
    soni = cache.get(kalit, 0)
    if soni >= YANGI_MIJOZ_SOATLIK_LIMIT:
        raise HujjatXato("Bir soatda juda ko'p yangi mijoz ro'yxatga olindi. Keyinroq urinib ko'ring", 429)
    cache.set(kalit, soni + 1, 3600)

    u = Foydalanuvchi(telefon=telefon, ism=ism, manzil=manzil, rol='mijoz', holat='faol')
    u.set_unusable_password()
    u.save()
    from apps.auth_app.models import audit_yoz
    audit_yoz(None, 'mijoz_ochildi', f'{ism}, {telefon}', user=xodim)       # kim ro'yxatga olgani jurnalda
    return u, True


# ───────────── Kvitansiya ─────────────

def kvitansiya_qatorlari(tushum):
    """Qog'oz kvitansiyadagi jadval (№, gaz jihoz nomi, narxnoma raqami va ko'rsatgichi, soni, narxi,
    umumiy summa). Buyurtmada xizmatlar tanlangan bo'lsa shular, aks holda ish turi (yoki umumiy nom)."""
    qatorlar = []
    b = tushum.buyurtma
    if b is not None:
        for i, xz in enumerate(b.xizmatlar.select_related('qator'), 1):
            gacha = xz.narx_gacha
            qatorlar.append({
                'nomi': xz.nomi, 'ustun_nomi': xz.ustun_nomi,
                'raqam': str(xz.qator.tartib) if xz.qator_id else '',
                'soni': xz.soni, 'narx_dan': xz.narx_dan, 'narx_gacha': gacha,
                'jami_dan': xz.narx_dan * xz.soni,
                'jami_gacha': (gacha if gacha is not None else xz.narx_dan) * xz.soni,
            })
    if not qatorlar:
        qatorlar.append({'nomi': tushum.ish_turi or "Gaz jihozlariga xizmat ko'rsatish", 'ustun_nomi': '',
                         'raqam': '', 'soni': 1, 'narx_dan': tushum.summa, 'narx_gacha': None,
                         'jami_dan': tushum.summa, 'jami_gacha': tushum.summa})
    return qatorlar


def kvitansiya_yarat(tushum, ism, telefon, manzil):
    """Tushum uchun kvitansiya va mijozni ro'yxatga olish. Qaytaradi: (kvitansiya, yangi_yaratildimi)."""
    if tushum.holat == 'rad':
        raise HujjatXato("Rad etilgan tushum uchun kvitansiya berilmaydi", 409)
    mavjud = Kvitansiya.objects.filter(tushum=tushum).first()
    if mavjud:
        return mavjud, False
    ism, telefon, manzil = aloqa_malumoti(ism, telefon, manzil)
    b = tushum.buyurtma
    shartnoma = b.shartnomalar.exclude(holat='bekor').first() if b else None
    try:
        with transaction.atomic():
            mijoz, yangi_mijoz = mijoz_ochish(tushum.xodim, ism, telefon, manzil)
            kv = Kvitansiya.objects.create(
                tushum=tushum, raqam=raqam_ber('kvitansiya'), xodim=tushum.xodim,
                mijoz=mijoz, yangi_mijoz=yangi_mijoz,
                mijoz_ism=ism, mijoz_telefon=telefon, manzil=manzil,
                buyurtma_id=tushum.buyurtma_id, ish_turi=tushum.ish_turi, summa=tushum.summa,
                usul_nomi=tushum.get_usul_display(), izoh=tushum.izoh,
                qatorlar=kvitansiya_qatorlari(tushum),
                shartnoma_raqami=shartnoma.raqam if shartnoma else '',
                buyurtma_summa=b.tasdiq_summa if b else None)
            # Buyurtma mijozsiz (saytdan emas, xodim yozgan) bo'lsa, endi shu mijozga bog'lanadi
            if b is not None and b.mijoz_id is None:
                b.mijoz = mijoz
                b.save(update_fields=['mijoz', 'yangilangan'])
    except IntegrityError:                       # ikki marta bosilgan: mavjudi qaytariladi
        return Kvitansiya.objects.get(tushum=tushum), False
    return kv, True


def kvitansiya_sms(kv):
    """Mijoz telefoniga kvitansiya raqami va havolasini yuboradi. Muvaffaqiyatli bo'lsa True."""
    if kv.holat != 'amal':
        raise HujjatXato('Bekor qilingan kvitansiya yuborilmaydi', 409)
    matn = (f"Soar Gaz: {pul(kv.summa)} so'm qabul qilindi. "
            f"Kvitansiya {kv.raqam}: {sayt_havolasi('/kvitansiya/' + kv.token + '/')}")
    if kv.yangi_mijoz:
        # Yangi ro'yxatga olingan mijozga shaxsiy kabinet haqida ham xabar beriladi
        matn += f" Shaxsiy kabinet: {sayt_havolasi('/kabinet/')}"
    ok = bool(sms_yubor(kv.mijoz_telefon, matn))
    kv.sms_holat = 'yuborildi' if ok else 'xato'
    kv.sms_vaqti = timezone.now()
    kv.save(update_fields=['sms_holat', 'sms_vaqti'])
    return ok


# ───────────── Shartnoma ─────────────

def xizmatlar_snapshoti(buyurtma):
    return [{'nomi': x.nomi, 'ustun_nomi': x.ustun_nomi, 'soni': x.soni,
             'narx_dan': x.narx_dan, 'narx_gacha': x.narx_gacha}
            for x in buyurtma.xizmatlar.all()]


def xizmatlar_matni(royxat):
    if not royxat:
        return "(xizmatlar ro'yxati shartnoma ilovasida ko'rsatiladi)"
    qatorlar = []
    for i, x in enumerate(royxat, 1):
        narx = pul(x['narx_dan']) if x['narx_gacha'] in (None, x['narx_dan']) else \
            f"{pul(x['narx_dan'])} – {pul(x['narx_gacha'])}"
        nom = x['nomi'] + (f" ({x['ustun_nomi']})" if x['ustun_nomi'] else '')
        qatorlar.append(f"{i}) {nom} × {x['soni']} — {narx} so'm")
    return '\n'.join(qatorlar)


def matn_toldir(shablon, **q):
    """Shablondagi {kalit} o'rinlari to'ldiriladi. Faqat ma'lum kalitlar almashtiriladi —
    shablondagi boshqa figurali qavslar (masalan {X}) o'zgarishsiz qoladi."""
    for kalit, qiymat in q.items():
        shablon = shablon.replace('{' + kalit + '}', str(qiymat))
    return shablon


def shartnoma_yarat(xodim, buyurtma, ism, telefon, manzil):
    sozlama = Sozlama.olish()
    if not sozlama.shartnoma_tasdiqlangan:
        raise HujjatXato("Shartnoma matni hali tasdiqlanmagan. Direktor Django panelida «Hujjat sozlamalari» "
                         "bo'limida kompaniyaning shartnoma matnini kiritib, tasdiqlashi kerak", 409)
    if buyurtma.tasdiq_summa is None:
        raise HujjatXato('Avval buyurtma summasini tasdiqlang, so\'ng shartnoma tuziladi', 409)
    if buyurtma.holat == 'bekor':
        raise HujjatXato('Bekor qilingan buyurtmaga shartnoma tuzilmaydi', 409)
    mavjud = buyurtma.shartnomalar.exclude(holat='bekor').first()
    if mavjud:
        return mavjud, False

    ism, telefon, manzil = aloqa_malumoti(ism, telefon, manzil)
    xizmatlar = xizmatlar_snapshoti(buyurtma)
    raqam = raqam_ber('shartnoma')
    sana = timezone.localtime().strftime('%d.%m.%Y')
    matn = matn_toldir(
        sozlama.shartnoma_matni, raqam=raqam, sana=sana, kompaniya=sozlama.kompaniya_nomi,
        mijoz_ism=ism, mijoz_telefon=telefon, manzil=manzil, xizmatlar=xizmatlar_matni(xizmatlar),
        summa=pul(buyurtma.tasdiq_summa), xodim=(xodim.ism or xodim.telefon))
    try:
        with transaction.atomic():
            mijoz, _yangi = mijoz_ochish(xodim, ism, telefon, manzil)     # shartnoma tuzilgan mijoz ham ro'yxatga olinadi
            sh = Shartnoma.objects.create(
                buyurtma=buyurtma, raqam=raqam, xodim=xodim, mijoz=mijoz, mijoz_ism=ism, mijoz_telefon=telefon,
                manzil=manzil, xizmatlar=xizmatlar, summa=buyurtma.tasdiq_summa, matn=matn)
            if buyurtma.mijoz_id is None:
                buyurtma.mijoz = mijoz
                buyurtma.save(update_fields=['mijoz', 'yangilangan'])
    except IntegrityError:
        return buyurtma.shartnomalar.exclude(holat='bekor').first(), False
    return sh, True


def _kod_xeshi(sh, kod):
    return salted_hmac('shartnoma-kod', f'{sh.pk}:{kod}').hexdigest()


def kod_yubor(sh):
    """Mijoz telefoniga 6 xonali tasdiqlash kodi yuboradi. Qayta yuborish va soatlik limit bor."""
    if sh.tasdiqlanganmi or sh.holat == 'bekor':
        raise HujjatXato('Bu shartnoma uchun kod kerak emas', 409)
    if not cache.add(f'shartnoma:kod:{sh.pk}', 1, KOD_QAYTA_SONIYA):
        raise HujjatXato(f'Kodni qayta yuborish uchun {KOD_QAYTA_SONIYA} soniya kuting', 429)
    soat_kalit = f'shartnoma:kod-soat:{sh.pk}'
    soni = cache.get(soat_kalit, 0)
    if soni >= KOD_SOATLIK_LIMIT:
        raise HujjatXato("Bir soatda eng ko'pi bilan %d marta kod yuboriladi" % KOD_SOATLIK_LIMIT, 429)
    cache.set(soat_kalit, soni + 1, 3600)

    kod = get_random_string(6, '0123456789')
    matn = f"Soar Gaz: shartnoma {sh.raqam} tasdiqlash kodi: {kod}. Kodni faqat xodimga ayting."
    if not sms_yubor(sh.mijoz_telefon, matn):
        cache.delete(f'shartnoma:kod:{sh.pk}')            # xato bo'lsa kutish shart emas
        raise HujjatXato("SMS yuborib bo'lmadi. Telefon raqamni tekshiring yoki shartnomani qog'ozga "
                         "imzolating", 502)
    sh.kod_xesh = _kod_xeshi(sh, kod)
    sh.kod_vaqti = timezone.now()
    sh.kod_urinish = 0
    sh.holat = 'tasdiq_kutilmoqda'
    sh.save(update_fields=['kod_xesh', 'kod_vaqti', 'kod_urinish', 'holat'])


def kod_tekshir(sh, kod):
    """Mijoz aytgan kodni tekshiradi. To'g'ri bo'lsa shartnoma tasdiqlanadi."""
    if sh.holat != 'tasdiq_kutilmoqda' or not sh.kod_xesh:
        raise HujjatXato('Avval mijozga SMS kod yuboring', 409)
    if timezone.now() > sh.kod_vaqti + timedelta(minutes=KOD_MUDDATI_DAQIQA):
        raise HujjatXato('Kod muddati tugagan. Yangi kod yuboring', 409)
    if sh.kod_urinish >= KOD_MAX_URINISH:
        raise HujjatXato("Juda ko'p noto'g'ri urinish. Yangi kod yuboring", 429)
    sh.kod_urinish += 1
    sh.save(update_fields=['kod_urinish'])
    if not constant_time_compare(_kod_xeshi(sh, str(kod or '').strip()), sh.kod_xesh):
        qoldi = KOD_MAX_URINISH - sh.kod_urinish
        raise HujjatXato(f"Kod noto'g'ri. Yana {qoldi} ta urinish qoldi" if qoldi else
                         "Kod noto'g'ri. Yangi kod yuboring", 400)
    sh.holat = 'tasdiqlandi'
    sh.tasdiq_vaqti = timezone.now()
    sh.kod_xesh = ''                                         # ishlatilgan kod qayta yaramasin
    sh.save(update_fields=['holat', 'tasdiq_vaqti', 'kod_xesh'])
    sms_yubor(sh.mijoz_telefon, f"Soar Gaz: shartnoma {sh.raqam} tasdiqlandi. Rahmat!")


def niqoblash(telefon):
    """+998 90 *** ** 67 — hujjatda tasdiqlash qatori uchun."""
    t = str(telefon or '')
    return f'{t[:4]} {t[4:6]} *** ** {t[-2:]}' if len(t) >= 9 else t
