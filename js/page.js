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

  /* ---------- filter (άρθρα, στήλη εφημερίδας, ερωτήσεις) ----------
   * The same forgiving search as the broadcast archive (js/search.js): typos, word forms, Greeklish,
   * partial words; best matches first. data-keys="…" on an item adds words to search (e.g. the Greek
   * title on the English page). Without js/search.js it falls back to plain matching.
   * The newspaper column also has topics (data-tags, names and colours from js/tags.js) and years
   * (data-year): a «Θέματα» button and year chips in #colBar, as in the broadcast archive. */
  function norm(s) { return s.normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase().replace(/ς/g, "σ"); }
  function esc(s) { return String(s).replace(/[&<>"]/g, function (c) { return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]; }); }
  var input = $("#filter");
  if (input) {
    var EN = document.documentElement.lang === "en";
    var L = EN ? { topics: "Topics", topicsTitle: "Article topics", all: "All topics", close: "Close", show: function (t) { return "All articles on “" + t + "”"; } }
               : { topics: "Θέματα", topicsTitle: "Θέματα άρθρων", all: "Όλα τα θέματα", close: "Κλείσιμο", show: function (t) { return "Όλα τα άρθρα με θέμα «" + t + "»"; } };
    var TAGS = {};
    (window.BROADCAST_TAGS || []).forEach(function (t) { TAGS[t.id] = { id: t.id, name: (EN && t.en) || t.name, el: t.name, hue: t.hue }; });
    var tagBtn = function (t, on, extra) {
      return '<button class="' + (on ? "tag is-on" : "tag") + (t.hue < 0 ? " tag--plain" : "") + '" data-tag="' + t.id + '"' +
        (t.hue >= 0 ? ' style="--h:' + t.hue + '"' : "") + ">" + esc(t.name) + (extra || "") + "</button>";
    };
    // the topics under each article (before the search reads the text, so a topic's name finds its articles)
    $$("[data-filter][data-tags]").forEach(function (el) {
      var ids = el.getAttribute("data-tags").split(/\s+/).filter(function (t) { return TAGS[t]; });
      if (!ids.length) return;
      var p = document.createElement("p");
      p.className = "ep__tags";
      p.innerHTML = ids.map(function (t) { return tagBtn(TAGS[t]).replace(">", ' title="' + esc(L.show(TAGS[t].name)) + '">'); }).join("");
      (el.querySelector(".ref__body") || el).appendChild(p);
      el.setAttribute("data-keys", (el.getAttribute("data-keys") || "") + " " + ids.map(function (t) { return TAGS[t].el; }).join(" "));
    });

    var SS = window.SiteSearch;
    var items = $$("[data-filter]").map(function (el, i) {
      var text = el.textContent + " " + (el.getAttribute("data-keys") || "");
      var it = SS ? SS.prepare(text) : { norm: norm(text) };
      it.el = el; it.id = -i; it.parent = el.parentNode;     // id: ties keep the page's own order
      it.year = el.getAttribute("data-year") || "";
      it.tags = (el.getAttribute("data-tags") || "").split(/\s+/);
      return it;
    });
    var groups = items.map(function (it) { return it.parent; }).filter(function (p, i, a) { return a.indexOf(p) === i; });
    var empty = $("#filterEmpty");
    var near = document.createElement("p");
    near.className = "empty"; near.hidden = true;
    near.textContent = EN ? "No exact match – these are the closest:" : "Δεν βρέθηκε ακριβές αποτέλεσμα – τα πλησιέστερα:";
    var anchor = empty || input.closest("label") || input;
    anchor.parentNode.insertBefore(near, anchor);
    var want = { tag: "all", year: "all" };

    function apply() {
      var q = input.value.trim(), res;
      var pool = items.filter(function (it) {
        return (want.year === "all" || it.year === want.year) && (want.tag === "all" || it.tags.indexOf(want.tag) !== -1);
      });
      if (!q) {
        res = { list: pool.map(function (it) { return { ep: it }; }), approx: false };
      } else if (SS) {
        res = SS.search(pool, q);
      } else {
        var tokens = norm(q).split(/\s+/).filter(Boolean);
        res = { list: pool.filter(function (it) { return tokens.every(function (t) { return it.norm.indexOf(t) !== -1; }); })
                          .map(function (it) { return { ep: it }; }), approx: false };
      }
      items.forEach(function (it) { it.el.hidden = true; });
      res.list.forEach(function (r) { r.ep.el.hidden = false; r.ep.parent.appendChild(r.ep.el); });   // in ranked order
      if (!q) items.forEach(function (it) { it.parent.appendChild(it.el); });                         // back to the page's order
      groups.forEach(function (g) {                // a list with no matches hides, with its heading (column: one per year)
        var none = !g.querySelector(":scope > [data-filter]:not([hidden])"), head = g.previousElementSibling;
        g.hidden = none;
        if (head && /^H[2-4]$/.test(head.tagName)) head.hidden = none;
      });
      near.hidden = !res.approx;
      if (empty) empty.hidden = res.list.length > 0;
      $$(".ep__tags .tag").forEach(function (b) { b.classList.toggle("is-on", b.dataset.tag === want.tag); });
    }
    input.addEventListener("input", apply);

    /* topics and years (the newspaper column) */
    var bar = $("#colBar"), pick = $("#tagPick");
    if (bar && pick && Object.keys(TAGS).length) {
      var used = {};
      items.forEach(function (it) { it.tags.forEach(function (t) { if (TAGS[t]) used[t] = (used[t] || 0) + 1; }); });
      var ICON_TOPICS = '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 6h16M7 12h10M10 18h4"/></svg>';
      var ICON_CLOSE = '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M6 6l12 12M18 6 6 18"/></svg>';
      var dlg = document.createElement("dialog");
      dlg.className = "tagdlg";
      dlg.setAttribute("aria-labelledby", "tagDlgTitle");
      dlg.innerHTML = '<div class="tagdlg__head"><h2 class="tagdlg__title" id="tagDlgTitle">' + L.topicsTitle + "</h2>" +
        '<button class="iconbtn" data-close aria-label="' + L.close + '">' + ICON_CLOSE + "</button></div>" +
        '<div class="tagdlg__list"><button class="tag tag--plain is-on" data-tag="all">' + L.all + '<span class="tag__n">' + items.length + "</span></button>" +
        Object.keys(used).map(function (t) { return TAGS[t]; })
          .sort(function (a, b) { return (b.hue >= 0) - (a.hue >= 0) || used[b.id] - used[a.id]; })
          .map(function (t) { return tagBtn(t, false, '<span class="tag__n">' + used[t.id] + "</span>"); }).join("") + "</div>";
      document.body.appendChild(dlg);
      var close = function () { if (dlg.close) dlg.close(); else dlg.removeAttribute("open"); };
      var setTag = function (id) {
        want.tag = TAGS[id] ? id : "all";
        var t = TAGS[want.tag];
        pick.innerHTML = t
          ? '<button class="chip chip--topics is-set" id="tagOpen" aria-haspopup="dialog"' + (t.hue >= 0 ? ' style="--h:' + t.hue + '"' : "") + ">" + esc(t.name) + "</button>" +
            '<button class="chip chip--clear" data-tag-clear aria-label="' + L.all + '">' + ICON_CLOSE + "</button>"
          : '<button class="chip chip--topics" id="tagOpen" aria-haspopup="dialog">' + ICON_TOPICS + L.topics + "</button>";
        $$("[data-tag]", dlg).forEach(function (b) { b.classList.toggle("is-on", b.dataset.tag === want.tag); });
        apply();
      };
      setTag("all");
      var toTop = function () { var top = bar.getBoundingClientRect().top; if (top < 0 || top > innerHeight) bar.scrollIntoView(); };
      bar.addEventListener("click", function (e) {
        if (e.target.closest("#tagOpen")) {
          if (dlg.showModal) dlg.showModal(); else dlg.setAttribute("open", "");
          var on = dlg.querySelector(".tag.is-on"); if (on) on.focus();
          return;
        }
        if (e.target.closest("[data-tag-clear]")) { setTag("all"); return; }
        var y = e.target.closest(".chip[data-year]"); if (!y) return;
        want.year = y.dataset.year;
        $$(".chip[data-year]", bar).forEach(function (c) { c.setAttribute("aria-pressed", c === y); });
        apply();
      });
      dlg.addEventListener("click", function (e) {
        if (e.target === dlg || e.target.closest("[data-close]")) { close(); return; }
        var b = e.target.closest("[data-tag]"); if (!b) return;
        setTag(b.dataset.tag); close(); toTop();
      });
      // a topic under an article: the same filter (again: all topics)
      document.addEventListener("click", function (e) {
        var b = e.target.closest(".ep__tags [data-tag]"); if (!b) return;
        setTag(want.tag === b.dataset.tag ? "all" : b.dataset.tag); toTop();
      });
    }
  }

  /* ---------- ερωτήσεις: άνοιγμα από σύνδεσμο #q-... ---------- */
  function openFromHash() {
    var el = location.hash && document.getElementById(location.hash.slice(1));
    if (el && el.tagName === "DETAILS") { el.open = true; el.scrollIntoView(); }
  }
  window.addEventListener("hashchange", openFromHash);
  openFromHash();

  /* ---------- "ask your own question" form (Ερωτήσεις) ----------
   * The question is posted from the page itself (no e-mail app opens) to the form service in
   * data-endpoint; data-key is that service's public access key (e.g. Web3Forms), if it needs one.
   * The service forwards each question by e-mail to the team's inbox. Until data-endpoint is
   * filled in, the form shows a calm "coming soon" note and keeps what the visitor wrote. */
  var form = $("#askForm");
  if (form) {
    var EN = document.documentElement.lang === "en";
    var MSG = EN ? {
      subject: "Question from the website",
      sending: "Sending…", failed: "Sending did not work. Please try again in a moment.",
      soon: "Sending questions from the website will be switched on very soon. Thank you for your patience."
    } : {
      subject: "Ερώτηση από την ιστοσελίδα",
      sending: "Αποστολή…", failed: "Η αποστολή δεν έγινε. Δοκιμάστε ξανά σε λίγο.",
      soon: "Η αποστολή ερωτήσεων από την ιστοσελίδα ενεργοποιείται πολύ σύντομα. Ευχαριστούμε για την υπομονή σας."
    };
    var q = $("#askQuestion"), mail = $("#askEmail"), nameIn = $("#askName"), status = $("#askStatus"),
        btn = form.querySelector("button[type=submit]"), count = $("#askCount"), done = $("#askDone"), again = $("#askAgain");
    var max = +q.getAttribute("maxlength") || 2000;
    var setError = function (input, errorEl, bad) {
      input.setAttribute("aria-invalid", bad ? "true" : "false");
      errorEl.hidden = !bad;
      if (bad) input.setAttribute("aria-describedby", errorEl.id); else input.removeAttribute("aria-describedby");
      return bad;
    };
    var say = function (text, kind) { status.textContent = text; status.className = "ask__status" + (kind ? " is-" + kind : ""); };
    var showCount = function () {
      if (!count) return;
      var n = q.value.length;
      count.textContent = n + " / " + max;
      count.classList.toggle("is-near", n > max * 0.9);
    };
    q.addEventListener("input", showCount); showCount();
    [q, mail].forEach(function (el) {
      el.addEventListener("input", function () { if (el.getAttribute("aria-invalid") === "true") el.setAttribute("aria-invalid", "false"); });
    });
    var finish = function () {
      form.reset(); showCount(); say("");
      form.hidden = true; done.hidden = false; done.focus();
    };
    if (again) again.addEventListener("click", function () { done.hidden = true; form.hidden = false; q.focus(); });
    form.addEventListener("submit", function (e) {
      e.preventDefault();
      var question = q.value.trim(), email = mail.value.trim(), name = nameIn ? nameIn.value.trim() : "";
      var badQ = setError(q, $("#askQuestionError"), question.length < 10);
      var badM = setError(mail, $("#askEmailError"), !/^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/.test(email));
      if (badQ || badM) { (badQ ? q : mail).focus(); say(""); return; }
      var trap = form.querySelector("[name=botcheck]");
      if (trap && trap.checked) { finish(); return; }                 // spam bot: pretend it worked, send nothing
      var endpoint = form.getAttribute("data-endpoint"), key = form.getAttribute("data-key");
      if (!endpoint) { say(MSG.soon, "info"); return; }               // not connected yet: keep the text, explain
      var body = { question: question, name: name, email: email, replyto: email, subject: MSG.subject,
                   from_name: name || "christianity-science.gr", page: location.href };
      if (key) body.access_key = key;
      btn.disabled = true; say(MSG.sending);
      fetch(endpoint, { method: "POST", headers: { "Content-Type": "application/json", "Accept": "application/json" }, body: JSON.stringify(body) })
        .then(function (r) {
          return r.json().catch(function () { return {}; }).then(function (d) {
            if (!r.ok || d.success === false) throw new Error(d.message || r.status);
          });
        })
        .then(finish)
        .catch(function () { say(MSG.failed, "error"); })
        .then(function () { btn.disabled = false; });
    });
  }

  /* ---------- shown in the home page's frame while a broadcast plays (js/app.js) ----------
   * The home page answers this page's "hello" if it holds the frame. Then links back to the home page
   * return to it (the broadcast keeps playing there), and links to other websites open in a new tab,
   * so they do not replace the frame. Messages also work for the site opened from a folder (file://). */
  if (window.parent !== window) {
    var HOME_IN = null;
    var homePath = function (p) { return p.replace(/index\.html$/, ""); };
    window.addEventListener("message", function (e) {
      var m = e.data;
      if (e.source !== window.parent || !m || m.cs !== "shell" || (e.origin !== location.origin && location.protocol !== "file:")) return;
      HOME_IN = m.home;
      document.documentElement.classList.add("in-shell");
    });
    document.addEventListener("click", function (e) {
      if (!HOME_IN) return;
      var a = e.target.closest("a[href]");
      if (!a || e.defaultPrevented || e.button || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) return;
      var u = new URL(a.href, location.href);
      if (u.protocol !== location.protocol || u.host !== location.host) { if (!a.target) { a.target = "_blank"; a.rel = "noopener"; } return; }
      if (homePath(u.pathname) === homePath(HOME_IN)) { e.preventDefault(); window.parent.postMessage({ cs: "home", hash: u.hash }, "*"); }
    });
    window.parent.postMessage({ cs: "hello", href: location.href, title: document.title }, "*");
  }
})();
