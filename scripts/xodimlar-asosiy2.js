// ═══════ Backend ═══════
// Barcha ma'lumot Django API dan keladi. Xodim hisobi va jamoa ro'yxati
// faqat Django admin panelida (/admin/auth_app/xodim/) boshqariladi.
// Sayt server orqali ochilsa nisbiy manzil, fayl sifatida ochilsa dev backend
const API = location.protocol === 'file:' ? 'http://localhost:8001/api' : '/api';
const TOKEN_KALIT = 'soargaz_xodim_token';
const TELEFON_KALIT = 'soargaz_xodim_telefon';
const ESLAB_KALIT = 'soargaz_xodim_eslab';

let token = null;
let profil = null;

// ── «Uning ko'zi bilan ko'rish» (egasi, faqat o'qish) ──
// Egasi boshqaruv panelidan shu sahifani ochadi; token URL fragmentidan olinadi va FAQAT
// shu tabning sessionStorage'ida turadi — xodimning o'z sessiyasiga (localStorage) tegilmaydi.
// Server bu token bilan o'zgartiruvchi so'rovlarni baribir rad etadi; bu yerda ham ularni
// yubormaymiz, geolokatsiya ham yoqilmaydi (egasining telefoni xodim deb ko'rinmasin).
const KORISH_KALIT = 'soargaz_korish_token';
let KORISH = false;
try {
  const m = location.hash.match(/korish=([^&]+)/);
  if (m) {
    sessionStorage.setItem(KORISH_KALIT, decodeURIComponent(m[1]));
    history.replaceState(null, '', location.pathname + location.search);   // token manzilda qolmasin
  }
  KORISH = !!sessionStorage.getItem(KORISH_KALIT);
} catch (e) {}

function korishBannerKorsat(ism){
  document.getElementById('korishIsm').textContent = ism;
  document.getElementById('korishBanner').style.display = 'block';
  document.body.classList.add('korish');
}
function korishChiq(){
  try { sessionStorage.removeItem(KORISH_KALIT); } catch (e) {}
  window.close();                                           // boshqaruv paneli ochgan tab yopiladi
  setTimeout(() => { location.href = '/boshqaruv/'; }, 250);  // yopilmasa — panelga qaytadi
}
document.getElementById('korishChiqish').addEventListener('click', korishChiq);

// "Ma'lumotlarimni saqlab qol" belgilansa — localStorage (brauzer yopilsa ham qoladi),
// belgilanmasa — sessionStorage (faqat shu oyna ochiq turganda saqlanadi).
function tokenYukla(){
  if (KORISH) { try { token = sessionStorage.getItem(KORISH_KALIT); } catch (e) {} return; }
  try { token = localStorage.getItem(TOKEN_KALIT) || sessionStorage.getItem(TOKEN_KALIT); } catch (e) {}
}
function tokenSaqla(t, eslab){
  if (KORISH) return;                // ko'rish rejimida hech narsa saqlanmaydi
  token = t;
  try {
    if (eslab) { localStorage.setItem(TOKEN_KALIT, t); sessionStorage.removeItem(TOKEN_KALIT); }
    else       { sessionStorage.setItem(TOKEN_KALIT, t); localStorage.removeItem(TOKEN_KALIT); }
  } catch (e) {}
}
function tokenOchir(){
  token = null;
  if (KORISH) return;                // egasi chiqish tugmasi bilan chiqadi
  // Serverda refresh tokenni bekor qilamiz va cookie'ni o'chiramiz
  try {
    fetch(API + '/auth/chiqish/', {
      method: 'POST', keepalive: true, headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ sessiya: 'xodim' })
    }).catch(() => {});
  } catch (e) {}
  try { localStorage.removeItem(TOKEN_KALIT); sessionStorage.removeItem(TOKEN_KALIT); } catch (e) {}
}

// Access token qisqa (30 daqiqa): 401 bo'lsa jimgina yangilanadi. Refresh token xodim
// sessiyasining ALOHIDA httpOnly cookie'sida turadi (brauzer o'zi yuboradi). Bir vaqtda
// ketgan bir nechta 401 uchun bitta so'rov: server eski refreshni bekor qiladi.
let _tokenYangilash = null;
function tokenYangila(){
  if (_tokenYangilash) return _tokenYangilash;
  const eslab = (function(){ try { return !!localStorage.getItem(TOKEN_KALIT); } catch (e) { return true; } })();
  _tokenYangilash = (async () => {
    try {
      const j = await fetch(API + '/auth/token/yangilash/', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ sessiya: 'xodim', eslab })
      });
      if (!j.ok) return false;
      const d = await j.json();
      tokenSaqla(d.access, eslab);
      return true;
    } catch (e) { return false; }
    finally { _tokenYangilash = null; }
  })();
  return _tokenYangilash;
}

// Telefon raqam va belgi holati keyingi kirish uchun eslab qolinadi
function eslabQolYukla(){
  try {
    const belgi = localStorage.getItem(ESLAB_KALIT);
    const eslab = belgi === null ? true : belgi === '1';
    document.getElementById('eslabQol').checked = eslab;
    if (eslab) document.getElementById('loginTelefon').value = localStorage.getItem(TELEFON_KALIT) || '';
  } catch (e) {}
}
function eslabQolSaqla(eslab, telefon){
  try {
    localStorage.setItem(ESLAB_KALIT, eslab ? '1' : '0');
    if (eslab) localStorage.setItem(TELEFON_KALIT, telefon);
    else       localStorage.removeItem(TELEFON_KALIT);
  } catch (e) {}
}

async function apiSorov(yol, sozlama = {}){
  // Ko'rish rejimi: faqat o'qish — o'zgartiruvchi so'rov serverga yuborilmaydi
  if (KORISH && String(sozlama.method || 'GET').toUpperCase() !== 'GET') {
    throw new Error("Ko'rish rejimida o'zgartirish mumkin emas");
  }
  const yubor = () => fetch(API + yol, {
    ...sozlama,
    headers: {
      ...(sozlama.body instanceof FormData ? {} : { 'Content-Type': 'application/json' }),
      ...(token ? { 'Authorization': 'Bearer ' + token } : {}),
      ...(sozlama.headers || {})
    }
  });
  let javob = await yubor();
  // Access muddati tugagan bo'lsa — jimgina yangilab, so'rovni bir marta qaytaramiz
  if (javob.status === 401 && !KORISH && token && await tokenYangila()) javob = await yubor();
  if (javob.status === 401 && KORISH) {
    alert("Ko'rish rejimi muddati tugadi. Boshqaruv panelidan qaytadan oching.");
    korishChiq();
    throw new Error("Ko'rish rejimi tugadi");
  }
  if (javob.status === 401) { chiqish(); throw new Error('Sessiya tugadi'); }
  const matn = await javob.text();
  const malumot = matn ? JSON.parse(matn) : null;
  if (!javob.ok) throw new Error((malumot && malumot.detail) || 'Server xatosi');
  return malumot;
}

// "Aziz Karimov" -> "AK"; bitta so'z bo'lsa birinchi ikki harf
function boshHarflar(ism){
  const b = (ism || '').trim().split(/\s+/).filter(Boolean);
  if (!b.length) return '?';
  if (b.length === 1) return b[0].slice(0, 2).toUpperCase();
  return (b[0][0] + b[b.length - 1][0]).toUpperCase();
}

function sanaFormat(iso){
  if (!iso) return '—';
  const [y, o, k] = iso.split('-');
  return `${k}.${o}.${y}`;
}

// ═══════ Profil ═══════
function profilChiz(){
  if (!profil) return;
  const ism = profil.ism || profil.telefon;
  document.querySelectorAll('[data-toliq-ism]').forEach(el => el.textContent = ism);
  document.querySelectorAll('[data-lavozim]').forEach(el => el.textContent = profil.lavozim || 'Xodim');
  document.querySelectorAll('[data-filial]').forEach(el => el.textContent = profil.tuman || '—');
  document.querySelectorAll('[data-ishga-kirgan]').forEach(el => el.textContent = sanaFormat(profil.ishga_kirgan));
  document.querySelectorAll('[data-bosh-harf]').forEach(el => el.textContent = boshHarflar(ism));

  document.getElementById('setIsm').value = ism;
  document.getElementById('setLavozim').value = profil.lavozim || '';
  document.getElementById('setTelefon').value = profil.telefon || '';
  document.getElementById('setEmail').value = profil.email || '';
  document.getElementById('setQoshimchaTelefon').value = profil.qoshimcha_telefon || '';
}

// Sozlamalar -> Saqlash (faqat email va qo'shimcha telefon o'zgaradi)
document.getElementById('saqlashBtn').addEventListener('click', async (e)=>{
  const btn = e.currentTarget;
  btn.disabled = true;
  try {
    profil = await apiSorov('/auth/xodim/profil/', {
      method: 'PATCH',
      body: JSON.stringify({
        email: document.getElementById('setEmail').value.trim(),
        qoshimcha_telefon: document.getElementById('setQoshimchaTelefon').value.trim()
      })
    });
    profilChiz();
    const belgi = document.getElementById('saqlandiBelgi');
    belgi.style.display = 'inline';
    setTimeout(()=> belgi.style.display = 'none', 2500);
  } catch (xato) {
    alert('Saqlanmadi: ' + xato.message);
  } finally {
    btn.disabled = false;
  }
});

// ═══════ Jamoa ro'yxati (Django admin panelidan) ═══════
async function jamoaYukla(){
  const grid = document.getElementById('jamoaGrid');
  const holat = document.getElementById('jamoaHolat');
  const soni = document.getElementById('jamoaSoni');
  try {
    const javob = await apiSorov('/auth/xodimlar/');
    const royxat = Array.isArray(javob) ? javob : (javob.results || []);
    grid.innerHTML = '';
    if (!royxat.length) {
      holat.textContent = 'Hozircha xodim kiritilmagan. Xodimlar Django admin panelida qo\'shiladi.';
      holat.style.display = 'block';
      soni.textContent = '';
      return;
    }
    holat.style.display = 'none';
    soni.textContent = `(${royxat.length} nafar xodim)`;
    royxat.forEach(x => {
      const ism = x.ism || x.telefon;
      const karta = document.createElement('div');
      karta.className = 'team-card';
      karta.innerHTML =
        `<div class="avatar"></div>` +
        `<div><p class="tname"></p><p class="trole"><span class="dot ${x.holat === 'faol' ? 'on' : 'off'}"></span><span class="lav"></span></p></div>`;
      karta.querySelector('.avatar').textContent = boshHarflar(ism);
      karta.querySelector('.tname').textContent = ism;
      karta.querySelector('.lav').textContent = x.lavozim || 'Xodim';
      grid.appendChild(karta);
    });
  } catch (xato) {
    holat.textContent = 'Ro\'yxatni yuklab bo\'lmadi: ' + xato.message;
    holat.style.display = 'block';
  }
}

// ═══════ Vazifalar (buyurtmalar) ═══════
// GET /api/buyurtmalar/ — backend rol='xodim' bo'lsa faqat shu xodimga
// tayinlangan buyurtmalarni qaytaradi, shuning uchun qo'shimcha filtr shart emas.
const FAOL_HOLATLAR = ['yangi', 'qabul', 'bajarilmoqda'];
const HOLAT_MATN = {
  yangi: 'Kutilmoqda', qabul: 'Qabul qilindi',
  bajarilmoqda: 'Jarayonda', bajarildi: 'Bajarildi', bekor: 'Bekor qilindi'
};
const HOLAT_TAG = {
  yangi: 'wait', qabul: 'progress',
  bajarilmoqda: 'progress', bajarildi: 'done', bekor: 'plan'
};

let vazifalar = [];

function sanaVaqt(iso){
  if (!iso) return '—';
  const d = new Date(iso);
  if (isNaN(d)) return '—';
  const p = n => String(n).padStart(2, '0');
  return `${p(d.getDate())}.${p(d.getMonth() + 1)}.${d.getFullYear()}`;
}
function soatMinut(iso){
  const d = new Date(iso);
  if (isNaN(d)) return '—';
  const p = n => String(n).padStart(2, '0');
  return `${p(d.getHours())}:${p(d.getMinutes())}`;
}
function bugunmi(iso){
  const d = new Date(iso), h = new Date();
  return !isNaN(d) && d.getFullYear() === h.getFullYear()
      && d.getMonth() === h.getMonth() && d.getDate() === h.getDate();
}
function shuOymi(iso){
  const d = new Date(iso), h = new Date();
  return !isNaN(d) && d.getFullYear() === h.getFullYear() && d.getMonth() === h.getMonth();
}

// Bitta vazifa qatori. amallar=true bo'lsa qabul/yakunlash tugmalari qo'shiladi.
let vazifaBelgilangan = null;   // narxnomadan biriktirilgan vazifa: ro'yxatda ajratib ko'rsatiladi

function pulMatni(n){ return Number(n).toLocaleString('ru-RU'); }

// Vazifadagi tanlangan xizmatlar, hisoblangan narx va tasdiqlangan summa
function xizmatBloki(b, amallar){
  const h = b.xizmatlar;
  if (!h || (!h.royxat.length && h.tasdiq_summa == null)) return null;
  const faol = amallar && FAOL_HOLATLAR.includes(b.holat);
  const tasdiqlangan = h.tasdiq_summa != null;
  const blok = document.createElement('div');
  blok.className = 'task-xizmatlar';

  h.royxat.forEach(x => {
    const q = document.createElement('div');
    q.className = 'xq';
    const nom = document.createElement('span');
    nom.className = 'nom';
    const narx = x.narx_gacha != null ? `${pulMatni(x.narx_dan)} – ${pulMatni(x.narx_gacha)}` : pulMatni(x.narx_dan);
    nom.textContent = `${x.nomi}${x.ustun_nomi ? ` (${x.ustun_nomi})` : ''} × ${x.soni} — ${narx} so'm`;
    q.append(nom);
    if (faol && !tasdiqlangan) {
      const olib = document.createElement('button');
      olib.type = 'button';
      olib.title = 'Olib tashlash';
      olib.textContent = '×';
      olib.addEventListener('click', () => xizmatOlibTashla(x.id));
      q.append(olib);
    }
    blok.append(q);
  });

  if (h.royxat.length) {
    const hisob = document.createElement('div');
    hisob.className = 'hisob';
    hisob.textContent = 'Hisob: ' + (h.jami_dan === h.jami_gacha
      ? pulMatni(h.jami_dan) : `${pulMatni(h.jami_dan)} – ${pulMatni(h.jami_gacha)}`) + " so'm";
    blok.append(hisob);
  }

  if (tasdiqlangan) {
    const t = document.createElement('div');
    t.className = 'hisob';
    t.style.color = 'var(--green)';
    t.textContent = `✓ Tasdiqlangan summa: ${pulMatni(h.tasdiq_summa)} so'm`;
    blok.append(t);
  } else if (faol && h.royxat.length) {
    const tugma = document.createElement('button');
    tugma.type = 'button';
    tugma.className = 'mini-btn asosiy';
    tugma.style.marginTop = '8px';
    tugma.textContent = 'Summani tasdiqlash';
    tugma.addEventListener('click', () => summaniTasdiqla(b, tugma));
    blok.append(tugma);
  }
  return blok;
}

async function xizmatOlibTashla(id){
  try {
    await apiSorov(`/buyurtmalar/xizmatlar/${id}/`, { method: 'DELETE' });
    await vazifalarYukla();
  } catch (xato) { alert(xato.message); }
}

async function summaniTasdiqla(b, tugma){
  const h = b.xizmatlar;
  let summa = h.jami_dan;
  if (h.jami_dan !== h.jami_gacha) {
    const javob = prompt(`Tanlangan xizmatlar narxi: ${pulMatni(h.jami_dan)} – ${pulMatni(h.jami_gacha)} so'm.\n` +
      `Mijoz bilan kelishilgan yakuniy summani kiriting.\nTasdiqlangandan keyin o'zgartirib bo'lmaydi.`, String(h.jami_dan));
    if (javob === null) return;
    summa = javob;
  } else if (!confirm(`${pulMatni(h.jami_dan)} so'm tasdiqlansinmi?\nTasdiqlangandan keyin o'zgartirib bo'lmaydi.`)) {
    return;
  }
  tugma.disabled = true;
  try {
    await apiSorov(`/buyurtmalar/${b.id}/summa/`, { method: 'POST', body: JSON.stringify({ summa }) });
    await vazifalarYukla();
  } catch (xato) {
    alert('Tasdiqlanmadi: ' + xato.message);
    tugma.disabled = false;
  }
}

function vazifaQator(b, amallar){
  const qator = document.createElement('div');
  qator.className = 'task-row' + (b.id === vazifaBelgilangan ? ' belgilangan' : '');

  const vaqt = document.createElement('div');
  vaqt.className = 'task-time';
  vaqt.textContent = b.vaqt_istagi || soatMinut(b.yaratilgan);

  const info = document.createElement('div');
  info.className = 'task-info';
  const sarlavha = document.createElement('h5');
  sarlavha.textContent = `#${b.id} ${b.xizmat_nomi || b.xizmat}` + (b.tarmoq_nomi ? ` · ${tarmoqQisqa(b.tarmoq_nomi)}` : '');
  const tavsif = document.createElement('p');
  const joy = [b.manzil, b.tuman].filter(Boolean).join(', ') || 'Manzil ko\'rsatilmagan';
  const mm = b.mijoz_malumot;
  const mijoz = mm && mm.ism ? ` · ${mm.ism}` : '';
  tavsif.textContent = joy + mijoz;
  // Mijoz telefoni bosilsa telefonda to'g'ridan-to'g'ri qo'ng'iroq qilinadi
  const tel = mm && mm.telefon ? String(mm.telefon).replace(/[^\d+]/g, '') : '';
  if (tel) {
    tavsif.append(' · ');
    const aloqa = document.createElement('a');
    aloqa.href = 'tel:' + tel;
    aloqa.textContent = mm.telefon;
    aloqa.style.fontWeight = '700';
    tavsif.append(aloqa);
  }
  info.append(sarlavha, tavsif);
  const xb = xizmatBloki(b, amallar);
  if (xb) info.append(xb);
  const hb = hujjatBloki(b, amallar);          // shartnoma (summa tasdiqlangan buyurtmalarda)
  if (hb) info.append(hb);

  const amal = document.createElement('div');
  amal.className = 'task-amal';
  const belgi = document.createElement('span');
  belgi.className = 'tag ' + (HOLAT_TAG[b.holat] || 'plan');
  belgi.textContent = HOLAT_MATN[b.holat] || b.holat;
  amal.appendChild(belgi);

  if (amallar && b.holat === 'yangi') {
    const tugma = document.createElement('button');
    tugma.className = 'mini-btn asosiy';
    tugma.textContent = 'Qabul qilish';
    tugma.addEventListener('click', ()=> vazifaQabul(b.id, tugma));
    amal.appendChild(tugma);
  }
  if (amallar && (b.holat === 'qabul' || b.holat === 'bajarilmoqda')) {
    const tugma = document.createElement('button');
    tugma.className = 'mini-btn yashil';
    tugma.textContent = 'Yakunlash';
    tugma.addEventListener('click', ()=> vazifaYakunla(b.id, tugma, b));
    amal.appendChild(tugma);
  }

  qator.append(vaqt, info, amal);
  return qator;
}

function vazifalarChiz(){
  const faol = vazifalar.filter(b => FAOL_HOLATLAR.includes(b.holat));
  const tarix = vazifalar.filter(b => !FAOL_HOLATLAR.includes(b.holat));

  // — Bosh sahifa: bugungi vazifalar
  const bugunRoyxat = document.getElementById('bugunRoyxat');
  const bugunHolat = document.getElementById('bugunHolat');
  const bugun = faol.filter(b => bugunmi(b.yaratilgan));
  bugunRoyxat.innerHTML = '';
  if (!bugun.length) {
    bugunHolat.textContent = faol.length
      ? 'Bugunga vazifa yo\'q. Barcha faol vazifalar "Vazifalarim" bo\'limida.'
      : 'Hozircha sizga vazifa tayinlanmagan.';
    bugunHolat.style.display = 'block';
  } else {
    bugunHolat.style.display = 'none';
    bugun.forEach(b => bugunRoyxat.appendChild(vazifaQator(b, true)));
  }

  // — Vazifalarim
  const vazifaRoyxat = document.getElementById('vazifaRoyxat');
  const vazifaHolat = document.getElementById('vazifaHolat');
  document.getElementById('vazifaSoni').textContent = faol.length ? `(${faol.length} ta)` : '';
  vazifaRoyxat.innerHTML = '';
  if (!faol.length) {
    vazifaHolat.textContent = 'Faol vazifa yo\'q. Yangi buyurtma tayinlanganda shu yerda ko\'rinadi.';
    vazifaHolat.style.display = 'block';
  } else {
    vazifaHolat.style.display = 'none';
    faol.forEach(b => vazifaRoyxat.appendChild(vazifaQator(b, true)));
  }

  // — Ish tarixi
  const tana = document.getElementById('tarixTana');
  const tarixHolat = document.getElementById('tarixHolat');
  document.getElementById('tarixSoni').textContent = tarix.length ? `(${tarix.length} ta)` : '';
  tana.innerHTML = '';
  if (!tarix.length) {
    tarixHolat.textContent = 'Yakunlangan ish hozircha yo\'q.';
    tarixHolat.style.display = 'block';
  } else {
    tarixHolat.style.display = 'none';
    tarix.forEach(b => {
      const tr = document.createElement('tr');
      [
        sanaVaqt(b.natija_sana || b.yangilangan || b.yaratilgan),
        b.xizmat_nomi || b.xizmat,
        [b.manzil, b.tuman].filter(Boolean).join(', ') || '—',
        b.natija_soat ? b.natija_soat + ' soat' : '—',
        b.material || '—',
        HOLAT_MATN[b.holat] || b.holat
      ].forEach(matn => {
        const td = document.createElement('td');
        td.textContent = matn;
        tr.appendChild(td);
      });
      tana.appendChild(tr);
    });
  }

  // — Bosh sahifa statistikasi
  const bajarildi = vazifalar.filter(b => b.holat === 'bajarildi');
  const oyBajarildi = bajarildi.filter(b => shuOymi(b.natija_sana || b.yangilangan));
  const oySoat = oyBajarildi.reduce((s, b) => s + (Number(b.natija_soat) || 0), 0);
  document.getElementById('statOyBajarildi').textContent = oyBajarildi.length;
  document.getElementById('statJamiBajarildi').textContent = bajarildi.length;
  document.getElementById('statOySoat').textContent = oySoat ? oySoat.toFixed(1) : '0';
  document.getElementById('statFaol').textContent = faol.length;
}

async function vazifalarYukla(){
  try {
    const javob = await apiSorov('/buyurtmalar/');
    vazifalar = Array.isArray(javob) ? javob : (javob.results || []);
    vazifalarChiz();
    tushumBuyurtmaTanla();
    narxVazifaTanla();
  } catch (xato) {
    ['bugunHolat', 'vazifaHolat', 'tarixHolat'].forEach(id => {
      const el = document.getElementById(id);
      el.textContent = 'Yuklab bo\'lmadi: ' + xato.message;
      el.style.display = 'block';
    });
  }
}

async function vazifaQabul(id, tugma){
  tugma.disabled = true;
  try {
    await apiSorov(`/buyurtmalar/${id}/qabul/`, { method: 'POST' });
    await vazifalarYukla();
  } catch (xato) {
    alert('Qabul qilinmadi: ' + xato.message);
    tugma.disabled = false;
  }
}

async function vazifaYakunla(id, tugma, b){
  // Ish yakunlanishidan oldin narx hisoblanib tasdiqlangan bo'lishi kerak (pul shu summa bo'yicha olinadi)
  if (b && !(b.xizmatlar && b.xizmatlar.tasdiq_summa != null)
      && !confirm('Bu buyurtmaning summasi hali tasdiqlanmagan (narxnomadan xizmat tanlab, "Summani tasdiqlash"ni bosing).\nBaribir yakunlaysizmi?')) {
    return;
  }
  const natija = prompt('Bajarilgan ish natijasi (mijozga SMS orqali yuboriladi):');
  if (natija === null) return;
  const soat = prompt('Ishga ketgan vaqt (soat), masalan 2.5:', '');
  if (soat === null) return;
  const material = prompt('Ishlatilgan material (bo\'sh qoldirish mumkin):', '') ?? '';
  tugma.disabled = true;
  try {
    await apiSorov(`/buyurtmalar/${id}/natija/`, {
      method: 'POST',
      body: JSON.stringify({
        natija: natija.trim(),
        natija_soat: soat.trim().replace(',', '.') || null,
        material: material.trim(),
        holat: 'bajarildi'
      })
    });
    await vazifalarYukla();
  } catch (xato) {
    alert('Yakunlanmadi: ' + xato.message);
    tugma.disabled = false;
  }
}

document.getElementById('yangilashBtn').addEventListener('click', async (e)=>{
  const btn = e.currentTarget;
  btn.disabled = true;
  await vazifalarYukla();
  btn.disabled = false;
});

// ═══════ Smena va joylashuv ═══════
// Joylashuv FAQAT smena ochiq bo'lganda va xodim rozilik bergandan keyin
// yuboriladi. Brauzer joylashuvni sahifa ochiq va ekran yoniq turgandagina
// bera oladi, shuning uchun smena davomida ekran o'chib qolmasligi so'raladi.
let smena = { rozilik: false, faol: false, oraliq_soniya: 15 };
let joyKuzatuvId = null;
let oxirgiYuborilgan = 0;
let ekranQulfi = null;

function smenaXato(matn){
  const el = document.getElementById('smenaXato');
  el.textContent = matn || '';
  el.classList.toggle('show', !!matn);
}

function smenaChiz(){
  const belgi = document.getElementById('smenaBelgi');
  const matn = document.getElementById('smenaMatn');
  const btn = document.getElementById('smenaBtn');
  const rozi = document.getElementById('smenaRozilik');
  belgi.textContent = smena.faol ? 'Smena ochiq' : 'Smena yopiq';
  belgi.className = 'tag ' + (smena.faol ? 'done' : 'wait');
  rozi.style.display = (!smena.faol && !smena.rozilik) ? 'block' : 'none';
  btn.disabled = false;
  if (smena.faol) {
    matn.textContent = 'Joylashuvingiz administratorga ko\'rinib turibdi. Aloqa uzilmasligi uchun shu sahifani ochiq va ekranni yoniq qoldiring. Ish tugagach "Ishni tugatish" tugmasini bosing.';
    btn.textContent = 'Ishni tugatish';
    btn.className = 'mini-btn qizil smena-btn';
  } else {
    matn.textContent = 'Joylashuv faqat smena davomida va sizning roziligingiz bilan olinadi. Smena yopiq paytda hech narsa kuzatilmaydi.';
    btn.textContent = 'Ishni boshlash';
    btn.className = 'mini-btn yashil smena-btn';
    if (!smena.rozilik) btn.disabled = !document.getElementById('roziBelgi').checked;
  }
}

async function ekranQulfiOl(){
  try {
    if ('wakeLock' in navigator && !ekranQulfi) {
      ekranQulfi = await navigator.wakeLock.request('screen');
      ekranQulfi.addEventListener('release', () => { ekranQulfi = null; });
    }
  } catch (e) { /* qo'llab-quvvatlanmasa ham kuzatuv ishlayveradi */ }
}
function ekranQulfiBosh(){
  try { if (ekranQulfi) ekranQulfi.release(); } catch (e) {}
  ekranQulfi = null;
}
document.addEventListener('visibilitychange', () => {
  if (document.visibilityState === 'visible' && smena.faol) ekranQulfiOl();
});

function joyKuzatuvToxtat(){
  if (joyKuzatuvId !== null && navigator.geolocation) navigator.geolocation.clearWatch(joyKuzatuvId);
  joyKuzatuvId = null;
  ekranQulfiBosh();
}

function joyKuzatuvBoshla(){
  if (KORISH) return;      // egasining telefoni xodim joylashuvi sifatida yuborilmasin
  if (joyKuzatuvId !== null || !navigator.geolocation) return;
  ekranQulfiOl();
  joyKuzatuvId = navigator.geolocation.watchPosition(async (poz) => {
    const hozir = Date.now();
    if (hozir - oxirgiYuborilgan < smena.oraliq_soniya * 1000) return;
    oxirgiYuborilgan = hozir;
    try {
      smenaXato('');
      await apiSorov('/joylashuv/nuqta/', { method: 'POST', body: JSON.stringify({
        lat: poz.coords.latitude, lng: poz.coords.longitude, aniqlik: poz.coords.accuracy }) });
    } catch (e) {
      // Xato bo'lsa smena holatini serverdan so'raymiz: yopilgan bo'lsa
      // (masalan, vaqti tugab o'zi yopilgan) kuzatuvni to'xtatamiz
      const h = await apiSorov('/joylashuv/smena/').catch(() => null);
      if (h && !h.faol) { smena = h; joyKuzatuvToxtat(); smenaChiz(); }
    }
  }, (xato) => {
    smenaXato(xato.code === 1
      ? 'Joylashuvga ruxsat berilmagan. Brauzer sozlamalarida ruxsat bering, aks holda administrator sizni ko\'ra olmaydi.'
      : 'Joylashuvni aniqlab bo\'lmadi. GPS yoqilganini tekshiring.');
  }, { enableHighAccuracy: true, maximumAge: 10000, timeout: 30000 });
}

async function smenaYukla(){
  try {
    smena = await apiSorov('/joylashuv/smena/');
  } catch (e) {
    document.getElementById('smenaMatn').textContent = 'Smena holatini yuklab bo\'lmadi.';
    return;
  }
  smenaChiz();
  if (smena.faol) joyKuzatuvBoshla();
}

// Ruxsatni smena ochishdan OLDIN so'raymiz: rad etilsa, smena ochilmaydi va
// administrator "kuzatilmoqda" deb o'ylab qolmaydi.
function joyRuxsatiniSora(){
  return new Promise((ok, rad) => {
    if (!navigator.geolocation) return rad(new Error('Bu qurilma joylashuvni qo\'llab-quvvatlamaydi.'));
    navigator.geolocation.getCurrentPosition(ok, (x) => rad(new Error(x.code === 1
      ? 'Joylashuvga ruxsat berilmadi. Ruxsat bermasangiz smenani boshlab bo\'lmaydi.'
      : 'Joylashuvni aniqlab bo\'lmadi. GPS yoqilganini tekshiring.')),
      { enableHighAccuracy: true, timeout: 20000 });
  });
}

document.getElementById('roziBelgi').addEventListener('change', smenaChiz);

document.getElementById('smenaBtn').addEventListener('click', async () => {
  const btn = document.getElementById('smenaBtn');
  smenaXato('');
  if (KORISH) { smenaXato("Ko'rish rejimida o'zgartirish mumkin emas"); return; }
  btn.disabled = true;
  try {
    if (smena.faol) {
      smena = await apiSorov('/joylashuv/smena/tugatish/', { method: 'POST' });
      joyKuzatuvToxtat();
    } else {
      await joyRuxsatiniSora();
      smena = await apiSorov('/joylashuv/smena/boshlash/', { method: 'POST',
        body: JSON.stringify({ rozilik: document.getElementById('roziBelgi').checked || smena.rozilik }) });
      oxirgiYuborilgan = 0;
      joyKuzatuvBoshla();
    }
  } catch (e) {
    smenaXato(e.message);
  }
  smenaChiz();
});

// ═══════ Administratordan xabarlar (qo'ng'iroqcha) ═══════
// Har 30 soniyada so'raladi; qo'ng'iroqcha ochilganda o'qilgan deb belgilanadi.
let xabarTaymer = null;
let oqilmaganXabar = 0;

async function xabarlarYukla(){
  if (!token) return;
  try {
    const r = await apiSorov('/aloqa/');
    oqilmaganXabar = r.oqilmagan;
    document.getElementById('bellDot').style.display = r.oqilmagan ? 'block' : 'none';
    document.getElementById('bellSoni').textContent = r.oqilmagan ? `${r.oqilmagan} ta yangi` : 'Yangi xabar yo\'q';
    document.getElementById('bellRoyxat').innerHTML = r.xabarlar.length
      ? r.xabarlar.map(x => `
        <div class="dd-item" style="align-items:flex-start;cursor:default;${x.oqilgan ? '' : 'background:var(--blue-light);'}">
          <i class="ti ti-message" style="margin-top:2px;"></i>
          <span style="white-space:normal;">${matnEsc(x.matn)}<br><span style="font-size:11px;color:var(--text-muted);">${matnEsc(sanaVaqt(x.yaratilgan))}</span></span>
        </div>`).join('')
      : '<div class="dd-item" style="cursor:default;">Hozircha xabar yo\'q</div>';
  } catch (e) { /* tarmoq xatosi — keyingi so'rovda qayta uriniladi */ }
}

async function xabarlarOqildi(){
  if (KORISH || !oqilmaganXabar) return;      // egasi ko'rgani xodim uchun "o'qildi" bo'lmasin
  try {
    await apiSorov('/aloqa/oqildi/', { method: 'POST' });
    oqilmaganXabar = 0;
    document.getElementById('bellDot').style.display = 'none';
    document.getElementById('bellSoni').textContent = 'Yangi xabar yo\'q';
  } catch (e) {}
}

function xabarlarBoshla(){
  xabarlarYukla();
  clearInterval(xabarTaymer);
  xabarTaymer = setInterval(xabarlarYukla, 30000);
}
function xabarlarToxtat(){
  clearInterval(xabarTaymer);
  xabarTaymer = null;
}

// ═══════ Xizmatlar narxnomasi (faqat ko'rish) ═══════
// Narxlarni administrator boshqaruv panelidan o'zgartiradi; bu yerda doim joriy narx ko'rinadi.
// Narxnomalar tarmoq (ulgurji / aholi) va bo'limlarga bo'lingan. `narxQatorlar` — hamma
// narxnomalarning qatorlari bitta ro'yxatda, har qatorda `n` (o'z narxnomasi) bor.
let narxNomalar = [];
let narxQatorlar = [];
let narxJoriyId = null;          // hozir ko'rsatilayotgan narxnoma

function narxJoriy(){ return narxNomalar.find(n => n.id === narxJoriyId) || null; }
function tarmoqQisqa(nom){ return String(nom || '').split(' (')[0]; }
// Tanlangan xizmat yonidagi qisqa nom («profilaktika»); bo'sh bo'lsa ko'rsatilmaydi
function ustunQisqa(r, ustun){ return (ustun === 'p' ? r.n.ustun1_qisqa : r.n.ustun2_qisqa) || ''; }

function narxMatni(dan, gacha, izoh){
  const f = (n) => Number(n).toLocaleString('ru-RU');
  if (dan == null) return izoh || '—';
  return gacha != null ? `${f(dan)} – ${f(gacha)}` : f(dan);
}

// Tanlangan narxlar: kalit "<qator id>:<p|r>" -> soni. Qidiruv jadvalni qayta
// chizsa ham tanlov saqlanadi.
const narxTanlangan = new Map();

function narxTanlaHujayra(r, ustun){
  if (ustun === 'r' && !r.n.ustun2) return '';        // bitta narxli narxnomada 2-ustun yo'q
  const dan = ustun === 'p' ? r.p_dan : r.r_dan;
  const gacha = ustun === 'p' ? r.p_gacha : r.r_gacha;
  if (dan == null) return `<td class="narx-matn">${matnEsc(r.izoh || '—')}</td>`;
  const kalit = `${r.id}:${ustun}`;
  const tanlangan = narxTanlangan.has(kalit);
  return `<td class="narx-tanla${tanlangan ? ' tanlangan' : ''}" tabindex="0" role="button"
      aria-pressed="${tanlangan}" data-kalit="${kalit}">${matnEsc(narxMatni(dan, gacha, ''))}</td>`;
}

// Tarmoq va bo'lim yorliqlari (tab). Bo'limlar faqat tarmoqda bittadan ko'p bo'lsa chiqadi.
function narxTabChiz(){
  const tarmoqlar = [];
  narxNomalar.forEach(n => { if (!tarmoqlar.includes(n.tarmoq)) tarmoqlar.push(n.tarmoq); });
  const joriy = narxJoriy();
  document.getElementById('narxTarmoqTab').innerHTML = tarmoqlar.length > 1 ? tarmoqlar.map(t => {
    const nom = tarmoqQisqa(narxNomalar.find(n => n.tarmoq === t).tarmoq_nomi);
    return `<button type="button" class="narx-tab-btn${joriy && joriy.tarmoq === t ? ' active' : ''}" data-tarmoq="${matnEsc(t)}">${matnEsc(nom)}</button>`;
  }).join('') : '';
  const bolimlar = joriy ? narxNomalar.filter(n => n.tarmoq === joriy.tarmoq) : [];
  document.getElementById('narxBolimTab').innerHTML = bolimlar.length > 1 ? bolimlar.map(n =>
    `<button type="button" class="narx-tab-btn sub${n.id === narxJoriyId ? ' active' : ''}" data-narxnoma="${Number(n.id)}">${matnEsc(n.bolim_nomi)}</button>`
  ).join('') : '';
}

function narxJoriyniQoy(id){
  narxJoriyId = id;
  const n = narxJoriy();
  if (!n) return;
  document.getElementById('narxTavsif').textContent = n.sarlavha + (n.tavsif ? ' — ' + n.tavsif : '');
  document.getElementById('narxU1').textContent = n.ustun1;
  const u2 = document.getElementById('narxU2');
  u2.textContent = n.ustun2;
  u2.style.display = n.ustun2 ? '' : 'none';
  // Ustunlar soniga qarab kengliklar (jadval qat'iy kenglikda)
  document.getElementById('narxCols').innerHTML = '<col style="width:52px"><col>'
    + '<col style="width:min(24%,230px)">' + (n.ustun2 ? '<col style="width:min(24%,230px)">' : '');
  document.getElementById('narxEslatma').textContent = n.eslatma ? 'Eslatma: ' + n.eslatma : '';
  narxTabChiz();
  narxChiz();
}

document.getElementById('narxTarmoqTab').addEventListener('click', (e) => {
  const b = e.target.closest('[data-tarmoq]');
  if (!b) return;
  const n = narxNomalar.find(x => x.tarmoq === b.dataset.tarmoq);
  if (!n) return;
  // Narxlar tarmoqlar bo'yicha aralashib ketmasin: boshqa tarmoqqa o'tganda tanlov tozalanadi
  if (narxTanlangan.size && narxTanlanganTarmoq() !== n.tarmoq) {
    if (!confirm('Boshqa tarmoq narxlariga o\'tsangiz, tanlangan xizmatlar tozalanadi. Davom etasizmi?')) return;
    narxTanlangan.clear();
  }
  narxJoriyniQoy(n.id);
  narxPanelChiz();
});
document.getElementById('narxBolimTab').addEventListener('click', (e) => {
  const b = e.target.closest('[data-narxnoma]');
  if (b) narxJoriyniQoy(Number(b.dataset.narxnoma));
});

// Tanlangan xizmatlar qaysi tarmoqdan (hammasi bir tarmoqdan bo'ladi)
function narxTanlanganTarmoq(){
  for (const kalit of narxTanlangan.keys()) {
    const r = narxQatorlar.find(x => String(x.id) === kalit.split(':')[0]);
    if (r) return r.n.tarmoq;
  }
  return null;
}

function narxChiz(){
  const q = document.getElementById('narxQidir').value.trim().toLowerCase();
  const tana = document.getElementById('narxTana');
  const joriyQatorlar = narxQatorlar.filter(r => r.n.id === narxJoriyId);
  const royxat = joriyQatorlar.filter(r => !q || r.nomi.toLowerCase().includes(q) || String(r.tartib) === q);
  tana.innerHTML = royxat.map(r => `
    <tr>
      <td>${Number(r.tartib)}</td>
      <td>${matnEsc(r.nomi)}</td>
      ${narxTanlaHujayra(r, 'p')}
      ${narxTanlaHujayra(r, 'r')}
    </tr>`).join('');
  const holat = document.getElementById('narxHolat');
  holat.textContent = royxat.length ? '' : (joriyQatorlar.length ? 'Hech narsa topilmadi'
    : "Bu bo'limda narxlar hali kiritilmagan. Narxlarni administrator kiritadi.");
  holat.style.display = royxat.length ? 'none' : 'block';
}

function narxPanelChiz(){
  const panel = document.getElementById('narxPanel');
  if (!narxTanlangan.size) { panel.style.display = 'none'; return; }
  let jamiMin = 0, jamiMax = 0;
  const qatorlar = [];
  narxTanlangan.forEach((soni, kalit) => {
    const [id, ustun] = kalit.split(':');
    const r = narxQatorlar.find(x => String(x.id) === id);
    if (!r) return;
    const dan = ustun === 'p' ? r.p_dan : r.r_dan;
    const gacha = ustun === 'p' ? r.p_gacha : r.r_gacha;
    jamiMin += dan * soni;
    jamiMax += (gacha != null ? gacha : dan) * soni;
    qatorlar.push({ kalit, soni, r, ustun, narx: narxMatni(dan, gacha, '') });
  });
  const f = (n) => n.toLocaleString('ru-RU');
  document.getElementById('narxPanelSoni').textContent = `Tanlangan xizmatlar: ${qatorlar.length} ta`;
  document.getElementById('narxJami').textContent =
    'Jami: ' + (jamiMin === jamiMax ? f(jamiMin) : `${f(jamiMin)} – ${f(jamiMax)}`) + " so'm";
  narxVazifaTanla();
  document.getElementById('narxPanelIzoh').textContent = jamiMin === jamiMax ? ''
    : 'Ba\'zi xizmatlarning narxi oraliqda berilgan, shuning uchun jami ham "eng kam – eng ko\'p" ko\'rinishida.';
  document.getElementById('narxTanlanganRoyxat').innerHTML = qatorlar.map(x => `
    <div class="qator">
      <span class="nom"><b>№${Number(x.r.tartib)}</b> ${matnEsc(x.r.nomi)}
        <span style="color:var(--text-muted)">(${matnEsc(ustunQisqa(x.r, x.ustun) ? ustunQisqa(x.r, x.ustun) + ': ' : '')}${matnEsc(x.narx)} so'm)</span></span>
      <input type="number" min="1" max="999" value="${Number(x.soni)}" data-soni="${x.kalit}" aria-label="Soni">
      <button type="button" data-olib="${x.kalit}" aria-label="Olib tashlash">×</button>
    </div>`).join('');
  panel.style.display = 'block';
}

function narxTanlovOzgardi(){
  narxChiz();
  narxPanelChiz();
}

// Tanlangan xizmatlar biriktiriladigan vazifalar: faol va summasi hali tasdiqlanmagan
function narxVazifaTanla(){
  const sel = document.getElementById('narxVazifa');
  const btn = document.getElementById('narxBiriktir');
  if (!sel) return;
  const oldingi = sel.value;
  // Narxlar tarmoqqa qarab farq qiladi: tanlangan xizmatlar faqat o'sha tarmoqdagi vazifaga biriktiriladi
  const tarmoq = narxTanlanganTarmoq();
  const royxat = (vazifalar || []).filter(b => FAOL_HOLATLAR.includes(b.holat)
    && !(b.xizmatlar && b.xizmatlar.tasdiq_summa != null)
    && (!tarmoq || b.tarmoq === tarmoq));
  const tarmoqNomi = tarmoq ? tarmoqQisqa((narxNomalar.find(n => n.tarmoq === tarmoq) || {}).tarmoq_nomi) : '';
  sel.innerHTML = royxat.length
    ? royxat.map(b => `<option value="${Number(b.id)}">#${Number(b.id)} ${matnEsc(b.xizmat_nomi || b.xizmat)} — ${matnEsc(b.manzil || b.tuman || '')}</option>`).join('')
    : `<option value="">${tarmoq ? matnEsc(tarmoqNomi) + ' tarmog\'idagi faol vazifa yo\'q' : 'Biriktirish uchun faol vazifa yo\'q'}</option>`;
  if (oldingi && royxat.some(b => String(b.id) === oldingi)) sel.value = oldingi;
  sel.disabled = btn.disabled = !royxat.length;
}

document.getElementById('narxBiriktir').addEventListener('click', async () => {
  const xato = document.getElementById('narxXato');
  const btn = document.getElementById('narxBiriktir');
  const vazifaId = Number(document.getElementById('narxVazifa').value);
  xato.classList.remove('show');
  if (!vazifaId || !narxTanlangan.size) return;
  const xizmatlar = [];
  narxTanlangan.forEach((soni, kalit) => {
    const [id, ustun] = kalit.split(':');
    xizmatlar.push({ qator: Number(id), ustun, soni });
  });
  btn.disabled = true;
  try {
    await apiSorov(`/buyurtmalar/${vazifaId}/xizmatlar/`, { method: 'POST', body: JSON.stringify({ xizmatlar }) });
    narxTanlangan.clear();
    narxTanlovOzgardi();
    await vazifalarYukla();
    // Vazifalarim bo'limiga o'tamiz va biriktirilgan vazifani ajratib ko'rsatamiz
    vazifaBelgilangan = vazifaId;
    vazifalarChiz();
    showPage('tasks');
    requestAnimationFrame(() => {
      const el = document.querySelector('#vazifaRoyxat .task-row.belgilangan');
      if (el) el.scrollIntoView({ behavior: 'smooth', block: 'center' });
    });
    setTimeout(() => { vazifaBelgilangan = null; vazifalarChiz(); }, 6000);
  } catch (e) {
    xato.textContent = e.message;
    xato.classList.add('show');
  } finally {
    btn.disabled = false;
  }
});

function narxHujayraBosildi(td){
  const kalit = td.dataset.kalit;
  if (!kalit) return;
  if (narxTanlangan.has(kalit)) narxTanlangan.delete(kalit); else narxTanlangan.set(kalit, 1);
  // Butun jadvalni qayta chizmaymiz: qidiruv/skroll joyi o'zgarmasin
  td.classList.toggle('tanlangan', narxTanlangan.has(kalit));
  td.setAttribute('aria-pressed', narxTanlangan.has(kalit));
  narxPanelChiz();
}

document.getElementById('narxTana').addEventListener('click', (e) => {
  const td = e.target.closest('td.narx-tanla');
  if (td) narxHujayraBosildi(td);
});
document.getElementById('narxTana').addEventListener('keydown', (e) => {
  if (e.key !== 'Enter' && e.key !== ' ') return;
  const td = e.target.closest('td.narx-tanla');
  if (td) { e.preventDefault(); narxHujayraBosildi(td); }
});

document.getElementById('narxTanlanganRoyxat').addEventListener('input', (e) => {
  const kalit = e.target.dataset && e.target.dataset.soni;
  if (!kalit) return;
  const son = Math.min(999, Math.max(1, parseInt(e.target.value, 10) || 1));
  narxTanlangan.set(kalit, son);
  // Faqat jamini yangilaymiz — yozayotgan maydon fokusdan chiqmasin
  let mn = 0, mx = 0;
  narxTanlangan.forEach((s, k) => {
    const [id, ustun] = k.split(':');
    const r = narxQatorlar.find(x => String(x.id) === id);
    if (!r) return;
    const dan = ustun === 'p' ? r.p_dan : r.r_dan;
    const gacha = ustun === 'p' ? r.p_gacha : r.r_gacha;
    mn += dan * s; mx += (gacha != null ? gacha : dan) * s;
  });
  const f = (n) => n.toLocaleString('ru-RU');
  document.getElementById('narxJami').textContent =
    'Jami: ' + (mn === mx ? f(mn) : `${f(mn)} – ${f(mx)}`) + " so'm";
});
document.getElementById('narxTanlanganRoyxat').addEventListener('click', (e) => {
  const b = e.target.closest('[data-olib]');
  if (!b) return;
  narxTanlangan.delete(b.dataset.olib);
  narxTanlovOzgardi();
});
document.getElementById('narxTozala').addEventListener('click', () => {
  narxTanlangan.clear();
  narxTanlovOzgardi();
});
document.getElementById('narxNusxa').addEventListener('click', async (e) => {
  const satrlar = [];
  narxTanlangan.forEach((soni, kalit) => {
    const [id, ustun] = kalit.split(':');
    const r = narxQatorlar.find(x => String(x.id) === id);
    if (!r) return;
    const dan = ustun === 'p' ? r.p_dan : r.r_dan;
    const gacha = ustun === 'p' ? r.p_gacha : r.r_gacha;
    const qisqa = ustunQisqa(r, ustun);
    satrlar.push(`${r.tartib}. ${r.nomi}${qisqa ? ` (${qisqa})` : ''} — ${narxMatni(dan, gacha, '')} so'm × ${soni}`);
  });
  satrlar.push(document.getElementById('narxJami').textContent);
  const tugma = e.currentTarget;
  try {
    await navigator.clipboard.writeText(satrlar.join('\n'));
    tugma.textContent = 'Nusxa olindi';
  } catch (err) {
    tugma.textContent = 'Nusxa olib bo\'lmadi';
  }
  setTimeout(() => { tugma.innerHTML = '<i class="ti ti-copy"></i> Nusxa olish'; }, 1800);
});

async function narxnomaYukla(){
  try {
    narxNomalar = await apiSorov('/narxnoma/');
    // Barcha narxnomalarning qatorlari bir ro'yxatda; har qator o'z narxnomasini `n` sifatida biladi
    narxQatorlar = narxNomalar.flatMap(n => n.qatorlar.map(q => ({ ...q, n })));
    // Yangilangan narxnomada olib tashlangan qatorlar tanlovdan chiqariladi
    [...narxTanlangan.keys()].forEach(k => {
      if (!narxQatorlar.some(x => String(x.id) === k.split(':')[0])) narxTanlangan.delete(k);
    });
    if (!narxNomalar.length) {
      narxJoriyId = null;
      tushumTuriToldir();
      document.getElementById('narxTavsif').textContent = '';
      document.getElementById('narxTarmoqTab').innerHTML = document.getElementById('narxBolimTab').innerHTML = '';
      narxChiz();
      narxPanelChiz();
      return;
    }
    // Ko'rsatiladigan narxnoma: oldingisi saqlanadi, bo'lmasa narxi bor birinchisi
    const tanlangan = narxNomalar.some(n => n.id === narxJoriyId) ? narxJoriyId
      : (narxNomalar.find(n => n.qatorlar.length) || narxNomalar[0]).id;
    narxJoriyniQoy(tanlangan);
    narxPanelChiz();
    tushumTuriToldir();       // Tushum turi ro'yxati narxnomalardan quriladi
  } catch (e) {
    const h = document.getElementById('narxHolat');
    h.textContent = 'Yuklab bo\'lmadi: ' + e.message;
    h.style.display = 'block';
  }
}

document.getElementById('narxQidir').addEventListener('input', narxChiz);

// ═══════ Pul tushumi (mijozdan olingan pul) ═══════
function somFormat(son){
  return (Number(son) || 0).toLocaleString('ru-RU') + " so'm";
}
function matnEsc(matn){
  const el = document.createElement('div');
  el.textContent = matn == null ? '' : String(matn);
  return el.innerHTML;
}

// ── Tushum turi (bosqich): narx tarmog'i + bo'lim ──
// Ro'yxat narxnomalardan quriladi: Aholi (buyurtma asosida / profilaktika va texnik ko'rik /
// yangi jihoz o'rnatish) va Ulgurji. Tanlangan bosqich qolgan maydonlarni belgilaydi:
// buyurtma (faqat shu tarmoqdagi) va ish turi (faqat shu narxnomadagi).
function tushumTuri(){
  const v = document.getElementById('tushTuri').value;
  if (!v) return { tanlanmagan: true };
  if (v === 'boshqa') return { boshqa: true };
  const [tarmoq, bolim] = v.split(':');
  return { tarmoq, bolim, nomi: (narxNomalar.find(n => n.tarmoq === tarmoq && n.bolim === bolim) || {}).bolim_nomi || '' };
}

function tushumTuriToldir(){
  const sel = document.getElementById('tushTuri');
  const oldingi = sel.value;
  const guruhlar = [];
  narxNomalar.forEach(n => { if (!guruhlar.includes(n.tarmoq)) guruhlar.push(n.tarmoq); });
  sel.innerHTML = '<option value="">— tanlang —</option>' + guruhlar.map(t => {
    const nomlar = narxNomalar.filter(n => n.tarmoq === t);
    return `<optgroup label="${matnEsc(tarmoqQisqa(nomlar[0].tarmoq_nomi))}">` + nomlar.map(n =>
      `<option value="${matnEsc(n.tarmoq)}:${matnEsc(n.bolim)}">${matnEsc(n.bolim_nomi)}</option>`).join('') + '</optgroup>';
  }).join('') + '<optgroup label="Boshqa"><option value="boshqa">Boshqa (turkumsiz pul)</option></optgroup>';
  sel.value = oldingi;
  if (sel.value !== oldingi) sel.value = '';
  tushumTuriChiz();
}

const TUSHUM_TURI_IZOH = {
  buyurtma: "Buyurtma bo'yicha olingan pul: tizimdagi buyurtmani YOKI quyidagi narxnomadan ish turini tanlang (mijoz o'zi murojaat qilgan bo'lsa, buyurtma shart emas).",
  profilaktika: "Profilaktika va texnik ko'rik uchun olingan pul. Ish turini narxnomadan tanlang.",
  ornatish: "Yangi jihoz o'rnatib ishga tushirib berish uchun olingan pul. Ish turini narxnomadan tanlang.",
  metrologiya: "Metrologiya xizmatlari (hisoblagichni almashtirish, qiyoslov, modem va aloqa) uchun olingan pul. Ish turini narxnomadan tanlang.",
};

function tushumTuriChiz(){
  const t = tushumTuri();
  const turkum = !t.tanlanmagan && !t.boshqa;
  document.getElementById('tushBuyurtmaBlok').style.display = turkum ? 'block' : 'none';
  document.getElementById('tushIshBlok').style.display = turkum ? 'block' : 'none';
  document.getElementById('tushBuyurtmaLabel').textContent = t.bolim === 'buyurtma'
    ? 'Buyurtma (yoki pastdan ish turini tanlang)' : 'Buyurtma (ixtiyoriy)';
  document.getElementById('tushTuriIzoh').textContent = t.tanlanmagan ? "Pul qaysi turdagi ish uchun olinganini tanlang."
    : t.boshqa ? "Narxnomaga kirmaydigan pul (masalan, transport). Buyurtma va ish turi so'ralmaydi."
    : (TUSHUM_TURI_IZOH[t.bolim] || '');
  // Boshqa bosqichdan tanlangan ish turi qolib ketmasin
  if (ishTanlov && turkum) {
    const r = narxQatorlar.find(x => x.id === ishTanlov.qator);
    if (!r || r.n.tarmoq !== t.tarmoq || r.n.bolim !== t.bolim) ishTozala();
  } else if (!turkum && ishTanlov) {
    ishTozala();
  }
  tushumBuyurtmaTanla();
}

function tushumBuyurtmaTanla(){
  const sel = document.getElementById('tushBuyurtma');
  if (!sel) return;
  const tanlangan = sel.value;
  const t = tushumTuri();
  // Buyurtmalar tanlangan tarmoqdan; pul faqat summasi tasdiqlangan buyurtma bo'yicha olinadi:
  // qolganlari ko'rinadi, lekin tanlab bo'lmaydi
  const royxat = (vazifalar || []).filter(b => b.holat !== 'bekor' && (!t.tarmoq || b.tarmoq === t.tarmoq));
  const hisobli = royxat.filter(b => b.xizmatlar && b.xizmatlar.tasdiq_summa != null);
  sel.innerHTML = '<option value="">— buyurtmani tanlang —</option>' + royxat
    .map(b => {
      const t = b.xizmatlar && b.xizmatlar.tasdiq_summa;
      const matn = `#${Number(b.id)} ${matnEsc(b.xizmat_nomi || b.xizmat)} — ${matnEsc(b.manzil || b.tuman || '')}`;
      return t != null
        ? `<option value="${Number(b.id)}">${matn} · summa ${matnEsc(pulMatni(t))} so'm</option>`
        : `<option value="${Number(b.id)}" disabled>${matn} · narx tasdiqlanmagan</option>`;
    }).join('');
  sel.value = tanlangan;
  const tarmoqNomi = t.tarmoq ? tarmoqQisqa((narxNomalar.find(n => n.tarmoq === t.tarmoq) || {}).tarmoq_nomi) : '';
  document.getElementById('tushBuyurtmaIzoh').textContent = hisobli.length
    ? ''
    : (royxat.length
        ? 'Pul olish uchun avval "Narxnoma"dan xizmat tanlab, Vazifalarim bo\'limida summani tasdiqlang.'
        : (t.bolim === 'buyurtma'
            ? `Sizga tayinlangan${tarmoqNomi ? ' ' + tarmoqNomi : ''} buyurtma yo'q: buyurtmasiz davom eting, pastdagi "Ish turi"ni narxnomadan tanlang.`
            : `Sizga tayinlangan${tarmoqNomi ? ' ' + tarmoqNomi : ''} buyurtma yo'q. Buyurtma shart emas.`));
}

document.getElementById('tushTuri').addEventListener('change', tushumTuriChiz);

// ── Tushum: narxnomadagi ish turini tanlash ──
// Maydon bosilganda narxnomadagi barcha ish turlari ochiladi (yozib qidirsa ham bo'ladi).
// Narx tugmasi (profilaktika/reviziya) bosilsa tanlov saqlanadi; aniq narx bo'lsa summa
// maydoni bo'sh bo'lganda o'sha narx taklif qilinadi.
let ishTanlov = null;   // { qator, ustun }

function ishPanelChiz(){
  const panel = document.getElementById('ishPanel');
  // Ish turlari faqat tanlangan tushum turining (tarmoq + bo'lim) narxnomasidan
  const t = tushumTuri();
  const joriyNarxnomalar = narxNomalar.filter(n => !t.tarmoq || (n.tarmoq === t.tarmoq && n.bolim === t.bolim));
  if (!joriyNarxnomalar.some(n => n.qatorlar.length)) {
    panel.innerHTML = '<div class="ish-bosh">Bu bo\'limda narxlar hali kiritilmagan. Ish turini administrator narxnomaga qo\'shadi; hozircha ish turisiz kiritishingiz mumkin.</div>';
    return;
  }
  const q = document.getElementById('tushIsh').value.trim().toLowerCase();
  let html = '';
  joriyNarxnomalar.forEach(n => {
    const royxat = n.qatorlar.map(q2 => ({ ...q2, n }))
      .filter(r => !q || r.nomi.toLowerCase().includes(q) || String(r.tartib) === q);
    if (!royxat.length) return;
    html += `<div class="ish-guruh">${matnEsc(tarmoqQisqa(n.tarmoq_nomi))} · ${matnEsc(n.bolim_nomi)}</div>`;
    html += royxat.map(r => {
      const chip = (ustun, dan, gacha, nom) => dan == null ? '' :
        `<button type="button" class="ish-chip" data-qator="${Number(r.id)}" data-ustun="${ustun}">${nom ? `<small>${matnEsc(nom)}</small>` : ''}${matnEsc(narxMatni(dan, gacha, ''))}</button>`;
      const chiplar = chip('p', r.p_dan, r.p_gacha, ustunQisqa(r, 'p'))
        + (n.ustun2 ? chip('r', r.r_dan, r.r_gacha, ustunQisqa(r, 'r')) : '')
        || `<button type="button" class="ish-chip" data-qator="${Number(r.id)}" data-ustun="">${matnEsc(r.izoh || 'Tanlash')}</button>`;
      return `<div class="ish-qator"><span class="nom"><b>${Number(r.tartib)}.</b>${matnEsc(r.nomi)}</span><span class="chiplar">${chiplar}</span></div>`;
    }).join('');
  });
  panel.innerHTML = html || '<div class="ish-bosh">Hech narsa topilmadi</div>';
}

function ishPanelOch(){
  ishPanelChiz();
  document.getElementById('ishPanel').style.display = 'block';
  document.getElementById('tushIsh').setAttribute('aria-expanded', 'true');
}
function ishPanelYop(){
  document.getElementById('ishPanel').style.display = 'none';
  document.getElementById('tushIsh').setAttribute('aria-expanded', 'false');
}
function ishTozala(){
  ishTanlov = null;
  document.getElementById('tushIsh').value = '';
  document.getElementById('ishIzoh').textContent = '';
  document.getElementById('ishTozala').style.display = 'none';
}

document.getElementById('tushIsh').addEventListener('focus', ishPanelOch);
document.getElementById('tushIsh').addEventListener('click', ishPanelOch);
document.getElementById('tushIsh').addEventListener('input', () => {
  // Yozishni boshlasa, oldingi tanlov bekor bo'ladi va qidiruv ishlaydi
  ishTanlov = null;
  document.getElementById('ishIzoh').textContent = '';
  document.getElementById('ishTozala').style.display = 'none';
  ishPanelOch();
});
document.getElementById('ishTozala').addEventListener('click', ishTozala);
document.addEventListener('click', (e) => { if (!e.target.closest('#ishTanla')) ishPanelYop(); });
document.getElementById('tushIsh').addEventListener('keydown', (e) => { if (e.key === 'Escape') ishPanelYop(); });

document.getElementById('ishPanel').addEventListener('click', (e) => {
  const b = e.target.closest('.ish-chip');
  if (!b) return;
  const r = narxQatorlar.find(x => String(x.id) === b.dataset.qator);
  if (!r) return;
  const ustun = b.dataset.ustun;
  ishTanlov = { qator: Number(r.id), ustun };
  const qisqa = ustun ? ustunQisqa(r, ustun) : '';
  document.getElementById('tushIsh').value = r.nomi + (qisqa ? ` (${qisqa})` : '');
  document.getElementById('ishTozala').style.display = 'block';
  const dan = ustun === 'p' ? r.p_dan : ustun === 'r' ? r.r_dan : null;
  const gacha = ustun === 'p' ? r.p_gacha : ustun === 'r' ? r.r_gacha : null;
  const summaEl = document.getElementById('tushSumma');
  const izoh = document.getElementById('ishIzoh');
  if (dan != null && gacha == null) {
    if (!summaEl.value) summaEl.value = Number(dan).toLocaleString('ru-RU');
    izoh.textContent = `Narxnoma bo'yicha: ${pulMatni(dan)} so'm. Mijozdan olingan summa boshqacha bo'lsa, o'zgartiring.`;
  } else if (dan != null) {
    izoh.textContent = `Narxnoma bo'yicha oraliq: ${pulMatni(dan)} – ${pulMatni(gacha)} so'm. Olingan summani kiriting.`;
  } else {
    izoh.textContent = '';
  }
  ishPanelYop();
});

const TUSHUM_RANG = { kutilmoqda: 'wait', qabul: 'done', rad: 'wait' };

async function tushumYukla(){
  const holat = document.getElementById('tushHolat');
  try {
    const r = await apiSorov('/tushum/');
    tushumRoyxati = r.yozuvlar;
    document.getElementById('tushKutilmoqda').textContent = somFormat(r.jami.kutilmoqda);
    document.getElementById('tushOyQabul').textContent = somFormat(r.jami.oy_qabul);
    document.getElementById('tushJamiQabul').textContent = somFormat(r.jami.qabul);
    const tana = document.getElementById('tushTana');
    tana.innerHTML = r.yozuvlar.map(t => `
      <tr>
        <td>${matnEsc(sanaVaqt(t.yaratilgan))}</td>
        <td><b>${somFormat(t.summa)}</b>${t.ish_turi ? `<br><span style="font-size:12px">${matnEsc(t.ish_turi)}</span>` : ''}${t.tarmoq ? `<br><span style="font-size:11px;color:var(--text-muted)">${matnEsc(tarmoqQisqa(t.tarmoq_nomi))}${t.bolim_nomi ? ' · ' + matnEsc(t.bolim_nomi) : ''}</span>` : ''}${t.izoh ?`<br><span style="color:var(--text-muted);font-size:12px">${matnEsc(t.izoh)}</span>` : ''}</td>
        <td>${matnEsc(t.usul_nomi)}</td>
        <td>${matnEsc(t.buyurtma_nomi || '—')}</td>
        <td>${kvitansiyaKatagi(t)}</td>
        <td><span class="tag ${TUSHUM_RANG[t.holat] || 'wait'}">${matnEsc(t.holat_nomi)}</span>${t.rad_sababi ? `<br><span style="color:#b91c1c;font-size:12px">${matnEsc(t.rad_sababi)}</span>` : ''}</td>
      </tr>`).join('');
    holat.textContent = r.yozuvlar.length ? '' : 'Hali tushum kiritilmagan';
    holat.style.display = r.yozuvlar.length ? 'none' : 'block';
  } catch (e) {
    holat.textContent = 'Yuklab bo\'lmadi: ' + e.message;
    holat.style.display = 'block';
  }
}

document.getElementById('tushSumma').addEventListener('input', (e) => {
  // Faqat raqam; ming ajratgich ko'rinish uchun
  const raqam = e.target.value.replace(/\D/g, '');
  e.target.value = raqam ? Number(raqam).toLocaleString('ru-RU') : '';
});

document.getElementById('tushumForm').addEventListener('submit', async (e) => {
  e.preventDefault();
  const btn = document.getElementById('tushBtn');
  const xato = document.getElementById('tushXato');
  xato.classList.remove('show');
  xato.style.color = '';                     // oldingi yashil xabardan keyin xato qizil bo'lib qoladi
  const summa = Number(document.getElementById('tushSumma').value.replace(/\D/g, ''));
  if (!summa) { xato.textContent = 'Summani kiriting'; xato.classList.add('show'); return; }
  // Tushum turi (bosqich) majburiy; undan buyurtma va ish turi talablari kelib chiqadi
  const tur = tushumTuri();
  if (tur.tanlanmagan) {
    xato.textContent = 'Tushum turini tanlang';
    xato.classList.add('show');
    document.getElementById('tushTuri').focus();
    return;
  }
  const turkum = !tur.boshqa;
  const buyurtma = turkum ? document.getElementById('tushBuyurtma').value : '';
  // «Buyurtma asosida»: buyurtma YOKI narxnomadan ish turi yetarli
  if (turkum && tur.bolim === 'buyurtma' && !buyurtma && !ishTanlov) {
    xato.textContent = 'Buyurtmani tanlang yoki narxnomadan ish turini tanlang';
    xato.classList.add('show');
    return;
  }
  if (turkum && document.getElementById('tushIsh').value.trim() && !ishTanlov) {
    xato.textContent = 'Ish turini ro\'yxatdan tanlang yoki maydonni tozalang';
    xato.classList.add('show');
    ishPanelOch();
    return;
  }
  if (!confirm(`${somFormat(summa)} kiritilsinmi? Kiritilgach o'zgartirib bo'lmaydi.`)) return;
  btn.disabled = true;
  try {
    const yangiTushum = await apiSorov('/tushum/', { method: 'POST', body: JSON.stringify({
      summa,
      usul: document.getElementById('tushUsul').value,
      izoh: document.getElementById('tushIzoh').value,
      tushum_turi: turkum ? `${tur.tarmoq}:${tur.bolim}` : '',
      buyurtma: buyurtma || null,
      ish_qator: turkum && ishTanlov ? ishTanlov.qator : null,
      ish_ustun: turkum && ishTanlov ? ishTanlov.ustun : '',
    }) });
    document.getElementById('tushSumma').value = '';
    document.getElementById('tushIzoh').value = '';
    ishTozala();
    await tushumYukla();
    // Pul olindi: darhol kvitansiya chiqarish taklif qilinadi (mijoz telefoni va turar joyi bilan)
    if (!KORISH) kvitansiyaChiqar(yangiTushum);
  } catch (err) {
    xato.textContent = err.message;
    xato.classList.add('show');
  } finally {
    btn.disabled = false;
  }
});

// ═══════ Hujjatlar: mijoz bilan shartnoma va kvitansiya ═══════
// Zanjir: xizmat tanlandi → summa tasdiqlandi → SHARTNOMA (mijoz SMS kod bilan tasdiqlaydi) →
// pul olindi → KVITANSIYA (mijoz telefoni va turar joyi bilan, mijozga SMS). Hujjat tuzilgach o'zgarmaydi.

// Mijoz ma'lumoti oynasi. `yubor(malumot)` serverga so'rov qiladi; xato bo'lsa oyna ochiq qoladi.
function aloqaDialog(o, yubor){
  return new Promise((hal) => {
    const d = document.getElementById('aloqaDialog');
    const xato = document.getElementById('aloqaXato');
    const tasdiq = document.getElementById('aloqaTasdiq');
    document.getElementById('aloqaSarlavha').textContent = o.sarlavha;
    document.getElementById('aloqaIzoh').textContent = o.izoh || '';
    document.getElementById('aloqaIsm').value = o.ism || '';
    document.getElementById('aloqaTel').value = o.telefon || '';
    document.getElementById('aloqaManzil').value = o.manzil || '';
    document.getElementById('aloqaSms').checked = true;
    document.getElementById('aloqaSmsQator').style.display = o.smsKorsat ? '' : 'none';
    tasdiq.textContent = o.tugma || 'Davom etish';
    xato.classList.remove('show');
    let tugadi = false;
    const yop = (natija) => { if (tugadi) return; tugadi = true; if (d.open) d.close(); hal(natija); };
    d.onclose = () => yop(null);                         // Esc yoki tashqariga bosish
    document.getElementById('aloqaBekor').onclick = () => yop(null);
    document.getElementById('aloqaForma').onsubmit = async (e) => {
      e.preventDefault();
      xato.classList.remove('show');
      tasdiq.disabled = true;
      try {
        const natija = await yubor({
          mijoz_ism: document.getElementById('aloqaIsm').value.trim(),
          mijoz_telefon: document.getElementById('aloqaTel').value.trim(),
          manzil: document.getElementById('aloqaManzil').value.trim(),
          sms: document.getElementById('aloqaSms').checked,
        });
        yop(natija);
      } catch (err) {
        xato.textContent = err.message;
        xato.classList.add('show');
      } finally {
        tasdiq.disabled = false;
      }
    };
    d.showModal();
  });
}

function buyurtmaAloqasi(b){
  const mm = (b && b.mijoz_malumot) || {};
  return {
    ism: mm.ism || (b && b.mijoz_ism) || '',
    telefon: mm.telefon || '',
    manzil: [mm.tuman, mm.manzil].filter(Boolean).join(', '),
  };
}

let tushumRoyxati = [];           // oxirgi yuklangan tushumlar (kvitansiya uchun)

// Server hujjat havolasini SAYT_MANZIL bilan beradi (ishlab chiqishda u "localhost"). Telefonda "localhost"
// telefonning o'zi bo'lib qoladi va hujjat ochilmaydi. Shuning uchun faqat /kvitansiya/ va /shartnoma/
// yo'llari shu sahifa ochilgan manzil (telefonda — kompyuter IP si) bilan almashtiriladi. Serverda manzillar bir xil.
function hujjatHavolasi(url){
  try {
    const u = new URL(url, location.origin);
    if (/^\/(kvitansiya|shartnoma)\/[\w-]+\/?$/.test(u.pathname)) return location.origin + u.pathname;
  } catch (e) { /* noto'g'ri havola — o'zgarishsiz */ }
  return url;
}
// Hujjatni yangi oynada ochadi. Telefon brauzeri so'rovdan keyin ochilgan oynani bloklasa, false qaytaradi
function hujjatOch(url){
  const w = window.open(url, '_blank');
  if (w) { try { w.opener = null; } catch (e) {} return true; }
  return false;
}

async function kvitansiyaChiqar(t){
  const b = t.buyurtma_id ? (vazifalar || []).find(v => v.id === t.buyurtma_id) : null;
  const a = buyurtmaAloqasi(b);
  const k = await aloqaDialog({
    sarlavha: 'Kvitansiya chiqarish',
    izoh: `${somFormat(t.summa)}: mijozning telefoni va turar joyi kvitansiyada chiqadi, tekshirib chiqing. ` +
      "Mijoz saytda ro'yxatdan o'tmagan bo'lsa, shu ma'lumot bilan avtomatik ro'yxatga olinadi.",
    ism: a.ism, telefon: a.telefon, manzil: a.manzil, smsKorsat: true, tugma: 'Kvitansiya chiqarish',
  }, (d) => apiSorov('/hujjatlar/kvitansiya/', { method: 'POST', body: JSON.stringify({ tushum: t.id, ...d }) }));
  if (!k) return;
  await tushumYukla();
  hujjatlarYukla();
  const havola = hujjatHavolasi(k.url);
  hujjatOch(havola);                                // chop etish uchun; bloklansa pastdagi "Kvitansiyani ochish" havolasi bor
  if (k.sms_yuborildi === false) {
    tushXabari(`Kvitansiya ${k.raqam} chiqarildi, lekin mijozga SMS yuborilmadi. Jadvaldagi "SMS yuborish" tugmasi bilan qayta urinib ko'ring.`, havola);
  } else if (k.yangi_mijoz) tushXabari(`${k.mijoz_ism} mijozlar ro'yxatiga olindi. ${k.mijoz_telefon} raqamiga SMS yuborildi.`, havola);
  else tushXabari(`Kvitansiya ${k.raqam} chiqarildi. ${k.mijoz_telefon} raqamiga SMS yuborildi.`, havola);
}

// Pul tushumi formasi tagida yashil xabar (xato emas)
function tushXabari(matn, havola){
  const el = document.getElementById('tushXato');
  el.textContent = matn;
  el.style.color = 'var(--green)';
  if (havola) {
    el.append(' ');
    const a = document.createElement('a');
    a.href = havola; a.target = '_blank'; a.rel = 'noopener';
    a.className = 'havola'; a.style.fontWeight = '700'; a.style.whiteSpace = 'nowrap';
    a.textContent = 'Kvitansiyani ochish';
    el.append(a);
  }
  el.classList.add('show');
}

async function kvitansiyaSms(id, tugma){
  tugma.disabled = true;
  try {
    const k = await apiSorov(`/hujjatlar/kvitansiya/${id}/sms/`, { method: 'POST' });
    if (!k.sms_yuborildi) alert('SMS yuborilmadi. Telefon raqamni tekshiring.');
  } catch (e) { alert(e.message); }
  await tushumYukla();
  hujjatlarYukla();
}

function smsBelgisi(k){
  if (k.holat === 'bekor') return '<span class="sms-xato">Bekor qilingan</span>';
  return k.sms_holat === 'yuborildi' ? '<span class="sms-ok">SMS ✓</span>'
    : k.sms_holat === 'xato' ? '<span class="sms-xato">SMS yuborilmadi</span>' : '<span>SMS yuborilmagan</span>';
}

// Tushum jadvalidagi "Kvitansiya" katagi
function kvitansiyaKatagi(t){
  const k = t.kvitansiya;
  if (k) {
    return `<a class="havola" href="${matnEsc(hujjatHavolasi(k.url))}" target="_blank" rel="noopener">${matnEsc(k.raqam)}</a><br>${smsBelgisi(k)}` +
      (k.holat === 'amal' && k.sms_holat !== 'yuborildi'
        ? ` <button class="mini-btn" type="button" data-kv-sms="${Number(k.id)}">SMS yuborish</button>` : '');
  }
  return t.holat === 'rad' ? '—'
    : `<button class="mini-btn asosiy" type="button" data-kv-chiqar="${Number(t.id)}">Kvitansiya</button>`;
}

// ── Shartnoma (buyurtma kartasida) ──
async function shartnomaTuz(b, tugma){
  const a = buyurtmaAloqasi(b);
  const s = await aloqaDialog({
    sarlavha: 'Shartnoma tuzish',
    izoh: `Buyurtma #${b.id}, summa ${pulMatni(b.xizmatlar.tasdiq_summa)} so'm. Mijoz ma'lumoti shartnomada chiqadi; ` +
      "saytda ro'yxatdan o'tmagan bo'lsa, shu ma'lumot bilan ro'yxatga olinadi.",
    ism: a.ism, telefon: a.telefon, manzil: a.manzil, smsKorsat: false, tugma: 'Shartnoma tuzish',
  }, (d) => apiSorov('/hujjatlar/shartnoma/', { method: 'POST', body: JSON.stringify({ buyurtma: b.id, ...d }) }));
  if (!s) return;
  await vazifalarYukla();
  hujjatlarYukla();
  hujjatOch(hujjatHavolasi(s.url));
}

async function shartnomaAmali(yol, tana, xatoQayerga){
  try {
    await apiSorov(yol, { method: 'POST', body: JSON.stringify(tana || {}) });
    await vazifalarYukla();
    hujjatlarYukla();
  } catch (e) { alert(e.message); }
}

// Vazifa kartasidagi "Hujjatlar" bloki (summa tasdiqlangan buyurtmalar uchun)
function hujjatBloki(b, amallar){
  const h = b.xizmatlar;
  if (!h || h.tasdiq_summa == null || b.holat === 'bekor') return null;
  const faol = amallar && FAOL_HOLATLAR.includes(b.holat);
  const s = b.shartnoma;
  if (!s && !faol) return null;
  const blok = document.createElement('div');
  blok.className = 'task-hujjat';

  const tugmaYasa = (matn, sinf, bos) => {
    const t = document.createElement('button');
    t.type = 'button';
    t.className = 'mini-btn ' + sinf;
    t.textContent = matn;
    t.addEventListener('click', () => bos(t));
    return t;
  };

  if (!s) {
    blok.append(tugmaYasa('Shartnoma tuzish', 'asosiy', (t) => shartnomaTuz(b, t)));
    return blok;
  }

  const sarlavha = document.createElement('div');
  sarlavha.innerHTML = `<b>Shartnoma ${matnEsc(s.raqam)}</b> · ${matnEsc(s.holat_nomi)} · ` +
    `<a class="havola" href="${matnEsc(hujjatHavolasi(s.url))}" target="_blank" rel="noopener">Ko'rish / chop etish</a>`;
  blok.append(sarlavha);

  const tugallanmagan = s.holat === 'qoralama' || s.holat === 'tasdiq_kutilmoqda';
  if (faol && tugallanmagan) {
    const qator = document.createElement('div');
    qator.className = 'qator';
    qator.append(tugmaYasa(s.holat === 'qoralama' ? 'Mijozga SMS kod yuborish' : 'Kodni qayta yuborish', 'asosiy',
      () => shartnomaAmali(`/hujjatlar/shartnoma/${s.id}/kod/`)));
    if (s.holat === 'tasdiq_kutilmoqda') {
      const kod = document.createElement('input');
      kod.type = 'text'; kod.inputMode = 'numeric'; kod.maxLength = 6; kod.placeholder = '______';
      kod.setAttribute('aria-label', 'Mijoz aytgan kod');
      qator.append(kod, tugmaYasa('Tasdiqlash', 'yashil',
        () => shartnomaAmali(`/hujjatlar/shartnoma/${s.id}/tasdiq/`, { kod: kod.value.trim() })));
    }
    qator.append(tugmaYasa("Qog'ozga imzolandi", '', () => {
      if (confirm("Mijoz shartnomani qog'ozga imzoladimi?")) shartnomaAmali(`/hujjatlar/shartnoma/${s.id}/qogoz/`);
    }));
    qator.append(tugmaYasa('Bekor qilish', 'qizil', () => {
      const sabab = (prompt('Bekor qilish sababi:') || '').trim();
      if (sabab) shartnomaAmali(`/hujjatlar/shartnoma/${s.id}/bekor/`, { sabab });
    }));
    blok.append(qator);
    if (s.holat === 'tasdiq_kutilmoqda') {
      const izoh = document.createElement('div');
      izoh.style.cssText = 'margin-top:4px;color:var(--text-muted);';
      izoh.textContent = `Kod ${s.mijoz_telefon} raqamiga yuborildi. Mijoz aytgan 6 xonali kodni kiriting (10 daqiqa amal qiladi).`;
      blok.append(izoh);
    }
  }
  return blok;
}

// ── "Hujjatlarim" sahifasi ──
async function hujjatlarYukla(){
  try {
    const [kvlar, shlar] = await Promise.all([apiSorov('/hujjatlar/kvitansiya/'), apiSorov('/hujjatlar/shartnoma/')]);
    document.getElementById('kvTana').innerHTML = kvlar.map(k => `
      <tr>
        <td><a class="havola" href="${matnEsc(hujjatHavolasi(k.url))}" target="_blank" rel="noopener">${matnEsc(k.raqam)}</a></td>
        <td>${matnEsc(sanaVaqt(k.yaratilgan))}</td>
        <td>${matnEsc(k.mijoz_ism)}</td>
        <td>${matnEsc(k.mijoz_telefon)}</td>
        <td>${matnEsc(k.manzil)}</td>
        <td><b>${somFormat(k.summa)}</b></td>
        <td>${smsBelgisi(k)}</td>
        <td>${k.holat === 'amal' ? `<button class="mini-btn" type="button" data-kv-sms="${Number(k.id)}">SMS qayta</button>` : ''}</td>
      </tr>`).join('');
    const kh = document.getElementById('kvHolat');
    kh.textContent = kvlar.length ? '' : 'Hali kvitansiya chiqarilmagan';
    kh.style.display = kvlar.length ? 'none' : 'block';

    document.getElementById('shTana').innerHTML = shlar.map(s => `
      <tr>
        <td><a class="havola" href="${matnEsc(hujjatHavolasi(s.url))}" target="_blank" rel="noopener">${matnEsc(s.raqam)}</a></td>
        <td>${matnEsc(s.mijoz_ism)}</td>
        <td>${matnEsc(s.mijoz_telefon)}</td>
        <td>${matnEsc(s.manzil)}</td>
        <td><b>${somFormat(s.summa)}</b></td>
        <td>${matnEsc(s.holat_nomi)}</td>
        <td></td>
      </tr>`).join('');
    const sh = document.getElementById('shHolat');
    sh.textContent = shlar.length ? '' : 'Hali shartnoma tuzilmagan';
    sh.style.display = shlar.length ? 'none' : 'block';
  } catch (e) {
    ['kvHolat', 'shHolat'].forEach(id => {
      const el = document.getElementById(id);
      el.textContent = 'Yuklab bo\'lmadi: ' + e.message;
      el.style.display = 'block';
    });
  }
}

document.getElementById('hujjatYangila').addEventListener('click', hujjatlarYukla);

// Tushum jadvali va "Hujjatlarim" jadvalidagi tugmalar
function kvitansiyaTugmalari(e){
  const chiq = e.target.closest('[data-kv-chiqar]');
  if (chiq) {
    const t = tushumRoyxati.find(x => x.id === Number(chiq.dataset.kvChiqar));
    if (t) kvitansiyaChiqar(t);
    return;
  }
  const sms = e.target.closest('[data-kv-sms]');
  if (sms) kvitansiyaSms(Number(sms.dataset.kvSms), sms);
}
document.getElementById('tushTana').addEventListener('click', kvitansiyaTugmalari);
document.getElementById('kvTana').addEventListener('click', kvitansiyaTugmalari);

// ═══════ Kirish / chiqish ═══════
// ═══════ Sertifikatlar va ish haqi ═══════
// Ikkalasi ham admin panelidan kiritiladi (Xodim sahifasi); xodim bu yerda faqat o'zinikini o'qiydi.
const OY_NOMLARI = ['Yanvar','Fevral','Mart','Aprel','May','Iyun','Iyul','Avgust','Sentabr','Oktabr','Noyabr','Dekabr'];
function oyMatni(iso){
  const [y, o] = String(iso).split('-');
  return `${OY_NOMLARI[Number(o) - 1] || o} ${y}`;
}

const SERT_BELGI = {
  muddatsiz: { sinf: '',        ikon: 'ti-certificate',   matn: () => 'Muddatsiz' },
  amalda:    { sinf: '',        ikon: 'ti-certificate',   matn: (c) => 'Amal qiladi: ' + sanaFormat(c.amal_qiladi) + ' gacha' },
  yaqin:     { sinf: 'warn',    ikon: 'ti-alert-triangle', matn: (c) => 'Muddati yaqinlashmoqda: ' + sanaFormat(c.amal_qiladi) + ' gacha' },
  tugagan:   { sinf: 'tugagan', ikon: 'ti-x',             matn: (c) => 'Muddati tugagan: ' + sanaFormat(c.amal_qiladi) }
};

function sertifikatKarta(c){
  const b = SERT_BELGI[c.holat] || SERT_BELGI.amalda;
  const karta = document.createElement('div');
  karta.className = 'cert-card' + (b.sinf ? ' ' + b.sinf : '');
  const bosh = document.createElement('div');
  bosh.className = 'cc-head';
  const ikon = document.createElement('div');
  ikon.className = 'cc-icon';
  ikon.innerHTML = `<i class="ti ${b.ikon}"></i>`;
  const nom = document.createElement('h5');
  nom.textContent = c.nomi;
  bosh.append(ikon, nom);
  const holat = document.createElement('p');
  holat.textContent = b.matn(c);
  karta.append(bosh, holat);
  if (c.raqami) {
    const raqam = document.createElement('p');
    raqam.className = 'cc-raqam';
    raqam.textContent = '№ ' + c.raqami;
    karta.appendChild(raqam);
  }
  return karta;
}

async function sertifikatlarYukla(){
  const grid = document.getElementById('sertGrid');
  const holat = document.getElementById('sertHolat');
  try {
    const royxat = await apiSorov('/auth/xodim/sertifikatlar/');
    grid.innerHTML = '';
    document.getElementById('sertSoni').textContent = royxat.length ? `(${royxat.length} ta)` : '';
    if (!royxat.length) {
      holat.textContent = "Sertifikat kiritilmagan. Sertifikatlaringiz administrator tomonidan qo'shiladi.";
      holat.style.display = 'block';
      return;
    }
    royxat.forEach(c => grid.appendChild(sertifikatKarta(c)));
    holat.style.display = 'none';
  } catch (xato) {
    holat.textContent = "Yuklab bo'lmadi: " + xato.message;
    holat.style.display = 'block';
  }
}

async function ishHaqiYukla(){
  const holat = document.getElementById('oyligHolat');
  try {
    const royxat = await apiSorov('/auth/xodim/ish-haqi/');
    const tana = document.getElementById('oyligTana');
    tana.innerHTML = '';
    const bor = royxat.length > 0;
    document.getElementById('oyligXulosa').style.display = bor ? '' : 'none';
    document.getElementById('oyligJadvalBlok').style.display = bor ? '' : 'none';
    if (!bor) {
      document.getElementById('oyligOy').textContent = '';
      holat.textContent = "Ish haqi ma'lumoti hali kiritilmagan.";
      holat.style.display = 'block';
      return;
    }
    const oxirgi = royxat[0];                       // eng yangi oy birinchi
    document.getElementById('oyligOy').textContent = '(' + oyMatni(oxirgi.oy) + ')';
    document.getElementById('oyligAsosiy').textContent = pulMatni(oxirgi.asosiy) + " so'm";
    document.getElementById('oyligBonus').textContent = pulMatni(oxirgi.bonus) + " so'm";
    document.getElementById('oyligJami').textContent = pulMatni(oxirgi.jami) + " so'm";
    royxat.forEach(y => {
      const tr = document.createElement('tr');
      [oyMatni(y.oy), pulMatni(y.asosiy) + " so'm", pulMatni(y.bonus) + " so'm",
       pulMatni(y.jami) + " so'm", y.izoh || '—'].forEach(matn => {
        const td = document.createElement('td');
        td.textContent = matn;
        tr.appendChild(td);
      });
      tana.appendChild(tr);
    });
    holat.style.display = 'none';
  } catch (xato) {
    holat.textContent = "Yuklab bo'lmadi: " + xato.message;
    holat.style.display = 'block';
  }
}

// ═══════ Lavozimga qarab kabinet ═══════
// Kirish hamma uchun bir xil; menyu tuzilmasini server beradi (profil.kabinet,
// backend/apps/auth_app/kabinet_turlari.py). Server javobida bo'lmasa — to'liq «oddiy xodim» kabineti.
const BARCHA_BOLIMLAR = ['overview','tasks','history','certs','cash','docs','price','pay','team','settings'];
let kabinetTuri = 'oddiy';
let ruxsatliBolimlar = BARCHA_BOLIMLAR;
const bolimBormi = kalit => ruxsatliBolimlar.includes(kalit);

function bolimNomiTopish(lavozim, tur){
  if (tur === 'kadrlar') return "Kadrlar bo'limi";
  if (tur === 'qongiroq') return "Arizalar qabuli";
  if (tur === 'hujjat') return "Mehnat muhofazasi va hujjatlar";
  const l = (lavozim || '').toLowerCase();
  if (l.includes('metrolog')) return "Metrologiya bo'limi";
  if (l.includes('loyiha')) return "Loyihalash bo'limi";
  if (l.includes('servis')) return "Servis bo'limi";
  return "Montaj xizmati bo'limi";
}

function menyuQur(){
  const k = profil && profil.kabinet;
  kabinetTuri = (k && k.tur) || 'oddiy';
  ruxsatliBolimlar = (k && Array.isArray(k.bolimlar) && k.bolimlar.length) ? k.bolimlar : BARCHA_BOLIMLAR;
  document.body.classList.remove('kabinet-oddiy', 'kabinet-qongiroq', 'kabinet-hujjat', 'kabinet-kadrlar');
  document.body.classList.add('kabinet-' + kabinetTuri);
  document.getElementById('bolimNomi').textContent = bolimNomiTopish(profil && profil.lavozim, kabinetTuri);

  const nav = document.getElementById('sbNav');
  const tugmalar = {};
  nav.querySelectorAll('.sb-item[data-page]').forEach(b => { tugmalar[b.dataset.page] = b; b.hidden = true; });
  // Ruxsat etilganlar server bergan tartibda qayta joylanadi
  ruxsatliBolimlar.forEach(kalit => { const b = tugmalar[kalit]; if (b) { b.hidden = false; nav.appendChild(b); } });
  showPage('overview');
}

// ═══════ Kadrlar: davomat va kunlik hisobotlar ═══════
let kunSana = null;          // 'YYYY-MM-DD'; null = bugun (server hal qiladi)
let kunMalumot = null;

function bugunISO(){
  const d = new Date(), p = n => String(n).padStart(2, '0');
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}`;
}
function sanaSurish(iso, kun){
  const [y, o, k] = iso.split('-').map(Number);
  const d = new Date(y, o - 1, k + kun), p = n => String(n).padStart(2, '0');
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}`;
}
function katak(tr, matn, sinf){
  const td = document.createElement('td');
  td.textContent = matn;
  if (sinf) td.className = sinf;
  tr.appendChild(td);
  return td;
}
function belgi(matn, sinf){
  const s = document.createElement('span');
  s.className = 'tag ' + sinf;
  s.textContent = matn;
  return s;
}
function soatMatn(x){ return x ? soatMinut(x) : '—'; }

async function kunYukla(){
  if (!bolimBormi('kadr-davomat')) return;
  try {
    kunMalumot = await apiSorov('/kadrlar/kun/' + (kunSana ? '?sana=' + encodeURIComponent(kunSana) : ''));
    kunSana = kunMalumot.sana;
    kunChiz();
  } catch (xato) {
    ['davomatHolat', 'hisobotHolat'].forEach(id => {
      const el = document.getElementById(id);
      el.textContent = "Yuklab bo'lmadi: " + xato.message;
      el.style.display = 'block';
    });
    // Noto'g'ri sana tanlangan bo'lsa — bugunga qaytiladi
    if (kunSana) { kunSana = null; }
  }
}

function kunChiz(){
  const m = kunMalumot;
  document.querySelectorAll('.kun-sana').forEach(i => { i.value = m.sana; i.max = bugunISO(); });
  document.querySelectorAll('.kun-sarlavha').forEach(e => { e.textContent = '(' + sanaFormat(m.sana) + (m.bugun ? ', bugun' : '') + ')'; });
  document.querySelectorAll('.kun-keyingi').forEach(b => { b.disabled = m.bugun; });
  document.getElementById('eslatmaBtn').disabled = !m.bugun;

  // Xulosa raqamlari (bosh sahifa + davomat + hisobotlar)
  const idlar = { jami: 'kxJami', keldi: 'kxKeldi', ishda: 'kxIshda', kelmadi: 'kxKelmadi', hisobotsiz: 'kxHisobotsiz' };
  Object.keys(m.xulosa).forEach(k => {
    if (idlar[k]) document.getElementById(idlar[k]).textContent = m.xulosa[k];
    document.querySelectorAll(`[data-kx="${k}"]`).forEach(e => { e.textContent = m.xulosa[k]; });
  });
  davomatChiz();
  hisobotJadvalChiz();
}

function davomatChiz(){
  const tana = document.getElementById('davomatTana'), holat = document.getElementById('davomatHolat');
  const filtr = document.getElementById('davomatFiltr').value;
  const royxat = kunMalumot.xodimlar.filter(x => !filtr || x.holat === filtr);
  tana.innerHTML = '';
  royxat.forEach(x => {
    const tr = document.createElement('tr');
    katak(tr, x.ism);
    katak(tr, x.lavozim || '—', 'matn-keng');
    const h = document.createElement('td');
    h.className = 'matn-keng';
    h.appendChild(x.holat === 'ishda' ? belgi('Smenada', 'progress')
      : x.holat === 'keldi' ? belgi('Keldi', 'done') : belgi('Kelmadi', 'red'));
    if (x.qolda && x.qolda.holat === 'kelmadi' && x.qolda.sabab_nomi) h.appendChild(belgi(x.qolda.sabab_nomi, 'wait')).style.marginLeft = '6px';
    if (x.qolda) {
      const k = document.createElement('small');
      k.style.cssText = 'display:block;color:var(--text-muted);margin-top:4px;white-space:normal;max-width:210px;';
      k.textContent = "Qo'lda: " + (x.qolda.belgilagan || '—') + (x.qolda.izoh ? ' · ' + x.qolda.izoh : '');
      h.appendChild(k);
    }
    if (x.qarama) {
      const k = document.createElement('small');
      k.style.cssText = 'display:block;color:#b91c1c;margin-top:3px;white-space:normal;max-width:210px;';
      k.textContent = "Smena ochgan, lekin qo'lda «kelmadi» belgilangan";
      h.appendChild(k);
    }
    tr.appendChild(h);
    // Smena vaqti: «10:55 → davom etmoqda (1.9 soat)»
    katak(tr, x.smena_soni
      ? `${soatMatn(x.boshlandi)} → ${x.holat === 'ishda' ? 'hozir' : soatMatn(x.tugadi)} · ${x.soat} soat` : '—');
    // Qo'lda belgilash tugmalari (faqat Kadrlar mutaxassisi; administrator ko'rish rejimida o'chiq)
    const amal = document.createElement('td');
    const quti = document.createElement('div');
    quti.className = 'dav-tugma';
    const keldi = document.createElement('button');
    keldi.type = 'button'; keldi.className = 'mini-btn yashil tor'; keldi.textContent = 'Keldi';
    keldi.disabled = !!(x.qolda && x.qolda.holat === 'keldi');
    keldi.addEventListener('click', () => davomatBelgila(x, 'keldi'));
    const kelmadi = document.createElement('button');
    kelmadi.type = 'button'; kelmadi.className = 'mini-btn qizil tor'; kelmadi.textContent = 'Kelmadi';
    kelmadi.disabled = !!(x.qolda && x.qolda.holat === 'kelmadi');
    kelmadi.addEventListener('click', () => kelmadiOchish(x));
    quti.append(keldi, kelmadi);
    if (x.qolda) {
      const bekor = document.createElement('button');
      bekor.type = 'button'; bekor.className = 'mini-btn bosh tor'; bekor.textContent = '↺';
      bekor.title = "Qo'lda belgini bekor qilish (avtomatik holatga qaytadi)";
      bekor.addEventListener('click', () => davomatBelgila(x, 'tozala'));
      quti.appendChild(bekor);
    }
    amal.appendChild(quti);
    tr.appendChild(amal);
    tana.appendChild(tr);
  });
  holat.textContent = kunMalumot.xodimlar.length ? 'Bu filtr bo\'yicha xodim yo\'q.' : "Kuzatuvdagi faol xodim yo'q.";
  holat.style.display = royxat.length ? 'none' : 'block';
}

async function davomatBelgila(x, holat, sabab, izoh){
  try {
    await apiSorov('/kadrlar/davomat/', {
      method: 'POST',
      body: JSON.stringify({ xodim_id: x.id, holat, sana: kunMalumot.sana, sabab, izoh })
    });
    await kunYukla();
  } catch (xato) { alert('Belgilanmadi: ' + xato.message); }
}

let kelmadiXodim = null;
function kelmadiOchish(x){
  kelmadiXodim = x;
  document.getElementById('kdSarlavha').textContent = x.ism + ' — kelmadi';
  document.getElementById('kdSana').textContent = 'Sana: ' + sanaFormat(kunMalumot.sana);
  document.getElementById('kdSabab').value = (x.qolda && x.qolda.sabab) || 'sababsiz';
  document.getElementById('kdIzoh').value = (x.qolda && x.qolda.izoh) || '';
  document.getElementById('kdXato').classList.remove('show');
  const d = document.getElementById('kelmadiDialog');
  if (typeof d.showModal === 'function') d.showModal(); else d.setAttribute('open', '');
}
document.getElementById('kdYopish').addEventListener('click', () => document.getElementById('kelmadiDialog').close());
document.getElementById('kdSaqlash').addEventListener('click', async () => {
  const btn = document.getElementById('kdSaqlash'), xato = document.getElementById('kdXato');
  btn.disabled = true; xato.classList.remove('show');
  try {
    await apiSorov('/kadrlar/davomat/', {
      method: 'POST',
      body: JSON.stringify({ xodim_id: kelmadiXodim.id, holat: 'kelmadi', sana: kunMalumot.sana,
        sabab: document.getElementById('kdSabab').value, izoh: document.getElementById('kdIzoh').value.trim() })
    });
    document.getElementById('kelmadiDialog').close();
    await kunYukla();
  } catch (x) { xato.textContent = x.message; xato.classList.add('show'); }
  finally { btn.disabled = false; }
});

function hisobotJadvalChiz(){
  const tana = document.getElementById('hisobotTana'), holat = document.getElementById('hisobotHolat');
  // Hisobot bermaganlar tepada — Kadrlar avval ularga e'tibor beradi
  const royxat = [...kunMalumot.xodimlar].sort((a, b) => (!!a.hisobot) - (!!b.hisobot));
  tana.innerHTML = '';
  royxat.forEach(x => {
    const tr = document.createElement('tr');
    katak(tr, x.ism);
    katak(tr, x.hisobot ? x.hisobot.joy : '—', 'matn-keng');
    katak(tr, x.hisobot ? x.hisobot.ish : '—', 'matn-keng');
    const h = document.createElement('td');
    h.appendChild(x.hisobot ? belgi('Topshirgan', 'done') : belgi('Topshirmagan', 'red'));
    tr.appendChild(h);
    tana.appendChild(tr);
  });
  holat.textContent = "Kuzatuvdagi faol xodim yo'q.";
  holat.style.display = royxat.length ? 'none' : 'block';
}

document.querySelectorAll('.kun-oldingi').forEach(b => b.addEventListener('click', () => {
  if (kunSana) { kunSana = sanaSurish(kunSana, -1); kunYukla(); }
}));
document.querySelectorAll('.kun-keyingi').forEach(b => b.addEventListener('click', () => {
  if (kunSana && !(kunMalumot && kunMalumot.bugun)) { kunSana = sanaSurish(kunSana, 1); kunYukla(); }
}));
document.querySelectorAll('.kun-bugun').forEach(b => b.addEventListener('click', () => { kunSana = null; kunYukla(); }));
document.querySelectorAll('.kun-sana').forEach(i => i.addEventListener('change', () => {
  if (i.value) { kunSana = i.value; kunYukla(); }
}));
document.querySelectorAll('[data-kun-yangila]').forEach(b => b.addEventListener('click', kunYukla));
document.getElementById('davomatFiltr').addEventListener('change', () => { if (kunMalumot) davomatChiz(); });

document.getElementById('eslatmaBtn').addEventListener('click', async (e) => {
  const btn = e.currentTarget, xabar = document.getElementById('eslatmaXabar');
  btn.disabled = true;
  xabar.classList.add('show');
  try {
    const j = await apiSorov('/kadrlar/eslatma/', { method: 'POST' });
    xabar.style.color = 'var(--green)';
    xabar.textContent = j.yuborildi
      ? `${j.yuborildi} nafar xodimga eslatma yuborildi.`
      : "Hamma xodim bugungi hisobotni topshirgan — eslatma shart emas.";
  } catch (xato) {
    xabar.style.color = '';
    xabar.textContent = xato.message;
  } finally {
    btn.disabled = !(kunMalumot && kunMalumot.bugun);
  }
});

// ═══════ Kadrlar: xodimlar hujjatlari reestri ═══════
let kadrHujjatlar = null;

async function kadrHujjatYukla(){
  if (!bolimBormi('kadr-hujjat')) return;
  const holat = document.getElementById('hujjatHolat');
  try {
    kadrHujjatlar = await apiSorov('/kadrlar/hujjatlar/');
    kadrHujjatChiz();
  } catch (xato) {
    holat.textContent = "Yuklab bo'lmadi: " + xato.message;
    holat.style.display = 'block';
  }
}

function hujjatMuddat(h){
  return h.amal_qiladi ? 'gacha ' + sanaFormat(h.amal_qiladi) : 'muddatsiz';
}

function kadrHujjatChiz(){
  const d = kadrHujjatlar;
  const majburiy = d.turlar.filter(t => t.majburiy);
  document.getElementById('hujjatSoni').textContent = d.xodimlar.length ? `(${d.xodimlar.length} nafar xodim)` : '';

  // Matritsa: xodim × majburiy hujjat
  const bosh = document.getElementById('hujjatBosh');
  bosh.innerHTML = '';
  const trB = document.createElement('tr');
  const thX = document.createElement('th'); thX.textContent = 'Xodim'; trB.appendChild(thX);
  majburiy.forEach(t => { const th = document.createElement('th'); th.className = 'markaz'; th.textContent = t.nomi; trB.appendChild(th); });
  const thY = document.createElement('th'); thY.className = 'markaz'; thY.textContent = 'Yetishmaydi'; trB.appendChild(thY);
  bosh.appendChild(trB);

  const tana = document.getElementById('hujjatMatTana');
  tana.innerHTML = '';
  d.xodimlar.forEach(x => {
    const tr = document.createElement('tr');
    katak(tr, x.ism);
    majburiy.forEach(t => {
      const td = document.createElement('td');
      td.className = 'markaz';
      const royxat = x.hujjatlar.filter(h => h.turi === t.kalit);
      if (!royxat.length) { td.innerHTML = '<span class="hq-yoq">—</span>'; }
      else {
        const amalda = royxat.some(h => h.holat === 'amalda' || h.holat === 'muddatsiz');
        const yaqin = royxat.some(h => h.holat === 'yaqin');
        const sinf = amalda ? 'hq-ok' : (yaqin ? 'hq-yaqin' : 'hq-tugagan');
        const s = document.createElement('span');
        s.className = sinf;
        s.textContent = '✓';
        const h0 = royxat[royxat.length - 1];
        s.title = [h0.raqami ? '№ ' + h0.raqami : '', hujjatMuddat(h0)].filter(Boolean).join(', ');
        td.appendChild(s);
      }
      tr.appendChild(td);
    });
    katak(tr, x.yetishmaydi.length ? x.yetishmaydi.length + ' ta' : 'to\'liq', 'markaz' + (x.yetishmaydi.length ? ' qizil-qator' : ''));
    tana.appendChild(tr);
  });
  const holat = document.getElementById('hujjatHolat');
  holat.textContent = "Kuzatuvdagi faol xodim yo'q.";
  holat.style.display = d.xodimlar.length ? 'none' : 'block';

  // Forma tanlovlari (tanlov saqlanib qoladi)
  const xSel = document.getElementById('hfXodim'), tSel = document.getElementById('hfTuri');
  const xQiymat = xSel.value, tQiymat = tSel.value;
  xSel.innerHTML = ''; tSel.innerHTML = '';
  d.xodimlar.forEach(x => { const o = document.createElement('option'); o.value = x.id; o.textContent = x.ism; xSel.appendChild(o); });
  d.turlar.forEach(t => { const o = document.createElement('option'); o.value = t.kalit; o.textContent = t.nomi; tSel.appendChild(o); });
  if (xQiymat) xSel.value = xQiymat;
  if (tQiymat) tSel.value = tQiymat;
  if (!document.getElementById('hfSana').value) document.getElementById('hfSana').value = bugunISO();

  // Kiritilgan hujjatlar ro'yxati
  const nom = Object.fromEntries(d.turlar.map(t => [t.kalit, t.nomi]));
  const rTana = document.getElementById('hujjatRoyxatTana');
  rTana.innerHTML = '';
  let jami = 0;
  d.xodimlar.forEach(x => x.hujjatlar.forEach(h => {
    jami++;
    const tr = document.createElement('tr');
    katak(tr, x.ism);
    katak(tr, nom[h.turi] || h.turi);
    katak(tr, h.raqami || '—');
    katak(tr, sanaFormat(h.sana));
    const m = document.createElement('td');
    m.appendChild(h.holat === 'tugagan' ? belgi('Muddati o\'tgan', 'red')
      : h.holat === 'yaqin' ? belgi(hujjatMuddat(h), 'wait')
      : document.createTextNode(hujjatMuddat(h)));
    tr.appendChild(m);
    katak(tr, h.izoh || '—');
    const amal = document.createElement('td');
    const b = document.createElement('button');
    b.type = 'button'; b.className = 'mini-btn qizil'; b.textContent = "O'chirish";
    b.addEventListener('click', () => kadrHujjatOchir(h.id, x.ism, nom[h.turi] || h.turi));
    amal.appendChild(b);
    tr.appendChild(amal);
    rTana.appendChild(tr);
  }));
  document.getElementById('hujjatRoyxatHolat').style.display = jami ? 'none' : 'block';
}

async function kadrHujjatOchir(id, ism, turi){
  if (!confirm(`${ism}: «${turi}» yozuvi o'chirilsinmi?`)) return;
  try {
    await apiSorov('/kadrlar/hujjatlar/' + id + '/', { method: 'DELETE' });
    kadrHujjatYukla();
  } catch (xato) { alert("O'chirilmadi: " + xato.message); }
}

document.getElementById('hujjatYangilaBtn').addEventListener('click', kadrHujjatYukla);
document.getElementById('hujjatForma').addEventListener('submit', async (e) => {
  e.preventDefault();
  const btn = document.getElementById('hfBtn'), xato = document.getElementById('hfXato');
  xato.classList.remove('show');
  btn.disabled = true;
  try {
    await apiSorov('/kadrlar/hujjatlar/', {
      method: 'POST',
      body: JSON.stringify({
        xodim: document.getElementById('hfXodim').value,
        turi: document.getElementById('hfTuri').value,
        raqami: document.getElementById('hfRaqam').value.trim(),
        sana: document.getElementById('hfSana').value,
        amal_qiladi: document.getElementById('hfAmal').value || null,
        izoh: document.getElementById('hfIzoh').value.trim()
      })
    });
    ['hfRaqam', 'hfAmal', 'hfIzoh'].forEach(id => { document.getElementById(id).value = ''; });
    await kadrHujjatYukla();
  } catch (x) {
    xato.textContent = x.message;
    xato.classList.add('show');
  } finally {
    btn.disabled = false;
  }
});

// ═══════ Xodimning o'z kunlik hisoboti (Kadrlar mutaxassisidan boshqa hamma) ═══════
function hisobotBelgiChiz(h){
  const b = document.getElementById('hisobotBelgi');
  b.className = 'tag ' + (h ? 'done' : 'wait');
  b.textContent = h ? 'Topshirildi' : 'Topshirilmagan';
  document.getElementById('hisobotBtn').textContent = h ? 'Hisobotni yangilash' : 'Hisobotni saqlash';
}
async function hisobotYukla(){
  try {
    const j = await apiSorov('/kadrlar/hisobot/');
    if (j.hisobot) {
      document.getElementById('hisobotJoy').value = j.hisobot.joy;
      document.getElementById('hisobotIsh').value = j.hisobot.ish;
    }
    hisobotBelgiChiz(j.hisobot);
  } catch (e) { /* karta bo'sh holda qoladi — saqlash baribir ishlaydi */ }
}
document.getElementById('hisobotBtn').addEventListener('click', async (e) => {
  const btn = e.currentTarget, xato = document.getElementById('hisobotXato');
  xato.classList.remove('show');
  btn.disabled = true;
  try {
    const j = await apiSorov('/kadrlar/hisobot/', {
      method: 'POST',
      body: JSON.stringify({
        joy: document.getElementById('hisobotJoy').value.trim(),
        ish: document.getElementById('hisobotIsh').value.trim()
      })
    });
    hisobotBelgiChiz(j.hisobot);
  } catch (x) {
    xato.textContent = x.message;
    xato.classList.add('show');
  } finally {
    btn.disabled = false;
  }
});

// ═══════ Kadrlar: xodimlardan pul qabul qilish ═══════
async function kadrTushumYukla(jim){
  if (!bolimBormi('kadr-tushum')) return;
  const holat = document.getElementById('ktHolat');
  const filtr = document.getElementById('ktFiltr').value;
  try {
    const d = await apiSorov('/tushum/admin/' + (filtr ? '?holat=' + encodeURIComponent(filtr) : ''));
    kadrTushumChiz(d);
  } catch (xato) {
    if (jim) return;          // avtomatik yangilashda xato ko'rsatilmaydi (keyingisida qayta uriniladi)
    holat.textContent = "Yuklab bo'lmadi: " + xato.message;
    holat.style.display = 'block';
  }
}

function kadrTushumChiz(d){
  const jami = (arr, k) => arr.reduce((a, x) => a + (Number(x[k]) || 0), 0);
  const kutilmoqda = jami(d.xodimlar, 'kutilmoqda_summa');
  const oyQabul = Object.values(d.tarmoq_jami || {}).reduce((a, t) => a + (Number(t.oy_qabul) || 0), 0);
  document.getElementById('ktKutilmoqda').textContent = pulMatni(kutilmoqda);
  document.getElementById('ktSoni').textContent = jami(d.xodimlar, 'kutilmoqda_soni');
  document.getElementById('ktOy').textContent = pulMatni(oyQabul);
  document.getElementById('kxTushum').textContent = pulMatni(kutilmoqda);
  const kutSoni = jami(d.xodimlar, 'kutilmoqda_soni');
  const sonBelgi = document.getElementById('ktBelgi');
  sonBelgi.textContent = kutSoni > 99 ? '99+' : kutSoni;
  sonBelgi.hidden = !kutSoni;

  // Xodimlar bo'yicha: eng ko'p topshirmagani tepada
  const xTana = document.getElementById('ktXodimTana');
  xTana.innerHTML = '';
  const qarzdorlar = [...d.xodimlar].sort((a, b) => b.kutilmoqda_summa - a.kutilmoqda_summa);
  qarzdorlar.forEach(x => {
    const tr = document.createElement('tr');
    katak(tr, x.ism);
    katak(tr, x.kutilmoqda_summa ? pulMatni(x.kutilmoqda_summa) + " so'm" : '—', x.kutilmoqda_summa ? 'qizil-qator' : '');
    katak(tr, x.kutilmoqda_soni || '—');
    katak(tr, x.oy_summa ? pulMatni(x.oy_summa) + " so'm" : '—');
    xTana.appendChild(tr);
  });
  const xh = document.getElementById('ktXodimHolat');
  xh.textContent = "Hali birorta xodim pul kiritmagan.";
  xh.style.display = qarzdorlar.length ? 'none' : 'block';

  // Yozuvlar
  const tana = document.getElementById('ktTana');
  tana.innerHTML = '';
  d.yozuvlar.forEach(t => {
    const tr = document.createElement('tr');
    katak(tr, sanaVaqt(t.yaratilgan) + ' ' + soatMinut(t.yaratilgan));
    katak(tr, t.xodim_ism);
    katak(tr, pulMatni(t.summa) + " so'm");
    katak(tr, t.usul_nomi);
    const nima = [t.buyurtma_nomi || t.ish_turi || t.tarmoq_nomi, t.izoh].filter(Boolean).join(' · ');
    katak(tr, nima || '—', 'matn-keng');
    const h = document.createElement('td');
    h.appendChild(t.holat === 'qabul' ? belgi('Qabul qilindi', 'done')
      : t.holat === 'rad' ? belgi('Rad etildi', 'red') : belgi('Kutilmoqda', 'wait'));
    if (t.holat === 'rad' && t.rad_sababi) { const k = document.createElement('small'); k.textContent = ' ' + t.rad_sababi; h.appendChild(k); }
    tr.appendChild(h);
    const amal = document.createElement('td');
    amal.className = 'amal-tugma';
    if (t.holat === 'kutilmoqda') {
      const q = document.createElement('button');
      q.type = 'button'; q.className = 'mini-btn yashil'; q.textContent = 'Qabul qilish';
      q.addEventListener('click', () => kadrTushumHal(t, 'qabul'));
      const r = document.createElement('button');
      r.type = 'button'; r.className = 'mini-btn qizil'; r.style.marginLeft = '6px'; r.textContent = 'Rad etish';
      r.addEventListener('click', () => kadrTushumHal(t, 'rad'));
      amal.append(q, r);
    }
    tr.appendChild(amal);
    tana.appendChild(tr);
  });
  const holat = document.getElementById('ktHolat');
  holat.textContent = "Bu bo'yicha yozuv yo'q.";
  holat.style.display = d.yozuvlar.length ? 'none' : 'block';
}

async function kadrTushumHal(t, amal){
  const nom = `${t.xodim_ism}: ${pulMatni(t.summa)} so'm`;
  try {
    if (amal === 'qabul') {
      if (!confirm(`${nom} — pul qo'lingizga topshirildimi? Qabul qilinsinmi?`)) return;
      await apiSorov('/tushum/' + t.id + '/qabul/', { method: 'POST' });
    } else {
      const sabab = (prompt(`${nom}\nRad etish sababi:`) || '').trim();
      if (!sabab) return;
      await apiSorov('/tushum/' + t.id + '/rad/', { method: 'POST', body: JSON.stringify({ sabab }) });
    }
  } catch (xato) { alert('Bajarilmadi: ' + xato.message); }
  kadrTushumYukla();
}

document.getElementById('ktFiltr').addEventListener('change', () => kadrTushumYukla());
document.getElementById('tushumKadrYangila').addEventListener('click', () => kadrTushumYukla());

// Xodimlar kiritgan yangi tushumlar o'zi paydo bo'lishi uchun ro'yxat har 20 soniyada jim yangilanadi
let kadrTushumTimer = null;
function kadrTushumKuzat(){
  clearInterval(kadrTushumTimer);
  kadrTushumTimer = setInterval(() => { if (!document.hidden) kadrTushumYukla(true); }, 20000);
}

// ═══════ Operatorlar: qo'ng'iroq arizalari ═══════
let arizaMalumot = null;

async function arizalarYukla(){
  if (!bolimBormi('op-arizalar')) return;
  const holat = document.getElementById('arizaHolat');
  const q = document.getElementById('arizaQidir').value.trim();
  try {
    arizaMalumot = await apiSorov('/buyurtmalar/operator/arizalar/?holat=' + encodeURIComponent(document.getElementById('arizaFiltr').value)
      + (q ? '&q=' + encodeURIComponent(q) : ''));
    arizalarChiz();
  } catch (xato) {
    holat.textContent = "Yuklab bo'lmadi: " + xato.message;
    holat.style.display = 'block';
  }
}

function xodimOptionlari(sel, tanlangan, birinchi){
  sel.innerHTML = '';
  const bosh = document.createElement('option');
  bosh.value = ''; bosh.textContent = birinchi;
  sel.appendChild(bosh);
  arizaMalumot.xodimlar.forEach(x => {
    const o = document.createElement('option');
    o.value = x.id;
    o.textContent = `${x.ism} (${x.faol_soni} ta faol)`;
    sel.appendChild(o);
  });
  sel.value = tanlangan ? String(tanlangan) : '';
}

function arizalarChiz(){
  const d = arizaMalumot;
  Object.keys(d.xulosa).forEach(k => {
    document.querySelectorAll(`[data-ox="${k}"]`).forEach(e => { e.textContent = d.xulosa[k]; });
  });
  document.getElementById('arizaSoni').textContent = d.arizalar.length ? `(${d.arizalar.length} ta)` : '';

  // Ariza formasidagi xodim tanlovi (tanlov saqlanadi)
  const fSel = document.getElementById('opXodim');
  xodimOptionlari(fSel, fSel.value, "— keyin biriktiraman —");

  const tana = document.getElementById('arizaTana');
  tana.innerHTML = '';
  d.arizalar.forEach(a => {
    const tr = document.createElement('tr');
    katak(tr, '#' + a.id);
    katak(tr, sanaVaqt(a.yaratilgan));
    const m = katak(tr, a.mijoz_ism || '—', 'matn-keng');
    const tel = document.createElement('small'); tel.textContent = a.mijoz_telefon; m.appendChild(tel);
    const x = katak(tr, a.xizmat_nomi, 'matn-keng');
    { const s = document.createElement('small'); s.textContent = a.tarmoq === 'ulgurji' ? 'Tashkilot (ulgurji)' : 'Aholi'; x.appendChild(s); }
    const man = katak(tr, a.manzil || '—', 'matn-keng');
    if (a.tuman) { const s = document.createElement('small'); s.textContent = a.tuman; man.appendChild(s); }
    if (a.tavsif) { const s = document.createElement('small'); s.textContent = a.tavsif; man.appendChild(s); }
    if (a.joy_bor) { const s = document.createElement('small'); s.innerHTML = '<i class="ti ti-map-pin"></i> xaritada belgilangan'; man.appendChild(s); }

    const h = document.createElement('td');
    h.appendChild(a.holat === 'bajarildi' ? belgi('Bajarildi', 'done')
      : a.holat === 'bekor' ? belgi('Bekor qilindi', 'plan')
      : a.holat === 'bajarilmoqda' ? belgi('Jarayonda', 'progress')
      : a.holat === 'qabul' ? belgi('Xodim qabul qildi', 'progress')
      : a.xodim_id ? belgi('Xodimga berilgan', 'wait') : belgi("Xodimi yo'q", 'red'));
    if (a.kechikkan) h.appendChild(belgi('Kechikkan', 'kech'));
    tr.appendChild(h);

    const amal = document.createElement('td');
    amal.className = 'amal-keng';
    if (a.holat === 'yangi' || a.holat === 'qabul') {
      const quti = document.createElement('div');
      quti.className = 'op-tayinla';
      const sel = document.createElement('select');
      sel.className = 'f-select';
      sel.setAttribute('aria-label', '#' + a.id + ' uchun mutaxassis');
      xodimOptionlari(sel, a.xodim_id, '— tanlang —');
      const b = document.createElement('button');
      b.type = 'button'; b.className = 'mini-btn asosiy'; b.textContent = a.xodim_id ? 'Almashtirish' : 'Biriktirish';
      b.addEventListener('click', () => arizaTayinla(a.id, sel.value, b));
      quti.append(sel, b);
      const yaqin = document.createElement('button');
      yaqin.type = 'button'; yaqin.className = 'mini-btn yashil'; yaqin.innerHTML = '<i class="ti ti-map-pin"></i> Yaqin xodim';
      yaqin.addEventListener('click', () => yaqinOchish(a));
      quti.appendChild(yaqin);
      amal.appendChild(quti);
    } else {
      amal.textContent = a.xodim_ism || '—';
      if (a.holat === 'bajarildi' && a.natija) { const s = document.createElement('small'); s.style.display = 'block'; s.textContent = a.natija; amal.appendChild(s); }
    }
    tr.appendChild(amal);
    tana.appendChild(tr);
  });
  const holat = document.getElementById('arizaHolat');
  holat.textContent = "Bu bo'yicha ariza yo'q.";
  holat.style.display = d.arizalar.length ? 'none' : 'block';
}

async function arizaTayinla(id, xodimId, btn){
  const xato = document.getElementById('tayinXato');
  xato.classList.remove('show');
  if (!xodimId) { xato.textContent = 'Avval mutaxassisni tanlang.'; xato.classList.add('show'); return; }
  btn.disabled = true;
  try {
    await apiSorov('/buyurtmalar/operator/arizalar/' + id + '/tayinlash/', {
      method: 'POST', body: JSON.stringify({ xodim_id: xodimId })
    });
    await arizalarYukla();
  } catch (x) {
    xato.textContent = '#' + id + ': ' + x.message;
    xato.classList.add('show');
    btn.disabled = false;
  }
}

document.getElementById('arizaForma').addEventListener('submit', async (e) => {
  e.preventDefault();
  const btn = document.getElementById('arizaBtn'), xato = document.getElementById('arizaXato');
  xato.classList.remove('show');
  xato.style.color = '';
  btn.disabled = true;
  try {
    const j = await apiSorov('/buyurtmalar/operator/arizalar/', {
      method: 'POST',
      body: JSON.stringify({
        mijoz_ism: document.getElementById('opIsm').value.trim(),
        mijoz_telefon: document.getElementById('opTelefon').value.trim(),
        xizmat: document.getElementById('opXizmat').value,
        tarmoq: document.getElementById('opTarmoq').value,
        tuman: document.getElementById('opTuman').value.trim(),
        manzil: document.getElementById('opManzil').value.trim(),
        tavsif: document.getElementById('opTavsif').value.trim(),
        xodim_id: document.getElementById('opXodim').value || undefined,
        lat: opJoy ? opJoy.lat : undefined,
        lng: opJoy ? opJoy.lng : undefined,
        yaqin_yuborish: (opJoy && document.getElementById('opYaqinYubor').checked) ? true : undefined
      })
    });
    ['opIsm', 'opTelefon', 'opTuman', 'opManzil', 'opTavsif'].forEach(id => { document.getElementById(id).value = ''; });
    document.getElementById('opXodim').value = '';
    document.getElementById('opJoyTozala').click();
    xato.style.color = 'var(--green)';
    let oxiri = j.xodim_ism ? `, ${j.xodim_ism}ga biriktirildi.` : '. Endi mutaxassisga biriktiring.';
    if (j.yaqin) oxiri = j.yaqin.yuborildi ? `, eng yaqin xodim ${j.yaqin.xodim.ism}ga yuborildi (${j.yaqin.masofa_km} km).`
      : `. Eng yaqin xodimga yuborilmadi: ${j.yaqin.sabab}. «Yaqin xodim» tugmasi bilan qo'lda yuboring.`;
    xato.textContent = `Ariza #${j.id} qabul qilindi` + oxiri;
    xato.classList.add('show');
    await arizalarYukla();
  } catch (x) {
    xato.textContent = x.message;
    xato.classList.add('show');
  } finally {
    btn.disabled = false;
  }
});
document.querySelectorAll('[data-arizalar-yangila]').forEach(b => b.addEventListener('click', arizalarYukla));
document.getElementById('arizaFiltr').addEventListener('change', arizalarYukla);
let arizaQidirTimer = null;
document.getElementById('arizaQidir').addEventListener('input', () => {
  clearTimeout(arizaQidirTimer);
  arizaQidirTimer = setTimeout(arizalarYukla, 350);
});

// ═══════ Ariza joylashuvi va eng yaqin xodim ═══════
// Xodimning koordinatasi operatorga berilmaydi — faqat masofa (km). Server: buyurtmalar/operator.py
const BUXORO = [39.7747, 64.4286];
function xaritaYarat(elId){
  const x = L.map(elId, { zoomControl: true }).setView(BUXORO, 11);
  L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', { maxZoom: 19, attribution: '© OpenStreetMap' }).addTo(x);
  return x;
}

// — Ariza formasidagi xarita —
let opXarita = null, opBelgi = null, opJoy = null;     // opJoy = {lat, lng} yoki null
let opJoyManba = '';                                   // '' | 'avto' (manzildan topilgan) | 'qolda' (operator xaritani bosgan)
function opJoyChiz(){
  const matn = document.getElementById('opJoyMatn'), chek = document.getElementById('opYaqinYubor');
  if (opJoy) {
    // Joy birinchi marta tanlanganda «eng yaqin xodimga yuborish» o'zi yoqiladi (operator o'chirib qo'ysa — tegilmaydi)
    if (chek.disabled && chek.dataset.qolda !== '1') chek.checked = true;
    chek.disabled = false;
    matn.textContent = `Joy belgilandi (${opJoy.lat.toFixed(5)}, ${opJoy.lng.toFixed(5)}). ` + (chek.checked
      ? "Ariza saqlanishi bilan eng yaqin xodimga o'zi yuboriladi. Joyni o'zgartirish uchun xaritani qayta bosing."
      : "Joyni o'zgartirish uchun xaritani qayta bosing.");
  } else {
    matn.textContent = "Joy belgilanmagan. Mijoz aytgan manzilni xaritadan toping va bosing — ariza o'zi eng yaqin xodimga yuboriladi.";
    chek.disabled = true; chek.checked = false; chek.dataset.qolda = '';
  }
}
function opXaritaTayyor(){
  if (typeof L === 'undefined') { document.getElementById('opJoyMatn').textContent = "Xarita yuklanmadi (internet kerak). Ariza joysiz saqlanadi."; return; }
  if (!opXarita) {
    opXarita = xaritaYarat('opXarita');
    opXarita.on('click', e => {
      opJoyQoy(e.latlng.lat, e.latlng.lng, 'qolda');
      document.getElementById('opGeoVariant').style.display = 'none';
      opGeoXabar("Joy xaritadan qo'lda belgilandi.");
    });
  }
  setTimeout(() => opXarita.invalidateSize(), 50);      // sahifa yashirin bo'lganda o'lchami noto'g'ri bo'ladi
}
document.getElementById('opYaqinYubor').addEventListener('change', e => { e.target.dataset.qolda = '1'; opJoyChiz(); });
document.getElementById('opJoyTozala').addEventListener('click', () => {
  opJoy = null; opJoyManba = '';
  if (opBelgi && opXarita) { opXarita.removeLayer(opBelgi); opBelgi = null; }
  document.getElementById('opGeoVariant').style.display = 'none';
  opGeoXabar('');
  opJoyChiz();
});
opJoyChiz();

// — Manzil yozilganda xarita o'zi joyni topadi (server: OpenStreetMap Nominatim, faqat manzil matni ketadi) —
function opGeoXabar(matn, xato){
  const e = document.getElementById('opGeoMatn');
  e.textContent = matn || '';
  e.style.color = xato ? '#b91c1c' : 'var(--text-muted)';
}
function opJoyQoy(lat, lng, manba, zoom){
  if (!opXarita) return;
  opJoy = { lat, lng }; opJoyManba = manba;
  if (opBelgi) opBelgi.setLatLng([lat, lng]); else opBelgi = L.marker([lat, lng]).addTo(opXarita);
  if (zoom) opXarita.setView([lat, lng], zoom);
  opJoyChiz();
}
let opGeoSeq = 0, opGeoTimer = null, opGeoNatijalar = [];

async function opManzilQidir(majbur){
  const manzil = document.getElementById('opManzil').value.trim();
  if (manzil.length < 3) return;
  if (opJoyManba === 'qolda' && !majbur) return;           // operator o'zi belgilagan joyni manzil yozuvi buzmasin
  if (typeof L === 'undefined') return;
  opXaritaTayyor();
  const seq = ++opGeoSeq;
  opGeoXabar('Manzil xaritadan qidirilmoqda...');
  try {
    const d = await apiSorov('/buyurtmalar/operator/geokod/?manzil=' + encodeURIComponent(manzil)
      + '&tuman=' + encodeURIComponent(document.getElementById('opTuman').value.trim()));
    if (seq !== opGeoSeq) return;                          // yangi so'rov ketgan — eskisi e'tiborsiz
    opGeoNatijalar = d.natijalar;
    const sel = document.getElementById('opGeoVariant');
    sel.innerHTML = '';
    d.natijalar.forEach((n, i) => { const o = document.createElement('option'); o.value = i; o.textContent = n.nomi; sel.appendChild(o); });
    sel.style.display = d.natijalar.length > 1 ? 'block' : 'none';
    const n = d.natijalar[0];
    if (d.aniqlik === 'manzil') {
      opJoyQoy(n.lat, n.lng, 'avto', 17);
      opGeoXabar('Manzil xaritadan topildi: ' + n.nomi + (d.natijalar.length > 1 ? " (boshqa variant bo'lsa, ro'yxatdan tanlang)" : ''));
    } else if (d.aniqlik === 'taxminiy') {
      opJoyQoy(n.lat, n.lng, 'avto', 16);
      opGeoXabar("Aniq uy topilmadi, shu nomli yaqin joy belgilandi: " + n.nomi + ". Noto'g'ri bo'lsa, xaritada to'g'ri joyni bosing.");
    } else if (d.aniqlik === 'hudud') {
      // Aniq joy yo'q: faqat xarita tuman markaziga o'tadi, belgi QO'YILMAYDI (xato joyga xodim yuborilmasin)
      opXarita.setView([n.lat, n.lng], 13);
      opGeoXabar("Aniq manzil topilmadi — tuman markazi ko'rsatildi. Mijoz uyini xaritada bosib belgilang.", true);
    } else {
      opGeoXabar("Manzil xaritadan topilmadi. Joyni xaritada qo'lda bosib belgilang.", true);
    }
  } catch (x) {
    if (seq === opGeoSeq) opGeoXabar(x.message, true);
  }
}
['opManzil', 'opTuman'].forEach(id => document.getElementById(id).addEventListener('input', () => {
  clearTimeout(opGeoTimer);
  opGeoTimer = setTimeout(() => opManzilQidir(false), 1000);       // yozib bo'lgach (1 soniya) qidiriladi
}));
document.getElementById('opGeoBtn').addEventListener('click', () => opManzilQidir(true));
document.getElementById('opGeoVariant').addEventListener('change', e => {
  const n = opGeoNatijalar[+e.target.value];
  if (n) { opJoyQoy(n.lat, n.lng, 'avto', 17); opGeoXabar('Tanlandi: ' + n.nomi); }
});

// — «Yaqin xodim» oynasi —
const yaqinDialog = document.getElementById('yaqinDialog');
let yqAriza = null, yqXarita = null, yqBelgi = null;

function yqVaqt(soniya){
  if (soniya < 90) return 'hozirgina';
  return Math.round(soniya / 60) + ' daqiqa oldin';
}
function yqXabar(matn, xato){
  const e = document.getElementById('yqXabar');
  e.textContent = matn || '';
  e.style.color = xato ? '#b91c1c' : 'var(--green)';
  e.style.display = matn ? 'block' : 'none';
}

function yaqinOchish(ariza){
  yqAriza = ariza;
  document.getElementById('yqSarlavha').textContent = `Ariza #${ariza.id} — eng yaqin xodim`;
  document.getElementById('yqManzil').textContent = [ariza.tuman, ariza.manzil].filter(Boolean).join(', ') || '—';
  yqXabar('');
  document.getElementById('yqRoyxat').innerHTML = '';
  document.getElementById('yqNomalum').textContent = '';
  document.getElementById('yqEngYaqin').disabled = true;
  if (typeof yaqinDialog.showModal === 'function') yaqinDialog.showModal(); else yaqinDialog.setAttribute('open', '');
  if (typeof L !== 'undefined') {
    if (!yqXarita) {
      yqXarita = xaritaYarat('yqXarita');
      yqXarita.on('click', e => yqJoyBelgila(e.latlng.lat, e.latlng.lng));
    }
    setTimeout(() => {
      yqXarita.invalidateSize();
      if (ariza.joy_bor) yqMarker(ariza.lat, ariza.lng, true);
      else if (yqBelgi) { yqXarita.removeLayer(yqBelgi); yqBelgi = null; }
    }, 80);
  }
  if (ariza.joy_bor) yqYukla();
  else yqXabar("Arizaning joyi belgilanmagan. Xaritadan mijoz manzilini toping va bosing.", true);
}

function yqMarker(lat, lng, markazga){
  if (!yqXarita) return;
  if (yqBelgi) yqBelgi.setLatLng([lat, lng]); else yqBelgi = L.marker([lat, lng]).addTo(yqXarita);
  if (markazga) yqXarita.setView([lat, lng], 13);
}

async function yqJoyBelgila(lat, lng){
  if (!yqAriza) return;
  try {
    const a = await apiSorov('/buyurtmalar/operator/arizalar/' + yqAriza.id + '/joy/', {
      method: 'POST', body: JSON.stringify({ lat, lng })
    });
    yqAriza = a;
    yqMarker(a.lat, a.lng, false);
    yqXabar('');
    await yqYukla();
    arizalarYukla();
  } catch (x) { yqXabar(x.message, true); }
}

async function yqYukla(){
  const royxat = document.getElementById('yqRoyxat');
  royxat.innerHTML = '<p class="bosh-holat">Qidirilmoqda...</p>';
  try {
    const d = await apiSorov('/buyurtmalar/operator/arizalar/' + yqAriza.id + '/yaqin/');
    royxat.innerHTML = '';
    const tugma = document.getElementById('yqEngYaqin');
    tugma.disabled = !d.nomzodlar.some(n => !n.band);
    if (!d.nomzodlar.length) {
      const p = document.createElement('p');
      p.className = 'bosh-holat';
      p.textContent = `Hozir joylashuvi aniq xodim yo'q (oxirgi ${d.yangilik_daqiqa} daqiqada nuqta yuborgan smenadagilar hisobga olinadi).`;
      royxat.appendChild(p);
    }
    d.nomzodlar.forEach((n, i) => {
      const qator = document.createElement('div');
      qator.className = 'yq-qator' + (i === 0 && !n.band ? ' eng' : '');
      const chap = document.createElement('div');
      const ism = document.createElement('b'); ism.textContent = n.ism;
      const kichik = document.createElement('small');
      kichik.textContent = `${n.lavozim || 'Xodim'} · ${n.faol_soni} ta faol vazifa · ${yqVaqt(n.oxirgi_soniya)}`;
      chap.append(ism, kichik);
      const km = document.createElement('div');
      km.className = 'yq-km'; km.textContent = n.masofa_km + ' km';
      const amal = document.createElement('div');
      if (n.band) amal.appendChild(belgi('Band', 'wait'));
      const b = document.createElement('button');
      b.type = 'button'; b.className = 'mini-btn asosiy'; b.style.marginLeft = '8px'; b.textContent = 'Yuborish';
      b.addEventListener('click', () => yqYubor(n.id, b));
      amal.appendChild(b);
      qator.append(chap, km, amal);
      royxat.appendChild(qator);
    });
    // Smenada bo'lmaganlar faqat son bilan; joylashuvi eskirganlar (smenada, lekin signal yo'q) ism bilan ko'rsatiladi
    const smenadaEmas = d.nomalum.filter(x => x.sabab === 'Smenada emas').length;
    const eskirgan = d.nomalum.filter(x => x.sabab !== 'Smenada emas');
    const qismlar = [];
    if (eskirgan.length) qismlar.push("Smenada, lekin joylashuvi yangilanmagan: " + eskirgan.map(x => x.ism).join(', '));
    if (smenadaEmas) qismlar.push("Smenada emas: " + smenadaEmas + " nafar xodim");
    document.getElementById('yqNomalum').textContent = qismlar.join('. ');
  } catch (x) {
    royxat.innerHTML = '';
    yqXabar(x.message, true);
  }
}

async function yqYubor(xodimId, btn){
  yqXabar('');
  const hammasi = [...document.querySelectorAll('#yaqinDialog button')];
  hammasi.forEach(b => { b.disabled = true; });
  try {
    const j = await apiSorov('/buyurtmalar/operator/arizalar/' + yqAriza.id + '/yaqin-yuborish/', {
      method: 'POST', body: JSON.stringify(xodimId ? { xodim_id: xodimId } : {})
    });
    yaqinDialog.close();
    const e = document.getElementById('tayinXato');
    e.style.color = 'var(--green)';
    e.textContent = `Ariza #${yqAriza.id} — ${j.xodim.ism}ga yuborildi (${j.masofa_km} km).`;
    e.classList.add('show');
    arizalarYukla();
  } catch (x) {
    yqXabar(x.message, true);
    hammasi.forEach(b => { b.disabled = false; });
  }
}

document.getElementById('yqEngYaqin').addEventListener('click', () => yqYubor(null));
document.getElementById('yqYopish').addEventListener('click', () => yaqinDialog.close());

// ═══════ Hujjatlar bilan ishlovchi xodim: mijozlardan kelgan ishlar, hujjat tayyorlash va yuborish ═══════
// Server: backend/apps/hujjatlar/ish.py
let ishMalumot = null, joriyIsh = null;

async function ishlarYukla(){
  if (!bolimBormi('hj-ishlar')) return;
  const holat = document.getElementById('ishHolat');
  const q = document.getElementById('ishQidir').value.trim();
  const tur = document.getElementById('ishTur').value;
  try {
    ishMalumot = await apiSorov('/hujjatlar/ish/?bosqich=' + encodeURIComponent(document.getElementById('ishBosqich').value)
      + (tur ? '&tur=' + tur : '') + (q ? '&q=' + encodeURIComponent(q) : ''));
    ishlarChiz();
    if (joriyIsh && yaqinIshDialogOchiq()) {                 // ochiq oyna yangilangan ma'lumot bilan qayta chiziladi
      const yangi = ishMalumot.ishlar.find(i => i.kalit === joriyIsh.kalit);
      if (yangi) { joriyIsh = yangi; ishDialogChiz(); }
    }
  } catch (xato) {
    holat.textContent = "Yuklab bo'lmadi: " + xato.message;
    holat.style.display = 'block';
  }
}
function yaqinIshDialogOchiq(){ return document.getElementById('ishDialog').open; }

function ishlarChiz(){
  const d = ishMalumot;
  document.querySelectorAll('[data-hx]').forEach(e => { e.textContent = d.xulosa[e.dataset.hx]; });
  const tana = document.getElementById('ishTana');
  tana.innerHTML = '';
  d.ishlar.forEach(i => {
    const tr = document.createElement('tr');
    katak(tr, i.kalit.toUpperCase());
    katak(tr, sanaVaqt(i.yaratilgan));
    const m = katak(tr, i.mijoz_ism || '—', 'matn-keng');
    const t = document.createElement('small'); t.textContent = i.mijoz_telefon; m.appendChild(t);
    const x = katak(tr, i.sarlavha, 'matn-keng');
    if (i.tafsilot) { const s = document.createElement('small'); s.textContent = i.tafsilot; x.appendChild(s); }
    katak(tr, i.manzil || '—', 'matn-keng');
    const h = document.createElement('td');
    h.appendChild(i.holat === 'yangi' ? belgi(i.holat_nomi, 'red')
      : (i.holat === 'bajarildi' || i.holat === 'yakunlandi') ? belgi(i.holat_nomi, 'done')
      : i.holat === 'bekor' ? belgi(i.holat_nomi, 'plan') : belgi(i.holat_nomi, 'progress'));
    tr.appendChild(h);
    const yuborilgan = i.hujjatlar.filter(x => x.yuborilgan).length, tayyor = i.hujjatlar.length - yuborilgan;
    const hj = katak(tr, i.hujjatlar.length ? `${yuborilgan} yuborilgan` : '—');
    if (tayyor) { const s = document.createElement('small'); s.style.color = 'var(--orange)'; s.textContent = `${tayyor} ta yuborilmagan`; hj.appendChild(s); }
    const amal = document.createElement('td');
    amal.className = 'amal-tugma';
    const b = document.createElement('button');
    b.type = 'button'; b.className = 'mini-btn asosiy'; b.textContent = 'Ochish';
    b.addEventListener('click', () => ishOchish(i));
    amal.appendChild(b);
    tr.appendChild(amal);
    tana.appendChild(tr);
  });
  const holat = document.getElementById('ishHolat');
  holat.textContent = "Bu bo'yicha ish yo'q.";
  holat.style.display = d.ishlar.length ? 'none' : 'block';
}

// — Ish oynasi —
function ishOchish(ish){
  joriyIsh = ish;
  document.getElementById('ishXabar').style.display = 'none';
  ['ishHujjatNom', 'ishHujjatIzoh'].forEach(id => { document.getElementById(id).value = ''; });
  document.getElementById('ishHujjatFayl').value = '';
  ishDialogChiz();
  const dlg = document.getElementById('ishDialog');
  if (typeof dlg.showModal === 'function') { if (!dlg.open) dlg.showModal(); } else dlg.setAttribute('open', '');
}

function ishXabar(matn, xato){
  const e = document.getElementById('ishXabar');
  e.textContent = matn || '';
  e.style.color = xato ? '#b91c1c' : 'var(--green)';
  e.style.display = matn ? 'block' : 'none';
}

function ishDialogChiz(){
  const i = joriyIsh;
  document.getElementById('ishSarlavha').textContent = `${i.kalit.toUpperCase()} — ${i.sarlavha}`;
  const malumot = document.getElementById('ishMalumot');
  malumot.innerHTML = '';
  [['Mijoz', `${i.mijoz_ism || '—'}, ${i.mijoz_telefon || '—'}`], ['Manzil', i.manzil || '—'],
   ['Ma\'lumot', i.tafsilot], ['Izoh', i.izoh], ['Mas\'ul xodim', i.xodim_ism], ['Holat', i.holat_nomi]]
    .filter(q => q[1]).forEach(([k, v]) => {
      const p = document.createElement('p');
      p.className = 'ish-qator-m';
      const b = document.createElement('b'); b.textContent = k + ': ';
      p.append(b, document.createTextNode(v));
      malumot.appendChild(p);
    });

  // Holat tugmalari (faqat metrologiya arizasi)
  const holatlar = document.getElementById('ishHolatTugma');
  holatlar.innerHTML = '';
  if (i.tur === 'ariza') {
    const tugma = (matn, holat, sinf) => {
      const b = document.createElement('button');
      b.type = 'button'; b.className = 'mini-btn ' + sinf; b.textContent = matn;
      b.addEventListener('click', () => ishHolatiniOzgartir(holat));
      holatlar.appendChild(b);
    };
    if (i.holat === 'yangi') tugma('Qabul qilish', 'korildi', 'yashil');
    if (i.holat === 'korildi') tugma("Mijoz bilan bog'lanildi", 'boglandi', 'asosiy');
    if (['korildi', 'boglandi'].includes(i.holat)) tugma('Yakunlash', 'yakunlandi', 'yashil');
    if (!['bekor', 'yakunlandi'].includes(i.holat)) tugma('Bekor qilish', 'bekor', 'qizil');
  } else {
    const p = document.createElement('small');
    p.style.color = 'var(--text-muted)';
    p.textContent = "Buyurtma holatini unga tayinlangan xodim boshqaradi.";
    holatlar.appendChild(p);
  }

  // Hujjatlar
  const royxat = document.getElementById('ishHujjatlar');
  royxat.innerHTML = '';
  i.hujjatlar.forEach(h => {
    const q = document.createElement('div');
    q.className = 'yq-qator';
    const chap = document.createElement('div');
    const nom = document.createElement('b'); nom.textContent = h.nom;
    const k = document.createElement('small');
    k.textContent = `${h.turi_nomi} · ${h.fayl_nomi} · ${h.tayyorlagan || '—'}` + (h.izoh ? ' · ' + h.izoh : '');
    chap.append(nom, k);
    const holat = document.createElement('div');
    holat.appendChild(h.yuborilgan ? belgi('Yuborilgan ' + sanaVaqt(h.yuborilgan), 'done') : belgi('Tayyor, yuborilmagan', 'wait'));
    const amal = document.createElement('div');
    if (!h.yuborilgan) {
      const y = document.createElement('button');
      y.type = 'button'; y.className = 'mini-btn yashil'; y.innerHTML = '<i class="ti ti-send"></i> Mijozga yuborish';
      y.addEventListener('click', () => hujjatYubor(h, y));
      const o = document.createElement('button');
      o.type = 'button'; o.className = 'mini-btn qizil'; o.style.marginLeft = '6px'; o.textContent = "O'chirish";
      o.addEventListener('click', () => hujjatOchir(h));
      amal.append(y, o);
    }
    q.append(chap, holat, amal);
    royxat.appendChild(q);
  });
  document.getElementById('ishHujjatBosh').style.display = i.hujjatlar.length ? 'none' : 'block';

  // Yuklash formasi: faqat qabul qilingan ish uchun
  document.getElementById('ishYuklashForma').style.display = i.tayyorlash_mumkin ? 'block' : 'none';
  document.getElementById('ishYuklashYopiq').style.display = i.tayyorlash_mumkin ? 'none' : 'block';
  document.getElementById('ishYuklashYopiq').textContent = i.tur === 'ariza'
    ? "Hujjat tayyorlash uchun avval arizani «Qabul qilish» kerak."
    : "Hujjat tayyorlash uchun buyurtmani tayinlangan xodim qabul qilgan bo'lishi kerak.";
}

async function ishHolatiniOzgartir(holat){
  ishXabar('');
  try {
    joriyIsh = await apiSorov('/hujjatlar/ish/' + joriyIsh.kalit + '/holat/', { method: 'POST', body: JSON.stringify({ holat }) });
    ishDialogChiz();
    ishlarYukla();
  } catch (x) { ishXabar(x.message, true); }
}

async function hujjatYubor(h, btn){
  if (!confirm(`«${h.nom}» hujjati mijozga yuborilsinmi? Mijoz kabinetida ko'rinadi va unga SMS boradi.`)) return;
  ishXabar('');
  btn.disabled = true;
  try {
    const j = await apiSorov('/hujjatlar/ish/hujjat/' + h.id + '/yuborish/', { method: 'POST' });
    joriyIsh = j.ish;
    ishDialogChiz();
    ishXabar('Hujjat mijozga yuborildi.');
    ishlarYukla(); hyYukla();
  } catch (x) { ishXabar(x.message, true); btn.disabled = false; }
}

async function hujjatOchir(h){
  if (!confirm(`«${h.nom}» o'chirilsinmi?`)) return;
  ishXabar('');
  try {
    await apiSorov('/hujjatlar/ish/hujjat/' + h.id + '/', { method: 'DELETE' });
    joriyIsh = { ...joriyIsh, hujjatlar: joriyIsh.hujjatlar.filter(x => x.id !== h.id) };
    ishDialogChiz();
    ishlarYukla(); hyYukla();
  } catch (x) { ishXabar(x.message, true); }
}

document.getElementById('ishYuklashForma').addEventListener('submit', async (e) => {
  e.preventDefault();
  const fayl = document.getElementById('ishHujjatFayl').files[0];
  if (!fayl) { ishXabar('Hujjat faylini tanlang.', true); return; }
  if (fayl.size > 30 * 1024 * 1024) { ishXabar('Fayl 30 MB dan oshmasin.', true); return; }
  const f = new FormData();
  f.append('fayl', fayl);
  f.append('nom', document.getElementById('ishHujjatNom').value.trim());
  f.append('turi', document.getElementById('ishHujjatTuri').value);
  f.append('izoh', document.getElementById('ishHujjatIzoh').value.trim());
  const btn = document.getElementById('ishYuklashBtn');
  btn.disabled = true; ishXabar('');
  try {
    const j = await apiSorov('/hujjatlar/ish/' + joriyIsh.kalit + '/hujjat/', { method: 'POST', body: f });
    joriyIsh = j.ish;
    ['ishHujjatNom', 'ishHujjatIzoh'].forEach(id => { document.getElementById(id).value = ''; });
    document.getElementById('ishHujjatFayl').value = '';
    ishDialogChiz();
    ishXabar("Hujjat saqlandi. Tekshirib, «Mijozga yuborish» ni bosing.");
    ishlarYukla(); hyYukla();
  } catch (x) { ishXabar(x.message, true); }
  finally { btn.disabled = false; }
});
document.getElementById('ishYopish').addEventListener('click', () => document.getElementById('ishDialog').close());
document.getElementById('ishBosqich').addEventListener('change', ishlarYukla);
document.getElementById('ishTur').addEventListener('change', ishlarYukla);
document.querySelectorAll('[data-ish-yangila]').forEach(b => b.addEventListener('click', ishlarYukla));
let ishQidirTimer = null;
document.getElementById('ishQidir').addEventListener('input', () => { clearTimeout(ishQidirTimer); ishQidirTimer = setTimeout(ishlarYukla, 350); });

// ═══════ Mijozga yuborish: tayyor hujjatlar ro'yxati (hamma ishlar bo'yicha) ═══════
// Server: backend/apps/hujjatlar/ish.py (tayyor_hujjatlar); yuborish/o'chirish — yuqoridagi bilan bir xil API.
function hyXabar(matn, xato){
  const e = document.getElementById('hyXabar');
  e.textContent = matn || '';
  e.style.color = xato ? '#b91c1c' : 'var(--green)';
  e.style.display = matn ? 'block' : 'none';
}

async function hyYukla(){
  if (!bolimBormi('hj-yuborish')) return;
  const bosh = document.getElementById('hyBosh');
  const q = document.getElementById('hyQidir').value.trim();
  try {
    const d = await apiSorov('/hujjatlar/ish/hujjatlar/?holat=' + encodeURIComponent(document.getElementById('hyHolat').value)
      + (q ? '&q=' + encodeURIComponent(q) : ''));
    document.querySelectorAll('[data-hy]').forEach(e => { e.textContent = d.xulosa[e.dataset.hy]; });
    const tana = document.getElementById('hyTana');
    tana.innerHTML = '';
    d.hujjatlar.forEach(h => {
      const tr = document.createElement('tr');
      const hj = katak(tr, h.nom, 'matn-keng');
      const k = document.createElement('small'); k.textContent = `${h.turi_nomi} · ${h.fayl_nomi}` + (h.izoh ? ' · ' + h.izoh : ''); hj.appendChild(k);
      const m = katak(tr, h.mijoz_ism || '—', 'matn-keng');
      const t = document.createElement('small'); t.textContent = h.mijoz_telefon || ''; m.appendChild(t);
      const x = katak(tr, h.ish_nomi, 'matn-keng');
      const s = document.createElement('small'); s.textContent = h.ish_kalit.toUpperCase() + (h.manzil ? ' · ' + h.manzil : ''); x.appendChild(s);
      const kim = katak(tr, h.tayyorlagan || '—');
      const sana = document.createElement('small'); sana.textContent = sanaVaqt(h.yaratilgan); kim.appendChild(sana);
      const holat = document.createElement('td');
      holat.appendChild(h.yuborilgan ? belgi('Yuborilgan ' + sanaVaqt(h.yuborilgan), 'done') : belgi('Tayyor, yuborilmagan', 'wait'));
      if (h.yuborilgan && h.yuborgan) { const y = document.createElement('small'); y.textContent = h.yuborgan; holat.appendChild(y); }
      tr.appendChild(holat);
      const amal = document.createElement('td');
      amal.className = 'amal-tugma';
      if (!h.yuborilgan) {
        const y = document.createElement('button');
        y.type = 'button'; y.className = 'mini-btn yashil'; y.innerHTML = '<i class="ti ti-send"></i> Mijozga yuborish';
        if (h.yuborish_mumkin) y.addEventListener('click', () => hyYubor(h, y));
        else { y.disabled = true; y.title = "Buyurtmada mijoz hisobi yo'q"; }
        const o = document.createElement('button');
        o.type = 'button'; o.className = 'mini-btn qizil'; o.style.marginLeft = '6px'; o.textContent = "O'chirish";
        o.addEventListener('click', () => hyOchir(h));
        amal.append(y, o);
      }
      tr.appendChild(amal);
      tana.appendChild(tr);
    });
    bosh.textContent = document.getElementById('hyHolat').value === 'tayyor'
      ? "Yuborilmagan hujjat yo'q." : "Bu bo'yicha hujjat yo'q.";
    bosh.style.display = d.hujjatlar.length ? 'none' : 'block';
  } catch (xato) {
    bosh.textContent = "Yuklab bo'lmadi: " + xato.message;
    bosh.style.display = 'block';
  }
}

async function hyYubor(h, btn){
  if (!confirm(`«${h.nom}» hujjati ${h.mijoz_ism || 'mijoz'}ga (${h.mijoz_telefon || '—'}) yuborilsinmi? Mijoz kabinetida ko'rinadi va unga SMS boradi.`)) return;
  hyXabar('');
  btn.disabled = true;
  try {
    await apiSorov('/hujjatlar/ish/hujjat/' + h.id + '/yuborish/', { method: 'POST' });
    hyXabar(`«${h.nom}» mijozga yuborildi.`);
    hyYukla(); ishlarYukla();
  } catch (x) { hyXabar(x.message, true); btn.disabled = false; }
}

async function hyOchir(h){
  if (!confirm(`«${h.nom}» o'chirilsinmi?`)) return;
  hyXabar('');
  try {
    await apiSorov('/hujjatlar/ish/hujjat/' + h.id + '/', { method: 'DELETE' });
    hyYukla(); ishlarYukla();
  } catch (x) { hyXabar(x.message, true); }
}

document.getElementById('hyHolat').addEventListener('change', hyYukla);
document.querySelectorAll('[data-hy-yangila]').forEach(b => b.addEventListener('click', hyYukla));
let hyQidirTimer = null;
document.getElementById('hyQidir').addEventListener('input', () => { clearTimeout(hyQidirTimer); hyQidirTimer = setTimeout(hyYukla, 350); });

// ═══════ Topshiriqlar: Kadrlar/call center -> hujjatchi, hujjatchi -> o'ziga; natija fayli ═══════
// Server: backend/apps/hujjatlar/topshiriq.py. Fayllar ochiq havolasiz — token bilan yuklab olinadi.
let tsMalumot = null, tsJoriy = null, tsTimer = null;
const TS_FAYL_MAX = 30 * 1024 * 1024;

function tsXabar(matn, xato, id = 'tsXabar'){
  const e = document.getElementById(id);
  e.textContent = matn || '';
  e.style.color = xato ? '#b91c1c' : 'var(--green)';
  e.style.display = matn ? 'block' : 'none';
}

async function tsFaylOl(t, tur){
  try {
    const javob = await fetch(API + `/hujjatlar/topshiriq/${t.id}/fayl/${tur}/`, { headers: token ? { 'Authorization': 'Bearer ' + token } : {} });
    if (!javob.ok) {
      let d = ''; try { d = (await javob.json()).detail; } catch (e) { /* JSON emas */ }
      throw new Error(d || "Faylni olib bo'lmadi");
    }
    const url = window.URL.createObjectURL(await javob.blob());
    const a = document.createElement('a');
    a.href = url; a.download = tur === 'natija' ? t.natija_nomi : t.fayl_nomi;
    document.body.appendChild(a); a.click(); a.remove();
    setTimeout(() => window.URL.revokeObjectURL(url), 10000);
  } catch (x) { tsXabar(x.message, true); }
}

function tsFaylTugma(matn, nom, bos){
  const b = document.createElement('button');
  b.type = 'button'; b.className = 'mini-btn'; b.style.cssText = 'margin-top:4px;background:var(--bg-bottom);';
  b.innerHTML = '<i class="ti ti-paperclip"></i> ';
  b.append(document.createTextNode(`${matn}: ${nom}`));
  b.addEventListener('click', bos);
  return b;
}

async function tsYukla(){
  if (!bolimBormi('topshiriq')) return;
  const bosh = document.getElementById('tsBosh');
  try {
    const d = await apiSorov('/hujjatlar/topshiriq/?holat=' + encodeURIComponent(document.getElementById('tsHolat').value));
    tsMalumot = d;
    document.querySelectorAll('[data-ts]').forEach(e => { e.textContent = d.xulosa[e.dataset.ts]; });
    const nav = document.getElementById('tsNavSoni');
    nav.textContent = d.xulosa.yangi; nav.style.display = d.xulosa.yangi ? 'inline-block' : 'none';
    tsFormaSozla(d);
    tsChiz(d);
    bosh.textContent = "Bu bo'yicha topshiriq yo'q.";
    bosh.style.display = d.topshiriqlar.length ? 'none' : 'block';
  } catch (xato) {
    bosh.textContent = "Yuklab bo'lmadi: " + xato.message;
    bosh.style.display = 'block';
  }
}

function tsFormaSozla(d){
  const yuboruvchi = !d.oziga_yozadi;                         // Kadrlar / call center: hujjatchiga yuboradi
  document.getElementById('tsKimgaBlok').style.display = yuboruvchi ? '' : 'none';
  document.getElementById('tsFormaSarlavha').textContent = yuboruvchi ? 'Topshiriq yuborish' : "O'zimga vazifa qo'shish";
  document.getElementById('tsBtn').textContent = yuboruvchi ? 'Topshiriqni yuborish' : "Vazifani qo'shish";
  document.getElementById('tsIzoh').textContent = yuboruvchi
    ? "Hujjatlar bilan ishlovchi xodimga topshiriq yuboring (fayl biriktirishingiz mumkin). U bajargach natija faylini shu yerdan yuklab olasiz."
    : "Kadrlar va call center xodimlari yuborgan topshiriqlar shu yerda. O'zingiz uchun ham vazifa qo'shishingiz, bajargach natija faylini yuklashingiz mumkin.";
  if (yuboruvchi) {
    const sel = document.getElementById('tsKimga'), tanlangan = sel.value;
    sel.innerHTML = '';
    d.kimlar.forEach(k => {
      const o = document.createElement('option'); o.value = k.id; o.textContent = k.ism; sel.appendChild(o);
    });
    if (!d.kimlar.length) {
      const o = document.createElement('option'); o.value = ''; o.textContent = "Hujjatchi xodim topilmadi"; sel.appendChild(o);
    } else if (tanlangan) sel.value = tanlangan;
  }
}

function tsChiz(d){
  const tana = document.getElementById('tsTana');
  tana.innerHTML = '';
  d.topshiriqlar.forEach(t => {
    const tr = document.createElement('tr');
    const a = katak(tr, t.sarlavha, 'matn-keng');
    a.style.fontWeight = '700';
    if (t.matn) { const s = document.createElement('small'); s.style.fontWeight = '400'; s.textContent = t.matn; a.appendChild(s); }
    if (t.fayl_nomi) a.appendChild(tsFaylTugma('Fayl', t.fayl_nomi, () => tsFaylOl(t, 'topshiriq')));
    const kim = katak(tr, t.oziga ? "O'zi uchun" : `${t.kim || '—'} → ${t.kimga}`, 'matn-keng');
    const y = document.createElement('small'); y.textContent = sanaVaqt(t.yaratilgan); kim.appendChild(y);
    const m = katak(tr, t.muddat ? sanaVaqt(t.muddat) : '—');
    if (t.kechikkan) { m.style.color = '#b91c1c'; m.style.fontWeight = '700'; const s = document.createElement('small'); s.textContent = "muddati o'tgan"; m.appendChild(s); }
    const h = document.createElement('td');
    h.appendChild(belgi(t.holat_nomi, { yangi: 'wait', jarayonda: 'progress', bajarildi: 'done', bekor: 'plan' }[t.holat] || 'plan'));
    if (t.bajarilgan) { const s = document.createElement('small'); s.textContent = sanaVaqt(t.bajarilgan); h.appendChild(s); }
    if (t.natija_izoh) { const s = document.createElement('small'); s.textContent = t.natija_izoh; h.appendChild(s); }
    if (t.natija_nomi) h.appendChild(tsFaylTugma('Natija', t.natija_nomi, () => tsFaylOl(t, 'natija')));
    tr.appendChild(h);
    const amal = document.createElement('td');
    amal.className = 'amal-tugma';
    const tugma = (matn, sinf, bos) => {
      const b = document.createElement('button');
      b.type = 'button'; b.className = 'mini-btn ' + sinf; b.textContent = matn; b.style.marginRight = '6px';
      b.addEventListener('click', bos); amal.appendChild(b);
    };
    if (t.boshlash_mumkin) tugma('Boshladim', 'asosiy', () => tsHolat(t, 'jarayonda'));
    if (t.bajarish_mumkin) tugma('Bajarildi', 'yashil', () => tsBajarOch(t));
    if (t.bekor_mumkin) tugma('Bekor qilish', 'qizil', () => tsBekor(t));
    tr.appendChild(amal);
    tana.appendChild(tr);
  });
}

async function tsHolat(t, holat){
  tsXabar('');
  try {
    await apiSorov(`/hujjatlar/topshiriq/${t.id}/holat/`, { method: 'POST', body: JSON.stringify({ holat }) });
    tsYukla();
  } catch (x) { tsXabar(x.message, true); }
}
function tsBekor(t){
  if (confirm(`«${t.sarlavha}» topshirig'i bekor qilinsinmi?`)) tsHolat(t, 'bekor');
}

function tsBajarOch(t){
  tsJoriy = t;
  document.getElementById('tsDialogSarlavha').textContent = `«${t.sarlavha}» — bajarildi`;
  document.getElementById('tsNatijaFayl').value = '';
  document.getElementById('tsNatijaIzoh').value = '';
  tsXabar('', false, 'tsDialogXabar');
  const dlg = document.getElementById('tsDialog');
  if (typeof dlg.showModal === 'function') { if (!dlg.open) dlg.showModal(); } else dlg.setAttribute('open', '');
}

document.getElementById('tsBajarForma').addEventListener('submit', async (e) => {
  e.preventDefault();
  const fayl = document.getElementById('tsNatijaFayl').files[0];
  if (fayl && fayl.size > TS_FAYL_MAX) { tsXabar('Fayl 30 MB dan oshmasin.', true, 'tsDialogXabar'); return; }
  const f = new FormData();
  if (fayl) f.append('natija_fayl', fayl);
  f.append('natija_izoh', document.getElementById('tsNatijaIzoh').value.trim());
  const btn = document.getElementById('tsBajarBtn');
  btn.disabled = true; tsXabar('', false, 'tsDialogXabar');
  try {
    await apiSorov(`/hujjatlar/topshiriq/${tsJoriy.id}/bajarildi/`, { method: 'POST', body: f });
    document.getElementById('tsDialog').close();
    tsXabar('Topshiriq bajarildi deb belgilandi.');
    tsYukla();
  } catch (x) { tsXabar(x.message, true, 'tsDialogXabar'); }
  finally { btn.disabled = false; }
});
document.getElementById('tsDialogYopish').addEventListener('click', () => document.getElementById('tsDialog').close());

document.getElementById('tsForma').addEventListener('submit', async (e) => {
  e.preventDefault();
  const fayl = document.getElementById('tsFayl').files[0];
  if (fayl && fayl.size > TS_FAYL_MAX) { tsXabar('Fayl 30 MB dan oshmasin.', true); return; }
  const f = new FormData();
  f.append('sarlavha', document.getElementById('tsSarlavha').value.trim());
  f.append('matn', document.getElementById('tsMatn').value.trim());
  const muddat = document.getElementById('tsMuddat').value;
  if (muddat) f.append('muddat', muddat);
  if (tsMalumot && !tsMalumot.oziga_yozadi) f.append('kimga', document.getElementById('tsKimga').value);
  if (fayl) f.append('fayl', fayl);
  const btn = document.getElementById('tsBtn');
  btn.disabled = true; tsXabar('');
  try {
    await apiSorov('/hujjatlar/topshiriq/', { method: 'POST', body: f });
    e.target.reset();
    tsXabar(tsMalumot && !tsMalumot.oziga_yozadi ? 'Topshiriq yuborildi.' : "Vazifa qo'shildi.");
    tsYukla();
  } catch (x) { tsXabar(x.message, true); }
  finally { btn.disabled = false; }
});
document.getElementById('tsHolat').addEventListener('change', tsYukla);
document.querySelectorAll('[data-ts-yangila]').forEach(b => b.addEventListener('click', tsYukla));
// Yangi topshiriq kelganini bilish uchun (menyudagi qizil son): sahifa ko'rinib turganda har daqiqada yangilanadi
function tsKuzat(){
  if (tsTimer) return;
  tsTimer = setInterval(() => { if (!document.hidden) tsYukla(); }, 60000);
}

// ═══════ Call center: chiquvchi qo'ng'iroqlar ═══════
async function qongiroqYukla(){
  if (!bolimBormi('op-qongiroq')) return;
  const holat = document.getElementById('qHolat');
  try {
    const d = await apiSorov('/buyurtmalar/operator/qongiroqlar/');
    document.getElementById('qBugun').textContent = `(bugun ${d.bugun_soni} ta qo'ng'iroq)`;

    const qt = document.getElementById('qQaytaTana');
    qt.innerHTML = '';
    d.qayta_qilinadigan.forEach(q => {
      const tr = document.createElement('tr');
      katak(tr, q.nomi); katak(tr, q.telefon); katak(tr, sanaFormat(q.qayta_sana)); katak(tr, q.izoh || '—', 'matn-keng');
      qt.appendChild(tr);
    });
    document.getElementById('qQaytaSoni').textContent = d.qayta_qilinadigan.length ? `(${d.qayta_qilinadigan.length} ta)` : '';
    document.getElementById('qQaytaHolat').style.display = d.qayta_qilinadigan.length ? 'none' : 'block';

    const tana = document.getElementById('qTana');
    tana.innerHTML = '';
    d.qongiroqlar.forEach(q => {
      const tr = document.createElement('tr');
      katak(tr, sanaVaqt(q.yaratilgan) + ' ' + soatMinut(q.yaratilgan));
      const k = katak(tr, q.nomi, 'matn-keng');
      const s = document.createElement('small'); s.textContent = q.shaxs_nomi; k.appendChild(s);
      katak(tr, q.telefon);
      const n = document.createElement('td');
      n.appendChild(q.natija === 'ariza' ? belgi(q.natija_nomi, 'done')
        : q.natija === 'rad' ? belgi(q.natija_nomi, 'red')
        : q.natija === 'qiziqdi' ? belgi(q.natija_nomi, 'progress') : belgi(q.natija_nomi, 'wait'));
      if (q.qayta_sana) { const t = document.createElement('small'); t.style.display = 'block'; t.style.marginTop = '5px'; t.textContent = sanaFormat(q.qayta_sana); n.appendChild(t); }
      tr.appendChild(n);
      katak(tr, q.izoh || '—', 'matn-keng');
      katak(tr, q.operator_ism || '—');
      tana.appendChild(tr);
    });
    holat.textContent = "Hali qo'ng'iroq qayd etilmagan.";
    holat.style.display = d.qongiroqlar.length ? 'none' : 'block';
  } catch (xato) {
    holat.textContent = "Yuklab bo'lmadi: " + xato.message;
    holat.style.display = 'block';
  }
}

document.getElementById('qYangila').addEventListener('click', qongiroqYukla);
document.getElementById('qongiroqForma').addEventListener('submit', async (e) => {
  e.preventDefault();
  const btn = document.getElementById('qBtn'), xato = document.getElementById('qXato');
  xato.classList.remove('show');
  btn.disabled = true;
  const shaxs = document.getElementById('qShaxs').value, nomi = document.getElementById('qNomi').value.trim();
  const telefon = document.getElementById('qTelefon').value.trim(), natija = document.getElementById('qNatija').value;
  try {
    await apiSorov('/buyurtmalar/operator/qongiroqlar/', {
      method: 'POST',
      body: JSON.stringify({
        shaxs, nomi, telefon, natija,
        qayta_sana: document.getElementById('qQayta').value || null,
        izoh: document.getElementById('qIzoh').value.trim()
      })
    });
    ['qNomi', 'qTelefon', 'qQayta', 'qIzoh'].forEach(id => { document.getElementById(id).value = ''; });
    await qongiroqYukla();
    if (natija === 'ariza') {         // mijoz ariza berdi: ariza formasi to'ldirib ochiladi
      document.getElementById('opIsm').value = nomi;
      document.getElementById('opTelefon').value = telefon;
      document.getElementById('opTarmoq').value = shaxs === 'yuridik' ? 'ulgurji' : 'aholi';
      showPage('op-arizalar');
      document.getElementById('opManzil').focus();
    }
  } catch (x) {
    xato.textContent = x.message;
    xato.classList.add('show');
  } finally {
    btn.disabled = false;
  }
});

function kabinetOch(){
  document.getElementById('authView').style.display = 'none';
  document.getElementById('dashView').style.display = 'block';
  if (KORISH) korishBannerKorsat((profil && (profil.ism || profil.telefon)) || '');
  profilChiz();
  menyuQur();
  jamoaYukla();
  // Faqat shu lavozimning bo'limlari uchun ma'lumot yuklanadi
  if (bolimBormi('tasks') || bolimBormi('cash')) vazifalarYukla();
  if (kabinetTuri !== 'kadrlar') smenaYukla();
  if (bolimBormi('cash')) tushumYukla();
  if (bolimBormi('price') || bolimBormi('cash')) narxnomaYukla();    // tushum turlari narxnomadan quriladi
  if (bolimBormi('docs')) hujjatlarYukla();
  if (bolimBormi('certs')) sertifikatlarYukla();
  if (bolimBormi('pay')) ishHaqiYukla();
  if (bolimBormi('hj-ishlar')) ishlarYukla();
  if (bolimBormi('hj-yuborish')) hyYukla();
  if (bolimBormi('topshiriq')) { tsYukla(); tsKuzat(); }
  if (kabinetTuri === 'kadrlar') { kunYukla(); kadrHujjatYukla(); kadrTushumYukla(); kadrTushumKuzat(); arizalarYukla(); qongiroqYukla(); }
  else {
    hisobotYukla();
    arizalarYukla();            // qo'ng'iroq vazifasi bor xodimda (boshqalarda bo'lim yo'q - bolimBormi o'zi to'xtatadi)
    qongiroqYukla();
  }
  xabarlarBoshla();
}

function chiqish(){
  if (KORISH) { korishChiq(); return; }      // ko'rish rejimida smenaga tegilmaydi, tab yopiladi
  // Chiqqan xodimning smenasi ochiq qolmasin (token hali o'chirilmagan)
  const smenaOchiqEdi = smena.faol && token;
  smena = { rozilik: false, faol: false, oraliq_soniya: 15 };   // avval tozalanadi — 401 da chiqish() qayta chaqirilsa aylanib qolmasin
  joyKuzatuvToxtat();
  xabarlarToxtat();
  clearInterval(kadrTushumTimer);
  if (smenaOchiqEdi) {
    apiSorov('/joylashuv/smena/tugatish/', { method: 'POST' }).catch(() => {});
  }
  tokenOchir();
  profil = null;
  document.getElementById('dashView').style.display = 'none';
  document.getElementById('authView').style.display = 'flex';
  document.getElementById('loginKod').value = '';
  eslabQolYukla();   // saqlangan telefon raqam qaytadan qo'yiladi
}

// Kod har doim katta harfda ko'rinsin — admin uni katta harfda beradi
document.getElementById('loginKod').addEventListener('input', (e)=>{
  const joy = e.target.selectionStart;
  e.target.value = e.target.value.toUpperCase();
  e.target.setSelectionRange(joy, joy);
});

document.getElementById('loginForm').addEventListener('submit', async (e)=>{
  e.preventDefault();
  const btn = document.getElementById('loginBtn');
  const xatoEl = document.getElementById('loginXato');
  xatoEl.classList.remove('show');
  btn.disabled = true;
  btn.textContent = 'Tekshirilmoqda...';
  const telefon = document.getElementById('loginTelefon').value.replace(/\s/g, '');
  const eslab = document.getElementById('eslabQol').checked;
  try {
    const javob = await fetch(API + '/auth/xodim/login/', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      // `eslab: false` — «meni eslab qolma»: refresh cookie brauzer yopilganda o'chadi
      body: JSON.stringify({ telefon, kod: document.getElementById('loginKod').value.trim(), eslab })
    });
    const malumot = await javob.json();
    if (!javob.ok) throw new Error(malumot.detail || 'Kirish amalga oshmadi');
    tokenSaqla(malumot.access, eslab);
    eslabQolSaqla(eslab, telefon);
    profil = malumot.xodim;
    kabinetOch();
  } catch (xato) {
    xatoEl.textContent = xato.message === 'Failed to fetch'
      ? 'Serverga ulanib bo\'lmadi. Backend ishga tushirilganini tekshiring (backend\\start.bat).'
      : xato.message;
    xatoEl.classList.add('show');
  } finally {
    btn.disabled = false;
    btn.textContent = 'Kirish';
  }
});

document.getElementById('logoutBtn').addEventListener('click', chiqish);
document.getElementById('logoutBtn2').addEventListener('click', chiqish);

// Sahifa ochilganda saqlangan token bo'lsa avtomatik kirish
(async function boshlash(){
  eslabQolYukla();
  tokenYukla();
  if (!token) return;
  try {
    profil = await apiSorov('/auth/xodim/profil/');
    kabinetOch();
  } catch (e) { tokenOchir(); }
})();

// ═══════ Yon paneldagi bo'limlar ═══════
document.querySelectorAll('.sb-item[data-page]').forEach(btn=>{
  btn.addEventListener('click', ()=> showPage(btn.dataset.page));
});
document.querySelectorAll('.dropdown .dd-item[data-page]').forEach(btn=>{
  btn.addEventListener('click', ()=> showPage(btn.dataset.page));
});
function showPage(key){
  if (!ruxsatliBolimlar.includes(key)) key = 'overview';     // lavozimga tegishli bo'lmagan bo'lim ochilmaydi
  document.querySelectorAll('.sb-item[data-page]').forEach(b=>b.classList.toggle('active', b.dataset.page===key));
  document.querySelectorAll('.page').forEach(p=>p.classList.toggle('active', p.id === 'page-'+key));
  // Narxnoma jadvali uchun oynaning to'liq kengligi
  document.querySelector('.content').classList.toggle('keng', key === 'price');
  document.querySelectorAll('.dropdown').forEach(d=>d.classList.remove('open'));
  closeSidebar();
  if (key === 'op-arizalar' && typeof opXaritaTayyor === 'function') opXaritaTayyor();
  if (key === 'topshiriq' && typeof tsYukla === 'function') tsYukla();
}

// ═══════ Mobil yon panel ═══════
const sidebar=document.getElementById('sidebar'), sbBackdrop=document.getElementById('sbBackdrop');
function closeSidebar(){ sidebar.classList.remove('open'); sbBackdrop.classList.remove('open'); }
document.getElementById('burgerBtn').addEventListener('click', (e)=>{
  e.stopPropagation();
  sidebar.classList.toggle('open');
  sbBackdrop.classList.toggle('open', sidebar.classList.contains('open'));
});
sbBackdrop.addEventListener('click', closeSidebar);

// ═══════ Yuqoridagi ochiluvchi menyular ═══════
const bellBtn=document.getElementById('bellBtn'), bellDD=document.getElementById('bellDropdown');
const profChip=document.getElementById('profileChip'), profDD=document.getElementById('profileDropdown');
bellBtn.addEventListener('click', (e)=>{
  e.stopPropagation(); profDD.classList.remove('open'); bellDD.classList.toggle('open');
  // Ochilganda xabarlar ko'rildi deb hisoblanadi (yangilari shu safar ajratib ko'rsatiladi)
  if (bellDD.classList.contains('open')) setTimeout(xabarlarOqildi, 1500);
});
profChip.addEventListener('click', (e)=>{ e.stopPropagation(); bellDD.classList.remove('open'); profDD.classList.toggle('open'); });
document.addEventListener('click', ()=>{ bellDD.classList.remove('open'); profDD.classList.remove('open'); });
document.addEventListener('keydown', (e)=>{
  if(e.key!=='Escape') return;
  bellDD.classList.remove('open'); profDD.classList.remove('open'); closeSidebar();
});
