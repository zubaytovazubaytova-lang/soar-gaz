/* "Kelajak Tadbirkori 2026" lavhalari slayderi — vanilla JS, kutubxonasiz.
   Markup: index.html dagi #tadbir ichida ([data-ev] ...). Inline-hodisalar yo'q (CSP). */
(function () {
  'use strict';
  var root = document.querySelector('[data-ev]');
  if (!root) return;

  var slides = Array.prototype.slice.call(root.querySelectorAll('.sg2-ev-slide'));
  var thumbs = Array.prototype.slice.call(root.querySelectorAll('.sg2-ev-th'));
  var stage = root.querySelector('[data-ev-stage]');
  var capEl = root.querySelector('[data-ev-cap]');
  var countEl = root.querySelector('[data-ev-count]');
  var bar = root.querySelector('[data-ev-bar]');
  var prev = root.querySelector('[data-ev-prev]');
  var next = root.querySelector('[data-ev-next]');
  if (slides.length < 2 || !stage) return;

  var INTERVAL = 5500;
  var cur = 0, timer = null, hover = false, visible = false;
  var kam = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  root.style.setProperty('--ev-ms', INTERVAL + 'ms');

  function pad(n) { return (n < 10 ? '0' : '') + n; }

  function show(i) {
    var n = (i + slides.length) % slides.length;
    slides.forEach(function (s, k) {
      s.classList.toggle('is-active', k === n);
      s.setAttribute('aria-hidden', k === n ? 'false' : 'true');
    });
    thumbs.forEach(function (t, k) {
      t.classList.toggle('is-active', k === n);
      if (k === n) t.setAttribute('aria-current', 'true'); else t.removeAttribute('aria-current');
    });
    var matn = slides[n].getAttribute('data-cap') || '';
    if (capEl) {
      if (kam) capEl.textContent = matn;
      else {
        capEl.classList.add('is-out');
        setTimeout(function () { capEl.textContent = matn; capEl.classList.remove('is-out'); }, 250);
      }
    }
    if (countEl) countEl.textContent = pad(n + 1) + ' / ' + pad(slides.length);
    cur = n;
  }

  function runBar() {
    if (!bar || kam) return;
    bar.classList.remove('is-run');
    void bar.offsetWidth;            // animatsiyani qayta boshlash
    bar.classList.add('is-run');
  }

  function stop() {
    clearTimeout(timer); timer = null;
    if (bar) bar.classList.remove('is-run');
  }
  function start() {
    stop();
    if (kam || hover || !visible || document.hidden) return;
    runBar();
    timer = setTimeout(function () { show(cur + 1); start(); }, INTERVAL);
  }
  function go(i) { show(i); start(); }

  if (prev) prev.addEventListener('click', function () { go(cur - 1); });
  if (next) next.addEventListener('click', function () { go(cur + 1); });
  thumbs.forEach(function (t, k) { t.addEventListener('click', function () { go(k); }); });

  root.addEventListener('mouseenter', function () { hover = true; stop(); });
  root.addEventListener('mouseleave', function () { hover = false; start(); });
  root.addEventListener('focusin', function () { hover = true; stop(); });
  root.addEventListener('focusout', function () { hover = false; start(); });
  document.addEventListener('visibilitychange', start);

  root.addEventListener('keydown', function (e) {
    if (e.key === 'ArrowLeft') { go(cur - 1); }
    else if (e.key === 'ArrowRight') { go(cur + 1); }
  });

  // Surish (swipe)
  var x0 = null;
  stage.addEventListener('pointerdown', function (e) { x0 = e.clientX; });
  stage.addEventListener('pointerup', function (e) {
    if (x0 == null) return;
    var dx = e.clientX - x0; x0 = null;
    if (Math.abs(dx) > 40) go(dx < 0 ? cur + 1 : cur - 1);
  });
  stage.addEventListener('pointercancel', function () { x0 = null; });

  // Faqat ko'rinib turganda avtomatik almashsin
  if ('IntersectionObserver' in window) {
    new IntersectionObserver(function (en) {
      visible = en[0].isIntersecting; start();
    }, { threshold: 0.25 }).observe(root);
  } else { visible = true; start(); }

  show(0);
})();
