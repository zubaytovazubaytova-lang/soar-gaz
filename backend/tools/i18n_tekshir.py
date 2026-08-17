# -*- coding: utf-8 -*-
"""`Accept-Language` bo'yicha serializer yorliqlari tarjima bo'lishini tekshiradi.

Ishlatish (backend papkasidan, virtual muhit bilan):
    venv/Scripts/python.exe tools/i18n_tekshir.py

Bazaga tegmaydi — saqlanmagan (in-memory) obyektlar seriyalanadi.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'soargaz.settings')

import django  # noqa: E402

django.setup()

from django.utils import translation  # noqa: E402

from apps.buyurtmalar.models import Buyurtma  # noqa: E402
from apps.buyurtmalar.serializers import BuyurtmaSerializer  # noqa: E402
from apps.kabinet.models import Obyekt  # noqa: E402

KUTILGAN = {
    'uz': {'xizmat_nomi': 'Metrologiya', 'holat_nomi': 'Bajarilmoqda',
           'turi_nomi': 'Xususiy uy'},
    'ru': {'xizmat_nomi': 'Метрология', 'holat_nomi': 'Выполняется',
           'turi_nomi': 'Частный дом'},
}


def tekshir():
    buyurtma = Buyurtma(xizmat='metrologiya', holat='bajarilmoqda')
    obyekt = Obyekt(nom='Test', turi='uy', manzil='1-uy')

    xato = 0
    for til, kutilgan in KUTILGAN.items():
        with translation.override(til):
            b = BuyurtmaSerializer(buyurtma).data
            # `ObyektSerializer` ichma-ich bog'lanishlarni o'qiydi va saqlanmagan
            # obyektda ishlamaydi — yorliq manbasini to'g'ridan-to'g'ri olamiz
            # (serializer aynan shu `get_turi_display` ni ishlatadi).
            turi_nomi = obyekt.get_turi_display()
        haqiqiy = {
            'xizmat_nomi': b['xizmat_nomi'],
            'holat_nomi': b['holat_nomi'],
            'turi_nomi': turi_nomi,
        }
        for kalit, qiymat in kutilgan.items():
            belgi = 'OK ' if haqiqiy[kalit] == qiymat else 'XATO'
            if haqiqiy[kalit] != qiymat:
                xato += 1
            print('%s %s.%s = %r (kutilgan %r)'
                  % (belgi, til, kalit, haqiqiy[kalit], qiymat))
    return xato


if __name__ == '__main__':
    sys.exit(1 if tekshir() else 0)