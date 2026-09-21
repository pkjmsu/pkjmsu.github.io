(function () {
  "use strict";
  var STATS_URL = "assets/stats.json";

  function number(n) {
    var v = Number(n);
    if (!isFinite(v)) return String(n);
    return v.toLocaleString("en-US");
  }

  fetch(STATS_URL, { cache: "no-store" })
    .then(function (res) {
      if (!res.ok) throw new Error("HTTP " + res.status);
      return res.json();
    })
    .then(function (data) {
      var fields = { citations: data.citations, hindex: data.hindex, i10index: data.i10index, updated: data.updated };
      Object.keys(fields).forEach(function (key) {
        if (fields[key] == null) return;
        var nodes = document.querySelectorAll('[data-scholar="' + key + '"]');
        for (var i = 0; i < nodes.length; i++) {
          nodes[i].textContent = key === "updated" ? fields[key] : number(fields[key]);
        }
      });
    })
    .catch(function () {});
})();