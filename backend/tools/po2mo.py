"""`.po` fayldan `.mo` yasaydi — GNU gettext o'rnatilmagan mashinalar uchun.

Windows'da `manage.py compilemessages` ishlamaydi: u `msgfmt`/`msguniq`
buyruqlarini talab qiladi va ular Python bilan birga kelmaydi
("CommandError: Can't find msguniq"). Bu skript o'sha ishni sof Python bilan
bajaradi, shuning uchun tarjima o'zgarganda uni ishlatish kifoya.

    python tools/po2mo.py locale/ru/LC_MESSAGES/django.po

GNU gettext o'rnatilgan bo'lsa odatdagi `manage.py compilemessages` ham
ishlaydi — bu skript uning o'rnini bosadi, almashtirmaydi.
"""

import array
import re
import struct
import sys
from pathlib import Path


def po_oqi(matn):
    """`.po` matnidan {msgid: msgstr} lug'atini yig'adi.

    Fuzzy va tarjimasiz yozuvlar tashlab yuboriladi: bo'sh `msgstr` `.mo` ga
    tushsa gettext uni "tarjima bor" deb hisoblab, asl matn o'rniga BO'SH satr
    qaytaradi va ekranda hech narsa ko'rinmaydi.
    """
    yozuvlar = {}
    msgid = msgstr = None
    joriy = None
    fuzzy = False

    def saqla():
        if msgid is not None and msgstr and not fuzzy:
            yozuvlar[msgid] = msgstr

    for qator in matn.splitlines():
        q = qator.strip()
        if q.startswith('#,') and 'fuzzy' in q:
            fuzzy = True
            continue
        if q.startswith('#') or not q:
            continue
        if q.startswith('msgid_plural'):
            joriy = None  # ko'plik shakllari qo'llab-quvvatlanmaydi
            continue
        if q.startswith('msgid'):
            saqla()
            msgid, msgstr, fuzzy = _satr(q, 'msgid'), '', False
            joriy = 'id'
        elif q.startswith('msgstr'):
            msgstr = _satr(q, 'msgstr')
            joriy = 'str'
        elif q.startswith('"') and joriy:
            qism = _tirnoq(q)
            if joriy == 'id':
                msgid += qism
            else:
                msgstr += qism
    saqla()
    return yozuvlar


def _satr(qator, kalit):
    return _tirnoq(qator[len(kalit):].strip())


def _tirnoq(q):
    m = re.match(r'^"(.*)"$', q)
    xom = m.group(1) if m else q
    return xom.encode().decode('unicode_escape').encode('latin-1').decode('utf-8')


def mo_yasa(yozuvlar):
    """gettext `.mo` ikkilik formatini quradi (little-endian, hash jadvalisiz)."""
    kalitlar = sorted(yozuvlar)
    idlar = b''
    matnlar = b''
    id_joy = []
    matn_joy = []

    for k in kalitlar:
        kb = k.encode('utf-8')
        vb = yozuvlar[k].encode('utf-8')
        id_joy.append((len(kb), len(idlar)))
        matn_joy.append((len(vb), len(matnlar)))
        idlar += kb + b'\x00'
        matnlar += vb + b'\x00'

    n = len(kalitlar)
    bosh = 7 * 4
    id_jadval = bosh
    matn_jadval = id_jadval + n * 8
    idlar_boshi = matn_jadval + n * 8
    matnlar_boshi = idlar_boshi + len(idlar)

    natija = struct.pack(
        '<7I',
        0x950412DE,   # sehrli raqam
        0,            # versiya
        n,
        id_jadval,
        matn_jadval,
        0, 0,         # hash jadvali ishlatilmaydi
    )
    natija += array.array('i', [
        x for uzunlik, ofset in id_joy for x in (uzunlik, ofset + idlar_boshi)
    ]).tobytes()
    natija += array.array('i', [
        x for uzunlik, ofset in matn_joy for x in (uzunlik, ofset + matnlar_boshi)
    ]).tobytes()
    return natija + idlar + matnlar


def main(argv):
    if len(argv) != 2:
        print(__doc__)
        return 2
    po = Path(argv[1])
    yozuvlar = po_oqi(po.read_text(encoding='utf-8'))
    mo = po.with_suffix('.mo')
    mo.write_bytes(mo_yasa(yozuvlar))
    print(f'{mo} — {len(yozuvlar)} ta tarjima')
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
