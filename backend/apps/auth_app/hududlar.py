"""O'zbekiston Respublikasi hududlari — butun platforma uchun yagona manba.

Ilgari bu ro'yxat faqat Buxoro viloyatining 11 ta tumanidan iborat edi.
Platforma respublika miqyosiga chiqqach, barcha 14 ta hudud (12 viloyat +
Qoraqalpog'iston Respublikasi + Toshkent shahri) qo'shildi.

Saqlanadigan qiymat — tuman/shahar nomi (masalan "G'ijduvon tumani").
Viloyat nomi faqat guruh sarlavhasi bo'lib, bazaga yozilmaydi. Shu sababli
eski yozuvlar ("Buxoro shahri", "Kogon shahri") o'zgarishsiz ishlayveradi.

Frontend ro'yxatlarini shu fayldan qayta yaratish uchun:
    python manage.py hududlar_yangila
"""

# Viloyat -> tuman/shaharlar. Tartib: Qoraqalpog'iston, keyin alifbo bo'yicha
# viloyatlar, oxirida Toshkent shahri.
HUDUDLAR_XARITASI = [
    ("Qoraqalpog'iston Respublikasi", [
        'Nukus shahri', 'Amudaryo tumani', 'Beruniy tumani', "Bo'zatov tumani",
        'Chimboy tumani', "Ellikqal'a tumani", 'Kegeyli tumani',
        "Mo'ynoq tumani", 'Nukus tumani', "Qanliko'l tumani",
        "Qo'ng'irot tumani", "Qorao'zak tumani", 'Shumanay tumani',
        "Taxtako'pir tumani", "To'rtko'l tumani", "Xo'jayli tumani",
    ]),
    ('Andijon viloyati', [
        'Andijon shahri', 'Xonobod shahri', 'Andijon tumani', 'Asaka tumani',
        'Baliqchi tumani', "Bo'ston tumani", 'Buloqboshi tumani',
        'Izboskan tumani', 'Jalaquduq tumani', "Qo'rg'ontepa tumani",
        'Marhamat tumani', "Oltinko'l tumani", 'Paxtaobod tumani',
        'Shahrixon tumani', "Ulug'nor tumani", "Xo'jaobod tumani",
    ]),
    ('Buxoro viloyati', [
        'Buxoro shahri', 'Kogon shahri', 'Buxoro tumani', "G'ijduvon tumani",
        'Jondor tumani', 'Kogon tumani', 'Olot tumani', 'Peshku tumani',
        "Qorako'l tumani", 'Qorovulbozor tumani', 'Romitan tumani',
        'Shofirkon tumani', 'Vobkent tumani',
    ]),
    ("Farg'ona viloyati", [
        "Farg'ona shahri", "Marg'ilon shahri", "Qo'qon shahri",
        'Quvasoy shahri', 'Beshariq tumani', "Bog'dod tumani",
        'Buvayda tumani', "Dang'ara tumani", "Farg'ona tumani",
        'Furqat tumani', 'Oltiariq tumani', "Qo'shtepa tumani", 'Quva tumani',
        'Rishton tumani', "So'x tumani", 'Toshloq tumani',
        "Uchko'prik tumani", "O'zbekiston tumani", 'Yozyovon tumani',
    ]),
    ('Jizzax viloyati', [
        'Jizzax shahri', 'Arnasoy tumani', 'Baxmal tumani', "Do'stlik tumani",
        'Forish tumani', "G'allaorol tumani", "Mirzacho'l tumani",
        'Paxtakor tumani', 'Sharof Rashidov tumani', 'Yangiobod tumani',
        'Zafarobod tumani', 'Zarbdor tumani', 'Zomin tumani',
    ]),
    ('Namangan viloyati', [
        'Namangan shahri', 'Chortoq tumani', 'Chust tumani',
        'Davlatobod tumani', 'Kosonsoy tumani', 'Mingbuloq tumani',
        'Namangan tumani', 'Norin tumani', 'Pop tumani',
        "To'raqo'rg'on tumani", "Uchqo'rg'on tumani", 'Uychi tumani',
        "Yangiqo'rg'on tumani",
    ]),
    ('Navoiy viloyati', [
        'Navoiy shahri', 'Zarafshon shahri', 'Karmana tumani',
        'Konimex tumani', 'Navbahor tumani', 'Nurota tumani',
        'Qiziltepa tumani', 'Tomdi tumani', 'Uchquduq tumani',
        'Xatirchi tumani',
    ]),
    ('Qashqadaryo viloyati', [
        'Qarshi shahri', 'Shahrisabz shahri', 'Chiroqchi tumani',
        'Dehqonobod tumani', "G'uzor tumani", 'Kasbi tumani',
        'Kitob tumani', 'Koson tumani', "Ko'kdala tumani",
        'Mirishkor tumani', 'Muborak tumani', 'Nishon tumani',
        'Qamashi tumani', 'Qarshi tumani', 'Shahrisabz tumani',
        "Yakkabog' tumani",
    ]),
    ('Samarqand viloyati', [
        'Samarqand shahri', "Kattaqo'rg'on shahri", "Bulung'ur tumani",
        'Ishtixon tumani', 'Jomboy tumani', "Kattaqo'rg'on tumani",
        'Narpay tumani', 'Nurobod tumani', 'Oqdaryo tumani',
        'Paxtachi tumani', 'Payariq tumani', "Pastdarg'om tumani",
        "Qo'shrabot tumani", 'Samarqand tumani', 'Toyloq tumani',
        'Urgut tumani',
    ]),
    ('Sirdaryo viloyati', [
        'Guliston shahri', 'Shirin shahri', 'Yangiyer shahri',
        'Boyovut tumani', 'Guliston tumani', 'Mirzaobod tumani',
        'Oqoltin tumani', 'Sardoba tumani', 'Sayxunobod tumani',
        'Sirdaryo tumani', 'Xovos tumani',
    ]),
    ('Surxondaryo viloyati', [
        'Termiz shahri', 'Angor tumani', 'Bandixon tumani', 'Boysun tumani',
        'Denov tumani', "Jarqo'rg'on tumani", 'Muzrabot tumani',
        'Oltinsoy tumani', 'Qiziriq tumani', "Qumqo'rg'on tumani",
        'Sariosiyo tumani', 'Sherobod tumani', "Sho'rchi tumani",
        'Termiz tumani', 'Uzun tumani',
    ]),
    ('Toshkent viloyati', [
        'Nurafshon shahri', 'Angren shahri', 'Bekobod shahri',
        'Chirchiq shahri', 'Olmaliq shahri', 'Ohangaron shahri',
        "Yangiyo'l shahri", 'Bekobod tumani', "Bo'ka tumani",
        "Bo'stonliq tumani", 'Chinoz tumani', 'Ohangaron tumani',
        "Oqqo'rg'on tumani", 'Parkent tumani', 'Piskent tumani',
        'Qibray tumani', 'Quyi Chirchiq tumani', "O'rta Chirchiq tumani",
        "Yangiyo'l tumani", 'Yuqori Chirchiq tumani', 'Zangiota tumani',
    ]),
    ('Xorazm viloyati', [
        'Urganch shahri', 'Xiva shahri', "Bog'ot tumani", 'Gurlan tumani',
        'Hazorasp tumani', "Qo'shko'pir tumani", 'Shovot tumani',
        "Tuproqqal'a tumani", 'Urganch tumani', 'Xonqa tumani',
        'Xiva tumani', 'Yangiariq tumani', 'Yangibozor tumani',
    ]),
    ('Toshkent shahri', [
        'Bektemir tumani', 'Chilonzor tumani', 'Mirobod tumani',
        "Mirzo Ulug'bek tumani", 'Olmazor tumani', 'Sergeli tumani',
        'Shayxontohur tumani', 'Uchtepa tumani', 'Yakkasaroy tumani',
        'Yashnobod tumani', 'Yunusobod tumani',
    ]),
]


def _guruhlangan_tanlovlar():
    """Django uchun guruhlangan choices — admin panelda <optgroup> bo'lib chiqadi."""
    return [(viloyat, [(t, t) for t in tumanlar])
            for viloyat, tumanlar in HUDUDLAR_XARITASI]


def barcha_hududlar():
    """Barcha tuman nomlari — tekis ro'yxat."""
    return [t for _, tumanlar in HUDUDLAR_XARITASI for t in tumanlar]


def viloyatlar():
    """Faqat viloyat nomlari."""
    return [v for v, _ in HUDUDLAR_XARITASI]


def viloyat_tumanlari(viloyat):
    """Berilgan viloyatning tumanlari."""
    for v, tumanlar in HUDUDLAR_XARITASI:
        if v == viloyat:
            return list(tumanlar)
    return []


def tuman_viloyati(tuman):
    """Tuman nomidan viloyatini topadi.

    Eski yozuvlarda faqat `tuman` saqlangan — `viloyat` maydoni to'ldirilganda
    shu funksiya ishlatiladi. Topilmasa bo'sh satr qaytadi (qo'lda yozilgan
    yoki eskirgan nom bo'lishi mumkin).
    """
    for viloyat, tumanlar in HUDUDLAR_XARITASI:
        if tuman in tumanlar:
            return viloyat
    return ''


HUDUDLAR = _guruhlangan_tanlovlar()

# Eski nom bilan import qilinadigan joylar buzilmasin
TUMANLAR = HUDUDLAR
