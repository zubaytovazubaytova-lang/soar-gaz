  // ====== API CONFIG ======
  // Sayt Django serveri orqali berilsa (production ham, localhost:8001 ham)
  // nisbiy manzil ishlatiladi. Faqat fayl sifatida ochilganda dev backendga
  // to'g'ridan-to'g'ri murojaat qilinadi.
  const API = location.protocol === 'file:' ? 'http://localhost:8001/api' : '/api';

  // ── PWA service worker ─────────────────────────────────────────
  // Sayt telefon ekraniga qo'shilishi va aloqa uzilganda ham
  // ochilishi uchun. Faqat http(s) da ishlaydi — fayl sifatida
  // ochilganda brauzer service worker'ga ruxsat bermaydi.
  if ('serviceWorker' in navigator && location.protocol !== 'file:') {
    window.addEventListener('load', () => {
      navigator.serviceWorker.register('/sw.js').catch((e) => {
        console.warn('Service worker ro\'yxatdan o\'tmadi:', e);
      });
    });
  }

  // ── Xaridlar do'koni (Next.js ilovasi) ─────────────────────────
  // Productionda nginx `/xaridlar/` manzilini Next.js (:3000) ga proxy qiladi
  // — shuning uchun nisbiy manzil ishlatiladi va domen kodda qolmaydi.
  // Dev rejimda (localhost yoki LAN orqali telefondan sinaganda) Next.js
  // alohida portda turadi. `location.hostname` dan foydalanamiz: shunda
  // telefondan 192.168.x.x:8001 ga kirilganda do'kon ham o'sha IP dan ochiladi.
  const XARIDLAR_URL = (function () {
    const h = location.hostname;
    const dev = location.protocol === 'file:' || h === 'localhost' || h === '127.0.0.1'
                || /^192\.168\./.test(h) || /^10\./.test(h);
    if (!dev) return '/xaridlar/';
    return 'http://' + (location.protocol === 'file:' ? 'localhost' : h) + ':3000';
  })();
  function openXaridlar(e) {
    if (e) e.preventDefault();
    window.open(XARIDLAR_URL, '_blank', 'noopener');
  }

  function apiToken() { return localStorage.getItem('sg_token'); }
  function apiUser()  { return JSON.parse(localStorage.getItem('sg_user') || 'null'); }
  function apiSaveSession(data) {
    // Refresh token endi httpOnly cookie'da (serverga tegishli) — JavaScript uni saqlamaydi
    localStorage.setItem('sg_token', data.access);
    localStorage.removeItem('sg_refresh');
    localStorage.setItem('sg_user', JSON.stringify(data.user));
  }
  function apiClearSession() {
    // Serverda refresh tokenni bekor qilamiz va cookie'ni o'chiramiz (o'g'irlangan nusxa
    // ishlamasin). Javobni kutmaymiz: tarmoq bo'lmasa ham mijoz baribir chiqib ketadi.
    try {
      fetch(API + '/auth/chiqish/', {
        method: 'POST', keepalive: true,
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ refresh: localStorage.getItem('sg_refresh') || undefined }),
      }).catch(() => {});
    } catch (e) {}
    ['sg_token','sg_refresh','sg_user'].forEach(k => localStorage.removeItem(k));
  }

  // Access token qisqa (30 daqiqa), shuning uchun muddati tugasa jimgina yangilanadi:
  // refresh token httpOnly cookie'da turadi va brauzer uni o'zi yuboradi. Mijozdan
  // qayta-qayta SMS kod so'ralmaydi — sessiya 90 kun davom etadi (faol bo'lsa uzayadi).
  let _tokenYangilash = null;   // bir vaqtda faqat bitta so'rov ketadi
  function tokenYangila() {
    if (_tokenYangilash) return _tokenYangilash;
    // Eski (cookie'ga o'tishdan oldingi) sessiya: localStorage'dagi refresh bir marta
    // serverga beriladi, server uni cookie'ga almashtiradi, biz esa o'chirib tashlaymiz.
    const eski = localStorage.getItem('sg_refresh');

    _tokenYangilash = fetch(API + '/auth/token/yangilash/', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(eski ? { refresh: eski } : {}),
    })
      .then(res => res.ok ? res.json() : null)
      .then(data => {
        localStorage.removeItem('sg_refresh');
        if (!data || !data.access) return false;
        localStorage.setItem('sg_token', data.access);
        return true;
      })
      .catch(() => false)
      .finally(() => { _tokenYangilash = null; });

    return _tokenYangilash;
  }

  async function apiReq(method, path, body, auth = true, qaytaUrinish = true, qoshimcha = null) {
    const headers = { 'Content-Type': 'application/json', ...(qoshimcha || {}) };
    if (auth) headers['Authorization'] = 'Bearer ' + apiToken();
    try {
      const res = await fetch(API + path, {
        method,
        headers,
        body: body ? JSON.stringify(body) : undefined,
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw { status: res.status, data };
      return data;
    } catch (err) {
      // 401 — tokenni yangilab, so'rovni bir marta qaytaramiz.
      // Faqat yangilash ham muvaffaqiyatsiz bo'lsa sessiya o'chiriladi.
      if (err.status === 401 && auth && qaytaUrinish) {
        if (await tokenYangila()) return apiReq(method, path, body, auth, false, qoshimcha);
        apiClearSession();
      }
      throw err;
    }
  }

  const apiGet    = (path)       => apiReq('GET',    path, null);
  const apiGetPub = (path)       => apiReq('GET',    path, null, false);  // ochiq (tokensiz) GET
  const apiPost   = (path, body) => apiReq('POST',   path, body, false);
  const apiPostA  = (path, body) => apiReq('POST',   path, body, true);
  // Buyurtma endpointlari: tizimga kirgan bo'lsa token yuboriladi (ega yoki xodim to'liq
  // ma'lumot oladi), mehmon uchun ma'lumot niqoblanadi.
  // Mehmon xaridi egasi telefonining oxirgi 4 raqamini ko'rsatsa, to'liq ma'lumot oladi
  // (buyurtma yaratilganda yoki so'ralganda shu tab sessionStorage'iga eslab qolinadi).
  const xaridTelOxiri = (path) => {
    try {
      const m = String(path).match(/^\/xaridlar\/([^/?]+)\//);
      return m ? sessionStorage.getItem('sg_tel_' + m[1]) : null;
    } catch (e) { return null; }
  };
  const apiGetXarid  = (path) => {
    const t = xaridTelOxiri(path);
    return apiReq('GET', path, null, !!apiToken(), true, t ? { 'X-Telefon-Oxiri': t } : null);
  };
  const apiPostXarid = (path, body) => apiReq('POST', path, body, !!apiToken());
  // O'zgartiruvchi buyurtma amallari (to'lov usuli, qayta yetkazish): egalik tasdig'i kerak.
  // Server telefon so'rasa — oxirgi 4 raqam so'raladi va shu tab uchun eslab qolinadi.
  const apiPostXaridTasdiq = async (path, body) => {
    const saqlangan = xaridTelOxiri(path);
    try {
      return await apiPostXarid(path, saqlangan ? { ...body, telefon: saqlangan } : body);
    } catch (err) {
      if (!(err && err.status === 403 && err.data && err.data.telefon_kerak)) throw err;
      const tel = prompt("Buyurtma egasini tasdiqlash uchun telefon raqamingizning oxirgi 4 raqamini kiriting:");
      if (!tel) throw err;
      const r = await apiPostXarid(path, { ...body, telefon: tel.trim() });
      try { sessionStorage.setItem('sg_tel_' + String(path).split('/')[2], tel.replace(/\D/g, '').slice(-4)); } catch (e) {}
      return r;
    }
  };
  // Profildagi email / qo'shimcha telefon o'zgarishi SMS kod talab qiladi
  const apiPatchTasdiq = async (path, body) => {
    try {
      return await apiPatch(path, body);
    } catch (err) {
      if (!(err && err.status === 403 && err.data && err.data.kod_kerak)) throw err;
      await apiPostA('/auth/tasdiq-kodi/', {});
      const kod = prompt("Xavfsizlik uchun telefoningizga SMS kod yuborildi.\nKodni kiriting:");
      if (!kod) throw { status: 400, data: { detail: 'Tasdiqlash bekor qilindi' } };
      return apiPatch(path, { ...body, tasdiq_kodi: kod.trim() });
    }
  };
  const apiPatch  = (path, body) => apiReq('PATCH',  path, body, true);
  const apiDelete = (path)       => apiReq('DELETE', path, null, true);

  async function apiUpload(path, formData) {
    const res = await fetch(API + path, {
      method: 'POST',
      headers: { 'Authorization': 'Bearer ' + apiToken() },
      body: formData,
    });
    return res.json();
  }

  function apiErr(err) {
    const msg = err?.data?.detail || err?.data?.non_field_errors?.[0]
              || Object.values(err?.data || {})[0]?.[0]
              || 'Server bilan bog\'lanishda xato';
    showToast(msg);
  }

  // ====== Navbar scroll
  window.addEventListener('scroll', () => {
    document.getElementById('navbar').classList.toggle('nav-scrolled', window.scrollY > 50);
    navFaolBelgila();
  });

  // Faol bo'limni ko'k qilib belgilash (scroll-spy).
  // Faqat sahifa ichidagi anchorlar tekshiriladi — kabinet tugmalari emas.
  function navFaolBelgila() {
    const links = document.querySelectorAll('.nav-link[href^="#"]');
    let faol = null;
    links.forEach(a => {
      const bolim = document.querySelector(a.getAttribute('href'));
      if (bolim && bolim.getBoundingClientRect().top <= 100) faol = a;
    });
    links.forEach(a => a.classList.toggle('faol', a === faol));
  }
  navFaolBelgila();

  // ====== Ko'rinish maydoniga kirganda ishga tushadigan animatsiyalar
  //  1) fade-in bloklari yumshoq paydo bo'ladi
  //  2) progress barlar 0 dan o'z qiymatiga to'ladi
  const korinishKuzatuvchi = new IntersectionObserver((yozuvlar) => {
    yozuvlar.forEach(y => {
      if (!y.isIntersecting) return;
      y.target.classList.add(y.target.classList.contains('progress-fill') ? 'tola' : 'korindi');
      korinishKuzatuvchi.unobserve(y.target);   // bir marta ishlaydi
    });
  }, { threshold: 0.15, rootMargin: '0px 0px -40px 0px' });

  function animatsiyalarniUlash() {
    document.querySelectorAll('.fade-in:not(.korindi), .progress-fill:not(.tola)')
      .forEach(el => korinishKuzatuvchi.observe(el));
  }

  // Bo'lim sarlavhalari va kartochkalarga fade-in avtomatik beriladi
  function fadeInBelgila() {
    document.querySelectorAll('section > div > .text-center, .card, .stat-card')
      .forEach(el => el.classList.add('fade-in'));
  }

  document.addEventListener('DOMContentLoaded', () => {
    fadeInBelgila();
    animatsiyalarniUlash();
    document.querySelectorAll('select[data-hudud]').forEach(joylashuvUla);
  });

  // ---- Viloyat -> tuman -> mahalla ----
  // Viloyat va tuman ro'yxatdan TANLANADI, mahalla/ko'cha esa qo'lda
  // yoziladi va ixtiyoriy. Viloyat tanlovi va mahalla maydoni shu yerda
  // yaratiladi: uchta forma uch xil uslubda, markupni qo'lda takrorlash
  // xatoga olib keladi — tuman tanlovining o'z sinf/uslubi ko'chiriladi.
  function joylashuvUla(tumanSel) {
    if (!tumanSel || tumanSel.dataset.ulangan) return;
    tumanSel.dataset.ulangan = '1';

    const asos = tumanSel.id || ('hudud' + Math.random().toString(36).slice(2, 7));
    if (!tumanSel.id) tumanSel.id = asos;
    const guruhlar = Array.from(tumanSel.getElementsByTagName('optgroup'));

    // Yorliqni nusxalash uchun tuman tanlovining yorlig'ini topamiz
    const yorliq = tumanSel.previousElementSibling &&
                   tumanSel.previousElementSibling.tagName === 'LABEL'
                   ? tumanSel.previousElementSibling : null;
    const yorliqYasa = (matn, uchun) => {
      if (!yorliq) return null;
      const y = yorliq.cloneNode(true);
      y.textContent = matn;
      y.setAttribute('for', uchun);
      return y;
    };

    // --- Viloyat tanlovi (tuman oldiga) ---
    const viloyatSel = document.createElement('select');
    viloyatSel.id = asos + '-viloyat';
    viloyatSel.className = tumanSel.className;
    viloyatSel.setAttribute('style', tumanSel.getAttribute('style') || '');
    if (tumanSel.required) viloyatSel.required = true;
    viloyatSel.innerHTML = '<option value="">Tanlang...</option>' +
      guruhlar.map(g => `<option>${g.label}</option>`).join('');

    const vYorliq = yorliqYasa('Viloyat *', viloyatSel.id);
    (yorliq || tumanSel).insertAdjacentElement('beforebegin', viloyatSel);
    if (vYorliq) viloyatSel.insertAdjacentElement('beforebegin', vYorliq);
    if (yorliq) yorliq.textContent = 'Tuman / shahar *';

    // --- Mahalla maydoni (tuman ortidan) ---
    const mahalla = document.createElement('input');
    mahalla.type = 'text';
    mahalla.id = asos + '-mahalla';
    mahalla.maxLength = 120;
    mahalla.placeholder = "ixtiyoriy — masalan: Navro'z MFY, Bog' ko'chasi 12";
    mahalla.className = tumanSel.className;
    mahalla.setAttribute('style', tumanSel.getAttribute('style') || '');
    tumanSel.insertAdjacentElement('afterend', mahalla);
    const mYorliq = yorliqYasa("Mahalla / ko'cha", mahalla.id);
    if (mYorliq) mahalla.insertAdjacentElement('beforebegin', mYorliq);

    function filtrla(tozala) {
      const v = viloyatSel.value;
      guruhlar.forEach(g => {
        const mos = !v || g.label === v;
        g.style.display = mos ? '' : 'none';
        if (!mos && tozala && tumanSel.selectedOptions[0] &&
            tumanSel.selectedOptions[0].parentElement === g) tumanSel.value = '';
      });
      tumanSel.disabled = !v;
    }

    viloyatSel.addEventListener('change', () => filtrla(true));
    // Tuman tashqaridan o'rnatilganda (profil yuklanganda) chaqiriladi
    tumanSel.viloyatniMoslash = function () {
      const t = tumanSel.selectedOptions[0];
      if (t && t.parentElement.tagName === 'OPTGROUP') viloyatSel.value = t.parentElement.label;
      filtrla(false);
    };
    tumanSel.viloyatniMoslash();
  }

  // Mobile nav
  function toggleNav() {
    const m = document.getElementById('mobileNav');
    const i = document.getElementById('navIcon');
    m.classList.toggle('hidden');
    i.className = m.classList.contains('hidden') ? 'fas fa-bars' : 'fas fa-times';
  }

  // Counter animation
  function animateCounters() {
    document.querySelectorAll('[data-target]').forEach(el => {
      const target = +el.dataset.target;
      const step = Math.ceil(target / 60);
      let cur = 0;
      const t = setInterval(() => {
        cur = Math.min(cur + step, target);
        el.textContent = cur + (target >= 100 || el.hasAttribute('data-plus') ? '+' : '');
        if (cur >= target) clearInterval(t);
      }, 30);
    });
  }
  const obs = new IntersectionObserver(entries => {
    if (entries[0].isIntersecting) { animateCounters(); obs.disconnect(); }
  });
  const counterEl = document.querySelector('[data-target]');
  if (counterEl) obs.observe(counterEl);

  // ---- PRODUCT FILTER ----
  function filterCat(cat, btn) {
    document.querySelectorAll('#filterTabs button').forEach(b => {
      b.className = 'px-5 py-2.5 rounded-full text-sm font-semibold border border-cobalt-500/30 text-gray-400 hover:text-gold-400 transition-all';
    });
    btn.className = 'tab-active px-5 py-2.5 rounded-full text-sm font-semibold border border-cobalt-500/25 transition-all';
    document.querySelectorAll('.product').forEach(p => {
      p.style.display = (cat === 'all' || p.dataset.cat === cat) ? 'block' : 'none';
    });
  }

  // ---- CART ----
  // Har bir element: { nom, narx, qty, ikona, rang }
  //   ikona/rang — mahsulot ko'rinishi (katalog bo'limidan olinadi)
  const CART_KEY = 'sg_savat';

  // Savatni localStorage'dan tiklash — brauzer yopilsa ham yo'qolmaydi
  function cartYukla() {
    try {
      const xom = JSON.parse(localStorage.getItem(CART_KEY) || '[]');
      if (!Array.isArray(xom)) return [];
      // Faqat to'g'ri yozuvlarni olamiz (eski/buzilgan ma'lumotdan himoya)
      return xom
        .filter(c => c && typeof c.nom === 'string' && Number(c.qty) > 0)
        .map(c => ({
          nom: c.nom,
          narx: Number(c.narx) || 0,
          qty: Math.min(Math.max(parseInt(c.qty, 10) || 1, 1), 999),
          ikona: typeof c.ikona === 'string' ? c.ikona : 'fa-box',
          rang: typeof c.rang === 'string' ? c.rang : '#ff8a00',
        }));
    } catch (e) {
      return [];
    }
  }

  function cartSaqla() {
    try { localStorage.setItem(CART_KEY, JSON.stringify(cart)); } catch (e) { /* to'lgan bo'lsa e'tiborsiz */ }
  }

  let cart = cartYukla();

  function cartTotalQty() { return cart.reduce((s,c)=>s+c.qty,0); }
  function cartTotalSum() { return cart.reduce((s,c)=>s+c.narx*c.qty,0); }

  // Savatga qo'shish (miqdor birlashtiriladi)
  function cartAdd(nom, narx, qty = 1, korinish = {}) {
    narx = narx || 0;
    const ikona = korinish.ikona || 'fa-box';
    const rang  = korinish.rang  || '#ff8a00';
    const ex = cart.find(c => c.nom === nom && c.narx === narx);
    if (ex) ex.qty = Math.min(ex.qty + qty, 999);
    else cart.push({ nom, narx, qty, ikona, rang });
    cartSync();
  }

  // Barcha savat ko'rsatkichlarini yangilash (+ saqlash)
  function cartSync() {
    cartSaqla();
    const n = cartTotalQty();
    const cc = document.getElementById('cartCount'); if (cc) cc.textContent = n;
    const gc = document.getElementById('grl-cart-count'); if (gc) gc.textContent = n;
    const hc = document.getElementById('cart-hdr-count'); if (hc) hc.textContent = n;
    const bar = document.getElementById('cartBar'); if (bar) bar.classList.toggle('hidden', n === 0);
    const badge = document.getElementById('grl-cart-badge');
    if (badge) {
      badge.classList.toggle('hidden', n === 0);
      badge.classList.toggle('flex', n > 0);
    }
    const page = document.getElementById('savat-page');
    if (page && !page.classList.contains('hidden')) renderCart();
  }

  function cartSetQty(idx, delta) {
    if (!cart[idx]) return;
    cart[idx].qty = Math.min(cart[idx].qty + delta, 999);
    if (cart[idx].qty <= 0) cart.splice(idx, 1);
    cartSync();
  }
  function cartRemove(idx) { cart.splice(idx, 1); cartSync(); }
  function clearCart() { cart = []; cartSync(); }

  // Umumiy katalog uchun (narxsiz) — tugma animatsiyasi bilan
  function addToCart(btn, name) {
    cartAdd(name, 0, 1);
    btn.innerHTML = '<i class="fas fa-check mr-1"></i>Qo\'shildi';
    btn.classList.add('bg-green-500/20','text-green-400');
    btn.classList.remove('text-gold-400');
    setTimeout(() => {
      btn.innerHTML = '<i class="fas fa-cart-plus mr-1"></i>Qo\'shish';
      btn.classList.remove('bg-green-500/20','text-green-400');
      btn.classList.add('text-gold-400');
    }, 2000);
    showToast(name + ' savatga qo\'shildi!');
  }

  // ---- SAVATCHA SAHIFASI ----
  function openCartPage() {
    renderCart();
    document.getElementById('savat-page').classList.remove('hidden');
    document.body.style.overflow = 'hidden';
  }
  function closeCartPage() {
    document.getElementById('savat-page').classList.add('hidden');
    const gOpen = !document.getElementById('garelka-page').classList.contains('hidden');
    const kOpen = !document.getElementById('kat-page').classList.contains('hidden');
    document.body.style.overflow = (gOpen || kOpen) ? 'hidden' : '';
  }
  // ─────────────────────────────────────────────────────────────
  //  XARID RASMIYLASHTIRISH — backend: /api/xaridlar/
  //  Summani backend qayta hisoblaydi, biz faqat ko'rsatamiz.
  // ─────────────────────────────────────────────────────────────
  // Narx qoidalari — backend settings.py bilan bir xil.
  // Sahifa ochilganda /xaridlar/narxlar/ dan yangilanadi, shuning uchun
  // qoida faqat bitta joyda (Django settings) o'zgartiriladi.
  const XARID_NARX = { ornatish: 250000, yetkazish: 30000, bepul_chegara: 1000000 };

  let xaridYetk  = 'kuryer';
  let xaridTlv   = 'naqd';
  let xaridPromo = null;   // { kod, tavsif, chegirma }
  let xaridQadam = 1;      // joriy bosqich (1–4)
  let xaridBolibOy = 0;    // bo'lib to'lash muddati (oy), 0 — tanlanmagan
  let xaridTuman = '';     // yetkazish hududi — narx va muddat shunga bog'liq
  let xaridKunTanlov = '', xaridOraliqTanlov = '';

  const MANZIL_KEY = 'sg_manzillar';
  const XARID_QADAM_SONI = 4;

  const TOLOV_NOMI = {
    naqd:  'Naqd (yetkazishda)',
    click: 'Click',
    payme: 'Payme',
    karta: 'Uzcard / Humo',
    bolib: "Bo'lib to'lash",
  };

  async function xaridNarxlarYukla() {
    try {
      const n = await apiGetPub('/xaridlar/narxlar/');
      if (n && typeof n.ornatish === 'number') Object.assign(XARID_NARX, n);
    } catch (e) { /* backend yo'q bo'lsa standart qiymatlar ishlatiladi */ }
  }

  const somFmt = (n) => (n || 0).toLocaleString('uz-UZ') + " so'm";

  // ---- Hudud (tuman) bo'yicha yetkazish ----
  function tumanlarChiz() {
    const sel = document.getElementById('xa-tuman');
    const royxat = XARID_NARX.hududlar || [];
    if (!sel || sel.options.length > 1) return;   // bir marta to'ldiramiz
    sel.innerHTML = '<option value="">— Tumanni tanlang —</option>' +
      royxat.map(h => `<option value="${h.tuman}">${h.tuman} — ${somFmt(h.narx)}, ${h.muddat}</option>`).join('');
    if (xaridTuman) sel.value = xaridTuman;
  }

  function tumanMalumoti(tuman) {
    return (XARID_NARX.hududlar || []).find(h => h.tuman === tuman) || null;
  }

  function tumanTanlandi() {
    xaridTuman = document.getElementById('xa-tuman').value;
    const h = tumanMalumoti(xaridTuman);
    const info = document.getElementById('xa-tuman-info');
    info.innerHTML = h
      ? `<i class="fas fa-truck mr-1" style="color:#0d6efd"></i>Yetkazish: <b style="color:#0d6efd">${somFmt(h.narx)}</b>
         · <b style="color:#0d6efd">${h.muddat}</b>
         ${XARID_NARX.bepul_chegara ? `· ${somFmt(XARID_NARX.bepul_chegara)}dan yuqori xaridda bepul` : ''}`
      : '<i class="fas fa-circle-info mr-1"></i>Tuman tanlansa narx va muddat aniqlanadi';
    xaridXato('');
    xaridXulosa();
  }

  // Nomdan URL-xavfsiz slug (backend SlugField talab qiladi).
  // Lotin bo'lmagan nomlar (kirill va h.k.) uchun tartib raqami bilan almashtiriladi.
  function xaridSlug(nom, tartib) {
    const s = (nom || '').toLowerCase()
      .replace(/['’`]/g, '')
      .replace(/[^a-z0-9]+/g, '-')
      .replace(/^-+|-+$/g, '')
      .slice(0, 150);
    return s.length >= 2 ? s : 'mahsulot-' + (tartib || 1);
  }

  function cartCheckout() {
    if (!cart.length) { showToast('Savat bo\'sh'); return; }
    openXaridPage();
  }

  function openXaridPage() {
    // Har safar toza boshlanadi — eski promokod savat o'zgargach yaroqsiz bo'lishi mumkin
    xaridPromo = null;
    document.getElementById('xa-promo').value = '';
    document.getElementById('xa-promo-info').classList.add('hidden');
    document.getElementById('xa-promo-btn').textContent = "Qo'llash";
    xaridKunTanlov = ''; xaridOraliqTanlov = ''; xaridBolibOy = 0;
    document.querySelectorAll('[data-kun],[data-oraliq]').forEach(el => el.classList.remove('tanlangan'));
    document.getElementById('xa-sana-wrap').classList.add('hidden');
    xaridXato('');
    document.getElementById('xarid-form').classList.remove('hidden');
    document.getElementById('xarid-natija').classList.add('hidden');
    document.getElementById('xarid-kuzat').classList.add('hidden');
    document.getElementById('xarid-title').innerHTML =
      'Buyurtmani <span style="background:linear-gradient(135deg,#0d6efd,#0d6efd,#17538f);-webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text">Rasmiylashtirish</span>';
    document.getElementById('xa-ornatish-narx').textContent = '+' + somFmt(XARID_NARX.ornatish);
    document.getElementById('xa-kuryer-narx').textContent =
      somFmt(XARID_NARX.yetkazish) + " · " + somFmt(XARID_NARX.bepul_chegara) + "dan yuqori — bepul";
    const bolibShart = document.getElementById('xa-bolib-shart');
    const oylar = (XARID_NARX.bolib || []).map(s => s.oy).join(' / ');
    bolibShart.textContent = oylar
      ? `${oylar} oy · ${somFmt(XARID_NARX.bolib_eng_kam)}dan yuqori buyurtmalarga`
      : 'Shartnoma asosida, operator tasdiqlaydi';

    // Ro'yxatdan o'tgan foydalanuvchi bo'lsa, ma'lumotini oldindan to'ldiramiz
    const u = apiUser();
    if (u) {
      const ism = document.getElementById('xa-ism'), tel = document.getElementById('xa-tel');
      const man = document.getElementById('xa-manzil');
      if (!ism.value) ism.value = u.ism || '';
      if (!tel.value) tel.value = u.telefon || '';
      if (!man.value) man.value = u.manzil || '';
    }

    const f = XARID_NARX.filial || {};
    if (f.manzil) {
      document.getElementById('xa-filial-info').textContent =
        `Bepul · ${f.manzil}${f.muddat ? ' · ' + f.muddat + ' tayyor' : ''}`;
    }
    tumanlarChiz();
    xaridYetkazish(xaridYetk);
    xaridTolov(xaridTlv);
    manzillarChiz();
    xaridVaqtYangila();
    xaridBosqich(1, true);
    document.getElementById('xarid-page').classList.remove('hidden');
    document.body.style.overflow = 'hidden';
  }

  // Mobil xulosani ochish/yopish
  function xulosaOch() {
    const el = document.getElementById('xa-xulosa');
    const ochiq = !el.classList.contains('hidden');
    el.classList.toggle('hidden', ochiq);
    document.getElementById('xa-xulosa-toggle').textContent = ochiq ? 'Ochish' : 'Yopish';
  }

  function closeXaridPage() {
    xaridKuzatToxtat();
    document.getElementById('xarid-page').classList.add('hidden');
    const savatOchiq = !document.getElementById('savat-page').classList.contains('hidden');
    document.body.style.overflow = savatOchiq ? 'hidden' : '';
  }

  function xaridYetkazish(usul) {
    xaridYetk = usul;
    document.querySelectorAll('[data-yetk]').forEach(el =>
      el.classList.toggle('tanlangan', el.dataset.yetk === usul));
    // Filialdan olishda manzil ham, yetkazish vaqti ham kerak emas
    const manzilForm = document.getElementById('xa-manzil-form');
    const manzillar  = document.getElementById('xa-manzillar-wrap');
    const kuryerMi = usul === 'kuryer';
    manzilForm.style.display = kuryerMi ? '' : 'none';
    if (!kuryerMi) manzillar.classList.add('hidden');
    else if (manzillarOqi().length) manzillar.classList.remove('hidden');
    document.getElementById('xa-vaqt-card').style.display = kuryerMi ? '' : 'none';
    // Yetkazish usuli summaga ta'sir qiladi
    if (document.getElementById('xa-xulosa')) xaridXulosa();
  }

  // ─────────────────────────────────────────────────────────────
  //  Bosqichlar bo'ylab harakat
  // ─────────────────────────────────────────────────────────────
  function xaridBosqich(n, tekshirmasdan) {
    n = Math.max(1, Math.min(XARID_QADAM_SONI, n));
    // Oldinga o'tishda joriy bosqich to'ldirilganini tekshiramiz
    if (!tekshirmasdan && n > xaridQadam) {
      for (let q = xaridQadam; q < n; q++) {
        const xato = xaridQadamTekshir(q);
        if (xato) { xaridBosqich(q, true); xaridXato(xato); return; }
      }
    }
    xaridQadam = n;
    xaridXato('');

    for (let i = 1; i <= XARID_QADAM_SONI; i++) {
      document.getElementById('xa-panel-' + i).classList.toggle('hidden', i !== n);
    }
    document.querySelectorAll('.xa-step').forEach(el => {
      const s = +el.dataset.step;
      el.classList.toggle('joriy', s === n);
      el.classList.toggle('tugagan', s < n);
    });

    document.getElementById('xa-orqaga').classList.toggle('hidden', n === 1);
    const oldinga = document.getElementById('xa-oldinga');
    oldinga.innerHTML = n === XARID_QADAM_SONI
      ? '<i class="fas fa-check"></i>Buyurtmani tasdiqlash'
      : 'Davom etish<i class="fas fa-arrow-right"></i>';

    if (n === XARID_QADAM_SONI) xaridTasdiqChiz();
    xaridXulosa();
    const sahifa = document.getElementById('xarid-page');
    if (sahifa) sahifa.scrollTop = 0;
  }

  // Bosqichdagi majburiy maydonlarni tekshiradi; xato matnini qaytaradi
  function xaridQadamTekshir(q) {
    if (q === 1) {
      const ism = document.getElementById('xa-ism').value.trim();
      const tel = document.getElementById('xa-tel').value.trim();
      if (!ism) return 'Ism-familiyani kiriting';
      if (tel.replace(/\D/g, '').length < 9) return "To'liq telefon raqamini kiriting";
      if (xaridYetk === 'kuryer') {
        if (!xaridTuman) return 'Yetkazish hududini (tumanni) tanlang';
        if (!document.getElementById('xa-manzil').value.trim())
          return 'Yetkazish manzilini kiriting';
      }
    }
    if (q === 2 && xaridYetk === 'kuryer' && !document.getElementById('xa-manzil').value.trim())
      return 'Kuryer uchun manzil kerak — 1-bosqichga qaytib kiriting';
    if (q === 3 && xaridTlv === 'bolib') {
      const engKam = XARID_NARX.bolib_eng_kam || 0;
      if (engKam && xaridHisobAsos() < engKam)
        return `Bo'lib to'lash ${somFmt(engKam)}dan yuqori buyurtmalarga beriladi`;
      if (!xaridBolibOy) return "Bo'lib to'lash muddatini tanlang";
    }
    return '';
  }

  function xaridOldinga() {
    if (xaridQadam === XARID_QADAM_SONI) { xaridYuborish(); return; }
    const xato = xaridQadamTekshir(xaridQadam);
    if (xato) { xaridXato(xato); return; }
    xaridBosqich(xaridQadam + 1, true);
  }
  function xaridOrqaga() { xaridBosqich(xaridQadam - 1, true); }

  // ─────────────────────────────────────────────────────────────
  //  Saqlangan manzillar (localStorage — mehmon xaridi uchun)
  // ─────────────────────────────────────────────────────────────
  function manzillarOqi() {
    try {
      const x = JSON.parse(localStorage.getItem(MANZIL_KEY) || '[]');
      return Array.isArray(x) ? x.filter(m => m && typeof m.manzil === 'string') : [];
    } catch (e) { return []; }
  }

  function manzilSaqla(yozuv) {
    const bor = manzillarOqi();
    // Bir xil manzil ikki marta saqlanmasin
    if (bor.some(m => m.manzil.toLowerCase() === yozuv.manzil.toLowerCase())) return;
    bor.unshift(yozuv);
    try { localStorage.setItem(MANZIL_KEY, JSON.stringify(bor.slice(0, 5))); } catch (e) {}
  }

  function manzilOchir(i, ev) {
    ev.stopPropagation();
    const bor = manzillarOqi();
    bor.splice(i, 1);
    try { localStorage.setItem(MANZIL_KEY, JSON.stringify(bor)); } catch (e) {}
    manzillarChiz();
    showToast("Manzil ro'yxatdan o'chirildi");
  }

  function manzilTanla(i) {
    const m = manzillarOqi()[i];
    if (!m) return;
    document.getElementById('xa-ism').value = m.ism || '';
    document.getElementById('xa-tel').value = m.telefon || '';
    document.getElementById('xa-manzil').value = m.manzil;
    if (m.tuman) {
      document.getElementById('xa-tuman').value = m.tuman;
      tumanTanlandi();
    }
    document.getElementById('xa-manzil-saqla').checked = false;
    document.querySelectorAll('.xa-manzil-item').forEach((el, j) =>
      el.classList.toggle('tanlangan', j === i));
    xaridXato('');
  }

  function manzillarChiz() {
    const royxat = manzillarOqi();
    const wrap = document.getElementById('xa-manzillar-wrap');
    const box  = document.getElementById('xa-manzillar');
    if (!royxat.length || xaridYetk !== 'kuryer') { wrap.classList.add('hidden'); return; }
    wrap.classList.remove('hidden');
    box.innerHTML = royxat.map((m, i) => `
      <div class="xa-manzil-item" data-h-click="c:manzilTanla" data-a-click="${SG_A([i])}">
        <i class="fas fa-location-dot"></i>
        <div class="flex-1 min-w-0">
          <div class="text-sm text-ink-900">${m.manzil}</div>
          <div class="text-xs mt-0.5" style="color:#5b7fa6">${[m.tuman, m.ism, m.telefon].filter(Boolean).join(' · ')}</div>
        </div>
        <button type="button" data-h-click="c:manzilOchir" data-a-click="${SG_A([i, '@event'])}" title="O'chirish"
          class="w-7 h-7 rounded-lg shrink-0" style="background:rgba(31,72,135,0.04);color:#3d7ab5">
          <i class="fas fa-trash-can text-xs"></i>
        </button>
      </div>`).join('');
  }

  // ─────────────────────────────────────────────────────────────
  //  Yetkazib berish vaqti
  // ─────────────────────────────────────────────────────────────
  function xaridKun(kun) {
    xaridKunTanlov = xaridKunTanlov === kun ? '' : kun;
    document.querySelectorAll('[data-kun]').forEach(el =>
      el.classList.toggle('tanlangan', el.dataset.kun === xaridKunTanlov));
    document.getElementById('xa-sana-wrap').classList.toggle('hidden', xaridKunTanlov !== 'sana');
    if (xaridKunTanlov === 'sana') {
      const inp = document.getElementById('xa-sana');
      const ertaga = new Date(Date.now() + 86400000);
      inp.min = ertaga.toISOString().slice(0, 10);
      if (!inp.value) inp.value = inp.min;
    }
    xaridVaqtYangila();
  }

  function xaridOraliq(oraliq) {
    xaridOraliqTanlov = xaridOraliqTanlov === oraliq ? '' : oraliq;
    document.querySelectorAll('[data-oraliq]').forEach(el =>
      el.classList.toggle('tanlangan', el.dataset.oraliq === xaridOraliqTanlov));
    xaridVaqtYangila();
  }

  // Tanlangan kun + oraliqdan matn yasaydi ("Ertaga, 09:00–12:00")
  function xaridVaqtMatni() {
    let kun = '';
    if (xaridKunTanlov === 'bugun')  kun = 'Bugun';
    if (xaridKunTanlov === 'ertaga') kun = 'Ertaga';
    if (xaridKunTanlov === 'sana') {
      const v = document.getElementById('xa-sana').value;
      if (v) {
        const d = new Date(v + 'T00:00:00');
        kun = d.toLocaleDateString('uz-UZ', { day: 'numeric', month: 'long' });
      }
    }
    return [kun, xaridOraliqTanlov].filter(Boolean).join(', ');
  }

  function xaridVaqtYangila() {
    const matn = xaridVaqtMatni();
    document.getElementById('xa-vaqt-natija').innerHTML = matn
      ? `<i class="fas fa-check mr-1" style="color:#15803d"></i>Tanlandi: <b style="color:#0d6efd">${matn}</b>`
      : "<i class=\"fas fa-circle-info mr-1\"></i>Vaqt tanlanmasa — operator siz bilan kelishib oladi";
    xaridXulosa();
  }

  function izohQosh(matn) {
    const el = document.getElementById('xa-izoh');
    const bor = el.value.trim();
    if (bor.includes(matn.trim())) return;
    el.value = bor ? bor.replace(/[.,\s]*$/, '') + ', ' + matn : matn;
    el.focus();
    // Kursor oxiriga
    el.setSelectionRange(el.value.length, el.value.length);
  }

  function xaridTolov(usul) {
    xaridTlv = usul;
    document.querySelectorAll('[data-tolov]').forEach(el =>
      el.classList.toggle('tanlangan', el.dataset.tolov === usul));
    document.getElementById('xa-bolib-wrap').classList.toggle('hidden', usul !== 'bolib');
    if (usul === 'bolib') bolibOylarChiz();
    xaridXulosa();
  }

  // ─────────────────────────────────────────────────────────────
  //  Bo'lib to'lash
  // ─────────────────────────────────────────────────────────────
  function bolibOylarChiz() {
    const box = document.getElementById('xa-bolib-oylar');
    const shartlar = XARID_NARX.bolib || [];
    box.innerHTML = shartlar.map(s => `
      <button type="button" class="xa-chip" data-oy="${s.oy}" data-h-click="c:bolibOy" data-a-click="${SG_A([s.oy])}">
        ${s.oy} oy${s.ustama ? `<div class="text-[10px] font-normal mt-0.5">+${s.ustama}%</div>`
                             : '<div class="text-[10px] font-normal mt-0.5">foizsiz</div>'}
      </button>`).join('');
    document.querySelectorAll('[data-oy]').forEach(el =>
      el.classList.toggle('tanlangan', +el.dataset.oy === xaridBolibOy));
    bolibNatija();
  }

  function bolibOy(oy) {
    xaridBolibOy = xaridBolibOy === oy ? 0 : oy;
    document.querySelectorAll('[data-oy]').forEach(el =>
      el.classList.toggle('tanlangan', +el.dataset.oy === xaridBolibOy));
    bolibNatija();
    xaridXulosa();
  }

  // Bo'lib to'lash summasi (backenddagi bolib_hisobla bilan bir xil)
  function bolibHisob(jami) {
    const shart = (XARID_NARX.bolib || []).find(s => s.oy === xaridBolibOy);
    if (!shart) return null;
    const umumiy = jami + Math.floor(jami * shart.ustama / 100);
    return { oy: shart.oy, ustama: shart.ustama, umumiy, oylik: Math.ceil(umumiy / shart.oy) };
  }

  function bolibNatija() {
    const el = document.getElementById('xa-bolib-natija');
    const engKam = XARID_NARX.bolib_eng_kam || 0;
    const asos = xaridHisobAsos();

    if (engKam && asos < engKam) {
      el.innerHTML = `<span style="color:#dc2626"><i class="fas fa-circle-exclamation mr-1"></i>
        Bo'lib to'lash ${somFmt(engKam)}dan yuqori buyurtmalarga beriladi</span>`;
      return;
    }
    const b = xaridBolibOy ? bolibHisob(asos) : null;
    el.innerHTML = b
      ? `<i class="fas fa-check mr-1" style="color:#15803d"></i>
         Oyiga <b style="color:#0d6efd">${somFmt(b.oylik)}</b> × ${b.oy} oy
         ${b.ustama ? `(ustama +${b.ustama}%, jami ${somFmt(b.umumiy)})` : '(foizsiz)'}`
      : "<i class=\"fas fa-circle-info mr-1\"></i>Muddatni tanlang";
  }

  // Summani backend bilan bir xil tartibda hisoblaydi:
  // mahsulotlar → chegirma → yetkazish (chegirmadan keyingi summaga qarab) → o'rnatish
  function xaridHisob() {
    const ornatish   = document.getElementById('xa-ornatish').checked;
    const mahsulotlar = cartTotalSum();
    const chegirma    = xaridPromo ? Math.min(xaridPromo.chegirma, mahsulotlar) : 0;
    const oraliq      = mahsulotlar - chegirma;

    // Yetkazish narxi va muddati hududga qarab
    let yetkazish = 0, muddat = '';
    if (xaridYetk === 'kuryer') {
      const h = tumanMalumoti(xaridTuman);
      const bepul = XARID_NARX.bepul_chegara && oraliq >= XARID_NARX.bepul_chegara;
      yetkazish = bepul ? 0 : (h ? h.narx : XARID_NARX.yetkazish);
      muddat = h ? h.muddat : '';
    } else {
      muddat = (XARID_NARX.filial || {}).muddat || '';
    }
    const ornatishNarxi = ornatish ? XARID_NARX.ornatish : 0;
    const asos = oraliq + yetkazish + ornatishNarxi;

    // Bo'lib to'lash tanlansa — ustama qo'shiladi
    const b = (xaridTlv === 'bolib' && xaridBolibOy) ? bolibHisob(asos) : null;

    return { mahsulotlar, chegirma, yetkazish, muddat, ornatishNarxi, asos, bolib: b,
             jami: b ? b.umumiy : asos };
  }

  // Ustamasiz asosiy summa (bo'lib to'lash shartlarini tekshirish uchun)
  function xaridHisobAsos() {
    const ornatish = document.getElementById('xa-ornatish').checked;
    const chegirma = xaridPromo ? Math.min(xaridPromo.chegirma, cartTotalSum()) : 0;
    const oraliq = cartTotalSum() - chegirma;
    let yetkazish = 0;
    if (xaridYetk === 'kuryer') {
      const h = tumanMalumoti(xaridTuman);
      yetkazish = (XARID_NARX.bepul_chegara && oraliq >= XARID_NARX.bepul_chegara)
        ? 0 : (h ? h.narx : XARID_NARX.yetkazish);
    }
    return oraliq + yetkazish + (ornatish ? XARID_NARX.ornatish : 0);
  }

  function xaridXulosa() {
    if (!document.getElementById('xa-xulosa')) return;
    const h = xaridHisob();
    const vaqt = xaridYetk === 'kuryer' ? xaridVaqtMatni() : '';
    const qatorlar = cart.map(c =>
      `<div class="xarid-qator"><span>${c.nom} × ${c.qty}</span><span>${c.narx ? somFmt(c.narx * c.qty) : '—'}</span></div>`
    ).join('');

    // Bepul yetkazishgacha qancha qolganini ko'rsatamiz
    const qolgan = XARID_NARX.bepul_chegara - (h.mahsulotlar - h.chegirma);
    const bepulEslatma = (xaridYetk === 'kuryer' && h.yetkazish > 0 && qolgan > 0)
      ? `<p class="text-xs mt-2" style="color:#5b7fa6"><i class="fas fa-circle-info mr-1"></i>
         Yana ${somFmt(qolgan)} xarid qilsangiz yetkazish bepul bo'ladi</p>` : '';

    document.getElementById('xa-xulosa').innerHTML = qatorlar +
      `<div class="xarid-qator" style="border-top:1px solid rgba(120,170,235,0.18);margin-top:8px;padding-top:8px">
         <span>Mahsulotlar</span><span>${somFmt(h.mahsulotlar)}</span></div>` +
      (h.chegirma ? `<div class="xarid-qator"><span>Chegirma (${xaridPromo.kod})</span>
         <span style="color:#15803d">−${somFmt(h.chegirma)}</span></div>` : '') +
      `<div class="xarid-qator"><span>Yetkazib berish</span><span>${
         xaridYetk === 'filialdan' ? 'Filialdan — bepul'
         : (h.yetkazish ? somFmt(h.yetkazish) : '<span style="color:#15803d">Bepul</span>')
       }</span></div>` +
      (h.muddat ? `<div class="xarid-qator"><span>Yetkazish muddati</span>
         <span style="color:#15803d">${h.muddat}</span></div>` : '') +
      (h.ornatishNarxi ? `<div class="xarid-qator"><span>O'rnatish xizmati</span><span>${somFmt(h.ornatishNarxi)}</span></div>` : '') +
      (h.bolib ? `<div class="xarid-qator"><span>Bo'lib to'lash ustamasi (+${h.bolib.ustama}%)</span>
         <span>${somFmt(h.bolib.umumiy - h.asos)}</span></div>` : '') +
      `<div class="xarid-jami"><span>Jami</span><span>${somFmt(h.jami)}</span></div>` +
      (h.bolib ? `<div class="xarid-qator"><span>Oylik to'lov</span>
         <span style="color:#0d6efd;font-weight:700">${somFmt(h.bolib.oylik)} × ${h.bolib.oy} oy</span></div>` : '') +
      (vaqt ? `<div class="xarid-qator mt-2"><span>Yetkazish vaqti</span><span>${vaqt}</span></div>` : '') +
      bepulEslatma;

    // Mobil qisqa ko'rinish
    document.getElementById('xa-qisqa-qty').textContent = cartTotalQty();
    document.getElementById('xa-qisqa-jami').textContent = somFmt(h.jami);
  }

  // ─── 4-bosqich: yakuniy tasdiqlash uchun to'liq ma'lumot ───
  function xaridTasdiqChiz() {
    const ism    = document.getElementById('xa-ism').value.trim();
    const tel    = document.getElementById('xa-tel').value.trim();
    const manzil = document.getElementById('xa-manzil').value.trim();
    const izoh   = document.getElementById('xa-izoh').value.trim();
    const vaqt   = xaridVaqtMatni();
    const h = xaridHisob();
    let tlvNomi = TOLOV_NOMI[xaridTlv] || xaridTlv;
    if (h.bolib) tlvNomi += ` — oyiga ${somFmt(h.bolib.oylik)} × ${h.bolib.oy} oy`;
    const ornatish = document.getElementById('xa-ornatish').checked;

    const qator = (belgi, nom, qiymat, qadam) => `
      <div class="flex items-start gap-3 py-2.5" style="border-bottom:1px solid rgba(120,170,235,0.12)">
        <i class="fas ${belgi} mt-1" style="color:#3d7ab5;width:16px"></i>
        <div class="flex-1 min-w-0">
          <div class="text-[11px] uppercase tracking-wider" style="color:#5b7fa6">${nom}</div>
          <div class="text-sm text-ink-900">${qiymat}</div>
        </div>
        <button type="button" data-h-click="c:xaridBosqich" data-a-click="${SG_A([qadam, true])}" class="text-xs font-bold shrink-0"
          style="color:#0d6efd"><i class="fas fa-pen text-[10px] mr-1"></i>O'zgartirish</button>
      </div>`;

    document.getElementById('xa-tasdiq').innerHTML = `
      <div class="xarid-card">
        <div class="xarid-legend"><i class="fas fa-clipboard-check mr-2"></i>Buyurtmani tekshiring</div>
        ${qator('fa-user', 'Mijoz', `${ism} · ${tel}`, 1)}
        ${xaridYetk === 'kuryer'
          ? qator('fa-location-dot', 'Yetkazish manzili',
              `${xaridTuman ? xaridTuman + ', ' : ''}${manzil}` +
              (h.muddat ? `<div class="text-xs mt-0.5" style="color:#15803d">${h.muddat} yetkaziladi</div>` : ''), 1)
          : qator('fa-store', 'Yetkazib berish',
              `Filialdan olib ketaman${(XARID_NARX.filial || {}).manzil ? '<div class="text-xs mt-0.5" style="color:#5b7fa6">' + XARID_NARX.filial.manzil + '</div>' : ''}`, 2)}
        ${xaridYetk === 'kuryer' ? qator('fa-clock', 'Yetkazish vaqti',
            vaqt || '<span style="color:#5b7fa6">Operator bilan kelishiladi</span>', 2) : ''}
        ${izoh ? qator('fa-comment-dots', 'Izoh', izoh, 2) : ''}
        ${qator('fa-credit-card', "To'lov usuli", tlvNomi, 3)}
        ${ornatish ? qator('fa-screwdriver-wrench', "Qo'shimcha", "O'rnatish xizmati", 3) : ''}
        ${xaridPromo ? qator('fa-ticket', 'Promokod', `${xaridPromo.kod} — ${somFmt(xaridPromo.chegirma)} chegirma`, 3) : ''}
      </div>

      <div class="xarid-card">
        <div class="xarid-legend"><i class="fas fa-box mr-2"></i>Mahsulotlar (${cartTotalQty()} ta)</div>
        ${cart.map(c => `
          <div class="flex items-center gap-3 py-2">
            <div class="w-9 h-9 rounded-lg flex items-center justify-center shrink-0"
              style="background:${c.rang}14;border:1px solid ${c.rang}44">
              <i class="fas ${c.ikona || 'fa-box'} text-sm" style="color:${c.rang}"></i>
            </div>
            <div class="flex-1 min-w-0"><div class="text-sm text-ink-900">${c.nom}</div>
              <div class="text-xs" style="color:#5b7fa6">${c.qty} dona</div></div>
            <div class="text-sm shrink-0">${c.narx ? somFmt(c.narx * c.qty) : '—'}</div>
          </div>`).join('')}
      </div>`;
  }

  // ---- Promokod ----
  async function promoQollash() {
    const inp  = document.getElementById('xa-promo');
    const info = document.getElementById('xa-promo-info');
    const btn  = document.getElementById('xa-promo-btn');
    const kod  = inp.value.trim().toUpperCase();

    // Bo'sh maydon — amaldagi promokodni bekor qilish
    if (!kod) {
      xaridPromo = null;
      info.classList.add('hidden');
      btn.textContent = "Qo'llash";
      xaridXulosa();
      return;
    }
    if (!cart.length) { promoInfo(info, false, "Savat bo'sh"); return; }

    btn.disabled = true;
    const eski = btn.textContent;
    btn.textContent = '...';
    try {
      const r = await apiPost('/xaridlar/promokod/', {
        kod,
        items: cart.map(c => ({ price: c.narx || 0, qty: c.qty })),
        delivery: xaridYetk,
        installService: document.getElementById('xa-ornatish').checked,
      });
      xaridPromo = { kod: r.kod, tavsif: r.tavsif, chegirma: r.chegirma };
      inp.value = r.kod;
      promoInfo(info, true, `${r.tavsif || 'Promokod qo\'llandi'} — ${somFmt(r.chegirma)} chegirma`);
      btn.textContent = 'Bekor qilish';
      showToast('Promokod qo\'llandi: −' + somFmt(r.chegirma));
    } catch (err) {
      xaridPromo = null;
      btn.textContent = eski;
      promoInfo(info, false, (err && err.data && err.data.detail) || 'Promokodni tekshirib bo\'lmadi');
    } finally {
      btn.disabled = false;
      xaridXulosa();
    }
  }

  function promoInfo(el, yaxshi, matn) {
    el.textContent = matn;
    el.style.color = yaxshi ? '#4ade80' : '#ff6b6b';
    el.classList.remove('hidden');
  }

  function xaridXato(matn) {
    const el = document.getElementById('xa-xato');
    if (!matn) { el.classList.add('hidden'); return; }
    el.textContent = matn;
    el.classList.remove('hidden');
  }

  async function xaridYuborish() {
    const ism    = document.getElementById('xa-ism').value.trim();
    const tel    = document.getElementById('xa-tel').value.trim();
    const manzil = document.getElementById('xa-manzil').value.trim();
    const izoh   = document.getElementById('xa-izoh').value.trim();
    const ornatish = document.getElementById('xa-ornatish').checked;

    // Barcha bosqichlarni yakuniy tekshirish
    for (let q = 1; q < XARID_QADAM_SONI; q++) {
      const xato = xaridQadamTekshir(q);
      if (xato) { xaridBosqich(q, true); xaridXato(xato); return; }
    }
    if (!cart.length) { xaridXato('Savat bo\'sh'); return; }
    xaridXato('');

    const tugma = document.getElementById('xa-oldinga');
    const eskiHtml = tugma.innerHTML;
    tugma.disabled = true;
    tugma.innerHTML = '<i class="fas fa-spinner fa-spin"></i>Yuborilmoqda...';

    try {
      const buyurtma = await apiPost('/xaridlar/', {
        customer: { name: ism, phone: tel, address: xaridYetk === 'kuryer' ? manzil : '' },
        delivery: {
          method: xaridYetk,
          note: izoh,
          time: xaridYetk === 'kuryer' ? xaridVaqtMatni() : '',
          region: xaridYetk === 'kuryer' ? xaridTuman : '',
        },
        payment:  { method: xaridTlv, months: xaridTlv === 'bolib' ? xaridBolibOy : 0 },
        installService: ornatish,
        promo: xaridPromo ? xaridPromo.kod : '',
        // Narx YUBORILMAYDI: server uni o'z bazasidan (KatalogNarx) kalit bo'yicha oladi
        items: cart.map(c => ({
          kalit: katKalitTop(c.nom),
          name: c.nom,
          qty: c.qty,
          image: c.ikona || '',
        })),
      });

      try { sessionStorage.setItem('sg_tel_' + buyurtma.id, String(tel).replace(/\D/g, '').slice(-4)); } catch (e) {}

      // Manzilni keyingi xaridlar uchun saqlab qo'yamiz
      if (xaridYetk === 'kuryer' && manzil && document.getElementById('xa-manzil-saqla').checked) {
        manzilSaqla({ ism, telefon: tel, manzil, tuman: xaridTuman });
      }

      clearCart();
      closeCartPage();
      xaridNatijaKorsat(buyurtma);

      // Onlayn to'lov: avtomatik yo'naltirmaymiz — natija ekranidagi tugma orqali
      // o'tiladi, shunda to'lov amalga oshmasa mijoz shu yerda qayta urina oladi.
    } catch (e) {
      // Backend aniq sabab qaytarsa (masalan promokod muddati tugagan) — shuni ko'rsatamiz
      const sabab = e && e.data && e.data.detail;
      xaridXato(sabab || 'Buyurtmani yuborishda xatolik. Internetni tekshirib, qayta urinib ko\'ring.');
      if (e && e.data && e.data.maydon === 'promo') {
        xaridPromo = null;
        document.getElementById('xa-promo-btn').textContent = "Qo'llash";
        xaridXulosa();
      }
    } finally {
      tugma.disabled = false;
      tugma.innerHTML = eskiHtml;
    }
  }

  // Buyurtma holati bosqichlari (backend HOLAT kodlari bilan bir xil)
  const XARID_OQIM = [
    ['qabul_qilindi',  'Qabul qilindi',  'fa-inbox'],
    ['tasdiqlandi',    'Tasdiqlandi',    'fa-circle-check'],
    ['tayyorlanmoqda', 'Tayyorlanmoqda', 'fa-box-open'],
    ['jonatildi',      "Jo'natildi",     'fa-warehouse'],
    ['yolda',          "Yo'lda",         'fa-truck-fast'],
    ['yetkazildi',     'Yetkazildi',     'fa-house-circle-check'],
  ];

  function xaridBosqichlar(holat) {
    if (holat === 'bekor') {
      return '<div class="xarid-step bajarildi"><i class="fas fa-xmark" style="background:#7f1d1d;color:#1c3d63"></i><span>Bekor qilindi</span></div>';
    }
    if (holat === 'muammo') {
      // Yetkazib bo'lmadi — "Yo'lda" gacha bosqichlar o'tilgan hisoblanadi
      return XARID_OQIM.slice(0, 5).map(([kod, nom], i) => `
        <div class="xarid-step bajarildi"><i class="fas fa-check"></i><span>${nom}</span></div>`).join('') +
        '<div class="xarid-step bajarildi joriy-bosqich"><i class="fas fa-triangle-exclamation" ' +
        'style="background:#7f1d1d;color:#1c3d63"></i><span>Yetkazib bo\'lmadi <b style="color:#dc2626">← hozir</b></span></div>';
    }
    const joriy = XARID_OQIM.findIndex(([kod]) => kod === holat);
    return XARID_OQIM.map(([kod, nom, ikona], i) => {
      const otgan = i < joriy, shu = i === joriy;
      return `
      <div class="xarid-step ${i <= joriy ? 'bajarildi' : ''} ${shu ? 'joriy-bosqich' : ''}">
        <i class="fas ${otgan ? 'fa-check' : ikona}"></i>
        <span>${nom}${shu ? ' <b style="color:#0d6efd">← hozir</b>' : ''}</span>
      </div>`;
    }).join('');
  }

  // Buyurtma summasi tafsiloti (backend `totals` obyektidan)
  function xaridSummaTafsil(b) {
    const t = b.totals;
    if (!t) return `<div class="xarid-jami"><span>Jami</span><span>${somFmt(b.total)}</span></div>`;
    return `
      <div class="xarid-qator" style="border-top:1px solid rgba(120,170,235,0.18);margin-top:8px;padding-top:8px">
        <span>Mahsulotlar</span><span>${somFmt(t.items)}</span></div>
      ${t.discount ? `<div class="xarid-qator"><span>Chegirma${t.promo ? ' (' + t.promo + ')' : ''}</span>
        <span style="color:#15803d">−${somFmt(t.discount)}</span></div>` : ''}
      <div class="xarid-qator"><span>Yetkazib berish</span><span>${
        t.delivery ? somFmt(t.delivery) : '<span style="color:#15803d">Bepul</span>'}</span></div>
      ${t.install ? `<div class="xarid-qator"><span>O'rnatish xizmati</span><span>${somFmt(t.install)}</span></div>` : ''}
      <div class="xarid-jami"><span>Jami</span><span>${somFmt(t.grand)}</span></div>`;
  }

  // ═════════════════════════════════════════════════════════════
  //  JONLI KUZATUV — holat, bildirishnoma va kuryer xaritasi
  // ═════════════════════════════════════════════════════════════
  let xaridKuzatTimer = null;
  let xaridOxirgiHolat = '';
  let xaridXarita = null, kuryerNishon = null, manzilNishon = null;

  const XARID_HOLAT_NOMI = Object.fromEntries(XARID_OQIM.map(([k, n]) => [k, n]));
  XARID_HOLAT_NOMI.bekor = 'Bekor qilindi';

  // ---- Brauzer bildirishnomasi ----
  function bildirishnomaSora() {
    if (!('Notification' in window)) return;
    if (Notification.permission === 'default') Notification.requestPermission();
  }

  function bildirishnoma(sarlavha, matn) {
    // Sahifa ochiq bo'lsa toast, fon rejimida bo'lsa tizim bildirishnomasi
    showToast(matn);
    if (!('Notification' in window) || Notification.permission !== 'granted') return;
    try {
      new Notification(sarlavha, { body: matn, icon: '/logo_icon.png?v=2', tag: 'soargaz-xarid' });
    } catch (e) { /* ba'zi brauzerlarda faqat service worker orqali ishlaydi */ }
  }

  // ---- Holatni davriy tekshirish ----
  function xaridKuzatBoshla(raqam, holat) {
    xaridKuzatToxtat();
    xaridJoriyRaqam = raqam;
    xaridOxirgiHolat = holat;
    bildirishnomaSora();
    // Yakunlangan buyurtmani kuzatishning hojati yo'q
    if (holat === 'yetkazildi' || holat === 'bekor') return;
    xaridKuzatTimer = setInterval(xaridHolatTekshir, 15000);
  }

  function xaridKuzatToxtat() {
    if (xaridKuzatTimer) { clearInterval(xaridKuzatTimer); xaridKuzatTimer = null; }
  }

  async function xaridHolatTekshir() {
    if (!xaridJoriyRaqam) return;
    let b;
    try {
      b = await apiGetXarid('/xaridlar/' + xaridJoriyRaqam + '/');
    } catch (e) {
      return;   // aloqa uzilgan bo'lsa keyingi tsiklda qayta urinamiz
    }

    // Holat o'zgargan bo'lsa — bosqichlarni yangilab, mijozni ogohlantiramiz
    if (b.status !== xaridOxirgiHolat) {
      xaridOxirgiHolat = b.status;
      const el = document.getElementById('xa-bosqichlar');
      if (el) el.innerHTML = xaridBosqichlar(b.status);
      bildirishnoma(
        'SOAR GAZ — ' + b.id,
        'Buyurtma holati yangilandi: ' + (XARID_HOLAT_NOMI[b.status] || b.status)
      );
      if (b.status === 'yetkazildi' || b.status === 'bekor') {
        xaridKuzatToxtat();
        const j = document.getElementById('xa-jonli');
        if (j) j.classList.add('hidden');
      }
    }

    // To'lov holati ham o'zgargan bo'lishi mumkin
    const panel = document.getElementById('xa-tolov-panel');
    if (panel) panel.innerHTML = tolovPanel(b);

    const mp = document.getElementById('xa-muammo-card');
    if (mp) mp.innerHTML = muammoPanel(b);

    kuryerYangila(b);
  }

  // ---- Kuryer xaritasi (Leaflet + OpenStreetMap) ----

  // Leaflet talab bo'yicha yuklanadi: 159 KB (js+css) faqat xaridga kuryer
  // biriktirilganda kerak, shuning uchun uni <head> da emas, shu yerda
  // ulaymiz. Bir marta yuklanadi — takroriy chaqiruvlar o'sha va'daga ulanadi.
  let leafletVada = null;

  function leafletYukla() {
    if (typeof L !== 'undefined') return Promise.resolve();
    if (leafletVada) return leafletVada;

    leafletVada = new Promise((bajar, rad) => {
      const uslub = document.createElement('link');
      uslub.rel = 'stylesheet';
      uslub.href = '/vendor/leaflet/leaflet.css';
      document.head.appendChild(uslub);

      const skript = document.createElement('script');
      skript.src = '/vendor/leaflet/leaflet.js';
      skript.onload = () => bajar();
      skript.onerror = () => { leafletVada = null; rad(new Error('leaflet')); };
      document.head.appendChild(skript);
    });
    return leafletVada;
  }

  function kuryerYangila(b) {
    const kartochka = document.getElementById('xa-kuryer-card');
    const k = b.delivery && b.delivery.courier;
    if (!kartochka) return;

    if (!k) { kartochka.classList.add('hidden'); return; }
    kartochka.classList.remove('hidden');

    if (typeof L === 'undefined') {   // Leaflet hali yuklanmagan — endi yuklaymiz
      const info = document.getElementById('xa-kuryer-info');
      if (info) info.textContent = 'Xarita yuklanmoqda...';
      leafletYukla()
        .then(() => kuryerYangila(b))
        .catch(() => {
          if (info) info.textContent = 'Xaritani yuklab bo\'lmadi';
        });
      return;
    }

    const nuqta = [k.lat, k.lng];
    if (!xaridXarita) {
      xaridXarita = L.map('xa-xarita', { zoomControl: true, attributionControl: true }).setView(nuqta, 14);
      L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        maxZoom: 19,
        attribution: '© OpenStreetMap',
      }).addTo(xaridXarita);
    }

    const kuryerIkona = L.divIcon({
      html: '<div class="kuryer-nishon"><i class="fas fa-truck-fast"></i></div>',
      className: '', iconSize: [34, 34], iconAnchor: [17, 17],
    });
    if (!kuryerNishon) {
      kuryerNishon = L.marker(nuqta, { icon: kuryerIkona }).addTo(xaridXarita);
      kuryerNishon.bindPopup('Kuryer' + (k.name ? ': ' + k.name : ''));
    } else {
      kuryerNishon.setLatLng(nuqta);
    }

    // Yetkazish manzili ma'lum bo'lsa — ikkinchi nishon va ikkalasini sig'dirish
    const m = b.delivery.destination;
    if (m && !manzilNishon) {
      manzilNishon = L.marker([m.lat, m.lng], {
        icon: L.divIcon({
          html: '<div class="manzil-nishon"><i class="fas fa-house"></i></div>',
          className: '', iconSize: [30, 30], iconAnchor: [15, 15],
        }),
      }).addTo(xaridXarita).bindPopup('Yetkazish manzili');
    }
    if (manzilNishon) {
      xaridXarita.fitBounds(L.latLngBounds([nuqta, manzilNishon.getLatLng()]).pad(0.35));
    } else {
      xaridXarita.setView(nuqta, xaridXarita.getZoom());
    }
    // Konteyner yashirin holatda chizilgan bo'lsa o'lchamini qayta hisoblaymiz
    setTimeout(() => xaridXarita.invalidateSize(), 60);

    const vaqt = k.updated ? new Date(k.updated) : null;
    document.getElementById('xa-kuryer-info').innerHTML =
      `<i class="fas fa-circle-info mr-1"></i>` +
      (k.name ? `Kuryer: <b style="color:#0d6efd">${k.name}</b>` : 'Kuryer yo\'lda') +
      (k.phone ? ` · <a href="tel:${k.phone}" style="color:#0d6efd">${k.phone}</a>` : '') +
      (vaqt ? ` · joylashuv ${vaqt.toLocaleTimeString('uz-UZ', { hour: '2-digit', minute: '2-digit' })} da yangilandi` : '');
  }

  // ─────────────────────────────────────────────────────────────
  //  Yetkazib bo'lmadi — mijozga sabab va qayta yetkazish so'rovi
  // ─────────────────────────────────────────────────────────────
  function muammoPanel(b) {
    const p = b.delivery && b.delivery.problem;
    if (!p || b.status !== 'muammo') return '';

    const limit = XARID_NARX.urinishlar || 3;
    const tugadi = p.attempts >= limit;
    const vaqt = p.at ? new Date(p.at).toLocaleString('uz-UZ', {
      day: 'numeric', month: 'long', hour: '2-digit', minute: '2-digit' }) : '';

    return `<div class="xarid-card" style="border-color:rgba(255,107,107,0.45)">
      <div class="flex items-start gap-3 mb-3">
        <i class="fas fa-triangle-exclamation mt-1" style="color:#dc2626"></i>
        <div class="flex-1">
          <div class="font-bold text-ink-900 text-sm">Buyurtmani yetkazib bo'lmadi</div>
          <div class="text-xs mt-1" style="color:#5b7fa6">
            Sabab: <b style="color:#0d6efd">${p.label}</b>
            ${p.note ? ` — ${p.note}` : ''}
            ${vaqt ? `<div class="mt-0.5">${vaqt}</div>` : ''}
            <div class="mt-0.5">${p.attempts} / ${limit} urinish</div>
          </div>
        </div>
      </div>
      ${tugadi ? `
        <p class="text-xs mb-3" style="color:#dc2626">
          <i class="fas fa-circle-info mr-1"></i>
          ${limit} marta urinib ko'rildi. Davom ettirish uchun operator bilan bog'laning.
        </p>
        <a href="tel:+998918341104" class="block text-center w-full font-black rounded-xl"
          style="padding:13px;background:linear-gradient(135deg,#ff8a00,#ff8a00);color:#0a0900">
          <i class="fas fa-phone mr-2"></i>Operatorga qo'ng'iroq
        </a>`
      : `
        <p class="text-xs mb-3" style="color:#5b7fa6">
          Qulay vaqtni tanlab yoki manzilni aniqlashtirib, qayta yetkazishni so'rang.
        </p>
        <input id="xa-qayta-vaqt" class="xarid-input mb-2" placeholder="Qulay vaqt (masalan: Ertaga, 15:00–18:00)">
        <input id="xa-qayta-manzil" class="xarid-input mb-3" placeholder="Manzilni aniqlashtirish (ixtiyoriy)">
        <button data-h-click="h191" class="w-full font-black rounded-xl active:scale-95 transition-all"
          style="padding:14px;background:linear-gradient(135deg,#ff8a00,#ff8a00,#ff8a00);color:#0a0900">
          <i class="fas fa-rotate-right mr-2"></i>Qayta yetkazishni so'rash
        </button>`}
    </div>`;
  }

  async function qaytaYetkazishSora() {
    const vaqt   = (document.getElementById('xa-qayta-vaqt') || {}).value || '';
    const manzil = (document.getElementById('xa-qayta-manzil') || {}).value || '';
    try {
      const b = await apiPostXaridTasdiq('/xaridlar/' + xaridJoriyRaqam + '/qayta/',
                              { time: vaqt.trim(), address: manzil.trim() });
      xaridOxirgiHolat = b.status;
      document.getElementById('xa-bosqichlar').innerHTML = xaridBosqichlar(b.status);
      document.getElementById('xa-muammo-card').innerHTML = muammoPanel(b);
      showToast("Qayta yetkazish so'rovi qabul qilindi");
    } catch (e) {
      showToast((e && e.data && e.data.detail) || "So'rovni yuborib bo'lmadi");
    }
  }

  // ─────────────────────────────────────────────────────────────
  //  KURYER TOMONI — joylashuvni ulashish
  //  Ochish:  sayt.uz/#kuryer=SG-2607-0001   (xodim yoki admin login bilan)
  // ─────────────────────────────────────────────────────────────
  let kuryerWatchId = null;

  let kuryerJoriyRaqam = '';

  function kuryerRejimTekshir() {
    // #kuryer  — ish ro'yxati;  #kuryer=SG-...  — to'g'ridan-to'g'ri buyurtma
    if (!/#kuryer/.test(location.hash)) return;
    const m = location.hash.match(/kuryer=([A-Za-z0-9-]+)/);
    kuryerPanelKorsat();
    if (m) kuryerBuyurtmaOch(m[1].toUpperCase()); else kuryerRoyxatYukla();
  }

  function kuryerPanelKorsat() {
    if (document.getElementById('kuryer-panel')) return;
    const panel = document.createElement('div');
    panel.id = 'kuryer-panel';
    panel.className = 'fixed inset-0 overflow-y-auto';
    panel.style.cssText = 'background:#ffffff;z-index:9600';
    panel.innerHTML = `
      <div class="sticky top-0 backdrop-blur-xl border-b" style="background:rgba(255,255,255,0.97);border-color:rgba(120,170,235,0.25)">
        <div class="max-w-lg mx-auto px-4 h-16 flex items-center justify-between">
          <div class="flex items-center gap-3">
            <div class="w-9 h-9 rounded-xl flex items-center justify-center" style="background:linear-gradient(135deg,#ff8a00,#ff8a00)">
              <i class="fas fa-truck-fast text-black text-sm"></i>
            </div>
            <div><span class="font-black text-ink-900">Kuryer rejimi</span>
              <div class="text-[10px] uppercase tracking-widest" style="color:#5b7fa6">SOAR GAZ</div></div>
          </div>
          <button data-h-click="h192" class="w-9 h-9 rounded-xl text-gray-400 hover:text-ink-900"
            style="background:#eef5fe;border:1px solid rgba(120,170,235,0.2)"><i class="fas fa-times"></i></button>
        </div>
      </div>
      <div class="max-w-lg mx-auto px-4 py-5">
        <div class="grid grid-cols-2 gap-2 mb-4">
          <button id="kt-mening" data-h-click="h193" class="xa-chip tanlangan">Mening ishlarim</button>
          <button id="kt-bosh"   data-h-click="h194" class="xa-chip">Bo'sh buyurtmalar</button>
        </div>
        <div id="kuryer-royxat"></div>
      </div>`;
    document.body.appendChild(panel);
    document.body.style.overflow = 'hidden';
  }

  async function kuryerRoyxatYukla(bosh) {
    kuryerJoriyRaqam = '';
    document.getElementById('kt-mening').classList.toggle('tanlangan', !bosh);
    document.getElementById('kt-bosh').classList.toggle('tanlangan', !!bosh);
    const box = document.getElementById('kuryer-royxat');
    box.innerHTML = '<p class="text-center py-8" style="color:#5b7fa6"><i class="fas fa-spinner fa-spin"></i></p>';

    if (!apiToken()) {
      box.innerHTML = `<div class="xarid-card text-center">
        <i class="fas fa-lock text-2xl mb-2" style="color:#3d7ab5"></i>
        <p class="text-sm" style="color:#5b7fa6">Xodim sifatida tizimga kiring.</p></div>`;
      return;
    }
    try {
      const list = await apiGet('/xaridlar/kuryer/' + (bosh ? '?bosh=1' : ''));
      if (!list.length) {
        box.innerHTML = `<p class="text-center py-10" style="color:#5b7fa6">
          ${bosh ? "Hozircha bo'sh buyurtma yo'q" : 'Sizga biriktirilgan buyurtma yo\'q'}</p>`;
        return;
      }
      box.innerHTML = list.map(b => `
        <div class="xarid-card" data-h-click="c:kuryerBuyurtmaOch" data-a-click="${SG_A([String(b.id)])}" style="cursor:pointer">
          <div class="flex items-start justify-between gap-3">
            <div class="flex-1 min-w-0">
              <div class="font-mono font-black" style="color:#0d6efd">${b.id}</div>
              <div class="text-sm text-ink-900 mt-1">${b.customer.name}</div>
              <div class="text-xs mt-0.5" style="color:#5b7fa6">
                ${b.delivery.region ? b.delivery.region + ' · ' : ''}${b.customer.address || ''}</div>
              ${b.delivery.time ? `<div class="text-xs mt-0.5" style="color:#0d6efd">
                <i class="fas fa-clock mr-1"></i>${b.delivery.time}</div>` : ''}
            </div>
            <div class="text-right shrink-0">
              <div class="font-black text-sm">${somFmt(b.total)}</div>
              <div class="text-[10px] mt-1 px-2 py-0.5 rounded-full inline-block"
                style="background:rgba(120,170,235,0.12);color:#0d6efd">
                ${XARID_HOLAT_NOMI[b.status] || b.status}</div>
              ${b.payment.method === 'naqd' && !b.payment.paid
                ? '<div class="text-[10px] mt-1" style="color:#0d6efd">Naqd olinadi</div>' : ''}
            </div>
          </div>
        </div>`).join('');
    } catch (e) {
      box.innerHTML = `<p class="text-center py-10" style="color:#dc2626">
        ${(e && e.data && e.data.detail) || "Ro'yxatni yuklab bo'lmadi"}</p>`;
    }
  }

  async function kuryerBuyurtmaOch(raqam) {
    kuryerJoriyRaqam = raqam;
    const box = document.getElementById('kuryer-royxat');
    box.innerHTML = '<p class="text-center py-8" style="color:#5b7fa6"><i class="fas fa-spinner fa-spin"></i></p>';
    let b;
    try { b = await apiGetXarid('/xaridlar/' + raqam + '/'); }
    catch (e) { box.innerHTML = '<p class="text-center py-10" style="color:#dc2626">Buyurtma topilmadi</p>'; return; }

    const biriktirilgan = !!(b.delivery.courier || b.status === 'yolda' || b.status === 'jonatildi');
    box.innerHTML = `
      <button data-h-click="h193" class="btn-ortga text-sm font-bold mb-3" style="color:#0d6efd">
        <i class="fas fa-arrow-left mr-1"></i>Ro'yxatga qaytish</button>

      <div class="xarid-card">
        <div class="font-mono font-black text-lg" style="color:#0d6efd">${b.id}</div>
        <div class="xarid-qator mt-2"><span>Mijoz</span><span>${b.customer.name}</span></div>
        <div class="xarid-qator"><span>Telefon</span>
          <span><a href="tel:${b.customer.phone}" style="color:#0d6efd">${b.customer.phone}</a></span></div>
        ${b.delivery.region ? `<div class="xarid-qator"><span>Hudud</span><span>${b.delivery.region}</span></div>` : ''}
        ${b.customer.address ? `<div class="xarid-qator"><span>Manzil</span><span>${b.customer.address}</span></div>` : ''}
        ${b.delivery.time ? `<div class="xarid-qator"><span>Vaqt</span><span>${b.delivery.time}</span></div>` : ''}
        ${b.delivery.note ? `<div class="xarid-qator"><span>Izoh</span><span style="color:#0d6efd">${b.delivery.note}</span></div>` : ''}
        <div class="xarid-jami"><span>${b.payment.method === 'naqd' && !b.payment.paid ? "Naqd olinadi" : TOLOV_NOMI[b.payment.method]}</span>
          <span>${somFmt(b.total)}</span></div>
      </div>

      <div class="xarid-card">
        <div class="xarid-legend"><i class="fas fa-list-check mr-2"></i>Mahsulotlar</div>
        ${b.items.map(it => `<div class="xarid-qator"><span>${it.name} × ${it.qty}</span>
          <span>${it.price ? somFmt(it.price * it.qty) : '—'}</span></div>`).join('')}
      </div>

      <div class="xarid-card">
        <div class="xarid-legend"><i class="fas fa-bolt mr-2"></i>Amallar</div>
        ${!biriktirilgan ? `
          <button data-h-click="h195" class="w-full font-black rounded-xl mb-2"
            style="padding:14px;background:linear-gradient(135deg,#ff8a00,#ff8a00,#ff8a00);color:#0a0900">
            <i class="fas fa-hand mr-2"></i>Buyurtmani qabul qilish
          </button>` : ''}
        <button id="kuryer-tugma" data-h-click="c:kuryerUlash" data-a-click="${SG_A([String(b.id)])}" class="w-full font-bold rounded-xl mb-2"
          style="padding:13px;background:rgba(120,170,235,0.1);color:#0d6efd;border:1px solid rgba(120,170,235,0.4)">
          <i class="fas fa-location-crosshairs mr-2"></i>Joylashuvni ulashishni boshlash
        </button>
        <p id="kuryer-holat" class="text-xs mb-3 text-center" style="color:#5b7fa6"></p>

        <div class="grid grid-cols-2 gap-2">
          <button data-h-click="h196" class="xa-chip">Yo'lga chiqdim</button>
          <button data-h-click="h197" class="xa-chip"
            style="border-color:rgba(74,222,128,0.4);color:#15803d">Yetkazdim ✓</button>
        </div>
        <button data-h-click="h198" class="w-full font-bold rounded-xl mt-2"
          style="padding:12px;background:rgba(255,107,107,0.1);color:#dc2626;border:1px solid rgba(255,107,107,0.35)">
          <i class="fas fa-triangle-exclamation mr-2"></i>Yetkazib bo'lmadi
        </button>
        <div id="kuryer-muammo" class="hidden mt-3"></div>
      </div>`;
  }

  async function kuryerAmal(amal) {
    try {
      if (amal === 'qabul') {
        await apiPostA('/xaridlar/' + kuryerJoriyRaqam + '/qabul/', {});
        showToast('Buyurtma sizga biriktirildi');
      } else {
        await apiPostA('/xaridlar/' + kuryerJoriyRaqam + '/holat/', { holat: amal });
        showToast('Holat yangilandi: ' + (XARID_HOLAT_NOMI[amal] || amal));
      }
      kuryerBuyurtmaOch(kuryerJoriyRaqam);
    } catch (e) {
      showToast((e && e.data && e.data.detail) || 'Amalni bajarib bo\'lmadi');
    }
  }

  const KURYER_MUAMMOLARI = [
    ['javob_bermadi',    'Mijoz javob bermadi'],
    ['manzil_topilmadi', 'Manzil topilmadi'],
    ['rad_etdi',         'Qabul qilishdan bosh tortdi'],
    ['vaqt_mos_emas',    'Vaqt mos kelmadi'],
    ['boshqa',           'Boshqa sabab'],
  ];

  function kuryerMuammoOch() {
    const box = document.getElementById('kuryer-muammo');
    if (!box.classList.contains('hidden')) { box.classList.add('hidden'); return; }
    box.innerHTML = `
      <label class="xarid-label">Sababni tanlang</label>
      <div class="space-y-2 mb-2">
        ${KURYER_MUAMMOLARI.map(([kod, nom]) => `
          <button type="button" class="w-full text-left rounded-xl text-sm" data-muammo="${kod}"
            data-h-click="c:kuryerMuammoTanla" data-a-click="${SG_A([String(kod)])}"
            style="padding:11px;background:#f1f7ff;color:#1c3d63;border:1px solid rgba(120,170,235,0.22)">
            <i class="fas fa-angle-right mr-2" style="color:#3d7ab5"></i>${nom}</button>`).join('')}
      </div>
      <textarea id="kuryer-izoh" rows="2" class="xarid-input mb-2" style="resize:none"
        placeholder="Qo'shimcha izoh (ixtiyoriy)"></textarea>
      <button data-h-click="h199" class="w-full font-black rounded-xl"
        style="padding:13px;background:linear-gradient(135deg,#7f1d1d,#dc2626);color:#1c3d63">
        Xabar berish
      </button>`;
    box.classList.remove('hidden');
  }

  let kuryerMuammoKod = '';
  function kuryerMuammoTanla(kod) {
    kuryerMuammoKod = kod;
    document.querySelectorAll('[data-muammo]').forEach(el =>
      el.style.borderColor = el.dataset.muammo === kod ? '#ff8a00' : 'rgba(120,170,235,0.22)');
  }

  async function kuryerMuammoYubor() {
    if (!kuryerMuammoKod) { showToast('Sababni tanlang'); return; }
    try {
      const r = await apiPostA('/xaridlar/' + kuryerJoriyRaqam + '/muammo/', {
        sabab: kuryerMuammoKod,
        izoh: (document.getElementById('kuryer-izoh') || {}).value || '',
      });
      showToast(r.operator_kerak
        ? `${r.urinish_soni}/${r.limit} urinish — operator aralashuvi kerak`
        : `Xabar berildi (${r.urinish_soni}/${r.limit} urinish). Mijozga SMS ketdi.`);
      kuryerMuammoKod = '';
      kuryerBuyurtmaOch(kuryerJoriyRaqam);
    } catch (e) {
      showToast((e && e.data && e.data.detail) || 'Xabar yuborilmadi');
    }
  }

  function kuryerPanelYop() {
    kuryerToxtat();
    const p = document.getElementById('kuryer-panel');
    if (p) p.remove();
    document.body.style.overflow = '';
    history.replaceState(null, '', location.pathname);
  }

  function kuryerUlash(raqam) {
    if (kuryerWatchId !== null) { kuryerToxtat(); return; }
    if (!navigator.geolocation) {
      document.getElementById('kuryer-holat').textContent = 'Bu brauzer joylashuvni qo\'llab-quvvatlamaydi';
      return;
    }
    if (!apiToken()) {
      document.getElementById('kuryer-holat').innerHTML =
        '<span style="color:#dc2626">Avval xodim sifatida tizimga kiring</span>';
      return;
    }

    const holatEl = document.getElementById('kuryer-holat');
    const tugma = document.getElementById('kuryer-tugma');
    holatEl.textContent = 'Joylashuv so\'ralmoqda...';

    kuryerWatchId = navigator.geolocation.watchPosition(
      async (pos) => {
        try {
          await apiPostA('/xaridlar/' + raqam + '/kuryer/', {
            lat: pos.coords.latitude, lng: pos.coords.longitude,
          });
          holatEl.innerHTML = `<i class="fas fa-circle-check mr-1" style="color:#15803d"></i>
            Yuborildi: ${pos.coords.latitude.toFixed(5)}, ${pos.coords.longitude.toFixed(5)}
            (${new Date().toLocaleTimeString('uz-UZ')})`;
        } catch (e) {
          holatEl.innerHTML = '<span style="color:#dc2626">Yuborilmadi — ' +
            ((e && e.data && e.data.detail) || 'server xatosi') + '</span>';
        }
      },
      (err) => {
        holatEl.innerHTML = '<span style="color:#dc2626">Joylashuvga ruxsat berilmadi (' + err.code + ')</span>';
        kuryerToxtat();
      },
      { enableHighAccuracy: true, maximumAge: 10000, timeout: 20000 }
    );

    tugma.innerHTML = '<i class="fas fa-stop mr-2"></i>Ulashishni to\'xtatish';
  }

  function kuryerToxtat() {
    if (kuryerWatchId !== null) {
      navigator.geolocation.clearWatch(kuryerWatchId);
      kuryerWatchId = null;
    }
    const t = document.getElementById('kuryer-tugma');
    if (t) t.innerHTML = '<i class="fas fa-location-crosshairs mr-2"></i>Joylashuvni ulashishni boshlash';
  }

  // ─────────────────────────────────────────────────────────────
  //  To'lov paneli — to'lash, qayta urinish, boshqa usulga o'tish
  // ─────────────────────────────────────────────────────────────
  let xaridJoriyRaqam = '';

  function tolovPanel(b) {
    const p = b.payment || {};
    xaridJoriyRaqam = b.id;

    if (p.paid) {
      return `<div class="xarid-card" style="border-color:rgba(74,222,128,0.4)">
        <div class="flex items-center gap-3">
          <i class="fas fa-circle-check text-xl" style="color:#15803d"></i>
          <div><div class="font-bold text-ink-900">To'lov qabul qilindi</div>
            <div class="text-xs" style="color:#5b7fa6">${somFmt(b.total)} · ${TOLOV_NOMI[p.method] || p.method}</div></div>
        </div></div>`;
    }

    if (p.method === 'naqd') {
      return `<div class="xarid-card">
        <div class="flex items-start gap-3">
          <i class="fas fa-money-bill-wave mt-1" style="color:#0d6efd"></i>
          <div class="flex-1"><div class="font-bold text-ink-900 text-sm">Naqd to'lov — yetkazib berishda</div>
            <div class="text-xs mt-0.5" style="color:#5b7fa6">
              Kuryerga ${somFmt(b.total)} naqd topshirasiz. Oldindan to'lash shart emas.</div>
          </div>
        </div>
        ${tolovUsulTugmasi()}
      </div>`;
    }

    if (p.method === 'bolib') {
      return `<div class="xarid-card">
        <div class="flex items-start gap-3">
          <i class="fas fa-calendar-days mt-1" style="color:#0d6efd"></i>
          <div class="flex-1"><div class="font-bold text-ink-900 text-sm">Bo'lib to'lash so'rovi yuborildi</div>
            <div class="text-xs mt-0.5" style="color:#5b7fa6">
              Operator siz bilan bog'lanib, shartnomani rasmiylashtiradi.
              ${p.months ? `Oyiga ${somFmt(p.monthly)} × ${p.months} oy.` : ''}</div>
          </div>
        </div>
        ${tolovUsulTugmasi()}
      </div>`;
    }

    // Onlayn to'lov (click / payme / karta)
    const xato = p.state === 'xato';
    const sozlanmagan = p.configured === false;
    return `<div class="xarid-card" style="border-color:${xato ? 'rgba(255,107,107,0.45)' : 'rgba(120,170,235,0.28)'}">
      ${xato ? `<div class="flex items-start gap-3 mb-3">
        <i class="fas fa-circle-exclamation mt-1" style="color:#dc2626"></i>
        <div><div class="font-bold text-ink-900 text-sm">To'lov amalga oshmadi</div>
          <div class="text-xs mt-0.5" style="color:#5b7fa6">
            Buyurtmangiz saqlanib qoldi — qaytadan urinib ko'ring yoki boshqa usul tanlang.
            ${p.attempts > 1 ? `(${p.attempts} urinish)` : ''}</div></div>
      </div>` : ''}
      ${sozlanmagan ? `<p class="text-xs mb-3" style="color:#dc2626">
        <i class="fas fa-triangle-exclamation mr-1"></i>
        ${TOLOV_NOMI[p.method]} hali sozlanmagan — administrator merchant kalitlarini kiritishi kerak.</p>` : ''}
      <button data-h-click="h200" class="w-full font-black rounded-xl mb-2 active:scale-95 transition-all"
        style="padding:15px;background:linear-gradient(135deg,#ff8a00,#ff8a00,#ff8a00);color:#0a0900">
        <i class="fas fa-lock mr-2"></i>${xato ? "Qayta urinib ko'rish" : "To'lovni amalga oshirish"} — ${somFmt(b.total)}
      </button>
      <p class="text-[11px] text-center mb-3" style="color:#5b7fa6">
        <i class="fas fa-shield-halved mr-1"></i>${TOLOV_NOMI[p.method]} himoyalangan sahifasi · 3-D Secure
      </p>
      ${tolovUsulTugmasi()}
    </div>`;
  }

  function tolovUsulTugmasi() {
    return `<button data-h-click="h201" class="w-full font-bold rounded-xl text-sm transition-all active:scale-95"
      style="padding:11px;background:rgba(31,72,135,0.04);color:#0d6efd;border:1px solid rgba(120,170,235,0.28)">
      <i class="fas fa-arrows-rotate mr-1"></i>Boshqa to'lov usulini tanlash
    </button>
    <div id="xa-usul-royxat" class="hidden mt-3 space-y-2"></div>`;
  }

  // To'lov sahifasini yangi oynada ochamiz — buyurtma sahifasi ochiq qoladi,
  // shunda mijoz to'lov muvaffaqiyatsiz bo'lsa darhol qayta urina oladi
  async function tolovniOch() {
    try {
      const t = await apiGetPub('/xaridlar/' + xaridJoriyRaqam + '/tolov/');
      if (!t.url) { showToast("To'lov havolasi mavjud emas"); return; }
      window.open(t.url, '_blank', 'noopener');
      showToast("To'lov sahifasi ochildi. Yakunlagach, holatni yangilang.");
      tolovHolatKuzat();
    } catch (e) {
      showToast("To'lov havolasini olishda xatolik");
    }
  }

  // To'lovdan keyin holatni bir necha marta tekshiramiz (webhook kechikishi mumkin)
  function tolovHolatKuzat() {
    let urinish = 0;
    const timer = setInterval(async () => {
      urinish++;
      try {
        const b = await apiGetXarid('/xaridlar/' + xaridJoriyRaqam + '/');
        document.getElementById('xa-tolov-panel').innerHTML = tolovPanel(b);
        if (b.payment.paid || b.payment.state === 'xato') { clearInterval(timer); }
        if (b.payment.paid) showToast("To'lov qabul qilindi! ✓");
      } catch (e) { /* keyingi urinishda qayta tekshiramiz */ }
      if (urinish >= 20) clearInterval(timer);   // ~2 daqiqa
    }, 6000);
  }

  async function tolovUsulOch() {
    const box = document.getElementById('xa-usul-royxat');
    if (!box.classList.contains('hidden')) { box.classList.add('hidden'); return; }

    const t = await apiGetPub('/xaridlar/' + xaridJoriyRaqam + '/tolov/').catch(() => null);
    const joriy = t ? t.method : '';
    const bolibBor = (XARID_NARX.bolib || []).length &&
                     (!XARID_NARX.bolib_eng_kam || (t && t.amount >= XARID_NARX.bolib_eng_kam));

    box.innerHTML = Object.keys(TOLOV_NOMI)
      .filter(u => u !== joriy && (u !== 'bolib' || bolibBor))
      .map(u => `
        <button data-h-click="c:tolovUsulTanla" data-a-click="${SG_A([String(u)])}" class="w-full text-left rounded-xl text-sm transition-all"
          style="padding:12px;background:#f1f7ff;color:#1c3d63;border:1px solid rgba(120,170,235,0.22)">
          <i class="fas fa-angle-right mr-2" style="color:#3d7ab5"></i>${TOLOV_NOMI[u]}
        </button>`).join('');
    box.classList.remove('hidden');
  }

  async function tolovUsulTanla(usul) {
    let oy = 0;
    if (usul === 'bolib') {
      const shartlar = (XARID_NARX.bolib || []).map(s => s.oy);
      const javob = prompt('Necha oyga bo\'lib to\'lamoqchisiz? (' + shartlar.join(' / ') + ')', shartlar[0]);
      oy = parseInt(javob, 10);
      if (!shartlar.includes(oy)) { showToast('Muddat tanlanmadi'); return; }
    }
    try {
      const r = await apiPostXaridTasdiq('/xaridlar/' + xaridJoriyRaqam + '/tolov/', { method: usul, months: oy });
      if (r.amount_changed) showToast('Summa yangilandi: ' + somFmt(r.amount));
      const b = await apiGetXarid('/xaridlar/' + xaridJoriyRaqam + '/');
      document.getElementById('xa-tolov-panel').innerHTML = tolovPanel(b);
      showToast("To'lov usuli o'zgartirildi: " + (TOLOV_NOMI[usul] || usul));
    } catch (e) {
      showToast((e && e.data && e.data.detail) || "To'lov usulini o'zgartirib bo'lmadi");
    }
  }

  function xaridNatijaKorsat(b) {
    const yetkNomi = b.delivery.method === 'kuryer' ? 'Kuryer yetkazib beradi' : 'Filialdan olib ketish';
    let tlvNomi = TOLOV_NOMI[b.payment.method] || b.payment.method;
    if (b.payment.months) tlvNomi += ` — oyiga ${somFmt(b.payment.monthly)} × ${b.payment.months} oy`;
    const tolovBelgi = b.payment.paid
      ? '<span style="color:#15803d;font-weight:700"> — To\'landi ✓</span>'
      : (b.payment.method !== 'naqd' ? '<span style="color:#5b7fa6"> — kutilmoqda</span>' : '');

    document.getElementById('xarid-form').classList.add('hidden');
    document.getElementById('xarid-kuzat').classList.add('hidden');
    document.getElementById('xarid-title').innerHTML =
      'Buyurtma <span style="background:linear-gradient(135deg,#0d6efd,#0d6efd,#17538f);-webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text">Holati</span>';

    document.getElementById('xarid-natija').innerHTML = `
      <div class="text-center mb-6">
        <div class="w-16 h-16 rounded-full mx-auto mb-4 flex items-center justify-center"
          style="background:linear-gradient(135deg,#ff8a00,#ff8a00);box-shadow:0 2px 8px rgba(31,72,135,0.10)">
          <i class="fas fa-check text-2xl" style="color:#0a0900"></i>
        </div>
        <h3 class="text-2xl font-black text-ink-900 mb-1">Buyurtmangiz qabul qilindi!</h3>
        <p class="text-sm" style="color:#5b7fa6">Raqamni saqlab qo'ying — holatni shu raqam orqali kuzatasiz.</p>
        <div class="inline-block mt-4 px-6 py-3 rounded-2xl"
          style="background:#f1f7ff;border:1px dashed rgba(120,170,235,0.5)">
          <div class="text-[10px] uppercase tracking-widest" style="color:#5b7fa6">Buyurtma raqami</div>
          <div class="text-2xl font-black" style="color:#0d6efd;font-family:monospace">${b.id}</div>
        </div>
      </div>

      <div class="xarid-card">
        <div class="flex items-center justify-between mb-3">
          <div class="xarid-legend" style="margin-bottom:0"><i class="fas fa-route mr-2"></i>Holat</div>
          <span id="xa-jonli" class="text-[10px] font-bold uppercase tracking-wider flex items-center gap-1.5"
            style="color:#15803d">
            <span style="width:6px;height:6px;border-radius:50%;background:#4ade80;display:inline-block;
              animation:xaridPuls 1.8s ease-in-out infinite"></span>Jonli kuzatuv
          </span>
        </div>
        <div id="xa-bosqichlar">${xaridBosqichlar(b.status)}</div>
      </div>

      <!-- Yetkazib bo'lmagan bo'lsa — sabab va qayta so'rash -->
      <div id="xa-muammo-card">${muammoPanel(b)}</div>

      <!-- Kuryer xaritasi (faqat yo'ldagi buyurtmalarda) -->
      <div id="xa-kuryer-card" class="xarid-card ${b.delivery.courier ? '' : 'hidden'}">
        <div class="xarid-legend"><i class="fas fa-map-location-dot mr-2"></i>Kuryer qayerda</div>
        <div id="xa-xarita"></div>
        <p id="xa-kuryer-info" class="text-xs mt-2" style="color:#5b7fa6"></p>
      </div>

      <div class="xarid-card">
        <div class="xarid-legend"><i class="fas fa-box mr-2"></i>Mahsulotlar</div>
        ${b.items.map(it => `
          <div class="flex items-center gap-3 py-2">
            <div class="w-10 h-10 rounded-lg flex items-center justify-center shrink-0"
              style="background:rgba(120,170,235,0.08);border:1px solid rgba(120,170,235,0.25)">
              <i class="fas ${it.image || 'fa-box'}" style="color:#0d6efd"></i>
            </div>
            <div class="flex-1 min-w-0"><div class="text-sm text-ink-900">${it.name}</div>
              <div class="text-xs" style="color:#5b7fa6">${it.qty} dona${it.price ? ' × ' + somFmt(it.price) : ''}</div></div>
            <div class="text-sm shrink-0" style="color:#1c3d63">${it.price ? somFmt(it.price * it.qty) : '—'}</div>
          </div>`).join('')}
        ${xaridSummaTafsil(b)}
      </div>

      <div class="xarid-card">
        <div class="xarid-legend"><i class="fas fa-truck mr-2"></i>Yetkazish va to'lov</div>
        <div class="xarid-qator"><span>Mijoz</span><span>${b.customer.name}</span></div>
        <div class="xarid-qator"><span>Telefon</span><span>${b.customer.phone}</span></div>
        ${b.customer.address ? `<div class="xarid-qator"><span>Manzil</span><span>${b.customer.address}</span></div>` : ''}
        <div class="xarid-qator"><span>Yetkazish</span><span>${yetkNomi}</span></div>
        ${b.delivery.time ? `<div class="xarid-qator"><span>Yetkazish vaqti</span><span>${b.delivery.time}</span></div>` : ''}
        ${b.delivery.note ? `<div class="xarid-qator"><span>Izoh</span><span>${b.delivery.note}</span></div>` : ''}
        <div class="xarid-qator"><span>To'lov</span><span>${tlvNomi}${tolovBelgi}</span></div>
        ${b.installService ? '<div class="xarid-qator"><span>Qo\'shimcha</span><span>O\'rnatish xizmati</span></div>' : ''}
      </div>

      <div id="xa-tolov-panel">${tolovPanel(b)}</div>

      <button data-h-click="h69" class="w-full font-bold rounded-xl transition-all active:scale-95"
        style="padding:13px;background:rgba(31,72,135,0.04);color:#0d6efd;border:1px solid rgba(120,170,235,0.28)">
        Bosh sahifaga qaytish
      </button>`;
    document.getElementById('xarid-natija').classList.remove('hidden');
    document.getElementById('xarid-page').classList.remove('hidden');
    document.getElementById('xarid-page').scrollTop = 0;
    document.body.style.overflow = 'hidden';

    // Har safar yangi buyurtma — xaritani noldan quramiz
    xaritaniTozala();
    kuryerYangila(b);
    xaridKuzatBoshla(b.id, b.status);
  }

  function xaritaniTozala() {
    if (xaridXarita) { xaridXarita.remove(); xaridXarita = null; }
    kuryerNishon = null;
    manzilNishon = null;
  }

  // ---- Buyurtmalarni kuzatish (raqam yoki telefon bo'yicha) ----
  function openXaridKuzat() {
    document.getElementById('xarid-form').classList.add('hidden');
    document.getElementById('xarid-natija').classList.add('hidden');
    document.getElementById('xarid-kuzat').classList.remove('hidden');
    document.getElementById('xarid-title').innerHTML =
      'Mening <span style="background:linear-gradient(135deg,#0d6efd,#0d6efd,#17538f);-webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text">Buyurtmalarim</span>';
    document.getElementById('xk-natija').innerHTML = '';
    document.getElementById('xarid-page').classList.remove('hidden');
    document.body.style.overflow = 'hidden';
  }

  async function xaridQidir() {
    const q = document.getElementById('xk-qidiruv').value.trim();
    const wrap = document.getElementById('xk-natija');
    if (!q) { wrap.innerHTML = ''; return; }
    wrap.innerHTML = '<p class="text-center py-8" style="color:#5b7fa6"><i class="fas fa-spinner fa-spin mr-2"></i>Qidirilmoqda...</p>';

    try {
      let royxat;
      if (/^SG-/i.test(q)) {
        const bitta = await apiGetXarid('/xaridlar/' + encodeURIComponent(q.toUpperCase()) + '/');
        royxat = [bitta];
      } else {
        royxat = await apiGetPub('/xaridlar/?telefon=' + encodeURIComponent(q));
      }
      if (!royxat.length) {
        wrap.innerHTML = '<p class="text-center py-10" style="color:#5b7fa6">Buyurtma topilmadi.</p>';
        return;
      }
      wrap.innerHTML = royxat.map(b => `
        <div class="xarid-card" style="cursor:pointer" data-h-click="c:xaridNatijaKorsat" data-a-click="${SG_A([b])}">
          <div class="flex items-center justify-between gap-3 flex-wrap">
            <div>
              <div class="font-black text-lg" style="color:#0d6efd;font-family:monospace">${b.id}</div>
              <div class="text-xs mt-0.5" style="color:#5b7fa6">
                ${new Date(b.createdAt).toLocaleDateString('uz-UZ')} · ${b.items.length} ta mahsulot
              </div>
            </div>
            <div class="text-right">
              <div class="font-black text-ink-900">${somFmt(b.total)}</div>
              <div class="text-xs mt-0.5" style="color:#0d6efd">
                ${(XARID_OQIM.find(([k]) => k === b.status) || [null, 'Bekor qilindi'])[1]}
              </div>
            </div>
          </div>
        </div>`).join('');
    } catch (e) {
      wrap.innerHTML = '<p class="text-center py-10" style="color:#dc2626">Topilmadi yoki serverga ulanib bo\'lmadi.</p>';
    }
  }

  function renderCart() {
    const wrap  = document.getElementById('cart-items');
    const empty = document.getElementById('cart-empty');
    const foot  = document.getElementById('cart-footer');
    if (!cart.length) {
      wrap.innerHTML = '';
      empty.classList.remove('hidden');
      foot.classList.add('hidden');
      return;
    }
    empty.classList.add('hidden');
    foot.classList.remove('hidden');
    wrap.innerHTML = cart.map((c, i) => {
      const unit = c.narx ? c.narx.toLocaleString('uz-UZ') + " so'm / dona" : "Narx so'rov asosida";
      const line = c.narx ? (c.narx * c.qty).toLocaleString('uz-UZ') + " so'm" : '—';
      return `
      <div class="flex items-center gap-3 sm:gap-4 rounded-2xl p-3 sm:p-4"
        style="background:linear-gradient(160deg,#e7f1fd 0%,#f1f7ff 60%,#f2f8ff 100%);border:1px solid rgba(120,170,235,0.28);box-shadow:0 4px 20px rgba(31,72,135,0.10)">
        <div class="w-14 h-14 sm:w-16 sm:h-16 rounded-xl flex items-center justify-center shrink-0"
          style="background:${c.rang}14;border:1px solid ${c.rang}44">
          <i class="fas ${c.ikona || 'fa-box'} text-lg sm:text-xl" style="color:${c.rang || '#0d6efd'}"></i>
        </div>
        <div class="flex-1 min-w-0">
          <div class="font-bold text-ink-900 text-sm leading-snug" style="overflow:hidden;text-overflow:ellipsis">${c.nom}</div>
          <div class="text-xs mt-1" style="color:#3d7ab5">${unit}</div>
          <div class="text-xs font-black mt-1 sm:hidden" style="color:#0d6efd">${line}</div>
        </div>
        <div class="flex items-center rounded-xl overflow-hidden shrink-0" style="background:#f1f7ff;border:1px solid rgba(120,170,235,0.35)">
          <button data-h-click="c:cartSetQty" data-a-click="${SG_A([i, -1])}" class="w-8 h-8 flex items-center justify-center font-black transition-colors"
            style="color:#3d7ab5;border-right:1px solid rgba(120,170,235,0.2)"
            data-h-mouseover="h202" data-h-mouseout="h203">−</button>
          <span class="w-9 text-center font-black text-sm" style="color:#0d6efd">${c.qty}</span>
          <button data-h-click="c:cartSetQty" data-a-click="${SG_A([i, 1])}" class="w-8 h-8 flex items-center justify-center font-black transition-colors"
            style="color:#3d7ab5;border-left:1px solid rgba(120,170,235,0.2)"
            data-h-mouseover="h202" data-h-mouseout="h203">+</button>
        </div>
        <div class="text-right shrink-0 hidden sm:block" style="min-width:104px">
          <div class="font-black text-sm" style="color:#0d6efd">${line}</div>
        </div>
        <button data-h-click="c:cartRemove" data-a-click="${SG_A([i])}" class="w-8 h-8 rounded-lg flex items-center justify-center shrink-0 transition-all"
          style="background:rgba(31,72,135,0.04);color:#3d7ab5;border:1px solid rgba(120,170,235,0.15)"
          data-h-mouseover="h204"
          data-h-mouseout="h205"
          title="O'chirish"><i class="fas fa-trash-can text-xs"></i></button>
      </div>`;
    }).join('');
    document.getElementById('cart-sum').textContent = cartTotalSum().toLocaleString('uz-UZ') + " so'm";
    document.getElementById('cart-qty').textContent = cartTotalQty();
  }

  // ---- MODAL ----
  const modalContents = {
    loyiha: `__LOYIHA_DYNAMIC__`,

    montaj: `<div class="text-3xl mb-3">🔧</div><h3 class="text-xl font-bold mb-3">Montaj xizmati</h3><p class="text-gray-400 text-sm leading-relaxed mb-4">Malakali jamoamiz tomonidan gaz tizimlarini xavfsiz va sifatli o'rnatish. Barcha ishlar sertifikatlangan mutaxassislar tomonidan bajariladi.</p><ul class="space-y-2 text-sm text-gray-400 mb-6"><li class="flex gap-2"><i class="fas fa-check text-gold-400 mt-0.5"></i>Ichki va tashqi gaz tarmoqlari</li><li class="flex gap-2"><i class="fas fa-check text-gold-400 mt-0.5"></i>Hisoblagichlar o'rnatish</li><li class="flex gap-2"><i class="fas fa-check text-gold-400 mt-0.5"></i>Xavfsizlik tizimlari</li><li class="flex gap-2"><i class="fas fa-check text-gold-400 mt-0.5"></i>2 yil kafolat</li></ul><button data-h-click="h206" class="w-full gold-btn text-oq font-bold py-3 rounded-xl">Narx hisoblash</button>`,

    servis: `<div class="text-3xl mb-3">🛠️</div><h3 class="text-xl font-bold mb-3">Servis chaqirish</h3><p class="text-gray-400 text-sm leading-relaxed mb-4">Texnik muammo yuzaga keldi? Mutaxassisimizni 30 daqiqada chaqiring.</p><div class="space-y-3 mb-6"><input type="text" placeholder="Ismingiz" class="w-full bg-navy-700 border border-navy-600 text-ink-900 rounded-xl px-4 py-3 text-sm outline-none"/><input type="tel" placeholder="+998 90 000 00 00" class="w-full bg-navy-700 border border-navy-600 text-ink-900 rounded-xl px-4 py-3 text-sm outline-none"/><textarea rows="3" placeholder="Muammo tavsifi..." class="w-full bg-navy-700 border border-navy-600 text-ink-900 rounded-xl px-4 py-3 text-sm outline-none resize-none"></textarea></div><button data-h-click="h207" class="w-full gold-btn text-oq font-bold py-3 rounded-xl">🚨 Tez yordam chaqirish</button>`,

    hisobot: `<div class="text-3xl mb-3">📊</div><h3 class="text-xl font-bold mb-3">Oylik hisobot</h3><div class="space-y-3 mb-6"><div class="flex justify-between p-3 bg-navy-700 rounded-xl text-sm"><span class="text-gray-400">Gaz sarfi (may)</span><span class="text-ink-900 font-bold">124.5 m³</span></div><div class="flex justify-between p-3 bg-navy-700 rounded-xl text-sm"><span class="text-gray-400">O'tgan oy</span><span class="text-ink-900 font-bold">118.2 m³</span></div><div class="flex justify-between p-3 bg-navy-700 rounded-xl text-sm"><span class="text-gray-400">Farq</span><span class="text-gold-400 font-bold">+6.3 m³ (+5.3%)</span></div><div class="flex justify-between p-3 bg-navy-700 rounded-xl text-sm"><span class="text-gray-400">To'lov summasi</span><span class="text-ink-900 font-bold">87,150 so'm</span></div></div><button data-h-click="h208" class="w-full gold-btn text-oq font-bold py-3 rounded-xl">📧 Emailga yuborish</button>`,

    buyurtma: `<div class="text-3xl mb-3">🛒</div><h3 class="text-xl font-bold mb-3">Buyurtma berish</h3><div class="space-y-3 mb-6"><input type="text" placeholder="Ism-familiya" class="w-full bg-navy-700 border border-navy-600 text-ink-900 rounded-xl px-4 py-3 text-sm outline-none"/><input type="tel" placeholder="+998 90 000 00 00" class="w-full bg-navy-700 border border-navy-600 text-ink-900 rounded-xl px-4 py-3 text-sm outline-none"/><select class="w-full bg-navy-700 border border-navy-600 text-ink-900 rounded-xl px-4 py-3 text-sm outline-none"><option>Loyihalashtirish</option><option>Montaj</option><option>Servis</option><option>Uskunalar</option></select><textarea rows="3" placeholder="Qo'shimcha ma'lumot..." class="w-full bg-navy-700 border border-navy-600 text-ink-900 rounded-xl px-4 py-3 text-sm outline-none resize-none"></textarea></div><button data-h-click="h209" class="w-full gold-btn text-oq font-bold py-3 rounded-xl">✅ Buyurtma berish</button>`,

    savat: `<div class="text-3xl mb-3">🛒</div><h3 class="text-xl font-bold mb-3">Sizning savatingiz</h3><div id="cartItemsList" class="space-y-2 mb-6 max-h-48 overflow-y-auto"></div><button data-h-click="h210" class="w-full gold-btn text-oq font-bold py-3 rounded-xl">Buyurtma berish</button>`,

    'lpg-balon': `<div class="text-4xl mb-3">🧪</div><h3 class="text-xl font-bold mb-2">Ballonli Tizim</h3><p class="text-gray-400 text-sm mb-5">Uy-joy va kichik ob'ektlar uchun 5–50 litrlik LPG ballonlar asosida qulay gaz ta'minoti.</p><div class="space-y-2 mb-5 text-sm text-gray-300"><div class="flex items-center gap-2 p-3 bg-navy-700 rounded-xl"><i class="fas fa-circle text-teal-400 text-[6px]"></i>5, 12, 27 va 50 kg hajmdagi balonlar</div><div class="flex items-center gap-2 p-3 bg-navy-700 rounded-xl"><i class="fas fa-circle text-teal-400 text-[6px]"></i>Regulyator o'rnatish va xavfsizlik tekshiruvi</div><div class="flex items-center gap-2 p-3 bg-navy-700 rounded-xl"><i class="fas fa-circle text-teal-400 text-[6px]"></i><b>Narxlar tez orada kiritiladi</b></div></div><button data-h-click="h211" class="w-full bg-gradient-to-r from-teal-600 to-teal-500 text-white font-bold py-3 rounded-xl hover:opacity-90 transition-all">Buyurtma berish</button>`,

    'lpg-rezervuar': `<div class="text-4xl mb-3">🗄️</div><h3 class="text-xl font-bold mb-2">Rezervuarli Tizim</h3><p class="text-gray-400 text-sm mb-5">500 dan 10 000 litrgacha yer osti yoki yer usti rezervuarlari bilan avtonom gaz ta'minoti. Ko'p xonadon va fermer xo'jaliklari uchun ideal.</p><div class="space-y-2 mb-5 text-sm text-gray-300"><div class="flex items-center gap-2 p-3 bg-navy-700 rounded-xl"><i class="fas fa-circle text-teal-400 text-[6px]"></i>500, 1000 va 2000 L rezervuarlar (yer usti yoki yer osti)</div><div class="flex items-center gap-2 p-3 bg-navy-700 rounded-xl"><i class="fas fa-circle text-teal-400 text-[6px]"></i>To'liq ulash va hujjatlashtirish kiritilgan</div><div class="flex items-center gap-2 p-3 bg-navy-700 rounded-xl"><i class="fas fa-circle text-teal-400 text-[6px]"></i><b>Narxlar tez orada kiritiladi</b></div></div><button data-h-click="h211" class="w-full bg-gradient-to-r from-teal-600 to-teal-500 text-white font-bold py-3 rounded-xl hover:opacity-90 transition-all">Buyurtma berish</button>`,

  };

  function showModal(type) {
    // Savat endi to'liq sahifada ochiladi
    if (type === 'savat') { openCartPage(); return; }
    const _m = document.getElementById('modal');
    // Oyna har doim sahifa ustida (overlay) ochilishi uchun body'ga ko'chiramiz —
    // aks holda transform/filter'li ota-element uni sahifa oqimiga tushirib yuboradi
    if (_m.parentElement !== document.body) document.body.appendChild(_m);
    _m.style.position = 'fixed';
    _m.style.inset = '0';
    _m.style.zIndex = '9999';
    _m.classList.remove('hidden');
    // Xizmat oynalari kengroq bo'ladi — ichida tablar bor
    const keng = ['loyiha', 'montaj', 'servis'].includes(type);
    document.getElementById('modalBox').classList.toggle('max-w-md', !keng);
    document.getElementById('modalBox').classList.toggle('max-w-2xl', keng);

    if (keng) {
      document.getElementById('modalContent').innerHTML = xzOynaHtml(type);
    } else {
      document.getElementById('modalContent').innerHTML = modalContents[type] || '';
    }
    document.body.style.overflow = 'hidden';
  }

  // ---- LOYIHA STEPS ----
  function loyihaYoq() {
    document.getElementById('modalContent').innerHTML = `
      <div>
        <button data-h-click="h212" class="btn-ortga flex items-center gap-2 text-gray-400 hover:text-ink-900 text-sm mb-5 transition-colors">
          <i class="fas fa-arrow-left"></i> Orqaga
        </button>
        <div class="bg-amber-500/10 border border-amber-500/40 rounded-xl p-5 mb-5">
          <div class="flex items-start gap-3">
            <i class="fas fa-info-circle text-amber-400 mt-0.5 text-lg shrink-0"></i>
            <div>
              <div class="font-semibold text-amber-300 mb-1">Texnik shart kerak</div>
              <p class="text-gray-400 text-sm leading-relaxed">
                Loyiha uchun <strong class="text-ink-900">texnik shart (ТУ)</strong> talab etiladi.
                Uni <strong class="text-ink-900">my.gov.uz</strong> orqali olishingiz mumkin.
              </p>
            </div>
          </div>
        </div>

        <div class="space-y-2 text-sm text-gray-400 mb-5">
          <div class="flex items-center gap-3 bg-navy-700 rounded-xl p-3">
            <i class="fas fa-file-alt text-gold-400"></i>
            <span>"Kommunal xizmatlar" → "Gaz texnik sharti" bo'limiga o'ting</span>
          </div>
          <div class="flex items-center gap-3 bg-navy-700 rounded-xl p-3">
            <i class="fas fa-id-card text-gold-400"></i>
            <span>Pasport va yer uchastkasi hujjatlari kerak bo'ladi</span>
          </div>
          <div class="flex items-center gap-3 bg-navy-700 rounded-xl p-3">
            <i class="fas fa-clock text-gold-400"></i>
            <span>Hujjat 5–10 ish kuni ichida tayyor bo'ladi</span>
          </div>
        </div>


        <a href="https://my.gov.uz" target="_blank"
          class="w-full gold-btn text-oq font-bold py-4 rounded-xl hover:opacity-90 transition-all flex items-center justify-center gap-2 text-base">
          <i class="fas fa-external-link-alt"></i> my.gov.uz ga o'tish
        </a>
        <p class="text-center text-gray-500 text-xs mt-3">Texnik shart olgach, bu yerga qaytib ariza topshiring</p>
      </div>
    `;
  }

  function loyihaHa() {
    document.getElementById('modalContent').innerHTML = `
      <div>
        <h3 class="text-lg font-bold mb-1">Loyihalashtirish</h3>
        <p class="text-gray-400 text-xs mb-5">Quyidagi bo'limlardan birini tanlang</p>

        <div class="space-y-3">
          <button data-h-click="h213"
            class="w-full flex items-center gap-4 bg-navy-700 hover:bg-navy-600 border border-navy-600 hover:border-gold-500/50 rounded-xl p-4 text-left transition-all">
            <div class="w-12 h-12 shrink-0 bg-gold-500/15 rounded-xl flex items-center justify-center">
              <i class="fas fa-drafting-compass text-gold-400 text-lg"></i>
            </div>
            <div class="flex-1">
              <div class="font-semibold text-ink-900 text-sm">Texnik loyiha</div>
              <div class="text-gray-400 text-xs mt-0.5">Texnik shart, manzil va arizalarni ko'rish</div>
            </div>
            <i class="fas fa-chevron-right text-gray-500"></i>
          </button>

          <button data-h-click="h214"
            class="w-full flex items-center gap-4 bg-navy-700 hover:bg-navy-600 border border-navy-600 hover:border-cobalt-500/50 rounded-xl p-4 text-left transition-all">
            <div class="w-12 h-12 shrink-0 bg-cobalt-500/15 rounded-xl flex items-center justify-center">
              <i class="fas fa-stamp text-cobalt-300 text-lg"></i>
            </div>
            <div class="flex-1">
              <div class="font-semibold text-ink-900 text-sm">Ruxsatnomalar</div>
              <div class="text-gray-400 text-xs mt-0.5">Loyihangiz uchun zarur ruxsat hujjatlari</div>
            </div>
            <i class="fas fa-chevron-right text-gray-500"></i>
          </button>

          <button data-h-click="h215"
            class="w-full flex items-center gap-4 bg-navy-700 hover:bg-navy-600 border border-navy-600 hover:border-teal-500/50 rounded-xl p-4 text-left transition-all">
            <div class="w-12 h-12 shrink-0 bg-teal-500/15 rounded-xl flex items-center justify-center">
              <i class="fas fa-magnifying-glass-chart text-teal-300 text-lg"></i>
            </div>
            <div class="flex-1">
              <div class="font-semibold text-ink-900 text-sm">Ekspertiza</div>
              <div class="text-gray-400 text-xs mt-0.5">Loyihaning texnik ekspertizadan o'tishi</div>
            </div>
            <i class="fas fa-chevron-right text-gray-500"></i>
          </button>

          <button data-h-click="h216"
            class="w-full flex items-center gap-4 bg-navy-700 hover:bg-navy-600 border border-navy-600 hover:border-gold-500/50 rounded-xl p-4 text-left transition-all">
            <div class="w-12 h-12 shrink-0 bg-gold-500/15 rounded-xl flex items-center justify-center">
              <i class="fas fa-cube text-gold-400 text-lg"></i>
            </div>
            <div class="flex-1">
              <div class="font-semibold text-ink-900 text-sm">3D modellashtirish</div>
              <div class="text-gray-400 text-xs mt-0.5">Gaz tizimingizning 3D vizual ko'rinishi</div>
            </div>
            <i class="fas fa-chevron-right text-gray-500"></i>
          </button>
        </div>
      </div>
    `;
  }

  function texnikLoyihaBolimi() {
    document.getElementById('modalContent').innerHTML = `
      <div>
        <button data-h-click="h217" class="btn-ortga flex items-center gap-2 text-gray-400 hover:text-ink-900 text-sm mb-5 transition-colors">
          <i class="fas fa-arrow-left"></i> Bo'limlarga qaytish
        </button>
        <h3 class="text-lg font-bold mb-1">Texnik loyiha</h3>
        <p class="text-gray-400 text-xs mb-5">Quyidagi bo'limlardan birini tanlab, ma'lumotlarni to'ldiring</p>

        <div class="space-y-3">
          <button data-h-click="h212"
            class="w-full flex items-center gap-4 bg-navy-700 hover:bg-navy-600 border border-navy-600 hover:border-gold-500/50 rounded-xl p-4 text-left transition-all">
            <div class="w-12 h-12 shrink-0 bg-gold-500/15 rounded-xl flex items-center justify-center">
              <i class="fas fa-file-contract text-gold-400 text-lg"></i>
            </div>
            <div class="flex-1">
              <div class="font-semibold text-ink-900 text-sm">Texnik shart bo'limi</div>
              <div class="text-gray-400 text-xs mt-0.5">TS raqami, tafsilotlari va hujjat fayli</div>
            </div>
            <i class="fas fa-chevron-right text-gray-500"></i>
          </button>

          <button data-h-click="h218"
            class="w-full flex items-center gap-4 bg-navy-700 hover:bg-navy-600 border border-navy-600 hover:border-cobalt-500/50 rounded-xl p-4 text-left transition-all">
            <div class="w-12 h-12 shrink-0 bg-cobalt-500/15 rounded-xl flex items-center justify-center">
              <i class="fas fa-map-marker-alt text-cobalt-300 text-lg"></i>
            </div>
            <div class="flex-1">
              <div class="font-semibold text-ink-900 text-sm">Loyiha manzili</div>
              <div class="text-gray-400 text-xs mt-0.5">Tuman, ko'cha-uy raqami va mo'ljal</div>
            </div>
            <i class="fas fa-chevron-right text-gray-500"></i>
          </button>

          <button data-h-click="h219"
            class="w-full flex items-center gap-4 bg-navy-700 hover:bg-navy-600 border border-navy-600 hover:border-teal-500/50 rounded-xl p-4 text-left transition-all">
            <div class="w-12 h-12 shrink-0 bg-teal-500/15 rounded-xl flex items-center justify-center">
              <i class="fas fa-folder-open text-teal-300 text-lg"></i>
            </div>
            <div class="flex-1">
              <div class="font-semibold text-ink-900 text-sm">Loyihani ko'rish</div>
              <div class="text-gray-400 text-xs mt-0.5">Telefon raqamingiz orqali arizalaringiz bilan tanishing</div>
            </div>
            <i class="fas fa-chevron-right text-gray-500"></i>
          </button>
        </div>
      </div>
    `;
  }

  function texnikShartTanlov() {
    document.getElementById('modalContent').innerHTML = `
      <div>
        <button data-h-click="h213" class="btn-ortga flex items-center gap-2 text-gray-400 hover:text-ink-900 text-sm mb-5 transition-colors">
          <i class="fas fa-arrow-left"></i> Bo'limlarga qaytish
        </button>
        <div class="text-center">
          <div class="w-16 h-16 bg-gold-500/20 rounded-2xl flex items-center justify-center mx-auto mb-4">
            <i class="fas fa-file-contract text-gold-400 text-2xl"></i>
          </div>
          <h3 class="text-xl font-bold mb-2">Texnik shart bo'limi</h3>
          <p class="text-gray-400 text-sm mb-8">Xizmatdan foydalanish uchun <strong class="text-ink-900">texnik shart</strong> hujjati talab qilinadi.</p>

          <p class="text-ink-900 font-semibold mb-5">Sizda texnik shart hujjati bormi?</p>

          <div class="grid grid-cols-2 gap-4">
            <button data-h-click="h220"
              class="bg-green-500/20 hover:bg-green-500/30 border border-green-500/50 hover:border-green-400 text-green-300 font-bold py-4 rounded-xl transition-all">
              <i class="fas fa-check-circle text-xl block mb-1"></i>
              Ha, bor
            </button>
            <button data-h-click="h221"
              class="bg-red-500/20 hover:bg-red-500/30 border border-red-500/50 hover:border-red-400 text-red-300 font-bold py-4 rounded-xl transition-all">
              <i class="fas fa-times-circle text-xl block mb-1"></i>
              Yo'q, kerak
            </button>
          </div>
        </div>
      </div>
    `;
  }

  function loyihaTexnikShartBolimi() {
    document.getElementById('modalContent').innerHTML = `
      <div>
        <button data-h-click="h213" class="btn-ortga flex items-center gap-2 text-gray-400 hover:text-ink-900 text-sm mb-5 transition-colors">
          <i class="fas fa-arrow-left"></i> Bo'limlarga qaytish
        </button>
        <div class="flex items-center gap-2 text-gold-400 font-semibold mb-1">
          <i class="fas fa-file-contract"></i> Texnik shart bo'limi
        </div>
        <p class="text-gray-400 text-xs mb-5">Texnik shart ma'lumotlarini to'ldiring — mutaxassisimiz 24 soat ichida bog'lanadi</p>

        <form data-h-submit="h222" class="space-y-4">
          <div class="grid grid-cols-2 gap-3">
            <div>
              <label class="text-gray-400 text-xs mb-1 block">Ism-familiya *</label>
              <input id="tsName" type="text" required placeholder="To'liq ism"
                class="w-full bg-navy-700 border border-navy-600 focus:border-cobalt-500 text-ink-900 rounded-xl px-3 py-2.5 text-sm outline-none transition-colors"/>
            </div>
            <div>
              <label class="text-gray-400 text-xs mb-1 block">Telefon *</label>
              <input id="tsPhone" type="tel" required placeholder="+998 90 000 00 00"
                class="w-full bg-navy-700 border border-navy-600 focus:border-cobalt-500 text-ink-900 rounded-xl px-3 py-2.5 text-sm outline-none transition-colors"/>
            </div>
          </div>
          <div>
            <label class="text-gray-400 text-xs mb-1 block">Texnik shart raqami *</label>
            <input id="tsNum" type="text" required placeholder="Masalan: ТУ-2024-00123"
              class="w-full bg-navy-700 border border-navy-600 focus:border-cobalt-500 text-ink-900 rounded-xl px-3 py-2.5 text-sm outline-none transition-colors font-mono"/>
          </div>
          <div>
            <label class="text-gray-400 text-xs mb-1 block">Texnik shart tafsilotlari</label>
            <textarea id="tsDesc" rows="3" placeholder="Gaz sarfi, bosim, binoning turi..."
              class="w-full bg-navy-700 border border-navy-600 focus:border-cobalt-500 text-ink-900 rounded-xl px-3 py-2.5 text-sm outline-none transition-colors resize-none"></textarea>
          </div>
          <div>
            <label class="text-gray-400 text-xs mb-1 block">Texnik shart fayli (ixtiyoriy)</label>
            <label class="flex items-center gap-3 w-full bg-navy-700 border border-dashed border-navy-500 hover:border-gold-500/60 rounded-xl px-3 py-3 cursor-pointer transition-colors">
              <i class="fas fa-paperclip text-gold-400"></i>
              <span id="tsFileName" class="text-gray-400 text-sm">Fayl tanlash (PDF, JPG, PNG)</span>
              <input type="file" id="tsFile" accept=".pdf,.jpg,.jpeg,.png" class="hidden" data-h-change="h223"/>
            </label>
          </div>
          <button type="submit"
            class="w-full gold-btn text-oq font-bold py-3.5 rounded-xl hover:opacity-90 transition-all flex items-center justify-center gap-2">
            <i class="fas fa-save"></i> Saqlash va Yuborish
          </button>
        </form>
      </div>
    `;
  }

  function loyihaManzilBolimi() {
    document.getElementById('modalContent').innerHTML = `
      <div>
        <button data-h-click="h213" class="btn-ortga flex items-center gap-2 text-gray-400 hover:text-ink-900 text-sm mb-5 transition-colors">
          <i class="fas fa-arrow-left"></i> Bo'limlarga qaytish
        </button>
        <div class="flex items-center gap-2 text-cobalt-300 font-semibold mb-1">
          <i class="fas fa-map-marker-alt"></i> Loyiha manzili
        </div>
        <p class="text-gray-400 text-xs mb-5">Loyiha amalga oshiriladigan manzil ma'lumotlarini to'ldiring</p>

        <form data-h-submit="h224" class="space-y-4">
          <div class="grid grid-cols-2 gap-3">
            <div>
              <label class="text-gray-400 text-xs mb-1 block">Ism-familiya *</label>
              <input id="mzName" type="text" required placeholder="To'liq ism"
                class="w-full bg-navy-700 border border-navy-600 focus:border-cobalt-500 text-ink-900 rounded-xl px-3 py-2.5 text-sm outline-none transition-colors"/>
            </div>
            <div>
              <label class="text-gray-400 text-xs mb-1 block">Telefon *</label>
              <input id="mzPhone" type="tel" required placeholder="+998 90 000 00 00"
                class="w-full bg-navy-700 border border-navy-600 focus:border-cobalt-500 text-ink-900 rounded-xl px-3 py-2.5 text-sm outline-none transition-colors"/>
            </div>
          </div>
          <div>
            <label class="text-gray-400 text-xs mb-1 block">Tuman / shahar *</label>
            <select id="mzTuman" required class="w-full bg-navy-700 border border-navy-600 focus:border-cobalt-500 text-ink-900 rounded-xl px-3 py-2.5 text-sm outline-none transition-colors" data-hudud>
              <option value="">Tanlang...</option>
              <!-- HUDUD:BOSH -->
                <optgroup label="Qoraqalpog'iston Respublikasi"><option>Nukus shahri</option><option>Amudaryo tumani</option><option>Beruniy tumani</option><option>Bo'zatov tumani</option><option>Chimboy tumani</option><option>Ellikqal'a tumani</option><option>Kegeyli tumani</option><option>Mo'ynoq tumani</option><option>Nukus tumani</option><option>Qanliko'l tumani</option><option>Qo'ng'irot tumani</option><option>Qorao'zak tumani</option><option>Shumanay tumani</option><option>Taxtako'pir tumani</option><option>To'rtko'l tumani</option><option>Xo'jayli tumani</option></optgroup>
                <optgroup label="Andijon viloyati"><option>Andijon shahri</option><option>Xonobod shahri</option><option>Andijon tumani</option><option>Asaka tumani</option><option>Baliqchi tumani</option><option>Bo'ston tumani</option><option>Buloqboshi tumani</option><option>Izboskan tumani</option><option>Jalaquduq tumani</option><option>Qo'rg'ontepa tumani</option><option>Marhamat tumani</option><option>Oltinko'l tumani</option><option>Paxtaobod tumani</option><option>Shahrixon tumani</option><option>Ulug'nor tumani</option><option>Xo'jaobod tumani</option></optgroup>
                <optgroup label="Buxoro viloyati"><option>Buxoro shahri</option><option>Kogon shahri</option><option>Buxoro tumani</option><option>G'ijduvon tumani</option><option>Jondor tumani</option><option>Kogon tumani</option><option>Olot tumani</option><option>Peshku tumani</option><option>Qorako'l tumani</option><option>Qorovulbozor tumani</option><option>Romitan tumani</option><option>Shofirkon tumani</option><option>Vobkent tumani</option></optgroup>
                <optgroup label="Farg'ona viloyati"><option>Farg'ona shahri</option><option>Marg'ilon shahri</option><option>Qo'qon shahri</option><option>Quvasoy shahri</option><option>Beshariq tumani</option><option>Bog'dod tumani</option><option>Buvayda tumani</option><option>Dang'ara tumani</option><option>Farg'ona tumani</option><option>Furqat tumani</option><option>Oltiariq tumani</option><option>Qo'shtepa tumani</option><option>Quva tumani</option><option>Rishton tumani</option><option>So'x tumani</option><option>Toshloq tumani</option><option>Uchko'prik tumani</option><option>O'zbekiston tumani</option><option>Yozyovon tumani</option></optgroup>
                <optgroup label="Jizzax viloyati"><option>Jizzax shahri</option><option>Arnasoy tumani</option><option>Baxmal tumani</option><option>Do'stlik tumani</option><option>Forish tumani</option><option>G'allaorol tumani</option><option>Mirzacho'l tumani</option><option>Paxtakor tumani</option><option>Sharof Rashidov tumani</option><option>Yangiobod tumani</option><option>Zafarobod tumani</option><option>Zarbdor tumani</option><option>Zomin tumani</option></optgroup>
                <optgroup label="Namangan viloyati"><option>Namangan shahri</option><option>Chortoq tumani</option><option>Chust tumani</option><option>Davlatobod tumani</option><option>Kosonsoy tumani</option><option>Mingbuloq tumani</option><option>Namangan tumani</option><option>Norin tumani</option><option>Pop tumani</option><option>To'raqo'rg'on tumani</option><option>Uchqo'rg'on tumani</option><option>Uychi tumani</option><option>Yangiqo'rg'on tumani</option></optgroup>
                <optgroup label="Navoiy viloyati"><option>Navoiy shahri</option><option>Zarafshon shahri</option><option>Karmana tumani</option><option>Konimex tumani</option><option>Navbahor tumani</option><option>Nurota tumani</option><option>Qiziltepa tumani</option><option>Tomdi tumani</option><option>Uchquduq tumani</option><option>Xatirchi tumani</option></optgroup>
                <optgroup label="Qashqadaryo viloyati"><option>Qarshi shahri</option><option>Shahrisabz shahri</option><option>Chiroqchi tumani</option><option>Dehqonobod tumani</option><option>G'uzor tumani</option><option>Kasbi tumani</option><option>Kitob tumani</option><option>Koson tumani</option><option>Ko'kdala tumani</option><option>Mirishkor tumani</option><option>Muborak tumani</option><option>Nishon tumani</option><option>Qamashi tumani</option><option>Qarshi tumani</option><option>Shahrisabz tumani</option><option>Yakkabog' tumani</option></optgroup>
                <optgroup label="Samarqand viloyati"><option>Samarqand shahri</option><option>Kattaqo'rg'on shahri</option><option>Bulung'ur tumani</option><option>Ishtixon tumani</option><option>Jomboy tumani</option><option>Kattaqo'rg'on tumani</option><option>Narpay tumani</option><option>Nurobod tumani</option><option>Oqdaryo tumani</option><option>Paxtachi tumani</option><option>Payariq tumani</option><option>Pastdarg'om tumani</option><option>Qo'shrabot tumani</option><option>Samarqand tumani</option><option>Toyloq tumani</option><option>Urgut tumani</option></optgroup>
                <optgroup label="Sirdaryo viloyati"><option>Guliston shahri</option><option>Shirin shahri</option><option>Yangiyer shahri</option><option>Boyovut tumani</option><option>Guliston tumani</option><option>Mirzaobod tumani</option><option>Oqoltin tumani</option><option>Sardoba tumani</option><option>Sayxunobod tumani</option><option>Sirdaryo tumani</option><option>Xovos tumani</option></optgroup>
                <optgroup label="Surxondaryo viloyati"><option>Termiz shahri</option><option>Angor tumani</option><option>Bandixon tumani</option><option>Boysun tumani</option><option>Denov tumani</option><option>Jarqo'rg'on tumani</option><option>Muzrabot tumani</option><option>Oltinsoy tumani</option><option>Qiziriq tumani</option><option>Qumqo'rg'on tumani</option><option>Sariosiyo tumani</option><option>Sherobod tumani</option><option>Sho'rchi tumani</option><option>Termiz tumani</option><option>Uzun tumani</option></optgroup>
                <optgroup label="Toshkent viloyati"><option>Nurafshon shahri</option><option>Angren shahri</option><option>Bekobod shahri</option><option>Chirchiq shahri</option><option>Olmaliq shahri</option><option>Ohangaron shahri</option><option>Yangiyo'l shahri</option><option>Bekobod tumani</option><option>Bo'ka tumani</option><option>Bo'stonliq tumani</option><option>Chinoz tumani</option><option>Ohangaron tumani</option><option>Oqqo'rg'on tumani</option><option>Parkent tumani</option><option>Piskent tumani</option><option>Qibray tumani</option><option>Quyi Chirchiq tumani</option><option>O'rta Chirchiq tumani</option><option>Yangiyo'l tumani</option><option>Yuqori Chirchiq tumani</option><option>Zangiota tumani</option></optgroup>
                <optgroup label="Xorazm viloyati"><option>Urganch shahri</option><option>Xiva shahri</option><option>Bog'ot tumani</option><option>Gurlan tumani</option><option>Hazorasp tumani</option><option>Qo'shko'pir tumani</option><option>Shovot tumani</option><option>Tuproqqal'a tumani</option><option>Urganch tumani</option><option>Xonqa tumani</option><option>Xiva tumani</option><option>Yangiariq tumani</option><option>Yangibozor tumani</option></optgroup>
                <optgroup label="Toshkent shahri"><option>Bektemir tumani</option><option>Chilonzor tumani</option><option>Mirobod tumani</option><option>Mirzo Ulug'bek tumani</option><option>Olmazor tumani</option><option>Sergeli tumani</option><option>Shayxontohur tumani</option><option>Uchtepa tumani</option><option>Yakkasaroy tumani</option><option>Yashnobod tumani</option><option>Yunusobod tumani</option></optgroup>
              <!-- HUDUD:OXIR -->
            </select>
          </div>
          <div>
            <label class="text-gray-400 text-xs mb-1 block">Ko'cha, uy raqami *</label>
            <input id="mzAddr" type="text" required placeholder="Masalan: Mustaqillik ko'chasi, 12-uy"
              class="w-full bg-navy-700 border border-navy-600 focus:border-cobalt-500 text-ink-900 rounded-xl px-3 py-2.5 text-sm outline-none transition-colors"/>
          </div>
          <div>
            <label class="text-gray-400 text-xs mb-1 block">Mo'ljal (ixtiyoriy)</label>
            <input id="mzIzoh" type="text" placeholder="Masalan: maktab yonida, 2-qavat..."
              class="w-full bg-navy-700 border border-navy-600 focus:border-cobalt-500 text-ink-900 rounded-xl px-3 py-2.5 text-sm outline-none transition-colors"/>
          </div>

          <div class="border-t border-navy-600 pt-4">
            <label class="text-gray-400 text-xs mb-2 block">Lokatsiya (ixtiyoriy)</label>
            <div class="space-y-2">
              <div class="flex gap-2">
                <input id="mzLokatsiya" type="text" readonly placeholder="Lokatsiya aniqlanmagan"
                  class="flex-1 bg-navy-700 border border-navy-600 text-ink-900 rounded-xl px-3 py-2.5 text-sm outline-none"/>
                <button type="button" data-h-click="h225"
                  class="px-4 bg-navy-700 border border-navy-600 hover:border-cobalt-500 text-cobalt-300 rounded-xl text-sm transition-colors flex items-center gap-2 whitespace-nowrap">
                  <i class="fas fa-location-crosshairs"></i> Xaritadan aniqlash
                </button>
              </div>
              <input id="mzYandexHavola" type="url" placeholder="Yandex Xaritalar lokatsiya havolasi (https://yandex.uz/maps/...)"
                class="w-full bg-navy-700 border border-navy-600 focus:border-cobalt-500 text-ink-900 rounded-xl px-3 py-2.5 text-sm outline-none transition-colors"/>
              <p class="text-gray-500 text-[11px] leading-relaxed">
                <i class="fas fa-circle-info mr-1"></i>Yandex Xaritalar ilovasida manzilni tanlang, "Ulashish" orqali havolani nusxalab shu yerga joylashtiring — bu lokatsiyani aniq topishimizga yordam beradi.
              </p>
            </div>
          </div>

          <button type="submit"
            class="w-full gold-btn text-oq font-bold py-3.5 rounded-xl hover:opacity-90 transition-all flex items-center justify-center gap-2">
            <i class="fas fa-save"></i> Saqlash va Yuborish
          </button>
        </form>
      </div>
    `;
  }

  function manzilLokatsiyaOl() {
    if (!navigator.geolocation) {
      showToast("Brauzeringiz joylashuvni aniqlashni qo'llamaydi");
      return;
    }
    const inp = document.getElementById('mzLokatsiya');
    inp.placeholder = 'Aniqlanmoqda...';
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        const lat = pos.coords.latitude.toFixed(6);
        const lng = pos.coords.longitude.toFixed(6);
        inp.value = lat + ', ' + lng;
        inp.dataset.lat = lat;
        inp.dataset.lng = lng;
        showToast('Joylashuv aniqlandi!');
      },
      () => {
        inp.placeholder = 'Lokatsiya aniqlanmagan';
        showToast("Joylashuvni aniqlab bo'lmadi. Brauzerda joylashuvga ruxsat berilganini tekshiring.");
      },
      { enableHighAccuracy: true, timeout: 10000 }
    );
  }

  // ---- LOYIHANI KO'RISH (telefon SMS-kod orqali tasdiqlanadi) ----
  let _lkTelefon = '';

  function loyihaKorishBolimi() {
    _lkTelefon = '';
    document.getElementById('modalContent').innerHTML = `
      <div>
        <button data-h-click="h213" class="btn-ortga flex items-center gap-2 text-gray-400 hover:text-ink-900 text-sm mb-5 transition-colors">
          <i class="fas fa-arrow-left"></i> Bo'limlarga qaytish
        </button>
        <div class="flex items-center gap-2 text-teal-300 font-semibold mb-1">
          <i class="fas fa-folder-open"></i> Loyihani ko'rish
        </div>
        <p class="text-gray-400 text-xs mb-5">Xavfsizlik uchun avval telefon raqamingiz SMS kod orqali tasdiqlanadi, so'ng shu raqamga tegishli arizalar ko'rsatiladi.</p>

        <form data-h-submit="h226" class="space-y-4">
          <div>
            <label class="text-gray-400 text-xs mb-1 block">Telefon raqami *</label>
            <input id="lkPhone" type="tel" required placeholder="+998 90 000 00 00"
              class="w-full bg-navy-700 border border-navy-600 focus:border-teal-500 text-ink-900 rounded-xl px-3 py-2.5 text-sm outline-none transition-colors"/>
          </div>
          <button type="submit"
            class="w-full gold-btn text-oq font-bold py-3.5 rounded-xl hover:opacity-90 transition-all flex items-center justify-center gap-2">
            <i class="fas fa-sms"></i> SMS tasdiqlash kodi yuborish
          </button>
        </form>
      </div>
    `;
  }

  async function loyihaKorishOtpYubor(e) {
    e.preventDefault();
    const tel = document.getElementById('lkPhone').value.trim();
    if (!tel) return;
    const btn = e.target.querySelector('button[type=submit]');
    btn.disabled = true; btn.innerHTML = '<i class="fas fa-spinner fa-spin mr-2"></i>Yuborilmoqda...';
    try {
      await apiPost('/auth/otp/yuborish/', { telefon: tel });
      _lkTelefon = tel;
      loyihaKorishKodFormasi();
      showToast('Tasdiqlash kodi ' + tel + ' raqamiga yuborildi!');
    } catch (err) {
      apiErr(err);
    } finally {
      btn.disabled = false; btn.innerHTML = '<i class="fas fa-sms mr-2"></i>SMS tasdiqlash kodi yuborish';
    }
  }

  function loyihaKorishKodFormasi() {
    document.getElementById('modalContent').innerHTML = `
      <div>
        <button data-h-click="h219" class="btn-ortga flex items-center gap-2 text-gray-400 hover:text-ink-900 text-sm mb-5 transition-colors">
          <i class="fas fa-arrow-left"></i> Orqaga
        </button>
        <div class="flex items-center gap-2 text-teal-300 font-semibold mb-1">
          <i class="fas fa-shield-alt"></i> Tasdiqlash kodi
        </div>
        <p class="text-gray-400 text-xs mb-5"><span class="text-ink-900 font-semibold">${escapeHtml(_lkTelefon)}</span> raqamiga yuborilgan kodni kiriting</p>

        <form data-h-submit="h227" class="space-y-4">
          <div>
            <label class="text-gray-400 text-xs mb-1 block">Tasdiqlash kodi *</label>
            <input id="lkKod" type="text" required maxlength="6" inputmode="numeric" placeholder="••••••"
              class="w-full bg-navy-700 border border-navy-600 focus:border-teal-500 text-ink-900 rounded-xl px-3 py-2.5 text-base text-center tracking-[0.4em] font-mono outline-none transition-colors"/>
          </div>
          <button type="submit"
            class="w-full gold-btn text-oq font-bold py-3.5 rounded-xl hover:opacity-90 transition-all flex items-center justify-center gap-2">
            <i class="fas fa-check-circle"></i> Tasdiqlash va ko'rish
          </button>
        </form>
      </div>
    `;
  }

  async function loyihaKorishTasdiqla(e) {
    e.preventDefault();
    const kod = document.getElementById('lkKod').value.trim();
    const btn = e.target.querySelector('button[type=submit]');
    btn.disabled = true; btn.innerHTML = '<i class="fas fa-spinner fa-spin mr-2"></i>Tekshirilmoqda...';
    try {
      await apiPost('/auth/otp/tasdiqlash/', { telefon: _lkTelefon, kod });
      loyihaKorishNatijalari();
    } catch (err) {
      document.getElementById('lkKod').value = '';
      document.getElementById('lkKod').focus();
      apiErr(err);
    } finally {
      btn.disabled = false; btn.innerHTML = '<i class="fas fa-check-circle mr-2"></i>Tasdiqlash va ko\'rish';
    }
  }

  function loyihaKorishNatijalari() {
    const tozalash = (s) => (s || '').replace(/[\s\-()]/g, '');
    const hammasi = JSON.parse(localStorage.getItem('soargaz_loyihalar') || '[]');
    const meniki = hammasi.filter(l => tozalash(l.telefon) === tozalash(_lkTelefon));

    const kartalar = meniki.length ? meniki.map(l => {
      const sarlavha = l.bolim === 'texnik_shart' ? 'Texnik shart bo\'limi' : 'Loyiha manzili';
      const ikonka   = l.bolim === 'texnik_shart' ? 'fa-file-contract text-gold-400' : 'fa-map-marker-alt text-cobalt-300';
      const tafsilot = l.bolim === 'texnik_shart'
        ? `ТУ raqami: <span class="text-ink-900 font-mono">${escapeHtml(l.tsRaqam)}</span>`
        : `Manzil: <span class="text-ink-900">${escapeHtml(l.tuman)}, ${escapeHtml(l.manzil)}</span>`;
      return `
        <div class="bg-navy-700 border border-navy-600 rounded-xl p-4 mb-3">
          <div class="flex items-center justify-between mb-2">
            <div class="flex items-center gap-2 text-sm font-semibold text-ink-900"><i class="fas ${ikonka}"></i> ${escapeHtml(sarlavha)}</div>
            <span class="text-xs text-gold-400 font-mono">#${String(l.id).slice(-6)}</span>
          </div>
          <div class="text-sm text-gray-300 mb-1">${tafsilot}</div>
          <div class="flex items-center justify-between text-xs text-gray-500 mt-2">
            <span>${escapeHtml(l.sana)}</span>
            <span class="text-green-400">${escapeHtml(l.holat)}</span>
          </div>
        </div>`;
    }).join('') : `<div class="text-center text-gray-400 text-sm py-8"><i class="fas fa-inbox text-2xl mb-2 block"></i>Bu raqamga tegishli arizalar topilmadi</div>`;

    document.getElementById('modalContent').innerHTML = `
      <div>
        <button data-h-click="h213" class="btn-ortga flex items-center gap-2 text-gray-400 hover:text-ink-900 text-sm mb-5 transition-colors">
          <i class="fas fa-arrow-left"></i> Bo'limlarga qaytish
        </button>
        <div class="flex items-center gap-2 text-teal-300 font-semibold mb-1">
          <i class="fas fa-folder-open"></i> Sizning loyihalaringiz
        </div>
        <p class="text-gray-400 text-xs mb-5"><span class="text-ink-900">${escapeHtml(_lkTelefon)}</span> raqamiga tegishli arizalar (${meniki.length})</p>
        ${kartalar}
      </div>
    `;
  }

  function escapeHtml(str) {
    const d = document.createElement('div');
    d.textContent = str ?? '';
    return d.innerHTML;
  }

  // ---- RUXSATNOMALAR / EKSPERTIZA / 3D MODELLASHTIRISH ----
  const ODDIY_BOLIMLAR = {
    ruxsatnomalar: {
      sarlavha: 'Ruxsatnomalar', ikon: 'fa-stamp', rang: 'cobalt',
      tavsif: "Gaz tizimini ishga tushirish uchun zarur bo'lgan rasmiy ruxsat hujjatlarini rasmiylashtirib beramiz.",
      royxat: ["Loyihani tasdiqlash uchun ruxsatnoma", "Yong'in xavfsizligi xulosasi", "Sanitariya-epidemiologik xulosa", "Ishga tushirish akti"],
    },
    ekspertiza: {
      sarlavha: 'Ekspertiza', ikon: 'fa-magnifying-glass-chart', rang: 'teal',
      tavsif: "Tayyor loyihangizni davlat ekspertizasi talablariga moslik bo'yicha tekshirib, rasmiy xulosa beramiz.",
      royxat: ["Texnik hujjatlar tahlili", "Xavfsizlik me'yorlariga moslik tekshiruvi", "Ekspertiza xulosasini rasmiylashtirish", "Kamchiliklar bo'yicha tavsiyalar"],
    },
    modellashtirish: {
      sarlavha: '3D modellashtirish', ikon: 'fa-cube', rang: 'gold',
      tavsif: "Gaz tizimingizning real ko'rinishini 3D formatda vizual modellashtirib, qurilishdan oldin ko'rib chiqish imkonini beramiz.",
      royxat: ["Bino va tarmoqlarning 3D vizualizatsiyasi", "Quvur yo'nalishlarini interaktiv ko'rish", "O'zgartirishlarni qurilishdan oldin sinab ko'rish", "Animatsion taqdimot fayli"],
    },
  };

  function loyihaOddiyBolim(kalit) {
    const b = ODDIY_BOLIMLAR[kalit];
    document.getElementById('modalContent').innerHTML = `
      <div>
        <button data-h-click="h213" class="btn-ortga flex items-center gap-2 text-gray-400 hover:text-ink-900 text-sm mb-5 transition-colors">
          <i class="fas fa-arrow-left"></i> Bo'limlarga qaytish
        </button>
        <div class="flex items-center gap-2 text-${b.rang}-300 font-semibold mb-1">
          <i class="fas ${b.ikon}"></i> ${escapeHtml(b.sarlavha)}
        </div>
        <p class="text-gray-400 text-xs mb-4">${escapeHtml(b.tavsif)}</p>
        <ul class="space-y-2 text-sm text-gray-300 mb-5">
          ${b.royxat.map(r => `<li class="flex items-start gap-2"><i class="fas fa-check text-${b.rang}-400 mt-0.5"></i>${escapeHtml(r)}</li>`).join('')}
        </ul>
        <form data-h-submit="c:loyihaOddiyAriza" data-a-submit="${SG_A(['@event', String(kalit)])}" class="space-y-3">
          <input id="obName" type="text" required placeholder="Ism-familiya"
            class="w-full bg-navy-700 border border-navy-600 focus:border-${b.rang}-500 text-ink-900 rounded-xl px-4 py-3 text-sm outline-none transition-colors"/>
          <input id="obPhone" type="tel" required placeholder="+998 90 000 00 00"
            class="w-full bg-navy-700 border border-navy-600 focus:border-${b.rang}-500 text-ink-900 rounded-xl px-4 py-3 text-sm outline-none transition-colors"/>
          <textarea id="obIzoh" rows="2" placeholder="Qo'shimcha izoh (ixtiyoriy)"
            class="w-full bg-navy-700 border border-navy-600 focus:border-${b.rang}-500 text-ink-900 rounded-xl px-4 py-3 text-sm outline-none transition-colors resize-none"></textarea>
          <button type="submit"
            class="w-full gold-btn text-oq font-bold py-3.5 rounded-xl hover:opacity-90 transition-all flex items-center justify-center gap-2">
            <i class="fas fa-paper-plane"></i> Ariza qoldirish
          </button>
        </form>
      </div>
    `;
  }

  function loyihaOddiyAriza(e, kalit) {
    e.preventDefault();
    const b = ODDIY_BOLIMLAR[kalit];
    closeModal();
    showToast(b.sarlavha + " bo'yicha arizangiz qabul qilindi! Tez orada bog'lanamiz.");
  }

  function updateFileName(input, spanId) {
    const name = input.files[0] ? input.files[0].name : 'Fayl tanlash (PDF, JPG, PNG)';
    document.getElementById(spanId).textContent = name;
  }

  function loyihaArizaNatija(data, qatorlar) {
    const saved = JSON.parse(localStorage.getItem('soargaz_loyihalar') || '[]');
    saved.push(data);
    localStorage.setItem('soargaz_loyihalar', JSON.stringify(saved));

    document.getElementById('modalContent').innerHTML = `
      <div class="text-center py-4">
        <div class="w-20 h-20 bg-green-500/20 rounded-full flex items-center justify-center mx-auto mb-5">
          <i class="fas fa-check-circle text-green-400 text-4xl"></i>
        </div>
        <h3 class="text-xl font-bold mb-2 text-green-300">Muvaffaqiyatli saqlandi!</h3>
        <p class="text-gray-400 text-sm mb-6">Arizangiz qabul qilindi. Mutaxassisimiz <strong class="text-ink-900">24 soat</strong> ichida bog'lanadi.</p>
        <div class="bg-navy-700 rounded-xl p-4 text-left text-sm space-y-2 mb-6">
          <div class="flex justify-between"><span class="text-gray-400">Ariza ID:</span><span class="text-gold-400 font-mono">#${data.id.toString().slice(-6)}</span></div>
          ${qatorlar}
          <div class="flex justify-between"><span class="text-gray-400">Holat:</span><span class="text-green-400">✓ Qabul qilindi</span></div>
        </div>
        <button data-h-click="h146" class="w-full gold-btn text-oq font-bold py-3 rounded-xl">Yopish</button>
      </div>
    `;
    showToast('Ariza #' + data.id.toString().slice(-6) + ' saqlandi!');
  }

  function saveTexnikShart(e) {
    e.preventDefault();
    const data = {
      id: Date.now(),
      sana: new Date().toLocaleString('uz-UZ'),
      bolim: 'texnik_shart',
      ism: document.getElementById('tsName').value,
      telefon: document.getElementById('tsPhone').value,
      tsRaqam: document.getElementById('tsNum').value,
      tavsif: document.getElementById('tsDesc').value,
      holat: 'Yangi'
    };
    loyihaArizaNatija(data, `
      <div class="flex justify-between"><span class="text-gray-400">Ism:</span><span class="text-ink-900">${data.ism}</span></div>
      <div class="flex justify-between"><span class="text-gray-400">ТУ raqami:</span><span class="text-ink-900 font-mono">${data.tsRaqam}</span></div>
    `);
  }

  function saveManzil(e) {
    e.preventDefault();
    const lokInp = document.getElementById('mzLokatsiya');
    const data = {
      id: Date.now(),
      sana: new Date().toLocaleString('uz-UZ'),
      bolim: 'loyiha_manzili',
      ism: document.getElementById('mzName').value,
      telefon: document.getElementById('mzPhone').value,
      viloyat: document.getElementById('mzTuman-viloyat').value,
      tuman: document.getElementById('mzTuman').value,
      mahalla: document.getElementById('mzTuman-mahalla').value.trim(),
      manzil: document.getElementById('mzAddr').value,
      manzilIzoh: document.getElementById('mzIzoh').value,
      lokatsiya: lokInp.value || '',
      lokatsiyaLat: lokInp.dataset.lat || '',
      lokatsiyaLng: lokInp.dataset.lng || '',
      yandexHavola: document.getElementById('mzYandexHavola').value,
      holat: 'Yangi'
    };
    let lokatsiyaQatori = '';
    if (data.lokatsiya) {
      lokatsiyaQatori += `<div class="flex justify-between"><span class="text-gray-400">Lokatsiya:</span><span class="text-ink-900">${escapeHtml(data.lokatsiya)}</span></div>`;
    }
    if (data.yandexHavola) {
      lokatsiyaQatori += `<div class="flex justify-between"><span class="text-gray-400">Yandex havola:</span><a href="${escapeHtml(data.yandexHavola)}" target="_blank" class="text-cobalt-300 underline truncate max-w-[180px]">${escapeHtml(data.yandexHavola)}</a></div>`;
    }
    loyihaArizaNatija(data, `
      <div class="flex justify-between"><span class="text-gray-400">Ism:</span><span class="text-ink-900">${escapeHtml(data.ism)}</span></div>
      <div class="flex justify-between"><span class="text-gray-400">Manzil:</span><span class="text-ink-900 text-right">${escapeHtml(data.tuman)}, ${escapeHtml(data.manzil)}</span></div>
      ${lokatsiyaQatori}
    `);
  }

  function closeModal() {
    document.getElementById('modal').classList.add('hidden');
    document.body.style.overflow = '';
  }

  function closeModalOutside(e) {
    if (e.target === document.getElementById('modal')) closeModal();
  }

  // Esc bosilganda eng ustidagi oyna yopiladi
  document.addEventListener('keydown', function (e) {
    if (e.key !== 'Escape') return;
    const m = document.getElementById('modal');
    if (m && !m.classList.contains('hidden')) { closeModal(); return; }
    const bo = document.getElementById('buyurtma-oyna');
    if (bo && !bo.classList.contains('hidden')) { closeBuyurtmaOyna(); return; }
    const bp = document.getElementById('balon-page');
    if (bp && !bp.classList.contains('hidden')) { closeBalonPage(); return; }
    const mp = document.getElementById('metro-page');
    if (mp && !mp.classList.contains('hidden')) { closeMetroPage(); return; }
    const rp = document.getElementById('rezervuar-page');
    if (rp && !rp.classList.contains('hidden')) { closeRezervuarPage(); return; }
    const lp = document.getElementById('lpg-page');
    if (lp && !lp.classList.contains('hidden')) { closeLpgPage(); return; }
    const bh = document.getElementById('biz-page');
    if (bh && !bh.classList.contains('hidden')) { closeBizPage(); return; }
    const np = document.getElementById('nega-page');
    if (np && !np.classList.contains('hidden')) { closeNegaPage(); return; }
    const fp = document.getElementById('faq-page');
    if (fp && !fp.classList.contains('hidden')) { closeFaqPage(); return; }
    if (tolovOchiqmi()) {
      const iv = document.getElementById('invoiceModal');
      if (iv && !iv.classList.contains('hidden')) { closeInvoice(); return; }
      const ichki = [['shartnomaDetails', closeShartnomaPage], ['onlineDetails', closeOnlinePage], ['bankDetails', closeBankPage]];
      for (const [id, yop] of ichki) {
        const el = document.getElementById(id);
        if (el && !el.classList.contains('hidden')) { yop(); return; }
      }
      closeTolovPage();
      return;
    }
    if (xaridBolimOchiqmi()) {
      const ustida = ['kat-page', 'garelka-page', 'savat-page', 'xarid-page'].some(id => {
        const el = document.getElementById(id);
        return el && !el.classList.contains('hidden');
      });
      if (!ustida) closeXaridBolim();
    }
  });

  // ---- PAYMENT SELECT ----
  function tval(id) { const e = document.getElementById(id); return e ? e.value.trim() : ''; }

  function _openOverlay(id) { document.getElementById(id).classList.remove('hidden'); document.body.style.overflow = 'hidden'; }
  function _closeOverlay(id) { document.getElementById(id).classList.add('hidden'); document.body.style.overflow = tolovOchiqmi() ? 'hidden' : ''; }

  function selectPayment(el, type) {
    document.querySelectorAll('#tolov-page .card').forEach(c => c.style.borderColor = '');
    el.style.borderColor = '#f83600';
    const pt = document.getElementById('payType');
    if (pt) pt.value = type === 'bank' ? 'Bank o\'tkazmasi' : type === 'online' ? 'Onlayn (Click/Payme)' : 'Shartnoma / Bo\'lib to\'lash';
    if (type === 'bank')       _openOverlay('bankDetails');
    else if (type === 'online') _openOverlay('onlineDetails');
    else                        _openOverlay('shartnomaDetails');
  }

  function closeBankPage()      { _closeOverlay('bankDetails'); }
  function closeOnlinePage()    { _closeOverlay('onlineDetails'); }
  function closeShartnomaPage() { _closeOverlay('shartnomaDetails'); }

  // ---- HISOB-FAKTURA OYNASI (modal) ----
  function openInvoice(turi) {
    if (turi) { const pt = document.getElementById('payType'); if (pt) pt.value = turi; }
    document.getElementById('invoiceModal').classList.remove('hidden');
    document.body.style.overflow = 'hidden';
  }
  function closeInvoice() {
    document.getElementById('invoiceModal').classList.add('hidden');
    document.body.style.overflow = tolovOchiqmi() ? 'hidden' : '';
  }

  function copyBankCard() {
    const card = '8600 1234 5678 9012';
    navigator.clipboard.writeText(card).then(
      () => showToast('Karta raqami nusxalandi: ' + card),
      () => showToast('Karta raqami: ' + card)
    );
  }

  // ---- ONLAYN TO'LOV ----
  async function onlinePay(tizimi) {
    const ism = tval('onl-ism'), tel = tval('onl-tel');
    const summa = parseInt(tval('onl-summa')) || 0;
    if (!ism || !tel) { showToast('Ism va telefon raqamini kiriting'); return; }
    if (summa < 1000) { showToast('To\'g\'ri summa kiriting (kamida 1000 so\'m)'); return; }
    try {
      const r = await apiPost('/tolovlar/sorov/', {
        tolov_turi: 'online', tolov_tizimi: tizimi,
        ism, telefon: tel, xizmat_turi: tval('onl-xizmat'), summa,
      });
      showToast('So\'rov #' + r.id + ' yaratildi. ' + tizimi.toUpperCase() + ' to\'lov sahifasiga o\'tilyapti...');
      if (r.tolov_url) setTimeout(() => { window.location.href = r.tolov_url; }, 1300);
    } catch (err) {
      showToast('Xatolik: serverga ulanib bo\'lmadi. Backend ishga tushganini tekshiring.');
    }
  }

  // ---- SHARTNOMA ARIZASI ----
  async function submitShartnoma() {
    const ism = tval('sht-ism'), tel = tval('sht-tel');
    if (!ism || !tel) { showToast('Ism va telefon raqamini kiriting'); return; }
    try {
      const r = await apiPost('/tolovlar/sorov/', {
        tolov_turi: 'shartnoma', ism, telefon: tel,
        summa: parseInt(tval('sht-summa')) || 0,
        muddat: tval('sht-muddat'), izoh: tval('sht-izoh'),
        xizmat_turi: 'Bo\'lib to\'lash',
      });
      showToast('Arizangiz #' + r.id + ' qabul qilindi! 24 soat ichida bog\'lanamiz.');
      closeShartnomaPage();
      ['sht-ism','sht-tel','sht-summa','sht-izoh'].forEach(id => { const e = document.getElementById(id); if (e) e.value = ''; });
    } catch (err) {
      showToast('Xatolik: serverga ulanib bo\'lmadi. Backend ishga tushganini tekshiring.');
    }
  }

  // ---- FORMS ----
  async function submitForm(e, type) {
    e.preventDefault();
    if (type === 'invoice') {
      const turiMap = { 'Bank o\'tkazmasi': 'bank', 'Onlayn (Click/Payme)': 'online', 'Shartnoma / Bo\'lib to\'lash': 'shartnoma' };
      const ptv = document.getElementById('payType').value;
      const turi = turiMap[ptv] || 'bank';
      const tizimi = turi === 'online' ? 'click' : '';
      try {
        const r = await apiPost('/tolovlar/sorov/', {
          tolov_turi: turi, tolov_tizimi: tizimi,
          ism: tval('inv-ism'), telefon: tval('inv-tel'),
          xizmat_turi: tval('inv-xizmat'), summa: parseInt(tval('inv-summa')) || 0,
        });
        showToast('Hisob-faktura so\'rovi #' + r.id + ' yuborildi!');
        e.target.reset();
        closeInvoice();
        if (turi === 'online' && r.tolov_url) setTimeout(() => { window.location.href = r.tolov_url; }, 1300);
      } catch (err) {
        showToast('Xatolik: serverga ulanib bo\'lmadi. Backend ishga tushganini tekshiring.');
      }
      return;
    }
    showToast('Xabaringiz yuborildi! 24 soat ichida javob beramiz.');
    e.target.reset();
  }

  // ---- TOAST ----
  let toastTimer;
  function showToast(msg) {
    clearTimeout(toastTimer);
    const t = document.getElementById('toast');
    document.getElementById('toastMsg').textContent = msg;
    t.classList.remove('hidden');
    toastTimer = setTimeout(() => t.classList.add('hidden'), 4000);
  }

  // ============================================================
  // GARELKALAR — ma'lumotlar + render + admin
  // ============================================================
  const GRL_DEFAULTS = [
    {id:1,  nom:'Uy-joy gaz garelkasi',        tavsif:"Plita va qozon uchun, po'lat korpus, kafolat 1 yil",  quvvat:'1.8 kW',   narx:85000,    kat:'Uy-joy',      mashhur:false},
    {id:2,  nom:'Uy-joy garelkasi Pro',         tavsif:'Kuchaytirilgan model, 4-konfolli plita uchun',        quvvat:'3.5 kW',   narx:125000,   kat:'Uy-joy',      mashhur:true},
    {id:3,  nom:'Sanoat garelkasi Mini',         tavsif:'Kichik qozonxona va issiqlik punktlari',             quvvat:'15 kW',    narx:380000,   kat:'Sanoat',      mashhur:false},
    {id:4,  nom:'Sanoat garelkasi Standard',     tavsif:"O'rta hajmli sanoat qozonlari uchun",               quvvat:'50 kW',    narx:650000,   kat:'Sanoat',      mashhur:true},
    {id:5,  nom:'Sanoat garelkasi Katta',        tavsif:'Sanoat qozonlari, avtomatik boshqaruv',              quvvat:'100 kW',   narx:1200000,  kat:'Sanoat',      mashhur:false},
    {id:6,  nom:'Sanoat garelkasi Ultra',        tavsif:'Yirik sanoat ob\'ektlari, modulli dizayn',           quvvat:'200 kW',   narx:2100000,  kat:'Sanoat',      mashhur:false},
    {id:7,  nom:'Infraqizil garelka I',          tavsif:'Iqtisodiy isitish, terracotta emiter',               quvvat:'3.5 kW',   narx:120000,   kat:'Infraqizil',  mashhur:false},
    {id:8,  nom:'Infraqizil garelka II',         tavsif:'Katta xonalar, 2-emiterli tizim',                    quvvat:'7 kW',     narx:195000,   kat:'Infraqizil',  mashhur:true},
    {id:9,  nom:'Portativ mini garelka',         tavsif:'Kampingda, sayrda va oshxona uchun',                 quvvat:'1.2 kW',   narx:35000,    kat:'Portativ',    mashhur:false},
    {id:10, nom:'Portativ garelka Standard',     tavsif:'Tez ulash, balon bilan ishlaydi',                    quvvat:'2.5 kW',   narx:55000,    kat:'Portativ',    mashhur:false},
    {id:11, nom:'Payvandlash garelkasi',         tavsif:"Propan-butan, qo'l rostlagich, DN15",               quvvat:'8 kW',     narx:95000,    kat:'Payvandlash', mashhur:false},
    {id:12, nom:'Payvandlash garelkasi Pro',     tavsif:'Professional, boshqaruv klapani bilan',              quvvat:'15 kW',    narx:160000,   kat:'Payvandlash', mashhur:false},
    {id:13, nom:'Duo-blok garelka S',            tavsif:'Gaz+havo aralash, avtomatik sozlash',                quvvat:'300 kW',   narx:2400000,  kat:'Duo-blok',    mashhur:false},
    {id:14, nom:'Duo-blok garelka M',            tavsif:"O'rta sanoat, modulli",                              quvvat:'500 kW',   narx:3800000,  kat:'Duo-blok',    mashhur:false},
    {id:15, nom:'Duo-blok garelka L',            tavsif:'Katta sanoat ob\'ektlari uchun',                     quvvat:'800 kW',   narx:5500000,  kat:'Duo-blok',    mashhur:false},
    {id:16, nom:'Atmosferik garelka I',          tavsif:'Tabiiy konveksiya, past bosim',                      quvvat:'20 kW',    narx:290000,   kat:'Atmosferik',  mashhur:false},
    {id:17, nom:'Atmosferik garelka II',         tavsif:'Ko\'p sekciyali, modulli tizim',                     quvvat:'35 kW',    narx:420000,   kat:'Atmosferik',  mashhur:true},
    {id:18, nom:'LPG suyultirilgan gaz garelkasi', tavsif:'Propan-butan tizimi uchun maxsus',                 quvvat:'25 kW',    narx:480000,   kat:'LPG',         mashhur:false},
    {id:19, nom:'Qozon garelkasi',               tavsif:'Uy-joy qozonxonasi, kam shovqin',                    quvvat:'60 kW',    narx:890000,   kat:'Qozon',       mashhur:true},
    {id:20, nom:'Maxsus sanoat garelkasi',       tavsif:'Yirik korxona, raqamli boshqaruv paneli',            quvvat:'1000 kW',  narx:8500000,  kat:'Sanoat',      mashhur:false},
  ];

  function grlLoadData() {
    try { return JSON.parse(localStorage.getItem('grlData')) || GRL_DEFAULTS; }
    catch(e) { return GRL_DEFAULTS; }
  }
  function grlSaveData(d) { localStorage.setItem('grlData', JSON.stringify(d)); }

  // Kategoriyaga qarab rang (gold/xrom/xaki/qoramtir)
  const GRL_KAT_STYLE = {
    'Uy-joy':      {bg:'rgba(120,170,235,0.18)',  color: '#0d6efd', border:'rgba(120,170,235,0.5)'},
    'Sanoat':      {bg:'rgba(168,184,200,0.15)', color: '#40699a', border:'rgba(168,184,200,0.45)'},
    'Infraqizil':  {bg:'rgba(139,150,96,0.18)',  color: '#5b7fa6', border:'rgba(139,150,96,0.5)'},
    'Portativ':    {bg:'rgba(120,170,235,0.12)',  color: '#7d6a20', border:'rgba(120,170,235,0.35)'},
    'Payvandlash': {bg:'rgba(140,160,168,0.15)', color: '#4a6d94', border:'rgba(140,160,168,0.4)'},
    'Duo-blok':    {bg:'rgba(200,200,192,0.12)', color: '#5b7fa6', border:'rgba(200,200,192,0.4)'},
    'Atmosferik':  {bg:'rgba(107,124,60,0.18)',  color: '#5b7fa6', border:'rgba(107,124,60,0.5)'},
    'LPG':         {bg:'rgba(96,140,120,0.18)',  color: '#2f7d9e', border:'rgba(96,140,120,0.45)'},
    'Qozon':       {bg:'rgba(168,120,60,0.18)',  color: '#0d6efd', border:'rgba(168,120,60,0.5)'},
  };
  function grlKatStyle(kat) {
    return GRL_KAT_STYLE[kat] || {bg:'rgba(120,170,235,0.15)',color: '#0d6efd',border:'rgba(120,170,235,0.4)'};
  }

  function grlRender() {
    const data = grlLoadData();
    const q = (document.getElementById('grl-search')?.value||'').toLowerCase();
    const list = q ? data.filter(g=>g.nom.toLowerCase().includes(q)||g.kat.toLowerCase().includes(q)) : data;
    const grid = document.getElementById('grl-grid');
    const empty = document.getElementById('grl-empty');
    if (!list.length) { grid.innerHTML=''; empty.classList.remove('hidden'); return; }
    empty.classList.add('hidden');
    grid.innerHTML = list.map(g => {
      const ks = grlKatStyle(g.kat);
      const narxStr = g.narx.toLocaleString('uz-UZ');
      return `
      <div class="grl-card rounded-2xl overflow-hidden flex flex-col"
        style="background:linear-gradient(160deg,#e7f1fd 0%,#f1f7ff 60%,#f2f8ff 100%);
               border:1px solid rgba(120,170,235,0.28);
               box-shadow:0 2px 12px rgba(31,72,135,0.08),inset 0 1px 0 rgba(255,220,80,0.06);
               transition:border-color .25s,box-shadow .25s,transform .25s"
        data-h-mouseover="h228"
        data-h-mouseout="h229">

        <!-- Rasm maydoni -->
        <div class="relative flex items-center justify-center overflow-hidden" style="height:176px;background:rgba(150,195,245,0.04)">

          <!-- Dekor chiziq -->
          <div class="absolute top-0 left-0 right-0 h-px" style="background:linear-gradient(to right,transparent,rgba(110,165,230,0.4),transparent)"></div>

          <!-- Kamera placeholder -->
          <div class="flex flex-col items-center gap-2 select-none" style="color:rgba(255,190,40,0.22)">
            <svg width="52" height="52" viewBox="0 0 24 24" fill="currentColor"><path d="M12 9a3 3 0 1 0 0 6 3 3 0 0 0 0-6zm0-2a5 5 0 1 1 0 10A5 5 0 0 1 12 7zm-1-4h2l1.5 2H19a1 1 0 0 1 1 1v11a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V6a1 1 0 0 1 1-1h4.5L11 3z"/></svg>
            <span style="font-size:9px;letter-spacing:.18em;font-weight:700;color:rgba(120,170,235,0.35)">RASM</span>
          </div>

          <!-- Kategoriya badge (pastki chap) -->
          <div class="absolute bottom-3 left-3 text-[9px] font-black uppercase tracking-widest px-2.5 py-1 rounded-full"
            style="background:${ks.bg};color:${ks.color};border:1px solid ${ks.border};backdrop-filter:blur(4px)">${g.kat}</div>

          <!-- Mashhur badge -->
          ${g.mashhur ? `<div class="absolute top-3 right-3 text-[9px] font-black uppercase tracking-widest px-2.5 py-1 rounded-full" style="background:linear-gradient(135deg,rgba(184,142,20,0.35),rgba(110,165,230,0.2));color:#0d6efd;border:1px solid rgba(110,165,230,0.5);backdrop-filter:blur(4px)">★ TOP</div>` : ''}

          <!-- Quvvat badge (yuqori chap) -->
          <div class="absolute top-3 left-3 text-[10px] font-black px-2.5 py-1 rounded-lg"
            style="background:rgba(0,0,0,0.65);color:#0d6efd;border:1px solid rgba(184,142,20,0.4);backdrop-filter:blur(6px);letter-spacing:.03em">${g.quvvat}</div>
        </div>

        <!-- Ajratuvchi chiziq -->
        <div style="height:1px;background:linear-gradient(to right,transparent,rgba(120,170,235,0.35),transparent)"></div>

        <!-- Info qismi -->
        <div class="flex flex-col flex-1 p-4" style="gap:0">
          <!-- Sarlavha + Ma'lumot tugmasi -->
          <div class="flex items-start justify-between gap-2 mb-1">
            <h3 class="font-black text-ink-900 leading-snug flex-1" style="font-size:14px">${g.nom}</h3>
            <button data-h-click="c:grlInfo" data-a-click="${SG_A([g.id])}"
              class="shrink-0 flex items-center gap-1 rounded-lg font-bold transition-all active:scale-95"
              style="font-size:10px;padding:3px 8px;background:rgba(120,170,235,0.1);color:#0d6efd;border:1px solid rgba(120,170,235,0.28);letter-spacing:.03em;white-space:nowrap"
              data-h-mouseover="h230"
              data-h-mouseout="h231">
              <i class="fas fa-circle-info" style="font-size:9px"></i>Ma'lumot
            </button>
          </div>
          <p class="text-xs leading-relaxed mb-4 flex-1" style="color:#6a6030">${g.tavsif}</p>

          <!-- Narx qatori -->
          <div class="flex items-center justify-between mb-2">
            <div>
              <div class="font-black leading-none" style="font-size:22px;background:linear-gradient(135deg,#0d6efd,#0d6efd);-webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text">${narxStr}</div>
              <div class="text-xs font-semibold mt-0.5" style="color:#4a4020">so'm / dona</div>
            </div>

            <!-- Soni tugmalari -->
            <div class="flex items-center rounded-xl overflow-hidden" style="background:#f1f7ff;border:1px solid rgba(120,170,235,0.35)">
              <button data-h-click="c:grlQty" data-a-click="${SG_A(['@this', -1, g.narx])}"
                class="w-9 h-9 flex items-center justify-center font-black text-base transition-colors"
                style="color:#3d7ab5;border-right:1px solid rgba(120,170,235,0.2)"
                data-h-mouseover="h232"
                data-h-mouseout="h233">−</button>
              <input type="number" value="1" min="1" max="99"
                class="grl-qty w-10 text-center font-black text-sm outline-none"
                style="background:transparent;color:#0d6efd;border:none"
                data-h-change="c:grlQtyInput" data-a-change="${SG_A(['@this', g.narx])}"/>
              <button data-h-click="c:grlQty" data-a-click="${SG_A(['@this', 1, g.narx])}"
                class="w-9 h-9 flex items-center justify-center font-black text-base transition-colors"
                style="color:#3d7ab5;border-left:1px solid rgba(120,170,235,0.2)"
                data-h-mouseover="h232"
                data-h-mouseout="h233">+</button>
            </div>
          </div>

          <!-- Jami narx -->
          <div class="text-right text-xs font-semibold mb-3 grl-total" style="color:#6a5818">Jami: ${narxStr} so'm</div>

          <!-- Savatga qo'shish -->
          <button data-h-click="c:grlOrder" data-a-click="${SG_A(['@this', g.nom, g.narx])}"
            class="w-full font-black rounded-xl text-sm active:scale-95 transition-all flex items-center justify-center gap-2"
            style="padding:11px 0;background:linear-gradient(135deg,#ff8a00 0%,#ff8a00 50%,#ff8a00 100%);
                   color:#0a0900;letter-spacing:.04em;
                   box-shadow:0 2px 8px rgba(31,72,135,0.10),inset 0 1px 0 rgba(255,255,255,0.15)"
            data-h-mouseover="h234"
            data-h-mouseout="h235">
            <i class="fas fa-cart-plus"></i>Savatga qo'shish
          </button>
        </div>
      </div>`;
    }).join('');
    // Xaridlar saytiga qaytib o'tganda "6 ta model" ni yangilaymiz
    const entryBtn = document.querySelector('[data-kat-tugma="gorelka"]');
    if (entryBtn) {
      const countEl = document.getElementById('grl-entry-count');
      if (countEl) countEl.textContent = data.length + ' ta model';
    }
  }

  // ---- Katalog narxlari backenddan (admin panel orqali o'zgartiriladi) ----
  // Django: /api/katalog/narxlar/ → {kalit: {narx, matn, birlik}}
  // Backend ishlamasa yoki fayl `file://` orqali ochilgan bo'lsa —
  // index.html dagi statik narxlar o'z holicha qoladi.
  let KAT_NARXLAR = {};

  async function katNarxlarniYukla() {
    try {
      const javob = await fetch('/api/katalog/narxlar/', { cache: 'no-store' });
      if (!javob.ok) return;
      KAT_NARXLAR = await javob.json();
      katNarxlarniQolla();
    } catch (e) {
      // Backend o'chiq — statik narxlar bilan ishlayveramiz
    }
  }

  // Narxi hozircha ko'rsatilmaydigan bo'limlar: narx kiritilguncha "tez orada" yoziladi.
  // Narxlarni qaytarish uchun bo'lim nomini shu ro'yxatdan olib tashlash kifoya.
  const KAT_NARX_TEZ_ORADA = ['gorelka'];
  function katNarxYopiqmi(item) {
    return KAT_NARX_TEZ_ORADA.some(k => KAT_DATA[k] && KAT_DATA[k].items.includes(item));
  }

  // Mahsulot narxi raqam ko'rinishida (savat va hisob-kitob uchun).
  // Backenddagi aniq qiymat ustun; bo'lmasa matndan raqamlar ajratiladi.
  // "So'rovnoma" bo'lsa 0 qaytadi.
  function katNarxRaqam(item) {
    if (katNarxYopiqmi(item)) return 0;
    const backend = item && item.kalit && KAT_NARXLAR[item.kalit];
    if (backend && typeof backend.narx === 'number') return backend.narx;
    const raqamlar = String((item && item.narx) || '').replace(/\s/g, '').match(/\d+/);
    return raqamlar ? parseInt(raqamlar[0], 10) : 0;
  }

  // Savatdagi mahsulot nomidan katalog kalitini topadi (serverga narx o'rniga kalit yuboriladi)
  function katKalitTop(nom) {
    for (const k of Object.values(KAT_DATA)) {
      const it = k.items.find(x => x.nom === nom);
      if (it) return it.kalit || '';
    }
    return '';
  }

  function katNarxlarniQolla() {
    Object.values(KAT_DATA).forEach(kategoriya => {
      kategoriya.items.forEach(item => {
        const yangi = item.kalit && KAT_NARXLAR[item.kalit];
        if (!yangi) return;
        item.narx = yangi.matn;
        if (yangi.birlik) item.birlik = yangi.birlik;
      });
    });
    if (currentKat) katRender();          // katalog ochiq bo'lsa — darhol yangilaymiz
  }

  document.addEventListener('DOMContentLoaded', katNarxlarniYukla);

  // ---- Katalog mediasi backenddan (admin panel orqali yuklanadi) ----
  // Django: /api/katalog/media/ → {kalit: {bolim, rasm: [...]}}
  // Admin panelda rasm/video yuklansa — quyidagi ro'yxat shu yerdagi statik
  // `rasm` massivining O'RNIGA qo'yiladi (admin — yagona haqiqat manbai).
  // Backend o'chiq bo'lsa yoki mahsulotga media yuklanmagan bo'lsa —
  // index.html dagi statik yo'llar o'z holicha qolaveradi.
  async function katMedianiYukla() {
    try {
      const javob = await fetch('/api/katalog/media/', { cache: 'no-store' });
      if (!javob.ok) return;
      const media = await javob.json();
      let ozgardi = false;

      Object.entries(KAT_DATA).forEach(([bolim, kategoriya]) => {
        kategoriya.items.forEach(item => {
          const yangi = item.kalit && media[item.kalit];
          if (!yangi || !yangi.rasm || !yangi.rasm.length) return;
          // Admin boshqa bo'limni ko'rsatgan bo'lsa — ogohlantiramiz, lekin
          // mediani baribir qo'llaymiz (mahsulot ikki bo'limda bo'lishi mumkin).
          if (yangi.bolim && yangi.bolim !== bolim) {
            console.warn(`[katalog] «${item.kalit}» admin panelda «${yangi.bolim}» `
                       + `bo'limiga biriktirilgan, saytda esa «${bolim}» da turibdi.`);
          }
          item.rasm = yangi.rasm;
          ozgardi = true;
        });
      });

      if (ozgardi && currentKat) katRender();
    } catch (e) {
      // Backend o'chiq — statik rasmlar bilan ishlayveramiz
    }
  }

  document.addEventListener('DOMContentLoaded', katMedianiYukla);

  // Bosh sahifadagi "N ta model" yozuvi ro'yxatdan o'zi hisoblanadi (qo'lda yangilash shart emas)
  document.addEventListener('DOMContentLoaded', () => {
    const el = document.getElementById('grl-entry-count');
    if (el && KAT_DATA.gorelka) el.textContent = KAT_DATA.gorelka.items.length + ' ta model';
  });

  // ---- Ikkita katalogda ko'rinadigan mahsulotlar ----
  // Regulyator va klapanlar ham «Jihozlar», ham «Ventillar» katalogiga kiradi.
  // Ma'lumot shu yerda bir marta yoziladi, ikkala ro'yxat shu obyektga havola qiladi —
  // narx yoki tavsifni o'zgartirsangiz, ikkala bo'limda ham yangilanadi.
  const M_RDSK50 = {nom:'Bosim regulyatori RDSK-50', kalit:'rdsk-50-regulyator', rasm:['images/jihozlar/rdsk-50-1.jpg','images/jihozlar/rdsk-50-2.png','images/jihozlar/rdsk-50-video.mp4'], tavsif:'Kirish bosimini barqaror chiqish bosimiga tushiruvchi regulyator. Bronza korpus, aniq sozlash va ishonchli ishlash.', narx:'So\'rovnoma', birlik:'dona', qollanish:'GRP/GRU, uy-joy va kichik obyektlar', xus:[['Standart','GOST R 54820'],['Kirish bosimi','1.2 MPa (maks)'],['Chiqish bosimi','0.3 MPa'],['O\'tkazuvchanlik','50 m³/soat'],['Korpus material','Bronza'],['Sozlanish','Prujinali'],['Kafolat','3 yil']]};

  const M_QOP400A = {nom:'Gaz bosim regulyatori QOP-400A', kalit:'qop-400a-regulyator', rasm:['images/jihozlar/qop-400a-1.jpg','images/jihozlar/qop-400a-2.jpg','images/jihozlar/qop-400a-video.mp4'], tavsif:'Membranali gaz yetkazib berish regulyatori. Kirish bosimi qanday o\'zgarmasin, chiqishda barqaror bosimni ushlab turadi: bosimni sezuvchi membrana balanslashgan klapanni boshqaradi, prujina esa kerakli darajaga sozlanadi.', narx:'So\'rovnoma', birlik:'dona', qollanish:'GRP/GRU tugunlari, qozonxona va sanoat obyektlariga gaz uzatish liniyalari', belgi:'0.4–5 bar', eslatma:'Regulyator <b>chiqish bosimiga qarab</b> tanlanadi — jihozingiz talab qiladigan ishchi bosimni oldindan aniqlang. O\'rnatishda gaz oqimi yo\'nalishi (korpusdagi strelka) va rezba o\'lchami mos kelishi shart. Regulyatordan <b>oldin filtr</b> o\'rnatilishi tavsiya etiladi — mexanik zarrachalar membrana va klapan o\'rindig\'ini ishdan chiqaradi.', xus:[['Model','QOP-400A'],['Turi','Membranali, to\'g\'ridan-to\'g\'ri ta\'sirli'],['Gaz turi','Tabiiy gaz'],['Chiqish bosimi','0.4–5 bar (sozlanadigan)'],['Sozlash','Prujinali vint'],['Klapan','Balanslashgan (balanced poppet)'],['Qo\'shimcha','Nolinchi bosim klapani (ixtiyoriy rejim)'],['Ventilyatsiya','H-shaklidagi shtuserlar (2 dona)'],['Korpus material','Alyuminiy quyma'],['Ulanish','Rezbali (ichki)'],['Kafolat','2 yil']]};

  const M_GRAFF = {nom:'Elektroklapan GRAFF G¾" (DN20)', kalit:'graff-elektroklapan-dn20', rasm:['images/jihozlar/graff-klapan-1.jpg','images/jihozlar/graff-klapan-2.jpg','images/jihozlar/graff-klapan-3.jpg','images/jihozlar/graff-klapan-video.mp4'], tavsif:'Gaz liniyasini avtomatik to\'suvchi elektromagnit klapan. Gaz sizib chiqish sensori bilan birga ishlaydi: xavf aniqlanganda sensordan signal keladi va klapan gaz oqimini bir zumda to\'sadi. Qayta ochish qo\'lda — ustidagi qizil tugma orqali.', narx:'So\'rovnoma', birlik:'dona', qollanish:'Oshxona, qozonxona va sanoat xonalarida avtomatik gaz to\'sish tizimi', belgi:'DC 9V', eslatma:'Klapan <b>gaz sizib chiqish sensori bilan juftlab</b> o\'rnatiladi — yolg\'iz o\'zi xavfni aniqlamaydi. O\'rnatishda korpusdagi <b>oqim yo\'nalishi strelkasiga</b> qat\'iy rioya qiling, teskari o\'rnatilsa klapan ishlamaydi. Rezba o\'lchami G¾" (DN20) — liniyangiz diametriga mos kelishini tekshiring.', xus:[['Brend','GRAFF'],['Turi','Elektromagnit klapan (elektroklapan)'],['O\'lcham','G¾" (DN20)'],['Ish bosimi','100 kPa'],['Kuchlanish','DC 9V'],['Ochish','Qo\'lda (qizil tugma)'],['Yopish','Sensordan signal bo\'yicha avtomatik'],['Oqim yo\'nalishi','Korpusdagi strelka bo\'yicha'],['Korpus material','Latun / alyuminiy'],['Kafolat','1 yil']]};

  // ---- UNIVERSAL KATALOG SAHIFASI ----
  const KAT_DATA = {
    quvur: {
      title: 'Gaz Quvurlari Katalogi',
      label: 'Quvurlar',
      desc: 'Polietilen, po\'lat va mis gaz quvurlari — yerosti va ustki montaj uchun barcha o\'lchamlar',
      color: '#0d6efd',
      bg: 'rgba(60,140,225,0.12)',
      border:'rgba(60,140,225,0.35)',
      icon: 'fa-grip-lines',
      iconBg: 'linear-gradient(135deg,#1d4ed8,#3b82f6)',
      pageBg: '#f2f6fc',
      items: [
        {nom:'Polietilen quvur PE-100 (63mm)',  rasm:['images/quvurlar/pe100-63.jpg','images/quvurlar/pe100-63-2.jpg'], tavsif:'SDR11 seriyali yuqori zichlikdagi polietilen quvur. Yerosti gaz taqsimlash tarmoqlari uchun mo\'ljallangan, korroziyaga chidamli va uzoq muddat xizmat qiladi.', narx:'So\'rovnoma', birlik:'m/p', qollanish:'Yerosti gaz taqsimlash tarmoqlari, pastki bosimli magistrallar', xus:[['Standart','GOST R 50838'],['Material','PE-100 polietilen'],['Diametr','63 mm'],['Devor qalinligi','5.8 mm (SDR11)'],['Ishchi bosim','10 bar'],['Kafolat','50 yil'],['Ishlab chiqaruvchi','Kazanorgsintez']]},
        {nom:'Polietilen quvur PE-100 (110mm)', tavsif:'O\'rta magistral tarmoqlar uchun SDR11 polietilen quvur. Payvandlash orqali germetik ulanadi, mexanik zarbalarga chidamli.', narx:'So\'rovnoma', birlik:'m/p', qollanish:'O\'rta magistral gaz tarmoqlari', xus:[['Standart','GOST R 50838'],['Material','PE-100 polietilen'],['Diametr','110 mm'],['Devor qalinligi','10 mm (SDR11)'],['Ishchi bosim','10 bar'],['Kafolat','50 yil'],['Ishlab chiqaruvchi','Kazanorgsintez']]},
        {nom:'Polietilen quvur PE-100 (160mm)', tavsif:'Asosiy magistrallar uchun katta diametrli SDR11 quvur. Yuqori o\'tkazuvchanlik va bardoshlilikni ta\'minlaydi.', narx:'So\'rovnoma', birlik:'m/p', qollanish:'Asosiy magistral gaz quvurlari', xus:[['Standart','GOST R 50838'],['Material','PE-100 polietilen'],['Diametr','160 mm'],['Devor qalinligi','14.6 mm (SDR11)'],['Ishchi bosim','10 bar'],['Kafolat','50 yil'],['Ishlab chiqaruvchi','Kazanorgsintez']]},
        {nom:'Po\'lat quvur 57×3.5',            tavsif:'GOST 3262 bo\'yicha payvandlanadigan po\'lat quvur. Yuqori bosimli magistrallar va ustki montaj uchun, sertifikatlangan.', narx:'So\'rovnoma', birlik:'m/p', qollanish:'Ustki montaj, yuqori bosimli tarmoqlar', xus:[['Standart','GOST 3262'],['Material','St3 po\'lat'],['Tashqi diametr','57 mm'],['Devor qalinligi','3.5 mm'],['Ishchi bosim','16 bar'],['Qoplama','Rux/bo\'yoq'],['Kafolat','15 yil']]},
        {nom:'Po\'lat quvur 89×4',              tavsif:'Sanoat gaz tarmoqlari uchun issiq deformatsiyalangan po\'lat quvur (GOST 8732). Yuqori mustahkamlik va bosimga chidamlilik.', narx:'So\'rovnoma', birlik:'m/p', qollanish:'Sanoat obyektlari, magistral tarmoqlar', xus:[['Standart','GOST 8732'],['Material','St20 po\'lat'],['Tashqi diametr','89 mm'],['Devor qalinligi','4 mm'],['Ishchi bosim','25 bar'],['Qoplama','Antikorroziya'],['Kafolat','15 yil']]},
        {nom:'Po\'lat quvur 108×5',             tavsif:'Katta magistrallar uchun yuqori bosimli po\'lat quvur (GOST 10705). Yirik sanoat loyihalarida qo\'llaniladi.', narx:'So\'rovnoma', birlik:'m/p', qollanish:'Yirik magistrallar, sanoat zavodlari', xus:[['Standart','GOST 10705'],['Material','St20 po\'lat'],['Tashqi diametr','108 mm'],['Devor qalinligi','5 mm'],['Ishchi bosim','25 bar'],['Qoplama','Antikorroziya'],['Kafolat','15 yil']]},
        {nom:'HDPE quvur 32mm',                 tavsif:'Ichki o\'rnatish va past bosimli tarmoqlar uchun yengil HDPE quvur (SDR17). Egiluvchan va o\'rnatish oson.', narx:'So\'rovnoma', birlik:'m/p', qollanish:'Ichki o\'rnatish, past bosimli ulanishlar', xus:[['Standart','GOST R 50838'],['Material','HDPE polietilen'],['Diametr','32 mm'],['Devor qalinligi','2.0 mm (SDR17)'],['Ishchi bosim','6 bar'],['Kafolat','40 yil'],['Ishlab chiqaruvchi','Local/Import']]},
        {nom:'Mis quvur 22mm',                  tavsif:'Uy-ichki gaz o\'tkazgichlari uchun yumshoq mis quvur (EN 1057). Estetik, korroziyaga chidamli va uzoq muddatli.', narx:'So\'rovnoma', birlik:'m/p', qollanish:'Uy-ichki gaz liniyalari, ko\'rinadigan montaj', xus:[['Standart','EN 1057'],['Material','Cu-DHP mis'],['Diametr','22 mm'],['Devor qalinligi','1.0 mm'],['Ishchi bosim','16 bar'],['Kafolat','30 yil'],['Ishlab chiqaruvchi','Wieland/KME']]},
      ]
    },
    hisob: {
      title: 'Gaz Hisoblagichlari Katalogi',
      label: 'Hisoblagichlar',
      desc: 'Uy-joy va sanoat uchun smart ultratovushli gaz hisoblagichlari',
      color: '#3f5fc0',
      bg: 'rgba(90,150,235,0.12)',
      border:'rgba(90,150,235,0.35)',
      icon: 'fa-tachometer-alt',
      iconBg: 'linear-gradient(135deg,#6d28d9,#8b5cf6)',
      pageBg: '#f5f2fd',
      items: [
        {nom:'Ultratovushli smart hisoblagich SMART GM G6', kalit:'smart-gm-g6', rasm:['images/jihozlar/smart-gm-g6-1.jpg','images/jihozlar/smart-gm-g6-2.jpg','images/jihozlar/smart-gm-g6-3.jpg','images/jihozlar/smart-gm-g6-4.jpg'], tavsif:'GTI ishlab chiqargan, O\'zbekistonda yig\'ilgan ultratovushli gaz hisoblagichi. Gaz oqimi o\'lchash kanalida ikki ultratovush datchigi orasidan o\'tadi, signal elektron modulda qayta ishlanadi — harakatlanuvchi mexanik qismlar yo\'q. Natija suyuq kristalli displeyda ko\'rinadi, korpusdagi ikki tugma bilan ko\'rsatkichlar almashtiriladi. Ichiga o\'rnatilgan klapan (Valve) bor, ximoya darajasi IP65, portlashdan himoyalangan bajarilish (Ex ib IIB T3 Gb). O\'lchash diapazoni keng: 0,06 dan 10 m³/soatgacha.', narx:'So\'rovnoma', birlik:'dona', qollanish:'Kvartira, xususiy uy, kichik savdo va xizmat obyektlari', belgi:'Ultratovushli', xus:[['Ishlab chiqaruvchi','GTI (O\'zbekistonda ishlab chiqarilgan)'],['O\'lchov turi','Ultratovush'],['Sinfi','G6'],['Qmax / Qt / Qmin','10 / 0,6 / 0,06 m³/soat'],['Maks. bosim','50 kPa'],['Ish va gaz harorati','−30…+55 °C'],['Aniqlik klassi','1.5'],['Iqlim / EMS sinfi','M2 / E2'],['Impuls qiymati','5 L/imp'],['Klapan','O\'rnatilgan (Valve)'],['Himoya darajasi','IP65'],['Portlashdan himoya','Ex ib IIB T3 Gb'],['Displey','LCD, 2 ta boshqaruv tugmasi']]},
        {nom:'Ultratovushli smart hisoblagich SMART GM G10', kalit:'smart-gm-g10', rasm:['images/jihozlar/smart-gm-g10-1.jpg','images/jihozlar/smart-gm-g10-2.jpg','images/jihozlar/smart-gm-g10-3.jpg','images/jihozlar/smart-gm-g10-4.jpg'], tavsif:'GTI ishlab chiqargan, O\'zbekistonda yig\'ilgan ultratovushli gaz hisoblagichi. Gaz oqimi o\'lchash kanalida ikki ultratovush datchigi orasidan o\'tadi, signal elektron modulda qayta ishlanadi — harakatlanuvchi mexanik qismlar yo\'q. Natija suyuq kristalli displeyda ko\'rinadi, korpusdagi ikki tugma bilan ko\'rsatkichlar almashtiriladi. Ichiga o\'rnatilgan klapan (Valve) bor, ximoya darajasi IP65, portlashdan himoyalangan bajarilish (Ex ib IIB T3 Gb). O\'lchash diapazoni keng: 0,1 dan 16 m³/soatgacha.', narx:'So\'rovnoma', birlik:'dona', qollanish:'Katta uylar, restoran, do\'kon va kichik korxonalar', belgi:'Ultratovushli', xus:[['Ishlab chiqaruvchi','GTI (O\'zbekistonda ishlab chiqarilgan)'],['O\'lchov turi','Ultratovush'],['Sinfi','G10'],['Qmax / Qt / Qmin','16 / 1,0 / 0,1 m³/soat'],['Maks. bosim','50 kPa'],['Ish va gaz harorati','−30…+55 °C'],['Aniqlik klassi','1.5'],['Iqlim / EMS sinfi','M2 / E2'],['Impuls qiymati','5 L/imp'],['Klapan','O\'rnatilgan (Valve)'],['Himoya darajasi','IP65'],['Portlashdan himoya','Ex ib IIB T3 Gb'],['Displey','LCD, 2 ta boshqaruv tugmasi']]},
        {nom:'Gaz hisoblagich G4',              kalit:'hisoblagich-g4', rasm:['images/jihozlar/hisoblagich-g4-1.jpg','images/jihozlar/hisoblagich-g4-2.jpg','images/jihozlar/hisoblagich-g4-3.jpg','images/jihozlar/hisoblagich-g4-4.jpg'], tavsif:'Uy-joy uchun membranasimon gaz hisoblagich. Aniq o\'lchov, oson o\'rnatish va uzoq muddatli barqaror ishlash. Davlat reyestriga kiritilgan.', narx:'So\'rovnoma', birlik:'dona', qollanish:'Kvartira va xususiy uylar', xus:[['Standart','GOST 8.324 / O\'zStandart'],['O\'lchov turi','Membranasimon'],['Maks. sarf','4 m³/soat'],['Ulanish','G1¼"'],['Ishchi bosim','0.5 bar'],['Aniqlik klassi','1.5'],['Kafolat','2 yil']]},
        {nom:'Ultratovush hisoblagich G25',     tavsif:'Ultratovushli yuqori aniqlikdagi hisoblagich telemetrik uzatish bilan. Harakatlanuvchi qismlarsiz, minimal xizmat talab qiladi.', narx:'So\'rovnoma', birlik:'dona', qollanish:'Kommersiya va sanoat, masofaviy nazorat', xus:[['Standart','OIML R137'],['O\'lchov turi','Ultratovush'],['Sarf diapazoni','25–250 m³/soat'],['Ulanish','DN80 flanets'],['Interfeys','Telemetriya/RS-485'],['Aniqlik klassi','1.0'],['Kafolat','3 yil']]},
        {nom:'Ultratovush hisoblagich G40',     tavsif:'Sanoat uchun keng diapazonli ultratovushli hisoblagich IoT interfeysi bilan. Real vaqtli monitoring imkoniyati.', narx:'So\'rovnoma', birlik:'dona', qollanish:'Yirik sanoat, SCADA tizimlari', xus:[['Standart','OIML R137'],['O\'lchov turi','Ultratovush'],['Sarf diapazoni','40–400 m³/soat'],['Ulanish','DN100 flanets'],['Interfeys','IoT / Modbus'],['Aniqlik klassi','1.0'],['Kafolat','3 yil']]},
      ]
    },
    ventil: {
      title: 'Ventillar va Kranlar Katalogi',
      label: 'Ventillar',
      desc: 'Shar kranlar, klapanlar, regulyatorlar, filtrlar, sensorlar va o\'lchov asboblari',
      color: '#1a6f9e',
      bg: 'rgba(70,160,230,0.12)',
      border:'rgba(70,160,230,0.35)',
      icon: 'fa-faucet',
      iconBg: 'linear-gradient(135deg,#0e7490,#06b6d4)',
      pageBg: '#f0f9fb',
      items: [
        // Jihozlar katalogi bilan umumiy — ta'rifi yuqorida, M_* o'zgaruvchilarida
        M_GRAFF,
        M_RDSK50,
        M_QOP400A,
        {nom:'ГАЛЛОП latun shar kran (ichki rezbali)', kalit:'gallop-shar-kran', rasm:['images/jihozlar/gallop-shar-kran-1.jpg','images/jihozlar/gallop-shar-kran-2.jpg','images/jihozlar/gallop-shar-kran-3.jpg'], tavsif:'ГАЛЛОП brendi latun korpusli qo\'lda boshqariladigan shar kran. Ikki tomoni ichki rezbali (mufta-mufta), qizil richagida ON/OFF yo\'nalish strelkalari bor — chorak burilishda to\'liq ochib-yopiladi.', narx:'So\'rovnoma', birlik:'dona', qollanish:'Uy-ichki va ichki obyekt liniyalari, jihoz oldidagi to\'siq', eslatma:'O\'lcham (DN) rasmdan aniqlanmadi — kerakli diametrni buyurtma berishda ko\'rsating.', xus:[['Brend','ГАЛЛОП'],['Turi','Shar kran (ball valve)'],['Korpus material','Latun'],['Ulash','Ikki tomoni ichki rezba (mufta-mufta)'],['Boshqaruv','Qo\'lda, richag (chorak burilish)'],['Nominal diametr','Aniqlanmadi — so\'rovnoma bo\'yicha']]},
        {nom:'Shar tiqinli kran DN15',       tavsif:'Ichki rezbali po\'lat korpusli shar kran. Teflon zichlovchi bilan germetiklikni ta\'minlaydi, tez ochib-yopiladi.', narx:'So\'rovnoma', birlik:'dona', qollanish:'Uy-ichki gaz liniyalari, jihoz oldidagi to\'siq', xus:[['Standart','GOST 21345'],['Nominal diametr','DN15 (½")'],['Bosim klassi','PN40'],['Korpus material','Uglerodli po\'lat'],['Zichlovchi','PTFE (teflon)'],['Boshqaruv','Qo\'lda (richag)'],['Kafolat','5 yil']]},
        {nom:'Shar tiqinli kran DN25',          tavsif:'Flanetsli ulanishli shar kran bronza o\'q bilan. O\'rta bosimli tarmoqlarda ishonchli to\'siq vazifasini bajaradi.', narx:'So\'rovnoma', birlik:'dona', qollanish:'O\'rta bosimli tarmoqlar, taqsimlash punktlari', xus:[['Standart','GOST 21345'],['Nominal diametr','DN25 (1")'],['Bosim klassi','PN40'],['Korpus material','Po\'lat + bronza o\'q'],['Zichlovchi','PTFE'],['Boshqaruv','Qo\'lda (richag)'],['Kafolat','5 yil']]},
        {nom:'Shar tiqinli kran DN50',          tavsif:'40 bargacha bosimga chidamli sertifikatlangan shar kran. Kauchuk zichlovchi va bardoshli korpus bilan.', narx:'So\'rovnoma', birlik:'dona', qollanish:'Magistral va taqsimlash tarmoqlari', xus:[['Standart','GOST 21345'],['Nominal diametr','DN50 (2")'],['Bosim klassi','PN40 (40 bar)'],['Korpus material','Uglerodli po\'lat'],['Zichlovchi','Kauchuk + PTFE'],['Boshqaruv','Qo\'lda (richag)'],['Kafolat','5 yil']]},
        {nom:'Shar tiqinli kran DN80',          tavsif:'Sanoat obyektlari uchun flanetsli katta o\'lchamli shar kran (PN16). Yuqori o\'tkazuvchanlik.', narx:'So\'rovnoma', birlik:'dona', qollanish:'Sanoat magistrallar, yirik obyektlar', xus:[['Standart','GOST 21345'],['Nominal diametr','DN80 (3")'],['Bosim klassi','PN16'],['Korpus material','Uglerodli po\'lat'],['Ulash','Flanets'],['Boshqaruv','Qo\'lda / reduktor'],['Kafolat','5 yil']]},
        {nom:'Elektromagnit klapan DN25',       tavsif:'220V bilan ishlaydigan avtomatik to\'sish klapani. Xavfsizlik tizimlarida gaz oqimini bir zumda uzadi.', narx:'So\'rovnoma', birlik:'dona', qollanish:'Avtomatik xavfsizlik tizimlari, signalizatsiya bilan', xus:[['Standart','GOST 12.2.063'],['Nominal diametr','DN25'],['Kuchlanish','220V AC'],['Turi','Normally Closed (NC)'],['Ishchi bosim','PN16'],['Ishga tushish','< 1 soniya'],['Kafolat','2 yil']]},
        {nom:'Qaytarilmaydigan klapan DN50',    tavsif:'Gazning orqaga qaytishini oldini oluvchi po\'lat klapan. Tizim xavfsizligini oshiradi.', narx:'So\'rovnoma', birlik:'dona', qollanish:'Nasos va kompressor chiqishlari, magistrallar', xus:[['Standart','GOST 27477'],['Nominal diametr','DN50'],['Bosim klassi','PN16'],['Korpus material','Po\'lat'],['Turi','Ko\'tariladigan tarelka'],['Ish holati','Gorizontal/vertikal'],['Kafolat','3 yil']]},
        {nom:'Xavfsizlik klapani (SPPK)',       tavsif:'Ortiqcha bosimda avtomatik ochiluvchi predoxranitel klapan. Tizimni bosim oshib ketishidan himoya qiladi.', narx:'So\'rovnoma', birlik:'dona', qollanish:'GRP/GRU, qozonxonalar, bosim tugunlari', xus:[['Standart','GOST 12.2.085'],['Turi','Prujinali (SPPK)'],['Sozlanish','0.05–1.6 MPa'],['Bosim klassi','PN16'],['Korpus material','Po\'lat/cho\'yan'],['Ochilish','Avtomatik'],['Kafolat','3 yil']]},
        {nom:'Gaz to\'suvchi klapan',          tavsif:'Gaz sizib chiqishi yoki bosim buzilishida avtomatik to\'suvchi sezgir klapan. Fojiali holatlarning oldini oladi.', narx:'So\'rovnoma', birlik:'dona', qollanish:'Uy-joy va sanoat xavfsizlik tugunlari', xus:[['Standart','GOST R 54960'],['Turi','Bosim/oqim sezgir'],['Ishga tushish','Bosim chegarasi buzilganda'],['Ishchi bosim','PN16'],['Korpus material','Po\'lat'],['Qayta tiklash','Qo\'lda'],['Kafolat','2 yil']]},
        {nom:'Gaz filtratori FGO-50',           tavsif:'Gazni mexanik zarrachalardan tozalovchi filtr. Regulyator va hisoblagichlarni himoya qiladi, xizmat muddatini uzaytiradi.', narx:'So\'rovnoma', birlik:'dona', qollanish:'Regulyator va hisoblagich oldida', xus:[['Standart','GOST R 54808'],['Nominal diametr','DN50'],['Filtrlash darajasi','40 mkm'],['Bosim klassi','PN16'],['Korpus material','Po\'lat'],['Element','To\'r/kaset'],['Kafolat','2 yil']]},
        {nom:'Gaz filtri SANITAS 1¼" (Y-shaklidagi)', kalit:'sanitas-filtr-1-4', rasm:['images/jihozlar/sanitas-filtr-1.jpg','images/jihozlar/sanitas-filtr-2.jpg'], tavsif:'Latun korpusli Y-shaklidagi mexanik filtr. Gaz oqimidagi qum, qirindi va zang zarrachalarini ushlab qoladi — shu orqali regulyator membranasi, hisoblagich va klapan o\'rindig\'ini ishdan chiqishdan saqlaydi. Qiya joylashgan filtr stakani yechib olinadi, ichidagi po\'lat to\'r tozalanib qayta ishlatiladi.', narx:'So\'rovnoma', birlik:'dona', qollanish:'Regulyator, hisoblagich va gaz jihozlari oldidagi tozalash tuguni', belgi:'1¼"', eslatma:'Filtr <b>regulyator va hisoblagichdan OLDIN</b> o\'rnatiladi — keyin qo\'yilsa vazifasini bajarmaydi. Korpusdagi <b>oqim yo\'nalishi</b>ga rioya qiling. Filtr stakani <b>pastga yoki yon tomonga</b> qaragan holda o\'rnatilsin — yuqoriga qaratilsa ushlangan zarrachalar tozalashda quvurga qaytib tushadi. Xizmat ko\'rsatishda to\'rni yechib olish uchun stakan atrofida bo\'sh joy qoldiring.', xus:[['Brend','SANITAS'],['Turi','Y-shaklidagi mexanik filtr (setkali)'],['O\'lcham','1¼" (DN32)'],['Ulanish','Rezbali, ichki (ikki tomon)'],['Korpus material','Latun'],['Filtr elementi','Po\'lat to\'r (yechib olinadi)'],['Xizmat','Tozalanadi, qayta ishlatiladi'],['Kafolat','2 yil']]},
        {nom:'Gaz sizib chiqish sensori',       tavsif:'Metan (CH4) konsentratsiyasini o\'lchovchi datchik. Xavfli darajaga yetganda ovozli va yorug\'lik signali beradi.', narx:'So\'rovnoma', birlik:'dona', qollanish:'Oshxona, qozonxona, sanoat xonalari', xus:[['O\'lchanadigan gaz','CH4 (metan)'],['Diapazon','0–100% LEL'],['Signal','Ovozli + LED'],['Kuchlanish','220V / 12V'],['Chiqish','Rele (klapanga)'],['O\'rnatish','Devorga'],['Kafolat','2 yil']]},
        {nom:'Gaz indikatori «Smart Gas Guardian»', kalit:'gaz-indikatori-smart', rasm:['images/jihozlar/gaz-indikatori-1.jpg','images/jihozlar/gaz-indikatori-2.jpg','images/jihozlar/gaz-indikatori-video.mp4'], tavsif:'Xonadagi gaz sizib chiqishini uzluksiz kuzatib boruvchi indikator. Korpus yon tomonidagi tirqishlardan havo namunasi sensor massiviga o\'tadi, signal kuchaytirgich orqali mikrokontrollerga uzatiladi. Konsentratsiya xavfli darajaga yetganda ichki sirena ishga tushadi, LED indikatorlar holatni ko\'rsatadi va rele chiqishi orqali tashqi elektroklapanga buyruq beriladi. Kompakt oq korpus — oshxona interyeriga bilinmay qo\'shiladi.', narx:'So\'rovnoma', birlik:'dona', qollanish:'Oshxona, qozonxona va gaz jihozlari o\'rnatilgan turar-joy xonalari', belgi:'Klapan chiqishi', eslatma:'Indikatorning o\'zi gazni <b>to\'smaydi</b> — u sizishni aniqlaydi va <b>klapan boshqarish chiqishi</b> orqali buyruq beradi. Gaz oqimi avtomatik uzilishi uchun alohida <b>elektroklapan</b> kerak (katalogdagi GRAFF G¾" modeliga qarang). O\'rnatish balandligi gaz turiga bog\'liq: tabiiy gaz (metan) havodan yengil — indikator <b>shift yaqiniga</b>, suyultirilgan gaz (propan-butan) og\'ir — <b>polga yaqin</b> o\'rnatiladi. Korpus yonidagi <b>havo tirqishlarini</b> mebel yoki parda bilan to\'sib qo\'ymang.', xus:[['Turi','Gaz sizishi indikatori (signalizator)'],['Sezgir element','Gaz sensori massivi + signal kuchaytirgich'],['Boshqaruv','Mikrokontroller (MCU)'],['Ovozli signal','Ichki trevoga sirenasi'],['Holat ko\'rsatkichi','2 ta LED (MCU boshqaruvida)'],['Klapan chiqishi','Rele drayveri orqali — elektroklapanga'],['Quvvat','Tarmoqdan, AC-DC almashtirgich (shnur bilan)'],['Korpus','Plastik, yon tomonda havo tirqishlari']]},
        {nom:'МАНОКИП МП3-У manometr (0–4 kgf/sm²) uch yo\'lli kran bilan', kalit:'manokip-mp3u-manometr', rasm:['images/jihozlar/manokip-mp3u-manometr-1.jpg','images/jihozlar/manokip-mp3u-manometr-2.jpg'], tavsif:'МАНОКИП МП3-У rusumli oq siferblatli bosim o\'lchagich, latun uch yo\'lli sinov krani (jo\'mrak) bilan yaxlit blok holida. Siferblat 0–4 kgf/sm² shkalasi, qora korpus, IP40 himoya darajasi. Uch yo\'lli kran manometrni tizimdan uzish va sinovdan o\'tkazish imkonini beradi.', narx:'So\'rovnoma', birlik:'dona', qollanish:'GRP, regulyator va bosim tugunlarida bosim nazorati', eslatma:'Siferblat diametri va ulanish rezbasi rasmdan aniqlanmadi — buyurtmada aniqlashtiring.', xus:[['Brend','МАНОКИП'],['Rusum','МП3-У'],['O\'lchov diapazoni','0–4 kgf/sm²'],['Aniqlik klassi','1,5'],['Himoya darajasi','IP40'],['Komplekt','Latun uch yo\'lli sinov krani bilan'],['Boshqaruv','Vizual ko\'rsatkich (strelkali)']]},
        {nom:'Manometr (0–1.6 MPa)',         tavsif:'Bosimni vizual nazorat qiluvchi glitserinli manometr. Tebranishga chidamli, paslanmaydigan korpus.', narx:'So\'rovnoma', birlik:'dona', qollanish:'GRP, regulyator va tugunlarda bosim nazorati', xus:[['Standart','GOST 2405'],['O\'lchov diapazoni','0–1.6 MPa'],['Diametr','100 mm'],['To\'ldirgich','Glitserin'],['Aniqlik klassi','1.5'],['Ulanish','M20×1.5'],['Kafolat','1 yil']]},
        {nom:'Termostat gaz qozonlari uchun',   tavsif:'Qozon haroratini avtomatik boshqaruvchi kapilyar termostat. Belgilangan haroratda gaz klapanini boshqaradi.', narx:'So\'rovnoma', birlik:'dona', qollanish:'Gaz qozonlari, isitish tizimlari', xus:[['Turi','Kapilyar termostat'],['Harorat diapazoni','0–90 °C'],['Boshqaruv','Klapan (rele)'],['Kapilyar uzunligi','1.5 m'],['Kuchlanish','220V'],['O\'rnatish','Panelga'],['Kafolat','2 yil']]},
        {nom:'Gaz analizatori portable',        tavsif:'Bir nechta gazni o\'lchovchi portativ analizator. Servis va tekshiruv ishlarida qo\'l keladi, batareyada ishlaydi.', narx:'So\'rovnoma', birlik:'dona', qollanish:'Servis xizmati, texnik ko\'rik, avariya', xus:[['O\'lchanadigan gazlar','CH4, CO, H2S'],['Ko\'rsatgich','Raqamli LCD'],['Signal','Ovozli/vibro'],['Quvvat','Akkumulyator (Li-ion)'],['Ish vaqti','~12 soat'],['Himoya','IP54'],['Kafolat','2 yil']]},
        {nom:'Quvur izolyatsiya lentasi',       tavsif:'Po\'lat quvurlarni korroziyadan himoya qiluvchi polietilen asosli lenta. Yerosti montajda majburiy qatlam.', narx:'So\'rovnoma', birlik:'rulon', qollanish:'Yerosti po\'lat quvurlar izolyatsiyasi', xus:[['Standart','GOST 9.602'],['Asos','Polietilen + bitum'],['Qalinlik','1.5 mm'],['Kenglik','450 mm'],['Rulon uzunligi','50 m'],['Ishlash harorati','−40…+60 °C'],['Kafolat','—']]},
      ]
    },
    gorelka: {
      title: 'Gorelkalar Katalogi',
      label: 'Gorelkalar',
      desc: 'Gaz qozonlari, kolonkalar va pechlar uchun gorelka bloklari — elektrsiz va avtomatik boshqaruvli',
      // Ko'k + shisha (glass) + kulrang uslub
      color: '#2563eb',
      bg: 'rgba(100,116,139,0.12)',
      border:'rgba(148,163,184,0.40)',
      icon: 'fa-fire',
      iconBg: 'linear-gradient(135deg,#475569,#2563eb)',
      pageBg: '#eef2f7',
      items: [
        {nom:'Gaz gorelkasi UGOP-16 (elektrsiz)', kalit:'ugop-16-gorelka', rasm:['images/jihozlar/ugop-16-muqova.webp','images/jihozlar/ugop-16-2.png','images/jihozlar/ugop-16-1.jpg','images/jihozlar/ugop-16-3.jpg','images/jihozlar/ugop-16-4.jpg','images/jihozlar/ugop-16-video.mp4'], tavsif:'Energiyaga bog\'liq bo\'lmagan sektsiyali gaz gorelkasi. Elektr tarmog\'isiz ishlaydi: qo\'lda yondiriladi, doimiy fitil (zapalnik) va termopara alangani nazorat qiladi — olov o\'chsa, klapan gazni avtomatik to\'sadi.', narx:'650 000 so\'m', birlik:'to\'plam', qollanish:'Gaz pechlari va qozonlarni jihozlash, eski gorelkani almashtirish', belgi:'16 kWt', eslatma:'Bu gorelka <b>elektr tarmog\'iga ulanmaydi</b> — elektr o\'chganda ham ishlayveradi. Yondirish qo\'lda bajariladi: tugmani bosib fitilni yoqasiz va termopara qizishi uchun <b>10–15 soniya</b> ushlab turasiz. O\'rnatishdan oldin pech (qozon) o\'chog\'i o\'lchamlari va gaz kirish rezbasi mos kelishini tekshiring.', xus:[['Model','UGOP-16'],['Quvvat','16 kWt'],['Boshqaruv','Mexanik (elektrsiz)'],['Gorelka turi','Sektsiyali'],['Yondirish','Qo\'lda, fitil (zapalnik) orqali'],['Xavfsizlik','Termopara — alanga o\'chsa gaz to\'siladi'],['Klapan','Shar tutqichli (qo\'lda)'],['Kafolat','1 yil']]},
        {nom:'Gorelka bloki EMMETI 650 gaz klapani bilan', kalit:'gorelka-bloki-emmeti-650', rasm:['images/jihozlar/gorelka-bloki-1.jpg','images/jihozlar/gorelka-bloki-2.jpg','images/jihozlar/gorelka-bloki-3.jpg','images/jihozlar/gorelka-bloki-4.jpg','images/jihozlar/gorelka-bloki-video.mp4'], tavsif:'Gaz kolonkasi va qozonlar uchun to\'liq gorelka to\'plami: asosiy gorelka, EMMETI 650 termostatli gaz klapani, uchqun beruvchi elektrod, termopara va yonish kamerasi himoya ekrani.', narx:'850 000 so\'m', birlik:'to\'plam', qollanish:'Gaz kolonkalari va qozonlarni ta\'mirlash, gorelka va klapan almashtirish', belgi:'6 seksiyali', eslatma:'Gorelka seksiyalari soni gaz qozonining quvvatiga qarab farqlanadi. Ushbu blok — <b>6 seksiyali</b> gorelka bilan jihozlangan. Buyurtma berishdan oldin qozoningizdagi eski gorelka seksiyalarini sanab, mos keladiganini tanlang: seksiyalar soni mos kelmasa, blok qozon korpusiga o\'rnatilmaydi.', xus:[['Gorelka seksiyalari','6 ta seksiya'],['Tarkibi','Gorelka + klapan + elektrod + ekran'],['Klapan modeli','EMMETI 650'],['Kirish bosimi','50 mbar (maks)'],['Chiqish bosimi','3–11 mbar'],['Harorat diapazoni','40–90 °C'],['Xavfsizlik','Termopara + ionizatsiya datchigi'],['Klapan korpusi','Alyuminiy'],['Kafolat','1 yil']]},
        {nom:'6 seksiyali garelka', kalit:'gorelka-6-seksiyali', rasm:['images/jihozlar/gorelka-6-seksiyali-0.jpg','images/jihozlar/gorelka-6-seksiyali-1.jpg','images/jihozlar/gorelka-6-seksiyali-2.jpg','images/jihozlar/gorelka-6-seksiyali-3.jpg','images/jihozlar/gorelka-6-seksiyali-4.jpg'], tavsif:'Po\'lat korpusli 6 seksiyali gaz garelkasi. Teshikli seksiyalar barqaror yonishni ta\'minlaydi, o\'rnatish kronshteyni bilan oson montaj qilinadi.', narx:'So\'rovnoma', birlik:'dona', qollanish:'Gaz qozonlari va isitish jihozlari', belgi:'6 seksiyali', xus:[['Garelka seksiyalari','6 ta seksiya'],['Balandligi','350 mm'],['Eni','270 mm'],['Qalinligi','80 mm'],['Toifa','Garelkalar']]},
        {nom:'10 seksiyali avtomat garelka', kalit:'gorelka-10-seksiyali-avtomat', rasm:['images/jihozlar/gorelka-10-seksiyali-avtomat-1.jpg','images/jihozlar/gorelka-10-seksiyali-avtomat-2.jpg','images/jihozlar/gorelka-10-seksiyali-avtomat-3.jpg','images/jihozlar/gorelka-10-seksiyali-avtomat-4.jpg'], tavsif:'10 seksiyali avtomatik garelka: gaz klapani, boshqaruv paneli va piezo yondirgich bilan to\'liq jihozlangan. Po\'lat korpus, o\'rnatish plitasi bilan.', narx:'So\'rovnoma', birlik:'to\'plam', qollanish:'Gaz qozonlari va isitish jihozlari', belgi:'10 seksiyali', xus:[['Garelka seksiyalari','10 ta seksiya'],['Boshqaruv','Avtomatik, boshqaruv paneli bilan'],['Yondirish','Piezo zapal'],['Tarkibi','Garelka bloki + gaz klapani + avtomatika bloki'],['O\'rnatish','O\'rnatish plitasi bilan'],['Toifa','Garelkalar']]},
        {nom:'8 seksiyali avtomat garelka', kalit:'gorelka-8-seksiyali-avtomat', rasm:['images/jihozlar/garelka-katalog-muqova.webp','images/jihozlar/gorelka-8-seksiyali-avtomat-1.jpg','images/jihozlar/gorelka-8-seksiyali-avtomat-2.jpg','images/jihozlar/gorelka-8-seksiyali-avtomat-3.jpg'], tavsif:'Gaz qozonlari uchun 8 seksiyali avtomat garelka: EUROSIT 630 termostatli gaz klapani, harorat sozlagichi va o\'rnatish plitasi bilan. Oddiy mexanik konstruksiya, xizmat ko\'rsatish qulay.', narx:'So\'rovnoma', birlik:'to\'plam', qollanish:'Gaz qozonlari', belgi:'8 seksiyali', xus:[['Garelka seksiyalari','8 ta seksiya'],['Klapan modeli','EUROSIT 630'],['Kirish bosimi','3–18 mbar'],['Maks. bosim','50 mbar'],['Atrof harorati','0–80 °C'],['Harorat diapazoni','40–90 °C'],['Boshqaruv','Mexanik, harorat sozlagichi bilan'],['Toifa','Garelkalar']]},
        {nom:'Gaz gorelkasi GGI 60 kVt (qozonlar uchun)', kalit:'gorelka-ggi-60', rasm:['images/jihozlar/gorelka-ggi-60-1.jpg','images/jihozlar/gorelka-ggi-60-2.jpg','images/jihozlar/gorelka-ggi-60-3.jpg'], tavsif:'Qozon va pechlar o\'chog\'iga o\'rnatiladigan injeksion gaz gorelkasi (GGI): sakkiz nurli halqasimon tuzilma, har bir nur tubular teshiklar bilan jihozlangan. Po\'lat quvurdan payvandlangan, uzun quvurli ulanish qismi va ilgak halqasi bor. O\'zbekistonda ishlab chiqarilgan.', narx:'So\'rovnoma', birlik:'dona', qollanish:'Sanoat va maishiy qozonlar, pech va isitish qurilmalari o\'chog\'i', belgi:'60 kVt', eslatma:'Gorelka <b>qozon yoki pech o\'chog\'iga</b> o\'rnatiladi. Buyurtma berishdan oldin o\'choq o\'lchamlarini (gorelka diametri <b>320 mm</b>, balandligi <b>95 mm</b>, quvur bilan uzunligi <b>540 mm</b>) va gaz ulash rezbasini tekshiring. Qozon quvvati gorelka quvvatiga mos kelishi kerak. Gaz jihozini o\'rnatish va sozlashni faqat malakali mutaxassis bajarishi kerak.', xus:[['Model','GGI (gaz gorelkasi, injeksion)'],['Quvvat','60 kVt'],['Ishlab chiqaruvchi','OOO «VANGUARD KASTECHNOLOGIES»'],['Ishlab chiqarilgan joyi','O\'zbekiston'],['Konstruksiya','Halqa + 8 ta nur (tubular teshiklar)'],['Diametri','320 mm'],['Balandligi','95 mm'],['Umumiy uzunligi','540 mm'],['Ulanish quvuri','Ø 48 mm, ichki rezbali'],['Nur quvurlari','Ø 22 mm'],['Qo\'shimcha','Ilgak halqasi (koltso)'],['Toifa','Qozon gorelkalari']]},
        {nom:'Gaz gorelkasi GGI Ø24 (65 kVt, qozonlar uchun)', kalit:'gorelka-ggi-24', rasm:['images/jihozlar/gorelka-ggi-24-1.jpg','images/jihozlar/gorelka-ggi-24-2.jpg','images/jihozlar/gorelka-ggi-24-3.jpg','images/jihozlar/gorelka-ggi-24-4.jpg'], tavsif:'24 diametrli injeksion gaz gorelkasi (GGI): sakkiz nurli halqasimon tuzilma, har bir nur tubular teshiklar bilan jihozlangan. Po\'lat quvurdan payvandlangan, pastki qismida gaz ulash quvuri (tashqi rezbali) va o\'rnatish plitasi bor. Qozon va pech o\'chog\'i uchun. O\'zbekistonda ishlab chiqarilgan.', narx:'So\'rovnoma', birlik:'dona', qollanish:'Sanoat va maishiy qozonlar, pech va isitish qurilmalari o\'chog\'i', belgi:'Ø24 · 65 kVt', eslatma:'Bu model — <b>24 diametrli</b> gorelka, nominal issiqlik quvvati <b>65 kVt</b> (zavod tablichkasi bo\'yicha). Buyurtma berishdan oldin qozon (pech) o\'chog\'i o\'lchamiga mosligini va gaz ulash rezbasini tekshiring: boshqa diametrdagi GGI gorelkalari (masalan, 320 mm li, 60 kVt) o\'chog\'ingizga to\'g\'ri kelmasligi mumkin. Gaz jihozini o\'rnatish va sozlashni faqat malakali mutaxassis bajarishi kerak.', xus:[['Model','GGI (gaz gorelkasi, injeksion)'],['Diametr turi','24 (Ø24)'],['Nominal quvvat','65 kVt'],['Ishlab chiqaruvchi','OOO «VANGUARD KASTECHNOLOGIES»'],['Ishlab chiqarilgan joyi','O\'zbekiston'],['Ishlab chiqarilgan sana','04.04.2023'],['Konstruksiya','Halqa + 8 ta nur (tubular teshiklar)'],['Gaz ulash','Pastki quvur, tashqi rezbali'],['O\'rnatish','O\'rnatish plitasi va kronshteyn bilan'],['Toifa','Qozon gorelkalari']]},
        {nom:'Gaz gorelkasi GGI 0,95 (qozonlar uchun)', kalit:'gorelka-ggi-095', rasm:['images/jihozlar/gorelka-ggi-095-3.jpg','images/jihozlar/gorelka-ggi-095-1.jpg','images/jihozlar/gorelka-ggi-095-2.jpg'], tavsif:'Qozon va pech o\'chog\'iga o\'rnatiladigan injeksion gaz gorelkasi (GGI 0,95): sakkiz nurli halqasimon tuzilma, har bir nur teshikli quvurdan iborat. Uzun dastali quvur, forsunka (injektor) va o\'rnatish kronshteyni bilan. Kuchli alanga, tejamkor gaz sarfi va ishonchli konstruksiya.', narx:'So\'rovnoma', birlik:'dona', qollanish:'10, 20 va 40 litrli qozonlar, pech va isitish qurilmalari o\'chog\'i', belgi:'GGI 0,95', eslatma:'Gorelka <b>qozon hajmiga qarab</b> uch o\'lchamda: <b>10 L</b> (Ø20 cm), <b>20 L</b> (Ø23 cm) va <b>40 L</b> (Ø30 cm). Buyurtma berishdan oldin qozon (pech) o\'chog\'i o\'lchamini va gaz ulash rezbasini tekshiring. Gaz jihozini o\'rnatish va sozlashni faqat malakali mutaxassis bajarishi kerak.', xus:[['Model','GGI 0,95 (gaz gorelkasi, injeksion)'],['Konstruksiya','Halqa + 8 ta nur (teshikli quvurlar)'],['Nur quvuri','Ø 2,5 cm, teshiklar Ø 3 mm'],['Dasta quvuri','Ø 3,4 cm'],['10 L qozon uchun','Ø20 cm · balandligi 11 cm · dastasi 36 cm'],['20 L qozon uchun','Ø23 cm · balandligi 14 cm · dastasi 38 cm'],['40 L qozon uchun','Ø30 cm · balandligi 17 cm · dastasi 50 cm'],['Gaz ulash','Forsunka (injektor), tashqi rezbali'],['Toifa','Qozon gorelkalari']]},
        {nom:'4 seksiyali gaz gorelkasi', kalit:'gorelka-4-seksiyali-ggi', rasm:['images/jihozlar/gorelka-4-seksiyali-ggi-1.jpg','images/jihozlar/gorelka-4-seksiyali-ggi-2.jpg','images/jihozlar/gorelka-4-seksiyali-ggi-3.jpg'], tavsif:'Po\'lat korpusli 4 seksiyali gaz gorelkasi. Teshikli seksiyalar barqaror yonishni ta\'minlaydi, yuqoridagi rezbali quvur gaz ulash uchun, o\'rnatish kronshteynlari va mustahkam asos plitasi bilan oson montaj qilinadi.', narx:'So\'rovnoma', birlik:'dona', qollanish:'Gaz qozonlari va isitish jihozlari', belgi:'4 seksiyali', xus:[['Model','4 seksiyali gaz gorelkasi'],['Garelka seksiyalari','4 ta seksiya'],['Konstruksiya','Teshikli seksiyalar, po\'lat korpus'],['Gaz ulash','Yuqorida rezbali quvur'],['O\'rnatish','Kronshteynlar va asos plitasi bilan'],['Toifa','Garelkalar']]},
        {nom:'Uy-joy garelkasi Pro', tavsif:'Kuchaytirilgan model, 4-konfolli plita uchun', narx:'125 000 so\'m', birlik:'dona', qollanish:'Uy-joy plitalari, qozon va isitish jihozlari', belgi:'3.5 kW', xus:[['Quvvat','3.5 kW'],['Toifa','Uy-joy garelkalari'],['Yoqilg\'i','Tabiiy / suyultirilgan gaz']]},
        {nom:'Sanoat garelkasi Mini', tavsif:'Kichik qozonxona va issiqlik punktlari', narx:'380 000 so\'m', birlik:'dona', qollanish:'Sanoat qozonxonalari va issiqlik punktlari', belgi:'15 kW', xus:[['Quvvat','15 kW'],['Toifa','Sanoat garelkalari'],['Yoqilg\'i','Tabiiy / suyultirilgan gaz']]},
        {nom:'Sanoat garelkasi Standard', tavsif:'O\'rta hajmli sanoat qozonlari uchun', narx:'650 000 so\'m', birlik:'dona', qollanish:'Sanoat qozonxonalari va issiqlik punktlari', belgi:'50 kW', xus:[['Quvvat','50 kW'],['Toifa','Sanoat garelkalari'],['Yoqilg\'i','Tabiiy / suyultirilgan gaz']]},
        {nom:'Sanoat garelkasi Katta', tavsif:'Sanoat qozonlari, avtomatik boshqaruv', narx:'1 200 000 so\'m', birlik:'dona', qollanish:'Sanoat qozonxonalari va issiqlik punktlari', belgi:'100 kW', xus:[['Quvvat','100 kW'],['Toifa','Sanoat garelkalari'],['Yoqilg\'i','Tabiiy / suyultirilgan gaz']]},
        {nom:'Sanoat garelkasi Ultra', tavsif:'Yirik sanoat ob\'ektlari, modulli dizayn', narx:'2 100 000 so\'m', birlik:'dona', qollanish:'Sanoat qozonxonalari va issiqlik punktlari', belgi:'200 kW', xus:[['Quvvat','200 kW'],['Toifa','Sanoat garelkalari'],['Yoqilg\'i','Tabiiy / suyultirilgan gaz']]},
        {nom:'Infraqizil garelka I', tavsif:'Iqtisodiy isitish, terracotta emiter', narx:'120 000 so\'m', birlik:'dona', qollanish:'Ustaxona, ombor va ochiq maydonlarni isitish', belgi:'3.5 kW', xus:[['Quvvat','3.5 kW'],['Toifa','Infraqizil garelkalari'],['Yoqilg\'i','Tabiiy / suyultirilgan gaz']]},
        {nom:'Infraqizil garelka II', tavsif:'Katta xonalar, 2-emiterli tizim', narx:'195 000 so\'m', birlik:'dona', qollanish:'Ustaxona, ombor va ochiq maydonlarni isitish', belgi:'7 kW', xus:[['Quvvat','7 kW'],['Toifa','Infraqizil garelkalari'],['Yoqilg\'i','Tabiiy / suyultirilgan gaz']]},
        {nom:'Portativ mini garelka', tavsif:'Kampingda, sayrda va oshxona uchun', narx:'35 000 so\'m', birlik:'dona', qollanish:'Kamping, dala sharoiti va ko\'chma foydalanish', belgi:'1.2 kW', xus:[['Quvvat','1.2 kW'],['Toifa','Portativ garelkalari'],['Yoqilg\'i','Tabiiy / suyultirilgan gaz']]},
        {nom:'Portativ garelka Standard', tavsif:'Tez ulash, balon bilan ishlaydi', narx:'55 000 so\'m', birlik:'dona', qollanish:'Kamping, dala sharoiti va ko\'chma foydalanish', belgi:'2.5 kW', xus:[['Quvvat','2.5 kW'],['Toifa','Portativ garelkalari'],['Yoqilg\'i','Tabiiy / suyultirilgan gaz']]},
        {nom:'Payvandlash garelkasi', tavsif:'Propan-butan, qo\'l rostlagich, DN15', narx:'95 000 so\'m', birlik:'dona', qollanish:'Payvandlash, kesish va metallni qizdirish ishlari', belgi:'8 kW', xus:[['Quvvat','8 kW'],['Toifa','Payvandlash garelkalari'],['Yoqilg\'i','Tabiiy / suyultirilgan gaz']]},
        {nom:'Payvandlash garelkasi Pro', tavsif:'Professional, boshqaruv klapani bilan', narx:'160 000 so\'m', birlik:'dona', qollanish:'Payvandlash, kesish va metallni qizdirish ishlari', belgi:'15 kW', xus:[['Quvvat','15 kW'],['Toifa','Payvandlash garelkalari'],['Yoqilg\'i','Tabiiy / suyultirilgan gaz']]},
        {nom:'Duo-blok garelka S', tavsif:'Gaz+havo aralash, avtomatik sozlash', narx:'2 400 000 so\'m', birlik:'dona', qollanish:'Yirik sanoat qozonlari (gaz+havo aralashmali)', belgi:'300 kW', xus:[['Quvvat','300 kW'],['Toifa','Duo-blok garelkalari'],['Yoqilg\'i','Tabiiy / suyultirilgan gaz']]},
        {nom:'Duo-blok garelka M', tavsif:'O\'rta sanoat, modulli', narx:'3 800 000 so\'m', birlik:'dona', qollanish:'Yirik sanoat qozonlari (gaz+havo aralashmali)', belgi:'500 kW', xus:[['Quvvat','500 kW'],['Toifa','Duo-blok garelkalari'],['Yoqilg\'i','Tabiiy / suyultirilgan gaz']]},
        {nom:'Duo-blok garelka L', tavsif:'Katta sanoat ob\'ektlari uchun', narx:'5 500 000 so\'m', birlik:'dona', qollanish:'Yirik sanoat qozonlari (gaz+havo aralashmali)', belgi:'800 kW', xus:[['Quvvat','800 kW'],['Toifa','Duo-blok garelkalari'],['Yoqilg\'i','Tabiiy / suyultirilgan gaz']]},
        {nom:'Atmosferik garelka I', tavsif:'Tabiiy konveksiya, past bosim', narx:'290 000 so\'m', birlik:'dona', qollanish:'Past bosimli atmosferik qozonlar', belgi:'20 kW', xus:[['Quvvat','20 kW'],['Toifa','Atmosferik garelkalari'],['Yoqilg\'i','Tabiiy / suyultirilgan gaz']]},
        {nom:'Atmosferik garelka II', tavsif:'Ko\'p sekciyali, modulli tizim', narx:'420 000 so\'m', birlik:'dona', qollanish:'Past bosimli atmosferik qozonlar', belgi:'35 kW', xus:[['Quvvat','35 kW'],['Toifa','Atmosferik garelkalari'],['Yoqilg\'i','Tabiiy / suyultirilgan gaz']]},
        {nom:'LPG suyultirilgan gaz garelkasi', tavsif:'Propan-butan tizimi uchun maxsus', narx:'480 000 so\'m', birlik:'dona', qollanish:'Suyultirilgan gaz (propan-butan) tizimlari', belgi:'25 kW', xus:[['Quvvat','25 kW'],['Toifa','LPG garelkalari'],['Yoqilg\'i','Tabiiy / suyultirilgan gaz']]},
        {nom:'Qozon garelkasi', tavsif:'Uy-joy qozonxonasi, kam shovqin', narx:'890 000 so\'m', birlik:'dona', qollanish:'Uy-joy va kichik obyekt qozonxonalari', belgi:'60 kW', xus:[['Quvvat','60 kW'],['Toifa','Qozon garelkalari'],['Yoqilg\'i','Tabiiy / suyultirilgan gaz']]},
        {nom:'Maxsus sanoat garelkasi', tavsif:'Yirik korxona, raqamli boshqaruv paneli', narx:'8 500 000 so\'m', birlik:'dona', qollanish:'Sanoat qozonxonalari va issiqlik punktlari', belgi:'1000 kW', xus:[['Quvvat','1000 kW'],['Toifa','Sanoat garelkalari'],['Yoqilg\'i','Tabiiy / suyultirilgan gaz']]},
      ]
    },
  };

  let currentKat = null;

  // Gaz quvurlari katalogi hozircha yopiq ("Tez orada"). Ochish uchun: KAT_QUVUR_OCHIQ = true
  // (va yuqoridagi kartadan `disabled` hamda "Tez orada" belgisini olib tashlang).
  const KAT_QUVUR_OCHIQ = false;
  function openKatPage(kat) {
    if (kat === 'quvur' && !KAT_QUVUR_OCHIQ) { showToast("Gaz quvurlari katalogi tez orada ishga tushadi"); return; }
    katNarxlarniYukla();          // har ochilganda eng yangi narxlarni olamiz
    currentKat = kat;
    const d = KAT_DATA[kat];
    const page = document.getElementById('kat-page');
    page.style.background = d.pageBg;
    document.getElementById('kat-header').style.borderColor = d.border;
    const btn = document.getElementById('kat-back-btn');
    btn.style.background = d.bg;
    btn.style.color = d.color;
    btn.style.borderColor = d.color;
    const icon = document.getElementById('kat-header-icon');
    icon.style.background = d.iconBg;
    icon.innerHTML = `<i class="fas ${d.icon} text-oq text-sm"></i>`;
    document.getElementById('kat-title').innerHTML = `${d.label} <span style="color:${d.color}">Katalogi</span>`;
    document.getElementById('kat-subtitle').style.color = d.color;
    document.getElementById('kat-subtitle').textContent = d.label + ' — SOAR GAZ';
    document.getElementById('kat-top-label').style.color = d.color;
    document.getElementById('kat-top-label').textContent = d.label;
    document.getElementById('kat-top-title').innerHTML = `<span style="color:${d.color}">${d.title}</span>`;
    document.getElementById('kat-top-desc').textContent = d.desc;
    document.getElementById('kat-search').value = '';
    page.classList.remove('hidden');
    document.body.style.overflow = 'hidden';
    katRender();
  }

  function closeKatPage() {
    document.getElementById('kat-page').classList.add('hidden');
    document.body.style.overflow = xaridBolimOchiqmi() ? 'hidden' : '';
    currentKat = null;
  }

  // `rasm` bitta satr ham, massiv ham bo'lishi mumkin — har doim massiv qaytaramiz
  function katRasmlar(item) {
    if (!item || !item.rasm) return [];
    return Array.isArray(item.rasm) ? item.rasm : [item.rasm];
  }

  // Slayd video-mi? (.mp4 / .webm)
  function katVideomi(src) { return /\.(mp4|webm)(\?|$)/i.test(src); }

  // Placeholder (ikon + "RASM") — rasm yo'q yoki yuklanmagan holat uchun
  function katPlaceholder(d, ikonSize, yashirin) {
    return `<div class="${yashirin ? '' : 'flex '}flex-col items-center justify-center gap-2 select-none absolute inset-0"
      style="${yashirin ? 'display:none;' : ''}color:${d.color};opacity:0.2">
      <i class="fas ${d.icon}" style="font-size:${ikonSize}"></i>
      <span style="font-size:9px;letter-spacing:.18em;font-weight:700">RASM</span>
    </div>`;
  }

  // Grid kartasi uchun — faqat birinchi rasm (video bo'lsa o'tkazib yuboriladi)
  function katRasmHTML(item, d, ikonSize) {
    const rasmlar = katRasmlar(item).filter(s => !katVideomi(s));
    if (!rasmlar.length) return katPlaceholder(d, ikonSize, false);
    return `<img src="${rasmlar[0]}" alt="${item.nom}" loading="lazy" decoding="async"
        class="w-full h-full object-contain p-4 transition-transform duration-500"
        data-h-mouseover="h236" data-h-mouseout="h237"
        data-h-error="h238"/>
      ${katPlaceholder(d, ikonSize, true)}`;
  }

  // Kompaniya Telegram hisobi — o'zgartirish uchun faqat shu qatorni tahrirlang
  const SOAR_TELEGRAM = 'soarcompany';

  // Mahsulot bo'yicha maslahat so'rab Telegramga yozish havolasi (matn oldindan to'ldiriladi)
  function katTelegramHavola(item) {
    const matn = `Assalomu alaykum! «${item.nom}» bo'yicha maslahat kerak — mos o'lchamni tanlashda yordam bera olasizmi?`;
    return `https://t.me/${SOAR_TELEGRAM}?text=${encodeURIComponent(matn)}`;
  }

  // ---- Jihoz pasporti va sertifikati paneli ----
  // Mahsulotga qo'shish: hujjatlar:[{tur:'sertifikat'|'pasport', nom:'...', fayl:'hujjatlar/xxx.pdf'}]
  const HUJJAT_TURLARI = {
    sertifikat: { nom: 'Sertifikat',     ikon: 'fa-certificate' },
    pasport:    { nom: 'Texnik pasport', ikon: 'fa-file-lines' },
    boshqa:     { nom: 'Hujjat',         ikon: 'fa-file' },
  };

  // Backenddan kelgan hujjatlar (kalit bo'yicha keshlanadi)
  const KAT_HUJJATLAR = {};

  function katHujjatlar(item) {
    if (item && item.kalit && Array.isArray(KAT_HUJJATLAR[item.kalit])) {
      return KAT_HUJJATLAR[item.kalit];
    }
    return Array.isArray(item && item.hujjatlar) ? item.hujjatlar : [];
  }

  // Hujjat havolalari 5 daqiqalik — oyna ochilganda har safar yangisini olamiz
  async function katHujjatlarniYukla(item) {
    if (!item || !item.kalit) return;
    try {
      const javob = await fetch(`/api/katalog/hujjatlar/${item.kalit}/`, { cache: 'no-store' });
      if (!javob.ok) return;
      KAT_HUJJATLAR[item.kalit] = await javob.json();
      // Panel allaqachon chizilgan bo'lsa — qayta chizamiz
      const panel = document.getElementById('kat-hujjat-panel');
      if (panel && katInfoIdx !== null) {
        panel.outerHTML = katHujjatlarPanel(item, KAT_DATA[currentKat]);
      }
    } catch (e) {
      // Backend o'chiq — statik `hujjatlar` maydoni ishlatiladi
    }
  }

  function katHujjatlarPanel(item, d) {
    const hujjatlar = katHujjatlar(item);

    const ichi = hujjatlar.length
      ? `<div class="grid sm:grid-cols-2 gap-2">${hujjatlar.map((h, i) => {
          const t = HUJJAT_TURLARI[h.tur] || HUJJAT_TURLARI.boshqa;
          return `<button data-h-click="c:katHujjatOch" data-a-click="${SG_A([i])}"
            class="flex items-center gap-3 rounded-xl px-3 py-2.5 text-left transition-all active:scale-95"
            style="background:#fff;border:1px solid ${d.border}"
            data-h-mouseover="sty" data-a-mouseover="${SG_A([{borderColor: `${d.color}`, boxShadow: `0 4px 14px rgba(31,72,135,0.10)`}])}"
            data-h-mouseout="sty" data-a-mouseout="${SG_A([{borderColor: `${d.border}`, boxShadow: `none`}])}">
            <span class="w-9 h-9 shrink-0 rounded-lg flex items-center justify-center"
              style="background:${d.bg};color:${d.color}"><i class="fas ${t.ikon} text-sm"></i></span>
            <span class="min-w-0 flex-1">
              <span class="block text-[9px] font-black uppercase tracking-widest" style="color:${d.color}">${t.nom}</span>
              <span class="block text-xs font-bold text-ink-900 truncate">${h.nom || t.nom}</span>
            </span>
            <i class="fas fa-up-right-and-down-left-from-center text-[10px]" style="color:${d.color}"></i>
          </button>`;
        }).join('')}</div>`
      : `<div class="flex items-center gap-3 rounded-xl px-3 py-3" style="background:#fff;border:1px dashed ${d.border}">
          <span class="w-9 h-9 shrink-0 rounded-lg flex items-center justify-center"
            style="background:${d.bg};color:${d.color}"><i class="fas fa-file-circle-question text-sm"></i></span>
          <p class="text-xs" style="color:#5b7fa6">Bu mahsulot uchun hujjat nusxalari hali yuklanmagan.
            Sertifikat va texnik pasport jihoz sotib olinganda qo'shib yuboriladi.</p>
        </div>`;

    return `<div id="kat-hujjat-panel" class="kat-anim rounded-xl overflow-hidden" style="border:1px solid ${d.border}">
      <div class="flex items-center gap-2 px-4 py-2.5" style="background:${d.bg.replace('0.12','0.10')}">
        <i class="fas fa-file-shield text-xs" style="color:${d.color}"></i>
        <span class="text-[10px] font-black uppercase tracking-widest" style="color:${d.color}">Jihoz pasporti va sertifikati</span>
        ${hujjatlar.length ? `<span class="ml-auto text-[10px] font-black px-2 py-0.5 rounded-full"
          style="background:${d.color};color:#fff">${hujjatlar.length}</span>` : ''}
      </div>
      <div class="p-3" style="background:${d.bg.replace('0.12','0.04')}">
        ${ichi}
        ${hujjatlar.length ? `<div class="flex items-start gap-2 mt-2.5 px-1">
          <i class="fas fa-lock text-[10px] mt-0.5" style="color:#b91c1c"></i>
          <p class="text-[11px] leading-relaxed" style="color:#5b7fa6">
            Hujjatlar <b class="text-ink-900">faqat ko'rish uchun</b> ochiladi — yuklab olish va nusxa ko'chirish taqiqlangan.
            Asl nusxalari <b class="text-ink-900">jihoz sotib olinganda qo'shib yuboriladi</b>.
          </p>
        </div>` : ''}
      </div>
    </div>`;
  }

  // Hujjatni ko'rish oynasida ochish
  function katHujjatOch(i) {
    const item = KAT_DATA[currentKat] && KAT_DATA[currentKat].items[katInfoIdx];
    const h = katHujjatlar(item)[i];
    if (!h) return;
    const t = HUJJAT_TURLARI[h.tur] || HUJJAT_TURLARI.boshqa;
    // Backend `havola` (imzolangan, 5 daqiqalik) yoki statik `fayl` yo'li
    const manba = h.havola || h.fayl;

    document.getElementById('kat-hujjat-nom').textContent = h.nom || t.nom;
    document.getElementById('kat-hujjat-ikon').className = `fas ${t.ikon}`;

    // PDF: brauzer ko'ruvchisining yuklab olish/chop etish paneli o'chiriladi
    const pdfMi = h.rasm === false || /\.pdf(\?|$)/i.test(manba);
    const ichi = pdfMi
      ? `<iframe src="${manba}#toolbar=0&navpanes=0&scrollbar=0&view=FitH"
           class="w-full rounded-lg" style="height:78vh;border:none;background:#fff"></iframe>`
      : `<img src="${manba}" alt="${h.nom || t.nom}" draggable="false" decoding="async"
           class="w-full h-auto rounded-lg" style="background:#fff"/>`;

    // Suv belgisi + ko'rinmas himoya qatlami
    const belgi = Array.from({ length: 14 }, () =>
      `<span>SOAR GAZ &nbsp;·&nbsp; faqat ko'rish uchun</span>`).join('');

    document.getElementById('kat-hujjat-body').innerHTML = `
      ${ichi}
      <div class="kat-suv-belgi"><div class="flex flex-col">${belgi}</div></div>
      <div class="kat-himoya-qatlam" data-h-contextmenu="h239"></div>`;

    const ov = document.getElementById('kat-hujjat-overlay');
    ov.classList.remove('hidden');
    ov.classList.add('flex');
  }

  function katHujjatYop() {
    const ov = document.getElementById('kat-hujjat-overlay');
    ov.classList.add('hidden');
    ov.classList.remove('flex');
    document.getElementById('kat-hujjat-body').innerHTML = '';   // PDF/rasmni bo'shatamiz
  }

  function katHujjatOchiqmi() {
    return !document.getElementById('kat-hujjat-overlay').classList.contains('hidden');
  }

  // Hujjat ochiq bo'lganda o'ng tugma, nusxalash, saqlash va chop etishni to'sish
  document.addEventListener('contextmenu', (e) => {
    if (katHujjatOchiqmi() && e.target.closest('#kat-hujjat-overlay')) e.preventDefault();
  });
  document.addEventListener('copy', (e) => { if (katHujjatOchiqmi()) e.preventDefault(); });
  document.addEventListener('dragstart', (e) => {
    if (katHujjatOchiqmi() && e.target.closest('#kat-hujjat-overlay')) e.preventDefault();
  });
  document.addEventListener('keydown', (e) => {
    if (!katHujjatOchiqmi()) return;
    const k = (e.key || '').toLowerCase();
    // Ctrl/Cmd + S (saqlash), P (chop etish), C (nusxa), U (kod), Shift+I (DevTools)
    if ((e.ctrlKey || e.metaKey) && ['s', 'p', 'c', 'u'].includes(k)) { e.preventDefault(); katHujjatOgohlantir(); }
    if (k === 'printscreen') { e.preventDefault(); katHujjatOgohlantir(); }
  }, true);

  let katOgohTimer = null;
  function katHujjatOgohlantir() {
    const body = document.getElementById('kat-hujjat-body');
    if (!body || body.querySelector('.kat-ogoh')) return;
    const el = document.createElement('div');
    el.className = 'kat-ogoh absolute left-1/2 -translate-x-1/2 text-xs font-bold px-4 py-2 rounded-xl flex items-center gap-2';
    el.style.cssText = 'bottom:16px;z-index:9;background:rgba(185,28,28,0.95);color:#fff;box-shadow:0 4px 16px rgba(0,0,0,0.25)';
    el.innerHTML = `<i class="fas fa-lock text-[10px]"></i>Hujjatdan nusxa olish taqiqlangan`;
    body.appendChild(el);
    clearTimeout(katOgohTimer);
    katOgohTimer = setTimeout(() => el.remove(), 2200);
  }

  // ---- Modal ichidagi rasm slayderi ----
  let katSlideIdx = 0;

  function katSliderHTML(item, d) {
    const rasmlar = katRasmlar(item);
    if (!rasmlar.length) return katPlaceholder(d, '2.5rem', false);

    const slaydlar = rasmlar.map(src => `
      <div class="shrink-0 w-full h-full relative">
        ${katVideomi(src)
          ? `<video src="${src}" class="w-full h-full object-contain" muted loop playsinline preload="metadata"></video>
             <div class="absolute top-2 left-2 text-[9px] font-black uppercase tracking-wider px-2 py-0.5 rounded-full flex items-center gap-1"
               style="background:rgba(255,255,255,0.9);color:${d.color};border:1px solid ${d.border}">
               <i class="fas fa-play text-[7px]"></i>Video
             </div>`
          : `<img src="${src}" alt="${item.nom}" class="w-full h-full object-contain"
               loading="lazy" decoding="async"
               data-h-error="h238"/>
             ${katPlaceholder(d, '2.5rem', true)}`}
      </div>`).join('');

    if (rasmlar.length === 1) {
      return `<div class="w-full h-full">${slaydlar}</div>`;
    }

    const nuqtalar = rasmlar.map((_, i) => `
      <button data-h-click="c:katSlideGoto" data-a-click="${SG_A([i])}" aria-label="${i + 1}-rasm"
        class="kat-nuqta rounded-full transition-all" data-idx="${i}"
        style="width:${i === 0 ? '18px' : '6px'};height:6px;background:${i === 0 ? d.color : 'rgba(31,72,135,0.25)'}"></button>`).join('');

    const strelka = (yon, belgi) => `
      <button data-h-click="c:katSlideMove" data-a-click="${SG_A([yon])}" aria-label="${yon > 0 ? 'Keyingi' : 'Oldingi'} rasm"
        class="absolute top-1/2 -translate-y-1/2 ${yon > 0 ? 'right-2' : 'left-2'} w-8 h-8 rounded-full flex items-center justify-center transition-all active:scale-90"
        style="background:rgba(255,255,255,0.9);color:${d.color};border:1px solid ${d.border};box-shadow:0 2px 8px rgba(31,72,135,0.15)">
        <i class="fas ${belgi} text-xs"></i>
      </button>`;

    return `
      <div id="kat-slider-track" class="flex w-full h-full transition-transform duration-300 ease-out"
        style="transform:translateX(0)"
        data-h-touchstart="h240" data-h-touchend="h241">${slaydlar}</div>
      ${strelka(-1, 'fa-chevron-left')}
      ${strelka(1, 'fa-chevron-right')}
      <div class="absolute top-2 right-2 text-[10px] font-bold px-2 py-0.5 rounded-full"
        style="background:rgba(255,255,255,0.9);color:${d.color};border:1px solid ${d.border}">
        <span id="kat-slider-hisob">1</span>/${rasmlar.length}
      </div>
      <div class="absolute bottom-2 left-1/2 -translate-x-1/2 flex items-center gap-1.5">${nuqtalar}</div>`;
  }

  // Faol slaydga belgi qo'yish — rasm yumshoq paydo bo'lishi uchun
  function katSlideBelgila() {
    const track = document.getElementById('kat-slider-track');
    if (!track) return;
    Array.from(track.children).forEach((s, idx) => {
      s.classList.remove('kat-slayd-faol');
      const video = s.querySelector('video');
      if (idx === katSlideIdx) {
        void s.offsetWidth;                    // animatsiyani qayta ishga tushirish
        s.classList.add('kat-slayd-faol');
        if (video) { video.currentTime = 0; video.play().catch(() => {}); }
      } else if (video) {
        video.pause();
      }
    });
  }

  // Oyna yopilganda barcha videolarni to'xtatish
  function katVideoToxtat() {
    document.querySelectorAll('#kat-info-body video').forEach(v => v.pause());
  }

  function katSlideGoto(i) {
    const track = document.getElementById('kat-slider-track');
    if (!track) return;
    const soni = track.children.length;
    katSlideIdx = (i + soni) % soni;          // aylanma: oxiridan boshiga o'tadi
    track.style.transform = `translateX(-${katSlideIdx * 100}%)`;

    const d = KAT_DATA[currentKat];
    document.querySelectorAll('.kat-nuqta').forEach((n, idx) => {
      const faol = idx === katSlideIdx;
      n.style.width = faol ? '18px' : '6px';
      n.style.background = faol ? d.color : 'rgba(31,72,135,0.25)';
    });
    const hisob = document.getElementById('kat-slider-hisob');
    if (hisob) hisob.textContent = katSlideIdx + 1;
    katSlideBelgila();
  }

  function katSlideMove(delta) { katSlideGoto(katSlideIdx + delta); }

  // Barmoq bilan surish (swipe)
  let katSwipeX = null;
  function katSwipeStart(e) { katSwipeX = e.changedTouches[0].clientX; }
  function katSwipeEnd(e) {
    if (katSwipeX === null) return;
    const farq = e.changedTouches[0].clientX - katSwipeX;
    if (Math.abs(farq) > 40) katSlideMove(farq < 0 ? 1 : -1);
    katSwipeX = null;
  }

  function katRender() {
    if (!currentKat) return;
    const d = KAT_DATA[currentKat];
    const q = (document.getElementById('kat-search')?.value || '').toLowerCase();
    const list = q ? d.items.filter(i => i.nom.toLowerCase().includes(q) || i.tavsif.toLowerCase().includes(q)) : d.items;
    const grid = document.getElementById('kat-grid');
    const empty = document.getElementById('kat-empty');
    if (!list.length) { grid.innerHTML = ''; empty.classList.remove('hidden'); return; }
    empty.classList.add('hidden');
    grid.innerHTML = list.map((item, idx) => `
      <div class="rounded-2xl overflow-hidden flex flex-col transition-all duration-300"
        style="background:linear-gradient(160deg,${d.bg.replace('0.12','0.08')} 0%,rgba(0,0,0,0.3) 100%);
               border:1px solid ${d.border.replace('0.35','0.2')};
               box-shadow:0 4px 20px rgba(31,72,135,0.10)"
        data-h-mouseover="sty" data-a-mouseover="${SG_A([{borderColor: `${d.color}`, transform: `translateY(-4px)`, boxShadow: `0 8px 30px ${d.bg}`}])}"
        data-h-mouseout="sty" data-a-mouseout="${SG_A([{borderColor: d.border.replace('0.35','0.2'), transform: 'translateY(0)', boxShadow: '0 4px 20px rgba(31,72,135,0.10)'}])}">
        <!-- Rasm maydoni -->
        <div class="relative flex items-center justify-center overflow-hidden" style="height:260px;background:#ffffff">
          ${katRasmHTML(item, d, '3rem')}
          <div class="absolute top-2 left-2 text-[9px] font-black uppercase tracking-wider px-2 py-0.5 rounded-full"
            style="background:${d.bg};color:${d.color};border:1px solid ${d.border}">${d.label}</div>
          <div class="absolute bottom-2 right-2 text-[9px] font-bold px-2 py-0.5 rounded-lg"
            style="background:rgba(0,0,0,0.6);color:${d.color};border:1px solid ${d.border.replace('0.35','0.3)')}">
            ${item.birlik}
          </div>
          ${item.belgi ? `<div class="absolute bottom-2 left-2 text-[10px] font-black px-2.5 py-1 rounded-lg flex items-center gap-1.5"
            style="background:${d.color};color:#fff;box-shadow:0 2px 8px rgba(0,0,0,0.15)">
            <i class="fas fa-layer-group text-[9px]"></i>${item.belgi}
          </div>` : ''}
        </div>
        <!-- Info -->
        <div class="p-4 flex flex-col flex-1">
          <h3 class="font-black text-ink-900 text-sm leading-snug mb-1">${item.nom}</h3>
          <p class="text-xs leading-relaxed flex-1 mb-3" style="color:#5b7fa6;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden">${item.tavsif}</p>
          <div class="flex items-center justify-between mb-3">
            ${katNarxYopiqmi(item)
              ? `<div class="font-bold text-sm" style="color:${d.color}"><i class="fas fa-clock mr-1.5"></i>Narxi tez orada</div>`
              : `<div class="font-black text-base" style="color:${d.color}">${item.narx}</div>`}
            <div class="text-xs" style="color:#6b7280">${item.birlik} uchun</div>
          </div>
          <button data-h-click="c:katInfo" data-a-click="${SG_A([idx])}"
            class="w-full font-bold rounded-xl text-xs py-2.5 transition-all active:scale-95 flex items-center justify-center gap-1.5"
            style="background:${d.bg};color:${d.color};border:1.5px solid ${d.color}"
            data-h-mouseover="sty" data-a-mouseover="${SG_A([{background: `${d.color}`, color: `#fff`}])}"
            data-h-mouseout="sty" data-a-mouseout="${SG_A([{background: `${d.bg}`, color: `${d.color}`}])}">
            <i class="fas fa-circle-info"></i>Batafsil / So'rov
          </button>
        </div>
      </div>`).join('');
  }

  // ---- Mahsulot detal oynasi (oynacha) ----
  let katInfoIdx = null;
  function katInfo(idx) {
    if (!currentKat) return;
    const d = KAT_DATA[currentKat];
    const item = d.items[idx];
    if (!item) return;
    katInfoIdx = idx;
    katSlideIdx = 0;
    document.getElementById('kat-info-hicon').style.color = d.color;
    document.getElementById('kat-info-hlabel').style.color = d.color;
    document.getElementById('kat-info-head').style.borderColor = d.border;
    document.getElementById('kat-info-card').style.borderColor = d.border;

    const xusRows = item.xus.map(x => `
      <div class="flex justify-between gap-3 py-2 border-b" style="border-color:rgba(31,72,135,0.06)">
        <span class="text-xs" style="color:#5b7fa6">${x[0]}</span>
        <span class="text-xs font-bold text-ink-900 text-right">${x[1]}</span>
      </div>`).join('');

    document.getElementById('kat-info-body').innerHTML = `
      <div class="lg:grid lg:grid-cols-2 lg:gap-6 lg:items-start">
        <!-- Chap ustun: rasm slayderi (keng ekranda yopishib turadi) -->
        <div class="relative rounded-2xl overflow-hidden mb-4 lg:mb-0 lg:sticky lg:top-0"
          style="height:min(70vh,640px);background:#ffffff;border:1px solid ${d.border.replace('0.35','0.2')}">
          ${katSliderHTML(item, d)}
        </div>
        <!-- O'ng ustun: ma'lumot -->
        <div class="flex flex-col gap-4">
        <div class="kat-anim">
          <div class="flex items-center gap-2 flex-wrap">
            <span class="text-[10px] font-black uppercase tracking-widest px-2.5 py-1 rounded-full" style="background:${d.bg};color:${d.color};border:1px solid ${d.border}">${d.label}</span>
            ${item.belgi ? `<span class="text-[10px] font-black uppercase tracking-widest px-2.5 py-1 rounded-full flex items-center gap-1.5"
              style="background:${d.color};color:#fff"><i class="fas fa-layer-group text-[9px]"></i>${item.belgi}</span>` : ''}
          </div>
          <h2 class="font-black text-ink-900 leading-snug mt-2" style="font-size:20px">${item.nom}</h2>
        </div>
        <p class="kat-anim text-sm leading-relaxed" style="color:#40699a">${item.tavsif}</p>
        ${item.eslatma ? `<div class="kat-anim rounded-xl overflow-hidden" style="border:1px solid ${d.border}">
          <div class="flex items-center gap-2 px-4 py-2.5" style="background:${d.color}">
            <i class="fas fa-triangle-exclamation text-xs" style="color:#fff"></i>
            <span class="text-[11px] font-black uppercase tracking-widest" style="color:#fff">Muhim: o'lchamni tanlash</span>
          </div>
          <div class="px-4 py-3" style="background:${d.bg.replace('0.12','0.05')}">
            <p class="text-xs leading-relaxed" style="color:#40699a">${item.eslatma}</p>
            <!-- Telegram orqali yordam so'rash -->
            <div class="mt-3 pt-3 flex items-center gap-3 flex-wrap" style="border-top:1px dashed ${d.border}">
              <p class="text-xs flex-1 min-w-[180px]" style="color:#40699a">
                <i class="fas fa-circle-question text-[11px] mr-1" style="color:${d.color}"></i>
                Tanlovda <b class="text-ink-900">ikkilansangiz yoki qiynalsangiz</b> — Telegramdan bizga yozing,
                mutaxassislarimiz sizga <b class="text-ink-900">mos o'lchamni tanlab beradi</b>.
              </p>
              <a href="${katTelegramHavola(item)}" target="_blank" rel="noopener"
                class="shrink-0 flex items-center gap-2 font-black text-xs px-4 py-2.5 rounded-xl transition-all active:scale-95"
                style="background:linear-gradient(135deg,#229ED9,#2AABEE);color:#fff;box-shadow:0 4px 14px rgba(34,158,217,0.3)"
                data-h-mouseover="h242"
                data-h-mouseout="h243">
                <i class="fab fa-telegram text-base"></i>Telegramdan yozish
              </a>
            </div>
          </div>
        </div>` : ''}
        <div class="kat-anim">
          <div class="text-[10px] uppercase tracking-widest mb-1.5 font-bold" style="color:${d.color}">Texnik xususiyatlar</div>
          <div class="rounded-xl px-4 py-1" style="background:rgba(31,72,135,0.03);border:1px solid rgba(31,72,135,0.07)">${xusRows}</div>
        </div>
        ${item.qollanish ? `<div class="kat-anim rounded-xl p-3 flex items-start gap-2.5" style="background:${d.bg.replace('0.12','0.06')};border:1px solid ${d.border.replace('0.35','0.2')}"><i class="fas fa-lightbulb mt-0.5" style="color:${d.color}"></i><div><div class="text-[10px] uppercase tracking-widest font-bold mb-0.5" style="color:${d.color}">Qo'llanish sohasi</div><p class="text-xs" style="color:#40699a">${item.qollanish}</p></div></div>` : ''}
        ${katHujjatlarPanel(item, d)}
        <div class="kat-anim flex items-center justify-between rounded-xl p-3" style="background:rgba(31,72,135,0.03);border:1px solid rgba(31,72,135,0.07)">
          <span class="text-sm font-bold" style="color:${d.color}">${katNarxYopiqmi(item) ? '<i class="fas fa-clock mr-1.5"></i>Narxi tez orada kiritiladi' : 'Narx: ' + item.narx}</span>
          <span class="text-xs" style="color:#5b7fa6">${item.birlik} uchun</span>
        </div>
        <div class="kat-anim rounded-xl p-4" style="background:rgba(31,72,135,0.03);border:1px solid rgba(31,72,135,0.08)">
          <div class="text-[10px] uppercase tracking-widest mb-3 font-bold" style="color:${d.color}">Narx so'rovi yuborish</div>
          <div class="grid grid-cols-2 gap-2 mb-2">
            <input id="kat-req-ism" type="text" placeholder="Ism-familiya" class="bg-white border text-ink-900 rounded-lg px-3 py-2 text-sm outline-none" style="border-color:rgba(31,72,135,0.15)"/>
            <input id="kat-req-tel" type="tel" placeholder="+998 90 000 00 00" class="bg-white border text-ink-900 rounded-lg px-3 py-2 text-sm outline-none" style="border-color:rgba(31,72,135,0.15)"/>
          </div>
          <div class="flex items-center gap-3 mb-3">
            <span class="text-xs" style="color:#5b7fa6">Miqdor:</span>
            <div class="flex items-center rounded-lg overflow-hidden" style="border:1px solid ${d.border}">
              <button data-h-click="h244" class="w-8 h-8 font-black transition-colors" style="color:${d.color}">−</button>
              <input id="kat-req-qty" type="number" value="1" min="1" max="999" class="w-12 text-center font-black text-sm bg-transparent outline-none" style="color:${d.color};border:none"/>
              <button data-h-click="h245" class="w-8 h-8 font-black transition-colors" style="color:${d.color}">+</button>
            </div>
          </div>
          <div class="grid grid-cols-2 gap-2">
            <button data-h-click="h246" class="font-bold rounded-lg text-xs py-2.5 flex items-center justify-center gap-1.5 transition-all active:scale-95" style="background:rgba(31,72,135,0.06);color:#1c3d63;border:1px solid rgba(255,255,255,0.15)"><i class="fas fa-cart-plus"></i>Savatga</button>
            <button data-h-click="h247" class="font-black rounded-lg text-xs py-2.5 flex items-center justify-center gap-1.5 transition-all active:scale-95" style="background:${d.color};color:#05070c"><i class="fas fa-paper-plane"></i>So'rov yuborish</button>
          </div>
        </div>
        </div>
      </div>`;
    const ov = document.getElementById('kat-info-overlay');
    ov.classList.remove('hidden', 'kat-yopilmoqda', 'kat-ochilmoqda');
    ov.classList.add('flex');
    void ov.offsetWidth;                 // reflow — animatsiya qayta ishga tushishi uchun
    ov.classList.add('kat-ochilmoqda');
    document.getElementById('kat-info-body').scrollTop = 0;
    katSlideBelgila();
    katHujjatlarniYukla(item);      // hujjat havolalari qisqa muddatli — har ochilganda yangilanadi
  }
  function katInfoClose() {
    const ov = document.getElementById('kat-info-overlay');
    if (ov.classList.contains('kat-yopilmoqda')) return;   // ikki marta bosilishdan himoya
    ov.classList.remove('kat-ochilmoqda');
    ov.classList.add('kat-yopilmoqda');
    katVideoToxtat();
    katInfoIdx = null;
    setTimeout(() => {
      ov.classList.add('hidden');
      ov.classList.remove('flex', 'kat-yopilmoqda');
    }, 180);                                                // CSS dagi .18s bilan bir xil
  }
  // Modal ochiq bo'lsa — klaviatura strelkalari bilan rasmlarni almashtirish
  document.addEventListener('keydown', (e) => {
    // Hujjat oynasi ochiq bo'lsa — avval o'shani yopamiz
    const hujjatOchiq = !document.getElementById('kat-hujjat-overlay').classList.contains('hidden');
    if (hujjatOchiq) {
      if (e.key === 'Escape') katHujjatYop();
      return;
    }
    if (katInfoIdx === null) return;
    if (e.key === 'ArrowRight') katSlideMove(1);
    else if (e.key === 'ArrowLeft') katSlideMove(-1);
    else if (e.key === 'Escape') katInfoClose();
  });
  function katQty(delta) {
    const inp = document.getElementById('kat-req-qty');
    inp.value = Math.max(1, Math.min(999, (parseInt(inp.value) || 1) + delta));
  }
  // Natija oynasi
  function katResult(html) {
    document.getElementById('kat-result-body').innerHTML = html;
    const ov = document.getElementById('kat-result-overlay');
    ov.classList.remove('hidden'); ov.classList.add('flex');
  }
  function katResultClose() {
    const ov = document.getElementById('kat-result-overlay');
    ov.classList.add('hidden'); ov.classList.remove('flex');
  }
  function _katRow(label, val) {
    return `<div class="flex justify-between gap-3 py-2 border-b" style="border-color:rgba(31,72,135,0.06)">
      <span class="text-xs" style="color:#5b7fa6">${label}</span>
      <span class="text-xs font-bold text-ink-900 text-right">${val}</span></div>`;
  }

  function katSavatga() {
    const d = KAT_DATA[currentKat];
    const item = d.items[katInfoIdx];
    if (!item) return;
    const qty = Math.max(1, parseInt(document.getElementById('kat-req-qty').value) || 1);
    // Savatda mahsulot o'z toifasining ikonkasi va rangi bilan ko'rinadi.
    // Narxi belgilangan bo'lsa savatga o'sha narx tushadi, aks holda 0 —
    // savat uni "Narx so'rov asosida" deb ko'rsatadi.
    cartAdd(item.nom, katNarxRaqam(item), qty, { ikona: d.icon, rang: d.color });
    const jami = cartTotalQty();
    katResult(`
      <div class="text-center mb-5">
        <div class="w-16 h-16 rounded-full flex items-center justify-center mx-auto mb-3" style="background:rgba(80,165,230,0.15);border:1px solid rgba(80,165,230,0.4)">
          <i class="fas fa-cart-plus text-2xl" style="color:#15803d"></i>
        </div>
        <h3 class="text-xl font-black text-ink-900">Savatga qo'shildi!</h3>
        <p class="text-sm mt-1" style="color:#5b7fa6">Mahsulot savatchangizga muvaffaqiyatli qo'shildi</p>
      </div>
      <div class="rounded-xl px-4 py-1 mb-4" style="background:rgba(31,72,135,0.03);border:1px solid rgba(31,72,135,0.08)">
        ${_katRow('Mahsulot', item.nom)}
        ${_katRow('Miqdor', qty + ' ' + item.birlik)}
        ${_katRow('Kategoriya', d.label)}
        ${_katRow('Savatdagi jami', jami + ' mahsulot')}
      </div>
      <div class="rounded-xl p-3 mb-5 flex items-start gap-2.5" style="background:rgba(60,140,225,0.06);border:1px solid rgba(60,140,225,0.2)">
        <i class="fas fa-circle-info mt-0.5" style="color:#0d6efd"></i>
        <p class="text-xs" style="color:#40699a">Savatchada mahsulotlar miqdorini o'zgartirishingiz, keyin bitta so'rov bilan buyurtma berishingiz mumkin.</p>
      </div>
      <div class="grid grid-cols-2 gap-2">
        <button data-h-click="h248" class="font-bold rounded-xl text-sm py-3 transition-all active:scale-95" style="background:rgba(31,72,135,0.06);color:#1c3d63;border:1px solid rgba(255,255,255,0.15)">Xaridni davom ettirish</button>
        <button data-h-click="h249" class="font-black rounded-xl text-sm py-3 transition-all active:scale-95 flex items-center justify-center gap-1.5" style="background:linear-gradient(135deg,#16a34a,#22c55e);color:#04120a"><i class="fas fa-shopping-cart"></i>Savatni ochish</button>
      </div>`);
  }

  async function katSorovSend(ev) {
    const d = KAT_DATA[currentKat];
    const item = d.items[katInfoIdx];
    if (!item) return;
    const ism = tval('kat-req-ism'), tel = tval('kat-req-tel');
    const qty = Math.max(1, parseInt(document.getElementById('kat-req-qty').value) || 1);
    if (!ism || !tel) { showToast('Ism va telefon raqamini kiriting'); return; }
    const btn = ev && ev.target ? ev.target.closest('button') : null;
    let orig;
    if (btn) { orig = btn.innerHTML; btn.innerHTML = '<i class="fas fa-spinner spin"></i> Yuborilmoqda...'; btn.disabled = true; }
    try {
      const r = await apiPost('/tolovlar/mahsulot-sorov/', {
        ism, telefon: tel, mahsulot: item.nom, katalog: currentKat,
        miqdor: qty, birlik: item.birlik, izoh: item.tavsif,
      });
      katInfoClose();
      katResult(`
        <div class="text-center mb-5">
          <div class="w-16 h-16 rounded-full flex items-center justify-center mx-auto mb-3" style="background:rgba(80,165,230,0.15);border:1px solid rgba(80,165,230,0.4)">
            <i class="fas fa-check text-2xl" style="color:#15803d"></i>
          </div>
          <h3 class="text-xl font-black text-ink-900">So'rov qabul qilindi!</h3>
          <p class="text-sm mt-1" style="color:#5b7fa6">So'rov raqami: <span class="font-black" style="color:${d.color}">#${r.id}</span></p>
        </div>
        <div class="rounded-xl px-4 py-1 mb-4" style="background:rgba(31,72,135,0.03);border:1px solid rgba(31,72,135,0.08)">
          ${_katRow('Mahsulot', item.nom)}
          ${_katRow('Miqdor', qty + ' ' + item.birlik)}
          ${_katRow('Mijoz', ism)}
          ${_katRow('Telefon', tel)}
        </div>
        <div class="rounded-xl p-4 mb-5" style="background:rgba(31,72,135,0.03);border:1px solid rgba(31,72,135,0.08)">
          <div class="text-[10px] uppercase tracking-widest mb-3 font-bold" style="color:${d.color}">Keyingi qadamlar</div>
          <div class="space-y-2.5">
            <div class="flex items-start gap-2.5"><span class="w-5 h-5 rounded-full flex items-center justify-center text-[10px] font-black shrink-0" style="background:${d.bg};color:${d.color}">1</span><p class="text-xs" style="color:#40699a">Mutaxassisimiz <b class="text-ink-900">24 soat</b> ichida siz bilan bog'lanadi</p></div>
            <div class="flex items-start gap-2.5"><span class="w-5 h-5 rounded-full flex items-center justify-center text-[10px] font-black shrink-0" style="background:${d.bg};color:${d.color}">2</span><p class="text-xs" style="color:#40699a">Aniq <b class="text-ink-900">narx va yetkazib berish shartlari</b> taklif etiladi</p></div>
            <div class="flex items-start gap-2.5"><span class="w-5 h-5 rounded-full flex items-center justify-center text-[10px] font-black shrink-0" style="background:${d.bg};color:${d.color}">3</span><p class="text-xs" style="color:#40699a">Kelishuv asosida <b class="text-ink-900">rasmiylashtiriladi va yetkaziladi</b></p></div>
          </div>
        </div>
        <div class="rounded-xl p-3 mb-5 flex items-center gap-2.5" style="background:rgba(80,165,230,0.06);border:1px solid rgba(80,165,230,0.2)">
          <i class="fas fa-comment-sms" style="color:#15803d"></i>
          <p class="text-xs" style="color:#40699a">Tasdiq SMS raqamingizga yuborildi. Savolingiz bo'lsa: <b class="text-ink-900">+998 71 234 56 78</b></p>
        </div>
        <button data-h-click="h248" class="w-full font-black rounded-xl text-sm py-3 transition-all active:scale-95" style="background:${d.color};color:#05070c">Yopish</button>`);
    } catch (err) {
      if (btn) { btn.innerHTML = orig; btn.disabled = false; }
      showToast('Xatolik: serverga ulanib bo\'lmadi. Backend ishlayotganini tekshiring.');
    }
  }

  // ---- Qadriyat sahifalari (Ish jarayoni / Tajribali jamoa / Kafolat) ----
  // Uchala kartochka bitta sahifani ochadi, mazmuni shu obyektdan olinadi.
  // MAZMUNNI TO'LDIRISH: kerakli kalitning `bolimlar` massiviga qo'shing —
  //   { sarlavha: '...', matn: '...' }            — oddiy matnli blok
  //   { sarlavha: '...', royxat: ['...', '...'] } — belgilangan ro'yxat
  // SLAYD (kadrlar ketma-ketligi): `slaydlar` massiviga qo'shing —
  //   { rasm: 'images/ish-jarayoni/01-...jpg', sarlavha: '...', matn: '...' }
  // Tartib qanday yozilsa, slaydda ham shunday ketma-ketlikda ko'rsatiladi.
  // HTML ga tegish shart emas.
  const QADRIYATLAR = {
    jarayon: {
      uzra: 'Qanday ishlaymiz',
      sarlavha: 'Ish jarayoni',
      ikon: 'fa-diagram-project',
      rang: '#0d6efd',
      tavsif: "Kotlovan qazishdan obyektni topshirishgacha — jamoamizning haqiqiy ish kadrlarida.",
      slaydlar: [
        {
          rasm: 'images/ish-jarayoni/01-kotlovan-qazish.webp',
          sarlavha: 'Maydonni ochamiz',
          matn: "Loyiha qog'ozda tugab, yerda boshlanadigan daqiqa. Texnika joyida, trassa belgilangan, jamoa safarbar.",
          shior: "Rejadan zaminga — biz shu yerdan boshlaymiz.",
        },
        {
          rasm: 'images/ish-jarayoni/02-trassa-ochish.webp',
          sarlavha: 'Trassani ochish',
          matn: "Ekskavator quvur o'qi bo'ylab traneshey ochadi: chuqurlik, kenglik va qiyalik loyihaga qat'iy mos bo'lishi shart.",
          shior: "To'g'ri o'lchov — mustahkam poydevor.",
        },
        {
          rasm: 'images/ish-jarayoni/03-quvurni-tushirish.webp',
          sarlavha: 'Quvurni joyiga tushirish',
          matn: "Bir necha tonnalik quvur jamoaning bir og'iz ishorasi bilan qimirlaydi. Bu yerda har bir kishi bir-birining xavfsizligiga javobgar.",
          shior: "Kuch — yolg'izlikda emas, uyg'unlikda.",
        },
        {
          rasm: 'images/ish-jarayoni/04-markazlash.webp',
          sarlavha: 'Markazlash va tekislash',
          matn: "Ikki quvur uchi millimetrgacha to'g'rilanadi. Payvandning sifati aynan shu daqiqada hal bo'ladi.",
          shior: "Bugungi bir millimetr xato — ertangi yillik muammo.",
        },
        {
          rasm: 'images/ish-jarayoni/05-tor-joyda-ulash.webp',
          sarlavha: 'Tor joyda aniq ish',
          matn: "Ko'chalar orasidagi tor kotlovanda ham ish hajmi kichraymaydi — talab va standart o'sha-o'sha qoladi.",
          shior: "Sharoit qiyin bo'lishi mumkin, sifat esa — hech qachon.",
        },
        {
          rasm: 'images/ish-jarayoni/06-payvandga-tayyorgarlik.webp',
          sarlavha: 'Payvandga tayyorgarlik',
          matn: "Quvur uchlari tozalanadi, qirralari kesiladi, moslik tekshiriladi. Shoshilinch bajarilgan tayyorgarlik keyin qayta ish bo'lib qaytadi.",
          shior: "Yaxshi tayyorgarlik — ishning yarmi bajarilgani.",
        },
        {
          rasm: 'images/ish-jarayoni/07-payvand-choki.webp',
          sarlavha: 'Ildiz choki',
          matn: "Elektrod uchidagi yoy ikki metalni bir butunga aylantiradi. Bu chok yer ostida o'nlab yillar xizmat qiladi.",
          shior: "Har bir chok — jamoamizning imzosi.",
        },
        {
          rasm: 'images/ish-jarayoni/08-uzluksiz-payvand.webp',
          sarlavha: 'Uzluksiz payvand',
          matn: "Bir chok tugaydi — ikkinchisi boshlanadi. Trassa shu tarzda metrma-metr uzayib, xonadonlarga yaqinlashadi.",
          shior: "Har bir metr quvur — kimningdir issiq uyi.",
        },
        {
          rasm: 'images/ish-jarayoni/09-burilish-tuguni.webp',
          sarlavha: 'Burilish tugunlari',
          matn: "Otvod, o'tish va ulanish nuqtalari — trassaning eng mas'uliyatli joylari. Bu yerda tajriba tezlikdan ustun turadi.",
          shior: "Eng qiyin nuqtada eng tajribali usta ishlaydi.",
        },
        {
          rasm: 'images/ish-jarayoni/10-izolyatsiya.webp',
          sarlavha: 'Izolyatsiya qoplamasi',
          matn: "Chok tozalanib, issiqlikda qisiluvchi qoplama bilan yopiladi. Bu — korroziyaga qarshi ko'rinmas qalqon.",
          shior: "Ko'rinmaydigan ish uzoq umr beradi.",
        },
        {
          rasm: 'images/ish-jarayoni/11-yakuniy-nazorat.webp',
          sarlavha: 'Nazorat va topshirish',
          matn: "Choklar tekshiriladi, bosim sinovi o'tkaziladi va obyekt to'liq hujjatlari bilan topshiriladi.",
          shior: "Ishonch va'da bilan emas, bajarilgan ish bilan qozoniladi.",
        },
      ],
      bolimlar: [],
    },
    jamoa: {
      uzra: 'Kim ishlaydi',
      sarlavha: 'Tajribali jamoa',
      ikon: 'fa-users',
      rang: '#ff8a00',
      tavsif: 'Muhandislar, metrologlar va montajchilardan iborat jamoamiz.',
      bolimlar: [],
    },
    kafolat: {
      uzra: 'Nimaga kafolat beramiz',
      sarlavha: 'Kafolat',
      ikon: 'fa-handshake-angle',
      rang: '#0d6efd',
      tavsif: 'Shartnoma, oldindan hisob-kitob va bajarilgan ishlarga kafolat.',
      bolimlar: [],
    },
  };

  // ---- Kadrlar ketma-ketligi slayderi ----
  // Bir vaqtda bitta slayder ochiq bo'ladi, shuning uchun holat shu yerda saqlanadi.
  let qdSlaydIndeks = 0;
  let qdSlaydSoni = 0;
  let qdSlaydTaymer = null;

  // Kadr o'zi almashishigacha necha soniya kutilsin.
  // 0 — avto-almashish o'chiq: kadr faqat foydalanuvchi surganda almashadi.
  const QD_AVTO_SONIYA = 0;

  function qdSlayderHtml(slaydlar, rang) {
    if (!slaydlar.length) return '';
    // Kadrlar turli o'lchamda (tik va yotiq) — shuning uchun rasm `contain`
    // bilan to'liq ko'rsatiladi, orqa fon esa o'sha rasmning xiralashgan nusxasi.
    const kadrlar = slaydlar.map((s, i) => `
      <figure class="qd-slayd absolute inset-0" style="transition:opacity .5s ease;opacity:${i === 0 ? 1 : 0};pointer-events:${i === 0 ? 'auto' : 'none'}">
        <img src="${escapeHtml(s.rasm)}" alt="" aria-hidden="true"
             loading="${i === 0 ? 'eager' : 'lazy'}" decoding="async"
             class="absolute inset-0 w-full h-full object-cover"
             style="filter:blur(26px) brightness(0.55);transform:scale(1.15)">
        <img src="${escapeHtml(s.rasm)}" alt="${escapeHtml(s.sarlavha || 'Ish jarayoni kadri')}"
             loading="${i === 0 ? 'eager' : 'lazy'}" decoding="async"
             class="relative w-full h-full object-contain">
        ${(s.sarlavha || s.matn || s.shior) ? `
        <figcaption class="absolute inset-x-0 bottom-0 p-5 sm:p-6 text-oq"
                    style="background:linear-gradient(to top,rgba(5,12,24,0.92),rgba(5,12,24,0.6) 50%,transparent)">
          <span class="inline-block text-[10px] font-black tracking-widest uppercase rounded-md px-2 py-1 mb-2"
                style="background:${rang};color:#05070c">${i + 1}-bosqich</span>
          ${s.sarlavha ? `<h4 class="font-black text-base sm:text-lg leading-tight">${escapeHtml(s.sarlavha)}</h4>` : ''}
          ${s.matn ? `<p class="text-xs sm:text-sm mt-1 opacity-90 max-w-2xl">${escapeHtml(s.matn)}</p>` : ''}
          ${s.shior ? `<p class="text-xs sm:text-sm font-black mt-2 pl-3" style="border-left:3px solid ${rang}">${escapeHtml(s.shior)}</p>` : ''}
        </figcaption>` : ''}
      </figure>`).join('');

    const nuqtalar = slaydlar.map((_, i) => `
      <button type="button" data-h-click="c:qdSlaydKorsat" data-a-click="${SG_A([i])}" aria-label="${i + 1}-kadr"
              class="qd-nuqta h-1.5 rounded-full transition-all"
              style="width:${i === 0 ? '26px' : '10px'};background:${i === 0 ? rang : 'rgba(120,170,235,0.45)'}"></button>`).join('');

    // Bittadan ko'p kadr bo'lgandagina strelka va nuqtalar ko'rsatiladi.
    const boshqaruv = slaydlar.length > 1 ? `
      <button type="button" data-h-click="h250" aria-label="Oldingi kadr"
              class="absolute left-3 top-1/2 -translate-y-1/2 w-10 h-10 rounded-full flex items-center justify-center transition-all active:scale-90"
              style="background:rgba(255,255,255,0.92);color:#0d2440;box-shadow:0 4px 14px rgba(5,12,24,0.25)">
        <i class="fas fa-chevron-left text-sm"></i>
      </button>
      <button type="button" data-h-click="h251" aria-label="Keyingi kadr"
              class="absolute right-3 top-1/2 -translate-y-1/2 w-10 h-10 rounded-full flex items-center justify-center transition-all active:scale-90"
              style="background:rgba(255,255,255,0.92);color:#0d2440;box-shadow:0 4px 14px rgba(5,12,24,0.25)">
        <i class="fas fa-chevron-right text-sm"></i>
      </button>` : '';

    return `
      <div class="rounded-2xl overflow-hidden mb-6" style="background:#fff;border:1px solid rgba(120,170,235,0.2)">
        <div id="qd-slayder" class="relative w-full" style="aspect-ratio:4/3;max-height:70vh;background:#0d2440">
          ${kadrlar}
          ${boshqaruv}
        </div>
        ${slaydlar.length > 1 ? `
        <div class="flex items-center justify-between gap-3 px-4 py-3">
          <div id="qd-nuqtalar" class="flex items-center gap-1.5">${nuqtalar}</div>
          <span id="qd-slayd-hisob" class="text-xs font-bold" style="color:#5b7fa6">1 / ${slaydlar.length}</span>
        </div>` : ''}
      </div>`;
  }

  function qdSlaydKorsat(indeks) {
    const kadrlar = document.querySelectorAll('#qd-slayder .qd-slayd');
    if (!kadrlar.length) return;
    qdSlaydIndeks = (indeks + kadrlar.length) % kadrlar.length;
    kadrlar.forEach((el, i) => {
      const faol = i === qdSlaydIndeks;
      el.style.opacity = faol ? 1 : 0;
      el.style.pointerEvents = faol ? 'auto' : 'none';
    });
    const nuqtalar = document.querySelectorAll('#qd-nuqtalar .qd-nuqta');
    nuqtalar.forEach((el, i) => {
      el.style.width = i === qdSlaydIndeks ? '26px' : '10px';
      el.style.background = i === qdSlaydIndeks ? '#0d6efd' : 'rgba(120,170,235,0.45)';
    });
    const hisob = document.getElementById('qd-slayd-hisob');
    if (hisob) hisob.textContent = `${qdSlaydIndeks + 1} / ${kadrlar.length}`;
  }

  function qdSlaydSurish(yonalish) {
    qdSlaydKorsat(qdSlaydIndeks + yonalish);
    qdSlaydAvtoQayta(); // qo'lda surilganda avto-almashish taymeri qaytadan boshlanadi
  }

  function qdSlaydAvtoQayta() {
    clearInterval(qdSlaydTaymer);
    if (!QD_AVTO_SONIYA || qdSlaydSoni < 2) return;
    qdSlaydTaymer = setInterval(() => qdSlaydKorsat(qdSlaydIndeks + 1), QD_AVTO_SONIYA * 1000);
  }

  function qdSlayderIshga(soni) {
    qdSlaydIndeks = 0;
    qdSlaydSoni = soni;
    clearInterval(qdSlaydTaymer);
    if (!soni) return;
    qdSlaydAvtoQayta();

    // Telefonda barmoq bilan surish
    const quti = document.getElementById('qd-slayder');
    if (!quti) return;
    let boshX = null;
    quti.addEventListener('touchstart', e => { boshX = e.touches[0].clientX; }, { passive: true });
    quti.addEventListener('touchend', e => {
      if (boshX === null) return;
      const farq = e.changedTouches[0].clientX - boshX;
      if (Math.abs(farq) > 45) qdSlaydSurish(farq < 0 ? 1 : -1);
      boshX = null;
    }, { passive: true });
  }

  function qadriyatOch(kalit) {
    const d = QADRIYATLAR[kalit];
    if (!d) return;

    document.getElementById('qd-sarlavha').textContent = d.sarlavha;
    document.getElementById('qd-bosh').textContent = d.sarlavha;
    document.getElementById('qd-uzra').textContent = d.uzra;
    document.getElementById('qd-tavsif').textContent = d.tavsif;
    document.getElementById('qd-ikon').className = `fas ${d.ikon} text-oq text-sm`;
    document.getElementById('qd-ikon-quti').style.background = d.rang;

    const mazmun = document.getElementById('qd-mazmun');
    const slaydlar = d.slaydlar || [];
    if (!d.bolimlar.length && !slaydlar.length) {
      // Mazmun hali to'ldirilmagan — bo'sh sahifa o'rniga aniq xabar
      mazmun.innerHTML = `
        <div class="rounded-2xl p-8 text-center" style="background:#fff;border:1px dashed rgba(120,170,235,0.45)">
          <i class="fas fa-pen-ruler text-2xl mb-3" style="color:#9db8d8"></i>
          <p class="text-sm font-bold text-ink-900 mb-1">Bu bo'lim tayyorlanmoqda</p>
          <p class="text-xs" style="color:#5b7fa6">Ma'lumotlar tez orada qo'shiladi.</p>
        </div>`;
    } else {
      mazmun.innerHTML = qdSlayderHtml(slaydlar, d.rang) + d.bolimlar.map(b => `
        <div class="rounded-2xl p-6" style="background:#fff;border:1px solid rgba(120,170,235,0.2)">
          <h4 class="font-bold text-base mb-2 text-ink-900">${escapeHtml(b.sarlavha)}</h4>
          ${b.matn ? `<p class="text-sm leading-relaxed" style="color:#5b7fa6">${escapeHtml(b.matn)}</p>` : ''}
          ${b.royxat ? `<ul class="text-sm leading-relaxed mt-2 space-y-1.5" style="color:#5b7fa6">${
            b.royxat.map(x => `<li class="flex gap-2"><i class="fas fa-check text-xs mt-1" style="color:${d.rang}"></i><span>${escapeHtml(x)}</span></li>`).join('')
          }</ul>` : ''}
        </div>`).join('');
      qdSlayderIshga(slaydlar.length);
    }

    document.getElementById('qadriyat-page').classList.remove('hidden');
    document.body.style.overflow = 'hidden';
    window.scrollTo(0, 0);
  }

  function qadriyatYop() {
    clearInterval(qdSlaydTaymer);
    qdSlaydSoni = 0;
    document.getElementById('qadriyat-page').classList.add('hidden');
    // Biz haqimizda sahifasi ortida ochiq turgan bo'lishi mumkin
    const bizOchiq = !document.getElementById('biz-page').classList.contains('hidden');
    if (!bizOchiq) document.body.style.overflow = '';
  }

  // Klaviatura: sahifa ochiq turganda strelkalar bilan kadrlarni almashtirish
  document.addEventListener('keydown', e => {
    if (!qdSlaydSoni) return;
    if (document.getElementById('qadriyat-page').classList.contains('hidden')) return;
    if (e.key === 'ArrowRight') qdSlaydSurish(1);
    else if (e.key === 'ArrowLeft') qdSlaydSurish(-1);
    else if (e.key === 'Escape') qadriyatYop();
  });

  // Biz haqimizda — navbardan ochiladigan to'liq ekran oyna
  function openBizPage() {
    document.getElementById('biz-page').classList.remove('hidden');
    document.body.style.overflow = 'hidden';
    window.scrollTo(0, 0);
  }
  function closeBizPage() {
    document.getElementById('biz-page').classList.add('hidden');
    document.body.style.overflow = '';
  }

  // ---- "Ko'p beriladigan savollar" oynasi
  function openFaqPage() {
    const p = document.getElementById('faq-page');
    if (!p) return;
    p.classList.remove('hidden');
    p.scrollTop = 0;
    document.body.style.overflow = 'hidden';
  }
  function closeFaqPage() {
    const p = document.getElementById('faq-page');
    if (p) p.classList.add('hidden');
    document.body.style.overflow = '';
  }

  // ---- "To'lovlar" oynasi: 3 ta to'lov usuli + hisob-faktura. Ichki oynalar (bank, onlayn, shartnoma, faktura) yuqorida ochiladi
  function tolovOchiqmi() {
    const p = document.getElementById('tolov-page');
    return !!p && !p.classList.contains('hidden');
  }
  function openTolovPage() {
    const p = document.getElementById('tolov-page');
    if (!p) return;
    p.classList.remove('hidden');
    p.scrollTop = 0;
    document.body.style.overflow = 'hidden';
  }
  function closeTolovPage() {
    const p = document.getElementById('tolov-page');
    if (p) p.classList.add('hidden');
    document.body.style.overflow = '';
  }

  // ---- "Nega SOAR GAZ?" oynasi: Afzalliklar va "Qanday ishlaymiz" bo'limlari
  function openNegaPage() {
    const p = document.getElementById('nega-page');
    if (!p) return;
    p.classList.remove('hidden');
    p.scrollTop = 0;
    document.body.style.overflow = 'hidden';
  }
  function closeNegaPage() {
    const p = document.getElementById('nega-page');
    if (p) p.classList.add('hidden');
    document.body.style.overflow = '';
  }
  // Oyna ichidagi bo'lim tugmalari: tegishli bo'limga silliq o'tadi
  function negaBolimga(id) {
    const el = document.getElementById(id);
    if (el) el.scrollIntoView({ behavior: 'smooth', block: 'start' });
  }

  // ---- Xaridlar bo'limi oynasi: 4 ta katalog (Garelkalar, Quvurlar, Hisoblagichlar, Ventillar) shu oyna ichida
  function xaridBolimOchiqmi() {
    const p = document.getElementById('xaridlar-page');
    return !!p && !p.classList.contains('hidden');
  }
  function openXaridBolim() {
    const p = document.getElementById('xaridlar-page');
    if (!p) return;
    p.classList.remove('hidden');
    p.scrollTop = 0;
    document.body.style.overflow = 'hidden';
  }
  function closeXaridBolim() {
    const p = document.getElementById('xaridlar-page');
    if (p) p.classList.add('hidden');
    document.body.style.overflow = '';
  }

  function openMetroPage() {
    const mp = document.getElementById('metro-page');
    mp.classList.remove('hidden');
    mp.scrollTop = 0;
    document.body.style.overflow = 'hidden';
  }
  function closeMetroPage() {
    document.getElementById('metro-page').classList.add('hidden');
    document.body.style.overflow = '';
  }

  // Narxnoma oynasi (hamma uchun ochiq, faqat o'qish).
  function openHisobPage() {
    document.getElementById('hisob-page').classList.remove('hidden');
    document.getElementById('hisob-page').scrollTop = 0;
    document.body.style.overflow = 'hidden';
    narxnomaYukla();
  }
  function closeHisobPage() {
    document.getElementById('hisob-page').classList.add('hidden');
    document.body.style.overflow = '';
  }

  // ═══════ OCHIQ NARXNOMA (hamma uchun, faqat o'qish) ═══════
  // Ma'lumot /api/narxnoma/ochiq/ dan olinadi — kodda narx yozilmagan.
  // metroEsc / metroPul pastda (Metrologiya bo'limida) e'lon qilingan; ular faqat chaqirilganda ishlatiladi.
  let _nnMalumot = null, _nnSorov = null, _nnTarmoq = null;
  const NN_TARMOQ_NOM = { aholi: 'Aholi uchun', ulgurji: 'Ulgurji (biznes) uchun' };

  function narxnomaYukla() {
    if (_nnMalumot) { narxnomaChiz(); return; }
    if (_nnSorov) return;
    const box = document.getElementById('nn-royxat');
    _nnSorov = fetch(API + '/narxnoma/ochiq/', { headers: { 'Accept': 'application/json' }, credentials: 'omit' })
      .then(r => { if (!r.ok) throw new Error('HTTP ' + r.status); return r.json(); })
      .then(j => { _nnMalumot = j; narxnomaChiz(); })
      .catch(() => {
        box.innerHTML = '<p class="text-center text-sm" style="color:#5b7fa6">Narxnomani yuklab bo\'lmadi. ' +
          '<button type="button" class="font-bold underline" style="color:#0d6efd" data-h-click="h252">Qayta urinish</button></p>';
      })
      .finally(() => { _nnSorov = null; });
  }

  function narxnomaTarmoq(t) { _nnTarmoq = t; narxnomaChiz(); }

  function narxnomaChiz() {
    const j = _nnMalumot || [];
    const tarmoqlar = ['aholi', 'ulgurji'].filter(t => j.some(n => n.tarmoq === t));
    const box = document.getElementById('nn-royxat');
    if (!tarmoqlar.length) {
      document.getElementById('nn-tarmoq-tablar').innerHTML = '';
      box.innerHTML = '<p class="text-center text-sm" style="color:#5b7fa6">Narxnoma hozircha kiritilmagan. Aniq narx uchun ariza qoldiring.</p>';
      return;
    }
    if (!tarmoqlar.includes(_nnTarmoq)) _nnTarmoq = tarmoqlar[0];

    document.getElementById('nn-tarmoq-tablar').innerHTML = tarmoqlar.map(t =>
      '<button type="button" role="tab" aria-selected="' + (t === _nnTarmoq) + '" data-h-click="c:narxnomaTarmoq" data-a-click="' + SG_A([t]) + '" ' +
      'class="px-5 py-2.5 rounded-xl font-bold text-sm transition-all" style="' +
      (t === _nnTarmoq ? 'background:#0d6efd;color:#fff;border:1px solid #0d6efd'
                       : 'background:#fff;color:#0d6efd;border:1px solid rgba(120,170,235,0.4)') + '">' +
      metroEsc(NN_TARMOQ_NOM[t]) + '</button>').join('');

    const narx = (dan, gacha) => dan == null ? '—'
      : (gacha != null ? metroPul(dan) + ' – ' + metroPul(gacha) : metroPul(dan));
    const sana = d => d ? d.split('-').reverse().join('.') : '';

    box.innerHTML = j.filter(n => n.tarmoq === _nnTarmoq).map(n => {
      const ikki = !!n.ustun2;
      const qatorlar = n.qatorlar.map(q => {
        // Narx yo'q qator: izoh ("kelishuv asosida") bitta katakda, butun narx ustunlari bo'ylab ko'rinadi
        const bosh = q.p_dan == null && (!ikki || q.r_dan == null);
        const narxTd = (dan, gacha) =>
          '<td class="px-3 py-3 text-right font-black whitespace-nowrap" style="color:#0d6efd">' + narx(dan, gacha) + '</td>';
        const boshTd = '<td class="px-3 py-3 text-right text-xs" colspan="' + (ikki ? 2 : 1) +
          '" style="color:#5b7fa6">' + metroEsc(q.izoh || 'Kelishuv asosida') + '</td>';
        return '<tr style="border-top:1px solid rgba(120,170,235,0.18)">' +
          '<td class="px-3 py-3 text-xs align-top" style="color:#5b7fa6">' + metroEsc(q.tartib) + '</td>' +
          '<td class="px-3 py-3 text-sm font-semibold text-ink-900">' + metroEsc(q.nomi) +
            (!bosh && q.izoh ? '<div class="text-xs font-normal mt-0.5" style="color:#5b7fa6">' + metroEsc(q.izoh) + '</div>' : '') + '</td>' +
          (bosh ? boshTd : narxTd(q.p_dan, q.p_gacha) + (ikki ? narxTd(q.r_dan, q.r_gacha) : '')) + '</tr>';
      }).join('');
      const eslatma = String(n.eslatma || '').split('\n').map(x => x.trim()).filter(Boolean)
        .map(x => '<p class="text-xs mt-1.5" style="color:#5b7fa6">' + metroEsc(x) + '</p>').join('');
      return '<div class="rounded-2xl overflow-hidden mb-8" style="background:#fff;border:1px solid rgba(120,170,235,0.25)">' +
        '<div class="px-5 py-4" style="background:linear-gradient(160deg,#e7f1fd,#f1f7ff)">' +
          '<h3 class="font-black text-lg text-ink-900">' + metroEsc(n.sarlavha) + '</h3>' +
          (n.tavsif ? '<p class="text-xs mt-1" style="color:#5b7fa6">' + metroEsc(n.tavsif) + '</p>' : '') +
          (n.amal_qiladi ? '<p class="text-[11px] mt-1" style="color:#3d7ab5">Amal qilish sanasi: ' + sana(n.amal_qiladi) + '</p>' : '') +
        '</div>' +
        '<div class="overflow-x-auto"><table class="w-full text-left">' +
          '<thead><tr class="text-[11px] uppercase tracking-wider" style="color:#3d7ab5">' +
            '<th class="px-3 py-2 font-semibold">№</th><th class="px-3 py-2 font-semibold">Xizmat</th>' +
            '<th class="px-3 py-2 font-semibold text-right">' + metroEsc(n.ustun1) + '</th>' +
            (ikki ? '<th class="px-3 py-2 font-semibold text-right">' + metroEsc(n.ustun2) + '</th>' : '') +
          '</tr></thead><tbody>' + (qatorlar || '<tr><td colspan="4" class="px-3 py-4 text-sm" style="color:#5b7fa6">Qatorlar yo\'q</td></tr>') + '</tbody>' +
        '</table></div>' +
        (eslatma ? '<div class="px-5 py-3" style="border-top:1px solid rgba(120,170,235,0.18)">' + eslatma + '</div>' : '') +
      '</div>';
    }).join('');
  }

  // Galereya va mijoz fikrlari — real ma'lumot qo'shilganda bo'limlar avtomatik ko'rinadi.
  // Namuna: { rasm: 'images/rezervuar/obyekt-1.jpg', matn: '2000L yer osti, G\'ijduvon' }
  const REZ_GALEREYA = [];
  // Namuna: { matn: '...', kim: 'Alisher A.', joy: 'Buxoro tumani' }
  const REZ_FIKRLAR = [];

  function rezGalereyaChiz() {
    if (REZ_GALEREYA.length) {
      document.getElementById('rz-galereya-blok').hidden = false;
      document.getElementById('rz-galereya').innerHTML = REZ_GALEREYA.map(g =>
        `<figure><img src="${g.rasm}" alt="${g.matn}" loading="lazy"><figcaption>${g.matn}</figcaption></figure>`
      ).join('');
    }
    if (REZ_FIKRLAR.length) {
      document.getElementById('rz-fikrlar-blok').hidden = false;
      document.getElementById('rz-fikrlar').innerHTML = REZ_FIKRLAR.map(f =>
        `<div class="rz-fikr"><blockquote>${f.matn}</blockquote>
         <footer>${f.kim}<span class="rz-fikr-joy"> — ${f.joy}</span></footer></div>`
      ).join('');
    }
  }


  // ═══════ XIZMAT OYNALARI (tabli) ═══════
  // Mijoz sharhlari. Real sharhlar qo'shilganda "Sharhlar" tab'i o'zi paydo bo'ladi.
  // Namuna: { xizmat:'montaj', kim:'Alisher A.', joy:'Buxoro', matn:'...' }
  const XIZMAT_SHARHLAR = [];

  const XZ_MATN = {
    loyiha: {
      sarlavha: 'Loyihalashtirish',
      tavsif: "Muhandislar gaz tizimini ob'ektingizga moslab loyihalaydi, kerakli hujjat va ruxsatnomalarni tayyorlaydi.",
      xizmatlar: [
        ['fa-file-lines', 'Texnik loyiha', "Quvur yo'nalishi, hisob-kitob va chizmalar tayyorlanadi."],
        ['fa-stamp', 'Ruxsatnomalar', 'Tegishli davlat idoralaridan ruxsat olish jarayoni.'],
        ['fa-magnifying-glass', 'Ekspertiza', 'Loyiha xavfsizlik ekspertizasidan o\'tkaziladi.'],
        ['fa-cube', '3D modellashtirish', 'Tizimni ishga tushirishdan oldin vizual ko\'rish imkoniyati.']
      ],
      jarayon: ["So'rov va dastlabki maslahat", "Ob'ektni o'lchash", 'Loyiha ishlab chiqish',
                '3D model taqdimoti', 'Ekspertiza va ruxsatnoma olish']
    },
    montaj: {
      sarlavha: 'Montaj qilish',
      tavsif: 'Litsenziyalangan ustalar ichki tarmoqdan magistral quvurgacha to\'liq montaj ishlarini bajaradi.',
      xizmatlar: [
        ['fa-house', 'Ichki tarmoqlar', 'Uy ichida quvur tortish, plita va qozonga ulash.'],
        ['fa-road', 'Magistral quvurlar', "Ko'chadan uygacha yer osti quvur tortish."],
        ['fa-gauge', 'Hisoblagichlar', "O'rnatish, plombalash va ro'yxatga olish."],
        ['fa-triangle-exclamation', 'Xavfsizlik tizimlari', 'Sizib chiqishni aniqlovchi sensor va klapan.']
      ],
      jarayon: ["So'rov qabul qilish", "Ob'ektni ko'rikdan o'tkazish", 'Montaj ishlari', 'Sinov va topshirish']
    },
    servis: {
      sarlavha: 'Servis xizmatlar',
      tavsif: "O'rnatilgan tizimni doimiy nazorat ostida ushlab turadi, muammoni tezkor bartaraf qiladi.",
      xizmatlar: [
        ['fa-calendar-check', 'Davriy tekshiruv', 'Rejalashtirilgan texnik ko\'rik va profilaktika.'],
        ['fa-screwdriver-wrench', "Ta'mirlash", 'Nosozlikni bartaraf etish, ehtiyot qismlar almashtirish.'],
        ['fa-headset', '24/7 tez yordam', 'Favqulodda holatlar uchun issiq liniya.'],
        ['fa-shield-halved', 'Kafolat xizmati', "Kafolat muddatida bepul ta'mirlash."]
      ],
      jarayon: ['Chaqiruv yoki shartnoma', "Ob'ektni diagnostika qilish", 'Ishlarni bajarish', 'Dalolatnoma va kafolat']
    }
  };

  function xzOynaHtml(kalit) {
    const d = XZ_MATN[kalit];
    const sharhlar = XIZMAT_SHARHLAR.filter(x => x.xizmat === kalit);

    const tablar = [['xizmat', 'Xizmat turlari'], ['jarayon', 'Jarayon']];
    if (kalit === 'loyiha') tablar.push(['ariza', 'Ariza berish']);
    if (sharhlar.length) tablar.push(['sharh', 'Sharhlar']);

    return `
      <div class="xz-intro">
        <h3>${d.sarlavha}</h3>
        <p>${d.tavsif}</p>
      </div>
      <div class="xz-tabs" role="tablist">
        ${tablar.map((t, i) => `<button class="xz-tab" role="tab" aria-selected="${i === 0}"
            data-h-click="c:xzTab" data-a-click="${SG_A([String(kalit), String(t[0]), '@this'])}">${t[1]}</button>`).join('')}
      </div>

      <div class="xz-pane" data-xz="xizmat">
        ${d.xizmatlar.map(x => `<div class="xz-feature"><i class="fas ${x[0]}"></i>
          <div><h4>${x[1]}</h4><p>${x[2]}</p></div></div>`).join('')}
      </div>

      <div class="xz-pane" data-xz="jarayon" hidden>
        ${d.jarayon.map((q, i) => `<div class="xz-step"><span class="xz-step-num">${i + 1}</span><p>${q}</p></div>`).join('')}
      </div>

      ${kalit === 'loyiha' ? `<div class="xz-pane" data-xz="ariza" hidden>
        <p style="font-size:14px;line-height:1.6;color:var(--text-color);margin-bottom:16px">
          Loyiha arizasi bosqichma-bosqich to'ldiriladi: texnik shart holati, manzil va telefon tasdig'i.
        </p>
        <button class="xz-cta" data-h-click="h217">Arizani boshlash</button>
      </div>` : ''}

      ${sharhlar.length ? `<div class="xz-pane" data-xz="sharh" hidden>
        ${sharhlar.map(f => `<div class="rz-fikr" style="margin-bottom:12px">
          <blockquote>${f.matn}</blockquote>
          <footer>${f.kim}<span class="rz-fikr-joy"> — ${f.joy}</span></footer></div>`).join('')}
      </div>` : ''}

      ${kalit !== 'loyiha' ? `<button class="xz-cta" style="margin-top:8px"
        data-h-click="h253">
        Ariza qoldirish
      </button>` : ''}
    `;
  }

  function xzTab(kalit, tab, btn) {
    const oyna = btn.closest('#modalContent');
    oyna.querySelectorAll('.xz-tab').forEach(b => b.setAttribute('aria-selected', b === btn));
    oyna.querySelectorAll('.xz-pane').forEach(p => { p.hidden = p.dataset.xz !== tab; });
  }

  function openRezervuarPage() {
    rezGalereyaChiz();
    const el = document.getElementById('rezervuar-page');
    el.classList.remove('hidden');
    el.scrollTop = 0;
    document.body.style.overflow = 'hidden';
  }
  function closeRezervuarPage() {
    document.getElementById('rezervuar-page').classList.add('hidden');
    if (document.getElementById('lpg-page').classList.contains('hidden')) {
      document.body.style.overflow = '';
    }
  }

  function openBalonPage() {
    document.getElementById('balon-page').classList.remove('hidden');
    document.getElementById('balon-page').scrollTop = 0;
    document.body.style.overflow = 'hidden';
  }
  function closeBalonPage() {
    document.getElementById('balon-page').classList.add('hidden');
    // Ostidagi LPG sahifasi ochiq bo'lsa, skroll qulfi saqlanadi
    if (document.getElementById('lpg-page').classList.contains('hidden')) {
      document.body.style.overflow = '';
    }
  }
  // Buyurtma formasi faqat shu oynada yashaydi (sahifada takrorlanmaydi).
  function openBuyurtmaOyna(_, tur) {
    const forma = document.getElementById('lpg-buyurtma-form');
    forma.reset();

    if (tur === 'rezervuar') {
      forma.querySelector('select').value = "Rezervuarli tizim o'rnatish";
    }

    const oyna = document.getElementById('buyurtma-oyna');
    if (oyna.parentElement !== document.body) document.body.appendChild(oyna);
    oyna.classList.remove('hidden');
    oyna.classList.add('flex');
    document.body.style.overflow = 'hidden';
    forma.querySelector('input').focus();
  }

  function closeBuyurtmaOyna() {
    const oyna = document.getElementById('buyurtma-oyna');
    oyna.classList.add('hidden');
    oyna.classList.remove('flex');
    // Ostida boshqa to'liq ekranli sahifa ochiq bo'lsa, skroll qulfi qoladi
    const ochiq = ['balon-page', 'lpg-page'].some(id => !document.getElementById(id).classList.contains('hidden'));
    if (!ochiq) document.body.style.overflow = '';
  }

  // Suyultirilgan gaz bo'limi hozircha mijoz va xodimlar uchun yopiq ("Tez orada").
  // Ochish uchun: LPG_OCHIQ = true  (va yuqoridagi tugmadan `disabled` ni olib tashlang).
  const LPG_OCHIQ = false;
  function openLpgPage() {
    if (!LPG_OCHIQ) { showToast("Suyultirilgan gaz bo'limi tez orada ishga tushadi"); return; }
    document.getElementById('lpg-page').classList.remove('hidden');
    document.body.style.overflow = 'hidden';
  }
  function closeLpgPage() {
    document.getElementById('lpg-page').classList.add('hidden');
    document.body.style.overflow = '';
  }

  function openGarelkaPage() {
    document.getElementById('garelka-page').classList.remove('hidden');
    document.body.style.overflow = 'hidden';
    document.getElementById('grl-filter-wrap').classList.remove('hidden');
    grlRender();
  }
  function closeGarelkaPage() {
    document.getElementById('garelka-page').classList.add('hidden');
    document.body.style.overflow = '';
  }

  function grlQty(btn, delta, price) {
    const card = btn.closest('.rounded-2xl');
    const inp = card.querySelector('.grl-qty');
    const tot = card.querySelector('.grl-total');
    let v = Math.max(1, Math.min(99, parseInt(inp.value||1) + delta));
    inp.value = v;
    tot.textContent = 'Jami: ' + (price * v).toLocaleString('uz-UZ') + ' so\'m';
  }
  function grlQtyInput(inp, price) {
    let v = Math.max(1, Math.min(99, parseInt(inp.value)||1));
    inp.value = v;
    const card = inp.closest('.rounded-2xl');
    card.querySelector('.grl-total').textContent = 'Jami: ' + (price * v).toLocaleString('uz-UZ') + ' so\'m';
  }

  function grlOrder(btn, name, price) {
    const card = btn.closest('.rounded-2xl');
    const qty = parseInt(card.querySelector('.grl-qty').value)||1;
    cartAdd(name, price, qty, { ikona: 'fa-fire', rang: '#ff8a00' });
    const orig = btn.innerHTML;
    btn.innerHTML = '<i class="fas fa-check mr-1.5"></i>Qo\'shildi!';
    btn.style.background = 'linear-gradient(135deg,#1a5c1a,#22a022)';
    btn.style.color = '#fff';
    btn.disabled = true;
    setTimeout(() => {
      btn.innerHTML = orig;
      btn.style.background = 'linear-gradient(135deg,#8b7018,#ff8a00)';
      btn.style.color = '#0a0a06';
      btn.disabled = false;
    }, 2000);
    const label = qty > 1 ? `${name} ×${qty}` : name;
    showToast(label + ' savatga qo\'shildi!');
  }

  function grlInfo(id) {
    const data = grlLoadData();
    const g = data.find(x => x.id === id);
    if (!g) return;
    const ks = grlKatStyle(g.kat);
    const narxStr = g.narx.toLocaleString('uz-UZ');
    const overlay = document.getElementById('grl-info-overlay');
    document.getElementById('grl-info-body').innerHTML = `
      <div class="flex flex-col gap-5">
        <!-- Rasm -->
        <div class="rounded-2xl flex items-center justify-center overflow-hidden" style="height:200px;background:rgba(150,195,245,0.04);border:1px solid rgba(120,170,235,0.2)">
          <div class="flex flex-col items-center gap-2" style="color:rgba(120,170,235,0.25)">
            <svg width="56" height="56" viewBox="0 0 24 24" fill="currentColor"><path d="M12 9a3 3 0 1 0 0 6 3 3 0 0 0 0-6zm0-2a5 5 0 1 1 0 10A5 5 0 0 1 12 7zm-1-4h2l1.5 2H19a1 1 0 0 1 1 1v11a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V6a1 1 0 0 1 1-1h4.5L11 3z"/></svg>
            <span style="font-size:10px;letter-spacing:.18em;font-weight:700">RASM</span>
          </div>
        </div>
        <!-- Sarlavha -->
        <div>
          <div class="flex items-center gap-2 mb-1 flex-wrap">
            <span class="text-[10px] font-black uppercase tracking-widest px-2.5 py-1 rounded-full" style="background:${ks.bg};color:${ks.color};border:1px solid ${ks.border}">${g.kat}</span>
            ${g.mashhur ? `<span class="text-[10px] font-black uppercase tracking-widest px-2.5 py-1 rounded-full" style="background:rgba(184,142,20,0.2);color:#0d6efd;border:1px solid rgba(110,165,230,0.45)">★ TOP mahsulot</span>` : ''}
          </div>
          <h2 class="font-black text-ink-900 leading-snug" style="font-size:22px">${g.nom}</h2>
        </div>
        <!-- Xususiyatlar grid -->
        <div class="grid grid-cols-2 gap-3">
          <div class="rounded-xl p-3" style="background:rgba(120,170,235,0.06);border:1px solid rgba(120,170,235,0.18)">
            <div class="text-[10px] uppercase tracking-widest mb-1" style="color:#3d7ab5">Quvvat</div>
            <div class="font-black text-lg" style="color:#0d6efd">${g.quvvat}</div>
          </div>
          <div class="rounded-xl p-3" style="background:rgba(120,170,235,0.06);border:1px solid rgba(120,170,235,0.18)">
            <div class="text-[10px] uppercase tracking-widest mb-1" style="color:#3d7ab5">Kategoriya</div>
            <div class="font-black text-lg" style="color:${ks.color}">${g.kat}</div>
          </div>
          <div class="rounded-xl p-3 col-span-2" style="background:rgba(120,170,235,0.06);border:1px solid rgba(120,170,235,0.18)">
            <div class="text-[10px] uppercase tracking-widest mb-1" style="color:#3d7ab5">Narx</div>
            <div class="font-black" style="font-size:28px;background:linear-gradient(135deg,#0d6efd,#0d6efd);-webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text">${narxStr} <span style="font-size:14px;-webkit-text-fill-color:#3d7ab5">so'm</span></div>
          </div>
        </div>
        <!-- Tavsif -->
        <div class="rounded-xl p-4" style="background:rgba(31,72,135,0.03);border:1px solid rgba(31,72,135,0.07)">
          <div class="text-[10px] uppercase tracking-widest mb-2 font-bold" style="color:#3d7ab5">Tavsif</div>
          <p class="text-sm leading-relaxed" style="color:#4a7fae">${g.tavsif}</p>
        </div>
        <!-- ID -->
        <div class="text-right text-xs" style="color:#3a3020">Mahsulot ID: #${g.id}</div>
      </div>`;
    overlay.classList.remove('hidden');
    overlay.classList.add('flex');
  }

  function grlInfoClose() {
    const overlay = document.getElementById('grl-info-overlay');
    overlay.classList.add('hidden');
    overlay.classList.remove('flex');
  }

  // Garelkalar CRUD olib tashlandi — mahsulotlar Django admin panelida boshqariladi


  // Suyultirilgan gaz form
  function submitLpg(e) {
    e.preventDefault();
    showToast('Buyurtmangiz qabul qilindi! 2 soat ichida bog\'lanamiz.');
    e.target.reset();
  }

  // Metrologiya: xizmat kartasi tafsiloti
  const METRO_XIZMATLAR = {
    kalibrovka: {
      forma: "Kalibrovka", ikon: "fa-sliders-h", nom: "Kalibrovka",
      qisqa: "Hisoblagich ko'rsatkichlarini etalon bo'yicha tekshirib, standart talablariga moslab sozlash va xatolik darajasini aniqlash.",
      qachon: ["Hisoblagich ko'rsatkichi haqiqiy sarfdan farq qilsa", "Sarf bilan hisob-kitob summasi o'rtasida shubha tug'ilsa", "Hisoblagich ta'mirdan yoki ko'chirishdan keyin", "Sanoat va tijorat hisobi uchun aniqlik kerak bo'lsa"],
      kiradi: ["Hisoblagichni tashqi ko'rikdan o'tkazish", "Hozirgi xatolikni etalon qurilmada o'lchash", "Ko'rsatkichlarni standartga moslab sozlash", "Sozlashdan keyingi nazorat o'lchovi", "Kalibrovka natijalari protokoli"],
      hujjat: ["Hisoblagich pasporti", "Model va seriya raqami", "Murojaat sababi (ko'rsatkichlar farqi va h.k.)", "Egasining pasporti yoki korxona rekvizitlari"],
      jarayon: ["Ariza qoldirasiz", "Hisoblagich qabul qilinadi", "O'lchash va sozlash", "Protokol bilan qaytariladi"],
      muddat: "1–2 ish kuni", natija: "Kalibrovka protokoli / sertifikati",
      izoh: "Har qanday model uchun bajariladi. Ultratovush va G40+ sanoat modellari alohida kelishiladi.",
      // 4 ta tugma: har biri alohida oynada ochiladi (metroBolimOch)
      bolimlar: {
        qachon: {
          tugma: "Qachon kerak?", ikon: "fa-circle-question",
          sarlavha: "Kalibrovka qachon kerak?",
          kirish: "Quyidagi holatlarning birortasi sizda uchrasa, hisoblagichni kalibrovka qildirish tavsiya etiladi:",
          elementlar: [
            ["Ko'rsatkich haqiqiy sarfdan farq qilsa", "Gazdan foydalanish odatdagidek, lekin hisoblagich ko'rsatkichi keskin oshib yoki kamayib ketgan bo'lsa."],
            ["Hisob-kitob summasiga shubha tug'ilsa", "Oylik to'lov sarfga mos kelmasa, hisoblagichning aniqligi tekshirib ko'riladi."],
            ["Ta'mir yoki ko'chirishdan keyin", "Hisoblagich ajratilgan, boshqa joyga o'rnatilgan yoki ta'mirlangan bo'lsa, ko'rsatkichlari qayta tekshiriladi."],
            ["Sanoat va tijorat hisobi uchun", "Gaz sarfi bo'yicha pul hisob-kitob qilinadigan joylarda yuqori aniqlik talab qilinadi."]
          ]
        },
        kiradi: {
          tugma: "Nimalar kiradi?", ikon: "fa-list-check",
          sarlavha: "Xizmatga nimalar kiradi?",
          kirish: "Kalibrovka xizmati doirasida quyidagi ishlar bajariladi:",
          elementlar: [
            ["Tashqi ko'rik", "Hisoblagich korpusi, plombasi, ko'rsatkich oynasi va ulanish joylari ko'zdan kechiriladi."],
            ["Hozirgi xatolikni o'lchash", "Hisoblagich etalon qurilmada sinaladi va ko'rsatkichdagi xatolik darajasi aniqlanadi."],
            ["Ko'rsatkichlarni sozlash", "Xatolik me'yordan chiqqan bo'lsa, hisoblagich standart talablariga moslab sozlanadi."],
            ["Nazorat o'lchovi", "Sozlashdan keyin natija to'g'riligi qayta o'lchab tasdiqlanadi."],
            ["Protokol rasmiylashtirish", "O'lchash natijalari kalibrovka protokoliga yoziladi va sizga topshiriladi."]
          ]
        },
        hujjat: {
          tugma: "Kerakli hujjatlar", ikon: "fa-file-alt",
          sarlavha: "Kerakli hujjatlar",
          kirish: "Hisoblagichni topshirishda quyidagi hujjat va ma'lumotlarni tayyorlang:",
          elementlar: [
            ["Hisoblagich pasporti", "Qurilma bilan birga berilgan texnik pasport."],
            ["Model va seriya raqami", "Hisoblagich korpusida yoki pasportida yozilgan (masalan, G4, UZ20241234)."],
            ["Murojaat sababi", "Nima sababdan kalibrovka kerakligini qisqa yozing: ko'rsatkichlar farqi, ta'mirdan keyin va hokazo."],
            ["Shaxsni tasdiqlovchi hujjat", "Jismoniy shaxs uchun egasining pasporti, korxona uchun rekvizitlari."]
          ],
          izoh: "Biror hujjat yetishmasa, arizani baribir qoldiring: qaysi hujjat kerakligini mutaxassis aniqlashtiradi."
        },
        jarayon: {
          tugma: "Jarayon", ikon: "fa-route",
          sarlavha: "Kalibrovka jarayoni",
          kirish: "Ariza qoldirishdan natijani olishgacha 4 bosqich:",
          qadamlar: [
            ["Ariza qoldirasiz", "Saytdagi formani to'ldirasiz: ism, telefon, hisoblagich modeli va seriya raqami. Arizangiz raqami SMS orqali yuboriladi."],
            ["Hisoblagich qabul qilinadi", "Mutaxassis siz bilan bog'lanib, hisoblagichni topshirish usulini kelishadi. Qabul paytida tashqi ko'rik o'tkaziladi."],
            ["O'lchash va sozlash", "Hisoblagich etalon qurilmada sinaladi, kerak bo'lsa sozlanadi va nazorat o'lchovidan o'tkaziladi."],
            ["Protokol bilan qaytariladi", "Hisoblagich kalibrovka protokoli bilan birga sizga qaytariladi."]
          ]
        }
      }
    },
    almashtirish: {
      forma: "Almashtirish", ikon: "fa-exchange-alt", nom: "Almashtirish",
      qisqa: "Muddati o'tgan, buzilgan yoki ko'rikdan o'tmagan hisoblagichni yangisiga almashtirib, plombalab topshirish.",
      qachon: ["Hisoblagichning ko'rik muddati o'tib ketgan bo'lsa", "Hisoblagich buzilgan yoki ko'rsatkichi yurmasa", "Hisoblagich eskirgan yoki ta'mirga yaroqsiz bo'lsa", "Quvvati kamlik qilsa (kattaroq modelga o'tish kerak bo'lsa)"],
      kiradi: ["Mos hisoblagichni tanlashda maslahat", "Eskisini demontaj qilish", "Yangisini o'rnatish va ulash", "Ulanishlar germetikligini tekshirish", "Plombalash va almashtirish dalolatnomasi"],
      hujjat: ["Eski hisoblagich ma'lumotlari (model, seriya)", "Abonent (hisob) raqami", "Manzil va egasining pasporti", "Yangi hisoblagich pasporti (u bizdan olinsa, beriladi)"],
      jarayon: ["Ariza qoldirasiz", "Mutaxassis manzilga boradi", "Almashtirish bajariladi", "Dalolatnoma va plomba topshiriladi"],
      muddat: "Kelishuv bo'yicha (odatda 1 kun)", natija: "Almashtirish dalolatnomasi, yangi hisoblagich pasporti",
      izoh: "Hisoblagich xaridi Xaridlar bo'limidagi katalog orqali ham mumkin.",
      // 4 ta tugma: har biri alohida oynada ochiladi (metroBolimOch)
      bolimlar: {
        qachon: {
          tugma: "Qachon kerak?", ikon: "fa-circle-question",
          sarlavha: "Almashtirish qachon kerak?",
          kirish: "Hisoblagichni almashtirish quyidagi hollarda kerak bo'ladi:",
          elementlar: [
            ["Ko'rik muddati o'tib ketgan bo'lsa", "Hisoblagichning qiyoslov muddati tugagan va u qayta qiyoslanmagan bo'lsa."],
            ["Hisoblagich buzilgan yoki ko'rsatkichi yurmasa", "Raqamlar o'zgarmayotgan, ko'rsatkich oynasi xira yoki mexanizm to'xtab qolgan bo'lsa."],
            ["Eskirgan yoki ta'mirga yaroqsiz bo'lsa", "Ta'mirlash o'zini oqlamasa yoki ehtiyot qism topilmasa."],
            ["Quvvati kamlik qilsa", "Gaz sarfi oshib, hozirgi hisoblagich yetmay qolsa, kattaroq modelga o'tish kerak bo'ladi."]
          ]
        },
        kiradi: {
          tugma: "Nimalar kiradi?", ikon: "fa-list-check",
          sarlavha: "Xizmatga nimalar kiradi?",
          kirish: "Almashtirish xizmati doirasida quyidagi ishlar bajariladi:",
          elementlar: [
            ["Mos hisoblagichni tanlash bo'yicha maslahat", "Sarfingizga qarab qaysi modelning mos kelishini mutaxassis tushuntiradi."],
            ["Eskisini demontaj qilish", "Eski hisoblagich gaz quvuridan xavfsiz ajratib olinadi."],
            ["Yangisini o'rnatish va ulash", "Yangi hisoblagich joyiga o'rnatilib, quvurga ulanadi."],
            ["Ulanishlar germetikligini tekshirish", "Ulanish joylarida gaz sizib chiqmasligi tekshiriladi."],
            ["Plombalash va dalolatnoma", "Hisoblagich plombalanadi va almashtirish dalolatnomasi rasmiylashtiriladi."]
          ]
        },
        hujjat: {
          tugma: "Kerakli hujjatlar", ikon: "fa-file-alt",
          sarlavha: "Kerakli hujjatlar",
          kirish: "Almashtirish uchun quyidagi hujjat va ma'lumotlarni tayyorlang:",
          elementlar: [
            ["Eski hisoblagich ma'lumotlari", "Model va seriya raqami, oxirgi ko'rsatkich."],
            ["Abonent (hisob) raqami", "Gaz ta'minoti bo'yicha shaxsiy hisob raqamingiz."],
            ["Manzil va egasining pasporti", "Hisoblagich o'rnatilgan manzil va egasining shaxsini tasdiqlovchi hujjat."],
            ["Yangi hisoblagich pasporti", "Yangi hisoblagich bizdan olinsa, pasporti o'zimiz tomonidan beriladi."]
          ]
        },
        jarayon: {
          tugma: "Jarayon", ikon: "fa-route",
          sarlavha: "Almashtirish jarayoni",
          kirish: "Ariza qoldirishdan topshirishgacha 4 bosqich:",
          qadamlar: [
            ["Ariza qoldirasiz", "Saytdagi formani to'ldirasiz: ism, telefon, eski hisoblagich modeli va seriya raqami. Ariza raqami SMS orqali yuboriladi."],
            ["Mutaxassis manzilga boradi", "Mutaxassis siz bilan bog'lanib, kelish vaqtini kelishadi va manzilga keladi."],
            ["Almashtirish bajariladi", "Eski hisoblagich olinadi, yangisi o'rnatilib, ulanishlar tekshiriladi."],
            ["Dalolatnoma va plomba topshiriladi", "Almashtirish dalolatnomasi, yangi hisoblagich pasporti va plomba sizga topshiriladi."]
          ]
        }
      }
    },
    qiyoslov: {
      forma: "Davlat qiyoslov ko'rigi", ikon: "fa-stamp", nom: "Davlat qiyoslov ko'rigi",
      qisqa: "Hisoblagichning o'lchash aniqligini davlat etaloni bilan solishtirib, undan foydalanishga yaroqliligini rasman tasdiqlash.",
      qachon: ["Hisoblagichning qiyoslov muddati tugagan yoki tugayotgan bo'lsa", "Yangi hisoblagichni birlamchi qiyoslashda", "Ta'mirdan keyin qayta qiyoslash kerak bo'lsa", "Gaz ta'minoti tashkiloti guvohnoma talab qilsa"],
      kiradi: ["Hisoblagichni tashqi ko'rikdan o'tkazish", "Aniqlik (xatolik) sinovi etalon qurilmada", "Yaroqli hisoblagichga muhr qo'yish", "Qiyoslov guvohnomasini rasmiylashtirish"],
      hujjat: ["Hisoblagich pasporti", "Oldingi qiyoslov guvohnomasi (bo'lsa)", "Egasining pasporti yoki korxona rekvizitlari"],
      jarayon: ["Ariza qoldirasiz", "Hisoblagich qabul qilinadi", "Laboratoriyada qiyoslanadi", "Guvohnoma va muhr topshiriladi"],
      muddat: "1–5 ish kuni (modelga qarab)", natija: "Qiyoslov guvohnomasi va muhr",
      izoh: "Qiyoslov davriyligi: G4 — 4 yilda 1 marta, G6–G10 — 2 yilda 1 marta, G16 va undan katta — yiliga 1 marta.",
      // 4 ta tugma: har biri alohida oynada ochiladi (metroBolimOch)
      bolimlar: {
        qachon: {
          tugma: "Qachon kerak?", ikon: "fa-circle-question",
          sarlavha: "Davlat qiyoslov ko'rigi qachon kerak?",
          kirish: "Davlat qiyoslov ko'rigi quyidagi hollarda o'tkaziladi:",
          elementlar: [
            ["Qiyoslov muddati tugagan yoki tugayotgan bo'lsa", "Hisoblagich o'z davriy ko'rik muddatiga yetgan bo'lsa."],
            ["Yangi hisoblagichni birlamchi qiyoslashda", "Yangi o'rnatiladigan hisoblagich foydalanishdan oldin qiyoslanishi kerak bo'lsa."],
            ["Ta'mirdan keyin", "Hisoblagich ta'mirlangan bo'lsa, uning aniqligi qayta qiyoslab tasdiqlanadi."],
            ["Gaz ta'minoti tashkiloti guvohnoma talab qilsa", "Tashkilot hisoblagichning yaroqliligini tasdiqlovchi hujjat so'raganda."]
          ]
        },
        kiradi: {
          tugma: "Nimalar kiradi?", ikon: "fa-list-check",
          sarlavha: "Xizmatga nimalar kiradi?",
          kirish: "Qiyoslov ko'rigi doirasida quyidagi ishlar bajariladi:",
          elementlar: [
            ["Tashqi ko'rik", "Hisoblagich korpusi, plombasi va ko'rsatkich oynasi ko'zdan kechiriladi."],
            ["Aniqlik (xatolik) sinovi", "Hisoblagich etalon qurilmada sinalib, o'lchash xatoligi aniqlanadi."],
            ["Yaroqli hisoblagichga muhr", "Sinovdan o'tgan hisoblagichga qiyoslov muhri qo'yiladi."],
            ["Qiyoslov guvohnomasini rasmiylashtirish", "Natija qiyoslov guvohnomasiga yoziladi va sizga topshiriladi."]
          ]
        },
        hujjat: {
          tugma: "Kerakli hujjatlar", ikon: "fa-file-alt",
          sarlavha: "Kerakli hujjatlar",
          kirish: "Qiyoslov uchun quyidagi hujjat va ma'lumotlarni tayyorlang:",
          elementlar: [
            ["Hisoblagich pasporti", "Qurilma bilan birga berilgan texnik pasport."],
            ["Oldingi qiyoslov guvohnomasi", "Agar ilgari qiyoslangan bo'lsa."],
            ["Shaxsni tasdiqlovchi hujjat", "Jismoniy shaxs uchun egasining pasporti, korxona uchun rekvizitlari."]
          ]
        },
        jarayon: {
          tugma: "Jarayon", ikon: "fa-route",
          sarlavha: "Qiyoslov ko'rigi jarayoni",
          kirish: "Ariza qoldirishdan guvohnomani olishgacha 4 bosqich:",
          qadamlar: [
            ["Ariza qoldirasiz", "Saytdagi formani to'ldirasiz: ism, telefon, hisoblagich modeli va seriya raqami. Ariza raqami SMS orqali yuboriladi."],
            ["Hisoblagich qabul qilinadi", "Mutaxassis siz bilan bog'lanib, hisoblagichni topshirish usulini kelishadi va tashqi ko'rikdan o'tkazadi."],
            ["Laboratoriyada qiyoslanadi", "Hisoblagich etalon qurilmada sinaladi va yaroqliligi aniqlanadi."],
            ["Guvohnoma va muhr topshiriladi", "Yaroqli hisoblagich muhrlanib, qiyoslov guvohnomasi bilan sizga qaytariladi."]
          ]
        }
      }
    }
  };

  // Strelka tugmalari bilan kartalar orasida yurish
  function metroTabKlavisha(e) {
    const kalitlar = Object.keys(METRO_XIZMATLAR);
    const joriy = document.activeElement && document.activeElement.dataset ? kalitlar.indexOf(document.activeElement.dataset.metro) : -1;
    if (joriy < 0) return;
    let yangi = joriy;
    if (e.key === 'ArrowDown') yangi = (joriy + 1) % kalitlar.length;
    else if (e.key === 'ArrowUp') yangi = (joriy - 1 + kalitlar.length) % kalitlar.length;
    else if (e.key === 'Home') yangi = 0;
    else if (e.key === 'End') yangi = kalitlar.length - 1;
    else return;
    e.preventDefault();
    document.getElementById('metro-kart-' + kalitlar[yangi]).focus();
  }

  // ---- Ikki bosqichli oyna.
  // 1-oyna ("Batafsil" bosilganda): xizmat nomi, qisqa tavsif va bo'limlar tugmalari USTUN shaklida.
  // 2-oyna (tugma bosilganda): tanlangan bo'lim (Qachon kerak / Nimalar kiradi / Kerakli hujjatlar /
  // Jarayon / Ulgurji narx / Aholi narx). Orqaga tugmasi 1-oynaga qaytaradi.
  // Narxlar serverdan o'qiladi (/api/narxnoma/metrologiya/, faqat o'qish) — kodda narx yozilmagan.
  let _metroOynaOldingi = null, _metroSektOldingi = null, _metroJoriy = null;
  let _metroNarxlar = null, _metroNarxSorov = null;

  // Serverdan kelgan har qanday matn HTML'ga qo'yishdan oldin tozalanadi (XSS himoyasi)
  const metroEsc = t => String(t == null ? '' : t).replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  const metroPul = n => String(Math.round(Number(n))).replace(/\B(?=(\d{3})+(?!\d))/g, ' ');

  function metroNarxYukla() {
    if (_metroNarxlar) return Promise.resolve(_metroNarxlar);
    if (!_metroNarxSorov) {
      _metroNarxSorov = fetch(API + '/narxnoma/metrologiya/', { headers: { 'Accept': 'application/json' }, credentials: 'omit' })
        .then(r => { if (!r.ok) throw new Error('HTTP ' + r.status); return r.json(); })
        .then(j => (_metroNarxlar = j))
        .catch(e => { _metroNarxSorov = null; throw e; });
    }
    return _metroNarxSorov;
  }

  const METRO_NARX_NOM = { ulgurji: "Ulgurji iste'molchilar uchun narxlar", aholi: 'Aholi uchun narxlar' };

  function metroNarxHTML(kalit, tarmoq, j) {
    const t = j && j[tarmoq];
    const qatorlar = (t && t.xizmatlar && t.xizmatlar[kalit]) || [];
    const bosh = tarmoq === 'ulgurji'
      ? "Bu xizmat uchun ulgurji narxnomada alohida narx yo'q. Narx kelishuv bo'yicha: ariza qoldiring, mutaxassis narxni aytadi."
      : "Aholi uchun bu xizmatning narxi hozircha kiritilmagan. Ariza qoldiring, mutaxassis narxni aytadi.";
    if (!qatorlar.length) {
      return '<div class="rounded-xl p-4 text-sm" style="background:#f1f7ff;border:1px dashed rgba(13,110,253,0.35);color:#5b7fa6"><i class="fas fa-circle-info mr-2" style="color:#0d6efd"></i>' + bosh + '</div>';
    }
    const narx = q => q.narx_gacha != null ? metroPul(q.narx_dan) + ' – ' + metroPul(q.narx_gacha) : metroPul(q.narx_dan);
    const royxat = qatorlar.map(q =>
      '<li class="flex items-start gap-3 rounded-xl p-3.5" style="background:#f1f7ff;border:1px solid rgba(120,170,235,0.18)">' +
      '<div class="min-w-0 flex-1"><div class="font-bold text-sm text-ink-900">' + metroEsc(q.nomi) + '</div>' +
      (q.izoh ? '<div class="text-xs mt-0.5" style="color:#5b7fa6">' + metroEsc(q.izoh) + '</div>' : '') + '</div>' +
      '<div class="text-right shrink-0"><div class="font-black text-sm" style="color:#0d6efd">' + narx(q) + '</div><div class="text-[11px]" style="color:#5b7fa6">so\'m</div></div></li>').join('');
    const eslatma = String((t && t.eslatma) || '').split('\n').map(x => x.trim()).filter(Boolean)
      .map(x => '<p class="text-xs mt-1.5" style="color:#5b7fa6">' + metroEsc(x) + '</p>').join('');
    const izoh = tarmoq === 'aholi' ? '<p class="text-xs mt-3" style="color:#5b7fa6">Ro\'yxatda yo\'q ishlarning narxini ariza qoldirganda mutaxassis aytadi.</p>' : '';
    return (tarmoq === 'ulgurji' ? '<p class="text-xs mb-3" style="color:#5b7fa6">Bitta gaz hisoblagich hisobida narx</p>' : '') +
      '<ul class="space-y-2.5">' + royxat + '</ul>' +
      (eslatma ? '<div class="mt-3"><i class="fas fa-info-circle mr-1.5" style="color:#0d6efd"></i>' + eslatma + '</div>' : '') + izoh;
  }

  // ----- 1-oyna: xizmat va bo'limlar tugmalari (ustun)
  function metroXizmatOch(kalit, tugma) {
    const x = METRO_XIZMATLAR[kalit], bl = x && x.bolimlar;
    const oyna = document.getElementById('metro-bolim-oyna');
    if (!x || !bl || !oyna) return;
    if (oyna.classList.contains('hidden')) _metroOynaOldingi = tugma || document.activeElement;
    const chip = (ikon, yorliq, qiymat) => '<div class="rounded-xl p-3.5 flex items-center gap-3" style="background:#f1f7ff;border:1px solid rgba(120,170,235,0.18)"><i class="fas ' + ikon + '" style="color:#0d6efd"></i><div class="min-w-0"><div class="text-[11px] uppercase tracking-wide" style="color:#5b7fa6">' + yorliq + '</div><div class="font-bold text-sm text-ink-900">' + qiymat + '</div></div></div>';
    const tugmalar = ['qachon', 'kiradi', 'hujjat', 'jarayon'].map(k => [k, bl[k].ikon, bl[k].tugma])
      .concat([['ulgurji', 'fa-building', 'Ulgurji narx'], ['aholi', 'fa-house-user', 'Aholi narx']]).map(t =>
        '<button type="button" data-h-click="c:metroBolimOch" data-a-click="' + SG_A([kalit, t[0], '@this']) + '" aria-haspopup="dialog" class="metro-bolim-tugma w-full rounded-xl p-4 flex items-center gap-3 text-left transition-all active:scale-[.98]">' +
        '<span class="metro-bolim-ikon w-10 h-10 rounded-xl flex items-center justify-center shrink-0"><i class="fas ' + t[1] + '"></i></span>' +
        '<span class="font-bold text-sm flex-1">' + t[2] + '</span>' +
        '<i class="metro-bolim-strelka fas fa-chevron-right text-[11px]"></i></button>').join('');
    document.getElementById('metro-bolim-sarlavha').textContent = x.nom;
    document.getElementById('metro-bolim-ikon').className = 'fas ' + x.ikon + ' text-oq';
    document.getElementById('metro-bolim-ichi').innerHTML =
      '<p class="text-sm mb-5" style="color:#5b7fa6">' + x.qisqa + '</p>' +
      '<div class="text-xs font-bold uppercase tracking-wide mb-2.5" style="color:#5b7fa6">Bo\'limni tanlang</div>' +
      '<div class="space-y-2.5">' + tugmalar + '</div>' +
      '<div class="grid sm:grid-cols-2 gap-2.5 mt-6">' + chip('fa-clock', 'Muddat', x.muddat) + chip('fa-award', 'Natija', x.natija) + '</div>' +
      '<p class="text-xs mt-3" style="color:#5b7fa6"><i class="fas fa-info-circle mr-1.5" style="color:#0d6efd"></i>' + x.izoh + '</p>' +
      '<div class="flex flex-col sm:flex-row gap-2.5 mt-6">' +
      '<button type="button" data-h-click="c:metroOynaYopArizaga" data-a-click="' + SG_A([kalit]) + '" class="font-bold px-5 py-3 rounded-xl text-sm text-oq flex-1" style="background:linear-gradient(135deg,#ff8a00,#ff8a00)"><i class="fas fa-paper-plane mr-2"></i>Shu xizmatga ariza qoldirish</button>' +
      '<button type="button" data-h-click="h128" class="font-bold px-5 py-3 rounded-xl text-sm flex-1" style="background:#f1f7ff;color:#0d6efd;border:1px solid rgba(13,110,253,0.35)">Yopish</button></div>';
    if (oyna.classList.contains('hidden')) { oyna.classList.remove('hidden'); oyna.scrollTop = 0; }
    if (!oyna.contains(document.activeElement) || document.activeElement === document.body) document.getElementById('metro-bolim-yop').focus();
  }

  function metroOynaYop() {
    metroBolimYop(true);
    const oyna = document.getElementById('metro-bolim-oyna');
    if (!oyna || oyna.classList.contains('hidden')) return;
    oyna.classList.add('hidden');
    if (_metroOynaOldingi && _metroOynaOldingi.focus) { try { _metroOynaOldingi.focus({ preventScroll: true }); } catch (e) {} }
    _metroOynaOldingi = null;
  }

  // ----- 2-oyna: tanlangan bo'lim
  function metroBolimOch(kalit, bolim, tugma) {
    const x = METRO_XIZMATLAR[kalit], bl = x && x.bolimlar;
    const oyna = document.getElementById('metro-sekt-oyna');
    const narxTabi = bolim === 'ulgurji' || bolim === 'aholi';
    const b = bl && bl[bolim];
    if (!oyna || !bl || (!narxTabi && !b)) return;
    if (oyna.classList.contains('hidden')) _metroSektOldingi = tugma || document.activeElement;
    _metroJoriy = { kalit: kalit, bolim: bolim };
    const nuqta = '<span class="w-6 h-6 rounded-full flex items-center justify-center shrink-0 mt-0.5" style="background:rgba(13,110,253,0.12)"><i class="fas fa-check text-[10px]" style="color:#0d6efd"></i></span>';
    const raqam = i => '<span class="w-7 h-7 rounded-full text-xs font-black flex items-center justify-center shrink-0 mt-0.5 text-oq" style="background:#0d6efd">' + (i + 1) + '</span>';
    const qator = (belgi, t) => '<li class="flex items-start gap-3 rounded-xl p-3.5" style="background:#f1f7ff;border:1px solid rgba(120,170,235,0.18)">' + belgi +
      '<div class="min-w-0"><div class="font-bold text-sm text-ink-900">' + t[0] + '</div><div class="text-sm mt-0.5 leading-relaxed" style="color:#5b7fa6">' + t[1] + '</div></div></li>';
    let sarlavha, kirish = '', govda, izohQism = '';
    if (narxTabi) {
      sarlavha = METRO_NARX_NOM[bolim];
      govda = '<div id="metro-narx-orin"><p class="text-sm" style="color:#5b7fa6"><i class="fas fa-spinner spin mr-2"></i>Narxlar yuklanmoqda...</p></div>';
    } else {
      const royxat = b.qadamlar ? b.qadamlar.map((t, i) => qator(raqam(i), t)).join('') : b.elementlar.map(t => qator(nuqta, t)).join('');
      sarlavha = b.sarlavha;
      kirish = '<p class="text-sm mb-3" style="color:#5b7fa6">' + b.kirish + '</p>';
      govda = '<ul class="space-y-2.5">' + royxat + '</ul>';
      izohQism = b.izoh ? '<p class="text-xs mt-3" style="color:#5b7fa6"><i class="fas fa-info-circle mr-1.5" style="color:#0d6efd"></i>' + b.izoh + '</p>' : '';
    }
    document.getElementById('metro-sekt-xizmat').textContent = x.nom;
    document.getElementById('metro-sekt-sarlavha').textContent = sarlavha;
    document.getElementById('metro-sekt-ichi').innerHTML = kirish + govda + izohQism +
      '<div class="flex flex-col sm:flex-row gap-2.5 mt-6">' +
      '<button type="button" data-h-click="c:metroOynaYopArizaga" data-a-click="' + SG_A([kalit]) + '" class="font-bold px-5 py-3 rounded-xl text-sm text-oq flex-1" style="background:linear-gradient(135deg,#ff8a00,#ff8a00)"><i class="fas fa-paper-plane mr-2"></i>Ariza qoldirish</button>' +
      '<button type="button" data-h-click="h130" class="font-bold px-5 py-3 rounded-xl text-sm flex-1" style="background:#f1f7ff;color:#0d6efd;border:1px solid rgba(13,110,253,0.35)"><i class="fas fa-arrow-left mr-2"></i>Orqaga</button></div>';
    if (oyna.classList.contains('hidden')) { oyna.classList.remove('hidden'); oyna.scrollTop = 0; }
    document.getElementById('metro-sekt-orqaga').focus();
    if (narxTabi) {
      const joriyMi = () => _metroJoriy && _metroJoriy.kalit === kalit && _metroJoriy.bolim === bolim;
      metroNarxYukla().then(j => {
        const orin = document.getElementById('metro-narx-orin');
        if (orin && joriyMi()) orin.innerHTML = metroNarxHTML(kalit, bolim, j);
      }).catch(() => {
        const orin = document.getElementById('metro-narx-orin');
        if (orin && joriyMi()) orin.innerHTML = '<div class="rounded-xl p-4 text-sm" style="background:#fff4e5;border:1px solid #ffb74d;color:#8a5200">Narxlarni yuklab bo\'lmadi. Internetni tekshirib, qayta urinib ko\'ring yoki ariza qoldiring.</div>';
      });
    }
  }

  // 2-oynani yopadi va 1-oynaga qaytaradi (`jim` = fokusni qaytarmaydi, 1-oyna ham yopilayotganda)
  function metroBolimYop(jim) {
    const oyna = document.getElementById('metro-sekt-oyna');
    if (!oyna || oyna.classList.contains('hidden')) return;
    oyna.classList.add('hidden');
    _metroJoriy = null;
    if (!jim && _metroSektOldingi && _metroSektOldingi.focus) { try { _metroSektOldingi.focus({ preventScroll: true }); } catch (e) {} }
    _metroSektOldingi = null;
  }

  // Esc: eng ustidagi oyna yopiladi (avval 2-oyna, keyin 1-oyna); Metrologiya sahifasi ochiq qoladi
  // Xizmat kartalari (role="button"): klaviaturada Enter / Probel ham bosadi
  document.addEventListener('keydown', function (e) {
    if (e.key !== 'Enter' && e.key !== ' ') return;
    const k = e.target;
    if (k && k.classList && k.classList.contains('xizmat-karta')) { e.preventDefault(); k.click(); }
  });
  document.addEventListener('keydown', function (e) {
    if (e.key !== 'Escape') return;
    const s2 = document.getElementById('metro-sekt-oyna'), s1 = document.getElementById('metro-bolim-oyna');
    if (s2 && !s2.classList.contains('hidden')) { e.stopImmediatePropagation(); metroBolimYop(); }
    else if (s1 && !s1.classList.contains('hidden')) { e.stopImmediatePropagation(); metroOynaYop(); }
  }, true);

  // Tafsilotdagi tugma: formadagi "Xizmat turi" ni tanlab, formaga olib boradi
  function metroArizaga(kalit) {
    const sel = document.getElementById('metro-xizmat');
    if (sel && METRO_XIZMATLAR[kalit]) sel.value = kalit;
    const forma = document.getElementById('metro-forma');
    if (forma) forma.scrollIntoView({ behavior: 'smooth', block: 'center' });
  }

  // Metrologiya form
  async function submitMetro(e) {
    e.preventDefault();
    const forma = e.target;
    const btn = document.getElementById('metro-yubor');
    const yil = parseInt(tval('metro-yil'));
    if (yil && (yil < 1990 || yil > new Date().getFullYear())) { showToast("O'rnatilgan yilni to'g'ri kiriting"); return; }
    const orig = btn.innerHTML;
    btn.disabled = true;
    btn.innerHTML = '<i class="fas fa-spinner spin mr-2"></i>Yuborilmoqda...';
    try {
      const r = await apiPost('/tolovlar/metrologiya-ariza/', {
        ism: tval('metro-ism'), telefon: tval('metro-tel'),
        xizmat: tval('metro-xizmat'), hisoblagich: tval('metro-model'),
        seriya_raqam: tval('metro-seriya'), ornatilgan_yil: yil || null,
        manzil: tval('metro-manzil'), izoh: tval('metro-izoh'),
      });
      showToast('Ariza #' + r.id + ' qabul qilindi! 24 soat ichida bog\'lanamiz.');
      forma.reset();
    } catch (err) {
      // Server tekshiruv xatosi (masalan, telefon noto'g'ri) yoki ulanish xatosi
      if (err && err.data && err.status) apiErr(err);
      else showToast("Ariza yuborilmadi: serverga ulanib bo'lmadi. Keyinroq urinib ko'ring.");
    } finally {
      btn.disabled = false;
      btn.innerHTML = orig;
    }
  }

  // ====== MIJOZ KABINETI ======

  // Admin paneli olib tashlandi — barcha boshqaruv Django admin panelida: /admin/

  // ====== KIRISH OYNASI ======
  // Navbardagi "Kirish" tugmasi oynani ochadi:
  //   1-bosqich — rol tanlash (Mijoz / Xodim)
  //   2-bosqich — telefon raqam va SMS kod
  // Server rolni tasdiqlaydi: tanlov noto'g'ri bo'lsa, ogohlantiriladi.

  let _kirishRol = 'mijoz';

  // Telefon formati: +998 va 9 ta raqam (jami 13 belgi)
  const TELEFON_SHABLON = /^\+998\d{9}$/;

  // Kiritish paytida faqat "+998..." ko'rinishini saqlab qoladi
  function kirishTelefonTozala(el) {
    let v = el.value.replace(/[^\d+]/g, '');
    if (!v.startsWith('+998')) v = '+998' + v.replace(/^\+?9*9*8*/, '');
    el.value = v.slice(0, 13);
    kirishXatoTozala();
  }

  function kirishXatoKorsat(matn) {
    document.getElementById('kirish-xato-matn').textContent = matn;
    document.getElementById('kirish-xato').classList.remove('hidden');
  }

  function kirishXatoTozala() {
    document.getElementById('kirish-xato').classList.add('hidden');
  }

  // Joriy sessiyani qaytaradi. Xodim va mijoz alohida kalitlarda saqlanadi.
  function kirishJoriySessiya() {
    if (xodimGetUser() && xodimGetToken()) return { rol: 'xodim', user: xodimGetUser() };
    const u = apiUser();
    if (u && apiToken()) return { rol: u.rol || 'mijoz', user: u };
    return null;
  }

  function kirishOch() {
    // Allaqachon tizimda bo'lsa — to'g'ridan-to'g'ri kabinetga
    const s = kirishJoriySessiya();
    if (s) {
      if (s.rol === 'xodim') { openXodimPage(); } else { openMijozPage(); }
      return;
    }
    const m = document.getElementById('kirish-modal');
    m.classList.remove('hidden');
    m.classList.add('flex');
    document.body.style.overflow = 'hidden';
    kirishRolgaQayt();
  }

  // 1-bosqichga qaytish — rol tanlash ro'yxati
  function kirishRolgaQayt() {
    document.getElementById('kirish-rol').classList.remove('hidden');
    document.getElementById('kirish-telefon-bosqich').classList.add('hidden');
    document.getElementById('kirish-sarlavha').textContent = 'Kirish';
    document.getElementById('kirish-izoh').textContent = 'Hisobingiz turini tanlang';
  }

  // 2-bosqich — tanlangan rol uchun telefon raqam
  function kirishRolTanla(rol) {
    // Mijoz kirishi to'liq kabinet sahifasida (kabinet.html) — SMS kod,
    // profil to'ldirish va 10 bo'limli kabinet o'sha yerda.
    if (rol === 'mijoz') { kirishYop(); openMijozPage(); return; }
    _kirishRol = rol;
    document.getElementById('kirish-rol').classList.add('hidden');
    document.getElementById('kirish-telefon-bosqich').classList.remove('hidden');
    document.getElementById('kirish-sarlavha').textContent =
      rol === 'xodim' ? 'Xodim kirishi' : 'Mijoz kirishi';
    document.getElementById('kirish-izoh').textContent = 'Telefon raqamingizni kiriting';
    // Ro'yxatdan o'tish faqat mijozlar uchun — xodimni admin qo'shadi
    document.getElementById('kirish-royxat-havola').classList.toggle('hidden', rol === 'xodim');
    kirishXatoTozala();
    setTimeout(() => document.getElementById('kirish-telefon').focus(), 50);
  }

  // "Ro'yxatdan o'tish" — SMS kutmasdan darhol profil maydonlarini ochadi
  function kirishRoyxatOch() {
    const tel = document.getElementById('kirish-telefon').value.trim().replace(/\s/g, '');
    kirishXatoTozala();
    if (!TELEFON_SHABLON.test(tel)) {
      kirishXatoKorsat('Avval telefon raqamingizni +998901234567 formatida kiriting.');
      return;
    }
    // Ro'yxatdan o'tish ham kabinet sahifasida: SMS kod tasdiqlangach
    // profil maydonlari o'sha yerda so'raladi.
    _otpPhone = tel;
    kirishYop();
    openMijozPage();
  }

  function kirishYop() {
    const m = document.getElementById('kirish-modal');
    m.classList.add('hidden');
    m.classList.remove('flex');
    document.body.style.overflow = '';
  }

  function kirishFonBosildi(e) {
    if (e.target === e.currentTarget) kirishYop();
  }

  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && !document.getElementById('kirish-modal').classList.contains('hidden')) kirishYop();
  });

  async function kirishDavomEt(e) {
    e.preventDefault();
    const tel = document.getElementById('kirish-telefon').value.trim().replace(/\s/g, '');
    kirishXatoTozala();

    if (!TELEFON_SHABLON.test(tel)) {
      kirishXatoKorsat('Telefon raqamini +998901234567 formatida kiriting.');
      return;
    }

    const btn = e.target.querySelector('button[type=submit]');
    const eskiHolat = btn.innerHTML;
    btn.disabled = true;
    btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Yuborilmoqda...';

    try {
      const res = await apiPost('/auth/otp/yuborish/', { telefon: tel });

      // Xodim tanlangan, lekin raqam tizimda xodim sifatida ro'yxatda emas
      if (_kirishRol === 'xodim' && res.rol !== 'xodim') {
        kirishXatoKorsat('Bu raqam xodim sifatida ro\'yxatdan o\'tmagan. Admin bilan bog\'laning.');
        return;
      }

      kirishYop();
      kirishKodBosqichi(_kirishRol, tel);
      showToast('Tasdiqlash kodi ' + tel + ' raqamiga yuborildi!');
    } catch (err) {
      kirishXatoKorsat(
        err?.data?.detail || 'Server bilan bog\'lanishda xatolik. Keyinroq urinib ko\'ring.'
      );
    } finally {
      btn.disabled = false;
      btn.innerHTML = eskiHolat;
    }
  }

  // Tegishli kabinetni ochib, uni to'g'ridan-to'g'ri kod kiritish bosqichiga qo'yadi.
  // Kodni tekshirish mavjud `mijozVerifyOtp` / `xodimVerifyOtp` orqali davom etadi.
  function kirishKodBosqichi(rol, tel) {
    if (rol === 'xodim') {
      openXodimPage();
      _xotpPhone = tel;
      document.getElementById('xotp-step1').classList.add('hidden');
      document.getElementById('xotp-notfound').classList.add('hidden');
      document.getElementById('xotp-step2').classList.remove('hidden');
      document.getElementById('xotp-phone-show').textContent = tel;
      document.getElementById('xotp-code').value = '';
      document.getElementById('xotp-code').focus();
      _xotpStartTimer('xotp-timer', document.getElementById('xotp-resend-btn'), 'xotp-resend-text');
    } else {
      // Mijoz kirishi to'liq kabinet sahifasida davom etadi
      _otpPhone = tel;
      openMijozPage();
    }
  }

  // Navbar tugmasi: tizimga kirgan bo'lsa "Kabinet", aks holda "Kirish"
  function kirishTugmaYangila() {
    const btn = document.getElementById('kirish-btn');
    if (!btn) return;
    const s = kirishJoriySessiya();
    // To'liq ism uzun bo'lib navbarni cho'zib yuboradi — qisqa "Profilim" yozuvi
    btn.innerHTML = s
      ? '<i class="fas fa-user-circle mr-1 opacity-70"></i>Profilim'
      : '<i class="fas fa-right-to-bracket mr-1 opacity-70"></i>Kirish';
    btn.title = s ? (s.user.ism || s.user.telefon || '') : 'Kirish';

    const mobil = document.getElementById('kirish-btn-mobil');
    if (mobil) {
      mobil.innerHTML = s
        ? '<i class="fas fa-user-circle mr-2"></i>Profilim'
        : '<i class="fas fa-right-to-bracket mr-2"></i>Kirish';
    }
  }
  document.addEventListener('DOMContentLoaded', kirishTugmaYangila);

  // Sahifa har ochilganda saqlangan mijoz sessiyasi tekshiriladi: token eskirgan
  // bo'lsa apiReq uni refresh orqali yangilaydi va mijoz kabinetga OTP so'ralmasdan
  // kiradi. Faqat refresh ham amal qilmasa sessiya tozalanadi.
  document.addEventListener('DOMContentLoaded', async () => {
    if (!apiToken() || !apiUser()) return;
    try {
      const user = await apiGet('/auth/profil/');
      const eski = JSON.parse(localStorage.getItem('sg_user') || '{}');
      apiSaveSession({
        access: apiToken(),
        refresh: localStorage.getItem('sg_refresh'),
        user: { ...eski, ...user },
      });
    } catch (err) {
      if (err?.status === 401) apiClearSession();   // muddati o'tgan — qayta kirish kerak
    }
    kirishTugmaYangila();
  });

  let _otpCode = '', _otpPhone = '', _otpTimer = null;

  // Mijoz kabineti endi alohida sahifada (kabinet.html) — 10 bo'limli to'liq
  // versiya. Sahifadagi eski modal ishlatilmaydi: tizimga kirgan mijozdan
  // har safar qaytadan SMS kod so'ralib qolayotgan edi.
  function openMijozPage() {
    location.href = location.protocol === 'file:' ? 'kabinet.html' : '/kabinet/';
  }

  function closeMijozPage() {
    document.getElementById('mijoz-page').classList.add('hidden');
    document.body.style.overflow = '';
    if (_otpTimer) clearInterval(_otpTimer);
  }

  function mijozOtpReset() {
    ['motp-step1','motp-step2','motp-step3'].forEach((id,i) =>
      document.getElementById(id).classList.toggle('hidden', i !== 0));
    if (_otpTimer) clearInterval(_otpTimer);
  }

  function mijozOtpBack() {
    document.getElementById('motp-step2').classList.add('hidden');
    document.getElementById('motp-step1').classList.remove('hidden');
    if (_otpTimer) clearInterval(_otpTimer);
  }

  async function mijozSendOtp(e) {
    e.preventDefault();
    _otpPhone = document.getElementById('motp-phone').value.trim();
    if (!_otpPhone) return;
    const btn = e.target.querySelector('button[type=submit]');
    btn.disabled = true; btn.innerHTML = '<i class="fas fa-spinner fa-spin mr-2"></i>Yuborilmoqda...';
    try {
      await apiPost('/auth/otp/yuborish/', { telefon: _otpPhone });
      document.getElementById('motp-step1').classList.add('hidden');
      document.getElementById('motp-step2').classList.remove('hidden');
      document.getElementById('motp-phone-show').textContent = _otpPhone;
      document.getElementById('motp-code').value = '';
      const t = document.getElementById('toast');
      t.style.background = 'linear-gradient(90deg,#2563eb,#3b82f6)';
      showToast('SMS yuborildi! Serverdan kodni kuting.');
      setTimeout(() => { t.style.background = ''; }, 4000);
      _otpStartCountdown('motp-timer','motp-resend-btn','motp-resend-text','blue');
    } catch(err) { apiErr(err); }
    finally { btn.disabled = false; btn.innerHTML = '<i class="fas fa-sms mr-2"></i>SMS kod yuborish'; }
  }

  async function mijozResendOtp() {
    try {
      await apiPost('/auth/otp/yuborish/', { telefon: _otpPhone });
      showToast('Yangi kod yuborildi!');
      document.getElementById('motp-resend-text').innerHTML = 'Qayta yuborish (<span id="motp-timer">60</span>s)';
      _otpStartCountdown('motp-timer','motp-resend-btn','motp-resend-text','blue');
    } catch(err) { apiErr(err); }
  }

  async function mijozVerifyOtp(e) {
    e.preventDefault();
    const kod = document.getElementById('motp-code').value.trim();
    const btn = e.target.querySelector('button[type=submit]');
    btn.disabled = true; btn.innerHTML = '<i class="fas fa-spinner fa-spin mr-2"></i>Tekshirilmoqda...';
    try {
      const data = await apiPost('/auth/otp/tasdiqlash/', { telefon: _otpPhone, kod });
      if (_otpTimer) clearInterval(_otpTimer);
      apiSaveSession(data);
      const user = data.user;
      if (!user.ism) {
        document.getElementById('motp-step2').classList.add('hidden');
        document.getElementById('motp-step3').classList.remove('hidden');
        mijozProfilFormasiToldir(user);
      } else {
        showToast('Xush kelibsiz, ' + user.ism + '!');
        mijozShowDash(user);
      }
    } catch(err) {
      document.getElementById('motp-code').value = '';
      document.getElementById('motp-code').focus();
      apiErr(err);
    }
    finally { btn.disabled = false; btn.innerHTML = '<i class="fas fa-check-circle mr-2"></i>Tasdiqlash'; }
  }

  // Profil formasini mavjud ma'lumotlar bilan to'ldiradi.
  // Yangi mijozda bo'sh, tahrirlashda esa saqlangan qiymatlar chiqadi.
  function mijozProfilFormasiToldir(user) {
    user = user || apiUser() || {};
    const q = id => document.getElementById(id);
    q('mp-telefon').value   = user.telefon || _otpPhone || '';
    q('mp-ism').value       = user.ism || '';
    q('mp-qoshimcha').value = user.qoshimcha_telefon || '';
    q('mp-email').value     = user.email || '';
    q('mp-tuman').value     = user.tuman || '';
    q('mp-tuman-mahalla').value = user.mahalla || '';
    // Tuman o'rnatilgach viloyatni ham moslaymiz
    const _mpT = document.getElementById('mp-tuman');
    if (_mpT.viloyatniMoslash) _mpT.viloyatniMoslash();
    q('mp-manzil').value    = user.manzil || '';
    q('mp-moljal').value    = user.moljal || '';
    q('mp-mulk').value      = user.mulk_turi || '';
    q('mp-sarlavha').textContent = user.ism ? 'Profilni tahrirlash' : 'Profilingizni to\'ldiring';
  }

  // Kabinetdan profilni tahrirlash uchun ochish
  function mijozProfilTahrirla() {
    document.getElementById('mijoz-dash').classList.add('hidden');
    document.getElementById('mijoz-auth').classList.remove('hidden');
    ['motp-step1','motp-step2','motp-step3'].forEach((id, i) =>
      document.getElementById(id).classList.toggle('hidden', i !== 2));
    mijozProfilFormasiToldir(apiUser());
  }

  async function mijozCompleteProfile(e) {
    e.preventDefault();
    const q = id => document.getElementById(id).value.trim();
    const malumot = {
      ism:               q('mp-ism'),
      manzil:            q('mp-manzil'),
      viloyat:           document.getElementById('mp-tuman-viloyat').value,
      tuman:             document.getElementById('mp-tuman').value,
      mahalla:           document.getElementById('mp-tuman-mahalla').value.trim(),
      qoshimcha_telefon: q('mp-qoshimcha'),
      email:             q('mp-email'),
      moljal:            q('mp-moljal'),
      mulk_turi:         document.getElementById('mp-mulk').value,
    };
    const btn = e.target.querySelector('button[type=submit]');
    const eski = btn.innerHTML;
    btn.disabled = true; btn.innerHTML = '<i class="fas fa-spinner fa-spin mr-2"></i>Saqlanmoqda...';
    try {
      let user;
      if (apiToken()) {
        // Tizimda bor: profilni yangilash
        user = await apiPatchTasdiq('/auth/profil/', malumot);
        const stored = JSON.parse(localStorage.getItem('sg_user') || '{}');
        apiSaveSession({ access: apiToken(), refresh: localStorage.getItem('sg_refresh'), user: { ...stored, ...user } });
        showToast('Profil yangilandi!');
      } else {
        // Yangi mijoz: hisob yaratiladi va sessiya ochiladi
        malumot.telefon = document.getElementById('mp-telefon').value.trim().replace(/\s/g, '');
        const data = await apiPost('/auth/royxat/', malumot);
        apiSaveSession(data);
        user = data.user;
        showToast('Ro\'yxatdan muvaffaqiyatli o\'tdingiz!');
      }
      mijozShowDash(user);
    } catch(err) { apiErr(err); }
    finally { btn.disabled = false; btn.innerHTML = eski; }
  }

  function _otpStartCountdown(timerId, btnId, textId, color) {
    if (_otpTimer) clearInterval(_otpTimer);
    let sec = 60;
    const btn = document.getElementById(btnId);
    btn.disabled = true;
    _otpTimer = setInterval(() => {
      sec--;
      const el = document.getElementById(timerId);
      if (el) el.textContent = sec;
      if (sec <= 0) {
        clearInterval(_otpTimer);
        btn.disabled = false;
        document.getElementById(textId).innerHTML = `<span class="text-${color}-400">Qayta yuborish</span>`;
      }
    }, 1000);
  }

  function mijozShowDash(mijoz) {
    document.getElementById('mijoz-auth').classList.add('hidden');
    document.getElementById('mijoz-dash').classList.remove('hidden');
    document.getElementById('md-name').textContent   = mijoz.ism;
    document.getElementById('md-manzil').textContent = mijoz.manzil || mijoz.tuman;
    document.getElementById('mb-manzil-display').textContent = (mijoz.manzil || '') + (mijoz.tuman ? ' (' + mijoz.tuman + ')' : '');
    mijozUpdateStats(mijoz);
    kirishTugmaYangila();
    mijozTab('buyurtma');
  }

  function mijozLogout() {
    apiClearSession();
    document.getElementById('mijoz-auth').classList.remove('hidden');
    document.getElementById('mijoz-dash').classList.add('hidden');
    mijozOtpReset();
    kirishTugmaYangila();
    showToast('Tizimdan chiqildi');
  }

  async function mijozUpdateStats() {
    try {
      const [buyurtmalar, smslar] = await Promise.all([
        apiGet('/buyurtmalar/'),
        apiGet('/sms/'),
      ]);
      const list = buyurtmalar.results || buyurtmalar;
      const sms  = smslar.results || smslar;
      document.getElementById('md-stat-jami').textContent       = list.length;
      document.getElementById('md-stat-kutilmoqda').textContent = list.filter(b => b.holat !== 'bajarildi').length;
      document.getElementById('md-stat-bajarildi').textContent  = list.filter(b => b.holat === 'bajarildi').length;
      document.getElementById('md-stat-sms').textContent        = sms.filter(s => !s.oqildi).length;
    } catch (_) {}
  }

  function mijozTab(tab) {
    ['buyurtma','tolov','tarix','sms','monitoring'].forEach(t => {
      document.getElementById('mt-' + t).classList.add('hidden');
      const b = document.getElementById('mtab-' + t);
      b.classList.remove('tab-active');
      b.classList.add('text-gray-400');
    });
    document.getElementById('mt-' + tab).classList.remove('hidden');
    const ab = document.getElementById('mtab-' + tab);
    ab.classList.add('tab-active');
    ab.classList.remove('text-gray-400');
    if (tab === 'tarix')      mijozRenderTarix();
    if (tab === 'sms')        mijozRenderSms();
    if (tab === 'tolov')      mijozRenderTolov();
    if (tab === 'monitoring') mijozRenderMonitoring();
  }

  async function mijozSubmitBuyurtma(e) {
    e.preventDefault();
    const xizmat      = document.getElementById('mb-xizmat').value;
    const vaqt_istagi = document.getElementById('mb-vaqt').value;
    const tavsif      = document.getElementById('mb-tavsif').value;
    const btn         = e.target.querySelector('button[type=submit]');
    btn.disabled = true; btn.innerHTML = '<i class="fas fa-spinner fa-spin mr-2"></i>Yuborilmoqda...';
    try {
      await apiPostA('/buyurtmalar/', { xizmat, vaqt_istagi, tavsif });
      showToast('Buyurtma yuborildi! SMS xabarnoma yuborildi ✓');
      e.target.reset();
      mijozUpdateStats();
    } catch(err) { apiErr(err); }
    finally { btn.disabled = false; btn.innerHTML = '<i class="fas fa-paper-plane mr-2"></i>Buyurtma Yuborish'; }
  }

  async function mijozRenderTolov() {
    const el = document.getElementById('md-tolov-list');
    try {
      const data   = await apiGet('/buyurtmalar/');
      const tolash = (data.results || data).filter(b => b.holat === 'bajarildi' && !b.tolandi);
      if (!tolash.length) {
        el.innerHTML = '<div class="bg-green-500/10 border border-green-500/30 rounded-2xl p-4 text-center text-green-400 text-sm mb-2"><i class="fas fa-check-circle mr-2"></i>Barcha to\'lovlar amalga oshirilgan</div>';
        return;
      }
      el.innerHTML = tolash.map(b => `
        <div class="bg-navy-800 border border-yellow-500/40 rounded-2xl p-4 flex items-center justify-between">
          <div>
            <div class="font-semibold text-sm">${b.xizmat_nomi||b.xizmat}</div>
            <div class="text-xs text-gray-400 mt-0.5">#${b.id}</div>
          </div>
          <div class="text-right"><div class="text-yellow-400 font-bold text-sm">To'lov kutilmoqda</div></div>
        </div>`).join('');
    } catch { el.innerHTML = ''; }
  }

  let selectedPayMethod = '';
  function mijozSelectPayMethod(btn, method) {
    document.querySelectorAll('.pay-method-btn').forEach(b => {
      b.classList.remove('border-blue-500', 'bg-blue-500/10');
      b.classList.add('border-navy-600');
    });
    btn.classList.add('border-blue-500', 'bg-blue-500/10');
    btn.classList.remove('border-navy-600');
    selectedPayMethod = method;
    const detail = document.getElementById('md-pay-detail');
    detail.classList.remove('hidden');
    const info = {
      click: '📱 Click ilovasini oching → To\'lov → Telefon raqam: <strong>+998712345678</strong>',
      payme: '💳 Payme ilovasini oching → Uzcard/Humo karta orqali to\'lang: <strong>8600 1234 5678 9012</strong>',
      bank: '🏦 Bank hisob raqami: <strong>2020 1234 5678 9012</strong> | Bank: NBU Buxoro filiali'
    };
    detail.innerHTML = info[method] || '';
  }

  async function mijozConfirmPayment() {
    if (!selectedPayMethod) { showToast('To\'lov usulini tanlang!'); return; }
    showToast('To\'lov tasdiqlandi! SMS yuborildi ✓');
    mijozRenderTolov();
    mijozUpdateStats();
  }

  async function mijozRenderTarix() {
    const el = document.getElementById('md-tarix-list');
    el.innerHTML = '<div class="text-center py-6 text-gray-500"><i class="fas fa-spinner fa-spin text-xl"></i></div>';
    try {
      const data   = await apiGet('/buyurtmalar/');
      const mening = data.results || data;
      if (!mening.length) {
        el.innerHTML = '<div class="text-center py-12 text-gray-500"><i class="fas fa-history text-4xl mb-3 block opacity-30"></i>Hali buyurtma yo\'q</div>';
        return;
      }
      const hColor = { yangi:'text-yellow-400', qabul:'text-blue-400', bajarilmoqda:'text-orange-400', bajarildi:'text-green-400' };
      const hText  = { yangi:'Yangi', qabul:'Qabul qilindi', bajarilmoqda:'Bajarilmoqda', bajarildi:'Bajarildi ✓' };
      el.innerHTML = mening.map(b => `
        <div class="bg-navy-800 border border-navy-700 rounded-2xl p-4">
          <div class="flex items-start justify-between">
            <div>
              <div class="font-semibold text-ink-900 text-sm">${b.xizmat_nomi||b.xizmat}</div>
              <div class="text-xs text-gray-400 mt-0.5">${new Date(b.yaratilgan).toLocaleString('uz-UZ')}</div>
              ${b.natija ? `<div class="text-xs text-gray-300 bg-navy-900 rounded-lg px-3 py-2 mt-2">${b.natija}</div>` : ''}
            </div>
            <span class="text-xs font-semibold ${hColor[b.holat]||'text-gray-400'} ml-3 shrink-0">${hText[b.holat]||b.holat}</span>
          </div>
          ${b.holat === 'bajarildi' && !b.tolandi ? `<div class="mt-3"><button data-h-click="h165" class="text-xs bg-yellow-500/20 border border-yellow-500/50 text-yellow-300 px-3 py-1.5 rounded-lg font-semibold"><i class="fas fa-credit-card mr-1"></i>To'lov qilish</button></div>` : ''}
        </div>`).join('');
    } catch { el.innerHTML = '<div class="text-center py-8 text-red-400">Xato</div>'; }
  }

  function mijozAddSms(id, matn) { /* API orqali avtomatik */ }

  async function mijozRenderSms() {
    const el = document.getElementById('md-sms-list');
    el.innerHTML = '<div class="text-center py-6 text-gray-500"><i class="fas fa-spinner fa-spin text-xl"></i></div>';
    try {
      const data = await apiGet('/sms/');
      const list = data.results || data;
      if (!list.length) {
        el.innerHTML = '<div class="text-center py-12 text-gray-500"><i class="fas fa-bell-slash text-4xl mb-3 block opacity-30"></i>Xabarnomalar yo\'q</div>';
        return;
      }
      el.innerHTML = list.map(s => `
        <div class="flex items-start gap-3 bg-navy-800 border ${s.oqildi ? 'border-navy-700' : 'border-blue-500/40'} rounded-2xl p-4">
          <div class="w-9 h-9 ${s.oqildi ? 'bg-navy-700' : 'bg-blue-500/20'} rounded-xl flex items-center justify-center shrink-0 mt-0.5">
            <i class="fas fa-sms ${s.oqildi ? 'text-gray-500' : 'text-blue-400'} text-sm"></i>
          </div>
          <div class="flex-1">
            <div class="text-sm text-ink-900">${s.matn}</div>
            <div class="text-xs text-gray-500 mt-1">${new Date(s.yaratilgan).toLocaleString('uz-UZ')}</div>
          </div>
          ${!s.oqildi ? '<span class="w-2 h-2 bg-blue-400 rounded-full shrink-0 mt-2"></span>' : ''}
        </div>`).join('');
      apiPostA('/sms/oqildi/', {}).catch(() => {});
    } catch { el.innerHTML = '<div class="text-center py-8 text-red-400">Xato</div>'; }
  }
  function mijozRenderMonitoring() {
    document.getElementById('mon-sana').textContent = new Date().toLocaleDateString('uz-UZ');
    const sarfi   = (3.5 + Math.random() * 2).toFixed(1);
    const harorat = Math.round(16 + Math.random() * 6);
    document.getElementById('mon-sarfi').innerHTML    = sarfi + ' <span class="text-base font-normal text-gray-400">m³/soat</span>';
    document.getElementById('mon-harorat').innerHTML  = harorat + ' <span class="text-base font-normal text-gray-400">°C</span>';
    const sarfiW = Math.min(90, Math.round((+sarfi / 8) * 100));
    document.getElementById('mon-sarfi-bar').style.width = sarfiW + '%';
    document.getElementById('mon-sarfi-status').textContent = sarfiW > 70 ? 'Yuqori' : sarfiW > 40 ? 'O\'rtacha' : 'Past';
    const haroratW = Math.round((harorat / 30) * 100);
    document.getElementById('mon-harorat-bar').style.width = haroratW + '%';
    document.getElementById('mon-harorat-status').textContent = harorat > 22 ? 'Issiq' : harorat > 16 ? 'Qulay' : 'Sovuq';
    const oySarfi   = Math.round(+sarfi * 14 * 30);
    const otganOy   = Math.round(oySarfi * (0.85 + Math.random() * 0.3));
    document.getElementById('mon-oy-sarfi').textContent  = oySarfi + ' m³';
    document.getElementById('mon-otgan-oy').textContent  = otganOy + ' m³';
    document.getElementById('mon-tolov').textContent     = (oySarfi * 850).toLocaleString('uz-UZ') + ' so\'m';
    const chartEl = document.getElementById('mon-chart');
    const vals    = Array.from({length: 24}, () => Math.round(2 + Math.random() * 6));
    const maxVal  = Math.max(...vals);
    chartEl.innerHTML = vals.map((v, i) => {
      const h = Math.round((v / maxVal) * 100);
      const isNow = i === new Date().getHours();
      return `<div class="flex-1 flex flex-col justify-end" title="${i}:00 — ${v} m³">
        <div class="rounded-t-sm transition-all" style="height:${h}%;background:${isNow ? '#3b82f6' : 'rgba(99,102,241,0.5)'}"></div>
      </div>`;
    }).join('');
    const alerts = document.getElementById('mon-alerts');
    const items  = [];
    if (+sarfi > 7) items.push('<div class="flex gap-2 text-red-400"><i class="fas fa-exclamation-triangle mt-0.5 shrink-0"></i><span>Gaz sarfi yuqori!</span></div>');
    if (harorat < 15) items.push('<div class="flex gap-2 text-blue-400"><i class="fas fa-snowflake mt-0.5 shrink-0"></i><span>Harorat past, isitishni kuchaytiring</span></div>');
    items.push('<div class="flex gap-2 text-green-400"><i class="fas fa-check-circle mt-0.5 shrink-0"></i><span>Gaz bosimi normal</span></div>');
    alerts.innerHTML = items.join('');
  }

  // ====== XODIM KABINETI ======

  let _xotpCode = '', _xotpPhone = '', _xotpTimer = null;

  function xodimGetToken() { return localStorage.getItem('sg_xodim_token'); }
  function xodimGetUser()  { return JSON.parse(localStorage.getItem('sg_xodim_user') || 'null'); }

  async function xodimApiGet(path) {
    const res = await fetch(API + path, { headers: { 'Authorization': 'Bearer ' + xodimGetToken() } });
    if (!res.ok) throw await res.json();
    return res.json();
  }
  async function xodimApiPost(path, body) {
    const res = await fetch(API + path, {
      method: 'POST', headers: { 'Authorization': 'Bearer ' + xodimGetToken(), 'Content-Type': 'application/json' },
      body: JSON.stringify(body)
    });
    if (!res.ok) throw await res.json();
    return res.json();
  }

  function openXodimPage() {
    document.getElementById('xodim-page').classList.remove('hidden');
    document.body.style.overflow = 'hidden';
    const session = xodimGetUser();
    if (session && xodimGetToken()) {
      xodimShowDash(session);
    } else {
      document.getElementById('xodim-auth').classList.remove('hidden');
      document.getElementById('xodim-dash').classList.add('hidden');
      xodimOtpReset();
    }
  }

  function closeXodimPage() {
    document.getElementById('xodim-page').classList.add('hidden');
    document.body.style.overflow = '';
    if (_xotpTimer) clearInterval(_xotpTimer);
  }

  function xodimOtpReset() {
    ['xotp-step1','xotp-step2','xotp-notfound'].forEach((id, i) =>
      document.getElementById(id).classList.toggle('hidden', i !== 0));
    if (_xotpTimer) clearInterval(_xotpTimer);
  }

  function xodimOtpBack() {
    document.getElementById('xotp-step2').classList.add('hidden');
    document.getElementById('xotp-step1').classList.remove('hidden');
    if (_xotpTimer) clearInterval(_xotpTimer);
  }

  function _xotpGenCode() {
    return String(Math.floor(1000000 + Math.random() * 9000000));
  }

  function _xotpStartTimer(timerEl, resendBtn, resendTextEl) {
    let sec = 60;
    resendBtn.disabled = true;
    if (_xotpTimer) clearInterval(_xotpTimer);
    _xotpTimer = setInterval(() => {
      sec--;
      const el = document.getElementById(timerEl);
      if (el) el.textContent = sec;
      if (sec <= 0) {
        clearInterval(_xotpTimer);
        resendBtn.disabled = false;
        document.getElementById(resendTextEl).innerHTML = '<span class="text-gold-400">Qayta yuborish</span>';
      }
    }, 1000);
  }

  async function xodimSendOtp(e) {
    e.preventDefault();
    _xotpPhone = document.getElementById('xotp-phone').value.trim();
    if (!_xotpPhone) return;
    const btn = e.target.querySelector('button[type=submit]');
    btn.disabled = true; btn.innerHTML = '<i class="fas fa-spinner fa-spin mr-2"></i>Yuborilmoqda...';
    try {
      const res = await apiPost('/auth/otp/yuborish/', { telefon: _xotpPhone });
      if (res.rol !== 'xodim' && res.yangi_mijoz === false) {
        document.getElementById('xotp-step1').classList.add('hidden');
        document.getElementById('xotp-notfound').classList.remove('hidden');
        return;
      }
      if (res.yangi_mijoz) {
        document.getElementById('xotp-step1').classList.add('hidden');
        document.getElementById('xotp-notfound').classList.remove('hidden');
        return;
      }
      document.getElementById('xotp-step1').classList.add('hidden');
      document.getElementById('xotp-step2').classList.remove('hidden');
      document.getElementById('xotp-phone-show').textContent = _xotpPhone;
      document.getElementById('xotp-code').value = '';
      const t = document.getElementById('toast');
      t.style.background = 'linear-gradient(90deg,#b45309,#d97706)';
      showToast('SMS yuborildi! Serverdan kodni kuting.');
      setTimeout(() => { t.style.background = ''; }, 4000);
      _xotpStartTimer('xotp-timer', document.getElementById('xotp-resend-btn'), 'xotp-resend-text');
    } catch(err) {
      const msg = err?.data?.detail || '';
      if (msg.includes('bloklangan')) {
        document.getElementById('xotp-step1').classList.add('hidden');
        document.getElementById('xotp-notfound').classList.remove('hidden');
        document.getElementById('xotp-notfound').querySelector('p').innerHTML =
          'Hisobingiz bloklangan.<br/>Admin bilan bog\'laning.';
      } else { apiErr(err); }
    }
    finally { btn.disabled = false; btn.innerHTML = '<i class="fas fa-sms mr-2"></i>SMS kod yuborish'; }
  }

  async function xodimResendOtp() {
    try {
      await apiPost('/auth/otp/yuborish/', { telefon: _xotpPhone });
      showToast('Yangi kod yuborildi!');
      document.getElementById('xotp-resend-text').innerHTML = 'Qayta yuborish (<span id="xotp-timer">60</span>s)';
      _xotpStartTimer('xotp-timer', document.getElementById('xotp-resend-btn'), 'xotp-resend-text');
    } catch(err) { apiErr(err); }
  }

  async function xodimVerifyOtp(e) {
    e.preventDefault();
    const kod = document.getElementById('xotp-code').value.trim();
    const btn = e.target.querySelector('button[type=submit]');
    btn.disabled = true; btn.innerHTML = '<i class="fas fa-spinner fa-spin mr-2"></i>Tekshirilmoqda...';
    try {
      const data = await apiPost('/auth/otp/tasdiqlash/', { telefon: _xotpPhone, kod });
      if (_xotpTimer) clearInterval(_xotpTimer);
      localStorage.setItem('sg_xodim_token',   data.access);
      localStorage.setItem('sg_xodim_refresh',  data.refresh || '');
      localStorage.setItem('sg_xodim_user',     JSON.stringify(data.user));
      showToast('Xush kelibsiz, ' + data.user.ism + '!');
      xodimShowDash(data.user);
    } catch(err) {
      document.getElementById('xotp-code').value = '';
      document.getElementById('xotp-code').focus();
      apiErr(err);
    }
    finally { btn.disabled = false; btn.innerHTML = '<i class="fas fa-check-circle mr-2"></i>Tasdiqlash'; }
  }

  function xodimShowDash(xodim) {
    document.getElementById('xodim-auth').classList.add('hidden');
    document.getElementById('xodim-dash').classList.remove('hidden');
    document.getElementById('xd-name').textContent  = xodim.ism;
    document.getElementById('xd-tuman').textContent = xodim.tuman;
    xodimUpdateStats(xodim);
    xodimTab('buyurtmalar');
    kirishTugmaYangila();
  }

  function xodimLogout() {
    ['sg_xodim_token','sg_xodim_refresh','sg_xodim_user'].forEach(k => localStorage.removeItem(k));
    document.getElementById('xodim-auth').classList.remove('hidden');
    document.getElementById('xodim-dash').classList.add('hidden');
    xodimOtpReset();
    kirishTugmaYangila();
    showToast('Tizimdan chiqildi');
  }

  async function xodimUpdateStats() {
    try {
      const data = await xodimApiGet('/buyurtmalar/?format=json');
      const list = data.results || data;
      document.getElementById('xd-stat-yangi').textContent     = list.filter(b => b.holat === 'yangi').length;
      document.getElementById('xd-stat-jarayonda').textContent = list.filter(b => b.holat === 'qabul' || b.holat === 'bajarilmoqda').length;
      document.getElementById('xd-stat-bajarildi').textContent = list.filter(b => b.holat === 'bajarildi').length;
    } catch (_) {}
  }

  function xodimTab(tab) {
    ['buyurtmalar','natija','foto','tarix'].forEach(t => {
      document.getElementById('xt-' + t).classList.add('hidden');
      const b = document.getElementById('xtab-' + t);
      b.classList.remove('tab-active');
      b.classList.add('text-gray-400');
    });
    document.getElementById('xt-' + tab).classList.remove('hidden');
    const ab = document.getElementById('xtab-' + tab);
    ab.classList.add('tab-active');
    ab.classList.remove('text-gray-400');
    if (tab === 'buyurtmalar') xodimRenderBuyurtmalar();
    if (tab === 'natija' || tab === 'foto') xodimPopulateOrderSelects();
    if (tab === 'tarix') xodimRenderTarix();
  }

  async function xodimRenderBuyurtmalar() {
    const el = document.getElementById('xd-buyurtmalar-list');
    el.innerHTML = '<div class="text-center py-8 text-gray-500"><i class="fas fa-spinner fa-spin text-2xl"></i></div>';
    try {
      const data = await xodimApiGet('/buyurtmalar/');
      const list = (data.results || data).filter(b => b.holat !== 'bajarildi' && b.holat !== 'bekor');
      if (!list.length) {
        el.innerHTML = '<div class="text-center py-12 text-gray-500"><i class="fas fa-inbox text-4xl mb-3 block opacity-30"></i>Hozircha buyurtma yo\'q</div>';
        return;
      }
      const hColors = { yangi:'text-yellow-400 bg-yellow-400/10', qabul:'text-blue-400 bg-blue-400/10', bajarilmoqda:'text-orange-400 bg-orange-400/10' };
      const hText   = { yangi:'Yangi', qabul:'Qabul qilindi', bajarilmoqda:'Bajarilmoqda' };
      el.innerHTML  = list.map(b => {
        const m    = b.mijoz_malumot || {};
        const btns = b.holat === 'yangi'
          ? `<button data-h-click="c:xodimAccept" data-a-click="${SG_A([b.id])}" class="w-full gold-btn text-oq font-bold py-2.5 rounded-xl text-sm hover:opacity-90 transition-all"><i class="fas fa-check mr-1.5"></i>Qabul qilish</button>`
          : b.holat === 'qabul'
            ? `<div class="flex gap-2"><button data-h-click="c:xodimStartWork" data-a-click="${SG_A([b.id])}" class="flex-1 bg-blue-500/20 hover:bg-blue-500/30 border border-blue-500/50 text-blue-300 font-bold py-2.5 rounded-xl text-sm transition-all"><i class="fas fa-play mr-1"></i>Boshlash</button><button data-h-click="h182" class="flex-1 bg-green-500/20 hover:bg-green-500/30 border border-green-500/50 text-green-300 font-bold py-2.5 rounded-xl text-sm transition-all"><i class="fas fa-clipboard-check mr-1"></i>Natija</button></div>`
            : `<div class="flex gap-2"><button data-h-click="h182" class="flex-1 bg-green-500/20 border border-green-500/50 text-green-300 font-bold py-2.5 rounded-xl text-sm transition-all"><i class="fas fa-clipboard-check mr-1"></i>Natija kiritish</button><button data-h-click="h183" class="flex-1 bg-gold-500/20 border border-cobalt-500/25 text-gold-300 font-bold py-2.5 rounded-xl text-sm transition-all"><i class="fas fa-camera mr-1"></i>Foto</button></div>`;
        return `<div class="bg-navy-800 border border-navy-700 hover:border-gold-500/40 rounded-2xl p-5 transition-all">
          <div class="flex items-start justify-between mb-3">
            <div>
              <div class="font-bold text-ink-900">${b.xizmat_nomi || b.xizmat}</div>
              <div class="text-xs text-gray-400 mt-0.5"><i class="fas fa-user mr-1"></i>${m.ism||'—'} &nbsp; <i class="fas fa-phone mr-1"></i>${m.telefon||'—'}</div>
              <div class="text-xs text-gray-400 mt-0.5"><i class="fas fa-map-marker-alt text-gold-400 mr-1"></i>${b.manzil||b.tuman}</div>
            </div>
            <span class="text-xs font-semibold px-3 py-1 rounded-full shrink-0 ml-2 ${hColors[b.holat]||'text-gray-400 bg-gray-400/10'}">${hText[b.holat]||b.holat}</span>
          </div>
          <div class="text-xs text-gray-500 mb-3">${new Date(b.yaratilgan).toLocaleString('uz-UZ')}</div>
          ${btns}
        </div>`;
      }).join('');
      xodimUpdateStats();
    } catch(err) {
      el.innerHTML = '<div class="text-center py-8 text-red-400"><i class="fas fa-exclamation-circle mr-2"></i>Xato yuz berdi</div>';
    }
  }

  async function xodimAccept(id) {
    try {
      await xodimApiPost(`/buyurtmalar/${id}/qabul/`, {});
      showToast('Buyurtma qabul qilindi! Mijozga SMS yuborildi ✓');
      xodimRenderBuyurtmalar();
    } catch(err) { showToast(err?.detail || 'Xato'); }
  }

  async function xodimStartWork(id) {
    try {
      await xodimApiPost(`/buyurtmalar/${id}/`, { holat: 'bajarilmoqda' });
      showToast('Ish boshlandi!');
      xodimRenderBuyurtmalar();
    } catch(err) { showToast('Xato'); }
  }

  async function xodimPopulateOrderSelects() {
    try {
      const data = await xodimApiGet('/buyurtmalar/');
      const faol = (data.results || data).filter(b => b.holat === 'qabul' || b.holat === 'bajarilmoqda');
      const opts = '<option value="">— Tanlang —</option>' + faol.map(b =>
        `<option value="${b.id}">#${String(b.id).slice(-4)} — ${b.xizmat_nomi||b.xizmat} (${b.mijoz_malumot?.ism||'—'})</option>`
      ).join('');
      ['xd-natija-order','xd-foto-order','xd-invoice-order'].forEach(id => {
        const el = document.getElementById(id);
        if (el) el.innerHTML = opts;
      });
    } catch (_) {}
  }

  async function xodimSubmitNatija(e) {
    e.preventDefault();
    const orderId  = +document.getElementById('xd-natija-order').value;
    if (!orderId) { showToast('Buyurtma tanlanmadi!'); return; }
    const natija   = document.getElementById('xd-natija-text').value;
    const soat     = document.getElementById('xd-natija-soat').value;
    const material = document.getElementById('xd-natija-material').value;
    const holat    = document.querySelector('input[name="xd-natija-holat"]:checked').value;
    const btn      = e.target.querySelector('button[type=submit]');
    btn.disabled = true;
    try {
      await xodimApiPost(`/buyurtmalar/${orderId}/natija/`, { natija, natija_soat: soat, material, holat });
      showToast('Natija saqlandi! Mijozga SMS yuborildi ✓');
      e.target.reset();
      xodimUpdateStats();
      xodimPopulateOrderSelects();
    } catch(err) { showToast(err?.detail || 'Xato'); }
    finally { btn.disabled = false; }
  }

  function xodimFotoPreview(input) {
    const preview = document.getElementById('xd-foto-preview');
    preview.innerHTML = '';
    preview.classList.remove('hidden');
    Array.from(input.files).forEach(file => {
      const reader = new FileReader();
      reader.onload = ev => {
        const img = document.createElement('img');
        img.src = ev.target.result;
        img.className = 'w-full h-20 object-cover rounded-xl border border-navy-600';
        preview.appendChild(img);
      };
      reader.readAsDataURL(file);
    });
  }

  async function xodimSaveFoto() {
    const orderId = +document.getElementById('xd-foto-order').value;
    const input   = document.getElementById('xd-foto-input');
    if (!orderId)            { showToast('Buyurtma tanlanmadi!'); return; }
    if (!input.files.length) { showToast('Rasm tanlanmadi!'); return; }
    const fd = new FormData();
    Array.from(input.files).forEach(f => fd.append('rasmlar', f));
    fd.append('tur', 'ish');
    try {
      const res = await fetch(`${API}/buyurtmalar/${orderId}/foto/`, {
        method: 'POST', headers: { 'Authorization': 'Bearer ' + xodimGetToken() }, body: fd
      });
      if (!res.ok) throw {};
      showToast(input.files.length + ' ta rasm yuklandi!');
      document.getElementById('xd-foto-preview').classList.add('hidden');
      input.value = '';
    } catch { showToast('Yuklashda xato'); }
  }

  function xodimInvoicePreview(input) {
    if (!input.files[0]) return;
    const reader = new FileReader();
    reader.onload = ev => {
      document.getElementById('xd-invoice-img').src = ev.target.result;
      document.getElementById('xd-invoice-preview').classList.remove('hidden');
    };
    reader.readAsDataURL(input.files[0]);
  }

  function xodimSaveInvoice() {
    const orderId = +document.getElementById('xd-invoice-order').value;
    const input   = document.getElementById('xd-invoice-input');
    if (!orderId)            { showToast('Buyurtma tanlanmadi!'); return; }
    if (!input.files.length) { showToast('Fayl tanlanmadi!'); return; }
    showToast('Hisob-faktura skrinshoti saqlandi!');
    document.getElementById('xd-invoice-preview').classList.add('hidden');
    input.value = '';
  }

  async function xodimRenderTarix() {
    const el = document.getElementById('xd-tarix-list');
    el.innerHTML = '<div class="text-center py-6 text-gray-500"><i class="fas fa-spinner fa-spin text-xl"></i></div>';
    try {
      const data      = await xodimApiGet('/buyurtmalar/?holat=bajarildi');
      const bajarildi = data.results || data;
      const jami      = bajarildi.length;
      const totalSoat = bajarildi.reduce((s, b) => s + (+b.natija_soat || 0), 0);
      const now       = new Date();
      const oyda      = bajarildi.filter(b => b.natija_sana && new Date(b.natija_sana).getMonth() === now.getMonth()).length;
      document.getElementById('xd-tarix-jami').textContent = jami;
      document.getElementById('xd-tarix-oy').textContent   = oyda;
      document.getElementById('xd-tarix-soat').textContent = totalSoat.toFixed(1);
      if (!jami) {
        el.innerHTML = '<div class="text-center py-12 text-gray-500"><i class="fas fa-history text-4xl mb-3 block opacity-30"></i>Hali bajarilgan ish yo\'q</div>';
        return;
      }
      el.innerHTML = bajarildi.map(b => {
        const m = b.mijoz_malumot || {};
        return `<div class="bg-navy-800 border border-navy-700 rounded-2xl p-4">
          <div class="flex items-start justify-between">
            <div class="flex-1">
              <div class="flex items-center gap-2 mb-1">
                <span class="w-2 h-2 bg-green-400 rounded-full shrink-0"></span>
                <span class="font-semibold text-ink-900 text-sm">${b.xizmat_nomi||b.xizmat}</span>
                <span class="text-xs text-gray-500">#${b.id}</span>
              </div>
              <div class="text-xs text-gray-400 mb-2"><i class="fas fa-user mr-1"></i>${m.ism||'—'} &nbsp; <i class="fas fa-map-marker-alt text-gold-400 mr-1"></i>${b.manzil||b.tuman}</div>
              ${b.natija ? `<div class="text-xs text-gray-300 bg-navy-900 rounded-lg px-3 py-2">${b.natija}</div>` : ''}
            </div>
            <div class="text-right ml-4 shrink-0">
              <div class="text-green-400 font-bold text-sm">✓ Bajarildi</div>
              <div class="text-xs text-gray-500 mt-0.5">${b.natija_sana ? new Date(b.natija_sana).toLocaleDateString('uz-UZ') : ''}</div>
              ${b.natija_soat ? `<div class="text-xs text-gold-400 mt-0.5">${b.natija_soat} soat</div>` : ''}
            </div>
          </div>
        </div>`;
      }).join('');
    } catch { el.innerHTML = '<div class="text-center py-8 text-red-400">Xato yuz berdi</div>'; }
  }

  // Smooth scroll
  document.querySelectorAll('a[href^="#"]').forEach(a => {
    a.addEventListener('click', e => {
      e.preventDefault();
      const h = a.getAttribute('href');
      // Bo'sh «#» (logotip, CTA tugmalar) — selector emas: tepaga qaytmaymiz, xato ham bermaymiz
      const el = h.length > 1 ? document.querySelector(h) : null;
      if (el) el.scrollIntoView({ behavior: 'smooth' });
    });
  });
