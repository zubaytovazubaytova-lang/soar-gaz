/* Hero carousel — vanilla JS, no deps.
   Placeholder slaydlar: keyinroq /images/hero-slider/1.jpg ... 6.jpg (yoki .mp4) qilib almashtiring. */
(function () {
  const root = document.getElementById('hero-carousel');
  if (!root) return;

  // Slaydlar ro'yxati. type: 'image' | 'video'
  // Hozircha mavjud "ish-jarayoni" rasmlaridan foydalanamiz — o'zgartirish oson.
  const slides = [
    { type: 'image', src: 'images/ish-jarayoni/01-kotlovan-qazish.webp',   alt: 'Kotlovan qazish' },
    { type: 'image', src: 'images/ish-jarayoni/03-quvurni-tushirish.webp', alt: 'Quvurni tushirish' },
    { type: 'image', src: 'images/ish-jarayoni/05-tor-joyda-ulash.webp',   alt: 'Ulash' },
    { type: 'image', src: 'images/ish-jarayoni/07-payvand-choki.webp',     alt: 'Payvand choki' },
    { type: 'image', src: 'images/ish-jarayoni/10-izolyatsiya.webp',       alt: 'Izolyatsiya' },
    { type: 'image', src: 'images/ish-jarayoni/11-yakuniy-nazorat.webp',   alt: 'Yakuniy nazorat' },
    // Video misol (fayl mavjud bo'lganda ochib qo'ying):
    // { type: 'video', src: 'images/hero-slider/demo.mp4' },
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
  const INTERVAL = 4000;

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
