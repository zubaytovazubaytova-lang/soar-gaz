/* Rasmiy ruxsatnomalarni kattalashtirib ko'rish oynasi (lightbox) — vanilla JS.
   #litsenziya ichidagi har bir <a class="sg2-doc"> bosilganda katta rasm ochiladi.
   Yopish: X tugmasi, fonga bosish yoki Esc. O'tish: strelkalar yoki chap/o'ng tugmalar. Inline-hodisalar yo'q (CSP). */
(function () {
  'use strict';
  var docs = Array.prototype.slice.call(document.querySelectorAll('#litsenziya .sg2-doc'));
  if (!docs.length) return;

  var box = document.createElement('div');
  box.className = 'sg2-lbox';
  box.setAttribute('role', 'dialog');
  box.setAttribute('aria-modal', 'true');
  box.setAttribute('aria-label', 'Ruxsatnoma');
  box.innerHTML =
    '<button type="button" class="sg2-lbox-x" aria-label="Yopish"><i class="fas fa-times"></i></button>' +
    '<button type="button" class="sg2-lbox-p" aria-label="Oldingi ruxsatnoma"><i class="fas fa-arrow-left"></i></button>' +
    '<button type="button" class="sg2-lbox-n" aria-label="Keyingi ruxsatnoma"><i class="fas fa-arrow-right"></i></button>' +
    '<div class="sg2-lbox-in"><img alt=""><div class="sg2-lbox-cap"></div></div>';
  document.body.appendChild(box);

  var img = box.querySelector('img');
  var cap = box.querySelector('.sg2-lbox-cap');
  var btnX = box.querySelector('.sg2-lbox-x');
  var cur = 0, opener = null;

  function show(i) {
    cur = (i + docs.length) % docs.length;
    var a = docs[cur];
    img.src = a.getAttribute('href');
    img.alt = 'Ruxsatnoma №' + a.getAttribute('data-lic-no');
    cap.innerHTML = '';
    var b = document.createElement('b');
    b.textContent = '№' + a.getAttribute('data-lic-no') + ' · ' + a.getAttribute('data-lic-until') + ' gacha amal qiladi';
    cap.appendChild(b);
    cap.appendChild(document.createTextNode(a.getAttribute('data-lic-title') || ''));
  }

  function open(i, from) {
    opener = from || null;
    show(i);
    box.classList.add('is-open');
    document.documentElement.style.overflow = 'hidden';
    btnX.focus();
  }
  function close() {
    box.classList.remove('is-open');
    document.documentElement.style.overflow = '';
    if (opener) opener.focus();
  }

  docs.forEach(function (a, i) {
    a.addEventListener('click', function (e) { e.preventDefault(); open(i, a); });
  });
  btnX.addEventListener('click', close);
  box.querySelector('.sg2-lbox-p').addEventListener('click', function () { show(cur - 1); });
  box.querySelector('.sg2-lbox-n').addEventListener('click', function () { show(cur + 1); });
  box.addEventListener('click', function (e) { if (e.target === box) close(); });
  document.addEventListener('keydown', function (e) {
    if (!box.classList.contains('is-open')) return;
    if (e.key === 'Escape') close();
    else if (e.key === 'ArrowLeft') show(cur - 1);
    else if (e.key === 'ArrowRight') show(cur + 1);
  });
})();
