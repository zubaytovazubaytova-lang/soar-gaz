"""IP bo'yicha cheklovlar — kirish va OTP endpointlari uchun.

Telefon raqam bo'yicha cheklovlar (`_otp_cheklov`, `ADMIN_URINISH_LIMIT`)
allaqachon bor, lekin ular faqat BITTA raqamni himoya qiladi. Hujumchi
minglab turli raqamni ketma-ket sinab ko'rsa (SMS to'ldirish, parol
taxmin qilish) ular ishlamaydi — buni shu yerdagi IP cheklovlari to'sadi.

IP ni aniqlash `REST_FRAMEWORK['NUM_PROXIES']` ga bog'liq (settings.py):
nginx orqasida 1, to'g'ridan-to'g'ri ishlaganda 0. Noto'g'ri qiymat
hujumchiga `X-Forwarded-For` ni soxtalashtirib, cheklovni aylanib o'tish
imkonini beradi.

Stavkalar oddiy foydalanuvchini bezovta qilmaydigan darajada keng: bitta
ofis/mobil operator NAT'i ortida ko'p odam bir IP dan kirishi mumkin.
"""
from rest_framework.throttling import AnonRateThrottle, UserRateThrottle


class KirishThrottle(AnonRateThrottle):
    """Parol bilan kirish (admin, xodim): bir IP dan daqiqasiga 10 urinish."""
    scope = 'kirish'
    rate = '10/min'


class OtpYuborishThrottle(AnonRateThrottle):
    """SMS kod so'rash: bir IP dan soatiga 30 ta. SMS pulli — suiiste'molni to'sadi."""
    scope = 'otp_yuborish'
    rate = '30/hour'


class OtpTasdiqThrottle(AnonRateThrottle):
    """Kodni tekshirish: bir IP dan daqiqasiga 15 urinish."""
    scope = 'otp_tasdiq'
    rate = '15/min'


class RoyxatThrottle(AnonRateThrottle):
    """Ro'yxatdan o'tish: bir IP dan soatiga 20 ta."""
    scope = 'royxat'
    rate = '20/hour'


class TokenYangilashThrottle(AnonRateThrottle):
    """Sessiyani jimgina yangilash: bir IP dan soatiga 300 (har mijoz ~30 daqiqada bir marta;
    ofis/operator NAT'i ortida ko'p odam bo'lishi mumkin)."""
    scope = 'token_yangilash'
    rate = '300/hour'


class TasdiqKodiThrottle(UserRateThrottle):
    """Maxfiy amal uchun SMS kod so'rash: bir IP dan soatiga 20 ta (SMS pulli)."""
    scope = 'tasdiq_kodi'
    rate = '20/hour'


class BuyurtmaKorishThrottle(AnonRateThrottle):
    """Buyurtmani raqam bo'yicha ko'rish: bir IP dan soatiga 600 ta (sahifa holatni 15 soniyada
    bir so'raydi, ya'ni bitta mijozga soatiga 240 ta kerak)."""
    scope = 'buyurtma_korish'
    rate = '600/hour'


class BuyurtmaTasdiqThrottle(AnonRateThrottle):
    """Buyurtma egaligini telefon bilan tasdiqlash urinishlari: bir IP dan soatiga 20 ta."""
    scope = 'buyurtma_tasdiq'
    rate = '20/hour'
