/* Χριστιανισμός & Επιστήμη — εσωτερικές σελίδες (θέμα, μενού, φίλτρα) */
(function () {
  "use strict";

  var $ = function (s, r) { return (r || document).querySelector(s); };
  var $$ = function (s, r) { return Array.prototype.slice.call((r || document).querySelectorAll(s)); };
  var store = {
    get: function (k, d) { try { var v = localStorage.getItem(k); return v ? JSON.parse(v) : d; } catch (e) { return d; } },
    set: function (k, v) { try { localStorage.setItem(k, JSON.stringify(v)); } catch (e) {} }
  };

  /* ---------- theme ---------- */
  var savedTheme = store.get("cs-theme", null);
  if (savedTheme) document.documentElement.setAttribute("data-theme", savedTheme);
  $("#themeToggle").addEventListener("click", function () {
    var cur = document.documentElement.getAttribute("data-theme") ||
      (matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light");
    var next = cur === "dark" ? "light" : "dark";
    document.documentElement.setAttribute("data-theme", next);
    store.set("cs-theme", next);
  });

  /* ---------- mobile menu ---------- */
  var menuBtn = $("#menuToggle"), nav = $("#nav");
  function closeNav() { nav.classList.remove("is-open"); menuBtn.setAttribute("aria-expanded", "false"); }
  menuBtn.addEventListener("click", function () {
    var open = nav.classList.toggle("is-open");
    menuBtn.setAttribute("aria-expanded", open);
  });
  document.addEventListener("click", function (e) {
    if (nav.classList.contains("is-open") && !nav.contains(e.target) && !menuBtn.contains(e.target)) closeNav();
  });
  document.addEventListener("keydown", function (e) {
    if (e.key === "Escape" && nav.classList.contains("is-open")) { closeNav(); menuBtn.focus(); }
  });

  /* ---------- filter (άρθρα, ερωτήσεις) — χωρίς τόνους, τελικό σίγμα ---------- */
  function norm(s) { return s.normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase().replace(/ς/g, "σ"); }
  var input = $("#filter");
  if (input) {
    var items = $$("[data-filter]");
    var empty = $("#filterEmpty");
    items.forEach(function (el) { el._norm = norm(el.textContent); });
    input.addEventListener("input", function () {
      var tokens = norm(input.value.trim()).split(/\s+/).filter(Boolean), shown = 0;
      items.forEach(function (el) {
        var ok = tokens.every(function (t) { return el._norm.indexOf(t) !== -1; });
        el.hidden = !ok; if (ok) shown++;
      });
      if (empty) empty.hidden = shown > 0;
    });
  }

  /* ---------- ερωτήσεις: άνοιγμα από σύνδεσμο #q-... ---------- */
  function openFromHash() {
    var el = location.hash && document.getElementById(location.hash.slice(1));
    if (el && el.tagName === "DETAILS") { el.open = true; el.scrollIntoView(); }
  }
  window.addEventListener("hashchange", openFromHash);
  openFromHash();
})();
