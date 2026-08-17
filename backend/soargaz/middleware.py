"""Loyihaga xos middleware'lar."""
from django.middleware.gzip import GZipMiddleware

# Faqat shu turlar siqiladi. Qolgani (rasm, video, shrift, arxiv) allaqachon
# siqilgan — ularni gzip qilish hajmni kamaytirmaydi, aksincha zarar keltiradi.
SIQILADIGAN = (
    'text/',
    'application/javascript',
    'application/json',
    'application/manifest+json',
    'application/xml',
    'image/svg+xml',
)


class MatnGZipMiddleware(GZipMiddleware):
    """Gzip'ni faqat matnli javoblarga qo'llaydi.

    Django'ning standart GZipMiddleware'i OQIMLI javoblarda (FileResponse —
    bu loyihada barcha sahifalar va statik fayllar shunday beriladi) "siqilgani
    kattaroq bo'lsa, tashla" tekshiruvini o'tkazib yuboradi va `Content-Length`
    sarlavhasini o'chiradi. Natijada:

      * .mp4 / .woff2 / .png bekorga qayta siqiladi (672 KB video -> 670 KB,
        ya'ni foyda deyarli nol, protsessor esa har so'rovda sarflanadi);
      * Content-Length yo'qolgani uchun brauzer videoni oldinga sura olmaydi
        (Range so'rovlari ishlamay qoladi);
      * 206 (qisman) javob siqilsa, umuman buziladi.

    Shuning uchun turini tekshirib, faqat matnga ruxsat beramiz.
    """

    def process_response(self, request, response):
        # Qisman javob (Range) hech qachon siqilmasin
        if response.status_code == 206:
            return response

        tur = response.headers.get('Content-Type', '').split(';')[0].strip()
        if not tur.startswith(SIQILADIGAN):
            return response

        return super().process_response(request, response)
