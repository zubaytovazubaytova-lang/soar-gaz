"""«Direktor» guruhini yaratadi/yangilaydi (Django paneli uchun FAQAT KO'RISH huquqlari).

Direktor — KUZATUVCHI: hamma narsani ko'radi, hech narsani qo'shmaydi, o'zgartirmaydi va o'chirmaydi
(boshqaruv paneli API'sida ham xuddi shunday: `apps/auth_app/korish.py`). O'zgartirishni faqat tizim egasi qiladi.

Guruh o'zi hech kimga huquq bermaydi. Direktor hisobiga uni TIZIM EGASI Django panelida
o'zi biriktiradi: foydalanuvchi sahifasida «Статус персонала / Xodim huquqi» (is_staff)
belgisini qo'yadi va «Direktor» guruhini tanlaydi.

Nima BERILMAYDI (ataylab): qo'shish, o'zgartirish va o'chirish (hech qaysi bo'limda), admin hisoblarini
ko'rish, xodimni nofaol/faol qilish va unga parol qo'yish (faqat egasi), superuser huquqi.

Buyruq takroran ishga tushirilsa, guruh huquqlari shu ro'yxatga tenglashtiriladi
(qo'lda qo'shilgan ortiqcha huquq olib tashlanadi).
"""
from django.contrib.auth.models import Group, Permission
from django.core.management.base import BaseCommand

GURUH = 'Direktor'

# (ilova, model, huquqlar) — hammasi faqat «view»: direktor kuzatuvchi, o'zgartirmaydi
HUQUQLAR = [
    ('buyurtmalar', 'buyurtma', ['view']),
    ('buyurtmalar', 'buyurtmaxizmat', ['view']),
    ('buyurtmalar', 'buyurtmafoto', ['view']),
    ('tushum', 'tushum', ['view']),
    ('narxnoma', 'narxnoma', ['view']),
    ('narxnoma', 'narxnomaqator', ['view']),
    ('katalog', 'katalognarx', ['view']),
    ('auth_app', 'xodim', ['view']),
    ('auth_app', 'audityozuv', ['view']),
    ('joylashuv', 'smena', ['view']),
    ('joylashuv', 'nuqta', ['view']),
    ('joylashuv', 'rozilik', ['view']),
    ('aloqa', 'xabar', ['view']),
    ('auth_app', 'mijoz', ['view']),                        # mijozlar bazasi
    ('tolovlar', 'tolovsorovi', ['view']),
    ('hujjatlar', 'kvitansiya', ['view']),
    ('hujjatlar', 'shartnoma', ['view']),
    ('hujjatlar', 'sozlama', ['view']),
    ('hujjatlar', 'hujjatloyiha', ['view']),                # xodim tayyorlagan hujjatlar jurnali
    ('hujjatlar', 'topshiriq', ['view']),                   # ichki topshiriqlar
]


def huquqlar_royxati():
    """Guruhga beriladigan Permission obyektlari (mavjud bo'lmaganlari xato beradi)."""
    natija = []
    for ilova, model, amallar in HUQUQLAR:
        for amal in amallar:
            # view/add/change/delete — standart (`view_<model>`); boshqalari (hal_qilish, kvitansiya_bekor...) — aynan shu nom
            kod = f'{amal}_{model}' if amal in ('view', 'add', 'change', 'delete') else amal
            natija.append(Permission.objects.get(content_type__app_label=ilova, codename=kod))
    return natija


class Command(BaseCommand):
    help = "«Direktor» guruhini (Django paneli uchun cheklangan huquqlar) yaratadi yoki yangilaydi."

    def handle(self, *args, **opts):
        guruh, yangi = Group.objects.get_or_create(name=GURUH)
        huquqlar = huquqlar_royxati()
        guruh.permissions.set(huquqlar)
        self.stdout.write(self.style.SUCCESS(
            f"«{GURUH}» guruhi {'yaratildi' if yangi else 'yangilandi'}: {len(huquqlar)} ta huquq."))
        self.stdout.write(
            "Direktor hisobiga biriktirish (tizim egasi, Django panelida): foydalanuvchi sahifasida "
            "«Xodim huquqi / is_staff» belgisini qo'ying va «Direktor» guruhini tanlang.")
