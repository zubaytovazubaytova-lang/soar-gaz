/* ============================================================
   SOAR GAZ — Service Worker
   ------------------------------------------------------------
   Vazifasi: saytni telefonda tez ochish va internet uzilganda
   butunlay "o'lik" bo'lib qolmasligi.

   ASOSIY QOIDA: bu yerda faqat O'ZGARMAS resurslar keshlanadi
   (uslub, shrift, ikonka). Sahifalar va API javoblari HECH QACHON
   keshdan birinchi berilmaydi — aks holda mijoz eski narxni yoki
   eski buyurtma holatini ko'rib qoladi. Bu real xavf, shuning
   uchun strategiyalar quyida ataylab ajratilgan.
   ============================================================ */

const VERSIYA = 'soargaz-v2';
const STATIK_KESH = `${VERSIYA}-statik`;
const SAHIFA_KESH = `${VERSIYA}-sahifa`;
const OFFLINE_SAHIFA = '/offline.html';

// O'rnatish paytida oldindan yuklanadigan o'zgarmas fayllar
const OLDINDAN = [
  OFFLINE_SAHIFA,
  '/assets/tailwind.css',
  '/assets/inter.css',
  '/assets/fonts/inter-latin.woff2',
  '/assets/fonts/inter-latin-ext.woff2',
  // Diqqat: manzillar sahifa SO'RAYDIGANI bilan aynan bir xil bo'lishi shart —
  // `?v=2` kesh kalitining bir qismi, usiz oldindan yuklangan nusxa
  // ishlatilmay qoladi.
  '/vendor/fontawesome/css/all.min.css?v=2',
  '/vendor/fontawesome/webfonts/fa-solid-900.woff2?v=2',
  '/assets/icons/favicon-48.png?v=2',
];

self.addEventListener('install', (e) => {
  e.waitUntil((async () => {
    const kesh = await caches.open(STATIK_KESH);
    // Bittasi yuklanmasa ham o'rnatish buzilmasin
    await Promise.allSettled(OLDINDAN.map((u) => kesh.add(u)));
    await self.skipWaiting();
  })());
});

self.addEventListener('activate', (e) => {
  e.waitUntil((async () => {
    // Eski versiya keshlarini tozalaymiz
    const nomlar = await caches.keys();
    await Promise.all(
      nomlar.filter((n) => !n.startsWith(VERSIYA)).map((n) => caches.delete(n))
    );
    await self.clients.claim();
  })());
});

self.addEventListener('fetch', (e) => {
  const req = e.request;

  // Faqat GET. POST/PUT (buyurtma berish, to'lov) hech qachon ushlanmaydi.
  if (req.method !== 'GET') return;

  const url = new URL(req.url);

  // Boshqa domenlar (Click, Payme, OpenStreetMap plitalari) — tegmaymiz
  if (url.origin !== self.location.origin) return;

  // API — HAR DOIM tarmoqdan. Narx, buyurtma holati, OTP kabi
  // ma'lumotlar keshlanishi mumkin emas.
  if (url.pathname.startsWith('/api/')) return;

  // Django admin va boshqaruv panellari — keshlanmaydi
  if (url.pathname.startsWith('/admin/') || url.pathname.startsWith('/boshqaruv/')) return;

  // Do'kon (Next.js) o'z keshiga ega — aralashmaymiz
  if (url.pathname.startsWith('/xaridlar/')) return;

  // ── HTML sahifalar: avval tarmoq, uzilsa kesh ────────────────
  // Mijoz doim eng yangi versiyani ko'radi; internet yo'q bo'lsa
  // oxirgi ko'rgan nusxasi, u ham bo'lmasa offline sahifa chiqadi.
  if (req.mode === 'navigate') {
    e.respondWith((async () => {
      try {
        const javob = await fetch(req);
        const kesh = await caches.open(SAHIFA_KESH);
        kesh.put(req, javob.clone());
        return javob;
      } catch (err) {
        const keshlangan = await caches.match(req);
        return keshlangan || (await caches.match(OFFLINE_SAHIFA));
      }
    })());
    return;
  }

  // ── O'zgarmas resurslar: avval kesh, bo'lmasa tarmoq ─────────
  // /assets/ va /vendor/ deploy paytidagina o'zgaradi.
  if (url.pathname.startsWith('/assets/') || url.pathname.startsWith('/vendor/')) {
    e.respondWith((async () => {
      const keshlangan = await caches.match(req);
      if (keshlangan) return keshlangan;
      const javob = await fetch(req);
      if (javob.ok) {
        const kesh = await caches.open(STATIK_KESH);
        kesh.put(req, javob.clone());
      }
      return javob;
    })());
    return;
  }

  // ── Mahsulot rasmlari: kesh bo'lsa beramiz, fonda yangilaymiz ─
  if (url.pathname.startsWith('/images/')) {
    e.respondWith((async () => {
      const kesh = await caches.open(STATIK_KESH);
      const keshlangan = await kesh.match(req);
      const tarmoq = fetch(req).then((javob) => {
        // Videolarni keshlamaymiz — har biri 2-3 MB, joy yetmaydi
        if (javob.ok && !/\.(mp4|webm|mov)$/i.test(url.pathname)) {
          kesh.put(req, javob.clone());
        }
        return javob;
      }).catch(() => keshlangan);
      return keshlangan || tarmoq;
    })());
  }
});
