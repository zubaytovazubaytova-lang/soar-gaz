// ═══════ Backend ═══════
// Sayt server orqali ochilsa nisbiy manzil, fayl sifatida ochilsa dev backend.
// Diqqat: bu sahifa admin ROLI uchun (/api/auth/admin/login/), Django'ning
// o'z /admin/ paneli bilan aralashtirmang.
const API = location.protocol === 'file:' ? 'http://localhost:8001/api' : '/api';
const TOKEN_KALIT = 'soargaz_admin_token';

let token = null;
let profil = null;
// Arizalar bir marta yuklanadi, chiplar shu ro'yxatni filtrlaydi
let arizalar = [];
let xodimlar = [];
let tanlanganHolat = '';

function tokenSaqla(t){ token = t; try { sessionStorage.setItem(TOKEN_KALIT, t); } catch(e){} }
function tokenYukla(){ try { token = sessionStorage.getItem(TOKEN_KALIT); } catch(e){} }
function tokenOchir(){ token = null; try { sessionStorage.removeItem(TOKEN_KALIT); } catch(e){} }

async function apiSorov(yol, sozlama = {}){
  const javob = await fetch(API + yol, {
    ...sozlama,
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { 'Authorization': 'Bearer ' + token } : {}),
      ...(sozlama.headers || {})
    }
  });
  // 401 "sessiya tugadi" degani FAQAT kirib bo'lgan (tokenli) holatda. Kirish
  // formasida 401 — bu noto'g'ri parol, serverning o'z xabari (qancha urinish
  // qolgani) ko'rsatilishi kerak.
  if (javob.status === 401 && token) { chiqish(); throw new Error('Sessiya tugadi'); }
  const matn = await javob.text();
  const malumot = matn ? JSON.parse(matn) : null;
  if (!javob.ok) throw new Error(xatoMatni(malumot));
  return malumot;
}

// Django REST forma xatolarini {maydon: ["sabab"]} ko'rinishida qaytaradi —
// faqat `detail` ni o'qisak, foydalanuvchi "Server xatosi" dan boshqa
// hech narsa ko'rmaydi va nimani noto'g'ri kiritganini bilmaydi.
function xatoMatni(malumot){
  if (!malumot) return 'Server xatosi';
  if (typeof malumot === 'string') return malumot;
  if (malumot.detail) return malumot.detail;
  const satrlar = [];
  for (const [maydon, qiymat] of Object.entries(malumot)){
    const matn = Array.isArray(qiymat) ? qiymat.join(' ') : String(qiymat);
    satrlar.push(maydon === 'non_field_errors' ? matn : `${maydon}: ${matn}`);
  }
  return satrlar.join('\n') || 'Server xatosi';
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
  const d = new Date(iso);
  if (isNaN(d)) return '—';
  const ikki = n => String(n).padStart(2, '0');
  return `${ikki(d.getDate())}.${ikki(d.getMonth() + 1)}.${d.getFullYear()}`;
}

function xavfsiz(matn){
  const el = document.createElement('div');
  el.textContent = matn == null ? '' : String(matn);
  return el.innerHTML;
}

// ═══════ Kirish / chiqish ═══════
function xatoKorsat(matn){
  const el = document.getElementById('loginXato');
  el.textContent = matn || '';
  el.classList.toggle('bor', !!matn);
}

document.getElementById('loginForm').addEventListener('submit', async (e) => {
  e.preventDefault();
  const tugma = document.getElementById('loginBtn');
  const telefon = document.getElementById('loginTelefon').value.replace(/\s/g, '');
  const parol = document.getElementById('loginParol').value;

  if (telefon.length < 13) { xatoKorsat("Telefon raqamni to'liq kiriting: +998 XX XXX XX XX"); return; }
  if (!parol) { xatoKorsat('Parolni kiriting'); return; }

  xatoKorsat('');
  tugma.disabled = true;
  tugma.textContent = 'Tekshirilmoqda…';
  try {
    const javob = await apiSorov('/auth/admin/login/', {
      method: 'POST',
      body: JSON.stringify({ telefon, parol })
    });
    document.getElementById('loginParol').value = '';
    parolniYashir();

    // 2FA yoqilgan bo'lsa parol bosqichi token bermaydi — kod so'raladi
    if (javob.otp_kerak) { otpBosqichiniOch(javob); return; }

    kirishYakunla(javob);
  } catch (xato) {
    xatoKorsat(xato.message);
  } finally {
    tugma.disabled = false;
    tugma.textContent = 'Kirish';
  }
});

// ═══════ Ikki bosqichli kirish (2FA) ═══════
// Chipta — parol bosqichidan o'tilganini isbotlaydigan vaqtinchalik kalit.
// Usiz OTP bosqichi qabul qilinmaydi, ya'ni ikkala bosqich ham majburiy.
let otpChipta = null;

function otpXatoKorsat(matn){
  const el = document.getElementById('otpXato');
  el.textContent = matn || '';
  el.classList.toggle('bor', !!matn);
}

function otpBosqichiniOch(javob){
  otpChipta = javob.chipta;
  document.getElementById('loginForm').style.display = 'none';
  document.getElementById('otpForm').style.display = 'block';
  document.getElementById('otpTelefon').textContent = javob.telefon_maskasi || '—';
  document.getElementById('otpMuddat').textContent = javob.muddat_daqiqa || 5;

  // Dev rejimda SMS provayder ulanmagan — kod javobda keladi, aks holda
  // lokal ishlab chiqishda panelga kirib bo'lmaydi. Serverda bu bo'lmaydi.
  otpXatoKorsat('');
  if (javob.dev_kod) {
    document.getElementById('otpKod').value = javob.dev_kod;
    otpXatoKorsat(`Dev rejim: SMS ulanmagan, kod — ${javob.dev_kod}`);
  } else if (javob.ogohlantirish) {
    otpXatoKorsat(javob.ogohlantirish);
  }
  document.getElementById('otpKod').focus();
}

function otpBosqichiniYop(){
  otpChipta = null;
  document.getElementById('otpForm').style.display = 'none';
  document.getElementById('loginForm').style.display = 'block';
  document.getElementById('otpKod').value = '';
  otpXatoKorsat('');
}

function kirishYakunla(javob){
  tokenSaqla(javob.access);
  profil = javob.user;
  if (javob.sessiya_daqiqa) sessiyaDaqiqa = javob.sessiya_daqiqa;
  otpBosqichiniYop();
  sessiyaYangila();
  panelniOch();
}

document.getElementById('otpOrtga').addEventListener('click', otpBosqichiniYop);

document.getElementById('otpForm').addEventListener('submit', async (e) => {
  e.preventDefault();
  const kod = document.getElementById('otpKod').value.trim();
  if (kod.length !== 6) { otpXatoKorsat('6 xonali kodni kiriting'); return; }

  const tugma = document.getElementById('otpBtn');
  otpXatoKorsat('');
  tugma.disabled = true;
  tugma.textContent = 'Tekshirilmoqda…';
  try {
    const javob = await apiSorov('/auth/admin/otp/', {
      method: 'POST',
      body: JSON.stringify({ chipta: otpChipta, kod })
    });
    kirishYakunla(javob);
  } catch (xato) {
    otpXatoKorsat(xato.message);
    // Chipta kuchdan qolgan bo'lsa — birinchi bosqichga qaytaramiz
    if (/qaytadan|muddati/i.test(xato.message || '')) {
      setTimeout(() => { otpBosqichiniYop(); xatoKorsat(xato.message); }, 1800);
    }
  } finally {
    tugma.disabled = false;
    tugma.textContent = 'Tasdiqlash';
  }
});

function chiqish(sabab){
  clearTimeout(sessiyaTaymer);
  otpBosqichiniYop();
  tokenOchir();
  profil = null;
  arizalar = [];
  joyMalumot = [];
  // Yangilanishlar to'xtaydi va qayta kirganda Rahbariyat sahifasidan boshlanadi.
  // (Tugmani bosib bo'lmaydi: u ma'lumot so'raydi, 401 esa yana chiqish() ni chaqirardi.)
  joySahifasiYopildi();
  rahSahifasiYopildi();
  sahifaniQoy('rahbariyat');
  parolniYashir();               // chiqqandan keyin parol ochiq ko'rinib qolmasin
  document.getElementById('dashView').style.display = 'none';
  document.getElementById('authView').style.display = 'flex';
  xatoKorsat(sabab || '');
}
document.getElementById('chiqishBtn').addEventListener('click', () => chiqish());

// ═══════ Sessiya nazorati ═══════
// Server tokeni ADMIN_SESSIYA_DAQIQA dan keyin kuchini yo'qotadi. Panel ham
// o'sha vaqt harakatsizlikdan keyin o'zi chiqadi — ochiq qolgan kompyuterda
// panel egasiz turmasin. Har qanday harakat hisobni qaytadan boshlaydi.
let sessiyaDaqiqa = 30;
let sessiyaTaymer = null;

function sessiyaYangila(){
  if (!token) return;
  clearTimeout(sessiyaTaymer);
  sessiyaTaymer = setTimeout(() => {
    chiqish(`${sessiyaDaqiqa} daqiqa harakatsizlikdan keyin sessiya yakunlandi. Qaytadan kiring.`);
  }, sessiyaDaqiqa * 60 * 1000);
}

['click', 'keydown', 'scroll', 'touchstart'].forEach(hodisa => {
  document.addEventListener(hodisa, sessiyaYangila, { passive: true });
});

async function panelniOch(){
  document.getElementById('authView').style.display = 'none';
  document.getElementById('dashView').style.display = 'block';
  profilChiz();
  rahSahifasiOchildi();          // kirgandan keyin Rahbariyat sahifasi birinchi ochiladi
  await Promise.all([
    statistikaYukla(), arizalarYukla(), xodimlarYukla(),
    mijozlarYukla(), moliyaYukla(), jurnalYukla(), tushumYukla(),
  ]);
}

function profilChiz(){
  const ism = (profil && (profil.ism || profil.telefon)) || 'Admin';
  document.getElementById('profilIsm').textContent = ism;
  document.getElementById('profilHarf').textContent = boshHarflar(ism);
  // Direktor — kuzatuvchi: hamma narsani ko'radi, o'zgartira olmaydi (server ham bloklaydi: apps/auth_app/korish.py)
  document.querySelector('.profile-chip .prole').textContent = (profil && profil.kuzatuvchi) ? "Kuzatuvchi — faqat ko'rish" : "To'liq huquq";
}

// ═══════ Bosh sahifa ═══════
async function statistikaYukla(){
  let s;
  try { s = await apiSorov('/buyurtmalar/statistika/'); } catch (e) { return; }
  document.getElementById('statYangi').textContent = s.yangi;
  document.getElementById('statJarayon').textContent = s.qabul + s.jarayonda;
  document.getElementById('statBajarildi').textContent = s.bajarildi;
  document.getElementById('statXodim').textContent = s.xodimlar_soni;
}

const HAFTA_NOM = ['Yak', 'Dush', 'Sesh', 'Chor', 'Pay', 'Jum', 'Shan'];

// Oxirgi 7 kunlik ustunlar — arizalarning 'yaratilgan' sanasidan sanaladi
function haftalikChiz(){
  const kunlar = [];
  const bugun = new Date();
  for (let i = 6; i >= 0; i--) {
    const d = new Date(bugun);
    d.setDate(bugun.getDate() - i);
    kunlar.push({ nom: HAFTA_NOM[d.getDay()], kalit: d.toDateString(), soni: 0 });
  }
  const indeks = new Map(kunlar.map(k => [k.kalit, k]));
  arizalar.forEach(a => {
    const kun = indeks.get(new Date(a.yaratilgan).toDateString());
    if (kun) kun.soni++;
  });

  const svg = ustunGrafik(
    kunlar.map(k => ({ nom: k.nom, qiymat: k.soni })), GRAFIK_RANG[0]);

  document.getElementById('haftaBars').innerHTML = svg || boshGrafik(
    "Bu hafta ariza kelmagan",
    "Saytdan ariza kelganda kunlar bo'yicha taqsimot shu yerda ko'rinadi.",
    'ti-chart-bar');

  // Holatlar bo'yicha halqa — arizalar qaysi bosqichda turganini bir qarashda
  const holatQuti = document.getElementById('holatHalqa');
  if (holatQuti) {
    const bolaklar = Object.keys(HOLAT_NOM).map(h => ({
      nom: HOLAT_NOM[h],
      qiymat: arizalar.filter(a => a.holat === h).length,
      rang: HOLAT_RANGI[h],
    }));
    holatQuti.innerHTML = halqaGrafik(bolaklar, 'jami ariza') || boshGrafik(
      'Ariza yo\'q',
      'Arizalar kelganda ular holati bo\'yicha shu yerda taqsimlanadi.',
      'ti-chart-donut');
  }
}

const FAOLIYAT_IKON = {
  yangi: 'ti-file-plus', qabul: 'ti-user-check',
  bajarilmoqda: 'ti-progress', bajarildi: 'ti-checkbox', bekor: 'ti-x'
};

function nechaVaqtOldin(iso){
  const daqiqa = Math.floor((Date.now() - new Date(iso)) / 60000);
  if (daqiqa < 1) return 'hozirgina';
  if (daqiqa < 60) return `${daqiqa} daqiqa oldin`;
  const soat = Math.floor(daqiqa / 60);
  if (soat < 24) return `${soat} soat oldin`;
  const kun = Math.floor(soat / 24);
  return kun === 1 ? 'kecha' : `${kun} kun oldin`;
}

function faoliyatChiz(){
  const oxirgi = arizalar.slice(0, 5);
  const royxat = document.getElementById('faoliyatRoyxat');
  if (!oxirgi.length) {
    royxat.innerHTML = '<p style="color:var(--text-muted);font-size:13px;padding:8px 0;">Hozircha ariza yo\'q</p>';
    return;
  }
  royxat.innerHTML = oxirgi.map(a => `
    <div class="activity-item">
      <div class="act-icon"><i class="ti ${FAOLIYAT_IKON[a.holat] || 'ti-file'}"></i></div>
      <div>
        <p>Ariza #${a.id} — ${xavfsiz(a.xizmat_nomi)}</p>
        <span>${nechaVaqtOldin(a.yangilangan || a.yaratilgan)}</span>
      </div>
    </div>`).join('');
}

// ═══════ Arizalar ═══════
const HOLAT_NOM = {
  yangi: 'Yangi', qabul: 'Qabul qilindi', bajarilmoqda: 'Bajarilmoqda',
  bajarildi: 'Bajarildi', bekor: 'Bekor qilindi'
};
const HOLAT_RANG = {
  yangi: 'orange', qabul: 'blue', bajarilmoqda: 'blue',
  bajarildi: 'green', bekor: 'red'
};

async function arizalarYukla(){
  try {
    arizalar = await apiSorov('/buyurtmalar/');
  } catch (xato) {
    document.getElementById('arizaTana').innerHTML =
      `<tr class="holat-qator"><td colspan="7">${xavfsiz(xato.message)}</td></tr>`;
    return;
  }
  arizalarChiz();
  haftalikChiz();
  faoliyatChiz();
  kanbanChiz();
}

// ════════════════════════════════════════════════════════════════════
//  GRAFIKLAR — tashqi kutubxonasiz, sof SVG
//  Loyihada barcha resurs lokal (index.html:29), shuning uchun Chart.js
//  kabi CDN kutubxona ishlatilmaydi. Bu funksiyalar SVG matnini qaytaradi.
// ════════════════════════════════════════════════════════════════════

// Ranglar tekshiruvdan o'tgan: ranglar ko'rlikda ham ajraladi (ΔE ≥ 14).
// Tartib QAT'IY — rang ma'lumotga biriktirilgan, o'rin almashtirilmaydi.
const GRAFIK_RANG = ['#2563eb', '#0891b2', '#f59e0b', '#7c3aed', '#65a30d'];

// Ariza holatlari — bular holat ranglari, kategoriya emas: har biri
// ma'noga biriktirilgan (yashil = bajarildi) va boshqa joyda ishlatilmaydi.
const HOLAT_RANGI = {
  yangi:        '#2563eb',
  qabul:        '#0891b2',
  bajarilmoqda: '#f59e0b',
  bajarildi:    '#16a34a',
  bekor:        '#94a3b8',
};

function boshGrafik(matn, izoh, ikon){
  return `<div class="bosh-holat"><i class="ti ${ikon || 'ti-chart-bar'}"></i>
    <b>${xavfsiz(matn)}</b><span>${xavfsiz(izoh || '')}</span></div>`;
}

/* Ustunli grafik. qatorlar: [{nom, qiymat}]
   Qiymat har ustun tepasida yozib qo'yiladi — o'qish uchun y o'qi shart emas. */
function ustunGrafik(qatorlar, rang){
  if (!qatorlar.length || qatorlar.every(q => !q.qiymat)) return null;

  const EN = 560, BALAND = 200, PAST = 34, TEPA = 22;
  const eng = Math.max(...qatorlar.map(q => q.qiymat), 1);
  const kengUst = EN / qatorlar.length;
  const ustEn = Math.min(38, kengUst * 0.55);

  const ustunlar = qatorlar.map((q, i) => {
    const h = Math.round((BALAND - TEPA - PAST) * (q.qiymat / eng));
    const x = i * kengUst + (kengUst - ustEn) / 2;
    const y = BALAND - PAST - h;
    return `
      <g class="gr-ustun">
        <title>${xavfsiz(q.nom)}: ${q.qiymat}</title>
        ${h > 0 ? `<rect x="${x}" y="${y}" width="${ustEn}" height="${h}" rx="4" fill="${rang}"/>` : ''}
        <text x="${x + ustEn / 2}" y="${(h > 0 ? y : BALAND - PAST) - 6}" class="gr-son">${q.qiymat}</text>
        <text x="${x + ustEn / 2}" y="${BALAND - PAST + 17}" class="gr-belgi">${xavfsiz(q.nom)}</text>
      </g>`;
  }).join('');

  return `<svg viewBox="0 0 ${EN} ${BALAND}" class="gr-svg" role="img">
    <line x1="0" y1="${BALAND - PAST}" x2="${EN}" y2="${BALAND - PAST}" class="gr-oq"/>
    ${ustunlar}
  </svg>`;
}

/* Halqa (donut) diagramma. bolaklar: [{nom, qiymat, rang}]
   Markazda jami son — asosiy raqam darhol o'qiladi. */
function halqaGrafik(bolaklar, markazBelgi){
  const jami = bolaklar.reduce((s, b) => s + b.qiymat, 0);
  if (!jami) return null;

  const R = 62, ICH = 42, MARKAZ = 80;
  let burchak = -Math.PI / 2;   // yuqoridan boshlanadi

  const nuqta = (r, a) => [MARKAZ + r * Math.cos(a), MARKAZ + r * Math.sin(a)];

  const yoylar = bolaklar.filter(b => b.qiymat > 0).map(b => {
    const ulush = b.qiymat / jami;
    // Ikki bo'lak orasida 2px tirqish — chegara aniq ko'rinadi
    const tirqish = bolaklar.filter(x => x.qiymat > 0).length > 1 ? 0.03 : 0;
    const bosh = burchak + tirqish / 2;
    const oxir = burchak + ulush * Math.PI * 2 - tirqish / 2;
    burchak += ulush * Math.PI * 2;

    const katta = (oxir - bosh) > Math.PI ? 1 : 0;
    const [x1, y1] = nuqta(R, bosh),   [x2, y2] = nuqta(R, oxir);
    const [x3, y3] = nuqta(ICH, oxir), [x4, y4] = nuqta(ICH, bosh);

    return `<path d="M${x1} ${y1} A${R} ${R} 0 ${katta} 1 ${x2} ${y2}
      L${x3} ${y3} A${ICH} ${ICH} 0 ${katta} 0 ${x4} ${y4} Z" fill="${b.rang}">
      <title>${xavfsiz(b.nom)}: ${b.qiymat} (${Math.round(ulush * 100)}%)</title></path>`;
  }).join('');

  const izoh = bolaklar.filter(b => b.qiymat > 0).map(b => `
    <div class="gr-izoh-qator">
      <span class="gr-nuqta" style="background:${b.rang}"></span>
      <span class="gr-izoh-nom">${xavfsiz(b.nom)}</span>
      <b>${b.qiymat}</b>
    </div>`).join('');

  return `
    <div class="gr-halqa-quti">
      <svg viewBox="0 0 160 160" class="gr-halqa" role="img">
        ${yoylar}
        <text x="80" y="76" class="gr-markaz-son">${jami}</text>
        <text x="80" y="94" class="gr-markaz-belgi">${xavfsiz(markazBelgi || '')}</text>
      </svg>
      <div class="gr-izoh">${izoh}</div>
    </div>`;
}

// ═══════ Vazifalar taqsimoti (kanban) ═══════
// Ustunlar aynan shu arizalar ro'yxatidan chiziladi — alohida so'rov yo'q,
// demak jadval bilan kanban hech qachon bir-biriga zid bo'lmaydi.
function kanbanChiz(){
  const ustunlar = [
    ['yangi',        'kanbanYangi'],
    ['qabul',        'kanbanQabul'],
    ['bajarilmoqda', 'kanbanJarayon'],
    ['bajarildi',    'kanbanBajarildi'],
  ];

  ustunlar.forEach(([holat, id]) => {
    const royxat = arizalar.filter(a => a.holat === holat);
    const quti = document.getElementById(id);
    const soni = document.getElementById(id + 'Soni');
    if (soni) soni.textContent = royxat.length;
    if (!quti) return;
    quti.innerHTML = royxat.map(a => `
      <div class="kcard">
        <h5>#${a.id} · ${xavfsiz(a.xizmat_nomi)}</h5>
        <p>${xavfsiz(a.mijoz_malumot ? (a.mijoz_malumot.ism || a.mijoz_malumot.telefon) : '—')}${
          a.tuman ? ', ' + xavfsiz(a.tuman) : ''}</p>
        ${a.mijoz_malumot && a.mijoz_malumot.telefon
          ? `<p style="font-size:12px;color:var(--text-muted)">${xavfsiz(a.mijoz_malumot.telefon)}</p>` : ''}
        ${a.xodim_malumot
          ? `<p style="font-weight:700">${xavfsiz(a.xodim_malumot.ism)}</p>`
          : ''}
      </div>`).join('');
  });

  // Umuman ariza bo'lmasa — tushuntirish, aks holda uni yashiramiz
  const bosh = document.getElementById('kanbanBosh');
  if (bosh) bosh.style.display = arizalar.length ? 'none' : '';
}

// ═══════ Mijozlar (CRM) ═══════
// Ro'yxat /api/auth/mijozlar/ dan keladi. Mijoz saytda ro'yxatdan o'tganda
// avtomatik qo'shiladi — bu yerdan qo'lda kiritilmaydi.
async function mijozlarYukla(){
  const tana = document.getElementById('crmTana');
  if (!tana) return;
  let royxat;
  try {
    royxat = await apiSorov('/auth/mijozlar/');
  } catch (e) {
    tana.innerHTML = `<tr class="holat-qator"><td colspan="5">${xavfsiz(e.message)}</td></tr>`;
    return;
  }
  if (!royxat.length) {
    tana.innerHTML = '<tr class="holat-qator"><td colspan="5">' +
      'Hali mijoz ro\'yxatdan o\'tmagan</td></tr>';
    return;
  }
  tana.innerHTML = royxat.map(m => `
    <tr>
      <td>${xavfsiz(m.ism || '—')}</td>
      <td>${xavfsiz(m.telefon)}</td>
      <td>${xavfsiz(m.tuman || m.viloyat || '—')}</td>
      <td>${sanaFormat(m.yaratilgan)}</td>
      <td>${m.buyurtmalar_soni}</td>
      <td>${egasimi() ? `<button class="btn-sm" data-h-click="c:korishBoshla" data-a-click="${SG_A([Number(m.id), '@this'])}"
            title="Mijoz kabinetini uning nomidan, faqat o'qish rejimida ochadi"><i class="ti ti-eye"></i> Uning ko'zi bilan ko'rish</button>` : ''}</td>
    </tr>`).join('');
}

// ═══════ Hisobot eksporti ═══════
// Kutubxonasiz: CSV — brauzerning o'zi yaratadi, PDF — chop etish oynasi
// orqali (har bir brauzerda "PDF ga saqlash" varianti bor). Shu sababli
// serverga ham, tashqi paketga ham ehtiyoj yo'q.
let moliyaMalumot = [];   // [{nom, summa}] — moliyaYukla() to'ldiradi

function hisobotYukla(tur){
  if (!moliyaMalumot.length) { alert("Hisobot uchun ma'lumot yo'q."); return; }

  if (tur === 'csv') {
    // BOM — Excel faylni UTF-8 deb tanishi uchun, aks holda o'zbekcha
    // harflar buziladi. Ajratgich `;` — rus/o'zbek Excel shu bilan ishlaydi.
    const qatorlar = [['Xizmat turi', "Summa (so'm)"]]
      .concat(moliyaMalumot.map(m => [m.nom, m.summa]));
    const matn = '﻿' + qatorlar
      .map(q => q.map(k => `"${String(k).replace(/"/g, '""')}"`).join(';'))
      .join('\r\n');

    const havola = document.createElement('a');
    havola.href = URL.createObjectURL(new Blob([matn], { type: 'text/csv;charset=utf-8' }));
    const bugun = new Date().toISOString().slice(0, 10);
    havola.download = `soargaz-daromad-${bugun}.csv`;
    havola.click();
    URL.revokeObjectURL(havola.href);
    return;
  }

  window.print();
}

// ═══════ Faoliyat jurnali (audit) ═══════
// Yozuvlar serverda avtomatik yaratiladi, bu yerdan qo'shib bo'lmaydi.
const JURNAL_RANG = {
  kirish: 'green', kirish_xato: 'orange', kirish_blok: 'red',
  ruxsat_rad: 'red', xodim_qoshildi: 'blue', xodim_holat: 'blue',
  xodim_kod: 'blue', ariza_tayinlandi: 'blue',
  joylashuv_rozilik: 'blue', smena_boshlandi: 'green', smena_tugadi: 'gray',
  joylashuv_korildi: 'orange',
  tushum_kiritildi: 'blue', tushum_qabul: 'green', tushum_rad: 'red',
  xabar_yuborildi: 'blue', narx_ozgardi: 'orange', narx_qoshildi: 'blue',
  korish_boshlandi: 'red', korish_rad: 'orange',
};

// Buyurtmaning narx tarmog'ini (aholi / ulgurji) administrator belgilaydi: xodim faqat
// shu tarmoq narxnomalaridan xizmat tanlay oladi. Xizmatlari bor buyurtmada o'zgarmaydi.
document.addEventListener('change', async (e) => {
  const s = e.target.closest('[data-tarmoq-id]');
  if (!s) return;
  s.disabled = true;
  try {
    await apiSorov(`/buyurtmalar/${s.dataset.tarmoqId}/`, { method: 'PATCH', body: JSON.stringify({ tarmoq: s.value }) });
    jurnalYukla();
  } catch (err) {
    alert(err.message);
  }
  await arizalarYukla();     // haqiqiy holat qaytadan chiziladi (xato bo'lsa eski qiymat)
});

// ═══════ Xizmatlar narxnomasi ═══════
// /api/narxnoma/admin/ — barcha qatorlar (nofaollari ham). Xodimlar portali
// shu narxlarni faqat o'qiydi.
// Narxnomalar tarmoq (ulgurji / aholi) va bo'limlarga bo'lingan; tab orqali almashtiriladi.
let nnNomalar = [];
let nnMalumot = null;          // hozir tahrirlanayotgan narxnoma

function nnRaqam(qiymat){
  return qiymat == null ? '' : Number(qiymat).toLocaleString('ru-RU');
}
function nnSon(matn){
  const r = String(matn || '').replace(/\D/g, '');
  return r === '' ? null : Number(r);
}
function nnTarmoqQisqa(nom){ return String(nom || '').split(' (')[0]; }
// Jadval sarlavhasida ustun nomi: qisqa nom bo'lsa shu, bo'lmasa "Narx"
function nnUstunNomi(n, ustun){
  const q = ustun === 'p' ? n.ustun1_qisqa : n.ustun2_qisqa;
  return q ? q.charAt(0).toUpperCase() + q.slice(1) : (ustun === 'p' ? 'Narx' : '2-narx');
}

async function nnYukla(){
  const tana = document.getElementById('nnTana');
  try {
    nnNomalar = await apiSorov('/narxnoma/admin/');
  } catch (e) {
    tana.innerHTML = `<tr class="holat-qator"><td colspan="9">${xavfsiz(e.message)}</td></tr>`;
    return;
  }
  // Oldingi narxnoma saqlanadi, bo'lmasa narxi borligi, bo'lmasa birinchisi
  const joriy = nnMalumot && nnNomalar.find(n => n.id === nnMalumot.id);
  nnTanla(joriy || nnNomalar.find(n => n.qatorlar.length) || nnNomalar[0] || null);
}

function nnTabChiz(){
  const tarmoqlar = [];
  nnNomalar.forEach(n => { if (!tarmoqlar.includes(n.tarmoq)) tarmoqlar.push(n.tarmoq); });
  document.getElementById('nnTarmoqTab').innerHTML = tarmoqlar.map(t =>
    `<button type="button" class="narx-tab-btn${nnMalumot && nnMalumot.tarmoq === t ? ' active' : ''}" data-tarmoq="${xavfsiz(t)}">${
      xavfsiz(nnTarmoqQisqa(nnNomalar.find(n => n.tarmoq === t).tarmoq_nomi))}</button>`).join('');
  const bolimlar = nnMalumot ? nnNomalar.filter(n => n.tarmoq === nnMalumot.tarmoq) : [];
  document.getElementById('nnBolimTab').innerHTML = bolimlar.length > 1 ? bolimlar.map(n =>
    `<button type="button" class="narx-tab-btn sub${n.id === nnMalumot.id ? ' active' : ''}" data-narxnoma="${Number(n.id)}">${xavfsiz(n.bolim_nomi)}</button>`
  ).join('') : '';
}

function nnTanla(n){
  nnMalumot = n;
  const tana = document.getElementById('nnTana');
  if (!n) {
    document.getElementById('nnSub').textContent = 'Narxnoma yaratilmagan (Django panelidan qo\'shing)';
    document.getElementById('nnThead').innerHTML = '';
    document.getElementById('nnTarmoqTab').innerHTML = document.getElementById('nnBolimTab').innerHTML = '';
    tana.innerHTML = '<tr class="holat-qator"><td colspan="9">Narxnoma yo\'q</td></tr>';
    return;
  }
  document.getElementById('nnSub').textContent = `${nnTarmoqQisqa(n.tarmoq_nomi)} · ${n.bolim_nomi}`;
  document.getElementById('nnSarlavha').value = n.sarlavha || '';
  document.getElementById('nnU1').value = n.ustun1 || '';
  document.getElementById('nnU1q').value = n.ustun1_qisqa || '';
  document.getElementById('nnU2').value = n.ustun2 || '';
  document.getElementById('nnU2q').value = n.ustun2_qisqa || '';
  document.getElementById('nnEslatma').value = n.eslatma || '';
  // Xizmat qo'shish formasi: 2-narx faqat ikki ustunli narxnomada
  document.getElementById('nnYPdLabel').textContent = `${nnUstunNomi(n, 'p')} (so'm)`;
  document.getElementById('nnYRdLabel').textContent = `${nnUstunNomi(n, 'r')} (so'm)`;
  document.getElementById('nnYRdWrap').style.display = n.ustun2 ? '' : 'none';
  nnTabChiz();
  nnChiz();
}

document.getElementById('nnTarmoqTab').addEventListener('click', (e) => {
  const b = e.target.closest('[data-tarmoq]');
  if (!b) return;
  const n = nnNomalar.find(x => x.tarmoq === b.dataset.tarmoq && x.qatorlar.length) ||
            nnNomalar.find(x => x.tarmoq === b.dataset.tarmoq);
  if (n) nnTanla(n);
});
document.getElementById('nnBolimTab').addEventListener('click', (e) => {
  const b = e.target.closest('[data-narxnoma]');
  const n = b && nnNomalar.find(x => x.id === Number(b.dataset.narxnoma));
  if (n) nnTanla(n);
});

function nnChiz(){
  const tana = document.getElementById('nnTana');
  const n = nnMalumot;
  const ikki = !!n.ustun2;
  const ustunlar = 7 + (ikki ? 2 : 0);
  document.getElementById('nnThead').innerHTML = `<tr><th>№</th><th>Xizmat nomi</th>
    <th>${xavfsiz(nnUstunNomi(n, 'p'))} (dan)</th><th>(gacha)</th>
    ${ikki ? `<th>${xavfsiz(nnUstunNomi(n, 'r'))} (dan)</th><th>(gacha)</th>` : ''}
    <th>Izoh</th><th>Faol</th><th></th></tr>`;
  const q = document.getElementById('nnQidir').value.trim().toLowerCase();
  const royxat = n.qatorlar.filter(r => !q || r.nomi.toLowerCase().includes(q) || String(r.tartib) === q);
  const kat = (maydon, qiymat) => `<input class="f-input" data-f="${maydon}" inputmode="numeric"
      style="margin:0;padding:6px 8px;width:105px;" value="${xavfsiz(nnRaqam(qiymat))}">`;
  tana.innerHTML = royxat.length ? royxat.map(r => `
    <tr data-id="${Number(r.id)}" style="${r.faol ? '' : 'opacity:.55'}">
      <td><input class="f-input" data-f="tartib" inputmode="numeric" style="margin:0;padding:6px 8px;width:56px;" value="${Number(r.tartib)}"></td>
      <td><input class="f-input" data-f="nomi" maxlength="400" style="margin:0;padding:6px 8px;min-width:260px;" value="${xavfsiz(r.nomi).replace(/"/g, '&quot;')}"></td>
      <td>${kat('p_dan', r.p_dan)}</td><td>${kat('p_gacha', r.p_gacha)}</td>
      ${ikki ? `<td>${kat('r_dan', r.r_dan)}</td><td>${kat('r_gacha', r.r_gacha)}</td>` : ''}
      <td><input class="f-input" data-f="izoh" maxlength="255" style="margin:0;padding:6px 8px;min-width:150px;" value="${xavfsiz(r.izoh).replace(/"/g, '&quot;')}"></td>
      <td><input type="checkbox" data-f="faol" ${r.faol ? 'checked' : ''}></td>
      <td style="white-space:nowrap"><button class="btn-sm ok" data-nn-saqla>Saqlash</button>
        <span class="nn-holat" style="font-size:12px;font-weight:600;margin-left:6px;"></span></td>
    </tr>`).join('') : `<tr class="holat-qator"><td colspan="${ustunlar}">${
      n.qatorlar.length ? 'Hech narsa topilmadi' : "Bu bo'limda narxlar hali kiritilmagan. Quyidagi forma orqali xizmat qo'shing."}</td></tr>`;
}

document.getElementById('nnQidir').addEventListener('input', () => { if (nnMalumot) nnChiz(); });

document.getElementById('nnTana').addEventListener('click', async (e) => {
  const b = e.target.closest('[data-nn-saqla]');
  if (!b) return;
  const tr = b.closest('tr');
  const holat = tr.querySelector('.nn-holat');
  const f = (m) => tr.querySelector(`[data-f="${m}"]`);
  const tana = {
    tartib: nnSon(f('tartib').value), nomi: f('nomi').value,
    p_dan: nnSon(f('p_dan').value), p_gacha: nnSon(f('p_gacha').value),
    izoh: f('izoh').value, faol: f('faol').checked,
  };
  if (nnMalumot.ustun2) {          // 2-narx ustuni faqat ikki ustunli narxnomada bor
    tana.r_dan = nnSon(f('r_dan').value);
    tana.r_gacha = nnSon(f('r_gacha').value);
  }
  b.disabled = true;
  holat.textContent = '';
  try {
    const y = await apiSorov(`/narxnoma/qator/${tr.dataset.id}/`, { method: 'PATCH', body: JSON.stringify(tana) });
    const i = nnMalumot.qatorlar.findIndex(r => r.id === y.id);
    if (i >= 0) nnMalumot.qatorlar[i] = y;
    holat.style.color = 'var(--green)';
    holat.textContent = 'Saqlandi';
    tr.style.opacity = y.faol ? '' : '.55';
    jurnalYukla();
  } catch (err) {
    holat.style.color = 'var(--red)';
    holat.textContent = err.message;
  } finally {
    b.disabled = false;
  }
});

document.getElementById('nnSarlavhaSaqla').addEventListener('click', async () => {
  const xabar = document.getElementById('nnSarlavhaXabar');
  try {
    const y = await apiSorov(`/narxnoma/${nnMalumot.id}/`, { method: 'PATCH', body: JSON.stringify({
      sarlavha: document.getElementById('nnSarlavha').value,
      ustun1: document.getElementById('nnU1').value,
      ustun1_qisqa: document.getElementById('nnU1q').value,
      ustun2: document.getElementById('nnU2').value,
      ustun2_qisqa: document.getElementById('nnU2q').value,
      eslatma: document.getElementById('nnEslatma').value }) });
    const i = nnNomalar.findIndex(n => n.id === y.id);
    if (i >= 0) nnNomalar[i] = y;
    nnTanla(y);
    xabar.style.color = 'var(--green)'; xabar.textContent = 'Saqlandi';
    jurnalYukla();
  } catch (err) { xabar.style.color = 'var(--red)'; xabar.textContent = err.message; }
});

document.getElementById('nnYQosh').addEventListener('click', async () => {
  const xato = document.getElementById('nnYXato');
  xato.style.display = 'none';
  try {
    await apiSorov(`/narxnoma/${nnMalumot.id}/qator/`, { method: 'POST', body: JSON.stringify({
      nomi: document.getElementById('nnYNomi').value,
      p_dan: nnSon(document.getElementById('nnYPd').value),
      ...(nnMalumot.ustun2 ? { r_dan: nnSon(document.getElementById('nnYRd').value) } : {}) }) });
    ['nnYNomi', 'nnYPd', 'nnYRd'].forEach(id => { document.getElementById(id).value = ''; });
    await nnYukla();
    jurnalYukla();
  } catch (err) { xato.textContent = err.message; xato.style.display = 'block'; }
});

// ═══════ Xodimlarga xabar ═══════
function xabarXodimlarChiz(){
  const faol = xodimlar.filter(x => x.holat === 'faol');
  document.getElementById('xabarXodimlar').innerHTML = faol.length
    ? faol.map(x => `<label style="display:flex;gap:8px;align-items:center;">
        <input type="checkbox" data-xabar-xodim="${Number(x.id)}"> ${xavfsiz(x.ism || x.telefon)}</label>`).join('')
    : '<span style="color:var(--text-muted);font-size:13px">Faol xodim yo\'q</span>';
}

async function xabarTarixiYukla(){
  const tana = document.getElementById('xabarTana');
  try {
    const r = await apiSorov('/aloqa/admin/');
    tana.innerHTML = r.length
      ? r.map(x => `<tr>
          <td style="white-space:nowrap">${vaqtFormat(x.yaratilgan)}</td>
          <td>${xavfsiz(x.xodim_ism)}</td>
          <td>${xavfsiz(x.matn)}</td>
          <td><span class="tag ${x.oqilgan ? 'green' : 'gray'}">${x.oqilgan ? "O'qilgan" : "O'qilmagan"}</span></td>
        </tr>`).join('')
      : '<tr class="holat-qator"><td colspan="4">Hali xabar yuborilmagan</td></tr>';
  } catch (e) {
    tana.innerHTML = `<tr class="holat-qator"><td colspan="4">${xavfsiz(e.message)}</td></tr>`;
  }
}

function xabarSahifasiOchildi(){
  xabarXodimlarChiz();
  xabarTarixiYukla();
}

document.getElementById('xabarMatn').addEventListener('input', (e) => {
  document.getElementById('xabarSanoq').textContent = `${e.target.value.length}/500`;
});
document.getElementById('xabarHammasi').addEventListener('change', (e) => {
  document.querySelectorAll('[data-xabar-xodim]').forEach(c => { c.checked = false; c.disabled = e.target.checked; });
});

document.getElementById('xabarForm').addEventListener('submit', async (e) => {
  e.preventDefault();
  const xato = document.getElementById('xabarXato');
  const btn = document.getElementById('xabarBtn');
  xato.style.display = 'none';
  const hammasi = document.getElementById('xabarHammasi').checked;
  const idlar = [...document.querySelectorAll('[data-xabar-xodim]:checked')].map(c => Number(c.dataset.xabarXodim));
  if (!hammasi && !idlar.length) {
    xato.textContent = 'Kimga yuborilishini tanlang'; xato.style.display = 'block'; return;
  }
  btn.disabled = true;
  try {
    const r = await apiSorov('/aloqa/admin/', { method: 'POST', body: JSON.stringify({
      matn: document.getElementById('xabarMatn').value, hammasi: hammasi ? true : undefined,
      xodimlar: hammasi ? undefined : idlar }) });
    document.getElementById('xabarMatn').value = '';
    document.getElementById('xabarSanoq').textContent = '0/500';
    xato.textContent = `Yuborildi: ${r.yuborildi} ta xodimga`;
    xato.style.color = 'var(--green)'; xato.style.display = 'block';
    xabarTarixiYukla();
  } catch (err) {
    xato.textContent = err.message; xato.style.color = ''; xato.style.display = 'block';
  } finally {
    btn.disabled = false;
  }
});

// ═══════ Xodimlar tushumi ═══════
// Xodim mijozdan olgan pulni kiritadi; bu yerda administrator pulni qo'liga
// olgach qabul qiladi yoki sabab bilan rad etadi (/api/tushum/).
const TUSHUM_RANG = { kutilmoqda: 'orange', qabul: 'green', rad: 'red' };

async function tushumYukla(){
  const tana = document.getElementById('tushTana');
  const filtr = document.getElementById('tushFiltr').value;
  const tarmoqFiltr = document.getElementById('tushTarmoqFiltr').value;
  const parametrlar = [filtr && `holat=${filtr}`, tarmoqFiltr && `tarmoq=${tarmoqFiltr}`].filter(Boolean).join('&');
  let r;
  try {
    r = await apiSorov('/tushum/admin/' + (parametrlar ? `?${parametrlar}` : ''));
  } catch (e) {
    tana.innerHTML = `<tr class="holat-qator"><td colspan="7">${xavfsiz(e.message)}</td></tr>`;
    return;
  }

  // Tarmoqlar bo'yicha kartalar (aholi / ulgurji / turkumsiz), filtrdan mustaqil
  const tartib = ['aholi', 'ulgurji', 'boshqa'];
  const kartalar = Object.entries(r.tarmoq_jami || {})
    .sort((a, b) => tartib.indexOf(a[0]) - tartib.indexOf(b[0]))
    .map(([, t]) => `
      <div class="card" style="margin:0;padding:14px 16px;background:var(--bg-bottom,#f8fafc);">
        <p style="margin:0 0 8px;font-weight:800;">${xavfsiz(nnTarmoqQisqa(t.nomi))}</p>
        <p style="margin:0;font-size:12px;color:var(--text-muted)">Topshirilishi kutilmoqda</p>
        <p style="margin:0 0 6px;font-weight:700;color:${t.kutilmoqda ? 'var(--orange)' : 'inherit'}">${pulFormat(t.kutilmoqda)}</p>
        <p style="margin:0;font-size:12px;color:var(--text-muted)">Bu oy qabul qilingan</p>
        <p style="margin:0 0 6px;font-weight:700;">${pulFormat(t.oy_qabul)}</p>
        <p style="margin:0;font-size:12px;color:var(--text-muted)">Jami qabul qilingan</p>
        <p style="margin:0;font-weight:700;">${pulFormat(t.qabul)}</p>
      </div>`).join('');
  document.getElementById('tushTarmoqKartalar').innerHTML = kartalar
    || '<span style="color:var(--text-muted);font-size:13px">Hali tushum kiritilmagan</span>';

  const jami = r.xodimlar.reduce((s, x) => s + x.kutilmoqda_summa, 0);
  const soni = r.xodimlar.reduce((s, x) => s + x.kutilmoqda_soni, 0);
  document.getElementById('tushSoni').textContent = soni
    ? `Qabul qilinishi kutilmoqda: ${soni} ta yozuv, jami ${pulFormat(jami)}`
    : 'Kutilayotgan tushum yo\'q';
  const belgi = document.getElementById('tushBelgi');
  belgi.textContent = soni;
  belgi.style.display = soni ? 'inline-block' : 'none';

  document.getElementById('tushXodimTana').innerHTML = r.xodimlar.length
    ? r.xodimlar.map(x => `
      <tr>
        <td>${xavfsiz(x.ism)}</td>
        <td><b style="color:${x.kutilmoqda_summa ? 'var(--orange)' : 'inherit'}">${pulFormat(x.kutilmoqda_summa)}</b></td>
        <td>${pulFormat(x.oy_summa)}</td>
        <td>${pulFormat(x.qabul_summa)}</td>
      </tr>`).join('')
    : '<tr class="holat-qator"><td colspan="4">Hali tushum kiritilmagan</td></tr>';

  tana.innerHTML = r.yozuvlar.length
    ? r.yozuvlar.map(t => `
      <tr>
        <td style="white-space:nowrap">${vaqtFormat(t.yaratilgan)}</td>
        <td>${xavfsiz(t.xodim_ism)}</td>
        <td><b>${pulFormat(t.summa)}</b>${t.ish_turi ? `<br><span style="font-size:12px">${xavfsiz(t.ish_turi)}</span>` : ''}${t.izoh ?`<br><span style="color:var(--text-muted);font-size:12px">${xavfsiz(t.izoh)}</span>` : ''}</td>
        <td>${xavfsiz(t.usul_nomi)}</td>
        <td>${xavfsiz(t.buyurtma_nomi || '—')}${t.tarmoq
          ? `<br><span style="font-size:11px;color:var(--text-muted)">${xavfsiz(nnTarmoqQisqa(t.tarmoq_nomi))}${t.bolim_nomi ? ' · ' + xavfsiz(t.bolim_nomi) : ''}</span>` : ''}</td>
        <td><span class="tag ${TUSHUM_RANG[t.holat] || 'gray'}">${xavfsiz(t.holat_nomi)}</span>${t.rad_sababi ? `<br><span style="color:var(--red);font-size:12px">${xavfsiz(t.rad_sababi)}</span>` : ''}</td>
        <td style="white-space:nowrap">${t.holat === 'kutilmoqda'
          ? `<button class="btn-sm ok" data-tushum-qabul="${t.id}">Qabul qilish</button>
             <button class="btn-sm danger" data-tushum-rad="${t.id}">Rad etish</button>` : ''}</td>
      </tr>`).join('')
    : '<tr class="holat-qator"><td colspan="7">Yozuv yo\'q</td></tr>';
}

document.getElementById('tushFiltr').addEventListener('change', tushumYukla);
document.getElementById('tushTarmoqFiltr').addEventListener('change', tushumYukla);

document.getElementById('tushTana').addEventListener('click', async (e) => {
  const b = e.target.closest('button');
  if (!b) return;
  const qabul = b.dataset.tushumQabul, rad = b.dataset.tushumRad;
  if (!qabul && !rad) return;
  try {
    if (qabul) {
      if (!confirm('Pulni qo\'lingizga oldingizmi? Qabul qilishni qaytarib bo\'lmaydi.')) return;
      b.disabled = true;
      await apiSorov(`/tushum/${qabul}/qabul/`, { method: 'POST' });
    } else {
      const sabab = (prompt('Rad etish sababini yozing:') || '').trim();
      if (!sabab) return;
      b.disabled = true;
      await apiSorov(`/tushum/${rad}/rad/`, { method: 'POST', body: JSON.stringify({ sabab }) });
    }
  } catch (err) {
    alert(err.message);
  }
  tushumYukla();
  jurnalYukla();
});

// ═══════ Parolni ko'rib tekshirish (ko'zcha) ═══════
// Parol faqat shu qurilma ekranida ochiladi, hech qayerga yuborilmaydi. Kirish urinishidan
// keyin (va chiqishda) maydon tozalanadi va parol yana yashirinadi.
function parolniYashir(){
  const inp = document.getElementById('loginParol');
  const btn = document.getElementById('parolKozcha');
  if (!inp || !btn) return;
  inp.type = 'password';
  btn.setAttribute('aria-pressed', 'false');
  btn.setAttribute('aria-label', "Parolni ko'rsatish");
  btn.title = "Parolni ko'rsatish";
  btn.querySelector('.kz-och').style.display = '';
  btn.querySelector('.kz-yop').style.display = 'none';
}
document.getElementById('parolKozcha').addEventListener('click', () => {
  const inp = document.getElementById('loginParol');
  const ochiq = inp.type === 'password';
  inp.type = ochiq ? 'text' : 'password';
  const btn = document.getElementById('parolKozcha');
  btn.setAttribute('aria-pressed', String(ochiq));
  btn.setAttribute('aria-label', ochiq ? 'Parolni yashirish' : "Parolni ko'rsatish");
  btn.title = ochiq ? 'Parolni yashirish' : "Parolni ko'rsatish";
  btn.querySelector('.kz-och').style.display = ochiq ? 'none' : '';
  btn.querySelector('.kz-yop').style.display = ochiq ? '' : 'none';
  inp.focus();
});

// ═══════ Rahbariyat bosh sahifasi ═══════
// /api/auth/rahbariyat/ — faqat o'qish; boshqa sahifalardagi ma'lumotdan yig'ilgan umumiy ko'rinish.
// Har daqiqada yangilanadi (bu foydalanuvchi harakati hisoblanmaydi — sessiya baribir tugaydi).
let rahTaymer = null;

function sahifaniQoy(kalit){
  document.querySelectorAll('.sb-item[data-page]').forEach(b => b.classList.toggle('active', b.dataset.page === kalit));
  document.querySelectorAll('.page').forEach(p => p.classList.toggle('active', p.id === 'page-' + kalit));
}

const RAH_TARMOQ = { aholi: 'Aholi', ulgurji: 'Ulgurji' };
const RAH_HOLAT = { yangi: 'Yangi', qabul: 'Qabul qilingan', bajarilmoqda: 'Bajarilmoqda', bajarildi: 'Bajarilgan', bekor: 'Bekor' };

async function rahbariyatYukla(){
  if (!token) return;
  let r;
  try {
    r = await apiSorov('/auth/rahbariyat/');
  } catch (e) {
    document.getElementById('rahDiqqat').innerHTML = `<p class="bosh-holat" style="padding:10px 0;margin:0;">${xavfsiz(e.message)}</p>`;
    return;
  }

  // Diqqat talab qiladi: har qator tegishli sahifaga olib boradi
  document.getElementById('rahDiqqat').innerHTML = r.diqqat.length ? r.diqqat.map(d => `
    <div class="rah-diqqat ${xavfsiz(d.daraja)}" data-sahifa="${xavfsiz(d.sahifa)}" role="button" tabindex="0">
      <i class="ti ${d.daraja === 'qizil' ? 'ti-alert-triangle' : (d.daraja === 'sariq' ? 'ti-alert-circle' : 'ti-info-circle')}"></i>
      <span>${xavfsiz(d.matn)}</span><i class="ti ti-chevron-right" style="margin-left:auto;"></i>
    </div>`).join('')
    : '<p style="margin:0;color:var(--green);font-weight:700;"><i class="ti ti-circle-check"></i> Hammasi joyida: e\'tibor talab qiladigan holat yo\'q</p>';

  // Tushum: tarmoqlar bo'yicha
  const t = r.tushum;
  const jamiKutilmoqda = t.aholi.kutilmoqda + t.ulgurji.kutilmoqda + t.boshqa.kutilmoqda;
  const jamiQoldiq = r.buyurtmalar.qoldiq.aholi + r.buyurtmalar.qoldiq.ulgurji;
  const tile = (n, l, sub) => `<div class="stat-box"><p class="n">${n}</p><p class="l">${xavfsiz(l)}</p>${
    sub ? `<p class="l" style="font-weight:400;opacity:.8;margin-top:2px;">${xavfsiz(sub)}</p>` : ''}</div>`;
  document.getElementById('rahTushum').innerHTML = [
    tile(pulFormat(t.aholi.oy_qabul), 'Aholi: qabul qilingan', `topshirilishi kutilmoqda: ${pulFormat(t.aholi.kutilmoqda)}`),
    tile(pulFormat(t.ulgurji.oy_qabul), 'Ulgurji: qabul qilingan', `topshirilishi kutilmoqda: ${pulFormat(t.ulgurji.kutilmoqda)}`),
    tile(pulFormat(jamiKutilmoqda), 'Topshirilishi kutilayotgan pul', 'xodimlarda turibdi'),
    tile(pulFormat(jamiQoldiq), 'Mijozlardan olinmagan qoldiq', 'tasdiqlangan summadan'),
  ].join('');

  // Buyurtmalar
  const h = r.buyurtmalar.holatlar;
  const satr = (nom, qiymat) => `<div class="rah-satr"><span>${xavfsiz(nom)}</span><b>${qiymat}</b></div>`;
  document.getElementById('rahBuyurtma').innerHTML =
    Object.keys(RAH_HOLAT).map(k => satr(RAH_HOLAT[k], h[k] || 0)).join('') +
    satr('Xodim tayinlanmagan (yangi)', r.buyurtmalar.tayinlanmagan) +
    satr('Bu oy tasdiqlangan: aholi', pulFormat(r.buyurtmalar.oy_tasdiqlangan.aholi)) +
    satr('Bu oy tasdiqlangan: ulgurji', pulFormat(r.buyurtmalar.oy_tasdiqlangan.ulgurji));

  // Xodimlar
  const x = r.xodimlar;
  document.getElementById('rahXodim').innerHTML =
    satr('Faol xodimlar', x.faol) + satr('Hozir smenada', x.smenada) +
    satr('Aloqada', `<span style="color:var(--green)">${x.aloqada}</span>`) +
    satr('Aloqada emas', `<span style="color:${x.aloqasiz ? 'var(--red)' : 'inherit'}">${x.aloqasiz}</span>`);

  // Kim qancha pul topshirmagan
  document.getElementById('rahQarz').innerHTML = r.qarzdorlar.length ? r.qarzdorlar.map(q => `
    <tr>
      <td>${xavfsiz(q.ism)}</td>
      <td><b style="color:${q.eski ? 'var(--red)' : 'inherit'}">${pulFormat(q.summa)}</b></td>
      <td>${q.soni} ta</td>
      <td>${q.kun === 0 ? 'bugun' : q.kun + ' kun oldin'}</td>
    </tr>`).join('')
    : '<tr class="holat-qator"><td colspan="4">Topshirilmagan pul yo\'q</td></tr>';

  // So'nggi faoliyat
  document.getElementById('rahFaoliyat').innerHTML = r.faoliyat.length ? r.faoliyat.map(f => `
    <div class="rah-satr" style="align-items:flex-start;flex-direction:column;gap:2px;">
      <span><b>${xavfsiz(f.kim)}</b>: ${xavfsiz(f.amal)}</span>
      <span style="font-size:12px;color:var(--text-muted);">${xavfsiz(f.tafsilot || '')} · ${nechaVaqtOldin(f.vaqt)}</span>
    </div>`).join('')
    : '<p class="bosh-holat" style="padding:10px 0;margin:0;">Faoliyat yo\'q</p>';
}

function rahSahifasiOchildi(){
  rahbariyatYukla();
  clearInterval(rahTaymer);
  rahTaymer = setInterval(rahbariyatYukla, 60000);
}
function rahSahifasiYopildi(){
  clearInterval(rahTaymer);
  rahTaymer = null;
}

// "Diqqat talab qiladi" qatorini bossa tegishli sahifaga o'tadi
document.getElementById('rahDiqqat').addEventListener('click', (e) => {
  const q = e.target.closest('[data-sahifa]');
  const btn = q && document.querySelector(`.sb-item[data-page="${q.dataset.sahifa}"]`);
  if (btn) btn.click();
});
document.getElementById('rahDiqqat').addEventListener('keydown', (e) => {
  if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); e.target.click(); }
});

// ═══════ Xodimlar xaritasi ═══════
// Ma'lumot /api/joylashuv/royxat/ dan keladi: faqat smenasi ochiq xodimlar.
// Sahifa ochiq turgandagina 15 soniyada bir yangilanadi.
let joyXarita = null, joyBelgilar = {}, joyYol = null, joyTaymer = null;
let joyTanlangan = null, joyMalumot = [];

function joyXaritaTayyor(){
  if (joyXarita || typeof L === 'undefined') return !!joyXarita;
  joyXarita = L.map('joyXarita').setView([41.3111, 69.2797], 11);   // Toshkent
  L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
    maxZoom: 19, attribution: '© OpenStreetMap',
  }).addTo(joyXarita);
  return true;
}

async function joyYukla(){
  const tana = document.getElementById('joyTana');
  if (!tana) return;
  let royxat;
  try {
    royxat = await apiSorov('/joylashuv/royxat/');
  } catch (e) {
    tana.innerHTML = `<tr class="holat-qator"><td colspan="6">${xavfsiz(e.message)}</td></tr>`;
    return;
  }
  joyMalumot = royxat;
  document.getElementById('joySoni').textContent = royxat.length
    ? `Hozir smenada: ${royxat.length} ta xodim`
    : "Hozir smenada xodim yo'q";
  joyChiz();
}

function joyChiz(){
  const tana = document.getElementById('joyTana');
  if (!joyMalumot.length) {
    tana.innerHTML = '<tr class="holat-qator"><td colspan="6">Hozir smenada xodim yo\'q</td></tr>';
  } else {
    tana.innerHTML = joyMalumot.map(x => `
      <tr class="${x.xodim_id === joyTanlangan ? 'joy-tanlangan' : ''}">
        <td>${xavfsiz(x.ism)}<br><span style="color:var(--text-muted);font-size:12px">${xavfsiz(x.telefon)}</span></td>
        <td>${xavfsiz(x.lavozim || '—')}</td>
        <td style="white-space:nowrap">${vaqtFormat(x.smena_boshlandi)}</td>
        <td style="white-space:nowrap">${x.oxirgi_vaqt ? nechaVaqtOldin(x.oxirgi_vaqt) : '—'}</td>
        <td><span class="tag ${x.aloqada ? 'green' : 'red'}">${x.aloqada ? 'Aloqada' : 'Aloqada emas'}</span></td>
        <td style="white-space:nowrap">
          <button class="btn-sm" data-joy-korish="${x.xodim_id}" ${x.lat == null ? 'disabled' : ''}>Xaritada</button>
          <button class="btn-sm" data-joy-yol="${x.xodim_id}">Yo'l (8 soat)</button>
        </td>
      </tr>`).join('');
  }
  if (!joyXaritaTayyor()) return;

  const bor = new Set();
  joyMalumot.forEach(x => {
    if (x.lat == null) return;
    bor.add(x.xodim_id);
    const rang = x.aloqada ? '#16a34a' : '#94a3b8';
    let b = joyBelgilar[x.xodim_id];
    if (!b) {
      b = joyBelgilar[x.xodim_id] = L.circleMarker([x.lat, x.lng], { radius: 9, weight: 3, color: '#fff', fillOpacity: 1 }).addTo(joyXarita);
    }
    b.setLatLng([x.lat, x.lng]).setStyle({ fillColor: rang });
    b.bindTooltip(`${xavfsiz(x.ism)} — ${x.aloqada ? 'aloqada' : 'aloqada emas'}`);
  });
  Object.keys(joyBelgilar).forEach(id => {
    if (!bor.has(Number(id))) { joyXarita.removeLayer(joyBelgilar[id]); delete joyBelgilar[id]; }
  });
}

async function joyYoliniChiz(id){
  if (!joyXaritaTayyor()) return;
  try {
    const r = await apiSorov(`/joylashuv/yol/${id}/?soat=8`);
    if (joyYol) joyXarita.removeLayer(joyYol);
    const nuqtalar = r.nuqtalar.map(n => [n.lat, n.lng]);
    if (!nuqtalar.length) { alert('So\'nggi 8 soatda nuqta yo\'q'); return; }
    joyYol = L.polyline(nuqtalar, { color: '#2563eb', weight: 4 }).addTo(joyXarita);
    joyXarita.fitBounds(joyYol.getBounds(), { padding: [30, 30] });
  } catch (e) { alert(e.message); }
}

document.getElementById('joyTana').addEventListener('click', (e) => {
  const b = e.target.closest('button');
  if (!b) return;
  if (b.dataset.joyKorish) {
    const id = Number(b.dataset.joyKorish);
    joyTanlangan = id;
    const m = joyBelgilar[id];
    if (m && joyXaritaTayyor()) joyXarita.setView(m.getLatLng(), 16);
    joyChiz();
  } else if (b.dataset.joyYol) {
    joyYoliniChiz(Number(b.dataset.joyYol));
  }
});

// Faqat xarita sahifasi ochiq bo'lganda yangilanadi — boshqa bo'limda ma'lumot
// so'ralmaydi va jurnalga ortiqcha yozuv tushmaydi.
function joySahifasiOchildi(){
  joyXaritaTayyor();
  joyYukla();
  setTimeout(() => joyXarita && joyXarita.invalidateSize(), 50);
  clearInterval(joyTaymer);
  joyTaymer = setInterval(joyYukla, 15000);
}
function joySahifasiYopildi(){
  clearInterval(joyTaymer);
  joyTaymer = null;
}

function vaqtFormat(iso){
  const d = new Date(iso);
  if (isNaN(d)) return '—';
  const ikki = n => String(n).padStart(2, '0');
  return `${ikki(d.getDate())}.${ikki(d.getMonth() + 1)}.${d.getFullYear()}, ${ikki(d.getHours())}:${ikki(d.getMinutes())}`;
}

async function jurnalYukla(){
  const tana = document.getElementById('jurnalTana');
  if (!tana) return;
  let royxat;
  try {
    royxat = await apiSorov('/auth/jurnal/');
  } catch (e) {
    tana.innerHTML = `<tr class="holat-qator"><td colspan="5">${xavfsiz(e.message)}</td></tr>`;
    return;
  }
  if (!royxat.length) {
    tana.innerHTML = '<tr class="holat-qator"><td colspan="5">Jurnal bo\'sh</td></tr>';
    return;
  }
  tana.innerHTML = royxat.map(y => `
    <tr>
      <td style="white-space:nowrap">${vaqtFormat(y.vaqt)}</td>
      <td>${xavfsiz(y.kim)}</td>
      <td><span class="tag ${JURNAL_RANG[y.amal] || 'gray'}">${xavfsiz(y.amal_nomi)}</span></td>
      <td>${xavfsiz(y.tafsilot || '—')}</td>
      <td style="color:var(--text-muted)">${xavfsiz(y.ip || '—')}</td>
    </tr>`).join('');
}

// ═══════ Moliya ═══════
// Barcha raqam to'lov so'rovlaridan hisoblanadi (/api/tolovlar/).
// Hech qanday summa qo'lda yozilmaydi.
function pulFormat(son){
  return (son || 0).toLocaleString('ru-RU').replace(/ /g, ' ') + " so'm";
}

async function moliyaYukla(){
  const quti = document.getElementById('molXizmatlar');
  if (!quti) return;
  let sorovlar;
  try {
    sorovlar = await apiSorov('/tolovlar/');
  } catch (e) {
    quti.innerHTML = `<div class="bosh-holat"><b>${xavfsiz(e.message)}</b></div>`;
    return;
  }

  const tolangan = sorovlar.filter(s => s.holat === 'tolandi');
  const kutilmoqda = sorovlar.filter(s => s.holat === 'kutilmoqda');
  const hozir = new Date();

  const jami = tolangan.reduce((s, t) => s + (t.summa || 0), 0);
  const oylik = tolangan.reduce((s, t) => {
    const d = new Date(t.yaratilgan);
    return (d.getFullYear() === hozir.getFullYear() && d.getMonth() === hozir.getMonth())
      ? s + (t.summa || 0) : s;
  }, 0);

  document.getElementById('molJami').textContent  = pulFormat(jami);
  document.getElementById('molOy').textContent    = pulFormat(oylik);
  document.getElementById('molKutil').textContent =
    pulFormat(kutilmoqda.reduce((s, t) => s + (t.summa || 0), 0));
  document.getElementById('molSoni').textContent  = tolangan.length;

  // Xizmat turi bo'yicha taqsimot
  const guruh = {};
  tolangan.forEach(t => {
    const nom = t.xizmat_turi || 'Boshqa';
    guruh[nom] = (guruh[nom] || 0) + (t.summa || 0);
  });
  const qatorlar = Object.entries(guruh).sort((a, b) => b[1] - a[1]);

  if (!qatorlar.length) {
    quti.innerHTML = `
      <div class="bosh-holat">
        <i class="ti ti-report-money"></i>
        <b>To'langan buyurtma yo'q</b>
        <span>Daromad to'lov so'rovlaridan hisoblanadi. To'lov "To'landi"
              holatiga o'tgach, raqamlar shu yerda paydo bo'ladi.</span>
      </div>`;
    return;
  }

  moliyaMalumot = qatorlar.map(([nom, summa]) => ({ nom, summa }));

  const eng = qatorlar[0][1] || 1;
  quti.innerHTML = qatorlar.map(([nom, summa]) => `
    <div class="hbar-row">
      <div class="hbar-top"><span>${xavfsiz(nom)}</span><b>${pulFormat(summa)}</b></div>
      <div class="hbar-track"><div class="hbar-fill" style="width:${Math.round(summa / eng * 100)}%"></div></div>
    </div>`).join('');

  // Halqa: xizmat turlari ulushi. 5 tadan ortig'i "Boshqa" ga yig'iladi —
  // rang ro'yxati cheklangan, yangi rang o'ylab topilmaydi.
  const halqaQuti = document.getElementById('molHalqa');
  if (halqaQuti) {
    const asosiy = qatorlar.slice(0, 4).map(([nom, summa], i) => ({
      nom, qiymat: summa, rang: GRAFIK_RANG[i],
    }));
    const qolgan = qatorlar.slice(4).reduce((s, [, v]) => s + v, 0);
    if (qolgan) asosiy.push({ nom: 'Boshqa', qiymat: qolgan, rang: GRAFIK_RANG[4] });
    halqaQuti.innerHTML = halqaGrafik(asosiy, 'xizmat turi') || '';
  }

  // Oxirgi 6 oy bo'yicha ustunlar
  const oyQuti = document.getElementById('molOylik');
  if (oyQuti) {
    const OY_NOM = ['Yan','Fev','Mar','Apr','May','Iyn','Iyl','Avg','Sen','Okt','Noy','Dek'];
    const oylar = [];
    for (let i = 5; i >= 0; i--) {
      const d = new Date(hozir.getFullYear(), hozir.getMonth() - i, 1);
      oylar.push({ nom: OY_NOM[d.getMonth()], yil: d.getFullYear(), oy: d.getMonth(), qiymat: 0 });
    }
    tolangan.forEach(t => {
      const d = new Date(t.yaratilgan);
      const o = oylar.find(x => x.yil === d.getFullYear() && x.oy === d.getMonth());
      if (o) o.qiymat += Math.round((t.summa || 0) / 1000000 * 10) / 10;  // mln so'm
    });
    oyQuti.innerHTML = ustunGrafik(oylar, GRAFIK_RANG[1]) ||
      boshGrafik("Bu davrda to'lov bo'lmagan", 'Raqamlar million so\'mda ko\'rsatiladi.', 'ti-chart-line');
  }
}

function arizalarChiz(){
  const royxat = tanlanganHolat
    ? arizalar.filter(a => a.holat === tanlanganHolat)
    : arizalar;

  const tana = document.getElementById('arizaTana');
  if (!royxat.length) {
    tana.innerHTML = '<tr class="holat-qator"><td colspan="7">Ariza topilmadi</td></tr>';
    return;
  }
  tana.innerHTML = royxat.map(a => `
    <tr>
      <td>#${a.id}</td>
      <td>${xavfsiz(a.mijoz_malumot ? (a.mijoz_malumot.ism || a.mijoz_malumot.telefon) : '—')}${
        a.mijoz_malumot && a.mijoz_malumot.telefon
          ? `<br><span style="color:var(--text-muted);font-size:12px">${xavfsiz(a.mijoz_malumot.telefon)}</span>` : ''}</td>
      <td>${xavfsiz(a.xizmat_nomi)}${
        a.xizmatlar && a.xizmatlar.tasdiq_summa != null
          ? `<br><span style="color:var(--green);font-size:12px;font-weight:700">✓ ${pulFormat(a.xizmatlar.tasdiq_summa)}</span>`
          : (a.xizmatlar && a.xizmatlar.royxat.length
              ? `<br><span style="color:var(--orange);font-size:12px">Hisob: ${a.xizmatlar.jami_dan === a.xizmatlar.jami_gacha
                  ? pulFormat(a.xizmatlar.jami_dan) : pulFormat(a.xizmatlar.jami_dan) + ' – ' + pulFormat(a.xizmatlar.jami_gacha)} (tasdiqlanmagan)</span>`
              : '')}<br><select class="f-select" data-tarmoq-id="${Number(a.id)}" title="Narx tarmog'i"
            style="margin:4px 0 0;padding:3px 6px;font-size:12px;width:auto;">
            <option value="aholi"${a.tarmoq === 'aholi' ? ' selected' : ''}>Aholi</option>
            <option value="ulgurji"${a.tarmoq === 'ulgurji' ? ' selected' : ''}>Ulgurji</option></select></td>
      <td>${xavfsiz(a.tuman || '—')}${
        a.manzil ? `<br><span style="color:var(--text-muted);font-size:12px">${xavfsiz(a.manzil)}</span>` : ''}</td>
      <td>${xavfsiz(a.xodim_malumot ? a.xodim_malumot.ism : 'Tayinlanmagan')}</td>
      <td>${sanaFormat(a.yaratilgan)}</td>
      <td><span class="tag ${HOLAT_RANG[a.holat] || 'gray'}">${HOLAT_NOM[a.holat] || a.holat}</span></td>
    </tr>`).join('');
}

// ═══════ Viloyat → tuman bog'lanishi ═══════
// Tuman ro'yxati <optgroup> bo'lib guruhlangan, guruh sarlavhasi — viloyat
// nomi. Shu sababli alohida ma'lumot ro'yxati kerak emas: viloyat ro'yxati
// ham, filtrlash ham o'sha sarlavhalardan kelib chiqadi.
function viloyatTumanUla(viloyatSel, tumanSel){
  if (!viloyatSel || !tumanSel || tumanSel.dataset.ulangan) return;
  tumanSel.dataset.ulangan = '1';

  const guruhlar = Array.from(tumanSel.getElementsByTagName('optgroup'));

  // Viloyat ro'yxatini guruh sarlavhalaridan to'ldiramiz
  viloyatSel.innerHTML = '<option value="">— tanlang —</option>' +
    guruhlar.map(g => `<option>${g.label}</option>`).join('');

  function filtrla(tozala){
    const v = viloyatSel.value;
    guruhlar.forEach(g => {
      const mos = !v || g.label === v;
      g.style.display = mos ? '' : 'none';
      // Viloyat almashsa, boshqa viloyatdagi tanlov qolib ketmasin
      if (!mos && tozala && tumanSel.selectedOptions[0] &&
          tumanSel.selectedOptions[0].parentElement === g) {
        tumanSel.value = '';
      }
    });
    tumanSel.disabled = !v;
  }

  viloyatSel.addEventListener('change', () => filtrla(true));

  // Tuman oldindan tanlangan bo'lsa (tahrirlash), viloyatini topamiz
  const tanlangan = tumanSel.selectedOptions[0];
  if (tanlangan && tanlangan.parentElement.tagName === 'OPTGROUP') {
    viloyatSel.value = tanlangan.parentElement.label;
  }
  filtrla(false);
}

viloyatTumanUla(document.getElementById('xf-viloyat'),
                document.getElementById('xf-tuman'));

// ═══════ Xodimlar ═══════
// Ro'yxat /api/auth/xodimlar/ dan keladi. Yangi xodim shu yerdan kiritiladi —
// Django admin paneli (/admin/auth_app/xodim/) ham ishlashda davom etadi.
async function xodimlarYukla(){
  const tana = document.getElementById('xodimJadval');
  try {
    xodimlar = await apiSorov('/auth/xodimlar/');
  } catch (e) {
    tana.innerHTML = `<tr class="holat-qator"><td colspan="7">Ro'yxatni yuklab bo'lmadi: ${xavfsiz(e.message)}</td></tr>`;
    document.getElementById('xodimSoni').textContent = '—';
    return;
  }
  xodimlarChiz();
}

function xodimlarChiz(){
  const tana = document.getElementById('xodimJadval');
  const soni = document.getElementById('xodimSoni');
  const faol = xodimlar.filter(x => x.holat === 'faol').length;

  soni.textContent = xodimlar.length
    ? `Jami ${xodimlar.length} nafar xodim · ${faol} tasi faol`
    : 'Hozircha xodim kiritilmagan';

  if (!xodimlar.length){
    tana.innerHTML = `<tr class="holat-qator"><td colspan="7">
      Ro'yxat bo'sh. Yuqoridagi forma orqali birinchi xodimni kiriting.</td></tr>`;
    return;
  }

  tana.innerHTML = xodimlar.map(x => `
    <tr>
      <td>${xavfsiz(x.ism || '—')}</td>
      <td>${xavfsiz(x.lavozim || '—')}</td>
      <td>${xavfsiz(x.telefon)}</td>
      <td><code class="kod-katak">${xavfsiz(x.kirish_kodi || '—')}</code>
          <button class="btn-sm ghost" data-h-click="c:kodYangila" data-a-click="${SG_A([x.id])}"
                  title="Yangi kod berish">↻</button></td>
      <td>${xavfsiz(x.tuman || '—')}</td>
      <td><span class="tag ${x.holat === 'faol' ? 'green' : 'gray'}">${x.holat === 'faol' ? 'Faol' : 'Nofaol'}</span></td>
      <td>${x.holat === 'faol' && !egasimi()
            ? '<span style="color:#94a3b8;font-size:13px">—</span>'
            : `<button class="btn-sm ${x.holat === 'faol' ? 'danger' : 'ok'}"
                 data-h-click="c:xodimHolat" data-a-click="${SG_A([x.id, String(x.holat === 'faol' ? 'nofaol' : 'faol')])}">
                 ${x.holat === 'faol' ? 'Nofaol qilish' : 'Faollashtirish'}</button>`}
          ${egasimi() ? `<button class="btn-sm" data-h-click="c:korishBoshla" data-a-click="${SG_A([x.id, '@this'])}"
                 title="Xodim portalini uning nomidan, faqat o'qish rejimida ochadi"><i class="ti ti-eye"></i> Uning ko'zi bilan ko'rish</button>` : ''}</td>
    </tr>`).join('');
}

// «Uning ko'zi bilan ko'rish»: faqat egasi. Xodim portali yoki mijoz kabineti yangi tabda,
// o'sha foydalanuvchi nomidan, FAQAT O'QISH rejimida va 30 daqiqaga ochiladi.
// Har ochish Faoliyat jurnaliga yoziladi.
async function korishBoshla(id, tugma){
  if (!confirm("Bu foydalanuvchi nomidan faqat ko'rish rejimida kirasiz (hech narsani o'zgartira olmaysiz).\n" +
               "Bu kirish Faoliyat jurnaliga yoziladi. Davom etasizmi?")) return;
  tugma.disabled = true;
  try {
    const r = await apiSorov(`/auth/korish/${id}/`, { method: 'POST' });
    // Token URL fragmentida: serverga ketmaydi va sahifa uni darhol manzildan olib tashlaydi
    window.open(`${r.portal}#korish=${encodeURIComponent(r.access)}`, '_blank', 'noopener');
    jurnalYukla();
  } catch (e) {
    alert(e.message);
  } finally {
    tugma.disabled = false;
  }
}

// Tizim egasimi? Faqat egasi xodimni nofaol qila oladi — boshqa adminlar
// (direktor) xodimlarni ko'radi va qo'shadi, lekin faolligini to'xtata olmaydi.
// Serverda ham shu tekshiruv bor (XodimDetailView.update) — bu faqat interfeys.
function egasimi(){ return !!(profil && profil.egasi); }

// Xodim o'chirilmaydi — nomi eski buyurtmalarda qolishi kerak.
// Nofaol xodim portalga kira olmaydi.
async function xodimHolat(id, holat){
  const x = xodimlar.find(v => v.id === id);
  const nom = (x && x.ism) || 'Xodim';
  if (holat === 'nofaol' && !confirm(`${nom} nofaol qilinsinmi? U portalga kira olmaydi.`)) return;
  try {
    await apiSorov('/auth/xodimlar/' + id + '/', {
      method: 'PATCH', body: JSON.stringify({ holat })
    });
    if (x) x.holat = holat;
    xodimlarChiz();
  } catch (e) {
    alert('Xatolik: ' + e.message);
  }
}

// Yangi xodim qo'shilgach kodini ko'rsatamiz — admin uni xodimga aytadi.
// Kod parolning o'rnini bosadi, shuning uchun e'tiborni tortadigan qilib.
function kodKorsat(x){
  const el = document.getElementById('xodimKod');
  el.innerHTML = `<i class="ti ti-key"></i>
    <span><b>${xavfsiz(x.ism)}</b> qo'shildi. Kirish kodi:
    <code class="kod-katak">${xavfsiz(x.kirish_kodi)}</code>
    — telefon <b>${xavfsiz(x.telefon)}</b> bilan birga xodimga ayting.</span>`;
  el.classList.add('bor');
}

async function kodYangila(id){
  const x = xodimlar.find(v => v.id === id);
  if (!confirm(`${(x && x.ism) || 'Xodim'} uchun yangi kod berilsinmi?\n` +
               'Eski kod darhol ishlamay qoladi.')) return;
  try {
    const j = await apiSorov('/auth/xodimlar/' + id + '/kod/', { method: 'POST' });
    if (x) { x.kirish_kodi = j.kirish_kodi; xodimlarChiz(); kodKorsat(x); }
  } catch (e) {
    alert('Xatolik: ' + e.message);
  }
}

function xodimXato(matn){
  const el = document.getElementById('xodimXato');
  el.textContent = matn || '';
  el.classList.toggle('bor', !!matn);
}

document.getElementById('xodimForm').addEventListener('submit', async (e) => {
  e.preventDefault();
  const tugma = document.getElementById('xodimSaqlaBtn');
  const q = id => document.getElementById(id).value.trim();
  const telefon = q('xf-telefon').replace(/[\s-]/g, '');

  if (!/^\+998\d{9}$/.test(telefon)) {
    xodimXato('Telefon raqam +998 bilan boshlanib, 12 ta raqamdan iborat bo\'lishi kerak');
    return;
  }

  xodimXato('');
  tugma.disabled = true;
  const asl = tugma.innerHTML;
  tugma.textContent = 'Saqlanmoqda…';
  try {
    const yangi = await apiSorov('/auth/xodimlar/', {
      method: 'POST',
      body: JSON.stringify({
        ism: q('xf-ism'), telefon,
        lavozim: q('xf-lavozim'),
        viloyat: q('xf-viloyat'), tuman: q('xf-tuman'),
        mahalla: q('xf-mahalla'),
        // Bo'sh sana null bo'lishi kerak — bo'sh satrni Django qabul qilmaydi
        ishga_kirgan: q('xf-sana') || null,
      })
    });
    xodimlar.push(yangi);
    xodimlar.sort((a, b) => (a.ism || '').localeCompare(b.ism || ''));
    xodimlarChiz();
    kodKorsat(yangi);
    e.target.reset();
    // reset() dan keyin viloyat bo'shaydi — tuman ro'yxatini qayta filtrlaymiz
    document.getElementById('xf-viloyat').dispatchEvent(new Event('change'));
  } catch (xato) {
    xodimXato(xato.message);
  } finally {
    tugma.disabled = false;
    tugma.innerHTML = asl;
  }
});

// ═══════ Navigatsiya ═══════
document.querySelectorAll('.sb-item[data-page]').forEach(btn=>{
  btn.addEventListener('click', ()=>{
    document.querySelectorAll('.sb-item[data-page]').forEach(b=>b.classList.toggle('active', b===btn));
    document.querySelectorAll('.page').forEach(p=>p.classList.toggle('active', p.id==='page-'+btn.dataset.page));
    if (btn.dataset.page === 'joy') joySahifasiOchildi(); else joySahifasiYopildi();
    if (btn.dataset.page === 'rahbariyat') rahSahifasiOchildi(); else rahSahifasiYopildi();
    if (btn.dataset.page === 'cash') tushumYukla();
    if (btn.dataset.page === 'msg') xabarSahifasiOchildi();
    if (btn.dataset.page === 'nn') nnYukla();
  });
});

document.querySelectorAll('.fchip').forEach(c=>{
  c.addEventListener('click', ()=>{
    c.parentElement.querySelectorAll('.fchip').forEach(x=>x.classList.remove('active'));
    c.classList.add('active');
    // Arizalar chiplari ro'yxatni filtrlaydi, qolganlari hozircha faqat ko'rinish
    if (c.dataset.holat !== undefined) {
      tanlanganHolat = c.dataset.holat;
      arizalarChiz();
    }
  });
});

// ═══════ Boshlash ═══════
// Sahifa yangilanganda sessiya saqlanib qolgan bo'lsa to'g'ridan-to'g'ri panel
(async function(){
  tokenYukla();
  if (!token) return;
  try {
    profil = await apiSorov('/auth/profil/');
    if (profil.rol !== 'admin') { chiqish(); return; }
    await panelniOch();
  } catch (e) { chiqish(); }
})();
