"""CSP: skriptlarda 'unsafe-inline' yo'q, sahifalarda inline skript/handler qaytib kirmasligi.

Bu testlar frontend uchun yagona avtomatik himoya: onclick="..." yoki inline <script>
qaytib qo'shilsa, CSP uni brauzerda JIM bloklaydi (tugma shunchaki ishlamaydi).
"""
import re

from django.conf import settings
from django.test import SimpleTestCase, TestCase

SAHIFALAR = ['index.html', 'kabinet.html', 'admin.html', 'xodimlar.html', 'offline.html', '404.html']
HANDLER = re.compile(
    r'(?<=[\s"\'`])on(click|dblclick|submit|input|change|keydown|keyup|keypress|focus|blur|'
    r'mouseover|mouseout|error|load|contextmenu|touchstart|touchend)\s*=\s*["\']', re.I)
INLINE_SKRIPT = re.compile(
    r'<script(?![^>]*\bsrc=)(?![^>]*(?:ld\+json|speculationrules))[^>]*>', re.I)


class CspSarlavhaTest(TestCase):
    def csp(self, yol):
        return self.client.get(yol)['Content-Security-Policy']

    def test_skriptda_unsafe_inline_yoq(self):
        script_src = [q for q in self.csp('/').split(';') if q.strip().startswith('script-src')][0]
        self.assertNotIn('unsafe-inline', script_src)
        self.assertIn("'self'", script_src)
        self.assertIn("'nonce-", script_src)

    def test_nonce_har_sorovda_yangi(self):
        a, b = self.csp('/'), self.csp('/')
        nonce = lambda s: re.search(r"'nonce-([^']+)'", s).group(1)
        self.assertNotEqual(nonce(a), nonce(b))
        self.assertGreaterEqual(len(nonce(a)), 16)

    def test_admin_shablonidagi_skript_nonce_oladi(self):
        r = self.client.get('/admin/login/')
        nonce = re.search(r"'nonce-([^']+)'", r['Content-Security-Policy']).group(1)
        html = r.content.decode()
        self.assertIn('nonce="%s"' % nonce, html)
        self.assertFalse(re.search(r'<script(?![^>]*\bnonce=)(?![^>]*\bsrc=)[^>]*>', html))


class SahifalardaInlineYoqTest(SimpleTestCase):
    def matn(self, nom):
        with open(settings.BASE_DIR.parent / nom, encoding='utf-8') as f:
            return f.read()

    def test_inline_skript_yoq(self):
        for nom in SAHIFALAR:
            with self.subTest(sahifa=nom):
                self.assertEqual(INLINE_SKRIPT.findall(self.matn(nom)), [],
                                 f'{nom}: inline <script> topildi — tashqi fayl (scripts/) ga ko\'chiring')

    def test_inline_handler_yoq(self):
        for nom in SAHIFALAR:
            with self.subTest(sahifa=nom):
                matn = re.sub(r'<!--.*?-->', '', self.matn(nom), flags=re.S)   # izohlar hisobga olinmaydi
                self.assertEqual([m.group(0) for m in HANDLER.finditer(matn)], [],
                                 f'{nom}: onclick="..." topildi — data-h-click yoki addEventListener ishlating')

    def test_inline_handler_tashqi_skriptlarda_ham_yoq(self):
        import glob
        for yol in glob.glob(str(settings.BASE_DIR.parent / 'scripts' / '*.js')):
            if yol.endswith('hodisa-boshqaruvchi.js'):
                continue
            with self.subTest(fayl=yol):
                with open(yol, encoding='utf-8') as f:
                    self.assertEqual(
                        [m.group(0) for m in HANDLER.finditer(f.read())], [],
                        'JS shablonida onclick="..." topildi (CSP bloklaydi)')

    def test_javascript_url_yoq(self):
        for nom in SAHIFALAR:
            with self.subTest(sahifa=nom):
                self.assertNotIn('href="javascript:', self.matn(nom))
