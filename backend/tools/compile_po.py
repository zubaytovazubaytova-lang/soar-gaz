# -*- coding: utf-8 -*-
"""`locale/*/LC_MESSAGES/*.po` fayllarini `.mo` ga kompilyatsiya qiladi.

Nega alohida vosita: `manage.py compilemessages` GNU gettext'ning `msgfmt`
dasturini talab qiladi, Windowsda esa u odatda o'rnatilmagan. Bu skript sof
Python — hech qanday tashqi dastur kerak emas.

Ishlatish (backend papkasidan):
    python tools/compile_po.py
"""
import array
import os
import re
import struct
import sys

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOCALE_DIR = os.path.join(BASE_DIR, 'locale')


def po_oqi(path):
    """`.po` faylini {msgid: msgstr} lug'atiga o'giradi.

    Faqat loyihada ishlatiladigan qism qo'llab-quvvatlanadi: oddiy
    `msgid`/`msgstr` juftliklari va ko'p qatorli satrlar. `msgid_plural`
    uchrasa xato beriladi — bunday satr paydo bo'lsa vositani kengaytiring.
    """
    katalog = {}
    kalit = None
    qism = None   # 'msgid' | 'msgstr'
    buf = {'msgid': '', 'msgstr': ''}

    def yakunla():
        if qism is None:
            return
        katalog[buf['msgid']] = buf['msgstr']

    with open(path, encoding='utf-8') as f:
        for raqam, satr in enumerate(f, 1):
            satr = satr.strip()
            if not satr or satr.startswith('#'):
                continue
            if satr.startswith('msgid_plural'):
                raise SystemExit('%s:%d — msgid_plural qo\'llab-quvvatlanmaydi'
                                 % (path, raqam))
            if satr.startswith('msgid '):
                yakunla()
                buf = {'msgid': '', 'msgstr': ''}
                qism = 'msgid'
                buf['msgid'] = matn_qismi(satr[len('msgid '):], path, raqam)
            elif satr.startswith('msgstr '):
                qism = 'msgstr'
                buf['msgstr'] = matn_qismi(satr[len('msgstr '):], path, raqam)
            elif satr.startswith('"'):
                if qism is None:
                    raise SystemExit('%s:%d — kutilmagan satr' % (path, raqam))
                buf[qism] += matn_qismi(satr, path, raqam)
            else:
                raise SystemExit('%s:%d — tushunarsiz satr: %s'
                                 % (path, raqam, satr))
        yakunla()
    return katalog


ESCAPES = {'n': '\n', 't': '\t', 'r': '\r', '"': '"', '\\': '\\'}


def matn_qismi(xom, path, raqam):
    xom = xom.strip()
    if not (xom.startswith('"') and xom.endswith('"')):
        raise SystemExit('%s:%d — tirnoq ichida bo\'lishi kerak' % (path, raqam))
    ichki = xom[1:-1]
    natija = []
    i = 0
    while i < len(ichki):
        belgi = ichki[i]
        if belgi == '\\' and i + 1 < len(ichki):
            keyingi = ichki[i + 1]
            natija.append(ESCAPES.get(keyingi, keyingi))
            i += 2
        else:
            natija.append(belgi)
            i += 1
    return ''.join(natija)


def mo_yoz(katalog, path):
    """GNU .mo formatida yozadi (kichik-endian, hash jadvalsiz)."""
    yozuvlar = sorted(katalog.items())
    kalitlar = b''
    qiymatlar = b''
    kalit_joyi = []
    qiymat_joyi = []
    for k, v in yozuvlar:
        kb = k.encode('utf-8')
        vb = v.encode('utf-8')
        kalit_joyi.append((len(kb), len(kalitlar)))
        qiymat_joyi.append((len(vb), len(qiymatlar)))
        kalitlar += kb + b'\x00'
        qiymatlar += vb + b'\x00'

    soni = len(yozuvlar)
    bosh = 7 * 4
    kalit_jadval = bosh
    qiymat_jadval = kalit_jadval + soni * 8
    kalit_boshi = qiymat_jadval + soni * 8
    qiymat_boshi = kalit_boshi + len(kalitlar)

    natija = struct.pack('<7I', 0x950412de, 0, soni, kalit_jadval,
                         qiymat_jadval, 0, 0)
    jadval = array.array('i')
    for uzunlik, siljish in kalit_joyi:
        jadval.extend([uzunlik, kalit_boshi + siljish])
    for uzunlik, siljish in qiymat_joyi:
        jadval.extend([uzunlik, qiymat_boshi + siljish])
    if sys.byteorder == 'big':
        jadval.byteswap()
    natija += jadval.tobytes() + kalitlar + qiymatlar

    with open(path, 'wb') as f:
        f.write(natija)


def main():
    if not os.path.isdir(LOCALE_DIR):
        raise SystemExit('locale/ papkasi topilmadi: %s' % LOCALE_DIR)
    topildi = 0
    for ildiz, _papkalar, fayllar in os.walk(LOCALE_DIR):
        for nom in fayllar:
            if not nom.endswith('.po'):
                continue
            po = os.path.join(ildiz, nom)
            mo = re.sub(r'\.po$', '.mo', po)
            katalog = po_oqi(po)
            mo_yoz(katalog, mo)
            topildi += 1
            print('%s -> %s (%d ta satr)' % (
                os.path.relpath(po, BASE_DIR),
                os.path.relpath(mo, BASE_DIR),
                len(katalog),
            ))
    if not topildi:
        raise SystemExit('.po fayl topilmadi')


if __name__ == '__main__':
    main()
