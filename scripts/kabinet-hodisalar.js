/* kabinet.html: inline hodisa handlerlari (onclick="..." o'rniga). Avtomatik yaratilgan: CSP uchun. */
(function () {
  var R = window.SG_H = window.SG_H || {};
  R["h1"] = function (event) { kodYubor(event)
  };
  R["h2"] = function (event) { kodTasdiqla(event)
  };
  R["h3"] = function (event) { this.value=this.value.replace(/\D/g,'')
  };
  R["h4"] = function (event) { qadamgaOt(1)
  };
  R["h5"] = function (event) { kodQaytaYubor()
  };
  R["h6"] = function (event) { profilSaqla(event)
  };
  R["h7"] = function (event) { yonPanel(false)
  };
  R["h8"] = function (event) { pageOch('bosh')
  };
  R["h9"] = function (event) { pageOch('buyurtmalar')
  };
  R["h10"] = function (event) { pageOch('obyektlar')
  };
  R["h11"] = function (event) { pageOch('hisoblagichlar')
  };
  R["h12"] = function (event) { pageOch('tolovlar')
  };
  R["h13"] = function (event) { pageOch('hujjatlar')
  };
  R["h14"] = function (event) { pageOch('bildirishnomalar')
  };
  R["h15"] = function (event) { pageOch('sharhlar')
  };
  R["h16"] = function (event) { pageOch('yordam')
  };
  R["h17"] = function (event) { pageOch('sozlamalar')
  };
  R["h18"] = function (event) { chiqish()
  };
  R["h19"] = function (event) { yonPanel(true)
  };
  R["h20"] = function (event) { arizaModalOch()
  };
  R["h21"] = function (event) { buyurtmaFiltrla('')
  };
  R["h22"] = function (event) { buyurtmaFiltrla('faol')
  };
  R["h23"] = function (event) { buyurtmaFiltrla('yakunlangan')
  };
  R["h24"] = function (event) { buyurtmaFiltrla('montaj')
  };
  R["h25"] = function (event) { buyurtmaFiltrla('servis')
  };
  R["h26"] = function (event) { buyurtmaFiltrla('metrologiya')
  };
  R["h27"] = function (event) { obyektModalOch()
  };
  R["h28"] = function (event) { hisoblagichModalOch()
  };
  R["h29"] = function (event) { tolovUsul('click')
  };
  R["h30"] = function (event) { tolovUsul('payme')
  };
  R["h31"] = function (event) { tolovUsul('bank')
  };
  R["h32"] = function (event) { hujjatFiltrla('')
  };
  R["h33"] = function (event) { hujjatFiltrla('shartnoma')
  };
  R["h34"] = function (event) { hujjatFiltrla('sertifikat')
  };
  R["h35"] = function (event) { hujjatFiltrla('hisobot')
  };
  R["h36"] = function (event) { hujjatFiltrla('faktura')
  };
  R["h37"] = function (event) { hammasiOqildi()
  };
  R["h38"] = function (event) { murojaatModalOch()
  };
  R["h39"] = function (event) { qongiroqSora(event)
  };
  R["h40"] = function (event) { sozlamaProfilSaqla(event)
  };
  R["h41"] = function (event) { sozlamaSaqla()
  };
  R["h42"] = function (event) { hisobOchirModal()
  };
  R["h43"] = function (event) { if(event.target===this) modalYop()
  };
  R["h44"] = function (event) { arizaYubor(event)
  };
  R["h45"] = function (event) { murojaatYarat(event)
  };
  R["h46"] = function (event) { hisobOchir(event)
  };
  R["h47"] = function (event) { modalYop()
  };
  R["c:bahoTanla"] = function (e) { bahoTanla.apply(null, SG_ARGS(this, e)); };
  R["c:faqOch"] = function (e) { faqOch.apply(null, SG_ARGS(this, e)); };
  R["c:hisoblagichModalOch"] = function (e) { hisoblagichModalOch.apply(null, SG_ARGS(this, e)); };
  R["c:hisoblagichOchir"] = function (e) { hisoblagichOchir.apply(null, SG_ARGS(this, e)); };
  R["c:hisoblagichSaqla"] = function (e) { hisoblagichSaqla.apply(null, SG_ARGS(this, e)); };
  R["c:murojaatYop"] = function (e) { murojaatYop.apply(null, SG_ARGS(this, e)); };
  R["c:obyektModalOch"] = function (e) { obyektModalOch.apply(null, SG_ARGS(this, e)); };
  R["c:obyektOchir"] = function (e) { obyektOchir.apply(null, SG_ARGS(this, e)); };
  R["c:obyektSaqla"] = function (e) { obyektSaqla.apply(null, SG_ARGS(this, e)); };
  R["c:pageOch"] = function (e) { pageOch.apply(null, SG_ARGS(this, e)); };
  R["c:sharhModalOch"] = function (e) { sharhModalOch.apply(null, SG_ARGS(this, e)); };
  R["c:sharhOchir"] = function (e) { sharhOchir.apply(null, SG_ARGS(this, e)); };
  R["c:sharhTahrir"] = function (e) { sharhTahrir.apply(null, SG_ARGS(this, e)); };
  R["c:sharhYangila"] = function (e) { sharhYangila.apply(null, SG_ARGS(this, e)); };
  R["c:sharhYubor"] = function (e) { sharhYubor.apply(null, SG_ARGS(this, e)); };
  R["c:tekshiruvgaYozil"] = function (e) { tekshiruvgaYozil.apply(null, SG_ARGS(this, e)); };
  R["c:uskunaModalOch"] = function (e) { uskunaModalOch.apply(null, SG_ARGS(this, e)); };
  R["c:uskunaSaqla"] = function (e) { uskunaSaqla.apply(null, SG_ARGS(this, e)); };
  R["c:xabarYubor"] = function (e) { xabarYubor.apply(null, SG_ARGS(this, e)); };
})();
