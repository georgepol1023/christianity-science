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

  /* ---------- "ask your own question" form (Ερωτήσεις) ----------
   * With data-endpoint set (e.g. a Formspree address) the question is posted there;
   * without it, the visitor's e-mail app opens with the question ready to send to data-to. */
  var form = $("#askForm");
  if (form) {
    var EN = document.documentElement.lang === "en";
    var MSG = EN ? {
      subject: "Question from the website", from: "Reply to: ",
      mailOpened: "Your e-mail app has opened with your question ready. Press “Send” there to send it.",
      sending: "Sending…", sent: "Thank you! Your question has been sent. We will reply by e-mail.",
      failed: "Sending did not work. Please e-mail us at "
    } : {
      subject: "Ερώτηση από την ιστοσελίδα", from: "Απάντηση στο: ",
      mailOpened: "Άνοιξε το πρόγραμμα e-mail σας με την ερώτηση έτοιμη. Πατήστε «Αποστολή» εκεί για να σταλεί.",
      sending: "Αποστολή…", sent: "Ευχαριστούμε! Η ερώτησή σας στάλθηκε. Θα σας απαντήσουμε με e-mail.",
      failed: "Η αποστολή δεν έγινε. Στείλτε μας e-mail στο "
    };
    var q = $("#askQuestion"), mail = $("#askEmail"), status = $("#askStatus"), btn = form.querySelector("button[type=submit]");
    var setError = function (input, errorEl, bad) {
      input.setAttribute("aria-invalid", bad ? "true" : "false");
      errorEl.hidden = !bad;
      if (bad) input.setAttribute("aria-describedby", errorEl.id); else input.removeAttribute("aria-describedby");
      return bad;
    };
    var say = function (text, kind) { status.textContent = text; status.className = "ask__status" + (kind ? " is-" + kind : ""); };
    [q, mail].forEach(function (el) {
      el.addEventListener("input", function () { if (el.getAttribute("aria-invalid") === "true") el.setAttribute("aria-invalid", "false"); });
    });
    form.addEventListener("submit", function (e) {
      e.preventDefault();
      var question = q.value.trim(), email = mail.value.trim();
      var badQ = setError(q, $("#askQuestionError"), question.length < 10);
      var badM = setError(mail, $("#askEmailError"), !/^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/.test(email));
      if (badQ || badM) { (badQ ? q : mail).focus(); say(""); return; }
      var to = form.getAttribute("data-to"), endpoint = form.getAttribute("data-endpoint");
      if (!endpoint) {
        var mailto = "mailto:" + to + "?subject=" + encodeURIComponent(MSG.subject) +
          "&body=" + encodeURIComponent(question + "\n\n" + MSG.from + email);
        form.setAttribute("data-mailto", mailto);          // the link that was opened (also used by the tests)
        location.href = mailto;
        say(MSG.mailOpened, "ok");
        return;
      }
      btn.disabled = true; say(MSG.sending);
      fetch(endpoint, { method: "POST", headers: { "Content-Type": "application/json", "Accept": "application/json" },
        body: JSON.stringify({ question: question, email: email, _subject: MSG.subject, page: location.href }) })
        .then(function (r) { if (!r.ok) throw new Error(r.status); form.reset(); say(MSG.sent, "ok"); })
        .catch(function () { say(MSG.failed + to, "error"); })
        .then(function () { btn.disabled = false; });
    });
  }
})();
