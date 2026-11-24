/* Bosh sahifa: «Aksiyalar va yangiliklar» bo'limida seshanba aksiyasi kartasi.
   Ma'lumot: /api/narxnoma/seshanba/ (navbat Django admin → «Seshanba aksiyasi — navbat»).
   «Batafsil» → /kabinet/?aksiya=seshanba: kabinetda ariza oynasi promokod yozilgan holda ochiladi
   (kirmagan bo'lsa — Telegram orqali kirgandan keyin). Navbat bo'sh bo'lsa karta chiqmaydi. */
(function () {
  'use strict';
  const bolim = document.querySelector('#yangiliklar .sg2-news');
  if (!bolim) return;

  const pul = (n) => (Number(n) || 0).toLocaleString('ru-RU').replace(/,/g, ' ') + " so'm";
  const sana = (iso) => { const m = String(iso || '').match(/^(\d{4})-(\d{2})-(\d{2})(?:T(\d{2}):(\d{2}))?/);
    return m ? (m[4] ? `${m[3]}.${m[2]}, ${m[4]}:${m[5]}` : `${m[3]}.${m[2]}`) : ''; };
  const esc = (s) => String(s ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));

  const uslub = document.createElement('style');
  uslub.textContent = `
  .sg-sesh{display:grid;grid-template-columns:auto 1fr auto;gap:22px;align-items:center;margin:0 0 28px;padding:22px 26px;
    border-radius:22px;background:linear-gradient(120deg,#fff7e6 0%,#fde68a 55%,#fbbf24 100%);border:1px solid #f59e0b;
    box-shadow:0 18px 40px -22px rgba(180,83,9,.55);color:#78350f;position:relative;overflow:hidden}
  .sg-sesh::after{content:'';position:absolute;right:-60px;top:-60px;width:220px;height:220px;border-radius:50%;
    background:radial-gradient(circle,rgba(255,255,255,.55),rgba(255,255,255,0) 70%);pointer-events:none}
  .sg-sesh-foiz{width:96px;height:96px;border-radius:22px;background:#0b3d91;color:#fff;display:flex;flex-direction:column;
    align-items:center;justify-content:center;font-weight:900;line-height:1;box-shadow:0 10px 22px -10px rgba(11,61,145,.7)}
  .sg-sesh-foiz b{font-size:32px}.sg-sesh-foiz small{font-size:11px;font-weight:700;margin-top:6px;letter-spacing:.06em;opacity:.85}
  .sg-sesh h3{margin:0 0 4px;font-size:22px;font-weight:900;color:#431407}
  .sg-sesh-holat{font-size:13.5px;font-weight:700;margin:0 0 10px}
  .sg-sesh-holat .kod{display:inline-block;padding:2px 10px;border-radius:8px;background:#0b3d91;color:#fff;letter-spacing:.08em;margin:0 2px}
  .sg-sesh ul{list-style:none;margin:0;padding:0;display:grid;gap:6px}
  .sg-sesh li{font-size:14px;color:#57260a}.sg-sesh li i{font-style:normal;font-weight:800;color:#0b3d91}
  .sg-sesh li s{opacity:.6;margin:0 4px}.sg-sesh li b{color:#14532d}
  .sg-sesh-btn{position:relative;z-index:1;display:inline-flex;align-items:center;gap:8px;padding:14px 22px;border-radius:14px;
    background:#0b3d91;color:#fff;font-weight:800;font-size:15px;text-decoration:none;white-space:nowrap;
    box-shadow:0 10px 22px -10px rgba(11,61,145,.8);transition:transform .2s}
  .sg-sesh-btn:hover{transform:translateY(-2px)}
  @media (max-width:760px){.sg-sesh{grid-template-columns:auto 1fr;padding:18px}.sg-sesh-foiz{width:72px;height:72px}
    .sg-sesh-foiz b{font-size:24px}.sg-sesh h3{font-size:19px}.sg-sesh-btn{grid-column:1/-1;justify-content:center}}
  .sg-sesh.sg-sesh-yonib{animation:sgYonib 1.6s ease-out 1}
  @keyframes sgYonib{0%{box-shadow:0 0 0 0 rgba(245,158,11,.9)}100%{box-shadow:0 0 0 22px rgba(245,158,11,0)}}
  /* Navbardagi «Aksiya ↓» — pastga tebranib turadigan strelka */
  .sg-aksiya-nav{display:inline-flex;align-items:center;gap:6px;padding:6px 12px;margin-right:6px;border-radius:999px;
    background:linear-gradient(135deg,#fbbf24,#f59e0b);color:#431407 !important;font-weight:800;font-size:13px;
    text-decoration:none;white-space:nowrap;box-shadow:0 6px 16px -8px rgba(217,119,6,.9);animation:sgNafas 2.4s ease-in-out infinite}
  .sg-aksiya-nav:hover{filter:brightness(1.05)}
  .sg-aksiya-nav .sg-strelka{display:inline-flex;width:18px;height:18px;border-radius:50%;background:#0b3d91;color:#fff;
    align-items:center;justify-content:center;font-size:11px;animation:sgPastga 1.1s ease-in-out infinite}
  .sg-aksiya-nav.mobil{display:none;padding:5px 10px;font-size:12px;margin-right:2px}
  .sg-aksiya-nav.menyu{display:flex;justify-content:space-between;padding:12px 16px;border-radius:12px;margin:0 0 4px;font-size:14px}
  @keyframes sgPastga{0%,100%{transform:translateY(-2px)}50%{transform:translateY(3px)}}
  @keyframes sgNafas{0%,100%{box-shadow:0 6px 16px -8px rgba(217,119,6,.9)}50%{box-shadow:0 0 0 5px rgba(251,191,36,.35),0 6px 16px -8px rgba(217,119,6,.9)}}
  @media (max-width:1023px){.sg-aksiya-nav.mobil{display:inline-flex}}
  @media (prefers-reduced-motion:reduce){.sg-aksiya-nav,.sg-aksiya-nav .sg-strelka,.sg-sesh.sg-sesh-yonib{animation:none}}`;
  document.head.appendChild(uslub);

  // Navbar: «Aksiya −N% ↓» — bosilganda aksiya kartasiga silliq tushadi va karta bir marta «yonadi»
  function navbargaQosh(karta, foiz) {
    const borish = (e) => {
      e.preventDefault();
      const menyu = document.getElementById('mobileNav');
      if (menyu && !menyu.classList.contains('hidden')) {
        const burger = document.querySelector('button[aria-label="Menyu"]');
        if (burger) burger.click();
      }
      karta.scrollIntoView({ behavior: 'smooth', block: 'center' });
      karta.classList.remove('sg-sesh-yonib');
      setTimeout(() => karta.classList.add('sg-sesh-yonib'), 450);
    };
    const yasa = (sinf) => {
      const a = document.createElement('a');
      a.href = '#seshanba-aksiya';
      a.className = 'sg-aksiya-nav' + (sinf ? ' ' + sinf : '');
      a.setAttribute('aria-label', `Seshanba aksiyasi: ${foiz}% chegirma — pastga o'tish`);
      a.innerHTML = `Aksiya −${foiz}% <span class="sg-strelka" aria-hidden="true">↓</span>`;
      a.addEventListener('click', borish);
      return a;
    };
    const desktop = document.querySelector('nav a.nav-link[href="#xaridlar"]');
    if (desktop && desktop.parentNode) desktop.parentNode.insertBefore(yasa(''), desktop);
    const burger = document.querySelector('nav button[aria-label="Menyu"]');
    if (burger && burger.parentNode) burger.parentNode.insertBefore(yasa('mobil'), burger);
    const menyu = document.querySelector('#mobileNav .flex');
    if (menyu) menyu.insertBefore(yasa('menyu'), menyu.firstChild);
  }

  fetch('/api/narxnoma/seshanba/', { credentials: 'same-origin' })
    .then((r) => (r.ok ? r.json() : null))
    .then((d) => {
      if (!d || !d.bor || !(d.xizmatlar || []).length) return;
      const holat = d.bugun
        ? `🟢 Hozir amalda · promokod <span class="kod">${esc(d.promokod)}</span> · ${esc(sana(d.tugash))} gacha`
        : `🗓 Keyingi seshanba: ${esc(sana(d.sana))} · promokod shu kuni beriladi (50 soat amal qiladi)`;
      const qatorlar = d.xizmatlar.map((x) => `<li><i>${esc(x.kim_uchun || '')}:</i> ${esc(x.nomi)}`
        + (x.narx != null ? ` — <s>${pul(x.narx)}</s><b>${pul(x.chegirmali)}</b>` : '') + '</li>').join('');
      const karta = document.createElement('div');
      karta.className = 'sg-sesh';
      karta.id = 'seshanba-aksiya';
      karta.innerHTML = `
        <div class="sg-sesh-foiz"><b>−${Number(d.foiz)}%</b><small>SESHANBA</small></div>
        <div><h3>Seshanba aksiyasi — servis xizmatlariga chegirma</h3>
          <p class="sg-sesh-holat">${holat}</p><ul>${qatorlar}</ul></div>
        <a class="sg-sesh-btn" href="/kabinet/?aksiya=seshanba">Batafsil <span aria-hidden="true">→</span></a>`;
      bolim.parentNode.insertBefore(karta, bolim);
      navbargaQosh(karta, Number(d.foiz));
    })
    .catch(() => { /* aksiya ma'lumoti kelmasa karta chiqmaydi */ });
})();
