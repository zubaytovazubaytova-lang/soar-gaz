/* Hero (asmanuni.uz uslubi) — vanilla JS, kutubxonasiz.
   Fon fotolari va matnlar index.html dagi #sg2-hero ichida turadi:
   har bir <img class="sg2-hero-img"> ning data-title / data-sub atributlari
   shu slayd uchun sarlavha va izohni beradi. Bu fayl faqat almashtiradi. */
(function () {
  'use strict';
  var root = document.getElementById('sg2-hero');
  if (!root) return;

  var imgs = Array.prototype.slice.call(root.querySelectorAll('.sg2-hero-img'));
  var title = root.querySelector('[data-hero-title]');
  var sub = root.querySelector('[data-hero-sub]');
  var dotsWrap = root.querySelector('[data-hc-dots]');
  if (imgs.length < 2 || !dotsWrap) return;

  var INTERVAL = 6000;
  var cur = 0;
  var timer = null;
  var kamHarakat = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  var dots = imgs.map(function (_, i) {
    var b = document.createElement('button');
    b.type = 'button';
    b.className = 'sg2-dot' + (i === 0 ? ' is-active' : '');
    b.setAttribute('aria-label', 'Slayd ' + (i + 1));
    b.addEventListener('click', function () { goTo(i); start(); });
    dotsWrap.appendChild(b);
    return b;
  });

  function matnQoy(el, matn) {
    if (!el || matn == null) return;
    if (kamHarakat) { el.textContent = matn; return; }
    el.classList.add('is-out');
    setTimeout(function () { el.textContent = matn; el.classList.remove('is-out'); }, 350);
  }

  function goTo(i) {
    var next = (i + imgs.length) % imgs.length;
    if (next === cur) return;
    imgs[cur].classList.remove('is-active');
    dots[cur].classList.remove('is-active');
    imgs[next].classList.add('is-active');
    dots[next].classList.add('is-active');
    matnQoy(title, imgs[next].getAttribute('data-title'));
    matnQoy(sub, imgs[next].getAttribute('data-sub'));
    cur = next;
  }

  function stop() { if (timer) { clearInterval(timer); timer = null; } }
  function start() {
    stop();
    if (kamHarakat) return;
    timer = setInterval(function () { goTo(cur + 1); }, INTERVAL);
  }

  document.addEventListener('visibilitychange', function () {
    if (document.hidden) stop(); else start();
  });
  start();
})();
