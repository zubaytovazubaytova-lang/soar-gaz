/* Hero carousel — vanilla JS, no deps.
   Slaydlar ro'yxati pastda (images/hero-slider/). */
(function () {
  const root = document.getElementById('hero-carousel');
  if (!root) return;

  // Slaydlar ro'yxati. type: 'image' | 'video'
  // Rasmlar images/hero-slider/ da: N.webp (2000px, kompyuter) va N-m.webp (900px, telefon).
  // Matn rasmning o'zida, shuning uchun alt shu matnni takrorlaydi.
  const slides = [
    { type: 'image', src: 'images/hero-slider/1.webp', small: 'images/hero-slider/1-m.webp',
      alt: "SOAR GAZ — Gaz va isitish yechimlari: loyihalash, montaj va texnik xizmat" },
    { type: 'image', src: 'images/hero-slider/2.webp', small: 'images/hero-slider/2-m.webp',
      alt: "SOAR GAZ — Qozon va radiator servisi: diagnostika va tizimni yuvish" },
    { type: 'image', src: 'images/hero-slider/3.webp', small: 'images/hero-slider/3-m.webp',
      alt: "SOAR GAZ — AGNKS uchun servis: uskunalarga texnik xizmat" },
  ];

  const track = root.querySelector('.hc-track');
  const dotsWrap = root.querySelector('[data-hc-dots]');
  const prevBtn = root.querySelector('[data-hc-prev]');
  const nextBtn = root.querySelector('[data-hc-next]');

  // Slaydlarni yarat
  slides.forEach((s, i) => {
    const el = document.createElement('div');
    // Ko'rinish faqat `is-active` sinfi bilan boshqariladi. Ilgari bu yerda
    // Tailwind sinflari (opacity-100/z-10) ishlatilgan edi, lekin karuselning
    // o'z CSS'i `#hero-carousel` id'si orqali yozilgani uchun undan kuchliroq
    // bo'lib, slaydlar ko'rinmay qolishi mumkin edi.
    el.className = 'hc-slide' + (i === 0 ? ' is-active' : '');
    if (s.type === 'video') {
      const v = document.createElement('video');
      v.src = s.src;
      v.muted = true;
      v.loop = true;
      v.autoplay = true;
      v.playsInline = true;
      v.className = 'w-full h-full object-cover';
      el.appendChild(v);
    } else {
      const img = document.createElement('img');
      img.src = s.src;
      if (s.small) { img.srcset = s.small + ' 900w, ' + s.src + ' 2000w'; img.sizes = '100vw'; }
      img.decoding = 'async';
      if (i === 0) img.fetchPriority = 'high';
      img.alt = s.alt || '';
      img.loading = i === 0 ? 'eager' : 'lazy';
      img.className = 'w-full h-full object-cover';
      el.appendChild(img);
    }
    // Yengil pastki gradient (matnsiz ham chiroyli ko'rinishi uchun)
    const shade = document.createElement('div');
    shade.className = 'hc-shade';
    el.appendChild(shade);
    track.appendChild(el);
  });

  // Dots yarat
  const dots = slides.map((_, i) => {
    const b = document.createElement('button');
    b.type = 'button';
    b.setAttribute('aria-label', 'Slayd ' + (i + 1));
    b.className = 'hc-dot' + (i === 0 ? ' is-active' : '');
    b.addEventListener('click', () => goTo(i, true));
    dotsWrap.appendChild(b);
    return b;
  });

  const slideEls = Array.from(track.querySelectorAll('.hc-slide'));
  let current = 0;
  let timer = null;
  const INTERVAL = 6000;   // matn rasmda — o'qishga vaqt kerak

  function goTo(i, userAction) {
    const next = (i + slides.length) % slides.length;
    if (next === current) return;
    slideEls[current].classList.remove('is-active');
    slideEls[next].classList.add('is-active');

    dots[current].classList.remove('is-active');
    dots[next].classList.add('is-active');

    current = next;
    if (userAction) restart();
  }

  function next() { goTo(current + 1); }
  function prev() { goTo(current - 1); }

  function start() { stop(); timer = setInterval(next, INTERVAL); }
  function stop()  { if (timer) { clearInterval(timer); timer = null; } }
  function restart() { start(); }

  prevBtn.addEventListener('click', () => { prev(); restart(); });
  nextBtn.addEventListener('click', () => { next(); restart(); });
  root.addEventListener('mouseenter', stop);
  root.addEventListener('mouseleave', start);
  document.addEventListener('visibilitychange', () => {
    if (document.hidden) stop(); else start();
  });

  start();
})();
