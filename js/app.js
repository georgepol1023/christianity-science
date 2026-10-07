/* Χριστιανισμός & Επιστήμη — front-end (χωρίς εξαρτήσεις) */
(function () {
  "use strict";

  var CFG = window.SITE_CONFIG || {};
  var SEASONS = window.BROADCASTS || [];
  var $ = function (s, r) { return (r || document).querySelector(s); };
  var $$ = function (s, r) { return Array.prototype.slice.call((r || document).querySelectorAll(s)); };

  /* ---------- language: pages in en/ have <html lang="en"> ---------- */
  var LANG = document.documentElement.lang === "en" ? "en" : "el";
  var ROOT = LANG === "en" ? "../" : "";                 // path from this page to the site root
  var EN_TITLES = window.BROADCAST_TITLES_EN || {};
  var T = {
    el: {
      locale: "el-GR", site: "Χριστιανισμός & Επιστήμη",
      months: ["Ιανουαρίου","Φεβρουαρίου","Μαρτίου","Απριλίου","Μαΐου","Ιουνίου","Ιουλίου","Αυγούστου","Σεπτεμβρίου","Οκτωβρίου","Νοεμβρίου","Δεκεμβρίου"],
      monthsShort: ["Ιαν","Φεβ","Μαρ","Απρ","Μαΐ","Ιουν","Ιουλ","Αυγ","Σεπ","Οκτ","Νοε","Δεκ"],
      seasonWord: "κυκλος",
      partBtn: function (n) { return '<span class="part__n">' + n + 'ο</span> <span class="part__l">ημίωρο</span>'; },
      part: function (n) { return n + "ο ημίωρο"; },
      partsAria: "Ημίωρα",
      listenPart: function (n) { return "Ακούστε το " + n + "ο ημίωρο"; },
      listenLatest: function (t) { return "Ακούστε την τελευταία εκπομπή: " + t; },
      latest: "Τελευταία εκπομπή",
      season: function (n) { return n + "ος κύκλος"; },
      seasonAria: function (n) { return n + "ος κύκλος εκπομπών"; },
      partsCount: function (n) { return n + " ημίωρα"; },
      resumeLabel: function (p, t) { return "Συνεχίστε από εκεί που σταματήσατε: " + p + "ο ημίωρο, " + t; },
      resume: "Συνέχεια", hide: "Απόκρυψη",
      allSeasons: "Όλοι οι κύκλοι",
      stats: function (e, n, h) { return e + " εκπομπές σε " + n + " κύκλους, περίπου " + h + " ώρες ακρόασης."; },
      sources: "Άρθρα &amp; πηγές", copyLink: "Αντιγραφή συνδέσμου",
      listen: function (t) { return "Ακούστε: " + t; }, download: "Λήψη mp3",
      searchAria: "Αποτελέσματα αναζήτησης", results: "Αποτελέσματα", closest: "Πλησιέστερες εκπομπές", byRelevance: "κατά συνάφεια",
      count: function (n) { return n + (n === 1 ? " εκπομπή" : " εκπομπές"); },
      approx: function (q) { return "Δεν βρέθηκε ακριβής αντιστοιχία για «" + q + "». Δείτε τις πλησιέστερες εκπομπές."; },
      found: function (n, q) { return (n === 1 ? "Βρέθηκε 1 εκπομπή" : "Βρέθηκαν " + n + " εκπομπές") + " για «" + q + "»" + (n > 1 ? ", οι πιο σχετικές πρώτα." : "."); },
      copied: "Ο σύνδεσμος αντιγράφηκε.", copyPrompt: "Αντιγράψτε τον σύνδεσμο:",
      dlItem: function (n) { return n + "ο ημίωρο (mp3)"; },
      meta: function (d, p, n) { return d + ", " + p + "ο από " + n + " ημίωρα"; },
      pause: "Παύση", play: "Αναπαραγωγή",
      next: function (n) { return "Συνέχεια με το " + n + "ο ημίωρο"; },
      finished: "Ολοκληρώθηκε η εκπομπή.",
      notFound: function (f) { return "Το αρχείο ήχου δεν βρέθηκε στον διακομιστή: " + f; },
      icsSummary: "Χριστιανισμός & Επιστήμη (ζωντανά)", icsDesc: "Ραδιοφωνική εκπομπή στο ράδιο «Χριστιανισμός»",
      onAir: "Σε εξέλιξη τώρα",
      units: function (dd) { return [dd === 1 ? "ημέρα" : "ημέρες", "ώρες", "λεπτά", "δευτ."]; },
      column: function (m) { return "Άρθρο " + m; },
      video: "Βίντεο: Χριστιανισμός & Επιστήμη"
    },
    en: {
      locale: "en-GB", site: "Christianity & Science",
      months: ["January","February","March","April","May","June","July","August","September","October","November","December"],
      monthsShort: ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"],
      seasonWord: "season",
      partBtn: function (n) { return '<span class="part__l">Part</span> <span class="part__n">' + n + "</span>"; },
      part: function (n) { return "part " + n; },
      partsAria: "Parts",
      listenPart: function (n) { return "Listen to part " + n; },
      listenLatest: function (t) { return "Listen to the latest broadcast: " + t; },
      latest: "Latest broadcast",
      season: function (n) { return "Season " + n; },
      seasonAria: function (n) { return "Season " + n + " broadcasts"; },
      partsCount: function (n) { return n + " parts"; },
      resumeLabel: function (p, t) { return "Continue where you left off: part " + p + ", " + t; },
      resume: "Continue", hide: "Hide",
      allSeasons: "All seasons",
      stats: function (e, n, h) { return e + " broadcasts in " + n + " seasons, about " + h + " hours of listening. Audio in Greek."; },
      sources: "Articles &amp; sources (in Greek)", copyLink: "Copy link",
      listen: function (t) { return "Listen: " + t; }, download: "Download mp3",
      searchAria: "Search results", results: "Results", closest: "Closest broadcasts", byRelevance: "most relevant first",
      count: function (n) { return n + (n === 1 ? " broadcast" : " broadcasts"); },
      approx: function (q) { return "No exact match for “" + q + "”. Here are the closest broadcasts."; },
      found: function (n, q) { return (n === 1 ? "Found 1 broadcast" : "Found " + n + " broadcasts") + " for “" + q + "”" + (n > 1 ? ", most relevant first." : "."); },
      copied: "Link copied.", copyPrompt: "Copy the link:",
      dlItem: function (n) { return "Part " + n + " (mp3)"; },
      meta: function (d, p, n) { return d + ", part " + p + " of " + n; },
      pause: "Pause", play: "Play",
      next: function (n) { return "Continuing with part " + n; },
      finished: "Broadcast finished.",
      notFound: function (f) { return "Audio file not found on the server: " + f; },
      icsSummary: "Christianity & Science (live)", icsDesc: "Radio broadcast on Radio Christianity",
      onAir: "On air now",
      units: function (dd) { return [dd === 1 ? "day" : "days", "hours", "minutes", "sec"]; },
      column: function () { return "Latest column (in Greek)"; },
      video: "Video: Christianity & Science"
    }
  }[LANG];

  /* ---------- storage (safe) ---------- */
  var store = {
    get: function (k, d) { try { var v = localStorage.getItem(k); return v ? JSON.parse(v) : d; } catch (e) { return d; } },
    set: function (k, v) { try { localStorage.setItem(k, JSON.stringify(v)); } catch (e) {} },
    del: function (k) { try { localStorage.removeItem(k); } catch (e) {} }
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
  menuBtn.addEventListener("click", function () {
    var open = nav.classList.toggle("is-open");
    menuBtn.setAttribute("aria-expanded", open);
  });
  function closeNav() { nav.classList.remove("is-open"); menuBtn.setAttribute("aria-expanded", "false"); }
  nav.addEventListener("click", function (e) { if (e.target.tagName === "A") closeNav(); });
  document.addEventListener("click", function (e) { if (nav.classList.contains("is-open") && !nav.contains(e.target) && !menuBtn.contains(e.target)) closeNav(); });

  /* ---------- stars in hero ---------- */
  (function () {
    var g = $("#stars"); if (!g) return;
    var seed = 7, rnd = function () { seed = (seed * 16807) % 2147483647; return seed / 2147483647; };
    var html = "";
    for (var i = 0; i < 70; i++) {
      var r = rnd() < .12 ? 1.6 : rnd() * .9 + .4;
      html += '<circle cx="' + (rnd() * 1200).toFixed(1) + '" cy="' + (rnd() * 600).toFixed(1) + '" r="' + r.toFixed(2) + '" opacity="' + (rnd() * .5 + .2).toFixed(2) + '"/>';
    }
    g.innerHTML = html;
  })();

  /* ---------- data ---------- */
  var EPISODES = [], BY_ID = {};
  SEASONS.forEach(function (s) {
    s.episodes.forEach(function (e) {
      var id = e.date.replace(/-/g, "_");
      var parts = [];
      for (var n = 1; n <= e.parts; n++) {
        parts.push(ROOT + (e.files ? e.files[n - 1] :
          (CFG.mp3Base || "") + "Season_" + (s.n < 10 ? "0" : "") + s.n + "/" + id + "/" + (e.cs ? "CS_" : "") + id + "_(" + n + ")_" + e.slug + ".mp3"));
      }
      var d = e.date.split("-").map(Number);
      var ep = {
        id: id, season: s.n, span: s.span, parts: parts,
        title: (LANG === "en" && EN_TITLES[e.date]) || e.title,
        link: e.link && !/^[a-z]+:/i.test(e.link) ? ROOT + e.link : e.link,
        y: d[0], m: d[1], d: d[2],
        dateLong: d[2] + " " + T.months[d[1] - 1] + " " + d[0],
        norm: null, words: null
      };
      // search both the shown title and the Greek original, so Greek queries work on the English site too
      var both = ep.title === e.title ? ep.title : ep.title + " " + e.title;
      ep.norm = norm(both + " " + ep.dateLong + " " + T.monthsShort[d[1] - 1] + " " + d[0] + " " + T.seasonWord + " " + s.n);
      ep.words = norm(both).split(/[^0-9a-zα-ω]+/).filter(Boolean);
      EPISODES.push(ep); BY_ID[id] = ep;
    });
  });

  /* Greek-aware normalisation: no accents, lowercase, final sigma */
  function normChar(c) { return c.normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase().replace(/ς/g, "σ"); }
  function norm(s) { return normChar(s); }

  /* ---------- forgiving search: typos, word forms, Greeklish, partial matches ---------- */
  var STOP = {};
  ("και ο η το οι τα του της των τον την τη στο στη στην στον στα στις στους σε με για απο προς " +
   "κατα μετα ενα μια ενας ως οτι ποσ πωσ τι ειναι δεν μη αλλα ή αυτο αυτη μεροσ ο " +
   "the and of a an in on to for with is are what how why part")
    .split(" ").forEach(function (w) { STOP[norm(w)] = true; });

  function words(s) { return norm(s).split(/[^0-9a-zα-ω]+/).filter(Boolean); }

  // Greeklish → Greek, so "genesi" finds "Γένεση" ("th" → θ, "ps" → ψ …)
  var GL = [["th", "θ"], ["ch", "χ"], ["ps", "ψ"], ["ks", "ξ"], ["ou", "ου"], ["mp", "μπ"],
    ["a", "α"], ["b", "β"], ["v", "β"], ["g", "γ"], ["d", "δ"], ["e", "ε"], ["z", "ζ"], ["h", "η"], ["i", "ι"],
    ["k", "κ"], ["l", "λ"], ["m", "μ"], ["n", "ν"], ["x", "ξ"], ["o", "ο"], ["p", "π"], ["r", "ρ"], ["s", "σ"],
    ["t", "τ"], ["y", "υ"], ["u", "υ"], ["f", "φ"], ["w", "ω"], ["c", "κ"], ["j", "τζ"], ["q", "κ"]];
  function greeklish(t) {
    var out = "", i = 0;
    while (i < t.length) {
      var hit = null;
      for (var k = 0; k < GL.length && !hit; k++) if (t.substr(i, GL[k][0].length) === GL[k][0]) hit = GL[k];
      if (hit) { out += hit[1]; i += hit[0].length; } else { out += t[i]; i++; }
    }
    return out;
  }

  // edit distance with transpositions, giving up beyond `max`
  function editDist(a, b, max) {
    if (Math.abs(a.length - b.length) > max) return max + 1;
    var prev2 = null, prev = [], cur, i, j;
    for (j = 0; j <= b.length; j++) prev[j] = j;
    for (i = 1; i <= a.length; i++) {
      cur = [i]; var rowMin = i;
      for (j = 1; j <= b.length; j++) {
        var c = a[i - 1] === b[j - 1] ? 0 : 1;
        cur[j] = Math.min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + c);
        if (prev2 && i > 1 && j > 1 && a[i - 1] === b[j - 2] && a[i - 2] === b[j - 1]) cur[j] = Math.min(cur[j], prev2[j - 2] + 1);
        if (cur[j] < rowMin) rowMin = cur[j];
      }
      if (rowMin > max) return max + 1;
      prev2 = prev; prev = cur;
    }
    return prev[b.length];
  }

  function trigrams(w) { var s = " " + w + " ", out = {}; for (var i = 0; i < s.length - 2; i++) out[s.substr(i, 3)] = 1; return out; }
  function dice(a, b) {
    var n = 0, na = 0, nb = 0, k;
    for (k in a) { na++; if (b[k]) n++; }
    for (k in b) nb++;
    return na + nb ? 2 * n / (na + nb) : 0;
  }

  /* How well one query word matches a broadcast: {s: score 0–10, hit: matched title word}. */
  function matchWord(q, ep) {
    var best = { s: 0, hit: null };
    function take(s, hit) { if (s > best.s) best = { s: s, hit: hit }; }
    if (ep.norm.indexOf(q) !== -1) take(7, q);                     // anywhere in title/date
    var lim = q.length >= 6 ? 2 : 1, qt = q.length >= 3 ? trigrams(q) : null;
    ep.words.forEach(function (w) {
      if (w === q) return take(10, w);
      if (q.length >= 2 && w.indexOf(q) === 0) take(8, w);                    // start of a word
      if (w.length >= 4 && q.indexOf(w) === 0) take(7 * Math.min(1, w.length / q.length / 0.7), w);  // a short word only partly covers the query
      var cp = 0; while (cp < w.length && cp < q.length && w[cp] === q[cp]) cp++;
      if (cp >= 4 && cp >= 0.7 * Math.min(w.length, q.length)) take(6, w);    // other word form
      if (q.length >= 4 && w.length >= 3) { var d = editDist(w, q, lim); if (d <= lim) take(5 - d, w); }  // typo
      if (qt && w.length >= 3) { var t = dice(qt, trigrams(w)); if (t >= 0.35) take(4 * t, w); }        // looks similar
    });
    return best;
  }

  /* Score a whole query against a broadcast; returns {score, hits[]}. */
  function scoreEpisode(ep, tokens, phrase) {
    var total = 0, strong = 0, hits = [];
    tokens.forEach(function (t) {
      var m = matchWord(t, ep);
      if (/^[a-z]{3,}$/.test(t)) { var g = matchWord(greeklish(t), ep); if (g.s > m.s) m = g; }
      total += m.s;
      if (m.s >= 4.5) strong++;
      if (m.hit && m.s >= 2) hits.push(m.hit);
    });
    if (tokens.length > 1 && strong === tokens.length) total += 4;            // every word matched
    if (phrase && phrase.indexOf(" ") > 0 && ep.norm.indexOf(phrase) !== -1) total += 6;  // exact phrase
    return { score: total, hits: hits };
  }

  /* Ranked results for a query; `approx` when nothing matched well. */
  function search(eps, q) {
    var all = words(q), tokens = all.filter(function (t) { return !STOP[t]; });
    if (!tokens.length) tokens = all;
    if (!tokens.length) return { list: eps.map(function (e) { return { ep: e, hits: [] }; }), approx: false };
    var phrase = norm(q).replace(/\s+/g, " ").trim();
    var scored = eps.map(function (e) { var r = scoreEpisode(e, tokens, phrase); return { ep: e, score: r.score, hits: r.hits }; })
      .filter(function (r) { return r.score > 0; })
      .sort(function (a, b) { return b.score - a.score || (a.ep.id < b.ep.id ? 1 : -1); });
    if (!scored.length) return { list: [], approx: false };
    var top = scored[0].score, good = 4.5 * Math.max(1, Math.ceil(tokens.length / 2));
    if (top >= good) {
      // keep everything reasonably close to the best match
      return { list: scored.filter(function (r) { return r.score >= Math.max(4, top * 0.35); }), approx: false };
    }
    return { list: scored.slice(0, 12), approx: true };                       // nothing good: closest ones
  }

  function esc(s) { return String(s).replace(/[&<>"']/g, function (c) { return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]; }); }

  function highlight(title, tokens) {
    if (!tokens.length) return esc(title);
    var chars = Array.from(title), normed = "", map = [];
    chars.forEach(function (c, i) { var n = normChar(c); for (var k = 0; k < n.length; k++) { normed += n[k]; map.push(i); } });
    var mark = new Array(chars.length).fill(false);
    tokens.forEach(function (t) {
      var from = 0, at;
      while ((at = normed.indexOf(t, from)) !== -1) {
        for (var j = at; j < at + t.length; j++) mark[map[j]] = true;
        from = at + t.length;
      }
    });
    var out = "", open = false;
    chars.forEach(function (c, i) {
      if (mark[i] && !open) { out += "<mark>"; open = true; }
      if (!mark[i] && open) { out += "</mark>"; open = false; }
      out += esc(c);
    });
    return out + (open ? "</mark>" : "");
  }

  /* ---------- progress ---------- */
  var PROG = store.get("cs-progress", {});
  function prog(id) { return PROG[id] || (PROG[id] = { t: [], d: [] }); }
  var saveProgT = 0;
  function saveProgress(force) {
    var now = Date.now();
    if (!force && now - saveProgT < 4000) return;
    saveProgT = now; store.set("cs-progress", PROG);
  }
  function partPct(id, i) {
    var p = PROG[id]; if (!p || !p.d[i]) return 0;
    return Math.min(100, (p.t[i] || 0) / p.d[i] * 100);
  }

  /* ---------- icons ---------- */
  var I = {
    play: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M8 5.5v13l11-6.5z"/></svg>',
    pause: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M7 5h3.5v14H7zM13.5 5H17v14h-3.5z"/></svg>',
    dl: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 4v11M7 10l5 5 5-5M5 20h14"/></svg>'
  };

  function partsHTML(ep) {
    var h = '<div class="parts" style="--n:' + ep.parts.length + '" role="group" aria-label="' + T.partsAria + '">';
    ep.parts.forEach(function (_, i) {
      var pct = partPct(ep.id, i);
      h += '<button class="part' + (pct > 97 ? " is-done" : "") + (pct >= 1 ? " has-progress" : "") + '" data-ep="' + ep.id + '" data-part="' + i + '" style="--p:' + pct.toFixed(1) + '%" aria-label="' + T.listenPart(i + 1) + '">' +
        T.partBtn(i + 1) + '<span class="part__track" aria-hidden="true"><span class="part__fill"></span></span></button>';
    });
    return h + "</div>";
  }

  /* ---------- latest ---------- */
  function renderLatest() {
    var ep = EPISODES[0]; if (!ep) return;
    $("#latest").innerHTML =
      '<button class="latest__play" data-play="' + ep.id + '" aria-label="' + esc(T.listenLatest(ep.title)) + '">' + I.play + "</button>" +
      '<div><p class="latest__label">' + T.latest + '</p><h2 class="latest__title">' + esc(ep.title) + '</h2>' +
      '<p class="latest__meta">' + ep.dateLong + ", " + T.season(ep.season) + ", " + T.partsCount(ep.parts.length) + "</p></div>" +
      partsHTML(ep);
  }

  /* ---------- resume ---------- */
  function renderResume() {
    var last = store.get("cs-last", null), box = $("#resume");
    var ep = last && BY_ID[last.id];
    if (!ep || (player.ep && player.ep.id === ep.id)) { box.hidden = true; return; }
    box.hidden = false;
    box.innerHTML = '<div class="resume__card"><div class="resume__txt"><p class="resume__label">' + T.resumeLabel(last.part + 1, fmt(last.t)) + '</p>' +
      '<p class="resume__title">' + esc(ep.title) + '</p></div>' +
      '<button class="resume__btn" id="resumeBtn">' + T.resume + '</button>' +
      '<button class="iconbtn resume__x" id="resumeX" aria-label="' + T.hide + '"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M6 6l12 12M18 6 6 18"/></svg></button></div>';
    $("#resumeBtn").onclick = function () { player.load(ep, last.part, last.t, true); };
    $("#resumeX").onclick = function () { store.del("cs-last"); box.hidden = true; };
  }

  /* ---------- archive ---------- */
  var state = { season: "all", q: "" };
  var seasonBar = $("#seasonBar");
  (function () {
    var h = '<button class="chip" data-season="all" aria-pressed="true">' + T.allSeasons + "</button>";
    SEASONS.forEach(function (s) { h += '<button class="chip" data-season="' + s.n + '" aria-pressed="false">' + T.season(s.n) + "</button>"; });
    seasonBar.innerHTML = h;
  })();
  seasonBar.addEventListener("click", function (e) {
    var b = e.target.closest(".chip"); if (!b) return;
    state.season = b.dataset.season;
    $$(".chip", seasonBar).forEach(function (c) { c.setAttribute("aria-pressed", c === b); });
    renderList();
  });

  var totalParts = EPISODES.reduce(function (a, e) { return a + e.parts.length; }, 0);
  $("#archiveStats").textContent = T.stats(EPISODES.length, SEASONS.length, Math.round(totalParts / 2));

  function epHTML(e, hits, showSeason) {
    var active = player.ep && player.ep.id === e.id;
    return '<article class="ep' + (active ? " is-active" : "") + '" id="e-' + e.id + '" data-id="' + e.id + '">' +
      '<div class="ep__date"><span class="ep__day">' + e.d + '</span><span class="ep__mon">' + T.monthsShort[e.m - 1] + " " + e.y + "</span></div>" +
      '<div><h4 class="ep__title">' + highlight(e.title, hits) + "</h4>" +
      '<p class="ep__links">' + (showSeason ? '<span class="ep__season">' + T.season(e.season) + "</span>" : "") +
      (e.link ? '<a href="' + esc(e.link) + '">' + T.sources + "</a>" : "") +
      '<button data-share="' + e.id + '">' + T.copyLink + "</button></p></div>" +
      partsHTML(e) +
      '<div class="ep__actions"><button class="ep__play" data-play="' + e.id + '" aria-label="' + esc(T.listen(e.title)) + '">' + (active && player.playing ? I.pause : I.play) + "</button>" +
      '<div class="ep__dl"><button class="iconbtn" data-dl="' + e.id + '" aria-haspopup="true" aria-expanded="false" aria-label="' + T.download + '">' + I.dl + "</button></div></div>" +
      "</article>";
  }

  function renderList() {
    var html = "", shown = 0, approx = false;
    var pool = EPISODES.filter(function (e) { return state.season === "all" || String(e.season) === state.season; });
    if (state.q) {
      // one list, best matches first
      var res = search(pool, state.q);
      shown = res.list.length; approx = res.approx;
      if (shown) {
        html += '<section class="season" aria-label="' + T.searchAria + '"><header class="season__head"><h3 class="season__title">' +
          (approx ? T.closest : T.results) + '</h3><span class="season__span">' + T.byRelevance + "</span>" +
          '<span class="season__count">' + T.count(shown) + "</span></header>";
        res.list.forEach(function (r) { html += epHTML(r.ep, r.hits, true); });
        html += "</section>";
      }
    } else {
      SEASONS.forEach(function (s) {
        var eps = pool.filter(function (e) { return e.season === s.n; });
        if (!eps.length) return;
        shown += eps.length;
        html += '<section class="season" aria-label="' + T.seasonAria(s.n) + '"><header class="season__head"><h3 class="season__title">' + T.season(s.n) + "</h3>" +
          '<span class="season__span">' + s.span + '</span><span class="season__count">' + T.count(eps.length) + "</span></header>";
        eps.forEach(function (e) { html += epHTML(e, [], false); });
        html += "</section>";
      });
    }
    $("#list").innerHTML = html;
    $("#empty").hidden = shown > 0;
    $("#results").textContent = !state.q ? "" : !shown ? "" : approx
      ? T.approx(state.q)
      : T.found(shown, state.q);
    if (player.ep) syncParts();
  }

  var qIn = $("#q"), qT;
  qIn.addEventListener("input", function () { clearTimeout(qT); qT = setTimeout(function () { state.q = qIn.value.trim(); renderList(); }, 120); });
  $("#clearSearch").addEventListener("click", function () {
    qIn.value = ""; state.q = ""; state.season = "all";
    $$(".chip", seasonBar).forEach(function (c) { c.setAttribute("aria-pressed", c.dataset.season === "all"); });
    renderList(); qIn.focus();
  });
  $("#searchJump").addEventListener("click", function () { $("#archive").scrollIntoView({ behavior: "smooth" }); setTimeout(function () { qIn.focus({ preventScroll: true }); }, 350); });

  /* ---------- delegated clicks ---------- */
  document.addEventListener("click", function (e) {
    var t;
    if ((t = e.target.closest("[data-play]"))) {
      var ep = BY_ID[t.dataset.play];
      if (player.ep && player.ep.id === ep.id) { player.toggle(); return; }
      var p = PROG[ep.id], start = 0, part = 0;
      if (p) { for (var i = 0; i < ep.parts.length; i++) { if (partPct(ep.id, i) < 97) { part = i; start = p.t[i] || 0; break; } } }
      player.load(ep, part, start, true); return;
    }
    if ((t = e.target.closest(".part[data-ep]"))) {
      var ep2 = BY_ID[t.dataset.ep], i2 = +t.dataset.part;
      if (player.ep && player.ep.id === ep2.id && player.part === i2) { player.toggle(); return; }
      var pp = PROG[ep2.id], st = pp && partPct(ep2.id, i2) < 97 ? (pp.t[i2] || 0) : 0;
      player.load(ep2, i2, st, true); return;
    }
    if ((t = e.target.closest("[data-share]"))) {
      var url = location.href.split("#")[0] + "#e-" + t.dataset.share;
      (navigator.clipboard ? navigator.clipboard.writeText(url) : Promise.reject()).then(
        function () { toast(T.copied); },
        function () { prompt(T.copyPrompt, url); });
      return;
    }
    if ((t = e.target.closest("[data-dl]"))) {
      var wrap = t.parentNode, open = wrap.querySelector(".dlmenu");
      closeMenus();
      if (open) return;
      var ep3 = BY_ID[t.dataset.dl], m = document.createElement("div");
      m.className = "dlmenu"; m.setAttribute("role", "menu");
      m.innerHTML = ep3.parts.map(function (u, i) { return '<a role="menuitem" href="' + encodeURI(u) + '" download>' + I.dl + " " + T.dlItem(i + 1) + "</a>"; }).join("");
      wrap.appendChild(m); t.setAttribute("aria-expanded", "true");
      m.querySelector("a").focus();
      return;
    }
    if (!e.target.closest(".dlmenu")) closeMenus();
  });
  function closeMenus() { $$(".dlmenu").forEach(function (m) { m.previousElementSibling.setAttribute("aria-expanded", "false"); m.remove(); }); }

  /* ---------- player ---------- */
  var audio = $("#audio"), bar = $("#player"), seek = $("#seek");
  var SPEEDS = [1, 1.25, 1.5, 1.75, 2, .75];
  var player = {
    ep: null, part: 0, playing: false, speed: store.get("cs-speed", 1), pendingSeek: null,
    load: function (ep, part, startAt, autoplay) {
      this.ep = ep; this.part = part;
      bar.hidden = false; setPlayerH();
      bar.classList.add("is-loading");
      audio.src = encodeURI(ep.parts[part]);
      audio.playbackRate = this.speed;
      // drop the pending seek of a previous load, or it would apply to this file
      if (this.pendingSeek) audio.removeEventListener("loadedmetadata", this.pendingSeek);
      var self = this, once = function () {
        audio.removeEventListener("loadedmetadata", once); self.pendingSeek = null;
        if (startAt > 3 && startAt < audio.duration - 3) audio.currentTime = startAt;
      };
      this.pendingSeek = once;
      audio.addEventListener("loadedmetadata", once);
      if (autoplay) audio.play().catch(function () {});
      $("#pTitle").textContent = ep.title;
      $("#pMeta").textContent = T.meta(ep.dateLong, part + 1, ep.parts.length);
      $("#pDownload").href = encodeURI(ep.parts[part]);
      $("#pParts").innerHTML = partsHTML(ep);
      $("#resume").hidden = true;
      $$(".ep.is-active").forEach(function (el) { el.classList.remove("is-active"); });
      var row = $("#e-" + ep.id); if (row) row.classList.add("is-active");
      syncParts(); mediaSession();
      store.set("cs-last", { id: ep.id, part: part, t: startAt || 0 });
    },
    toggle: function () { if (!this.ep) return; audio.paused ? audio.play().catch(function () {}) : audio.pause(); },
    skip: function (s) { if (!isFinite(audio.duration)) return; audio.currentTime = Math.max(0, Math.min(audio.duration - .5, audio.currentTime + s)); },
    next: function () { if (this.ep && this.part < this.ep.parts.length - 1) this.load(this.ep, this.part + 1, 0, true); },
    prev: function () { if (this.ep && this.part > 0) this.load(this.ep, this.part - 1, 0, true); }
  };
  $("#speed").textContent = fmtSpeed(player.speed);

  function syncParts() {
    if (!player.ep) return;
    $$('.part[data-ep="' + player.ep.id + '"]').forEach(function (b) {
      var i = +b.dataset.part, cur = i === player.part;
      b.classList.toggle("is-current", cur);
      b.classList.toggle("is-playing", cur && player.playing);
      b.classList.toggle("is-done", partPct(player.ep.id, i) > 97);
      b.style.setProperty("--p", partPct(player.ep.id, i).toFixed(1) + "%");
      b.classList.toggle("has-progress", partPct(player.ep.id, i) >= 1);
    });
    $$("[data-play]").forEach(function (b) {
      var on = player.ep && b.dataset.play === player.ep.id && player.playing;
      b.innerHTML = on ? I.pause : I.play;
    });
  }

  audio.addEventListener("play", function () { player.playing = true; bar.classList.add("is-playing"); $("#playPause").setAttribute("aria-label", T.pause); syncParts(); });
  audio.addEventListener("pause", function () { player.playing = false; bar.classList.remove("is-playing"); $("#playPause").setAttribute("aria-label", T.play); syncParts(); saveProgress(true); });
  audio.addEventListener("waiting", function () { bar.classList.add("is-loading"); });
  audio.addEventListener("playing", function () { bar.classList.remove("is-loading"); });
  audio.addEventListener("canplay", function () { bar.classList.remove("is-loading"); });
  audio.addEventListener("timeupdate", function () {
    var d = audio.duration, t = audio.currentTime;
    if (!isFinite(d) || !d) return;
    seek.value = Math.round(t / d * 1000);
    seek.style.setProperty("--v", (t / d * 100) + "%");
    $("#pTime").textContent = fmt(t) + " / " + fmt(d);
    var p = prog(player.ep.id); p.t[player.part] = t; p.d[player.part] = d;
    saveProgress(false);
    store.set("cs-last", { id: player.ep.id, part: player.part, t: t });
    var pct = (t / d * 100).toFixed(1) + "%";
    $$('.part[data-ep="' + player.ep.id + '"][data-part="' + player.part + '"]').forEach(function (b) { b.style.setProperty("--p", pct); b.classList.toggle("has-progress", t / d >= .01); });
  });
  audio.addEventListener("ended", function () {
    var p = prog(player.ep.id); p.t[player.part] = p.d[player.part] = audio.duration || 1; saveProgress(true);
    if (player.part < player.ep.parts.length - 1) { toast(T.next(player.part + 2)); player.next(); }
    else { toast(T.finished); store.del("cs-last"); syncParts(); }
  });
  audio.addEventListener("error", function () {
    bar.classList.remove("is-loading", "is-playing");
    if (!audio.getAttribute("src")) return;
    toast(T.notFound(decodeURI(audio.getAttribute("src")).split("/").pop()));
  });

  seek.addEventListener("input", function () {
    if (isFinite(audio.duration)) { audio.currentTime = seek.value / 1000 * audio.duration; seek.style.setProperty("--v", seek.value / 10 + "%"); }
  });
  $("#playPause").addEventListener("click", function () { player.toggle(); });
  $("#back15").addEventListener("click", function () { player.skip(-15); });
  $("#fwd15").addEventListener("click", function () { player.skip(15); });
  $("#speed").addEventListener("click", function () {
    var i = SPEEDS.indexOf(player.speed); player.speed = SPEEDS[(i + 1) % SPEEDS.length];
    audio.playbackRate = player.speed; store.set("cs-speed", player.speed);
    this.textContent = fmtSpeed(player.speed);
  });
  $("#pClose").addEventListener("click", function () {
    audio.pause(); saveProgress(true); audio.removeAttribute("src"); audio.load();
    bar.hidden = true; player.ep = null; setPlayerH();
    $$(".ep.is-active").forEach(function (el) { el.classList.remove("is-active"); });
    $$(".part.is-current").forEach(function (b) { b.classList.remove("is-current", "is-playing"); });
    $$("[data-play]").forEach(function (b) { b.innerHTML = I.play; });
    renderResume();
  });

  function setPlayerH() { document.documentElement.style.setProperty("--player-h", bar.hidden ? "0px" : bar.offsetHeight + "px"); }
  window.addEventListener("resize", setPlayerH);

  function mediaSession() {
    if (!("mediaSession" in navigator) || !player.ep) return;
    navigator.mediaSession.metadata = new MediaMetadata({
      title: player.ep.title + " (" + T.part(player.part + 1) + ")",
      artist: T.site,
      album: T.seasonAria(player.ep.season)
    });
    var h = {
      play: function () { audio.play(); }, pause: function () { audio.pause(); },
      seekbackward: function () { player.skip(-15); }, seekforward: function () { player.skip(15); },
      previoustrack: function () { player.prev(); }, nexttrack: function () { player.next(); }
    };
    Object.keys(h).forEach(function (k) { try { navigator.mediaSession.setActionHandler(k, h[k]); } catch (e) {} });
  }

  /* ---------- keyboard ---------- */
  document.addEventListener("keydown", function (e) {
    var tag = (e.target.tagName || "").toLowerCase(), typing = tag === "input" || tag === "textarea";
    if (e.key === "Escape") { closeMenus(); if (nav.classList.contains("is-open")) { closeNav(); menuBtn.focus(); } if (typing) e.target.blur(); return; }
    if (typing || e.metaKey || e.ctrlKey || e.altKey) return;
    if (e.key === "/") { e.preventDefault(); $("#searchJump").click(); }
    if (!player.ep) return;
    if (e.key === " " && tag !== "button" && tag !== "a") { e.preventDefault(); player.toggle(); }
    if (e.key === "ArrowLeft" && tag !== "input") player.skip(-15);
    if (e.key === "ArrowRight" && tag !== "input") player.skip(15);
  });

  /* ---------- next live broadcast ---------- */
  var DAY = 864e5, SHOW = 2 * 36e5, TZ = "Europe/Athens";
  var athensFmt = new Intl.DateTimeFormat("en-GB", { timeZone: TZ, year: "numeric", month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit", hourCycle: "h23" });
  /* Wall-clock date/time in Athens for an instant. */
  function athensParts(ms) {
    var o = {};
    athensFmt.formatToParts(ms).forEach(function (p) { if (p.type !== "literal") o[p.type] = +p.value; });
    return { y: o.year, mo: o.month, d: o.day, h: o.hour, mi: o.minute };
  }
  /* Instant for an Athens wall-clock time (handles summer/winter time). */
  function athensWallToUtc(y, mo, d, h, mi) {
    var want = Date.UTC(y, mo - 1, d, h, mi), t = want;
    for (var i = 0; i < 3; i++) {
      var p = athensParts(t);
      t += want - Date.UTC(p.y, p.mo - 1, p.d, p.h, p.mi);
    }
    return t;
  }
  /* Next broadcast: every 14 days at the same Athens time as CFG.nextBroadcast. */
  function nextSlot() {
    var base = Date.parse(CFG.nextBroadcast), now = Date.now();
    if (isNaN(base)) return null;
    var p = athensParts(base), t = base, k = 0;
    while (now > t + SHOW) {
      k += 14;
      var day = new Date(Date.UTC(p.y, p.mo - 1, p.d + k));
      t = athensWallToUtc(day.getUTCFullYear(), day.getUTCMonth() + 1, day.getUTCDate(), p.h, p.mi);
    }
    return t;
  }
  $("#liveLink").href = CFG.liveUrl || "#";

  var pad = function (n) { return String(n).padStart(2, "0"); };
  function icsLocal(ms) { var p = athensParts(ms); return p.y + pad(p.mo) + pad(p.d) + "T" + pad(p.h) + pad(p.mi) + "00"; }
  function icsUtc(ms) { var d = new Date(ms); return d.getUTCFullYear() + pad(d.getUTCMonth() + 1) + pad(d.getUTCDate()) + "T" + pad(d.getUTCHours()) + pad(d.getUTCMinutes()) + pad(d.getUTCSeconds()) + "Z"; }
  function calendarFile(slot) {
    return ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//christianity-science.gr//EL", "CALSCALE:GREGORIAN",
      "BEGIN:VTIMEZONE", "TZID:" + TZ,
      "BEGIN:DAYLIGHT", "TZOFFSETFROM:+0200", "TZOFFSETTO:+0300", "TZNAME:EEST", "DTSTART:19700329T030000", "RRULE:FREQ=YEARLY;BYMONTH=3;BYDAY=-1SU", "END:DAYLIGHT",
      "BEGIN:STANDARD", "TZOFFSETFROM:+0300", "TZOFFSETTO:+0200", "TZNAME:EET", "DTSTART:19701025T040000", "RRULE:FREQ=YEARLY;BYMONTH=10;BYDAY=-1SU", "END:STANDARD",
      "END:VTIMEZONE",
      "BEGIN:VEVENT", "UID:cs-radio@christianity-science.gr", "DTSTAMP:" + icsUtc(Date.now()),
      "DTSTART;TZID=" + TZ + ":" + icsLocal(slot), "DTEND;TZID=" + TZ + ":" + icsLocal(slot + SHOW),
      "RRULE:FREQ=WEEKLY;INTERVAL=2", "SUMMARY:" + T.icsSummary,
      "URL:" + (CFG.liveUrl || ""), "DESCRIPTION:" + T.icsDesc, "END:VEVENT", "END:VCALENDAR"].join("\r\n");
  }

  var slot = nextSlot(), onairLabel = $("#onairLabel").textContent;
  function showSlot() {
    $("#nextDate").textContent = new Intl.DateTimeFormat(T.locale, { weekday: "long", day: "numeric", month: "long", timeZone: TZ }).format(slot);
    $("#calLink").href = "data:text/calendar;charset=utf-8," + encodeURIComponent(calendarFile(slot));
  }
  if (slot) {
    showSlot();
    var tick = function () {
      var box = $("#countdown");
      if (Date.now() > slot + SHOW) {                 // the show has ended: move on to the next one
        slot = nextSlot(); showSlot();
        $(".onair").classList.remove("is-live");
        $("#onairLabel").textContent = onairLabel; box.hidden = false;
      }
      var diff = slot - Date.now();
      if (diff <= 0) {
        $(".onair").classList.add("is-live");
        $("#onairLabel").textContent = T.onAir;
        box.innerHTML = ""; box.hidden = true; return;
      }
      var dd = Math.floor(diff / DAY), hh = Math.floor(diff / 36e5) % 24, mm = Math.floor(diff / 6e4) % 60, ss = Math.floor(diff / 1e3) % 60;
      var u = T.units(dd);
      box.innerHTML = [[dd, u[0]], [hh, u[1]], [mm, u[2]], [ss, u[3]]]
        .map(function (x) { return "<div><b>" + String(x[0]).padStart(2, "0") + "</b><span>" + x[1] + "</span></div>"; }).join("");
    };
    tick(); setInterval(tick, 1000);
  }

  /* ---------- column + video ---------- */
  if (CFG.latestColumn) {
    $("#colMonth").textContent = T.column(CFG.latestColumn.month);
    $("#colLink").textContent = CFG.latestColumn.title;
    $("#colLink").href = CFG.latestColumn.url;
  }
  $("#colAll").href = CFG.columnUrl || "#";
  if (CFG.youtubeId) {
    var poster = $("#videoPoster");
    poster.style.backgroundImage = "url(https://i.ytimg.com/vi/" + CFG.youtubeId + "/hqdefault.jpg)";
    poster.addEventListener("click", function () {
      $("#videoFrame").innerHTML = '<iframe src="https://www.youtube-nocookie.com/embed/' + CFG.youtubeId + '?autoplay=1" title="' + T.video + '" allow="autoplay; encrypted-media; picture-in-picture" allowfullscreen></iframe>';
    });
  }

  /* ---------- helpers ---------- */
  function fmt(s) { s = Math.max(0, Math.floor(s || 0)); var m = Math.floor(s / 60), h = Math.floor(m / 60); return (h ? h + ":" + String(m % 60).padStart(2, "0") : m) + ":" + String(s % 60).padStart(2, "0"); }
  function fmtSpeed(x) { return String(x).replace(".", ",") + "×"; }
  var toastT;
  function toast(msg) { var t = $("#toast"); t.textContent = msg; t.classList.add("is-on"); clearTimeout(toastT); toastT = setTimeout(function () { t.classList.remove("is-on"); }, 3200); }

  /* ---------- deep link #e-YYYY_MM_DD ---------- */
  function openHash() {
    var m = location.hash.match(/^#e-(\d{4}_\d{2}_\d{2})$/); if (!m || !BY_ID[m[1]]) return;
    var row = $("#e-" + m[1]); if (!row) { state.season = "all"; state.q = ""; qIn.value = ""; renderList(); row = $("#e-" + m[1]); }
    row.scrollIntoView({ block: "center" }); row.classList.remove("is-target"); void row.offsetWidth; row.classList.add("is-target");
  }
  window.addEventListener("hashchange", openHash);

  /* ---------- boot ---------- */
  renderLatest();
  renderList();
  renderResume();
  openHash();
})();
