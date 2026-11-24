/* "Kelajak Tadbirkori 2026" lavhalari slayderi — vanilla JS, kutubxonasiz.
   O'zi doim aylanib turadi (qo'lda boshqarilmaydi): har 2 soniyada shaxmat effekti bilan
   almashadi — yangi rasm kataklar bo'lib (avval bir rangdagi kataklar, keyin ikkinchisi) ochiladi.
   Markup: index.html dagi #tadbir ichida ([data-ev] ...). Inline-hodisalar yo'q (CSP). */
(function () {
  'use strict';
  var root = document.querySelector('[data-ev]');
  if (!root) return;

  var slides = Array.prototype.slice.call(root.querySelectorAll('.sg2-ev-slide'));
  var thumbs = Array.prototype.slice.call(root.querySelectorAll('.sg2-ev-th'));
  var stage = root.querySelector('[data-ev-stage]');
  var capEl = root.querySelector('[data-ev-cap]');
  if (slides.length < 2 || !stage) return;

  var COLS = 6, ROWS = 7;          // shaxmat taxtasi (rasm nisbatiga yaqin kvadrat kataklar)
  var CYCLE = 2000;                // bir slayd ko'rinib turish + almashish: 2 soniya
  var TILE = 340;                  // bitta katak ochilish vaqti, ms
  var WAVE = 230;                  // ikkinchi rang kataklari kechikishi, ms
  var RIPPLE = 14;                 // diagonal bo'ylab kechikish, ms
  var TOTAL = TILE + WAVE + (COLS + ROWS - 2) * RIPPLE + 40;
  var HOLD = Math.max(CYCLE - TOTAL, 400);

  var cur = 0, timer = null, busy = null;
  var kam = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  // Rasmlar oldindan yuklansin (shaxmat kataklari ularni fon sifatida ishlatadi)
  slides.forEach(function (s) {
    var im = s.querySelector('img');
    if (im) { im.loading = 'eager'; }
  });

  function setActive(n) {
    slides.forEach(function (s, k) {
      s.classList.toggle('is-active', k === n);
      s.setAttribute('aria-hidden', k === n ? 'false' : 'true');
    });
    cur = n;
  }

  function setMeta(n) {
    thumbs.forEach(function (t, k) { t.classList.toggle('is-active', k === n); });
    var matn = slides[n].getAttribute('data-cap') || '';
    if (!capEl) return;
    if (kam) { capEl.textContent = matn; return; }
    capEl.classList.add('is-out');
    setTimeout(function () { capEl.textContent = matn; capEl.classList.remove('is-out'); }, 220);
  }

  function finish() {
    if (!busy) return;
    clearTimeout(busy.t);
    setActive(busy.to);
    if (busy.el.parentNode) busy.el.parentNode.removeChild(busy.el);
    busy = null;
  }

  function chess(to) {
    var im = slides[to].querySelector('img');
    var src = im ? (im.currentSrc || im.src) : '';
    var el = document.createElement('div');
    el.className = 'sg2-ev-chess';
    el.setAttribute('aria-hidden', 'true');
    el.style.gridTemplateColumns = 'repeat(' + COLS + ',1fr)';
    el.style.gridTemplateRows = 'repeat(' + ROWS + ',1fr)';
    for (var r = 0; r < ROWS; r++) {
      for (var c = 0; c < COLS; c++) {
        var t = document.createElement('i');
        t.style.backgroundImage = 'url("' + src + '")';
        t.style.backgroundSize = (COLS * 100) + '% ' + (ROWS * 100) + '%';
        t.style.backgroundPosition = (c / (COLS - 1) * 100) + '% ' + (r / (ROWS - 1) * 100) + '%';
        t.style.animationDelay = (((r + c) % 2) * WAVE + (r + c) * RIPPLE) + 'ms';
        el.appendChild(t);
      }
    }
    stage.appendChild(el);
    busy = { to: to, el: el, t: setTimeout(finish, TOTAL) };
  }

  function show(i) {
    finish();
    var n = (i + slides.length) % slides.length;
    if (n === cur) return;
    setMeta(n);
    if (kam) { setActive(n); return; }
    chess(n);
  }

  function tick() {
    show(cur + 1);
    timer = setTimeout(tick, HOLD + TOTAL);
  }

  // Sahifa yashirin (boshqa varaq) bo'lganda to'xtab, qaytganda davom etadi; boshqa to'xtatish yo'q
  function sync() {
    clearTimeout(timer); timer = null;
    if (!document.hidden) timer = setTimeout(tick, HOLD + TOTAL);
  }
  document.addEventListener('visibilitychange', sync);

  setActive(0);
  setMeta(0);
  sync();
})();
