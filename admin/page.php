<?php
/* The upload page's HTML, styles and script (included by index.php; not reachable on its own). */
if (!isset($nonce)) { http_response_code(404); exit; }
?><!doctype html>
<html lang="el">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex, nofollow">
<meta name="csrf" content="<?= $csrf ?>">
<title>Διαχείριση · Χριστιανισμός &amp; Επιστήμη</title>
<style nonce="<?= $nonce ?>">
:root { --lapis:#1C2B6E; --lapis-soft:#2C3E8C; --deep:#121C4D; --gold:#C8A54A; --paper:#F6F7FA; --surface:#fff; --ink:#1A1D33;
  --slate:#5B6180; --line:#DDE0EA; --tint:#ECEFF8; --ok:#2E7D4F; --okbg:#E4F3EA; --warn:#8A5A00; --warnbg:#FBF0D6; --bad:#A3262A; --badbg:#FBE4E4;
  color-scheme: light; }
@media (prefers-color-scheme: dark) { :root { --paper:#0E1330; --surface:#161D40; --ink:#E8EAF5; --slate:#9CA3C4; --line:#283160; --tint:#1C2450;
  --ok:#7FD3A0; --okbg:#173A2A; --warn:#E8C25A; --warnbg:#3A2F12; --bad:#F2A0A0; --badbg:#3E1A1F; color-scheme: dark; } }
* { box-sizing: border-box; }
body { margin:0; background:var(--paper); color:var(--ink); font:15px/1.55 "Segoe UI", system-ui, -apple-system, Arial, sans-serif; }
button, input, select, textarea { font: inherit; color: inherit; }
:focus-visible { outline: 2px solid var(--gold); outline-offset: 2px; }
header { background:var(--deep); color:#fff; display:flex; align-items:center; gap:12px; padding:12px max(16px, env(safe-area-inset-left)); flex-wrap:wrap; }
header b { font-family: Georgia, serif; font-size:17px; }
header small { color:var(--gold); letter-spacing:.1em; text-transform:uppercase; font-size:11px; }
header .sp { flex:1; }
header button { background:none; border:1px solid rgba(255,255,255,.35); color:#fff; border-radius:6px; padding:4px 12px; cursor:pointer; }
nav { display:flex; gap:4px; overflow-x:auto; background:var(--surface); border-bottom:1px solid var(--line); padding:0 max(16px, env(safe-area-inset-left)); }
nav button { border:0; background:none; padding:12px 14px; cursor:pointer; color:var(--slate); font-weight:600; white-space:nowrap; border-bottom:3px solid transparent; }
nav button[aria-selected="true"] { color:var(--ink); border-bottom-color:var(--gold); }
main { max-width:760px; margin:0 auto; padding:24px max(16px, env(safe-area-inset-left)) 80px; display:flex; flex-direction:column; gap:18px; }
h1 { font:600 24px/1.2 Georgia, serif; margin:0; }
.lede { color:var(--slate); margin:-8px 0 0; }
.card { background:var(--surface); border:1px solid var(--line); border-radius:12px; padding:18px; display:flex; flex-direction:column; gap:14px; }
.row { display:grid; grid-template-columns:1fr 1fr; gap:14px; }
label.f, div.f { display:flex; flex-direction:column; gap:6px; min-width:0; }
.f > span { font-weight:600; font-size:14px; }
.f > em { font-style:normal; font-size:13px; color:var(--slate); }
input[type=text], input[type=password], input[type=date], input[type=time], input[type=url], select {
  background:var(--paper); border:1px solid var(--line); border-radius:6px; padding:9px 11px; width:100%; min-width:0; }
.chips { display:flex; flex-wrap:wrap; gap:6px; }
.chip { border:1px solid var(--line); background:var(--paper); border-radius:99px; padding:4px 12px; font-size:13px; cursor:pointer; }
.chip[aria-pressed="true"] { background:var(--lapis); border-color:var(--lapis); color:#fff; }
.drop { border:2px dashed var(--line); border-radius:12px; padding:18px; text-align:center; color:var(--slate); cursor:pointer; }
.drop.over { border-color:var(--gold); background:var(--tint); }
.files { display:flex; flex-direction:column; gap:6px; }
.file { display:flex; align-items:center; gap:8px; background:var(--paper); border-radius:6px; padding:6px 10px; font-size:14px; }
.file b { font-weight:600; white-space:nowrap; }
.file span { flex:1; min-width:0; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
.file button { border:1px solid var(--line); background:var(--surface); border-radius:4px; cursor:pointer; padding:0 7px; }
.btn { border:1px solid var(--line); background:var(--surface); border-radius:6px; padding:10px 18px; cursor:pointer; font-weight:600; }
.btn.primary { background:var(--lapis); border-color:var(--lapis); color:#fff; }
.btn:disabled { opacity:.5; cursor:default; }
.actions { display:flex; gap:10px; justify-content:flex-end; flex-wrap:wrap; }
.msg { border-radius:8px; padding:10px 14px; font-size:14px; }
.msg.ok { background:var(--okbg); color:var(--ok); } .msg.warn { background:var(--warnbg); color:var(--warn); } .msg.bad { background:var(--badbg); color:var(--bad); }
progress { width:100%; height:12px; }
.list { display:flex; flex-direction:column; gap:8px; }
.item { border:1px solid var(--line); border-radius:8px; padding:10px 12px; background:var(--surface); display:flex; flex-direction:column; gap:4px; }
.item .top { display:flex; gap:8px; align-items:baseline; flex-wrap:wrap; }
.item .when { color:var(--slate); font-size:13px; margin-left:auto; }
.pill { font-size:12px; padding:1px 9px; border-radius:99px; white-space:nowrap; }
.pill.published { background:var(--okbg); color:var(--ok); } .pill.rejected, .pill.error { background:var(--badbg); color:var(--bad); }
.pill.waiting, .pill.publishing, .pill.retrying { background:var(--warnbg); color:var(--warn); }
.thumb { width:200px; max-width:100%; aspect-ratio:16/9; object-fit:cover; border-radius:6px; background:var(--tint); }
.check { display:flex; gap:8px; align-items:flex-start; }
.login { max-width:380px; margin:8vh auto; }
[hidden] { display:none !important; }
@media (max-width:600px) { .row { grid-template-columns:1fr; } }
</style>
</head>
<body>
<header>
  <b>Χριστιανισμός &amp; Επιστήμη</b><small>Διαχείριση</small><span class="sp"></span>
  <?php if ($user): ?><span><?= $name ?></span><button type="button" id="logout">Αποσύνδεση</button><?php endif; ?>
</header>

<?php if (!$user): ?>
<main class="login">
  <form class="card" id="loginForm" autocomplete="on">
    <h1>Σύνδεση</h1>
    <label class="f"><span>Όνομα χρήστη</span><input type="text" id="lName" autocomplete="username" required></label>
    <label class="f"><span>Κωδικός</span><input type="password" id="lPass" autocomplete="current-password" required></label>
    <label class="f"><span>Κωδικός επιβεβαίωσης (από την εφαρμογή του κινητού)</span>
      <input type="text" id="lCode" inputmode="numeric" autocomplete="one-time-code" maxlength="7" placeholder="123456"></label>
    <div class="msg bad" id="lErr" hidden></div>
    <div class="actions"><button class="btn primary" type="submit">Σύνδεση</button></div>
  </form>
</main>
<?php else: ?>
<nav role="tablist">
  <button role="tab" aria-selected="true" data-tab="new">Νέα εκπομπή</button>
  <button role="tab" aria-selected="false" data-tab="fix">Διόρθωση εκπομπής</button>
  <button role="tab" aria-selected="false" data-tab="home">Αρχική σελίδα</button>
  <button role="tab" aria-selected="false" data-tab="mail">Από email <span id="draftCount"></span></button>
  <button role="tab" aria-selected="false" data-tab="status">Κατάσταση <span id="pendingCount"></span></button>
</nav>
<main>
  <!-- NEW BROADCAST -->
  <section data-pane="new">
    <div class="card">
      <h1>Νέα εκπομπή</h1>
      <p class="lede">Συμπληρώστε ημερομηνία και τίτλο, προσθέστε τα mp3 και πατήστε «Αποστολή». Θα λάβετε email όταν δημοσιευτεί.</p>
      <div class="row">
        <label class="f"><span>Ημερομηνία εκπομπής</span><input type="date" id="nDate" required></label>
        <label class="f"><span>Τίτλος</span><input type="text" id="nTitle" maxlength="200" required></label>
      </div>
      <div class="msg warn" id="nExists" hidden></div>
      <label class="check" id="nReplaceBox" hidden><input type="checkbox" id="nReplace">
        <span>Αντικατάσταση: η παλιά ηχογράφηση φυλάσσεται και τη θέση της παίρνει η νέα (ίδια διεύθυνση, ίδιο επεισόδιο στο Spotify).</span></label>
      <label class="f"><span>Αγγλικός τίτλος (προαιρετικά)</span><input type="text" id="nTitleEn" maxlength="200">
        <em>Αν μείνει κενό, προτείνεται αυτόματα.</em></label>
      <div class="f"><span>Θέματα (έως 3, το πιο σχετικό πρώτο· προαιρετικά)</span><div class="chips" id="nTags"></div>
        <em>Αν δεν επιλέξετε, προτείνονται αυτόματα.</em></div>
      <div class="f"><span>Αρχεία mp3 (ένα για κάθε ημίωρο, με τη σειρά)</span>
        <div class="drop" id="drop" tabindex="0">Σύρετε εδώ τα mp3 ή πατήστε για να τα επιλέξετε</div>
        <input type="file" id="nFiles" accept=".mp3,audio/mpeg" multiple hidden>
        <div class="files" id="fileList"></div></div>
      <div id="progressBox" hidden><progress id="progress" max="1" value="0"></progress> <span id="progressText"></span></div>
      <div class="msg" id="nMsg" hidden></div>
      <div class="actions"><button class="btn primary" type="button" id="send">Αποστολή</button></div>
    </div>
  </section>

  <!-- CORRECTION -->
  <section data-pane="fix" hidden>
    <div class="card">
      <h1>Διόρθωση εκπομπής</h1>
      <p class="lede">Αλλάξτε τίτλο, αγγλικό τίτλο ή θέματα μιας εκπομπής που είναι ήδη στην ιστοσελίδα.</p>
      <label class="f"><span>Εκπομπή</span><select id="fDate"></select></label>
      <label class="f"><span>Τίτλος</span><input type="text" id="fTitle" maxlength="200"></label>
      <label class="f"><span>Αγγλικός τίτλος</span><input type="text" id="fTitleEn" maxlength="200"></label>
      <div class="f"><span>Θέματα (1 έως 3)</span><div class="chips" id="fTags"></div></div>
      <div class="msg" id="fMsg" hidden></div>
      <div class="actions"><button class="btn primary" type="button" id="fSend">Αποθήκευση</button></div>
    </div>
  </section>

  <!-- HOME PAGE -->
  <section data-pane="home" hidden>
    <div class="card">
      <h1>Αρχική σελίδα</h1>
      <div class="f"><span>Βίντεο</span><img class="thumb" id="hThumb" alt="Το βίντεο της αρχικής σελίδας"></div>
      <label class="f"><span>Νέο βίντεο: σύνδεσμος YouTube</span><input type="url" id="hVideo" placeholder="https://youtu.be/…">
        <em>Αφήστε κενό για να μείνει το ίδιο.</em></label>
      <div class="row">
        <label class="f"><span>Επόμενη ζωντανή εκπομπή</span><input type="date" id="hDate"></label>
        <label class="f"><span>Ώρα (Ελλάδας)</span><input type="time" id="hTime" value="22:00"></label>
      </div>
      <p class="lede">Αν δεν αλλάξει, η ιστοσελίδα προσθέτει μόνη της 14 ημέρες μετά από κάθε εκπομπή.</p>
      <div class="msg" id="hMsg" hidden></div>
      <div class="actions"><button class="btn primary" type="button" id="hSend">Αποθήκευση</button></div>
    </div>
  </section>

  <!-- FROM EMAIL -->
  <section data-pane="mail" hidden>
    <h1>Από email</h1>
    <p class="lede">Ηχογραφήσεις που ήρθαν με email στο science@christianity.gr και χρειάζονται τίτλο ή ημερομηνία.
      Όσες είχαν και τα δύο δημοσιεύτηκαν ήδη αυτόματα (δείτε «Κατάσταση»).</p>
    <div class="list" id="drafts"></div>
  </section>

  <!-- STATUS -->
  <section data-pane="status" hidden>
    <h1>Κατάσταση</h1>
    <p class="lede">Ό,τι περιμένει δημοσίευση και τα τελευταία αποτελέσματα. Η σελίδα ανανεώνεται μόνη της.</p>
    <div class="list" id="pending"></div>
    <div class="list" id="results"></div>
  </section>
</main>
<?php endif; ?>

<script nonce="<?= $nonce ?>">
"use strict";
(function () {
  var CSRF = document.querySelector('meta[name="csrf"]').content;
  var $ = function (id) { return document.getElementById(id); };
  var MONTHS = ["Ιανουαρίου","Φεβρουαρίου","Μαρτίου","Απριλίου","Μαΐου","Ιουνίου","Ιουλίου","Αυγούστου","Σεπτεμβρίου","Οκτωβρίου","Νοεμβρίου","Δεκεμβρίου"];
  function gdate(d) { var p = d.split("-"); return +p[2] + " " + MONTHS[+p[1] - 1] + " " + p[0]; }

  function call(action, body, opts) {
    opts = opts || {};
    var url = "?a=" + action + (opts.query || "");
    var init = { method: body === undefined ? "GET" : "POST", headers: { "X-CSRF": CSRF }, credentials: "same-origin" };
    if (body !== undefined) {
      if (opts.raw) { init.body = body; init.headers["Content-Type"] = "application/octet-stream"; }
      else { init.body = JSON.stringify(body); init.headers["Content-Type"] = "application/json"; }
    }
    return fetch(url, init).then(function (r) {
      return r.json().then(function (j) { j.status = r.status; return j; },
        function () { return { ok: false, status: r.status, error: "Ο server δεν απάντησε σωστά (" + r.status + ")." }; });
    }, function () { return { ok: false, error: "Δεν υπάρχει σύνδεση με τον server.", network: true }; });
  }
  function show(el, text, kind) { el.textContent = text; el.className = "msg " + kind; el.hidden = !text; }

  /* -------- sign-in */
  var loginForm = $("loginForm");
  if (loginForm) {
    loginForm.addEventListener("submit", function (ev) {
      ev.preventDefault();
      call("login", { name: $("lName").value.trim(), password: $("lPass").value, code: $("lCode").value }).then(function (r) {
        if (r.ok) location.reload(); else show($("lErr"), r.error, "bad");
      });
    });
    return;
  }
  $("logout").addEventListener("click", function () { call("logout", {}).then(function () { location.reload(); }); });

  /* -------- tabs */
  var tabs = document.querySelectorAll("nav button");
  tabs.forEach(function (t) {
    t.addEventListener("click", function () {
      tabs.forEach(function (x) { x.setAttribute("aria-selected", x === t); });
      document.querySelectorAll("[data-pane]").forEach(function (p) { p.hidden = p.dataset.pane !== t.dataset.tab; });
      if (t.dataset.tab === "status" || t.dataset.tab === "mail") refresh();
    });
  });

  /* -------- data from the site */
  var S = { broadcasts: [], topics: [], byDate: {} };
  function chips(box, selected) {
    box.textContent = "";
    S.topics.forEach(function (t) {
      var b = document.createElement("button");
      b.type = "button"; b.className = "chip"; b.dataset.id = t[0]; b.textContent = t[1];
      b.setAttribute("aria-pressed", selected.indexOf(t[0]) >= 0);
      b.addEventListener("click", function () {
        var on = b.getAttribute("aria-pressed") !== "true";
        if (on && picked(box).length >= 3) return;
        b.setAttribute("aria-pressed", on);
        if (on) box.dataset.order = (box.dataset.order ? box.dataset.order + " " : "") + t[0];
        else box.dataset.order = (box.dataset.order || "").split(" ").filter(function (x) { return x && x !== t[0]; }).join(" ");
      });
      box.appendChild(b);
    });
    box.dataset.order = selected.join(" ");
  }
  function picked(box) { return (box.dataset.order || "").split(" ").filter(Boolean); }

  function refresh() {
    return call("state").then(function (r) {
      if (!r.ok) { if (r.error) show($("nMsg"), r.error, "bad"); return; }
      var first = !S.topics.length;
      S = r; S.byDate = {};
      r.broadcasts.forEach(function (b) { S.byDate[b.date] = b; });
      if (first) { chips($("nTags"), []); fillFix(); fillHome(); }
      renderDrafts();
      renderStatus();
      checkDate();
    });
  }

  /* -------- new broadcast */
  var files = [];
  function nat(a, b) { return a.name.localeCompare(b.name, undefined, { numeric: true, sensitivity: "base" }); }
  function mb(n) { return (n / 1048576).toFixed(1).replace(".", ",") + " MB"; }
  function renderFiles() {
    var box = $("fileList"); box.textContent = "";
    files.forEach(function (f, i) {
      var row = document.createElement("div"); row.className = "file";
      var b = document.createElement("b"); b.textContent = (i + 1) + "ο ημίωρο";
      var s = document.createElement("span"); s.textContent = f.name + " · " + mb(f.size); s.title = f.name;
      row.appendChild(b); row.appendChild(s);
      [["↑", -1, "Πιο πάνω"], ["↓", 1, "Πιο κάτω"], ["✕", 0, "Αφαίρεση"]].forEach(function (a) {
        var btn = document.createElement("button"); btn.type = "button"; btn.textContent = a[0]; btn.title = a[2];
        btn.addEventListener("click", function () {
          if (a[1] === 0) files.splice(i, 1);
          else { var j = i + a[1]; if (j < 0 || j >= files.length) return; var t = files[i]; files[i] = files[j]; files[j] = t; }
          renderFiles();
        });
        row.appendChild(btn);
      });
      box.appendChild(row);
    });
  }
  function addFiles(list) {
    Array.prototype.forEach.call(list, function (f) {
      if (!/\.mp3$/i.test(f.name)) { show($("nMsg"), "Το «" + f.name + "» δεν είναι mp3 και δεν προστέθηκε.", "warn"); return; }
      if (!files.some(function (x) { return x.name === f.name && x.size === f.size; })) files.push(f);
    });
    files.sort(nat);
    renderFiles();
  }
  var drop = $("drop"), picker = $("nFiles");
  drop.addEventListener("click", function () { picker.click(); });
  drop.addEventListener("keydown", function (e) { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); picker.click(); } });
  picker.addEventListener("change", function () { addFiles(picker.files); picker.value = ""; });
  ["dragenter", "dragover"].forEach(function (ev) { drop.addEventListener(ev, function (e) { e.preventDefault(); drop.classList.add("over"); }); });
  ["dragleave", "drop"].forEach(function (ev) { drop.addEventListener(ev, function (e) { e.preventDefault(); drop.classList.remove("over"); }); });
  drop.addEventListener("drop", function (e) { addFiles(e.dataTransfer.files); });

  function checkDate() {
    var d = $("nDate").value, b = S.byDate[d];
    var waiting = (S.pending || []).some(function (p) { return p.type === "broadcast" && p.date === d; });
    if (waiting) { show($("nExists"), "Μια εκπομπή της " + gdate(d) + " έχει ήδη σταλεί και περιμένει δημοσίευση.", "warn"); }
    else if (b) { show($("nExists"), "Η εκπομπή της " + gdate(d) + " υπάρχει ήδη: «" + b.title + "».", "warn"); }
    else { show($("nExists"), "", "warn"); }
    $("nReplaceBox").hidden = !b || waiting;
    if (!b) $("nReplace").checked = false;
  }
  $("nDate").addEventListener("change", checkDate);

  var sending = false;
  window.addEventListener("beforeunload", function (e) { if (sending) { e.preventDefault(); e.returnValue = ""; } });

  var chunk = 0;
  function sendPiece(id, n, file, offset, size, tries) {
    var blob = file.slice(offset, offset + chunk);
    return call("piece", blob, { raw: true, query: "&id=" + id + "&n=" + n + "&offset=" + offset }).then(function (r) {
      if (r.ok) return r.size;
      if (r.status === 413 && chunk > 256 * 1024) {        // the server takes smaller pieces: halve and go on
        chunk = Math.max(256 * 1024, Math.floor(chunk / 2));
        return sendPiece(id, n, file, offset, size, tries);
      }
      if (r.network && tries < 6) {
        // some servers just hang up on a request that is too big: after a second failure, smaller pieces
        if (tries >= 1 && chunk > 256 * 1024) chunk = Math.max(256 * 1024, Math.floor(chunk / 2));
        return new Promise(function (res) { setTimeout(res, 2000 * (tries + 1)); })
          .then(function () { return call("piece", new Blob([]), { raw: true, query: "&id=" + id + "&n=" + n + "&offset=-1" }); })
          .then(function (q) { return q.ok ? sendPiece(id, n, file, q.size, size, tries + 1) : sendPiece(id, n, file, offset, size, tries + 1); });
      }
      throw new Error(r.error);
    });
  }

  $("send").addEventListener("click", function () {
    var d = $("nDate").value, title = $("nTitle").value.trim();
    if (!d) return show($("nMsg"), "Επιλέξτε την ημερομηνία της εκπομπής.", "bad");
    if (!title) return show($("nMsg"), "Γράψτε τον τίτλο της εκπομπής.", "bad");
    if (!files.length) return show($("nMsg"), "Προσθέστε τα αρχεία mp3.", "bad");
    if (S.byDate[d] && !$("nReplace").checked) return show($("nMsg"), "Η εκπομπή αυτής της ημερομηνίας υπάρχει ήδη. Επιλέξτε «Αντικατάσταση» αν θέλετε να την αλλάξετε.", "bad");
    var total = files.reduce(function (a, f) { return a + f.size; }, 0), done = 0, id = null;
    sending = true; $("send").disabled = true; show($("nMsg"), "", "ok");
    $("progressBox").hidden = false; $("progress").value = 0; $("progressText").textContent = "Ξεκινά…";
    call("start", { date: d, title: title, title_en: $("nTitleEn").value.trim(), tags: picked($("nTags")), replace: $("nReplace").checked,
                    files: files.map(function (f) { return { name: f.name, size: f.size }; }) }).then(function (r) {
      if (!r.ok) throw new Error(r.error);
      id = r.id; chunk = r.chunk;
      var chain = Promise.resolve();
      files.forEach(function (f, i) {
        chain = chain.then(function () {
          var offset = 0;
          function next() {
            if (offset >= f.size) return;
            return sendPiece(id, i + 1, f, offset, chunk, 0).then(function (size) {
              done += size - offset; offset = size;
              $("progress").value = done / total;
              $("progressText").textContent = Math.round(100 * done / total) + "% · " + (i + 1) + "ο από " + files.length + " αρχεία";
              return next();
            });
          }
          return next();
        });
      });
      return chain;
    }).then(function () { return call("finish", { id: id }); }).then(function (r) {
      if (!r.ok) throw new Error(r.error);
      sending = false;
      show($("nMsg"), "Παραλήφθηκε. Η εκπομπή θα δημοσιευτεί σε λίγα λεπτά· θα λάβετε email. Δείτε την καρτέλα «Κατάσταση».", "ok");
      $("progressText").textContent = "Ολοκληρώθηκε";
      files = []; renderFiles(); $("nTitle").value = ""; $("nTitleEn").value = ""; $("nDate").value = ""; chips($("nTags"), []);
      refresh();
    }).catch(function (e) {
      sending = false;
      show($("nMsg"), (e && e.message) || "Κάτι πήγε στραβά. Δοκιμάστε ξανά.", "bad");
      if (id) call("cancel", { id: id });
      $("progressBox").hidden = true;
    }).then(function () { $("send").disabled = false; });
  });

  /* -------- correction */
  function fillFix() {
    var sel = $("fDate"); sel.textContent = "";
    S.broadcasts.forEach(function (b) {
      var o = document.createElement("option"); o.value = b.date; o.textContent = gdate(b.date) + " — " + b.title; sel.appendChild(o);
    });
    loadFix();
  }
  function loadFix() {
    var b = S.byDate[$("fDate").value]; if (!b) return;
    $("fTitle").value = b.title; $("fTitleEn").value = b.en; chips($("fTags"), b.tags);
  }
  $("fDate").addEventListener("change", loadFix);
  $("fSend").addEventListener("click", function () {
    var b = S.byDate[$("fDate").value]; if (!b) return;
    var body = { date: b.date }, t = $("fTitle").value.trim(), en = $("fTitleEn").value.trim(), tags = picked($("fTags"));
    if (t !== b.title) body.title = t;
    if (en !== b.en) body.title_en = en;
    if (tags.join(" ") !== b.tags.join(" ")) body.tags = tags;
    call("correct", body).then(function (r) {
      show($("fMsg"), r.ok ? "Παραλήφθηκε· η διόρθωση θα φανεί σε λίγα λεπτά." : r.error, r.ok ? "ok" : "bad");
      refresh();
    });
  });

  /* -------- home page */
  function fillHome() {
    if (S.youtube) $("hThumb").src = "https://i.ytimg.com/vi/" + encodeURIComponent(S.youtube) + "/hqdefault.jpg";
    var m = /^(\d{4}-\d\d-\d\d)T(\d\d:\d\d)/.exec(S.next || "");
    if (m) { $("hDate").value = m[1]; $("hTime").value = m[2]; $("hDate").dataset.was = m[1] + "T" + m[2]; }
  }
  $("hVideo").addEventListener("input", function () {
    var m = /(?:youtu\.be\/|[?&]v=|\/embed\/|\/shorts\/|\/live\/)([\w-]{11})/.exec(this.value);
    if (m) $("hThumb").src = "https://i.ytimg.com/vi/" + m[1] + "/hqdefault.jpg";
  });
  $("hSend").addEventListener("click", function () {
    var body = {}, next = $("hDate").value ? $("hDate").value + "T" + ($("hTime").value || "22:00") : "";
    if ($("hVideo").value.trim()) body.youtube = $("hVideo").value.trim();
    if (next && next !== $("hDate").dataset.was) body.next = next;
    call("settings", body).then(function (r) {
      show($("hMsg"), r.ok ? "Παραλήφθηκε· η αλλαγή θα φανεί σε λίγα λεπτά." : r.error, r.ok ? "ok" : "bad");
      if (r.ok) $("hVideo").value = "";
      refresh();
    });
  });

  /* -------- status */
  var LABEL = { waiting: "Περιμένει", publishing: "Δημοσιεύεται", published: "Δημοσιεύτηκε", rejected: "Δεν δημοσιεύτηκε",
                error: "Απέτυχε", retrying: "Θα ξαναδοκιμαστεί" };
  var KIND = { broadcast: "Εκπομπή", correction: "Διόρθωση", settings: "Αρχική σελίδα" };
  function item(state, head, text, when, link) {
    var d = document.createElement("div"); d.className = "item";
    var top = document.createElement("div"); top.className = "top";
    var p = document.createElement("span"); p.className = "pill " + state; p.textContent = LABEL[state] || state;
    var h = document.createElement("b"); h.textContent = head;
    top.appendChild(p); top.appendChild(h);
    if (when) { var w = document.createElement("span"); w.className = "when"; w.textContent = when; top.appendChild(w); }
    d.appendChild(top);
    if (text) { var t = document.createElement("div"); t.textContent = text; d.appendChild(t); }
    if (link) { var a = document.createElement("a"); a.href = link; a.target = "_blank"; a.rel = "noopener"; a.textContent = "Άνοιγμα στην ιστοσελίδα"; d.appendChild(a); }
    return d;
  }
  function head(r) { return (KIND[r.type] || "Αίτημα") + (r.date ? " · " + gdate(r.date) : "") + (r.title ? " · " + r.title : ""); }
  /* -------- recordings from email, waiting to be completed */
  var draftShown = "";
  function renderDrafts() {
    var list = S.drafts || [];
    $("draftCount").textContent = list.length ? "(" + list.length + ")" : "";
    var key = JSON.stringify(list.map(function (d) { return d.id; }));
    if (key === draftShown) return;             // do not wipe what the admin is typing
    draftShown = key;
    var box = $("drafts"); box.textContent = "";
    if (!list.length) { box.appendChild(item("", "Δεν περιμένει τίποτα.", "", "")); return; }
    list.forEach(function (d) {
      var card = document.createElement("div"); card.className = "card"; card.dataset.draft = d.id;
      var head = document.createElement("div"); head.className = "lede";
      head.textContent = "Από " + (d.from || "?") + " · «" + (d.subject || "") + "»";
      card.appendChild(head);
      var row = document.createElement("div"); row.className = "row";
      var f1 = document.createElement("label"); f1.className = "f";
      f1.innerHTML = "<span>Ημερομηνία εκπομπής</span>";
      var date = document.createElement("input"); date.type = "date"; date.value = d.date || ""; f1.appendChild(date);
      var f2 = document.createElement("label"); f2.className = "f";
      f2.innerHTML = "<span>Τίτλος</span>";
      var title = document.createElement("input"); title.type = "text"; title.maxLength = 200; title.value = d.title || ""; f2.appendChild(title);
      row.appendChild(f1); row.appendChild(f2); card.appendChild(row);
      var tagsBox = document.createElement("div"); tagsBox.className = "chips"; chips(tagsBox, []);
      var tf = document.createElement("div"); tf.className = "f"; tf.innerHTML = "<span>Θέματα (προαιρετικά)</span>"; tf.appendChild(tagsBox);
      card.appendChild(tf);
      var files = document.createElement("div"); files.className = "files";
      d.files.forEach(function (f, i) {
        var r = document.createElement("div"); r.className = "file";
        var b = document.createElement("b"); b.textContent = (i + 1) + "ο ημίωρο";
        var s = document.createElement("span"); s.textContent = f.original + " · " + mb(f.bytes);
        var play = document.createElement("audio"); play.controls = true; play.preload = "none";
        play.src = "?a=draft_audio&id=" + encodeURIComponent(d.id) + "&n=" + (i + 1);
        r.appendChild(b); r.appendChild(s); files.appendChild(r); files.appendChild(play);
      });
      card.appendChild(files);
      var msg = document.createElement("div"); msg.className = "msg"; msg.hidden = true; card.appendChild(msg);
      var actions = document.createElement("div"); actions.className = "actions";
      var drop = document.createElement("button"); drop.type = "button"; drop.className = "btn"; drop.textContent = "Απόρριψη";
      var go = document.createElement("button"); go.type = "button"; go.className = "btn primary"; go.textContent = "Δημοσίευση";
      actions.appendChild(drop); actions.appendChild(go); card.appendChild(actions);
      drop.addEventListener("click", function () {
        if (drop.dataset.sure !== "1") { drop.dataset.sure = "1"; drop.textContent = "Σίγουρα; Πατήστε ξανά"; return; }
        call("draft_discard", { id: d.id }).then(function (r) {
          if (r.ok) { draftShown = ""; refresh(); } else show(msg, r.error, "bad");
        });
      });
      go.addEventListener("click", function () {
        go.disabled = true;
        call("draft_publish", { id: d.id, date: date.value, title: title.value.trim(), title_en: "", tags: picked(tagsBox) }).then(function (r) {
          go.disabled = false;
          if (r.ok) { show(msg, "Παραλήφθηκε· δημοσιεύεται σε λίγα λεπτά.", "ok"); draftShown = ""; setTimeout(refresh, 1500); }
          else show(msg, r.error, "bad");
        });
      });
      box.appendChild(card);
    });
  }

  function renderStatus() {
    var p = $("pending"), q = $("results"); p.textContent = ""; q.textContent = "";
    (S.pending || []).forEach(function (r) { p.appendChild(item(r.state, head(r), "", "")); });
    (S.results || []).forEach(function (r) {
      q.appendChild(item(r.status, head(r), r.message, new Date(r.time * 1000).toLocaleString("el-GR"), r.status === "published" ? r.link : ""));
    });
    if (!(S.pending || []).length && !(S.results || []).length) q.appendChild(item("", "Δεν υπάρχει τίποτα ακόμα.", "", ""));
    $("pendingCount").textContent = (S.pending || []).length ? "(" + S.pending.length + ")" : "";
  }
  setInterval(function () { if (!sending && document.visibilityState === "visible" && (S.pending || []).length) refresh(); }, 30000);
  refresh();
})();
</script>
</body>
</html>
