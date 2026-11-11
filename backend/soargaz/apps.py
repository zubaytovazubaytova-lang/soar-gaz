from django.contrib.admin.apps import AdminConfig


class SoarAdminConfig(AdminConfig):
    """Standart admin sayti o'rniga SoarAdminSite ishlatiladi (rahbariyat bosh sahifasi,
    login urinishlari cheklovi). Barcha `admin.site` ro'yxatdan o'tkazishlari o'zgarishsiz ishlaydi."""
    default_site = 'soargaz.admin_site.SoarAdminSite'
