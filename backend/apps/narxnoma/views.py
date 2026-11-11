import datetime

from django.db.models import Q
from django.utils.translation import gettext as _
from rest_framework.decorators import api_view, authentication_classes, permission_classes, throttle_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import AnonRateThrottle

from apps.auth_app.models import audit_yoz
from .models import Narxnoma, NarxnomaQator, SAYT_XIZMAT_CHOICES

MAX_NARX = 10_000_000_000
SON_MAYDONLAR = ('p_dan', 'p_gacha', 'r_dan', 'r_gacha')
NOM_MAX = 400


def _adminmi(request):
    return getattr(request.user, 'rol', None) == 'admin'


def _korishMumkin(request):
    """Narxnomani admin va FAOL xodim ko'ra oladi; mijoz va tokensiz — yo'q."""
    u = request.user
    rol = getattr(u, 'rol', None)
    return rol == 'admin' or (rol == 'xodim' and getattr(u, 'holat', '') == 'faol')


def _qator(q):
    return {
        'id': q.id, 'tartib': q.tartib, 'nomi': q.nomi,
        'p_dan': q.p_dan, 'p_gacha': q.p_gacha,
        'r_dan': q.r_dan, 'r_gacha': q.r_gacha,
        'izoh': q.izoh, 'faol': q.faol,
    }


def _narxnoma(n, faqat_faol):
    qs = n.qatorlar.all()
    if faqat_faol:
        qs = qs.filter(faol=True)
    return {
        'id': n.id, 'sarlavha': n.sarlavha, 'tavsif': n.tavsif,
        'tarmoq': n.tarmoq, 'tarmoq_nomi': n.tarmoq_nomi,
        'bolim': n.bolim, 'bolim_nomi': n.bolim_nomi,
        'amal_qiladi': n.amal_qiladi,
        'ustun1': n.ustun1, 'ustun1_qisqa': n.ustun1_qisqa,
        'ustun2': n.ustun2, 'ustun2_qisqa': n.ustun2_qisqa,
        'eslatma': n.eslatma, 'faol': n.faol, 'yangilangan': n.yangilangan,
        'qatorlar': [_qator(q) for q in qs],
    }


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def narxnoma_royxat(request):
    """Xodimlar portali uchun: faqat faol narxnomalar va faol qatorlar."""
    if not _korishMumkin(request):
        return Response({'detail': _("Ruxsat yo'q")}, status=403)
    return Response([_narxnoma(n, True) for n in Narxnoma.objects.filter(faol=True).prefetch_related('qatorlar')])


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def narxnoma_admin(request):
    if not _adminmi(request):
        return Response({'detail': _("Ruxsat yo'q")}, status=403)
    return Response([_narxnoma(n, False) for n in Narxnoma.objects.prefetch_related('qatorlar')])


class XatoQiymat(Exception):
    pass


def _narx(qiymat):
    """None/'' -> None; aks holda 0..MAX_NARX orasidagi butun son."""
    if qiymat is None or qiymat == '':
        return None
    if isinstance(qiymat, bool):
        raise XatoQiymat(_("Narx noto'g'ri"))
    if isinstance(qiymat, str):
        qiymat = qiymat.replace(' ', '')
        if not qiymat.isdigit():
            raise XatoQiymat(_("Narx noto'g'ri"))
    elif isinstance(qiymat, float) and qiymat != int(qiymat):
        raise XatoQiymat(_("Narx noto'g'ri"))
    try:
        son = int(qiymat)
    except (TypeError, ValueError):
        raise XatoQiymat(_("Narx noto'g'ri"))
    if not (0 <= son <= MAX_NARX):
        raise XatoQiymat(_("Narx noto'g'ri"))
    return son


def _matn(qiymat, maks, nom, majburiy=False):
    s = str(qiymat if qiymat is not None else '').strip()
    if majburiy and not s:
        raise XatoQiymat(_('%(nom)s kiritilishi shart') % {'nom': nom})
    if len(s) > maks:
        raise XatoQiymat(_('%(nom)s juda uzun') % {'nom': nom})
    return s


def _qatorga_qoy(q, data):
    """Kelgan maydonlarni tekshirib `q` ga qo'yadi (saqlamaydi). Tuzatilgan
    maydonlar ro'yxatini qaytaradi."""
    ozgargan = []
    if 'tartib' in data:
        try:
            t = int(data['tartib'])
        except (TypeError, ValueError):
            raise XatoQiymat(_("Tartib raqami noto'g'ri"))
        if not (1 <= t <= 9999):
            raise XatoQiymat(_("Tartib raqami noto'g'ri"))
        q.tartib = t
        ozgargan.append('tartib')
    if 'nomi' in data:
        q.nomi = _matn(data['nomi'], NOM_MAX, _('Nomi'), majburiy=True)
        ozgargan.append('nomi')
    for m in SON_MAYDONLAR:
        if m in data:
            setattr(q, m, _narx(data[m]))
            ozgargan.append(m)
    if 'izoh' in data:
        q.izoh = _matn(data['izoh'], 255, _('Izoh'))
        ozgargan.append('izoh')
    if 'faol' in data:
        if not isinstance(data['faol'], bool):
            raise XatoQiymat(_("Holat noto'g'ri"))
        q.faol = data['faol']
        ozgargan.append('faol')
    # 2-ustunsiz narxnomada (bitta narxli) ikkinchi narx kiritilmaydi
    if not q.narxnoma.ustun2 and (q.r_dan is not None or q.r_gacha is not None):
        raise XatoQiymat(_('Bu narxnomada faqat bitta narx ustuni bor'))
    # Oraliqda "dan" "gacha" dan katta bo'lmasin
    for dan, gacha in (('p_dan', 'p_gacha'), ('r_dan', 'r_gacha')):
        a, b = getattr(q, dan), getattr(q, gacha)
        if b is not None and a is None:
            raise XatoQiymat(_('"Gacha" narx faqat "dan" bilan birga kiritiladi'))
        if a is not None and b is not None and b < a:
            raise XatoQiymat(_('"Gacha" narx "dan" narxdan kichik bo\'lmasin'))
    return ozgargan


def _farq(eski, q, ozgargan):
    qismlar = []
    for m in ozgargan:
        yangi = getattr(q, m)
        if eski.get(m) != yangi:
            qismlar.append(f'{m}: {eski.get(m)} → {yangi}')
    return ', '.join(qismlar)


@api_view(['PATCH'])
@permission_classes([IsAuthenticated])
def qator_yangila(request, pk):
    if not _adminmi(request):
        return Response({'detail': _("Ruxsat yo'q")}, status=403)
    try:
        q = NarxnomaQator.objects.get(pk=pk)
    except NarxnomaQator.DoesNotExist:
        return Response({'detail': _('Qator topilmadi')}, status=404)
    eski = {m: getattr(q, m) for m in ('tartib', 'nomi', 'izoh', 'faol') + SON_MAYDONLAR}
    try:
        ozgargan = _qatorga_qoy(q, request.data)
    except XatoQiymat as e:
        return Response({'detail': str(e)}, status=400)
    q.save()
    farq = _farq(eski, q, ozgargan)
    if farq:
        audit_yoz(request, 'narx_ozgardi', f'#{q.tartib} {q.nomi[:50]} — {farq}')
    return Response(_qator(q))


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def qator_qosh(request, pk):
    if not _adminmi(request):
        return Response({'detail': _("Ruxsat yo'q")}, status=403)
    try:
        n = Narxnoma.objects.get(pk=pk)
    except Narxnoma.DoesNotExist:
        return Response({'detail': _('Narxnoma topilmadi')}, status=404)
    q = NarxnomaQator(narxnoma=n, tartib=0, nomi='')
    data = dict(request.data.items())
    data.setdefault('tartib', (n.qatorlar.order_by('-tartib').values_list('tartib', flat=True).first() or 0) + 1)
    if 'nomi' not in data:
        return Response({'detail': _('Nomi kiritilishi shart')}, status=400)
    try:
        _qatorga_qoy(q, data)
    except XatoQiymat as e:
        return Response({'detail': str(e)}, status=400)
    q.save()
    audit_yoz(request, 'narx_qoshildi', f'#{q.tartib} {q.nomi[:80]}')
    return Response(_qator(q), status=201)


@api_view(['PATCH'])
@permission_classes([IsAuthenticated])
def narxnoma_yangila(request, pk):
    """Narxnoma sarlavhasi: amal qilish sanasi, eslatma, tavsif, ustun nomlari, faol."""
    if not _adminmi(request):
        return Response({'detail': _("Ruxsat yo'q")}, status=403)
    try:
        n = Narxnoma.objects.get(pk=pk)
    except Narxnoma.DoesNotExist:
        return Response({'detail': _('Narxnoma topilmadi')}, status=404)
    d = request.data
    try:
        if 'sarlavha' in d:
            n.sarlavha = _matn(d['sarlavha'], 300, _('Sarlavha'), majburiy=True)
        if 'tavsif' in d:
            n.tavsif = _matn(d['tavsif'], 300, _('Tavsif'))
        if 'ustun1' in d:
            n.ustun1 = _matn(d['ustun1'], 200, _('Ustun nomi'), majburiy=True)
        if 'ustun1_qisqa' in d:
            n.ustun1_qisqa = _matn(d['ustun1_qisqa'], 40, _('Qisqa nom'))
        if 'ustun2' in d:
            # Bo'sh bo'lishi mumkin: narxnomada bitta narx ustuni qoladi. Lekin
            # allaqachon ikkinchi narx kiritilgan bo'lsa, ustunni olib tashlab bo'lmaydi
            yangi = _matn(d['ustun2'], 200, _('Ustun nomi'))
            if not yangi and n.qatorlar.filter(Q(r_dan__isnull=False) | Q(r_gacha__isnull=False)).exists():
                raise XatoQiymat(_("2-ustunda narxlar bor. Avval ularni o'chiring"))
            n.ustun2 = yangi
        if 'ustun2_qisqa' in d:
            n.ustun2_qisqa = _matn(d['ustun2_qisqa'], 40, _('Qisqa nom'))
        if 'eslatma' in d:
            n.eslatma = _matn(d['eslatma'], 2000, _('Eslatma'))
        if 'amal_qiladi' in d:
            if d['amal_qiladi'] in (None, ''):
                n.amal_qiladi = None
            else:
                try:
                    n.amal_qiladi = datetime.date.fromisoformat(str(d['amal_qiladi']))
                except ValueError:
                    raise XatoQiymat(_("Sana noto'g'ri"))
        if 'faol' in d:
            if not isinstance(d['faol'], bool):
                raise XatoQiymat(_("Holat noto'g'ri"))
            n.faol = d['faol']
    except XatoQiymat as e:
        return Response({'detail': str(e)}, status=400)
    n.save()
    audit_yoz(request, 'narx_ozgardi', f'Narxnoma sarlavhasi: {n.sarlavha[:80]}')
    return Response(_narxnoma(n, False))


# ──────────────────────────────────────────────────────────────
#  Ochiq: saytdagi Metrologiya bo'limi uchun narxlar (FAQAT O'QISH)
# ──────────────────────────────────────────────────────────────
class MetrologiyaNarxThrottle(AnonRateThrottle):
    """Ochiq ro'yxat: bir IP dan soatiga 120 so'rov (sahifa uni bir marta yuklaydi)."""
    scope = 'metrologiya_narx'
    rate = '120/hour'


@api_view(['GET'])
@authentication_classes([])          # token tekshirilmaydi: noto'g'ri sarlavha ham 401 bermaydi
@permission_classes([AllowAny])
@throttle_classes([MetrologiyaNarxThrottle])
def metrologiya_narxlar(request):
    """Saytga chiqadigan metrologiya narxlari: {tarmoq: {eslatma, xizmatlar: {xizmat: [qator, ...]}}}.

    Faqat FAOL narxnoma va FAOL qatorlar, faqat `sayt_xizmat` belgilanganlari. Ichki maydonlar
    (id, yangilangan, nofaol qatorlar, boshqa bo'lim narxnomalari) umuman chiqmaydi."""
    xizmatlar = [k for k, _nom in SAYT_XIZMAT_CHOICES if k]
    javob = {}
    for n in Narxnoma.objects.filter(bolim='metrologiya', faol=True).prefetch_related('qatorlar'):
        guruh = {k: [] for k in xizmatlar}
        for q in n.qatorlar.all():
            if q.faol and q.sayt_xizmat in guruh and q.p_dan is not None:
                guruh[q.sayt_xizmat].append({
                    'tartib': q.tartib, 'nomi': q.nomi,
                    'narx_dan': q.p_dan, 'narx_gacha': q.p_gacha, 'izoh': q.izoh,
                })
        javob[n.tarmoq] = {'eslatma': n.eslatma, 'xizmatlar': guruh}
    r = Response(javob)
    r['Cache-Control'] = 'public, max-age=60'
    return r


# ──────────────────────────────────────────────────────────────
#  Ochiq: saytdagi "Narxnoma" oynasi (FAQAT O'QISH, hamma uchun)
# ──────────────────────────────────────────────────────────────
class OchiqNarxnomaThrottle(AnonRateThrottle):
    """Ochiq ro'yxat: bir IP dan soatiga 120 so'rov (oyna uni bir marta yuklaydi)."""
    scope = 'ochiq_narxnoma'
    rate = '120/hour'


@api_view(['GET'])
@authentication_classes([])          # token tekshirilmaydi: noto'g'ri sarlavha ham 401 bermaydi
@permission_classes([AllowAny])
@throttle_classes([OchiqNarxnomaThrottle])
def ochiq_narxnomalar(request):
    """Saytga chiqadigan narxnomalar ro'yxati (tokensiz ham ochiq).

    Faqat FAOL narxnoma va FAOL qatorlar. Ichki maydonlar (id, yangilangan, faol,
    qisqa ustun nomlari) chiqmaydi. Xodim/admin uchun yopiq `narxnoma_royxat` o'zgarmagan."""
    javob = []
    for n in Narxnoma.objects.filter(faol=True).prefetch_related('qatorlar'):
        javob.append({
            'sarlavha': n.sarlavha, 'tavsif': n.tavsif,
            'tarmoq': n.tarmoq, 'tarmoq_nomi': n.tarmoq_nomi,
            'bolim': n.bolim, 'bolim_nomi': n.bolim_nomi,
            'amal_qiladi': n.amal_qiladi.isoformat() if n.amal_qiladi else None,
            'ustun1': n.ustun1, 'ustun2': n.ustun2,
            'eslatma': n.eslatma,
            'qatorlar': [
                {'tartib': q.tartib, 'nomi': q.nomi,
                 'p_dan': q.p_dan, 'p_gacha': q.p_gacha,
                 'r_dan': q.r_dan, 'r_gacha': q.r_gacha, 'izoh': q.izoh}
                for q in n.qatorlar.all() if q.faol
            ],
        })
    r = Response(javob)
    r['Cache-Control'] = 'public, max-age=60'
    return r
