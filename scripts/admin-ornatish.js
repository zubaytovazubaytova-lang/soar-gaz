/* Admin panelni kompyuterga alohida ilova sifatida o'rnatish (PWA).
   Chrome / Edge «O'rnatish» taklifini bersa — topbarda «Kompyuterga o'rnatish» tugmasi chiqadi.
   O'rnatilgach panel o'z oynasida, ish stoli / Pusk menyusidagi belgisi bilan ochiladi.
   sw.js /boshqaruv/ sahifalarini KESHLAMAYDI: panel doim serverdagi eng yangi holatda. */
(function () {
  'use strict';
  const tugma = document.getElementById('ornatishBtn');
  let taklif = null;

  // Ilova manifesti faqat /boshqaruv/ manzilida amal qiladi (eski /admin.html havolasidan — o'tkazamiz)
  if (location.pathname === '/admin.html') {
    location.replace('/boshqaruv/' + location.search + location.hash);
    return;
  }

  if ('serviceWorker' in navigator && location.protocol === 'https:') {
    navigator.serviceWorker.register('/sw.js').catch(function () { /* o'rnatishga to'sqinlik qilmaydi */ });
  }

  const ornatilgan = window.matchMedia('(display-mode: standalone)').matches || navigator.standalone === true;
  if (ornatilgan || !tugma) return;

  window.addEventListener('beforeinstallprompt', function (e) {
    e.preventDefault();
    taklif = e;
    tugma.hidden = false;
  });

  tugma.addEventListener('click', async function () {
    if (!taklif) return;
    taklif.prompt();
    try { await taklif.userChoice; } catch (err) { /* bekor qilindi */ }
    taklif = null;
    tugma.hidden = true;
  });

  window.addEventListener('appinstalled', function () {
    taklif = null;
    tugma.hidden = true;
  });
})();
