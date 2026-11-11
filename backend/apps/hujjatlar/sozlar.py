"""Summani so'z bilan yozish (o'zbek, lotin): 55000 -> «ellik besh ming»."""

BIR = ['', 'bir', 'ikki', 'uch', "to'rt", 'besh', 'olti', 'yetti', 'sakkiz', "to'qqiz"]
ON = ['', "o'n", 'yigirma', "o'ttiz", 'qirq', 'ellik', 'oltmish', 'yetmish', 'sakson', "to'qson"]
KATTALIKLAR = [(10 ** 9, 'milliard'), (10 ** 6, 'million'), (10 ** 3, 'ming')]


def _uch_xonali(n):
    """1..999."""
    qismlar = []
    if n >= 100:
        qismlar += [BIR[n // 100], 'yuz']
        n %= 100
    if n >= 10:
        qismlar.append(ON[n // 10])
        n %= 10
    if n:
        qismlar.append(BIR[n])
    return ' '.join(qismlar)


def summa_sozlar(n):
    """Butun son so'z bilan. Manfiy va juda katta qiymatlar uchun bo'sh qator."""
    try:
        n = int(n)
    except (TypeError, ValueError):
        return ''
    if n < 0 or n >= 10 ** 12:
        return ''
    if n == 0:
        return 'nol'
    qismlar = []
    for kattalik, nom in KATTALIKLAR:
        q, n = divmod(n, kattalik)
        if q:
            qismlar.append(f'{_uch_xonali(q)} {nom}')
    if n:
        qismlar.append(_uch_xonali(n))
    return ' '.join(qismlar)
