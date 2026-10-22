/*
 * Site-wide search: the magnifying glass in the top bar (also "/" or Ctrl+K).
 * Opens a panel that searches broadcasts, newspaper column articles, topics, media pages, questions
 * and «Άρθρα & πηγές» pages at once, with the same forgiving matching as the broadcast archive
 * (js/search.js: typos, word forms, Greeklish). The list it searches is js/search-index.js, made by
 * tools/site_search.py; both are loaded only when the panel is first opened.
 */
(function () {
  "use strict";
  var me = document.currentScript;
  var ROOT = new URL("..", me.src).href;                       // the site root, from this script's address
  var VERSION = me.getAttribute("data-index") || "";
  var EN = document.documentElement.lang === "en";
  var T = EN ? {
    label: "Search the site", placeholder: "Search broadcasts, articles, topics…", close: "Close",
    hint: "Type a word or two – for example “creation”, “DNA” or “flood”. Greek and Greeklish work too.",
    none: "Nothing found. Try another word.", near: "No exact match – these are the closest:",
    loading: "Loading…", failed: "The search could not be loaded. Please try again.",
    kinds: { B: "Broadcasts", C: "From our newspaper column", T: "Topics", M: "Media", Q: "Questions", A: "Articles & sources" },
    more: function (n) { return "and " + n + " more"; },
    months: ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
  } : {
    label: "Αναζήτηση στον ιστότοπο", placeholder: "Αναζήτηση σε εκπομπές, άρθρα, θέματα…", close: "Κλείσιμο",
    hint: "Γράψτε μια-δυο λέξεις – π.χ. «δημιουργία», «DNA» ή «κατακλυσμός». Δουλεύει και με greeklish.",
    none: "Δεν βρέθηκε κάτι. Δοκιμάστε άλλη λέξη.", near: "Δεν βρέθηκε ακριβές αποτέλεσμα – τα πλησιέστερα:",
    loading: "Φόρτωση…", failed: "Η αναζήτηση δεν φόρτωσε. Δοκιμάστε ξανά.",
    kinds: { B: "Εκπομπές", C: "Από τη στήλη μας στην εφημερίδα", T: "Θέματα", M: "Πολυμέσα", Q: "Ερωτήσεις", A: "Άρθρα & πηγές" },
    more: function (n) { return "και άλλα " + n; },
    months: ["Ιαν", "Φεβ", "Μαρ", "Απρ", "Μαΐ", "Ιουν", "Ιουλ", "Αυγ", "Σεπ", "Οκτ", "Νοε", "Δεκ"]
  };
  var ORDER = ["B", "C", "T", "M", "Q", "A"], PER_KIND = 6;

  var panel, input, results, opener, items = null, loading = null, timer;

  function esc(s) { return String(s).replace(/[&<>"]/g, function (c) { return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]; }); }

  function load(src, hourly) {
    return new Promise(function (ok, fail) {
      var s = document.createElement("script");
      // the list (search-index.js) changes with every new broadcast: asked for afresh at most once an hour,
      // so the pages do not have to carry its version; the code (search.js) by the version the page carries
      var v = hourly ? "h" + Math.floor(Date.now() / 3600000) : VERSION;
      s.src = ROOT + src + (v ? "?v=" + v : ""); s.onload = ok; s.onerror = fail;
      document.head.appendChild(s);
    });
  }

  function ready() {
    if (items) return Promise.resolve();
    if (!loading) {
      loading = (window.SiteSearch ? Promise.resolve() : load("js/search.js"))
        .then(function () { return window.SITE_INDEX ? null : load("js/search-index.js", true); })
        .then(function () {
          var SS = window.SiteSearch;
          items = window.SITE_INDEX.map(function (r, i) {
            var title = EN && r.e ? r.e : r.t;
            var titles = r.t + " " + (r.e || "");
            var it = { id: -i, r: r, title: title, greek: EN && !r.e,
                       norm: SS.norm(titles + " " + (r.w || "") + " " + (EN ? r.x || "" : "")),
                       words: SS.words(titles).filter(function (w) { return !SS.stop[w]; }) };   // «κατά», «από» … match nothing
            return it;
          });
        })
        .catch(function (e) { loading = null; throw e; });
    }
    return loading;
  }

  function href(r) {
    var base = EN && r.h ? ROOT + "en/" : ROOT;
    return base + r.u;
  }

  function dateOf(r) {
    if (!r.d) return "";
    var p = r.d.split("-");
    return +p[2] + " " + T.months[+p[1] - 1] + " " + p[0];
  }

  function build() {
    panel = document.createElement("div");
    panel.className = "ssearch"; panel.hidden = true;
    panel.setAttribute("role", "dialog"); panel.setAttribute("aria-modal", "true"); panel.setAttribute("aria-label", T.label);
    panel.innerHTML =
      '<div class="ssearch__panel">' +
        '<div class="ssearch__bar">' +
          '<svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="11" cy="11" r="6.5"/><path d="m16 16 4.5 4.5"/></svg>' +
          '<input type="search" class="ssearch__input" autocomplete="off" spellcheck="false" aria-label="' + esc(T.label) + '" placeholder="' + esc(T.placeholder) + '">' +
          '<button type="button" class="ssearch__close" aria-label="' + esc(T.close) + '"><span aria-hidden="true">✕</span></button>' +
        "</div>" +
        '<div class="ssearch__results" aria-live="polite"><p class="ssearch__hint">' + esc(T.hint) + "</p></div>" +
      "</div>";
    document.body.appendChild(panel);
    input = panel.querySelector(".ssearch__input");
    results = panel.querySelector(".ssearch__results");
    input.addEventListener("input", function () { clearTimeout(timer); timer = setTimeout(run, 80); });
    panel.querySelector(".ssearch__close").addEventListener("click", close);
    panel.addEventListener("mousedown", function (e) { if (e.target === panel) close(); });
    panel.addEventListener("keydown", keys);
    results.addEventListener("click", function (e) {
      var a = e.target.closest("a");
      if (a) close(true);                                          // e.g. a broadcast on this same page (#e-…)
    });
  }

  function run() {
    var q = input.value.trim();
    if (!q) { results.innerHTML = '<p class="ssearch__hint">' + esc(T.hint) + "</p>"; return; }
    if (!items) { results.innerHTML = '<p class="ssearch__hint">' + esc(T.loading) + "</p>"; ready().then(run, failed); return; }
    var res = window.SiteSearch.search(items, q);
    if (!res.list.length) { results.innerHTML = '<p class="ssearch__hint">' + esc(T.none) + "</p>"; return; }
    var groups = {};
    res.list.forEach(function (x) { (groups[x.ep.r.k] = groups[x.ep.r.k] || []).push(x.ep); });
    var html = res.approx ? '<p class="ssearch__note">' + esc(T.near) + "</p>" : "";
    ORDER.forEach(function (k) {
      var g = groups[k];
      if (!g) return;
      html += '<section class="ssearch__group"><h2 class="ssearch__head">' + esc(T.kinds[k]) + "</h2><ul>" +
        g.slice(0, PER_KIND).map(function (it) {
          var d = dateOf(it.r);
          return '<li><a class="ssearch__item" href="' + esc(href(it.r)) + '"' + (it.greek ? ' lang="el"' : "") + ">" +
            '<span class="ssearch__title">' + esc(it.title) + "</span>" + (d ? '<span class="ssearch__meta">' + d + "</span>" : "") + "</a></li>";
        }).join("") + "</ul>" +
        (g.length > PER_KIND ? '<p class="ssearch__more">' + esc(T.more(g.length - PER_KIND)) + "</p>" : "") + "</section>";
    });
    results.innerHTML = html;
  }

  function failed() { results.innerHTML = '<p class="ssearch__hint">' + esc(T.failed) + "</p>"; }

  function keys(e) {
    if (e.key === "Escape") { e.preventDefault(); close(); return; }
    if (e.key !== "ArrowDown" && e.key !== "ArrowUp") return;
    var links = [].slice.call(results.querySelectorAll("a"));
    if (!links.length) return;
    e.preventDefault();
    var i = links.indexOf(document.activeElement);
    if (e.key === "ArrowDown") (i < 0 ? links[0] : links[Math.min(i + 1, links.length - 1)]).focus();
    else if (i <= 0) input.focus(); else links[i - 1].focus();
  }

  function open() {
    if (!panel) build();
    opener = document.activeElement;
    panel.hidden = false;
    document.documentElement.classList.add("ssearch-open");
    input.focus(); input.select();
    ready().then(function () { if (input.value.trim()) run(); }, failed);
  }

  function close(keepFocus) {
    if (!panel || panel.hidden) return;
    panel.hidden = true;
    document.documentElement.classList.remove("ssearch-open");
    if (keepFocus !== true && opener && opener.focus) opener.focus();
  }

  var btn = document.getElementById("siteSearch");
  if (btn) btn.addEventListener("click", open);
  document.addEventListener("keydown", function (e) {
    var t = e.target, typing = t && (t.isContentEditable || /^(INPUT|TEXTAREA|SELECT)$/.test(t.tagName));
    if ((e.key === "k" || e.key === "K") && (e.ctrlKey || e.metaKey)) { e.preventDefault(); open(); return; }
    if (e.key === "/" && !typing && !e.altKey && !e.ctrlKey && !e.metaKey) { e.preventDefault(); open(); }
  });
  window.SiteSearchPanel = { open: open, close: close };
})();
