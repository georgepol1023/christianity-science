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
  // a full address for an mp3: while another page is open in the frame (SiteShell below) this page's
  // address shows that page's, so a relative path would point to the wrong folder
  var PAGE = location.href;
  var fileURL = function (u) { return new URL(encodeURI(u), PAGE).href; };
  var EN_TITLES = window.BROADCAST_TITLES_EN || {};
  // topics (js/broadcasts.js); names in English from js/broadcasts-en.js
  var TAGS = {}, TAG_LIST = (window.BROADCAST_TAGS || []).map(function (t) {
    var en = (window.BROADCAST_TAGS_EN || {})[t.id];
    return (TAGS[t.id] = { id: t.id, name: (LANG === "en" && en) || t.name, el: t.name, hue: t.hue });
  });
  var RELATED = window.RELATED || {};                    // «Σχετικά» per broadcast, from js/related.js
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
      allSeasons: "Όλοι οι κύκλοι", allTags: "Όλα τα θέματα", topics: "Θέματα", topicsTitle: "Θέματα εκπομπών", close: "Κλείσιμο",
      tagFound: function (n, t) { return (n === 1 ? "1 εκπομπή" : n + " εκπομπές") + " με θέμα «" + t + "»."; },
      tagShow: function (t) { return "Όλες οι εκπομπές με θέμα «" + t + "»"; },
      stats: function (e, n, h) { return e + " εκπομπές σε " + n + " κύκλους, περίπου " + h + " ώρες ακρόασης."; },
      sources: "Άρθρα &amp; πηγές", copyLink: "Αντιγραφή συνδέσμου", related: "Σχετικά",
      relKind: { B: "Εκπομπή", C: "Από τη στήλη μας", T: "Θέμα", M: "Πολυμέσα", Q: "Ερώτηση" }, share: "Κοινοποίηση",
      listen: function (t) { return "Ακούστε: " + t; }, download: "Λήψη mp3",
      searchAria: "Αποτελέσματα αναζήτησης", results: "Αποτελέσματα", closest: "Πλησιέστερες εκπομπές", byRelevance: "κατά συνάφεια",
      count: function (n) { return n + (n === 1 ? " εκπομπή" : " εκπομπές"); },
      approx: function (q) { return "Δεν βρέθηκε ακριβής αντιστοιχία για «" + q + "». Δείτε τις πλησιέστερες εκπομπές."; },
      found: function (n, q) { return (n === 1 ? "Βρέθηκε 1 εκπομπή" : "Βρέθηκαν " + n + " εκπομπές") + " για «" + q + "»" + (n > 1 ? ", οι πιο σχετικές πρώτα." : "."); },
      copied: "Ο σύνδεσμος αντιγράφηκε.", copyPrompt: "Αντιγράψτε τον σύνδεσμο:",
      dlItem: function (n) { return n + "ο ημίωρο (mp3)"; }, dlAll: "Ολόκληρη η εκπομπή (ένα mp3)",
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
      allSeasons: "All seasons", allTags: "All topics", topics: "Topics", topicsTitle: "Broadcast topics", close: "Close",
      tagFound: function (n, t) { return (n === 1 ? "1 broadcast" : n + " broadcasts") + " on “" + t + "”."; },
      tagShow: function (t) { return "All broadcasts on “" + t + "”"; },
      stats: function (e, n, h) { return e + " broadcasts in " + n + " seasons, about " + h + " hours of listening. Audio in Greek."; },
      sources: "Articles &amp; sources (in Greek)", copyLink: "Copy link", related: "Related",
      relKind: { B: "Broadcast", C: "From our column", T: "Topic", M: "Media", Q: "Question" }, share: "Share",
      listen: function (t) { return "Listen: " + t; }, download: "Download mp3",
      searchAria: "Search results", results: "Results", closest: "Closest broadcasts", byRelevance: "most relevant first",
      count: function (n) { return n + (n === 1 ? " broadcast" : " broadcasts"); },
      approx: function (q) { return "No exact match for “" + q + "”. Here are the closest broadcasts."; },
      found: function (n, q) { return (n === 1 ? "Found 1 broadcast" : "Found " + n + " broadcasts") + " for “" + q + "”" + (n > 1 ? ", most relevant first." : "."); },
      copied: "Link copied.", copyPrompt: "Copy the link:",
      dlItem: function (n) { return "Part " + n + " (mp3)"; }, dlAll: "The whole broadcast (one mp3)",
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
        // the whole broadcast in one file, made by tools/join_broadcasts.py next to the parts
        full: parts.length > 1 ? parts[0].replace(/[^\/]*$/, "") + id + "_full.mp3" : null,
        title: (LANG === "en" && EN_TITLES[e.date]) || e.title,
        link: e.link && !/^[a-z]+:/i.test(e.link) ? ROOT + e.link : e.link,
        y: d[0], m: d[1], d: d[2],
        dateLong: d[2] + " " + T.months[d[1] - 1] + " " + d[0],
        tags: (e.tags || []).filter(function (t) { return TAGS[t]; }),
        norm: null, words: null
      };
      // search both the shown title and the Greek original, so Greek queries work on the English site too
      var both = ep.title === e.title ? ep.title : ep.title + " " + e.title;
      // topic names too (Greek and English), so «βιοηθική» finds the broadcasts on bioethics
      var topics = ep.tags.map(function (t) { return TAGS[t].name + (TAGS[t].el !== TAGS[t].name ? " " + TAGS[t].el : ""); }).join(" ");
      ep.norm = norm(both + " " + ep.dateLong + " " + T.monthsShort[d[1] - 1] + " " + d[0] + " " + T.seasonWord + " " + s.n + " " + topics);
      ep.words = norm(both).split(/[^0-9a-zα-ω]+/).filter(Boolean);
      EPISODES.push(ep); BY_ID[id] = ep;
    });
  });

  /* matching lives in js/search.js, shared with the lists on the other pages */
  function norm(s) { return window.SiteSearch.norm(s); }
  function normChar(c) { return norm(c); }
  function words(s) { return window.SiteSearch.words(s); }
  function search(eps, q) { return window.SiteSearch.search(eps, q); }
  var STOP = window.SiteSearch.stop;

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
    dl: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 4v11M7 10l5 5 5-5M5 20h14"/></svg>',
    link: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M10 14a4.5 4.5 0 0 0 6.4 0l3-3a4.5 4.5 0 0 0-6.4-6.4l-1.2 1.2"/><path d="M14 10a4.5 4.5 0 0 0-6.4 0l-3 3a4.5 4.5 0 0 0 6.4 6.4l1.2-1.2"/></svg>'
  };
  // phones and tablets share through their own menu (WhatsApp, Viber, e-mail…); computers copy the link
  var SHARE = !!navigator.share && matchMedia("(pointer: coarse)").matches;

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
  var state = { season: "all", tag: "all", q: "" };
  var seasonBar = $("#seasonBar");
  (function () {
    var h = '<span class="topicpick" id="tagPick"></span>' +
      '<button class="chip" data-season="all" aria-pressed="true">' + T.allSeasons + "</button>";
    SEASONS.forEach(function (s) { h += '<button class="chip" data-season="' + s.n + '" aria-pressed="false">' + T.season(s.n) + "</button>"; });
    seasonBar.innerHTML = h;
  })();
  seasonBar.addEventListener("click", function (e) {
    if (e.target.closest("#tagOpen")) { openTags(); return; }
    if (e.target.closest("[data-tag-clear]")) { setTag("all"); renderList(); return; }
    var b = e.target.closest(".chip[data-season]"); if (!b) return;
    state.season = b.dataset.season;
    $$(".chip[data-season]", seasonBar).forEach(function (c) { c.setAttribute("aria-pressed", c === b); });
    renderList();
  });

  /* ---------- topics ----------
   * One «Θέματα» button at the start of the season row opens a window with every topic (with how many
   * broadcasts it has); while a topic is chosen the button shows it, with ✕ next to it to show all again.
   * The coloured topics under each title choose the same filter. */
  var tagChip = function (t, on, extra) {
    return '<button class="' + (on ? "tag is-on" : "tag") + (t.hue < 0 ? " tag--plain" : "") + '" data-tag="' + t.id + '"' +
      (t.hue >= 0 ? ' style="--h:' + t.hue + '"' : "") + ">" + esc(t.name) + (extra || "") + "</button>";
  };
  var ICON_TOPICS = '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 6h16M7 12h10M10 18h4"/></svg>';
  var ICON_CLOSE = '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M6 6l12 12M18 6 6 18"/></svg>';
  var used = {};
  EPISODES.forEach(function (e) { e.tags.forEach(function (t) { used[t] = (used[t] || 0) + 1; }); });
  var tagDlg = document.createElement("dialog");
  tagDlg.className = "tagdlg";
  tagDlg.setAttribute("aria-labelledby", "tagDlgTitle");
  tagDlg.innerHTML = '<div class="tagdlg__head"><h2 class="tagdlg__title" id="tagDlgTitle">' + T.topicsTitle + "</h2>" +
    '<button class="iconbtn" data-close aria-label="' + T.close + '">' + ICON_CLOSE + "</button></div>" +
    '<div class="tagdlg__list"><button class="tag tag--plain is-on" data-tag="all">' + T.allTags + '<span class="tag__n">' + EPISODES.length + "</span></button>" +
    TAG_LIST.filter(function (t) { return used[t.id]; })
      .sort(function (a, b) { return (b.hue >= 0) - (a.hue >= 0) || used[b.id] - used[a.id]; })     // most used first
      .map(function (t) { return tagChip(t, false, '<span class="tag__n">' + used[t.id] + "</span>"); }).join("") +
    "</div>";
  document.body.appendChild(tagDlg);
  function openTags() {
    if (tagDlg.showModal) tagDlg.showModal(); else tagDlg.setAttribute("open", "");
    var on = $(".tag.is-on", tagDlg); if (on) on.focus();
  }
  function closeTags() { if (tagDlg.close) tagDlg.close(); else tagDlg.removeAttribute("open"); }
  tagDlg.addEventListener("click", function (e) {
    if (e.target === tagDlg || e.target.closest("[data-close]")) { closeTags(); return; }      // the backdrop, or ✕
    var b = e.target.closest("[data-tag]"); if (!b) return;
    setTag(b.dataset.tag); renderList(); closeTags();
    var top = $("#archive"); if (top && top.getBoundingClientRect().top < 0) top.scrollIntoView();
  });
  function setTag(id) {
    state.tag = TAGS[id] ? id : "all";
    var t = TAGS[state.tag];
    $("#tagPick").innerHTML = t
      ? '<button class="chip chip--topics is-set" id="tagOpen" aria-haspopup="dialog"' + (t.hue >= 0 ? ' style="--h:' + t.hue + '"' : "") + ">" + esc(t.name) + "</button>" +
        '<button class="chip chip--clear" data-tag-clear aria-label="' + T.allTags + '">' + ICON_CLOSE + "</button>"
      : '<button class="chip chip--topics" id="tagOpen" aria-haspopup="dialog">' + ICON_TOPICS + T.topics + "</button>";
    $$("[data-tag]", tagDlg).forEach(function (b) { b.classList.toggle("is-on", b.dataset.tag === state.tag); });
  }
  setTag("all");

  var totalParts = EPISODES.reduce(function (a, e) { return a + e.parts.length; }, 0);
  $("#archiveStats").textContent = T.stats(EPISODES.length, SEASONS.length, Math.round(totalParts / 2));

  function epHTML(e, hits, showSeason) {
    var active = player.ep && player.ep.id === e.id;
    return '<article class="ep' + (active ? " is-active" : "") + '" id="e-' + e.id + '" data-id="' + e.id + '">' +
      '<div class="ep__date"><span class="ep__day">' + e.d + '</span><span class="ep__mon">' + T.monthsShort[e.m - 1] + " " + e.y + "</span></div>" +
      '<div><h4 class="ep__title">' + highlight(e.title, hits) + "</h4>" +
      (e.tags.length ? '<p class="ep__tags">' + e.tags.map(function (t) {
        return tagChip(TAGS[t], t === state.tag).replace(">", ' title="' + esc(T.tagShow(TAGS[t].name)) + '">');
      }).join("") + "</p>" : "") +
      '<p class="ep__links">' + (showSeason ? '<span class="ep__season">' + T.season(e.season) + "</span>" : "") +
      (e.link ? '<a href="' + esc(e.link) + '">' + T.sources + "</a>" : "") +
      (RELATED[e.id] ? '<span class="ep__rel"><button data-rel="' + e.id + '" aria-haspopup="true" aria-expanded="false">' + T.related + "</button></span>" : "") +
      '<button class="ep__share" data-share="' + e.id + '" aria-label="' + (SHARE ? T.share : T.copyLink) + '" title="' + (SHARE ? T.share : T.copyLink) + '">' +
      I.link + "</button></p></div>" +
      partsHTML(e) +
      '<div class="ep__actions"><button class="ep__play" data-play="' + e.id + '" aria-label="' + esc(T.listen(e.title)) + '">' + (active && player.playing ? I.pause : I.play) + "</button>" +
      '<div class="ep__dl"><button class="iconbtn" data-dl="' + e.id + '" aria-haspopup="true" aria-expanded="false" aria-label="' + T.download + '">' + I.dl + "</button></div></div>" +
      "</article>";
  }

  function renderList() {
    var html = "", shown = 0, approx = false;
    var pool = EPISODES.filter(function (e) {
      return (state.season === "all" || String(e.season) === state.season) && (state.tag === "all" || e.tags.indexOf(state.tag) !== -1);
    });
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
    $("#results").textContent = !state.q ? (state.tag !== "all" && shown ? T.tagFound(shown, TAGS[state.tag].name) : "") : !shown ? "" : approx
      ? T.approx(state.q)
      : T.found(shown, state.q);
    if (player.ep) syncParts();
  }

  var qIn = $("#q"), qT;
  qIn.addEventListener("input", function () { clearTimeout(qT); qT = setTimeout(function () { state.q = qIn.value.trim(); renderList(); }, 120); });
  $("#clearSearch").addEventListener("click", function () {
    qIn.value = ""; state.q = ""; state.season = "all"; setTag("all");
    $$(".chip[data-season]", seasonBar).forEach(function (c) { c.setAttribute("aria-pressed", c.dataset.season === "all"); });
    renderList(); qIn.focus();
  });

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
    if ((t = e.target.closest(".ep__tags [data-tag]"))) {
      setTag(state.tag === t.dataset.tag ? "all" : t.dataset.tag);
      renderList();
      var top = $("#archive"); if (top) top.scrollIntoView({ behavior: "smooth" });
      return;
    }
    if ((t = e.target.closest('.dlmenu a[href^="#e-"]'))) {
      e.preventDefault(); closeMenus();
      var h = t.getAttribute("href");
      if (location.hash === h) openHash(); else location.hash = h;
      return;
    }
    if ((t = e.target.closest("[data-share]"))) {
      var url = PAGE.split("#")[0] + "#e-" + t.dataset.share;
      if (SHARE) { navigator.share({ title: BY_ID[t.dataset.share].title + " – " + T.site, url: url }).catch(function () {}); return; }
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
      m.innerHTML = (ep3.full ? '<a role="menuitem" class="dlmenu__all" href="' + encodeURI(ep3.full) + '" download="Christianity-Science_' + ep3.id.replace(/_/g, "-") + '.mp3">' +
          I.dl + " " + T.dlAll + '</a><span class="dlmenu__sep" role="separator"></span>' : "") +
        ep3.parts.map(function (u, i) { return '<a role="menuitem" href="' + encodeURI(u) + '" download>' + I.dl + " " + T.dlItem(i + 1) + "</a>"; }).join("");
      wrap.appendChild(m); t.setAttribute("aria-expanded", "true");
      m.querySelector("a").focus();
      return;
    }
    if ((t = e.target.closest("[data-rel]"))) {             // «Σχετικά»: related articles, topics, questions
      var wrapR = t.parentNode, openR = wrapR.querySelector(".dlmenu");
      closeMenus();
      if (openR) return;
      var mr = document.createElement("div");
      mr.className = "dlmenu dlmenu--rel"; mr.setAttribute("role", "menu");
      mr.innerHTML = RELATED[t.dataset.rel].map(function (r) {
        var en = LANG === "en" && r[3], title = en ? r[3] : r[2];
        if (r[0] === "B") {                                      // another broadcast: go to it in this archive
          var b = BY_ID[r[1].split("#e-")[1]]; if (!b) return "";
          return '<a role="menuitem" href="#e-' + b.id + '"><span class="dlmenu__kind">' + T.relKind.B + " · " +
            b.d + " " + T.monthsShort[b.m - 1] + " " + b.y + "</span>" + esc(b.title) + "</a>";
        }
        return '<a role="menuitem" href="' + ROOT + r[1] + '"' + (LANG === "en" && !en ? ' lang="el"' : "") + '><span class="dlmenu__kind">' +
          T.relKind[r[0]] + "</span>" + title + "</a>";
      }).join("");
      wrapR.appendChild(mr); t.setAttribute("aria-expanded", "true");
      mr.querySelector("a").focus();
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
      audio.src = fileURL(ep.parts[part]);
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
      $("#pDownload").href = fileURL(ep.parts[part]);
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
    // the broadcast played before no longer looks current
    $$(".part.is-current").forEach(function (b) {
      if (b.dataset.ep && b.dataset.ep !== player.ep.id) b.classList.remove("is-current", "is-playing");
    });
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
    $("#colLink").textContent = (window.COLUMN_TITLES_EN || {})[CFG.latestColumn.url] || CFG.latestColumn.title;
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
    var row = $("#e-" + m[1]);
    if (!row) {
      state.season = "all"; state.q = ""; qIn.value = ""; setTag("all");
      $$(".chip[data-season]", seasonBar).forEach(function (c) { c.setAttribute("aria-pressed", c.dataset.season === "all"); });
      renderList(); row = $("#e-" + m[1]);
    }
    land(row); row.classList.remove("is-target"); void row.offsetWidth; row.classList.add("is-target");
  }
  // put the broadcast a little below the middle of the free space under the top bar and the season chips
  function land(row) {
    var bar = $("#seasonBar"), top = 70;                          // where the sticky bars end once they stick
    if (bar) top = (parseFloat(getComputedStyle(bar).top) || 0) + bar.offsetHeight;
    var free = innerHeight - top, r = row.getBoundingClientRect();
    // "instant": the page scrolls smoothly otherwise, which takes seconds from the top to an old broadcast
    scrollTo({ top: scrollY + r.top - top - Math.max(24, (free - r.height) * 0.4), behavior: "instant" });
  }
  window.addEventListener("hashchange", openHash);
  // the browser also jumps to #e-… by itself once the page has loaded; land the broadcast again after it
  window.addEventListener("load", function () { setTimeout(function () { if (/^#e-/.test(location.hash)) openHash(); }, 0); });

  /* ---------- nav: underline "Broadcasts" only once the archive is on screen ---------- */
  var archLink = $('.nav a[href="#archive"]'), archive = $("#archive");
  function markArchive() {
    if (!archLink || !archive) return;
    var on = archive.getBoundingClientRect().top < window.innerHeight * 0.5;
    if (on) archLink.setAttribute("aria-current", "page"); else archLink.removeAttribute("aria-current");
  }
  window.addEventListener("scroll", markArchive, { passive: true });
  window.addEventListener("resize", markArchive);
  window.addEventListener("hashchange", markArchive);
  markArchive();

  /* ---------- keep playing while browsing the site ----------
   * While a broadcast is loaded, a link to another page of the site opens that page in a frame over
   * this one (#shell); this page – and the player bar with its <audio> – stays alive underneath, so
   * the broadcast does not stop. The address bar, title and Back button follow the page in the frame.
   * Links back to this page close the frame. The page in the frame talks to this one with messages
   * ({cs: …}), which also work when the site is opened from a folder (file://), and uses this page's
   * player instead of its own. */
  var sameSite = function (u) { return u.protocol === location.protocol && u.host === location.host; };
  var homePath = function (p) { return p.replace(/index\.html$/, ""); };

  if (window.parent === window) {
    var shell = null, shellScroll = 0, shellHref = "", shell0 = document.title;
    var HOME = location.pathname;                              // this page's address (the frame changes location)
    var here = function (u) { return sameSite(u) && homePath(u.pathname) === homePath(HOME); };
    var playState = function () { return player.ep ? { id: player.ep.id, part: player.part, playing: player.playing } : null; };
    var tell = function (msg) {
      if (shell && shell.contentWindow) shell.contentWindow.postMessage(msg, location.protocol === "file:" ? "*" : location.origin);
    };
    var oldSync = syncParts;
    syncParts = function () { oldSync(); tell({ cs: "state", state: playState() }); };
    // the address bar cannot be changed for pages opened from a folder; the frame still works
    var setURL = function (push, st, url) { try { history[push ? "pushState" : "replaceState"](st, "", url); } catch (e) {} };
    var pageLink = function (a, e) {                           // a link to another page of this site?
      if (!a || e.defaultPrevented || e.button || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) return null;
      if (a.hasAttribute("download") || (a.target && a.target !== "_self")) return null;
      var u = new URL(a.href, location.href);
      if (!sameSite(u) || here(u)) return null;
      return /\.html?$|\/$/.test(u.pathname) ? u : null;     // pages only, not mp3 or pdf
    };
    var closeShell = function (hash) {
      if (!shell) return;
      shell.remove(); shell = null; shellHref = "";
      document.documentElement.classList.remove("shell-on");
      document.title = shell0;
      setURL(false, null, HOME + (hash || ""));
      if (hash && /^#e-/.test(hash)) openHash();
      else if (hash) { var t = document.getElementById(hash.slice(1)); if (t) t.scrollIntoView(); }
      else scrollTo(0, shellScroll);
      markArchive();
    };
    var pageShown = function (href, title) {                       // a page has opened in the frame
      var u = new URL(href);
      if (u.protocol === "about:") return;                     // the empty frame before the page loads
      if (here(u)) { closeShell(u.hash); return; }             // came back to this page inside the frame
      shellHref = u.href;
      if (title) document.title = title;
      setURL(false, { shell: true }, u.href);
    };
    var openShell = function (url) {
      if (!shell) {
        shellScroll = scrollY;
        shell = document.createElement("iframe");
        shell.id = "shell"; shell.title = T.site;
        shell.addEventListener("load", function () {           // also for pages without the site's scripts
          try { var w = shell.contentWindow; pageShown(w.location.href, w.document.title); } catch (err) {}
        });
        document.body.appendChild(shell);
        setURL(true, { shell: true }, url);
        document.documentElement.classList.add("shell-on");
      }
      shell.src = url;
    };
    window.addEventListener("message", function (e) {
      var m = e.data;
      if (!shell || e.source !== shell.contentWindow || !m || typeof m.cs !== "string") return;
      if (m.cs === "hello") { tell({ cs: "shell", home: HOME, state: playState() }); if (m.href) pageShown(m.href, m.title); }
      else if (m.cs === "home") closeShell(m.hash || "");
      else if (m.cs === "load") { if (BY_ID[m.id]) player.load(BY_ID[m.id], m.part, m.start, m.autoplay); }
      else if (m.cs === "toggle") player.toggle();
      else if (m.cs === "skip") player.skip(m.s);
    });
    document.addEventListener("click", function (e) {
      if (!player.ep) return;                                  // nothing playing: links work as usual
      var u = pageLink(e.target.closest("a[href]"), e);
      if (!u) return;
      e.preventDefault();
      openShell(u.href);
    });
    window.addEventListener("popstate", function (e) { if (shell && !(e.state && e.state.shell)) closeShell(location.hash); });
    // closing the player: leave the frame for the real page, so the site behaves as usual again
    $("#pClose").addEventListener("click", function () {
      if (shell) { if (shellHref) location.href = shellHref; else closeShell(""); }
    });
    // light/dark chosen inside the frame applies here too
    window.addEventListener("storage", function (e) {
      if (e.key === "cs-theme") { var v = store.get("cs-theme", null); if (v) document.documentElement.setAttribute("data-theme", v); }
    });
  } else {
    // perhaps shown in the home page's frame: ask; if so, use the main player instead of a second one
    var HOME_IN = null;
    var up = function (msg) { window.parent.postMessage(msg, "*"); };
    var follow = function (s) {
      player.ep = s ? BY_ID[s.id] || null : null; player.part = s ? s.part : 0; player.playing = !!(s && s.playing);
      $$(".ep.is-active").forEach(function (el) { el.classList.remove("is-active"); });
      if (player.ep) { var row = $("#e-" + player.ep.id); if (row) row.classList.add("is-active"); }
      syncParts();
    };
    window.addEventListener("message", function (e) {
      var m = e.data;
      if (e.source !== window.parent || !m || (e.origin !== location.origin && location.protocol !== "file:")) return;
      if (m.cs === "shell" && !HOME_IN) {
        HOME_IN = m.home;
        document.documentElement.classList.add("in-shell");
        audio.pause(); bar.hidden = true;
        player.load = function (ep, part, start, autoplay) { up({ cs: "load", id: ep.id, part: part, start: start, autoplay: autoplay }); };
        player.toggle = function () { up({ cs: "toggle" }); };
        player.skip = function (s) { up({ cs: "skip", s: s }); };
      }
      if ((m.cs === "shell" || m.cs === "state") && HOME_IN) follow(m.state);
    });
    document.addEventListener("click", function (e) {
      if (!HOME_IN) return;
      var a = e.target.closest("a[href]");
      if (!a || e.defaultPrevented || e.button || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) return;
      var u = new URL(a.href, location.href);
      if (!sameSite(u)) { if (!a.target) { a.target = "_blank"; a.rel = "noopener"; } return; }
      if (homePath(u.pathname) === homePath(HOME_IN)) { e.preventDefault(); up({ cs: "home", hash: u.hash }); }
    });
    up({ cs: "hello", href: location.href, title: document.title });
  }

  /* ---------- boot ---------- */
  renderLatest();
  renderList();
  renderResume();
  openHash();
})();
