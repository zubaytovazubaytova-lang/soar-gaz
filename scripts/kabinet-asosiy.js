/* ============================================================
   SOAR GAZ — MIJOZ KABINETI
   Barcha ma'lumot Django API dan keladi (/api/kabinet/...).
   Sessiya index.html bilan umumiy: sg_token / sg_refresh / sg_user.
   ============================================================ */

const API = location.protocol === 'file:' ? 'http://localhost:8001/api' : '/api';

/* Sahifa "/kabinet/" manzilida ochilganda nisbiy havola "/kabinet/index.html" ga
   ketib qoladi — shuning uchun havolalar absolyut. Fayl sifatida ochilsa (file://)
   eski nisbiy nomlar ishlatiladi. */
const FAYL_REJIM = location.protocol === 'file:';
const ASOSIY_SAYT = FAYL_REJIM ? 'index.html' : '/';
const XODIM_SAHIFA = FAYL_REJIM ? 'xodimlar.html' : '/xodimlar/';

// Hududlar — viloyat bo'yicha guruhlangan. Bu ro'yxatni QO'LDA tahrirlamang:
// u backend/apps/auth_app/hududlar.py dan generatsiya qilinadi:
//     python manage.py hududlar_yangila
// HUDUD:BOSH
const HUDUDLAR = [
  ["Qoraqalpog'iston Respublikasi", ["Nukus shahri", "Amudaryo tumani", "Beruniy tumani", "Bo'zatov tumani", "Chimboy tumani", "Ellikqal'a tumani", "Kegeyli tumani", "Mo'ynoq tumani", "Nukus tumani", "Qanliko'l tumani", "Qo'ng'irot tumani", "Qorao'zak tumani", "Shumanay tumani", "Taxtako'pir tumani", "To'rtko'l tumani", "Xo'jayli tumani"]],
  ["Andijon viloyati", ["Andijon shahri", "Xonobod shahri", "Andijon tumani", "Asaka tumani", "Baliqchi tumani", "Bo'ston tumani", "Buloqboshi tumani", "Izboskan tumani", "Jalaquduq tumani", "Qo'rg'ontepa tumani", "Marhamat tumani", "Oltinko'l tumani", "Paxtaobod tumani", "Shahrixon tumani", "Ulug'nor tumani", "Xo'jaobod tumani"]],
  ["Buxoro viloyati", ["Buxoro shahri", "Kogon shahri", "Buxoro tumani", "G'ijduvon tumani", "Jondor tumani", "Kogon tumani", "Olot tumani", "Peshku tumani", "Qorako'l tumani", "Qorovulbozor tumani", "Romitan tumani", "Shofirkon tumani", "Vobkent tumani"]],
  ["Farg'ona viloyati", ["Farg'ona shahri", "Marg'ilon shahri", "Qo'qon shahri", "Quvasoy shahri", "Beshariq tumani", "Bog'dod tumani", "Buvayda tumani", "Dang'ara tumani", "Farg'ona tumani", "Furqat tumani", "Oltiariq tumani", "Qo'shtepa tumani", "Quva tumani", "Rishton tumani", "So'x tumani", "Toshloq tumani", "Uchko'prik tumani", "O'zbekiston tumani", "Yozyovon tumani"]],
  ["Jizzax viloyati", ["Jizzax shahri", "Arnasoy tumani", "Baxmal tumani", "Do'stlik tumani", "Forish tumani", "G'allaorol tumani", "Mirzacho'l tumani", "Paxtakor tumani", "Sharof Rashidov tumani", "Yangiobod tumani", "Zafarobod tumani", "Zarbdor tumani", "Zomin tumani"]],
  ["Namangan viloyati", ["Namangan shahri", "Chortoq tumani", "Chust tumani", "Davlatobod tumani", "Kosonsoy tumani", "Mingbuloq tumani", "Namangan tumani", "Norin tumani", "Pop tumani", "To'raqo'rg'on tumani", "Uchqo'rg'on tumani", "Uychi tumani", "Yangiqo'rg'on tumani"]],
  ["Navoiy viloyati", ["Navoiy shahri", "Zarafshon shahri", "Karmana tumani", "Konimex tumani", "Navbahor tumani", "Nurota tumani", "Qiziltepa tumani", "Tomdi tumani", "Uchquduq tumani", "Xatirchi tumani"]],
  ["Qashqadaryo viloyati", ["Qarshi shahri", "Shahrisabz shahri", "Chiroqchi tumani", "Dehqonobod tumani", "G'uzor tumani", "Kasbi tumani", "Kitob tumani", "Koson tumani", "Ko'kdala tumani", "Mirishkor tumani", "Muborak tumani", "Nishon tumani", "Qamashi tumani", "Qarshi tumani", "Shahrisabz tumani", "Yakkabog' tumani"]],
  ["Samarqand viloyati", ["Samarqand shahri", "Kattaqo'rg'on shahri", "Bulung'ur tumani", "Ishtixon tumani", "Jomboy tumani", "Kattaqo'rg'on tumani", "Narpay tumani", "Nurobod tumani", "Oqdaryo tumani", "Paxtachi tumani", "Payariq tumani", "Pastdarg'om tumani", "Qo'shrabot tumani", "Samarqand tumani", "Toyloq tumani", "Urgut tumani"]],
  ["Sirdaryo viloyati", ["Guliston shahri", "Shirin shahri", "Yangiyer shahri", "Boyovut tumani", "Guliston tumani", "Mirzaobod tumani", "Oqoltin tumani", "Sardoba tumani", "Sayxunobod tumani", "Sirdaryo tumani", "Xovos tumani"]],
  ["Surxondaryo viloyati", ["Termiz shahri", "Angor tumani", "Bandixon tumani", "Boysun tumani", "Denov tumani", "Jarqo'rg'on tumani", "Muzrabot tumani", "Oltinsoy tumani", "Qiziriq tumani", "Qumqo'rg'on tumani", "Sariosiyo tumani", "Sherobod tumani", "Sho'rchi tumani", "Termiz tumani", "Uzun tumani"]],
  ["Toshkent viloyati", ["Nurafshon shahri", "Angren shahri", "Bekobod shahri", "Chirchiq shahri", "Olmaliq shahri", "Ohangaron shahri", "Yangiyo'l shahri", "Bekobod tumani", "Bo'ka tumani", "Bo'stonliq tumani", "Chinoz tumani", "Ohangaron tumani", "Oqqo'rg'on tumani", "Parkent tumani", "Piskent tumani", "Qibray tumani", "Quyi Chirchiq tumani", "O'rta Chirchiq tumani", "Yangiyo'l tumani", "Yuqori Chirchiq tumani", "Zangiota tumani"]],
  ["Xorazm viloyati", ["Urganch shahri", "Xiva shahri", "Bog'ot tumani", "Gurlan tumani", "Hazorasp tumani", "Qo'shko'pir tumani", "Shovot tumani", "Tuproqqal'a tumani", "Urganch tumani", "Xonqa tumani", "Xiva tumani", "Yangiariq tumani", "Yangibozor tumani"]],
  ["Toshkent shahri", ["Bektemir tumani", "Chilonzor tumani", "Mirobod tumani", "Mirzo Ulug'bek tumani", "Olmazor tumani", "Sergeli tumani", "Shayxontohur tumani", "Uchtepa tumani", "Yakkasaroy tumani", "Yashnobod tumani", "Yunusobod tumani"]],
];
// HUDUD:OXIR

// Guruhlangan ro'yxatdan <optgroup> yasaydi; `tanlangan` bo'lsa belgilaydi
function hududOptionlari(tanlangan) {
  return HUDUDLAR.map(([viloyat, tumanlar]) => {
    const ichi = tumanlar.map(t =>
      `<option ${t === tanlangan ? 'selected' : ''}>${t}</option>`).join('');
    return `<optgroup label="${viloyat}">${ichi}</optgroup>`;
  }).join('');
}

const XIZMATLAR = [
  ['montaj','Montaj — gaz jihozini o\'rnatish'],
  ['servis','Servis va ta\'mirlash'],
  ['metrologiya','Metrologiya — hisoblagich tekshiruvi'],
  ['loyiha','Loyihalashtirish'],
  ['uskunalar','Uskuna almashtirish'],
];

const BOSQICH_NOMLARI = [
  ['yangi','Yangi'],
  ['korilmoqda',"Ko'rib chiqilmoqda"],
  ['tayinlandi','Xodim tayinlandi'],
  ['bajarilmoqda','Bajarilmoqda'],
  ['yakunlandi','Yakunlandi'],
];

let profil = null;         // joriy foydalanuvchi
let obzorMalumot = null;   // bosh sahifa ma'lumoti
let obyektlarKesh = [];    // forma select'lari uchun
let joriyBuyurtmaFiltr = '';
let joriyHujjatFiltr = '';
let taymerId = null;

/* ---------- kichik yordamchilar ---------- */
const el = (id) => document.getElementById(id);

function xabar(matn, xato) {
  const t = el('toast');
  t.textContent = matn;
  t.className = 'ko' + (xato ? ' xato' : '');
  setTimeout(() => { t.className = ''; }, 2600);
}

function xavfsiz(s) {
  return String(s == null ? '' : s)
    .replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;')
    .replace(/"/g,'&quot;').replace(/'/g,'&#39;');
}

function sana(qiymat, vaqtBilan) {
  if (!qiymat) return '—';
  const d = new Date(qiymat);
  if (isNaN(d)) return '—';
  const s = d.toLocaleDateString('uz-UZ', { day:'2-digit', month:'long', year:'numeric' });
  return vaqtBilan ? s + ', ' + d.toLocaleTimeString('uz-UZ',{hour:'2-digit',minute:'2-digit'}) : s;
}

function pul(summa) {
  return (Number(summa) || 0).toLocaleString('uz-UZ') + " so'm";
}

function bosh(harf) {
  const s = (harf || '').trim();
  return s ? s.split(/\s+/).slice(0,2).map(x => x[0].toUpperCase()).join('') : '?';
}

/* ---------- «Uning ko'zi bilan ko'rish» (egasi, faqat o'qish) ----------
   Egasi boshqaruv panelidan shu sahifani ochadi; token URL fragmentidan olinadi va
   FAQAT shu tabning sessionStorage'ida turadi — egasining o'z sessiyasiga (localStorage)
   tegilmaydi. Server bu token bilan o'zgartiruvchi so'rovlarni baribir rad etadi;
   bu yerda ham ularni yubormaymiz. */
let KORISH = false;
try {
  const m = location.hash.match(/korish=([^&]+)/);
  if (m) {
    sessionStorage.setItem('sg_token', decodeURIComponent(m[1]));
    sessionStorage.setItem('sg_korish', '1');
    sessionStorage.removeItem('sg_refresh');
    sessionStorage.removeItem('sg_user');
    history.replaceState(null, '', location.pathname + location.search);   // token manzilda qolmasin
  }
  KORISH = sessionStorage.getItem('sg_korish') === '1';
} catch (e) {}
const saqlash = KORISH ? sessionStorage : localStorage;

function korishBannerKorsat(ism) {
  el('korishIsm').textContent = ism;
  el('korishBanner').style.display = 'block';
  document.body.classList.add('korish');
}
function korishChiq() {
  ['sg_token', 'sg_refresh', 'sg_user', 'sg_korish'].forEach(k => sessionStorage.removeItem(k));
  window.close();                                         // boshqaruv paneli ochgan tab yopiladi
  setTimeout(() => { location.href = '/boshqaruv/'; }, 250);   // yopilmasa — panelga qaytadi
}
document.addEventListener('DOMContentLoaded', () => {
  el('korishChiqish').addEventListener('click', korishChiq);
});

/* ---------- token boshqaruvi ---------- */
function tokenSaqla(d) {
  // Refresh token httpOnly cookie'da (serverga tegishli) — JavaScript uni saqlamaydi
  saqlash.setItem('sg_token', d.access);
  saqlash.removeItem('sg_refresh');
  if (d.user) saqlash.setItem('sg_user', JSON.stringify(d.user));
}
function tokenOchir() {
  // Serverda refresh tokenni bekor qilamiz va cookie'ni o'chiramiz. Ko'rish rejimida
  // (egasi mijoz nomidan ochgan tab) tegilmaydi: cookie boshqa sessiyaga tegishli.
  if (!KORISH) {
    try {
      fetch(API + '/auth/chiqish/', {
        method: 'POST', keepalive: true,
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ refresh: saqlash.getItem('sg_refresh') || undefined })
      }).catch(() => {});
    } catch (e) {}
  }
  ['sg_token','sg_refresh','sg_user'].forEach(k => saqlash.removeItem(k));
}

/* Bir vaqtda ketgan bir nechta 401 uchun refresh BIR marta chaqiriladi: server
   har refreshdan keyin eski tokenni bekor qiladi, ikkinchi parallel so'rov
   mijozni tizimdan chiqarib yuborardi. Refresh httpOnly cookie'da — brauzer o'zi yuboradi. */
let _tokenYangilash = null;
function tokenYangila() {
  if (_tokenYangilash) return _tokenYangilash;
  if (KORISH) return Promise.resolve(false);     // ko'rish tokeni yangilanmaydi
  const eski = saqlash.getItem('sg_refresh');    // eski sessiya: bir martalik cookie'ga ko'chish
  _tokenYangilash = (async () => {
    try {
      const j = await fetch(API + '/auth/token/yangilash/', {
        method:'POST', headers:{'Content-Type':'application/json'},
        body: JSON.stringify(eski ? { refresh: eski } : {})
      });
      saqlash.removeItem('sg_refresh');
      if (!j.ok) return false;
      const d = await j.json();
      saqlash.setItem('sg_token', d.access);
      return true;
    } catch (e) { return false; }
    finally { _tokenYangilash = null; }
  })();
  return _tokenYangilash;
}

/* Maxfiy amal (email/telefon almashtirish, hisobni o'chirish) uchun SMS kod: serverga
   so'rov yuboramiz; server kod kerakligini aytsa, kod so'rab, so'rovni qaytaramiz. */
async function smsTasdiqBilan(yol, sozlama) {
  try {
    return await so(yol, sozlama);
  } catch (err) {
    if (!err.kodKerak) throw err;
  }
  await so('/auth/tasdiq-kodi/', { method: 'POST', body: {} });
  const kod = prompt("Xavfsizlik uchun telefoningizga SMS kod yuborildi.\nKodni kiriting:");
  if (!kod) throw new Error('Tasdiqlash bekor qilindi');
  const tana = Object.assign({}, JSON.parse(sozlama.body), { tasdiq_kodi: kod.trim() });
  return so(yol, Object.assign({}, sozlama, { body: JSON.stringify(tana) }));
}

/* API so'rovi — 401 bo'lsa refresh token bilan bir marta qayta uriniladi */
async function so(yol, sozlama, qaytaUrinma) {
  sozlama = sozlama || {};
  // Ko'rish rejimi: faqat o'qish — o'zgartiruvchi so'rov serverga yuborilmaydi
  if (KORISH && String(sozlama.method || 'GET').toUpperCase() !== 'GET') {
    throw new Error("Ko'rish rejimida o'zgartirish mumkin emas");
  }
  const bosh_ = Object.assign({}, sozlama.headers);
  const token = saqlash.getItem('sg_token');
  if (token) bosh_['Authorization'] = 'Bearer ' + token;
  if (sozlama.body && !(sozlama.body instanceof FormData)) {
    bosh_['Content-Type'] = 'application/json';
    if (typeof sozlama.body !== 'string') sozlama.body = JSON.stringify(sozlama.body);
  }

  let javob;
  try {
    javob = await fetch(API + yol, Object.assign({}, sozlama, { headers: bosh_ }));
  } catch (e) {
    throw new Error('Server bilan aloqa yo\'q. Backend ishga tushganini tekshiring.');
  }

  if (javob.status === 401 && KORISH) {
    alert("Ko'rish rejimi muddati tugadi. Boshqaruv panelidan qaytadan oching.");
    korishChiq();
    throw new Error("Ko'rish rejimi tugadi");
  }
  if (javob.status === 401 && !qaytaUrinma) {
    if (await tokenYangila()) return so(yol, sozlama, true);
    tokenOchir();
    kirishKorsat();
    throw new Error('Sessiya tugadi. Qaytadan kiring.');
  }

  const matn = await javob.text();
  const malumot = matn ? JSON.parse(matn) : null;
  if (!javob.ok) {
    const xato = (malumot && (malumot.detail || Object.values(malumot)[0])) || 'Xatolik yuz berdi';
    const e = new Error(Array.isArray(xato) ? xato[0] : xato);
    e.kodKerak = !!(malumot && malumot.kod_kerak) && javob.status === 403;
    throw e;
  }
  return malumot;
}

/* ============================================================
   KIRISH: telefon → SMS kod → profil
   ============================================================ */
let kirishTelefon = '';

function authXato(matn) {
  const p = el('authXato');
  if (!matn) { p.className = 'auth-error'; return; }
  p.textContent = matn;
  p.className = 'auth-error show';
}

function qadamgaOt(n) {
  authXato('');
  [1,2,3].forEach(i => {
    el('qadam' + i).style.display = i === n ? 'block' : 'none';
    el('qn' + i).classList.toggle('active', i <= n);
  });
  if (n === 2) setTimeout(() => el('kodInput').focus(), 50);
}

function telefonTozala(xom) {
  const raqamlar = String(xom).replace(/\D/g, '');
  return raqamlar ? '+' + raqamlar : '';
}

async function kodYubor(e) {
  e.preventDefault();
  const btn = el('kodBtn');
  const telefon = telefonTozala(el('telefonInput').value);
  if (telefon.length < 12) { authXato("Telefon raqamni to'liq kiriting: +998 XX XXX XX XX"); return; }

  btn.disabled = true;
  try {
    await so('/auth/otp/yuborish/', { method:'POST', body:{ telefon } });
    kirishTelefon = telefon;
    el('kodTelefon').textContent = telefon;
    el('kodInput').value = '';
    qadamgaOt(2);
    taymerBoshla();
  } catch (err) { authXato(err.message); }
  btn.disabled = false;
}

function taymerBoshla() {
  let qoldi = 60;
  const btn = el('qaytaBtn');
  btn.disabled = true;
  btn.innerHTML = 'Qayta yuborish (<span id="taymer">60</span>s)';
  clearInterval(taymerId);
  taymerId = setInterval(() => {
    qoldi--;
    if (qoldi <= 0) {
      clearInterval(taymerId);
      btn.disabled = false;
      btn.textContent = 'Kodni qayta yuborish';
    } else {
      btn.innerHTML = 'Qayta yuborish (' + qoldi + 's)';
    }
  }, 1000);
}

async function kodQaytaYubor() {
  try {
    await so('/auth/otp/yuborish/', { method:'POST', body:{ telefon: kirishTelefon } });
    xabar('Kod qayta yuborildi');
    taymerBoshla();
  } catch (err) { authXato(err.message); }
}

async function kodTasdiqla(e) {
  e.preventDefault();
  const btn = el('tasdiqBtn');
  const kod = el('kodInput').value.trim();
  if (kod.length !== 6) { authXato('6 xonali kodni kiriting'); return; }

  btn.disabled = true;
  try {
    const d = await so('/auth/otp/tasdiqlash/', { method:'POST', body:{ telefon: kirishTelefon, kod } });
    tokenSaqla(d);
    profil = d.user;
    if (!profil.ism || !profil.manzil || !profil.tuman) {
      tumanlarniQoy(el('pTuman'));
      el('pTuman').value = profil.tuman || '';
      el('pMahalla').value = profil.mahalla || '';
      el('pTuman').viloyatniMoslash && el('pTuman').viloyatniMoslash();
      el('pIsm').value = profil.ism || '';
      el('pManzil').value = profil.manzil || '';
      qadamgaOt(3);
    } else {
      kabinetOch();
    }
  } catch (err) { authXato(err.message); }
  btn.disabled = false;
}

async function profilSaqla(e) {
  e.preventDefault();
  const btn = el('profilBtn');
  btn.disabled = true;
  try {
    profil = await so('/auth/profil/', { method:'PATCH', body:{
      ism: el('pIsm').value.trim(),
      viloyat: el('pViloyat').value,
      tuman: el('pTuman').value,
      mahalla: el('pMahalla').value.trim(),
      manzil: el('pManzil').value.trim(),
      moljal: el('pMoljal').value.trim(),
      mulk_turi: el('pMulk').value,
    }});
    saqlash.setItem('sg_user', JSON.stringify(profil));
    kabinetOch();
  } catch (err) { authXato(err.message); }
  btn.disabled = false;
}

function tumanlarniQoy(select) {
  if (!select || select.dataset.toldirilgan) return;
  const bor = select.options.length ? '' : '<option value="">Tanlang...</option>';
  select.innerHTML = bor + hududOptionlari();
  select.dataset.toldirilgan = '1';
  // Yonidagi viloyat tanlovini bog'laymiz (id: pTuman -> pViloyat)
  const viloyatId = select.id.replace(/Tuman$/, 'Viloyat');
  viloyatTumanUla(el(viloyatId), select);
}

// Viloyat -> tuman bog'lanishi. Tuman ro'yxati <optgroup> bo'lib guruhlangan,
// guruh sarlavhasi — viloyat nomi. Shuning uchun viloyat ro'yxati ham,
// filtrlash ham o'sha sarlavhalardan kelib chiqadi.
function viloyatTumanUla(viloyatSel, tumanSel) {
  if (!viloyatSel || !tumanSel || tumanSel.dataset.ulangan) return;
  tumanSel.dataset.ulangan = '1';

  const guruhlar = Array.from(tumanSel.getElementsByTagName('optgroup'));
  viloyatSel.innerHTML = '<option value="">Tanlang...</option>' +
    guruhlar.map(g => `<option>${g.label}</option>`).join('');

  function filtrla(tozala) {
    const v = viloyatSel.value;
    guruhlar.forEach(g => {
      const mos = !v || g.label === v;
      g.style.display = mos ? '' : 'none';
      if (!mos && tozala && tumanSel.selectedOptions[0] &&
          tumanSel.selectedOptions[0].parentElement === g) tumanSel.value = '';
    });
    tumanSel.disabled = !v;
  }

  viloyatSel.addEventListener('change', () => filtrla(true));
  tumanSel.viloyatniMoslash = function () {
    const t = tumanSel.selectedOptions[0];
    if (t && t.parentElement.tagName === 'OPTGROUP') viloyatSel.value = t.parentElement.label;
    filtrla(false);
  };
  tumanSel.viloyatniMoslash();
}

function kirishKorsat() {
  el('dashView').style.display = 'none';
  el('authView').style.display = 'flex';
  qadamgaOt(1);
}

function chiqish() {
  tokenOchir();
  profil = null;
  kirishTelefon = '';
  el('telefonInput').value = '';
  kirishKorsat();
}

/* ============================================================
   KABINET
   ============================================================ */
async function kabinetOch() {
  el('authView').style.display = 'none';
  el('dashView').style.display = 'block';
  profilChiqar();
  await boshYukla();
  pageOch('bosh');
}

function profilChiqar() {
  if (!profil) return;
  el('avatarKichik').textContent = bosh(profil.ism);
  el('avatarKatta').textContent = bosh(profil.ism);
  el('chipIsm').textContent = profil.ism || 'Mijoz';
  el('chipTel').textContent = profil.telefon || '';
  el('boshIsm').textContent = profil.ism || 'Mijoz';
  el('boshManzil').textContent = [profil.tuman, profil.manzil].filter(Boolean).join(', ') || 'Manzil kiritilmagan';
  el('qTelefon').value = profil.telefon || '';
}

const SAHIFA_NOMLARI = {
  bosh:'Bosh sahifa', buyurtmalar:'Mening buyurtmalarim', obyektlar:'Mening obyektlarim',
  hisoblagichlar:'Hisoblagichlarim va texnik ko\'rik', tolovlar:"To'lovlar va hisob-fakturalar",
  hujjatlar:'Hujjatlarim', bildirishnomalar:'Bildirishnomalar', sharhlar:'Sharhlarim',
  yordam:'Yordam markazi', sozlamalar:'Profil sozlamalari',
};

const YUKLAGICH = {
  bosh: boshYukla, buyurtmalar: buyurtmalarYukla, obyektlar: obyektlarYukla,
  hisoblagichlar: hisoblagichlarYukla, tolovlar: tolovlarYukla, hujjatlar: hujjatlarYukla,
  bildirishnomalar: bildirishnomalarYukla, sharhlar: sharhlarYukla, yordam: yordamYukla,
  sozlamalar: sozlamalarYukla,
};

function pageOch(nom) {
  document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
  el('page-' + nom).classList.add('active');
  document.querySelectorAll('.sb-item[data-page]').forEach(b =>
    b.classList.toggle('active', b.dataset.page === nom));
  el('sahifaSarlavha').textContent = SAHIFA_NOMLARI[nom] || '';
  yonPanel(false);
  window.scrollTo(0, 0);
  const yuk = YUKLAGICH[nom];
  if (yuk) yuk().catch(e => xabar(e.message, true));
}

function yonPanel(ochiq) {
  el('sidebar').classList.toggle('open', ochiq);
  el('sbBackdrop').classList.toggle('open', ochiq);
}

function oqilmaganChiqar(soni) {
  const nuqta = el('bellDot'), belgi = el('sbBadge');
  nuqta.style.display = soni ? 'flex' : 'none';
  nuqta.textContent = soni > 9 ? '9+' : soni;
  belgi.style.display = soni ? 'inline-block' : 'none';
  belgi.textContent = soni;
}

/* ---------- 1. BOSH SAHIFA ---------- */
async function boshYukla() {
  const d = await so('/kabinet/obzor/');
  obzorMalumot = d;
  profil = Object.assign({}, profil, d.mijoz);
  profilChiqar();
  oqilmaganChiqar(d.oqilmagan_bildirishnoma);

  el('boshStat').innerHTML = `
    <div class="stat-box"><p class="n">${d.faol_buyurtma}</p><p class="l">Faol buyurtma</p></div>
    <div class="stat-box ok"><p class="n">${d.bajarilgan_buyurtma}</p><p class="l">Bajarilgan xizmat</p></div>
    <div class="stat-box"><p class="n">${d.obyekt_soni}</p><p class="l">Obyektlarim</p></div>
    <div class="stat-box ${d.kutilayotgan_tolov ? 'warn' : ''}"><p class="n">${d.kutilayotgan_tolov}</p><p class="l">Kutilayotgan to'lov</p></div>`;

  el('tezTolovIzoh').textContent = d.kutilayotgan_tolov
    ? d.kutilayotgan_tolov + ' ta — ' + pul(d.kutilayotgan_summa)
    : "Qarzdorlik yo'q";

  const k = d.keyingi_xizmat;
  el('boshEslatma').innerHTML = k
    ? `<div class="eslatma ${k.kun_qoldi < 0 ? 'otgan' : (k.kun_qoldi <= 30 ? 'yaqin' : 'yaxshi')}">
         <i class="ti ti-calendar-event"></i>
         <div style="flex:1">
           <h5>Keyingi metrologik tekshiruv: ${sana(k.sana)}</h5>
           <p>${xavfsiz(k.obyekt)} — hisoblagich ${xavfsiz(k.hisoblagich)}.
              ${k.kun_qoldi < 0 ? 'Muddati ' + Math.abs(k.kun_qoldi) + ' kun oldin tugagan!'
                                : k.kun_qoldi + ' kun qoldi.'}</p>
         </div>
         <button class="btn asosiy kichik" data-h-click="h11">Yozilish</button>
       </div>`
    : `<div class="eslatma yaxshi"><i class="ti ti-circle-check"></i>
         <div><h5>Rejalashtirilgan xizmat yo'q</h5>
         <p>Hisoblagich qo'shsangiz, tekshiruv muddati avtomatik kuzatiladi.</p></div></div>`;

  el('boshBuyurtmalar').innerHTML = d.oxirgi_buyurtmalar.length
    ? d.oxirgi_buyurtmalar.map(b => `
        <div class="row-item">
          <div class="row-ikon"><i class="ti ti-tool"></i></div>
          <div class="r-info">
            <h5>#${b.id} — ${xavfsiz(b.xizmat_nomi)}</h5>
            <p>${sana(b.yaratilgan)} · ${xavfsiz(b.manzil || b.tuman || '')}</p>
          </div>
          ${holatTegi(b.holat)}
        </div>`).join('')
    : '<p class="bosh-holat">Hali buyurtma bermagansiz.</p>';
}

function holatTegi(holat) {
  const xarita = {
    yangi:['plan','Yangi'], qabul:['progress','Xodim tayinlandi'],
    bajarilmoqda:['progress','Bajarilmoqda'], bajarildi:['done','Yakunlandi'],
    bekor:['bad','Bekor qilindi'],
  };
  const [sinf, nom] = xarita[holat] || ['plan', holat];
  return `<span class="tag ${sinf}">${nom}</span>`;
}

/* ---------- 2. BUYURTMALAR ---------- */
function buyurtmaFiltrla(f) {
  joriyBuyurtmaFiltr = f;
  document.querySelectorAll('#buyurtmaFiltr .filtr-tab').forEach(b =>
    b.classList.toggle('active', b.dataset.f === f));
  buyurtmalarYukla().catch(e => xabar(e.message, true));
}

async function buyurtmalarYukla() {
  const f = joriyBuyurtmaFiltr;
  let so_rov = '/kabinet/buyurtmalar/';
  if (f === 'faol' || f === 'yakunlangan') so_rov += '?holat=' + f;
  else if (f) so_rov += '?xizmat=' + f;

  const royxat = await so(so_rov);
  el('buyurtmaRoyxat').innerHTML = royxat.length ? royxat.map(b => `
    <div class="mini-karta" style="margin-bottom:14px">
      <div style="display:flex;justify-content:space-between;gap:12px;align-items:flex-start">
        <div>
          <h5>#${b.id} — ${xavfsiz(b.xizmat_nomi)}</h5>
          <p class="manzil">${sana(b.yaratilgan, true)}</p>
        </div>
        ${holatTegi(b.holat)}
      </div>
      ${b.holat === 'bekor' ? '' : bosqichChiziq(b.bosqich)}
      <div style="margin-top:14px">
        <div class="kv"><span>Manzil</span><span>${xavfsiz(b.obyekt_nomi || b.manzil || b.tuman || '—')}</span></div>
        ${b.xodim_malumot ? `<div class="kv"><span>Keladigan xodim</span><span>${xavfsiz(b.xodim_malumot.ism || '—')} · ${xavfsiz(b.xodim_malumot.telefon)}</span></div>` : ''}
        ${b.vaqt_istagi ? `<div class="kv"><span>Taxminiy vaqt</span><span>${xavfsiz(b.vaqt_istagi)}</span></div>` : ''}
        ${b.tavsif ? `<div class="kv"><span>Tavsif</span><span>${xavfsiz(b.tavsif)}</span></div>` : ''}
        ${b.natija ? `<div class="kv"><span>Natija</span><span>${xavfsiz(b.natija)}</span></div>` : ''}
      </div>
      ${b.holat === 'bajarildi' && !b.baholangan
        ? `<button class="btn sokin kichik" style="margin-top:12px" data-h-click="c:sharhModalOch" data-a-click="${SG_A([b.id, String(b.xizmat_nomi)])}"><i class="ti ti-star"></i> Baho qoldirish</button>` : ''}
    </div>`).join('') : '<p class="bosh-holat">Bu bo\'limda buyurtma topilmadi.</p>';
}

function bosqichChiziq(joriy) {
  const indeks = BOSQICH_NOMLARI.findIndex(x => x[0] === joriy);
  return '<div class="bosqich-chiziq">' + BOSQICH_NOMLARI.map(([kod, nom], i) => {
    const sinf = i < indeks ? 'done' : (i === indeks ? 'now' : '');
    return `<div class="bq ${sinf}"><div class="nuqta"></div><span>${nom}</span></div>`;
  }).join('') + '</div>';
}

/* Yangi ariza */
function arizaModalOch() {
  obyektlarKeshYukla().then(() => {
    modalOch('Yangi ariza qoldirish', `
      <form data-h-submit="h44">
        <label class="f-label" for="aXizmat">Xizmat turi *</label>
        <select class="f-select" id="aXizmat" required>
          <option value="">Tanlang...</option>
          ${XIZMATLAR.map(([k,n]) => `<option value="${k}">${n}</option>`).join('')}
        </select>
        <label class="f-label" for="aObyekt">Obyekt</label>
        <select class="f-select" id="aObyekt">
          <option value="">Profildagi asosiy manzil</option>
          ${obyektlarKesh.map(o => `<option value="${o.id}">${xavfsiz(o.nom)} — ${xavfsiz(o.manzil)}</option>`).join('')}
        </select>
        <label class="f-label" for="aVaqt">Qulay vaqt *</label>
        <select class="f-select" id="aVaqt" required>
          <option>Bugun (imkon bo'lsa)</option>
          <option>Ertaga ertalab (09:00–12:00)</option>
          <option>Ertaga tushdan keyin (13:00–18:00)</option>
          <option>2 kun ichida</option>
          <option>Operator bog'lansin</option>
        </select>
        <label class="f-label" for="aTel">Bog'lanish raqami (ixtiyoriy)</label>
        <input class="f-input" id="aTel" type="tel" placeholder="+998 90 123 45 67" autocomplete="tel">
        <p class="f-hint" style="margin:-8px 0 14px;font-size:12px;opacity:.7">Bo'sh qoldirsangiz profilingizdagi raqamga qo'ng'iroq qilinadi.</p>
        <label class="f-label" for="aTavsif">Muammo tavsifi</label>
        <textarea class="f-area" id="aTavsif" placeholder="Qisqacha yozing..."></textarea>
        <button class="btn asosiy" type="submit" style="width:100%;justify-content:center"><i class="ti ti-send"></i> Arizani yuborish</button>
      </form>`);
  }).catch(e => xabar(e.message, true));
}

async function arizaYubor(e) {
  e.preventDefault();
  const tana = {
    xizmat: el('aXizmat').value,
    vaqt_istagi: el('aVaqt').value,
    tavsif: el('aTavsif').value.trim(),
  };
  const obyekt = el('aObyekt').value;
  if (obyekt) tana.obyekt = Number(obyekt);
  const aloqaTel = el('aTel').value.trim();
  if (aloqaTel) tana.mijoz_telefon = aloqaTel;
  try {
    const b = await so('/buyurtmalar/', { method:'POST', body: tana });
    modalYop();
    xabar('Ariza #' + b.id + ' qabul qilindi');
    pageOch('buyurtmalar');
  } catch (err) { xabar(err.message, true); }
}

/* ---------- 3. OBYEKTLAR ---------- */
async function obyektlarKeshYukla() {
  obyektlarKesh = await so('/kabinet/obyektlar/');
  return obyektlarKesh;
}

async function obyektlarYukla() {
  const royxat = await obyektlarKeshYukla();
  el('obyektRoyxat').innerHTML = royxat.length ? '<div class="grid-kartalar">' + royxat.map(o => `
    <div class="mini-karta">
      <div style="display:flex;justify-content:space-between;gap:8px;align-items:flex-start">
        <div>
          <h5>${xavfsiz(o.nom)} ${o.asosiy ? '<span class="tag done">Asosiy</span>' : ''}</h5>
          <p class="manzil">${xavfsiz(o.turi_nomi)} · ${xavfsiz([o.tuman, o.manzil].filter(Boolean).join(', '))}</p>
        </div>
      </div>
      ${o.moljal ? `<div class="kv"><span>Mo'ljal</span><span>${xavfsiz(o.moljal)}</span></div>` : ''}
      ${o.rezervuar_hajmi ? `<div class="kv"><span>Rezervuar</span><span>${o.rezervuar_hajmi} litr</span></div>` : ''}
      <div class="kv"><span>Hisoblagich</span><span>${o.hisoblagichlar.length} ta</span></div>
      <div class="kv"><span>Uskunalar</span><span>${o.uskunalar.length ? o.uskunalar.map(u => xavfsiz(u.nom)).join(', ') : '—'}</span></div>
      <div class="kv"><span>Buyurtmalar</span><span>${o.buyurtma_soni} ta</span></div>
      <div style="display:flex;gap:8px;margin-top:12px;flex-wrap:wrap">
        <button class="btn sokin kichik" data-h-click="c:obyektModalOch" data-a-click="${SG_A([o.id])}"><i class="ti ti-edit"></i> Tahrirlash</button>
        <button class="btn sokin kichik" data-h-click="c:uskunaModalOch" data-a-click="${SG_A([o.id])}"><i class="ti ti-plus"></i> Uskuna</button>
        <button class="btn sokin kichik" data-h-click="c:obyektOchir" data-a-click="${SG_A([o.id])}"><i class="ti ti-trash"></i></button>
      </div>
    </div>`).join('') + '</div>'
    : '<p class="bosh-holat">Obyekt qo\'shilmagan. Bir nechta manzilda xizmat olsangiz, har birini alohida qo\'shing.</p>';
}

function obyektModalOch(id) {
  const o = obyektlarKesh.find(x => x.id === id) || {};
  modalOch(id ? 'Obyektni tahrirlash' : 'Yangi obyekt', `
    <form data-h-submit="c:obyektSaqla" data-a-submit="${SG_A(['@event', id || 0])}">
      <label class="f-label" for="oNom">Obyekt nomi *</label>
      <input class="f-input" id="oNom" required placeholder="Masalan: Uy, Dala hovli, Ofis" value="${xavfsiz(o.nom || '')}">
      <div class="ikki-ustun">
        <div>
          <label class="f-label" for="oTuri">Turi</label>
          <select class="f-select" id="oTuri">
            ${[['uy','Xususiy uy'],['kvartira','Kvartira'],['dala_hovli','Dala hovli'],['ofis','Ofis'],['korxona','Korxona / tashkilot']]
              .map(([k,n]) => `<option value="${k}" ${o.turi===k?'selected':''}>${n}</option>`).join('')}
          </select>
        </div>
        <div>
          <label class="f-label" for="oViloyat">Viloyat</label>
          <select class="f-select" id="oViloyat"></select>
          <label class="f-label" for="oTuman">Tuman / shahar</label>
          <select class="f-select" id="oTuman">
            <option value="">Tanlang...</option>
            ${hududOptionlari(o.tuman)}
          </select>
          <label class="f-label" for="oMahalla">Mahalla / ko'cha</label>
          <input class="f-input" id="oMahalla" maxlength="120" placeholder="ixtiyoriy"
                 value="${xavfsiz(o.mahalla || '')}">
        </div>
      </div>
      <label class="f-label" for="oManzil">Manzil *</label>
      <input class="f-input" id="oManzil" required placeholder="Ko'cha, uy raqami" value="${xavfsiz(o.manzil || '')}">
      <label class="f-label" for="oMoljal">Mo'ljal</label>
      <input class="f-input" id="oMoljal" value="${xavfsiz(o.moljal || '')}">
      <label class="f-label" for="oRezervuar">Rezervuar hajmi (litr)</label>
      <input class="f-input" id="oRezervuar" type="number" min="0" value="${o.rezervuar_hajmi || ''}">
      <label style="display:flex;align-items:center;gap:9px;font-size:13px;font-weight:600;margin-bottom:16px">
        <input type="checkbox" id="oAsosiy" ${o.asosiy ? 'checked' : ''}> Asosiy obyekt sifatida belgilash
      </label>
      <button class="btn asosiy" type="submit" style="width:100%;justify-content:center"><i class="ti ti-device-floppy"></i> Saqlash</button>
    </form>`);
  // Modal DOM ga qo'yilgach viloyat tanlovini bog'laymiz
  viloyatTumanUla(el('oViloyat'), el('oTuman'));
}

async function obyektSaqla(e, id) {
  e.preventDefault();
  const tana = {
    nom: el('oNom').value.trim(),
    turi: el('oTuri').value,
    viloyat: el('oViloyat').value,
    tuman: el('oTuman').value,
    mahalla: el('oMahalla').value.trim(),
    manzil: el('oManzil').value.trim(),
    moljal: el('oMoljal').value.trim(),
    rezervuar_hajmi: el('oRezervuar').value ? Number(el('oRezervuar').value) : null,
    asosiy: el('oAsosiy').checked,
  };
  try {
    if (id) await so('/kabinet/obyektlar/' + id + '/', { method:'PATCH', body: tana });
    else await so('/kabinet/obyektlar/', { method:'POST', body: tana });
    modalYop();
    xabar('Obyekt saqlandi');
    obyektlarYukla();
  } catch (err) { xabar(err.message, true); }
}

async function obyektOchir(id) {
  if (!confirm("Obyekt o'chirilsinmi? Unga bog'langan hisoblagich va uskunalar ham o'chadi.")) return;
  try {
    await so('/kabinet/obyektlar/' + id + '/', { method:'DELETE' });
    xabar("Obyekt o'chirildi");
    obyektlarYukla();
  } catch (err) { xabar(err.message, true); }
}

function uskunaModalOch(obyektId) {
  modalOch('Uskuna qo\'shish', `
    <form data-h-submit="c:uskunaSaqla" data-a-submit="${SG_A(['@event', obyektId])}">
      <label class="f-label" for="uTuri">Uskuna turi</label>
      <select class="f-select" id="uTuri">
        ${[['rezervuar','Rezervuar'],['hisoblagich','Hisoblagich'],['qozon','Qozon'],
           ['gorelka','Gorelka'],['ventil','Ventil / reduktor'],['boshqa','Boshqa']]
          .map(([k,n]) => `<option value="${k}">${n}</option>`).join('')}
      </select>
      <label class="f-label" for="uNom">Nomi *</label>
      <input class="f-input" id="uNom" required placeholder="Masalan: Yer osti rezervuari">
      <div class="ikki-ustun">
        <div><label class="f-label" for="uModel">Model</label><input class="f-input" id="uModel"></div>
        <div><label class="f-label" for="uSeriya">Seriya raqami</label><input class="f-input" id="uSeriya"></div>
        <div><label class="f-label" for="uHajm">Hajm / quvvat</label><input class="f-input" id="uHajm" placeholder="Masalan: 4850 l"></div>
        <div><label class="f-label" for="uSana">O'rnatilgan sana</label><input class="f-input" id="uSana" type="date"></div>
      </div>
      <button class="btn asosiy" type="submit" style="width:100%;justify-content:center"><i class="ti ti-plus"></i> Qo'shish</button>
    </form>`);
}

async function uskunaSaqla(e, obyektId) {
  e.preventDefault();
  try {
    await so('/kabinet/uskunalar/', { method:'POST', body:{
      obyekt: obyektId,
      turi: el('uTuri').value,
      nom: el('uNom').value.trim(),
      model: el('uModel').value.trim(),
      seriya_raqam: el('uSeriya').value.trim(),
      hajm: el('uHajm').value.trim(),
      ornatilgan_sana: el('uSana').value || null,
    }});
    modalYop();
    xabar("Uskuna qo'shildi");
    obyektlarYukla();
  } catch (err) { xabar(err.message, true); }
}

/* ---------- 4. HISOBLAGICHLAR ---------- */
async function hisoblagichlarYukla() {
  const d = await so('/kabinet/hisoblagichlar/');
  const royxat = d.royxat;
  el('hisoblagichRoyxat').innerHTML = royxat.length ? '<div class="grid-kartalar">' + royxat.map(h => {
    const sinf = h.muddat_holati === 'otgan' ? 'bad' : (h.muddat_holati === 'yaqin' ? 'warn' : '');
    const izoh = h.kun_qoldi == null ? 'Tekshiruv sanasi kiritilmagan'
      : (h.kun_qoldi < 0 ? `Muddati ${Math.abs(h.kun_qoldi)} kun oldin tugagan!`
                         : `${h.kun_qoldi} kundan keyin muddati tugaydi`);
    return `
    <div class="mini-karta ${sinf}">
      <h5>${xavfsiz(h.seriya_raqam)}</h5>
      <p class="manzil">${xavfsiz(h.obyekt_nomi)} · ${xavfsiz(h.turi_nomi)}${h.markasi ? ' · ' + xavfsiz(h.markasi) : ''}</p>
      <div class="kv"><span>Keyingi tekshiruv</span><span>${sana(h.keyingi_tekshiruv)}</span></div>
      <div class="kv"><span>Oxirgi tekshiruv</span><span>${sana(h.oxirgi_tekshiruv)}</span></div>
      ${h.oxirgi_korsatkich != null ? `<div class="kv"><span>Ko'rsatkich</span><span>${h.oxirgi_korsatkich} m³</span></div>` : ''}
      <div class="kv"><span>Holat</span><span>${h.holat === 'faol' ? 'Faol' : xavfsiz(h.holat)}</span></div>
      <p style="font-size:12px;font-weight:700;margin:12px 0 10px;color:${sinf==='bad'?'var(--red)':(sinf==='warn'?'var(--orange)':'var(--text-secondary)')}">
        <i class="ti ti-clock"></i> ${izoh}</p>
      <div style="display:flex;gap:8px;flex-wrap:wrap">
        <button class="btn asosiy kichik" data-h-click="c:tekshiruvgaYozil" data-a-click="${SG_A([h.id])}"><i class="ti ti-calendar-plus"></i> Tekshiruvga yozilish</button>
        <button class="btn sokin kichik" data-h-click="c:hisoblagichModalOch" data-a-click="${SG_A([h.id])}"><i class="ti ti-edit"></i></button>
        <button class="btn sokin kichik" data-h-click="c:hisoblagichOchir" data-a-click="${SG_A([h.id])}"><i class="ti ti-trash"></i></button>
      </div>
    </div>`;
  }).join('') + '</div>'
   : '<p class="bosh-holat">Hisoblagich qo\'shilmagan. Qo\'shsangiz, tekshiruv muddati avtomatik kuzatiladi.</p>';
  window._hisoblagichlar = royxat;
}

function hisoblagichModalOch(id) {
  const h = (window._hisoblagichlar || []).find(x => x.id === id) || {};
  obyektlarKeshYukla().then(() => {
    if (!obyektlarKesh.length) {
      xabar("Avval obyekt qo'shing", true);
      pageOch('obyektlar');
      return;
    }
    modalOch(id ? 'Hisoblagichni tahrirlash' : 'Yangi hisoblagich', `
      <form data-h-submit="c:hisoblagichSaqla" data-a-submit="${SG_A(['@event', id || 0])}">
        <label class="f-label" for="hObyekt">Obyekt *</label>
        <select class="f-select" id="hObyekt" required ${id ? 'disabled' : ''}>
          ${obyektlarKesh.map(o => `<option value="${o.id}" ${h.obyekt===o.id?'selected':''}>${xavfsiz(o.nom)}</option>`).join('')}
        </select>
        <div class="ikki-ustun">
          <div>
            <label class="f-label" for="hTuri">Turi</label>
            <select class="f-select" id="hTuri">
              ${[['mexanik','Mexanik'],['elektron','Elektron'],['smart','Smart (masofadan)']]
                .map(([k,n]) => `<option value="${k}" ${h.turi===k?'selected':''}>${n}</option>`).join('')}
            </select>
          </div>
          <div><label class="f-label" for="hMarka">Markasi</label><input class="f-input" id="hMarka" value="${xavfsiz(h.markasi || '')}"></div>
        </div>
        <label class="f-label" for="hSeriya">Seriya raqami *</label>
        <input class="f-input" id="hSeriya" required value="${xavfsiz(h.seriya_raqam || '')}">
        <div class="ikki-ustun">
          <div><label class="f-label" for="hOrnatilgan">O'rnatilgan sana</label><input class="f-input" type="date" id="hOrnatilgan" value="${h.ornatilgan_sana || ''}"></div>
          <div><label class="f-label" for="hOxirgi">Oxirgi tekshiruv</label><input class="f-input" type="date" id="hOxirgi" value="${h.oxirgi_tekshiruv || ''}"></div>
          <div><label class="f-label" for="hKeyingi">Keyingi tekshiruv</label><input class="f-input" type="date" id="hKeyingi" value="${h.keyingi_tekshiruv || ''}"></div>
          <div><label class="f-label" for="hKorsatkich">Oxirgi ko'rsatkich (m³)</label><input class="f-input" type="number" id="hKorsatkich" value="${h.oxirgi_korsatkich != null ? h.oxirgi_korsatkich : ''}"></div>
        </div>
        <button class="btn asosiy" type="submit" style="width:100%;justify-content:center"><i class="ti ti-device-floppy"></i> Saqlash</button>
      </form>`);
  }).catch(e => xabar(e.message, true));
}

async function hisoblagichSaqla(e, id) {
  e.preventDefault();
  const tana = {
    turi: el('hTuri').value,
    markasi: el('hMarka').value.trim(),
    seriya_raqam: el('hSeriya').value.trim(),
    ornatilgan_sana: el('hOrnatilgan').value || null,
    oxirgi_tekshiruv: el('hOxirgi').value || null,
    keyingi_tekshiruv: el('hKeyingi').value || null,
    oxirgi_korsatkich: el('hKorsatkich').value ? Number(el('hKorsatkich').value) : null,
  };
  try {
    if (id) {
      await so('/kabinet/hisoblagichlar/' + id + '/', { method:'PATCH', body: tana });
    } else {
      tana.obyekt = Number(el('hObyekt').value);
      await so('/kabinet/hisoblagichlar/', { method:'POST', body: tana });
    }
    modalYop();
    xabar('Hisoblagich saqlandi');
    hisoblagichlarYukla();
  } catch (err) { xabar(err.message, true); }
}

async function hisoblagichOchir(id) {
  if (!confirm("Hisoblagich o'chirilsinmi?")) return;
  try {
    await so('/kabinet/hisoblagichlar/' + id + '/', { method:'DELETE' });
    xabar("O'chirildi");
    hisoblagichlarYukla();
  } catch (err) { xabar(err.message, true); }
}

async function tekshiruvgaYozil(id) {
  if (!confirm('Metrologik tekshiruv uchun ariza yuborilsinmi?')) return;
  try {
    const b = await so('/kabinet/hisoblagichlar/' + id + '/tekshiruv/', { method:'POST', body:{} });
    xabar('Ariza #' + b.id + ' qabul qilindi');
    pageOch('buyurtmalar');
  } catch (err) { xabar(err.message, true); }
}

/* ---------- 5. TO'LOVLAR ---------- */
async function tolovlarYukla() {
  const d = await so('/kabinet/tolovlar/');
  el('tolovStat').innerHTML = `
    <div class="stat-box ${d.kutilayotgan_soni ? 'warn' : 'ok'}">
      <p class="n">${d.kutilayotgan_soni}</p><p class="l">Kutilayotgan to'lov</p></div>
    <div class="stat-box ${d.kutilayotgan_soni ? 'warn' : 'ok'}">
      <p class="n" style="font-size:19px">${pul(d.kutilayotgan_summa)}</p><p class="l">To'lanishi kerak</p></div>
    <div class="stat-box ok"><p class="n" style="font-size:19px">${pul(d.tolangan_summa)}</p><p class="l">Jami to'langan</p></div>`;

  el('tolovRoyxat').innerHTML = d.royxat.length ? `
    <div class="table-wrap"><table class="data-table">
      <thead><tr><th>Xizmat / buyurtma</th><th>Summa</th><th>Usul</th><th>Sana</th><th>Holat</th></tr></thead>
      <tbody>${d.royxat.map(t => `
        <tr>
          <td>${xavfsiz(t.nom)}</td>
          <td>${pul(t.summa)}</td>
          <td>${xavfsiz(t.usul || '—')}</td>
          <td>${sana(t.sana)}</td>
          <td>${t.tolandi ? '<span class="tag done">To\'landi</span>' : '<span class="tag wait">Kutilmoqda</span>'}</td>
        </tr>`).join('')}</tbody>
    </table></div>` : '<p class="bosh-holat">To\'lov tarixi bo\'sh.</p>';

  el('fakturaRoyxat').innerHTML = d.fakturalar.length
    ? d.fakturalar.map(f => hujjatQatori(f)).join('')
    : '<p class="bosh-holat">Hisob-faktura hali yaratilmagan. Yaratilgach shu yerda yuklab olish mumkin bo\'ladi.</p>';
}

function tolovUsul(usul) {
  const matn = {
    click: "Click orqali to'lash uchun kutilayotgan to'lov ro'yxatidan buyurtmani tanlang — Click checkout sahifasi ochiladi.",
    payme: "Payme orqali to'lash uchun kutilayotgan to'lov ro'yxatidan buyurtmani tanlang — Payme checkout sahifasi ochiladi.",
    bank: "Bank o'tkazmasi uchun operator siz bilan bog'lanadi va hisob-faktura yuboradi.",
  };
  xabar(matn[usul]);
}

/* ---------- 6. HUJJATLAR ---------- */
function hujjatFiltrla(f) {
  joriyHujjatFiltr = f;
  document.querySelectorAll('#hujjatFiltr .filtr-tab').forEach(b =>
    b.classList.toggle('active', b.dataset.f === f));
  hujjatlarYukla().catch(e => xabar(e.message, true));
}

function hujjatQatori(h) {
  return `
    <div class="row-item">
      <div class="row-ikon"><i class="ti ti-file-type-pdf"></i></div>
      <div class="r-info">
        <h5>${xavfsiz(h.nom)}</h5>
        <p>${xavfsiz(h.turi_nomi)} · ${sana(h.sana)}${h.obyekt_nomi ? ' · ' + xavfsiz(h.obyekt_nomi) : ''}${h.olcham ? ' · ' + h.olcham + ' KB' : ''}</p>
      </div>
      <a class="btn sokin kichik" href="${h.fayl_url}" target="_blank" rel="noopener" download><i class="ti ti-download"></i> Yuklab olish</a>
    </div>`;
}

async function hujjatlarYukla() {
  const royxat = await so('/kabinet/hujjatlar/' + (joriyHujjatFiltr ? '?turi=' + joriyHujjatFiltr : ''));
  el('hujjatRoyxat').innerHTML = royxat.length
    ? royxat.map(hujjatQatori).join('')
    : '<p class="bosh-holat">Hujjat topilmadi. Shartnoma va sertifikatlar rasmiylashtirilgach shu yerda paydo bo\'ladi.</p>';
}

/* ---------- 7. BILDIRISHNOMALAR ---------- */
async function bildirishnomalarYukla() {
  const d = await so('/kabinet/bildirishnomalar/');
  oqilmaganChiqar(d.oqilmagan);

  const ikonlar = { buyurtma:'ti-clipboard-list', tolov:'ti-credit-card', texnik:'ti-gauge', umumiy:'ti-info-circle' };
  el('bildirishnomaRoyxat').innerHTML = d.royxat.length ? d.royxat.map(b => `
    <div class="row-item" style="${b.oqildi ? 'opacity:.65' : ''}">
      <div class="row-ikon"><i class="ti ${ikonlar[b.turi] || 'ti-bell'}"></i></div>
      <div class="r-info">
        <h5>${xavfsiz(b.sarlavha)} ${b.oqildi ? '' : '<span class="tag wait">Yangi</span>'}</h5>
        <p>${xavfsiz(b.matn)}</p>
        <p style="color:var(--text-muted);margin-top:3px">${sana(b.yaratilgan, true)}</p>
      </div>
      ${b.bolim ? `<button class="btn sokin kichik" data-h-click="c:pageOch" data-a-click="${SG_A([String(b.bolim)])}">Ochish</button>` : ''}
    </div>`).join('') : '<p class="bosh-holat">Bildirishnoma yo\'q.</p>';

  el('smsRoyxat').innerHTML = d.sms.length ? d.sms.map(s => `
    <div class="row-item">
      <div class="row-ikon"><i class="ti ti-message-2"></i></div>
      <div class="r-info"><h5>${xavfsiz(s.matn)}</h5><p>${sana(s.yaratilgan, true)}</p></div>
    </div>`).join('') : '<p class="bosh-holat">SMS xabarlar yo\'q.</p>';
}

async function hammasiOqildi() {
  try {
    await so('/kabinet/bildirishnomalar/oqildi/', { method:'POST', body:{} });
    bildirishnomalarYukla();
  } catch (err) { xabar(err.message, true); }
}

/* ---------- 8. SHARHLAR ---------- */
async function sharhlarYukla() {
  const d = await so('/kabinet/sharhlar/');
  el('baholanmaganRoyxat').innerHTML = d.baholanmagan.length ? d.baholanmagan.map(b => `
    <div class="row-item">
      <div class="row-ikon"><i class="ti ti-tool"></i></div>
      <div class="r-info"><h5>#${b.id} — ${xavfsiz(b.xizmat_nomi)}</h5><p>${sana(b.sana)}</p></div>
      <button class="btn asosiy kichik" data-h-click="c:sharhModalOch" data-a-click="${SG_A([b.id, String(b.xizmat_nomi)])}"><i class="ti ti-star"></i> Baho berish</button>
    </div>`).join('') : '<p class="bosh-holat">Baho kutayotgan xizmat yo\'q.</p>';

  el('sharhRoyxat').innerHTML = d.royxat.length ? d.royxat.map(s => `
    <div class="row-item">
      <div class="row-ikon"><i class="ti ti-star-filled"></i></div>
      <div class="r-info">
        <h5>${xavfsiz(s.buyurtma_nomi || 'Xizmat')} <span class="yulduz-kichik">${'★'.repeat(s.baho)}${'☆'.repeat(5 - s.baho)}</span></h5>
        <p>${xavfsiz(s.matn || '—')}</p>
        <p style="color:var(--text-muted);margin-top:3px">${sana(s.yaratilgan)}</p>
      </div>
      <div style="display:flex;gap:6px">
        <button class="btn sokin kichik" data-h-click="c:sharhTahrir" data-a-click="${SG_A([s.id])}"><i class="ti ti-edit"></i></button>
        <button class="btn sokin kichik" data-h-click="c:sharhOchir" data-a-click="${SG_A([s.id])}"><i class="ti ti-trash"></i></button>
      </div>
    </div>`).join('') : '<p class="bosh-holat">Hali sharh qoldirmagansiz.</p>';
  window._sharhlar = d.royxat;
}

let tanlanganBaho = 5;

function yulduzHtml(baho) {
  return `<div class="yulduzlar" id="yulduzlar">${[1,2,3,4,5].map(i =>
    `<i class="ti ti-star-filled ${i <= baho ? 'on' : ''}" data-h-click="c:bahoTanla" data-a-click="${SG_A([i])}"></i>`).join('')}</div>`;
}

function bahoTanla(n) {
  tanlanganBaho = n;
  document.querySelectorAll('#yulduzlar i').forEach((y, i) => y.classList.toggle('on', i < n));
}

function sharhModalOch(buyurtmaId, nom) {
  tanlanganBaho = 5;
  modalOch('Xizmatni baholang', `
    <p class="f-hint" style="margin:0 0 14px">${xavfsiz(nom)}</p>
    <form data-h-submit="c:sharhYubor" data-a-submit="${SG_A(['@event', buyurtmaId])}">
      ${yulduzHtml(5)}
      <label class="f-label" style="margin-top:16px" for="shMatn">Sharhingiz</label>
      <textarea class="f-area" id="shMatn" placeholder="Xizmat sifati haqida yozing..."></textarea>
      <button class="btn asosiy" type="submit" style="width:100%;justify-content:center"><i class="ti ti-send"></i> Yuborish</button>
    </form>`);
}

async function sharhYubor(e, buyurtmaId) {
  e.preventDefault();
  try {
    await so('/kabinet/sharhlar/', { method:'POST', body:{
      buyurtma: buyurtmaId, baho: tanlanganBaho, matn: el('shMatn').value.trim(),
    }});
    modalYop();
    xabar('Sharhingiz uchun rahmat!');
    pageOch('sharhlar');
  } catch (err) { xabar(err.message, true); }
}

function sharhTahrir(id) {
  const s = (window._sharhlar || []).find(x => x.id === id);
  if (!s) return;
  tanlanganBaho = s.baho;
  modalOch('Sharhni tahrirlash', `
    <form data-h-submit="c:sharhYangila" data-a-submit="${SG_A(['@event', id])}">
      ${yulduzHtml(s.baho)}
      <label class="f-label" style="margin-top:16px" for="shMatn">Sharhingiz</label>
      <textarea class="f-area" id="shMatn">${xavfsiz(s.matn || '')}</textarea>
      <button class="btn asosiy" type="submit" style="width:100%;justify-content:center"><i class="ti ti-device-floppy"></i> Saqlash</button>
    </form>`);
}

async function sharhYangila(e, id) {
  e.preventDefault();
  try {
    await so('/kabinet/sharhlar/' + id + '/', { method:'PATCH', body:{
      baho: tanlanganBaho, matn: el('shMatn').value.trim(),
    }});
    modalYop();
    xabar('Sharh yangilandi');
    sharhlarYukla();
  } catch (err) { xabar(err.message, true); }
}

async function sharhOchir(id) {
  if (!confirm("Sharh o'chirilsinmi?")) return;
  try {
    await so('/kabinet/sharhlar/' + id + '/', { method:'DELETE' });
    xabar("O'chirildi");
    sharhlarYukla();
  } catch (err) { xabar(err.message, true); }
}

/* ---------- 9. YORDAM MARKAZI ---------- */
async function yordamYukla() {
  const [murojaatlar, faqlar] = await Promise.all([
    so('/kabinet/yordam/murojaatlar/'),
    so('/kabinet/yordam/faq/'),
  ]);

  el('murojaatRoyxat').innerHTML = murojaatlar.length ? murojaatlar.map(m => `
    <div class="mini-karta" style="margin-bottom:14px">
      <div style="display:flex;justify-content:space-between;gap:10px;align-items:flex-start">
        <div><h5>${xavfsiz(m.mavzu)}</h5><p class="manzil">#${m.id} · ${sana(m.yangilangan, true)}</p></div>
        <span class="tag ${m.holat === 'yopiq' ? 'plan' : (m.holat === 'javob' ? 'done' : 'wait')}">${xavfsiz(m.holat_nomi)}</span>
      </div>
      <div class="chat-oyna">
        ${m.xabarlar.map(x => `
          <div class="chat-xabar ${x.kim}">${xavfsiz(x.matn)}
            <span class="chat-vaqt">${x.kim === 'mijoz' ? 'Siz' : 'Operator'} · ${sana(x.yaratilgan, true)}</span>
          </div>`).join('')}
      </div>
      ${m.holat === 'yopiq' ? '<p class="f-hint" style="margin:12px 0 0">Murojaat yopilgan.</p>' : `
        <form class="chat-yozish" data-h-submit="c:xabarYubor" data-a-submit="${SG_A(['@event', m.id])}">
          <input class="f-input" id="chat-${m.id}" placeholder="Xabar yozing..." required>
          <button class="btn asosiy" type="submit"><i class="ti ti-send"></i></button>
        </form>
        <button class="btn sokin kichik" style="margin-top:10px" data-h-click="c:murojaatYop" data-a-click="${SG_A([m.id])}">Murojaatni yopish</button>`}
    </div>`).join('') : '<p class="bosh-holat">Murojaat yo\'q. Savolingiz bo\'lsa yangi murojaat oching.</p>';

  el('faqRoyxat').innerHTML = faqlar.length ? faqlar.map((f, i) => `
    <div class="faq-item" id="faq-${i}">
      <button class="faq-savol" data-h-click="c:faqOch" data-a-click="${SG_A([i])}">${xavfsiz(f.savol)} <i class="ti ti-chevron-down"></i></button>
      <div class="faq-javob">${xavfsiz(f.javob)}</div>
    </div>`).join('') : '<p class="bosh-holat">Savol-javoblar hali qo\'shilmagan.</p>';
}

function faqOch(i) { el('faq-' + i).classList.toggle('ochiq'); }

function murojaatModalOch() {
  modalOch('Yangi murojaat', `
    <form data-h-submit="h45">
      <label class="f-label" for="mMavzu">Mavzu *</label>
      <input class="f-input" id="mMavzu" required placeholder="Masalan: Hisoblagich ko'rsatkichi noto'g'ri">
      <label class="f-label" for="mMatn">Xabar *</label>
      <textarea class="f-area" id="mMatn" required placeholder="Muammoni batafsil yozing..."></textarea>
      <button class="btn asosiy" type="submit" style="width:100%;justify-content:center"><i class="ti ti-send"></i> Yuborish</button>
    </form>`);
}

async function murojaatYarat(e) {
  e.preventDefault();
  try {
    await so('/kabinet/yordam/murojaatlar/', { method:'POST', body:{
      mavzu: el('mMavzu').value.trim(), matn: el('mMatn').value.trim(),
    }});
    modalYop();
    xabar('Murojaat yuborildi. Operator tez orada javob beradi.');
    yordamYukla();
  } catch (err) { xabar(err.message, true); }
}

async function xabarYubor(e, id) {
  e.preventDefault();
  const input = el('chat-' + id);
  const matn = input.value.trim();
  if (!matn) return;
  try {
    await so('/kabinet/yordam/murojaatlar/' + id + '/xabar/', { method:'POST', body:{ matn } });
    input.value = '';
    yordamYukla();
  } catch (err) { xabar(err.message, true); }
}

async function murojaatYop(id) {
  if (!confirm('Murojaat yopilsinmi?')) return;
  try {
    await so('/kabinet/yordam/murojaatlar/' + id + '/yopish/', { method:'POST', body:{} });
    yordamYukla();
  } catch (err) { xabar(err.message, true); }
}

async function qongiroqSora(e) {
  e.preventDefault();
  try {
    await so('/kabinet/yordam/qongiroq/', { method:'POST', body:{
      telefon: el('qTelefon').value.trim(),
      qulay_vaqt: el('qVaqt').value,
      mavzu: el('qMavzu').value.trim(),
    }});
    el('qMavzu').value = '';
    xabar("So'rov qabul qilindi — operator qo'ng'iroq qiladi");
  } catch (err) { xabar(err.message, true); }
}

/* ---------- 10. SOZLAMALAR ---------- */
async function sozlamalarYukla() {
  tumanlarniQoy(el('sTuman'));
  const [p, s] = await Promise.all([so('/auth/profil/'), so('/kabinet/sozlamalar/')]);
  profil = Object.assign({}, profil, p);
  saqlash.setItem('sg_user', JSON.stringify(profil));

  el('sIsm').value = p.ism || '';
  el('sTelefon').value = p.telefon || '';
  el('sQoshimcha').value = p.qoshimcha_telefon || '';
  el('sEmail').value = p.email || '';
  el('sTuman').value = p.tuman || '';
  el('sMahalla').value = p.mahalla || '';
  el('sTuman').viloyatniMoslash && el('sTuman').viloyatniMoslash();
  el('sManzil').value = p.manzil || '';
  el('sMoljal').value = p.moljal || '';

  el('tgSms').checked = s.sms_bildirishnoma;
  el('tgEmail').checked = s.email_bildirishnoma;
  el('tgPush').checked = s.push_bildirishnoma;
  el('tgTekshiruv').checked = s.tekshiruv_eslatma;
}

async function sozlamaProfilSaqla(e) {
  e.preventDefault();
  try {
    // Email / qo'shimcha telefon o'zgarsa server SMS kod so'raydi (smsTasdiqBilan)
    profil = await smsTasdiqBilan('/auth/profil/', { method:'PATCH', body: JSON.stringify({
      ism: el('sIsm').value.trim(),
      qoshimcha_telefon: el('sQoshimcha').value.trim(),
      email: el('sEmail').value.trim(),
      viloyat: el('sViloyat').value,
      tuman: el('sTuman').value,
      mahalla: el('sMahalla').value.trim(),
      manzil: el('sManzil').value.trim(),
      moljal: el('sMoljal').value.trim(),
    })});
    saqlash.setItem('sg_user', JSON.stringify(profil));
    profilChiqar();
    xabar('Ma\'lumotlar saqlandi');
  } catch (err) { xabar(err.message, true); }
}

async function sozlamaSaqla() {
  try {
    await so('/kabinet/sozlamalar/', { method:'PATCH', body:{
      sms_bildirishnoma: el('tgSms').checked,
      email_bildirishnoma: el('tgEmail').checked,
      push_bildirishnoma: el('tgPush').checked,
      tekshiruv_eslatma: el('tgTekshiruv').checked,
    }});
    xabar('Sozlama saqlandi');
  } catch (err) { xabar(err.message, true); }
}

function hisobOchirModal() {
  modalOch('Hisobni o\'chirish', `
    <p style="font-size:13px;color:var(--text-secondary);line-height:1.6;margin:0 0 16px">
      Bu amalni ortga qaytarib bo'lmaydi. Tasdiqlash uchun quyidagi maydonga
      <b>O'CHIRISH</b> so'zini kiriting.</p>
    <form data-h-submit="h46">
      <input class="f-input" id="ochirTasdiq" placeholder="O'CHIRISH" required>
      <button class="btn xavf" type="submit" style="width:100%;justify-content:center"><i class="ti ti-trash"></i> Hisobni butunlay o'chirish</button>
    </form>`);
}

async function hisobOchir(e) {
  e.preventDefault();
  try {
    await smsTasdiqBilan('/kabinet/hisob/ochirish/', { method:'POST', body: JSON.stringify({ tasdiq: el('ochirTasdiq').value }) });
    modalYop();
    tokenOchir();
    alert("Hisobingiz o'chirildi. Xizmatimizdan foydalanganingiz uchun rahmat.");
    location.href = ASOSIY_SAYT;
  } catch (err) { xabar(err.message, true); }
}

/* ---------- modal ---------- */
function modalOch(sarlavha, html) {
  el('modalTana').innerHTML = `
    <div class="modal-head"><h3>${sarlavha}</h3>
      <button class="modal-yop" data-h-click="h47"><i class="ti ti-x"></i></button></div>${html}`;
  el('modalFon').classList.add('ochiq');
  document.body.style.overflow = 'hidden';
}

function modalYop() {
  el('modalFon').classList.remove('ochiq');
  document.body.style.overflow = '';
}

document.addEventListener('keydown', e => { if (e.key === 'Escape') modalYop(); });

/* ---------- boshlash ---------- */
(async function boshlash() {
  el('qaytishHavola').href = ASOSIY_SAYT;
  el('saytHavola').href = ASOSIY_SAYT;
  tumanlarniQoy(el('pTuman'));
  const token = saqlash.getItem('sg_token');
  if (!token) { kirishKorsat(); return; }
  try {
    profil = await so('/auth/profil/');
    if (profil.rol === 'xodim') { location.href = XODIM_SAHIFA; return; }
    saqlash.setItem('sg_user', JSON.stringify(profil));
    if (KORISH) korishBannerKorsat(profil.ism || profil.telefon);
    // Ko'rish rejimida to'ldirilmagan profil formasi ochilmaydi (u yozish talab qiladi)
    if (!KORISH && (!profil.ism || !profil.manzil || !profil.tuman)) {
      kirishTelefon = profil.telefon;
      el('authView').style.display = 'flex';
      tumanlarniQoy(el('pTuman'));
      el('pIsm').value = profil.ism || '';
      el('pTuman').value = profil.tuman || '';
      el('pMahalla').value = profil.mahalla || '';
      el('pTuman').viloyatniMoslash && el('pTuman').viloyatniMoslash();
      el('pManzil').value = profil.manzil || '';
      qadamgaOt(3);
      return;
    }
    kabinetOch();
  } catch (e) {
    kirishKorsat();
  }
})();
