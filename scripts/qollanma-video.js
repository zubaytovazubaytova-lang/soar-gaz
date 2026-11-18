/* "Ariza qoldiring" bo'limidagi video qo'llanma (images/qollanma/).
 *
 * - Video sahifa ochilganda yuklanmaydi (preload="none") — faqat bo'lim
 *   ekranga chiqqanda yuklanib o'ynaydi, ekrandan chiqsa to'xtaydi.
 * - Bosish (yoki Enter/Probel) — to'xtatish/davom ettirish. Foydalanuvchi o'zi
 *   to'xtatgan bo'lsa, qayta ekranga chiqqanda avtomatik o'ynamaydi.
 * - "Harakatni kamaytirish" yoqilgan bo'lsa avtomatik o'ynamaydi — oddiy
 *   boshqaruv tugmalari ko'rsatiladi.
 */
(function () {
  'use strict';

  var video = document.querySelector('video[data-qollanma]');
  if (!video) return;

  var kamHarakat = window.matchMedia &&
    window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  if (kamHarakat || !('IntersectionObserver' in window)) {
    video.controls = true;
    return;
  }

  var qoldaToxtatilgan = false;

  function oyna() {
    var natija = video.play();
    // Brauzer avtomatik o'ynatishni taqiqlasa — boshqaruv tugmalarini ko'rsatamiz
    if (natija && natija.catch) natija.catch(function () { video.controls = true; });
  }

  function almashtir() {
    if (video.paused) { qoldaToxtatilgan = false; oyna(); }
    else { qoldaToxtatilgan = true; video.pause(); }
  }

  new IntersectionObserver(function (yozuvlar) {
    yozuvlar.forEach(function (y) {
      if (y.isIntersecting) { if (!qoldaToxtatilgan) oyna(); }
      else if (!video.paused) video.pause();
    });
  }, { threshold: 0.35 }).observe(video);

  video.addEventListener('click', almashtir);
  video.addEventListener('keydown', function (e) {
    if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); almashtir(); }
  });
})();
