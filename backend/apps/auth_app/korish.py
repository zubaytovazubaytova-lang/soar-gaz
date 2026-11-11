"""«Uning ko'zi bilan ko'rish» (impersonation): egasi xodim yoki mijoz portalini
o'sha foydalanuvchi nomidan, FAQAT O'QISH rejimida ko'radi.

Nega django-hijack emas: u Django SESSIYASIGA asoslangan, bu loyihadagi portallar
esa (xodimlar, kabinet) JWT bilan ishlaydi. Shuning uchun xuddi shu talablar JWT
uchun shu yerda bajariladi:

  * token alohida (`korish` belgisi bilan), qisqa muddatli va YANGILANMAYDI —
    muddati tugagach egasi qaytadan ochishi kerak;
  * bu token bilan har qanday o'zgartiruvchi so'rov (POST/PUT/PATCH/DELETE) HAMMA
    endpointlarda bloklanadi — autentifikatsiya bosqichida, view'larga yetmasdan;
  * har bir ochish Faoliyat jurnaliga yoziladi (kim, kimning nomidan, qachon, IP),
    bloklangan o'zgartirish urinishlari ham;
  * token egasi har so'rovda tekshiriladi: u endi faol tizim egasi bo'lmasa,
    token darhol kuchini yo'qotadi.
"""
from django.core.cache import cache
from django.utils.translation import gettext as _
from rest_framework import exceptions
from rest_framework.permissions import SAFE_METHODS
from rest_framework_simplejwt.authentication import JWTAuthentication


# Kuzatuvchi ham ishlata oladigan o'zgartiruvchi so'rovlar: ular hech qanday ma'lumotni o'zgartirmaydi
# (kirish bosqichlari va tokenni yangilash).
KUZATUVCHI_RUXSAT = ('/api/auth/admin/login/', '/api/auth/admin/otp/', '/api/auth/token/yangilash/')


def kuzatuvchimi(user):
    """Direktor — KUZATUVCHI: admin roli bor, lekin tizim egasi (superuser) emas. U hamma narsani ko'radi,
    hech narsani o'zgartirmaydi; o'zgartirishni faqat egasi qiladi."""
    return getattr(user, 'rol', None) == 'admin' and not getattr(user, 'is_superuser', False)


class KorishJWTAuthentication(JWTAuthentication):
    """Oddiy JWT + «ko'rish» tokenlari uchun qo'shimcha qoidalar."""

    def authenticate(self, request):
        natija = super().authenticate(request)
        if natija is None:
            return None
        user, token = natija

        # Kuzatuvchi (direktor): har qanday o'zgartiruvchi so'rov HAMMA endpointlarda autentifikatsiya
        # bosqichida bloklanadi — view'larga yetmasdan (yangi endpoint qo'shilsa ham himoya o'z-o'zidan ishlaydi).
        if kuzatuvchimi(user) and request.method not in SAFE_METHODS and request.path not in KUZATUVCHI_RUXSAT:
            from .models import audit_yoz
            if cache.add(f'kuzatuvchi:rad:{user.pk}', 1, 300):       # 5 daqiqada bir marta — jurnal to'lib ketmasin
                audit_yoz(request, 'korish_rad', f"Kuzatuvchi {user.ism or user.telefon}: {request.method} {request.path}",
                          user=user)
            raise exceptions.PermissionDenied(_("Kuzatuvchi rejimida o'zgartirish mumkin emas — faqat ko'rish"))
        if not token.get('korish'):
            return natija

        from .models import Foydalanuvchi, audit_yoz

        egasi = Foydalanuvchi.objects.filter(
            pk=token.get('korish_egasi'), is_superuser=True, rol='admin', is_active=True,
            holat='faol').first()
        if egasi is None:
            raise exceptions.AuthenticationFailed(_("Ko'rish rejimi tugagan. Qaytadan oching."))

        if request.method not in SAFE_METHODS:
            # Bloklangan urinish jurnalga yoziladi (5 daqiqada bir marta — jurnal to'lib ketmasin)
            if cache.add(f'korish:rad:{egasi.pk}:{user.pk}', 1, 300):
                audit_yoz(request, 'korish_rad',
                          f"{user.ism or user.telefon} nomidan {request.method} {request.path}",
                          user=egasi)
            raise exceptions.PermissionDenied(_("Ko'rish rejimida o'zgartirish mumkin emas"))

        user.korish_egasi = egasi
        return user, token
