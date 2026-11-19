/* ============================================================
   SOAR GAZ — Bank to'lovi cheklarini tekshirish paneli
   ------------------------------------------------------------
   admin.html (administrator) va xodimlar.html (Kadrlar mutaxassisi) uchun umumiy.
   Sahifaning global `apiSorov` va `token` lariga tayanadi.
   Konteynerlar: #bankChekPanel (ro'yxat), #bankChekBelgi (kutilayotganlar soni, ixtiyoriy),
                 .bc-filtr[data-holat] tugmalari (ixtiyoriy).
   Chek skrinshoti isbot emas: «Tasdiqlash» faqat bankda pul ko'rilgandan keyin bosiladi.
   ============================================================ */
(function () {
  'use strict';
  let holatFiltr = 'tekshirilmoqda';
  const $ = id => document.getElementById(id);

  const uslub = document.createElement('style');
  uslub.textContent = `
    .bc-karta{border:1px solid #e3e8ef;border-radius:12px;padding:14px 16px;margin-bottom:12px;background:#fff;}
    .bc-bosh{display:flex;justify-content:space-between;gap:10px;align-items:flex-start;flex-wrap:wrap;}
    .bc-bosh h4{margin:0;font-size:15px;}
    .bc-summa{font-size:18px;font-weight:800;color:#0f5132;}
    .bc-qator{display:flex;gap:8px;font-size:13px;color:#475569;margin-top:6px;flex-wrap:wrap;}
    .bc-qator b{color:#0f172a;}
    .bc-ogoh{margin-top:8px;padding:8px 10px;border-radius:8px;background:#fff7ed;border:1px solid #fed7aa;color:#9a3412;font-size:12.5px;}
    .bc-tugmalar{display:flex;gap:8px;margin-top:12px;flex-wrap:wrap;}
    .bc-tugmalar button{border:none;border-radius:8px;padding:8px 14px;font-weight:700;font-size:13px;cursor:pointer;font-family:inherit;}
    .bc-korish{background:#eff6ff;color:#1d4ed8;}
    .bc-tasdiq{background:#16a34a;color:#fff;}
    .bc-rad{background:#fee2e2;color:#b91c1c;}
    .bc-teg{display:inline-block;padding:2px 9px;border-radius:999px;font-size:12px;font-weight:700;}
    .bc-teg.tekshirilmoqda{background:#fef3c7;color:#92400e;}
    .bc-teg.tasdiqlandi{background:#dcfce7;color:#166534;}
    .bc-teg.rad{background:#fee2e2;color:#991b1b;}
    .bc-filtrlar{display:flex;gap:6px;margin-bottom:14px;flex-wrap:wrap;}
    .bc-filtr{border:1px solid #cbd5e1;background:#fff;border-radius:999px;padding:6px 14px;font-size:13px;cursor:pointer;font-family:inherit;}
    .bc-filtr.active{background:#1d4ed8;border-color:#1d4ed8;color:#fff;}
    .bc-bosh-holat{color:#64748b;text-align:center;padding:30px 10px;}`;
  document.head.appendChild(uslub);

  function esc(s) {
    return String(s == null ? '' : s).replace(/[&<>"']/g, c =>
      ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  }
  const pul = n => Number(n || 0).toLocaleString('ru-RU').replace(/[ ,]/g, ' ') + " so'm";
  const sana = s => s ? new Date(s).toLocaleString('uz-UZ', { day: '2-digit', month: '2-digit', year: 'numeric', hour: '2-digit', minute: '2-digit' }) : '';

  function karta(t) {
    const farq = t.tasdiq_summa && Number(t.tasdiq_summa) !== Number(t.summa);
    return `<div class="bc-karta">
      <div class="bc-bosh">
        <div><h4>Buyurtma #${t.buyurtma} — ${esc(t.xizmat)}</h4>
          <div class="bc-qator"><span>${esc(t.mijoz || '—')}</span><span>${esc(t.telefon)}</span><span>${esc(sana(t.yaratilgan))}</span></div></div>
        <div style="text-align:right"><div class="bc-summa">${pul(t.summa)}</div>
          <span class="bc-teg ${esc(t.holat)}">${esc(t.holat_nomi)}</span></div>
      </div>
      <div class="bc-qator"><span>Hisob raqam:</span><b>${esc(t.hisob_raqam)}</b></div>
      ${t.izoh ? `<div class="bc-qator"><span>Mijoz izohi:</span><b>${esc(t.izoh)}</b></div>` : ''}
      ${farq ? `<div class="bc-ogoh">⚠️ Buyurtmaning tasdiqlangan summasi: <b>${pul(t.tasdiq_summa)}</b>. Mijoz kiritgan summa boshqacha.</div>` : ''}
      ${t.holat === 'rad' ? `<div class="bc-qator"><span>Rad sababi:</span><b>${esc(t.rad_sabab)}</b></div>` : ''}
      ${t.tekshirdi ? `<div class="bc-qator"><span>Tekshirdi:</span><b>${esc(t.tekshirdi)}</b><span>${esc(sana(t.tekshirilgan))}</span></div>` : ''}
      <div class="bc-tugmalar">
        <button type="button" class="bc-korish" data-bc-amal="korish" data-bc-url="${esc(t.chek_url)}">🧾 Chekni ko'rish</button>
        ${t.holat === 'tekshirilmoqda' ? `
          <button type="button" class="bc-tasdiq" data-bc-amal="tasdiq" data-bc-id="${t.id}" data-bc-summa="${esc(pul(t.summa))}">✓ Pul keldi — tasdiqlash</button>
          <button type="button" class="bc-rad" data-bc-amal="rad" data-bc-id="${t.id}">✕ Rad etish</button>` : ''}
      </div></div>`;
  }

  async function yukla() {
    const panel = $('bankChekPanel');
    if (!panel || typeof apiSorov !== 'function') return;
    try {
      const d = await apiSorov('/tolovlar/bank/cheklar/' + (holatFiltr ? '?holat=' + holatFiltr : ''));
      panel.innerHTML = d.royxat.length ? d.royxat.map(karta).join('')
        : '<p class="bc-bosh-holat">Bu bo\'limda chek yo\'q.</p>';
      const belgi = $('bankChekBelgi');
      if (belgi) { belgi.textContent = d.kutilmoqda; belgi.hidden = !d.kutilmoqda; belgi.style.display = d.kutilmoqda ? '' : 'none'; }
    } catch (e) {
      panel.innerHTML = `<p class="bc-bosh-holat">${esc(e.message)}</p>`;
    }
  }

  async function chekKorish(url) {
    const oyna = window.open('', '_blank');             // bosish paytida ochiladi (popup bloklanmasin)
    try {
      const javob = await fetch(url, { headers: { Authorization: 'Bearer ' + token } });
      if (!javob.ok) throw new Error('Chek ochilmadi');
      const blob = await javob.blob();
      const manzil = URL.createObjectURL(blob);
      if (oyna) oyna.location = manzil; else window.location = manzil;
      setTimeout(() => URL.revokeObjectURL(manzil), 60000);
    } catch (e) {
      if (oyna) oyna.close();
      alert(e.message);
    }
  }

  async function tekshir(id, natija, sabab) {
    try {
      await apiSorov(`/tolovlar/bank/cheklar/${id}/tekshir/`,
        { method: 'POST', body: JSON.stringify({ natija, sabab: sabab || '' }) });
      await yukla();
    } catch (e) { alert(e.message); }
  }

  document.addEventListener('click', e => {
    const f = e.target.closest('.bc-filtr[data-holat]');
    if (f) {
      holatFiltr = f.dataset.holat;
      document.querySelectorAll('.bc-filtr[data-holat]').forEach(b => b.classList.toggle('active', b === f));
      yukla();
      return;
    }
    const t = e.target.closest('[data-bc-amal]');
    if (!t) return;
    const amal = t.dataset.bcAmal;
    if (amal === 'korish') chekKorish(t.dataset.bcUrl);
    else if (amal === 'tasdiq') {
      if (confirm(`Bank hisobingizga ${t.dataset.bcSumma} haqiqatan tushganini tekshirdingizmi?\n\nTasdiqlangandan keyin qaytarib bo'lmaydi.`)) tekshir(t.dataset.bcId, 'tasdiq');
    } else if (amal === 'rad') {
      const sabab = prompt("Rad etish sababi (mijozga yuboriladi):", "Pul hisobimizga kelib tushmadi");
      if (sabab && sabab.trim()) tekshir(t.dataset.bcId, 'rad', sabab.trim());
    }
  });

  window.BankCheklar = { yukla };
})();
