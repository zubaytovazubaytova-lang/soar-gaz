/* Bosh sahifa, #tadbir bo'limi: «Yangi gaz trassasi» — kitob varag'i ochiladigandek slayder.
   Chap sahifa — matn, o'ng sahifa — rasm. «Keyingi»da o'ng varaq umurtqa atrofida 3D aylanib
   chapga o'tadi (orqasida yangi matn), ostidan keyingi rasm ochiladi. Telefonda — bitta sahifa.
   «Kelajak Tadbirkori 2026» tadbiri shu bo'limda yonga, ixcham karta bo'lib o'tadi (CSS quyida).
   Markup: index.html dagi <div data-trassa>. Inline-hodisalar yo'q (CSP). */
(function () {
  'use strict';
  const ildiz = document.querySelector('[data-trassa]');
  if (!ildiz) return;

  const SAHIFALAR = [
    { rasm: '01-maydon', sarlavha: 'Maydon ochildi', matn: "Loyiha qog'ozdan yerga ko'chdi: texnika joyida, trassa belgilangan, jamoa safarbar.", shior: "Rejadan zaminga." },
    { rasm: '02-trassa', sarlavha: 'Trassa qazildi', matn: "Ekskavator quvur o'qi bo'ylab xandaq ochdi — chuqurlik va qiyalik loyihaga millimetrgacha mos.", shior: "To'g'ri o'lchov — mustahkam poydevor." },
    { rasm: '03-quvur', sarlavha: 'Quvur joyiga tushirildi', matn: "Tonnalab og'irlikdagi quvur jamoaning bir og'iz ishorasi bilan xandaqqa tushdi. Har kim bir-birining xavfsizligiga javobgar.", shior: "Kuch — uyg'unlikda." },
    { rasm: '04-tayyorgarlik', sarlavha: 'Payvandga tayyorgarlik', matn: "Quvur uchlari tozalandi, qirralari kesildi, moslik tekshirildi. Shoshilmaymiz — sifat shu yerda tug'iladi.", shior: "Yaxshi tayyorgarlik — ishning yarmi." },
    { rasm: '05-payvand', sarlavha: 'Payvand choki', matn: "Elektrod yoyi ikki metallni bir butunga aylantiradi. Bu chok yer ostida o'nlab yillar xizmat qiladi.", shior: "Har bir chok — imzomiz." },
    { rasm: '06-uzluksiz', sarlavha: 'Metrma-metr oldinga', matn: "Bir chok tugaydi — ikkinchisi boshlanadi. Trassa shu tarzda xonadonlarga yaqinlashib boradi.", shior: "Har metr quvur — kimningdir issiq uyi." },
    { rasm: '07-kran', sarlavha: 'Sinovga tayyorgarlik', matn: "Trassa uchlari qopqoq bilan yopildi, kran va manometr o'rnatildi, har bir rezba zichlab tortildi.", shior: "Ishonchni o'lchov asbobi tasdiqlaydi." },
    { rasm: '08-manometr', sarlavha: 'Bosim sinovi', matn: "Quvur me'yoriy bosim bilan to'ldirildi va belgilangan vaqt kuzatildi — manometr ko'rsatkichi o'zgarmadi.", shior: "Bosim tushmadi — ish to'g'ri." },
    { rasm: '09-tayyor', sarlavha: 'Trassa tayyor', matn: "Germetiklik tasdiqlandi. Yangi trassa gaz berishga tayyor — xonadonlarga issiqlik yo'lda.", shior: "Ishonch. Sifat. Mas'uliyat." },
  ];
  const URL = (n) => `images/trassa/${n}.webp`;
  const JAMI = SAHIFALAR.length;
  const esc = (s) => String(s).replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  const raqam = (i) => `${String(i + 1).padStart(2, '0')} / ${String(JAMI).padStart(2, '0')}`;
  const sekin = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  const uslub = document.createElement('style');
  uslub.textContent = `
  /* Bo'lim: chapda trassa kitobi (asosiy), o'ngda tadbir — ixcham karta */
  .sg2-event-grid{display:grid;grid-template-columns:minmax(0,1.85fr) minmax(250px,.8fr);gap:clamp(24px,3.5vw,48px);align-items:center}
  .sg2-event-grid .sg2-ev{grid-template-columns:1fr;gap:14px;padding:16px;border-radius:22px;background:rgba(255,255,255,.06);
    border:1px solid rgba(255,255,255,.12);align-self:center}
  .sg2-event-grid .sg2-ev-stage{max-width:100%;border-radius:16px;justify-self:stretch}
  .sg2-event-grid .sg2-ev-side .sg2-pill{font-size:11px;padding:4px 10px}
  .sg2-event-grid .sg2-ev-side h2{font-size:20px;margin-top:10px}
  .sg2-event-grid .sg2-ev-lead{font-size:13px;margin-top:6px;line-height:1.5}
  .sg2-event-grid .sg2-ev-cap{font-size:14px;margin-top:10px;min-height:2.7em}
  .sg2-event-grid .sg2-ev-thumbs{display:none}
  @media(max-width:1000px){.sg2-event-grid{grid-template-columns:1fr}
    .sg2-event-grid .sg2-ev{grid-template-columns:180px 1fr;align-items:center}}
  /* Telefon: tadbir kartasi — rasm tepada to'liq kenglikda, matn ostida */
  @media(max-width:560px){.sg2-event-grid .sg2-ev{grid-template-columns:1fr;gap:12px;padding:12px}
    .sg2-event-grid .sg2-ev-stage{aspect-ratio:4/3;border-radius:14px}
    .sg2-event-grid .sg2-ev-side h2{font-size:18px;margin-top:8px}.sg2-event-grid .sg2-ev-lead{display:none}
    .sg2-event-grid .sg2-ev-cap{min-height:0;font-size:13.5px}}

  .tk-bosh h2{margin:14px 0 0;font-size:clamp(26px,3vw,40px);font-weight:900;line-height:1.1;letter-spacing:-.02em;color:#fff}
  .tk-bosh h2 em{font-style:normal;color:#ffb866}
  .tk-bosh p{margin:10px 0 22px;max-width:62ch;color:#b9cde6;font-size:15px;line-height:1.6}
  /* Kitob */
  .tk-kitob{position:relative;display:grid;grid-template-columns:1fr 1fr;aspect-ratio:3/2;perspective:2400px;
    border-radius:10px 14px 14px 10px;background:#e9dfc8;outline:none;
    box-shadow:0 46px 80px -40px rgba(0,0,0,.85),0 0 0 1px rgba(255,255,255,.08)}
  .tk-kitob::before{content:'';position:absolute;inset:6px -7px -7px auto;width:12px;border-radius:0 6px 6px 0;z-index:0;
    background:repeating-linear-gradient(90deg,#efe6d1 0 1px,#d8ccb1 1px 2px)}
  .tk-varaq{position:relative;overflow:hidden;z-index:1}
  .tk-chap{border-radius:10px 0 0 10px;padding:clamp(18px,3vw,40px);display:flex;flex-direction:column;color:#2b1d0e;
    background:linear-gradient(90deg,#f7f1e3 0%,#f4ecd9 82%,#e3d6ba 100%)}
  .tk-ong{border-radius:0 14px 14px 0;background:#1b2a3d}
  .tk-ong img,.tk-flip img{width:100%;height:100%;object-fit:cover;display:block}
  .tk-ong::after,.tk-old.tk-rasm::after,.tk-orqa.tk-rasm::after{content:'';position:absolute;inset:0 auto 0 0;width:16%;pointer-events:none;
    background:linear-gradient(90deg,rgba(0,0,0,.38),rgba(0,0,0,0))}
  .tk-umurtqa{position:absolute;top:0;bottom:0;left:50%;width:2px;transform:translateX(-1px);z-index:3;pointer-events:none;
    background:linear-gradient(180deg,rgba(0,0,0,.15),rgba(0,0,0,.35),rgba(0,0,0,.15))}
  .tk-raqam{font:800 12px/1 Inter,Arial,sans-serif;letter-spacing:.18em;color:#a1652a}
  .tk-chap h3{margin:14px 0 10px;font-family:Georgia,'Times New Roman',serif;font-size:clamp(20px,2.4vw,32px);line-height:1.15;color:#1f160b}
  .tk-chap p{margin:0;font-family:Georgia,'Times New Roman',serif;font-size:clamp(13.5px,1.3vw,16.5px);line-height:1.65;color:#4a3826}
  .tk-shior{margin-top:auto;padding-top:14px;border-top:1px solid rgba(120,80,30,.25);font-style:italic;font-family:Georgia,serif;
    font-size:clamp(13px,1.2vw,15px);color:#8a5a22}
  .tk-chap::after{content:'SOAR GAZ';position:absolute;right:18px;bottom:14px;font:800 10px/1 Inter,Arial;letter-spacing:.3em;color:rgba(120,80,30,.35)}
  /* Ag'dariladigan varaq */
  .tk-flip{position:absolute;top:0;bottom:0;width:50%;z-index:4;transform-style:preserve-3d;will-change:transform}
  .tk-flip.oldinga{left:50%;transform-origin:left center;animation:tkOldinga .95s cubic-bezier(.45,.05,.3,1) forwards}
  .tk-flip.ortga{left:0;transform-origin:right center;animation:tkOrtga .95s cubic-bezier(.45,.05,.3,1) forwards}
  .tk-flip>div{position:absolute;inset:0;backface-visibility:hidden;-webkit-backface-visibility:hidden;overflow:hidden}
  .tk-flip>.tk-orqa{transform:rotateY(180deg)}
  .tk-flip .tk-chap{position:absolute}
  .tk-flip>div::before{content:'';position:absolute;inset:0;z-index:2;pointer-events:none;opacity:0;animation:tkSoya .95s ease-in-out forwards}
  .tk-flip.oldinga>.tk-old::before{background:linear-gradient(270deg,rgba(0,0,0,.55),rgba(0,0,0,.05))}
  .tk-flip.oldinga>.tk-orqa::before{background:linear-gradient(90deg,rgba(0,0,0,.05),rgba(0,0,0,.4))}
  .tk-flip.ortga>.tk-old::before{background:linear-gradient(90deg,rgba(0,0,0,.55),rgba(0,0,0,.05))}
  .tk-flip.ortga>.tk-orqa::before{background:linear-gradient(270deg,rgba(0,0,0,.05),rgba(0,0,0,.4))}
  @keyframes tkOldinga{0%{transform:rotateY(0)}100%{transform:rotateY(-180deg)}}
  @keyframes tkOrtga{0%{transform:rotateY(0)}100%{transform:rotateY(180deg)}}
  @keyframes tkSoya{0%{opacity:0}50%{opacity:1}100%{opacity:0}}
  /* Boshqaruv */
  .tk-boshqaruv{display:flex;align-items:center;gap:14px;margin-top:20px}
  .tk-btn{width:46px;height:46px;border-radius:50%;border:1px solid rgba(255,255,255,.3);background:rgba(255,255,255,.08);color:#fff;
    font-size:18px;cursor:pointer;display:grid;place-items:center;transition:background .2s,transform .2s}
  .tk-btn:hover{background:rgba(255,255,255,.2);transform:translateY(-2px)}
  .tk-chiziq{flex:1;height:4px;border-radius:4px;background:rgba(255,255,255,.15);overflow:hidden}
  .tk-chiziq i{display:block;height:100%;width:0;background:linear-gradient(90deg,#ffb866,#ff8a1f);transition:width .6s ease}
  .tk-son{font:800 13px/1 Inter,Arial,sans-serif;letter-spacing:.12em;color:#ffcf99;min-width:68px;text-align:right}
  .tk-mobil{display:none}
  @media(max-width:720px){
    .tk-kitob{grid-template-columns:1fr;aspect-ratio:3/4;border-radius:14px}
    .tk-kitob .tk-chap,.tk-umurtqa{display:none}
    .tk-ong{border-radius:14px}
    .tk-flip,.tk-flip.ortga{left:0;width:100%;transform-origin:left center}
    .tk-flip.ortga{animation-name:tkOldinga}
    .tk-mobil{display:block;margin-top:14px;padding:14px 16px;border-radius:14px;background:#f7f1e3;color:#2b1d0e}
    .tk-mobil h3{margin:6px 0 6px;font-family:Georgia,serif;font-size:20px}
    .tk-mobil p{margin:0;font-family:Georgia,serif;font-size:14px;line-height:1.55;color:#4a3826}
  }
  @media(prefers-reduced-motion:reduce){.tk-flip{display:none}}`;
  document.head.appendChild(uslub);

  // Ota konteyner — ikki ustunli to'r (trassa + tadbir)
  if (ildiz.parentElement) ildiz.parentElement.classList.add('sg2-event-grid');

  ildiz.innerHTML = `
    <div class="tk-bosh">
      <span class="sg2-pill" style="background:rgba(255,255,255,.1);border-color:rgba(255,255,255,.25);color:#fff"><i class="fas fa-location-dot"></i> Buxoro · 24-noyabr · Yangi trassa</span>
      <h2>Yangi gaz trassasi: <em>kotlovandan bosim sinovigacha</em></h2>
      <p>Jamoamiz yangi gaz trassasini barcha bosqichlarda qurib bitkazdi: xandaq ochildi, quvurlar payvandlandi va trassa bosim sinovidan muvaffaqiyatli o'tdi. Varaqlab, mehnatimizni ko'ring.</p>
    </div>
    <div class="tk-kitob" tabindex="0" role="region" aria-roledescription="kitob slayder" aria-label="Trassa qurilishi — kadrlar">
      <div class="tk-varaq tk-chap" data-chap></div>
      <div class="tk-varaq tk-ong" data-ong></div>
      <div class="tk-umurtqa" aria-hidden="true"></div>
    </div>
    <div class="tk-mobil" data-mobil aria-live="polite"></div>
    <div class="tk-boshqaruv">
      <button type="button" class="tk-btn" data-ortga aria-label="Oldingi sahifa">←</button>
      <div class="tk-chiziq" aria-hidden="true"><i data-chiziq></i></div>
      <span class="tk-son" data-son></span>
      <button type="button" class="tk-btn" data-oldinga aria-label="Keyingi sahifa">→</button>
    </div>`;

  const kitob = ildiz.querySelector('.tk-kitob');
  const chap = ildiz.querySelector('[data-chap]');
  const ong = ildiz.querySelector('[data-ong]');
  const mobil = ildiz.querySelector('[data-mobil]');
  const matnHtml = (i) => { const s = SAHIFALAR[i];
    return `<span class="tk-raqam">${raqam(i)}</span><h3>${esc(s.sarlavha)}</h3><p>${esc(s.matn)}</p><div class="tk-shior">${esc(s.shior)}</div>`; };
  // Kechiktirib yuklash (lazy) YO'Q: keyingi kadr oldindan yuklanadi, varaq ochilganda darhol chizilishi kerak
  const rasmHtml = (i) => `<img src="${URL(SAHIFALAR[i].rasm)}" alt="${esc(SAHIFALAR[i].sarlavha)}" width="720" height="960">`;

  let joriy = 0, band = false;
  function chiz(i) {
    chap.innerHTML = matnHtml(i);
    ong.innerHTML = rasmHtml(i);
    mobil.innerHTML = matnHtml(i);
    ildiz.querySelector('[data-son]').textContent = raqam(i);
    ildiz.querySelector('[data-chiziq]').style.width = ((i + 1) / JAMI * 100) + '%';
  }
  // Keyingi kadrni oldindan yuklab qo'yamiz (varaq ochilganda bo'sh joy ko'rinmasin)
  const oldindan = (i) => { const im = new Image(); im.src = URL(SAHIFALAR[(i + JAMI) % JAMI].rasm); };

  function bor(yangi, yon) {
    if (band || yangi === joriy) return;
    yangi = (yangi + JAMI) % JAMI;
    if (sekin) { joriy = yangi; chiz(joriy); return; }
    band = true;
    const eski = joriy;
    const flip = document.createElement('div');
    if (yon > 0) {
      // O'ng varaq ag'dariladi: oldi — eski rasm, orqasi — yangi matn; ostida yangi rasm
      flip.className = 'tk-flip oldinga';
      flip.innerHTML = `<div class="tk-old tk-rasm">${rasmHtml(eski)}</div><div class="tk-orqa tk-chap">${matnHtml(yangi)}</div>`;
      ong.innerHTML = rasmHtml(yangi);
    } else {
      // Chap varaq ortga ag'dariladi: oldi — eski matn, orqasi — oldingi rasm; ostida oldingi matn
      flip.className = 'tk-flip ortga';
      flip.innerHTML = `<div class="tk-old tk-chap">${matnHtml(eski)}</div><div class="tk-orqa tk-rasm">${rasmHtml(yangi)}</div>`;
      chap.innerHTML = matnHtml(yangi);
      if (window.matchMedia('(max-width:720px)').matches) ong.innerHTML = rasmHtml(yangi);
    }
    kitob.appendChild(flip);
    let tugadi = false;
    const yakun = () => {
      if (tugadi) return;
      tugadi = true;
      joriy = yangi;
      chiz(joriy);
      flip.remove();
      band = false;
      oldindan(joriy + 1);
    };
    flip.addEventListener('animationend', (e) => { if (e.target === flip) yakun(); });
    // Zaxira: tab yashirin bo'lsa animatsiya to'xtab, animationend kelmasligi mumkin — slayder qotib qolmasin
    setTimeout(yakun, 1600);
  }
  const keyingi = () => bor(joriy + 1, 1);
  const oldingi = () => bor(joriy - 1, -1);

  ildiz.querySelector('[data-oldinga]').addEventListener('click', () => { keyingi(); qaytaBoshla(); });
  ildiz.querySelector('[data-ortga]').addEventListener('click', () => { oldingi(); qaytaBoshla(); });
  kitob.addEventListener('keydown', (e) => {
    if (e.key === 'ArrowRight') { e.preventDefault(); keyingi(); qaytaBoshla(); }
    if (e.key === 'ArrowLeft') { e.preventDefault(); oldingi(); qaytaBoshla(); }
  });
  kitob.addEventListener('click', (e) => {               // varaqni bosish: o'ng yarmi — keyingi, chap — oldingi
    const r = kitob.getBoundingClientRect();
    if (e.clientX - r.left > r.width / 2) keyingi(); else oldingi();
    qaytaBoshla();
  });
  let tegX = null;
  kitob.addEventListener('touchstart', (e) => { tegX = e.touches[0].clientX; }, { passive: true });
  kitob.addEventListener('touchend', (e) => {
    if (tegX === null) return;
    const dx = e.changedTouches[0].clientX - tegX; tegX = null;
    if (Math.abs(dx) > 40) { (dx < 0 ? keyingi : oldingi)(); qaytaBoshla(); }
  });

  // Avtomatik varaqlash: 6 soniyada bir — sichqoncha ustida yoki bo'lim ko'rinmasa to'xtaydi
  let taymer = null, korinadi = false, ustida = false;
  function qaytaBoshla() {
    clearInterval(taymer);
    if (sekin) return;
    taymer = setInterval(() => { if (korinadi && !ustida && !document.hidden) keyingi(); }, 6000);
  }
  ildiz.addEventListener('mouseenter', () => { ustida = true; });
  ildiz.addEventListener('mouseleave', () => { ustida = false; });
  if ('IntersectionObserver' in window) {
    new IntersectionObserver((y) => { korinadi = y[0].isIntersecting; }, { threshold: 0.35 }).observe(kitob);
  } else { korinadi = true; }

  chiz(0);
  // Bo'limga yaqinlashganda barcha sahifalar oldindan yuklanadi (9 ta, jami ~1,2 MB)
  if ('IntersectionObserver' in window) {
    const kuzat = new IntersectionObserver((y) => {
      if (y[0].isIntersecting) { SAHIFALAR.forEach((_, i) => oldindan(i)); kuzat.disconnect(); }
    }, { rootMargin: '600px' });
    kuzat.observe(kitob);
  } else { oldindan(1); }
  qaytaBoshla();
})();
