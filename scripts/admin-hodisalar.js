/* admin.html: inline hodisa handlerlari (onclick="..." o'rniga). Avtomatik yaratilgan: CSP uchun. */
(function () {
  var R = window.SG_H = window.SG_H || {};
  R["h1"] = function (event) { hisobotYukla('csv')
  };
  R["h2"] = function (event) { hisobotYukla('chop')
  };
  R["c:kodYangila"] = function (e) { kodYangila.apply(null, SG_ARGS(this, e)); };
  R["c:korishBoshla"] = function (e) { korishBoshla.apply(null, SG_ARGS(this, e)); };
  R["c:xodimHolat"] = function (e) { xodimHolat.apply(null, SG_ARGS(this, e)); };
})();
