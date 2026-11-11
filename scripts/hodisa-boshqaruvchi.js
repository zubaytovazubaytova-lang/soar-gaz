/* ============================================================
   SOAR GAZ — hodisa boshqaruvchisi (inline onclick="..." o'rniga)
   ------------------------------------------------------------
   Nega kerak: Content-Security-Policy `script-src` dan 'unsafe-inline'
   olib tashlangan, shuning uchun HTML ichidagi onclick="..." ishlamaydi.
   Ularning o'rniga elementda faqat belgi turadi:

       data-h-click="h12"        -> SG_H.h12 (sahifa-hodisalar.js dagi funksiya)
       data-h-click="c:fn"       -> fn(...argumentlar)  (JS shablonlaridagi chaqiruvlar)
       data-a-click='[...]'      -> shu chaqiruv argumentlari (JSON)

   Argumentlarda "@this" — hodisa tegishli element, "@event" — hodisaning o'zi.

   Hodisalar document'da BITTA marta tinglanadi (delegatsiya), shuning uchun
   keyinroq innerHTML bilan qo'shilgan elementlar ham ishlayveradi.
   Faqat SG_H ro'yxatidagi funksiyalar chaqiriladi — atributga yozilgan
   ixtiyoriy matn bajarilmaydi (HTML kiritib yuborgan hujumchi ham
   ro'yxatdan tashqari hech narsa ishga tushira olmaydi).
   ============================================================ */
(function () {
  'use strict';
  var R = window.SG_H = window.SG_H || {};

  /* Shablon ichida argumentlarni atributga xavfsiz yozish: SG_A([id, nom]) */
  window.SG_A = function (royxat) {
    return JSON.stringify(royxat)
      .replace(/&/g, '&amp;').replace(/"/g, '&quot;')
      .replace(/</g, '&lt;').replace(/>/g, '&gt;');
  };

  /* "c:fn" handlerlari uchun argumentlarni o'qish */
  window.SG_ARGS = function (el, e) {
    var xom = el.getAttribute('data-a-' + e.type), a = [];
    try { a = JSON.parse(xom || '[]'); } catch (x) { a = []; }
    return a.map(function (v) { return v === '@this' ? el : (v === '@event' ? e : v); });
  };

  function ushla(e) {
    var attr = 'data-h-' + e.type;
    var n = e.target;
    /* Inline handler kabi: avval elementning o'zi, keyin ota-onalari (pastdan yuqoriga) */
    while (n && n !== document) {
      if (n.getAttribute) {
        var id = n.getAttribute(attr);
        if (id && Object.prototype.hasOwnProperty.call(R, id) && typeof R[id] === 'function') {
          if (R[id].call(n, e) === false) e.preventDefault();   // «return false» ma'nosi
        }
      }
      n = n.parentNode;
    }
  }

  /* Capture: focus/blur/error kabi ko'pirmaydigan hodisalar ham ushlanadi */
  ['click', 'dblclick', 'submit', 'input', 'change', 'keydown', 'keyup', 'keypress', 'focus', 'blur',
   'mouseover', 'mouseout', 'error', 'contextmenu', 'touchstart', 'touchend', 'load']
    .forEach(function (ev) { document.addEventListener(ev, ushla, true); });
})();
