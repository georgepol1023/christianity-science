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
   * title on the English page). Without js/search.js it falls back to plain matching. */
  function norm(s) { return s.normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase().replace(/ς/g, "σ"); }
  var input = $("#filter");
  if (input) {
    var SS = window.SiteSearch;
    var items = $$("[data-filter]").map(function (el, i) {
      var text = el.textContent + " " + (el.getAttribute("data-keys") || "");
      var it = SS ? SS.prepare(text) : { norm: norm(text) };
      it.el = el; it.id = -i; it.parent = el.parentNode;     // id: ties keep the page's own order
      return it;
    });
    var groups = items.map(function (it) { return it.parent; }).filter(function (p, i, a) { return a.indexOf(p) === i; });
    var empty = $("#filterEmpty");
    var near = document.createElement("p");
    near.className = "empty"; near.hidden = true;
    near.textContent = document.documentElement.lang === "en" ? "No exact match – these are the closest:" : "Δεν βρέθηκε ακριβές αποτέλεσμα – τα πλησιέστερα:";
    var anchor = empty || input.closest("label") || input;
    anchor.parentNode.insertBefore(near, anchor);

    input.addEventListener("input", function () {
      var q = input.value.trim(), res;
      if (!q) {
        res = { list: items.map(function (it) { return { ep: it }; }), approx: false };
      } else if (SS) {
        res = SS.search(items, q);
      } else {
        var tokens = norm(q).split(/\s+/).filter(Boolean);
        res = { list: items.filter(function (it) { return tokens.every(function (t) { return it.norm.indexOf(t) !== -1; }); })
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
    });
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
})();
