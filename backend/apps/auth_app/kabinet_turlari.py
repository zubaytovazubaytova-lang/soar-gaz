"""Xodim kabineti tuzilmasi: lavozimga qarab menyu.

Kirish hamma uchun bir xil (telefon + admin bergan kod) — farq faqat KABINETNING
ichida: qaysi bo'limlar va qanday tartibda ko'rinishi. Lavozim matni erkin
yoziladi (admin panelida), shuning uchun tur matn bo'yicha aniqlanadi; tanilmagan
lavozim «oddiy xodim» kabinetini oladi — ya'ni mavjud to'liq kabinet o'zgarmaydi.

Bo'lim kalitlari xodimlar.html dagi `data-page` qiymatlari bilan bir xil.
Frontend menyuni shu ro'yxatdan quradi (tartibi ham shu yerdan).

DIQQAT: menyu o'zi himoya emas. Ammo ish bajaradigan bo'limlar serverda ham
yopilgan: Kadrlar (`apps/kadrlar`, tushum qabuli), qo'ng'iroq vazifasi
(`apps/buyurtmalar/operator.py`) va hujjatlar (`apps/hujjatlar/ish.py`) — ular `kadrmi()` /
`qongiroq_huquqi()` / `hujjatchimi()` ni ishlatadi.

Turlar (alohida «Call center» yoki «Servis operatori» kabineti YO'Q — bu vazifalar odamlarga biriktirilgan):
  oddiy    — montaj ustalari, metrolog, loyihachi va boshqa barcha xodimlar (to'liq kabinet);
  qongiroq — Nargiza: oddiy xodim kabineti + QO'NG'IROQ VAZIFASI («op-arizalar», «op-qongiroq»);
  hujjat   — Ferangiz (mehnat muhofazasi muhandisi): oddiy xodim kabineti + mijozlardan kelgan
             metrologiya arizalari / loyiha va metrologiya buyurtmalari uchun hujjat tayyorlash va mijozga yuborish;
  kadrlar  — Ruxsora (Kadrlar mutaxassisi): davomat, hisobotlar, hujjatlar, xodimlardan pul qabul qilish
             VA o'sha QO'NG'IROQ VAZIFASI.

QO'NG'IROQ VAZIFASI (Ruxsora va Nargiza bir xil bajaradi): aholi va tashkilot (ulgurji) arizalarini
qabul qilish, xodimga yo'naltirish (eng yaqin xodimni topish ham), chiquvchi qo'ng'iroqlar jurnali, bajarilishini nazorat.
"""

ODDIY = 'oddiy'
QONGIROQ = 'qongiroq'
KADRLAR = 'kadrlar'
HUJJAT = 'hujjat'

_ODDIY_BOLIMLAR = ['tasks', 'history', 'certs', 'cash', 'docs', 'price', 'pay', 'team', 'settings']

# Bo'limlar (kalit tartibi = menyu tartibi)
BOLIMLAR = {
    # Montaj ustalari, loyihachi, metrolog va boshqa tanilmagan lavozimlar: to'liq oddiy kabinet.
    ODDIY: ['overview'] + _ODDIY_BOLIMLAR,
    # Oddiy xodim kabineti + qo'ng'iroq vazifasi
    QONGIROQ: ['overview', 'op-arizalar', 'op-qongiroq', 'topshiriq'] + _ODDIY_BOLIMLAR,
    # Oddiy xodim kabineti + «hj-ishlar»: mijozlardan kelgan ishlar va ular uchun hujjat tayyorlash/yuborish
    # «Pul tushumi» (cash) YO'Q: hujjat tayyorlovchi mijozdan pul olmaydi.
    # «hj-yuborish»: tayyor hujjatlarni mijozga yuborish (hamma ishlar bo'yicha bitta ro'yxat).
    HUJJAT: ['overview', 'hj-ishlar', 'hj-yuborish', 'topshiriq'] + [b for b in _ODDIY_BOLIMLAR if b != 'cash'],
    # Kadrlar: xodimlar nazorati. Mijozdan pul olmaydi — aksincha, har bir xodim topshirgan pulni
    # QABUL QILADI («kadr-tushum»). Qo'ng'iroq vazifasi ham shu kabinetda.
    KADRLAR: ['overview', 'op-arizalar', 'op-qongiroq', 'topshiriq', 'kadr-davomat', 'kadr-hisobot', 'kadr-tushum', 'kadr-hujjat',
              'certs', 'pay', 'team', 'settings'],
}


def kabinet_turi(lavozim):
    """Lavozim matnidan kabinet turi ('oddiy' | 'qongiroq' | 'hujjat' | 'kadrlar')."""
    matn = (lavozim or '').strip().lower()
    if 'kadr' in matn:          # «Kadrlar bo'yicha mutaxassis», «Kadrlar bo'limi boshlig'i» ...
        return KADRLAR
    if 'call' in matn or 'qo\'ng\'iroq' in matn or 'qongiroq' in matn:     # «Call center operatori» ...
        return QONGIROQ
    if 'muhofaza' in matn or 'texnika xavfsizligi' in matn or 'hujjat' in matn:   # mehnat muhofazasi muhandisi
        return HUJJAT
    return ODDIY


def kabinet_malumoti(lavozim):
    """Frontendga beriladigan tuzilma: {'tur': ..., 'bolimlar': [...]}."""
    tur = kabinet_turi(lavozim)
    return {'tur': tur, 'bolimlar': list(BOLIMLAR[tur])}


def vazifa_olishi_mumkin(lavozim):
    """Xodimga buyurtma biriktirsa bo'ladimi (u mijoz oldiga borib ishlaydigan xodimmi).

    Ariza qabul qiluvchilar (Ruxsora, Nargiza) ish bajarmaydi — ularga vazifa BERILMAYDI va «eng yaqin xodim»
    qidiruvida ular chiqmaydi, garchi Nargizaning kabinetida «Vazifalarim» bo'limi bo'lsa ham."""
    return kabinet_turi(lavozim) in (ODDIY, HUJJAT)


def faol_xodimmi(user):
    return getattr(user, 'rol', None) == 'xodim' and getattr(user, 'holat', '') == 'faol'


def kadrmi(user):
    """Kadrlar mutaxassisi (faol xodim, kabinet turi «kadrlar»)."""
    return faol_xodimmi(user) and kabinet_turi(user.lavozim) == KADRLAR


def qongiroq_huquqi(user):
    """Qo'ng'iroq vazifasi (arizalar, yo'naltirish, qo'ng'iroqlar jurnali): Kadrlar mutaxassisi va Nargiza."""
    return faol_xodimmi(user) and kabinet_turi(user.lavozim) in (KADRLAR, QONGIROQ)


def hujjatchimi(user):
    """Hujjatlar bilan ishlovchi xodim (faol, kabinet turi «hujjat»): mijozlardan kelgan ishlar uchun hujjat tayyorlaydi."""
    return faol_xodimmi(user) and kabinet_turi(user.lavozim) == HUJJAT
