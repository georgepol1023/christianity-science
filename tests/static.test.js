/*
 * Static tests (no browser): data, helper functions, HTML, links, CSS, tools.
 * Run from the project folder:   node --test tests/
 */
"use strict";
const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("fs");
const path = require("path");
const vm = require("vm");
const crypto = require("crypto");
const { execFileSync } = require("child_process");
const os = require("os");

const ROOT = path.resolve(__dirname, "..");
const read = (p) => fs.readFileSync(path.join(ROOT, p), "utf8");

/* ---------- helpers ---------- */
function loadData() {
  const ctx = { window: {} };
  vm.runInNewContext(read("js/broadcasts.js"), ctx);
  return { cfg: ctx.window.SITE_CONFIG, seasons: ctx.window.BROADCASTS };
}

// Same path rule as js/app.js
function partPaths(cfg, s, e) {
  const id = e.date.replace(/-/g, "_"), out = [];
  for (let n = 1; n <= e.parts; n++) {
    out.push(e.files ? e.files[n - 1] :
      (cfg.mp3Base || "") + "Season_" + (s.n < 10 ? "0" : "") + s.n + "/" + id + "/" + (e.cs ? "CS_" : "") + id + "_(" + n + ")_" + e.slug + ".mp3");
  }
  return out;
}

// Pull named functions out of app.js so they can be unit-tested without a DOM.
function appFunctions(names, extra) {
  const src = read("js/app.js");
  let code = (extra || "") + "\n";
  for (const name of names) {
    const start = src.indexOf("function " + name + "(");
    assert.ok(start >= 0, "app.js should define " + name);
    let i = src.indexOf("{", start), depth = 0;
    for (; i < src.length; i++) {
      if (src[i] === "{") depth++;
      else if (src[i] === "}" && --depth === 0) break;
    }
    code += src.slice(start, i + 1) + "\n";
  }
  return code;
}

function allPages() {
  const out = [];
  (function walk(dir) {
    for (const f of fs.readdirSync(dir, { withFileTypes: true })) {
      if (["mp3", "pictures", "tests", "tools", "node_modules", ".git"].includes(f.name) && dir === ROOT) continue;
      const p = path.join(dir, f.name);
      if (f.isDirectory()) walk(p);
      else if (/\.html?$/.test(f.name)) out.push(path.relative(ROOT, p).replace(/\\/g, "/"));
    }
  })(ROOT);
  return out;
}

const VOID = new Set(["area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "param", "source", "track", "wbr"]);
function checkHtml(src) {
  const errors = [], stack = [];
  const body = src.replace(/<!--[\s\S]*?-->/g, "").replace(/<(script|style)\b[^>]*>[\s\S]*?<\/\1>/gi, "<$1></$1>");
  const re = /<(\/?)([a-zA-Z][a-zA-Z0-9-]*)\b[^>]*?(\/?)>/g;
  let m;
  while ((m = re.exec(body))) {
    const [, close, rawTag, selfClose] = m, tag = rawTag.toLowerCase();
    if (VOID.has(tag) || selfClose) continue;
    if (!close) { stack.push(tag); continue; }
    if (stack[stack.length - 1] === tag) { stack.pop(); continue; }
    errors.push(`unexpected </${tag}> (open: ${stack.slice(-3).join(">")})`);
    const at = stack.lastIndexOf(tag);
    if (at >= 0) stack.length = at;
  }
  if (stack.length) errors.push("unclosed: " + stack.join(">"));
  return errors;
}

const attrs = (src, name) => [...src.matchAll(new RegExp(`\\s${name}="([^"]*)"`, "g"))].map((m) => m[1]);
const decodeEntities = (s) => s.replace(/&#x([0-9a-f]+);/gi, (_, h) => String.fromCharCode(parseInt(h, 16))).replace(/&#(\d+);/g, (_, d) => String.fromCharCode(+d)).replace(/&amp;/g, "&").replace(/&quot;/g, '"').replace(/&#39;/g, "'").replace(/&lt;/g, "<").replace(/&gt;/g, ">");

/* =====================================================================
   1. Broadcast data (js/broadcasts.js)
   ===================================================================== */
test("data: broadcasts.js loads and has seasons 1–20", () => {
  const { seasons } = loadData();
  assert.deepEqual(Array.from(seasons, (s) => s.n), Array.from({ length: 20 }, (_, i) => 20 - i));
});

test("data: every broadcast has a valid, unique date", () => {
  const { seasons } = loadData(), seen = new Map();
  for (const s of seasons) for (const e of s.episodes) {
    assert.match(e.date, /^\d{4}-\d{2}-\d{2}$/, e.title);
    const d = new Date(e.date + "T12:00:00Z");
    assert.equal(d.toISOString().slice(0, 10), e.date, "real calendar date: " + e.date);
    assert.ok(!seen.has(e.date), `duplicate date ${e.date}: "${seen.get(e.date)}" and "${e.title}" (ids are built from the date)`);
    seen.set(e.date, e.title);
  }
  assert.equal(seen.size, 355);
});

test("data: broadcasts are newest-first and inside their season's years", () => {
  const { seasons } = loadData();
  let prev = "9999";
  for (const s of seasons) {
    const years = s.span.split(/\s*–\s*/).map(Number);
    for (const e of s.episodes) {
      assert.ok(e.date < prev, `${e.date} should be older than ${prev}`);
      prev = e.date;
      const y = +e.date.slice(0, 4);
      assert.ok(y >= years[0] && y <= years[years.length - 1], `${e.date} outside season ${s.n} (${s.span})`);
    }
  }
});

test("data: titles, slugs and part counts are well-formed", () => {
  const { seasons } = loadData();
  for (const s of seasons) for (const e of s.episodes) {
    assert.ok(e.title && e.title === e.title.trim() && !/\s{2}/.test(e.title), "title spacing: " + e.title);
    assert.ok(e.parts >= 1 && e.parts <= 4, e.date + " parts");
    if (e.files) assert.equal(e.files.length, e.parts, e.date + " files vs parts");
    else assert.match(e.slug, /^[\w&\-]+$/, e.date + " slug");
  }
});

// Known gap: these recordings are missing on the old server too (HTTP 404), so they could not be copied.
const KNOWN_MISSING_MP3 = [1, 2, 3, 4].map((n) => `mp3/broadcasts/Season_06/2013_03_07/CS_2013_03_07_(${n})_Nisteia.mp3`);

test("data: every broadcast mp3 exists in mp3/ (apart from the known missing recordings)", () => {
  const { cfg, seasons } = loadData(), missing = [];
  for (const s of seasons) for (const e of s.episodes)
    for (const p of partPaths(cfg, s, e)) if (!fs.existsSync(path.join(ROOT, p))) missing.push(p);
  assert.deepEqual(missing.filter((p) => !KNOWN_MISSING_MP3.includes(p)).slice(0, 10), [], `${missing.length} mp3 files missing`);
  for (const p of KNOWN_MISSING_MP3)
    if (fs.existsSync(path.join(ROOT, p))) assert.fail(p + " has been added — remove it from KNOWN_MISSING_MP3");
});

test("data: 'Άρθρα & πηγές' links point to existing pages", () => {
  const { seasons } = loadData();
  for (const s of seasons) for (const e of s.episodes)
    if (e.link && !/^https?:/.test(e.link)) assert.ok(fs.existsSync(path.join(ROOT, e.link)), `${e.date}: ${e.link}`);
});

test("data: SITE_CONFIG is complete and the next broadcast is a Thursday 22:00 (Athens)", () => {
  const { cfg } = loadData();
  for (const k of ["nextBroadcast", "liveUrl", "columnUrl", "latestColumn", "youtubeId", "mp3Base"]) assert.ok(cfg[k], k);
  const t = Date.parse(cfg.nextBroadcast);
  assert.ok(!isNaN(t));
  const parts = new Intl.DateTimeFormat("en-GB", { timeZone: "Europe/Athens", weekday: "long", hour: "2-digit", minute: "2-digit", hourCycle: "h23" }).formatToParts(t);
  const get = (type) => parts.find((p) => p.type === type).value;
  assert.equal(get("weekday"), "Thursday");
  assert.equal(get("hour") + ":" + get("minute"), "22:00");
  assert.match(cfg.youtubeId, /^[\w-]{11}$/);
});

/* =====================================================================
   2. app.js helper functions
   ===================================================================== */
test("app.js: Greek search normalisation ignores accents, case and final sigma", () => {
  const ctx = {};
  vm.runInNewContext(appFunctions(["normChar", "norm"]), ctx);
  assert.equal(ctx.norm("Γένεση"), "γενεση");
  assert.equal(ctx.norm("ΓΕΝΕΣΗΣ"), "γενεσησ");
  assert.equal(ctx.norm("Κόσμος"), "κοσμοσ");
  assert.equal(ctx.norm("ΐ ΰ Ϊ"), "ι υ ι");
  assert.equal(ctx.norm("DNA"), "dna");
});

test("app.js: esc() escapes HTML special characters", () => {
  const ctx = {};
  vm.runInNewContext(appFunctions(["esc"]), ctx);
  assert.equal(ctx.esc(`<a href="x">'&'</a>`), "&lt;a href=&quot;x&quot;&gt;&#39;&amp;&#39;&lt;/a&gt;");
  assert.equal(ctx.esc(42), "42");
});

test("app.js: highlight() marks accent-insensitive matches and stays safe", () => {
  const ctx = {};
  vm.runInNewContext(appFunctions(["normChar", "esc", "highlight"]), ctx);
  assert.equal(ctx.highlight("Η Γένεση", ["γενεση"]), "Η <mark>Γένεση</mark>");
  assert.equal(ctx.highlight("Ερωτήσεις από τη Γένεση", ["γεν", "ερω"]), "<mark>Ερω</mark>τήσεις από τη <mark>Γέν</mark>εση");
  assert.equal(ctx.highlight("a <b> & c", []), "a &lt;b&gt; &amp; c");
  assert.equal(ctx.highlight("<script>", ["scr"]), "&lt;<mark>scr</mark>ipt&gt;");
  assert.equal(ctx.highlight("αα", ["α"]), "<mark>αα</mark>");
});

test("app.js: editDist() counts typos, including swapped letters, and stops early", () => {
  const ctx = {};
  vm.runInNewContext(appFunctions(["editDist"]), ctx);
  assert.equal(ctx.editDist("γενεση", "γενεση", 2), 0);
  assert.equal(ctx.editDist("γενσεη", "γενεση", 2), 1);          // swapped letters count once
  assert.equal(ctx.editDist("εγκεφαλσ", "εγκεφαλοσ", 2), 1);      // inputs are normalised (ς → σ) before comparing
  assert.equal(ctx.editDist("αβγδ", "ωψχφ", 1), 2);              // gives up beyond max
  assert.equal(ctx.editDist("α", "αβγδεζ", 2), 3);
});

test("app.js: greeklish() turns Latin typing into Greek", () => {
  const ctx = {};
  vm.runInNewContext("var GL = " + read("js/app.js").match(/var GL = (\[[\s\S]*?\]\]);/)[1] + ";\n" + appFunctions(["greeklish"]), ctx);
  assert.equal(ctx.greeklish("genesi"), "γενεσι");
  assert.equal(ctx.greeklish("theos"), "θεοσ");
  assert.equal(ctx.greeklish("psychi"), "ψυχι");
  assert.equal(ctx.greeklish("exelixi"), "εξελιξι");
});

test("app.js: fmt() and fmtSpeed() format times and speeds", () => {
  const ctx = {};
  vm.runInNewContext(appFunctions(["fmt", "fmtSpeed"]), ctx);
  assert.equal(ctx.fmt(0), "0:00");
  assert.equal(ctx.fmt(65.9), "1:05");
  assert.equal(ctx.fmt(3725), "1:02:05");
  assert.equal(ctx.fmt(-5), "0:00");
  assert.equal(ctx.fmt(NaN), "0:00");
  assert.equal(ctx.fmtSpeed(1.25), "1,25×");
  assert.equal(ctx.fmtSpeed(2), "2×");
});

function athensClock(ms) {
  const p = new Intl.DateTimeFormat("en-GB", { timeZone: "Europe/Athens", weekday: "short", hour: "2-digit", minute: "2-digit", hourCycle: "h23" }).formatToParts(ms);
  const g = (t) => p.find((x) => x.type === t).value;
  return g("weekday") + " " + g("hour") + ":" + g("minute");
}
function nextSlotAt(nowIso, nextBroadcast) {
  const fixedNow = Date.parse(nowIso);
  const FakeDate = function (...a) { return new Date(...a); };
  Object.assign(FakeDate, { parse: Date.parse, UTC: Date.UTC, now: () => fixedNow });
  const ctx = { Date: FakeDate, CFG: { nextBroadcast }, Intl };
  // the constants app.js defines next to these functions
  const consts = 'var DAY = 864e5, SHOW = 2 * 36e5, TZ = "Europe/Athens";' +
    'var athensFmt = new Intl.DateTimeFormat("en-GB", { timeZone: TZ, year: "numeric", month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit", hourCycle: "h23" });';
  vm.runInNewContext(appFunctions(["athensParts", "athensWallToUtc", "nextSlot"], consts), ctx);
  return ctx.nextSlot();
}

test("app.js: nextSlot() keeps the configured slot while it is upcoming", () => {
  const t = nextSlotAt("2026-10-06T10:00:00Z", "2026-10-15T22:00:00+03:00");
  assert.equal(new Date(t).toISOString(), "2026-10-15T19:00:00.000Z");
});

test("app.js: nextSlot() stays at Thursday 22:00 Athens time across the winter clock change", () => {
  // Clocks go back on 25 Oct 2026; the broadcast is still at 22:00 local on 29 Oct.
  const t = nextSlotAt("2026-10-20T10:00:00Z", "2026-10-15T22:00:00+03:00");
  assert.equal(athensClock(t), "Thu 22:00");
});

test("app.js: nextSlot() stays at 22:00 Athens time across the summer clock change", () => {
  const t = nextSlotAt("2027-04-01T10:00:00Z", "2027-03-18T22:00:00+02:00");
  assert.equal(athensClock(t), "Thu 22:00");
});

/* =====================================================================
   3. Page ↔ script contracts
   ===================================================================== */
test("index.html: every element app.js looks up by id exists", () => {
  const html = read("index.html"), ids = new Set([...attrs(html, "id"), ...attrs(read("js/app.js"), "id")]);   // ids the script creates itself
  const used = new Set([...read("js/app.js").matchAll(/\$\("#([\w-]+)"\)/g)].map((m) => m[1]));
  const missing = [...used].filter((id) => !ids.has(id));
  assert.deepEqual(missing, []);
});

test("inner pages: every element page.js needs exists", () => {
  for (const p of allPages()) {
    const html = read(p);
    if (!/js\/page\.js/.test(html)) continue;
    for (const id of ["themeToggle", "menuToggle", "nav"]) assert.ok(html.includes(`id="${id}"`), `${p} lacks #${id}`);
    if (html.includes('id="filter"')) assert.ok(html.includes("data-filter"), p + " has a filter box but nothing to filter");
  }
});

test("js: all scripts parse", () => {
  for (const f of ["js/app.js", "js/page.js", "js/broadcasts.js"])
    execFileSync(process.execPath, ["--check", path.join(ROOT, f)]);
});

/* =====================================================================
   4. Every HTML page
   ===================================================================== */
const PAGES = allPages();

test(`html: ${PAGES.length} pages are well-formed`, () => {
  const bad = PAGES.map((p) => [p, checkHtml(read(p))]).filter(([, e]) => e.length);
  assert.deepEqual(bad.slice(0, 5), [], `${bad.length} pages with tag errors`);
});

test("html: no duplicate ids on any page", () => {
  const bad = [];
  for (const p of PAGES) {
    const ids = attrs(read(p), "id"), dup = ids.filter((x, i) => ids.indexOf(x) !== i);
    if (dup.length) bad.push(p + ": " + [...new Set(dup)].join(", "));
  }
  assert.deepEqual(bad, []);
});

test("html: every content page has lang, charset, viewport, title and description", () => {
  const bad = [];
  for (const p of PAGES) {
    const s = read(p);
    if (/http-equiv="refresh"/.test(s)) continue;                      // redirect stubs
    const need = { lang: /<html lang="(el|en)"/, charset: /<meta charset="utf-8">/i, viewport: /name="viewport"/,
      title: /<title>[^<]{3,}<\/title>/, description: /name="description" content="[^"]{10,}"/ };
    const miss = Object.entries(need).filter(([, re]) => !re.test(s)).map(([k]) => k);
    if (miss.length) bad.push(p + ": " + miss.join(", "));
  }
  assert.deepEqual(bad, []);
});

test("html: every local link and image resolves to a file", () => {
  const missing = [];
  for (const p of PAGES) {
    const s = read(p);
    for (const raw of [...attrs(s, "href"), ...attrs(s, "src")]) {
      const u = decodeEntities(raw);
      if (/^([a-z]+:|#|\/\/)/i.test(u)) continue;
      const target = path.normalize(path.join(path.dirname(p), decodeURIComponent(u.split(/[#?]/)[0])));
      if (!fs.existsSync(path.join(ROOT, target))) missing.push(`${p} -> ${u}`);
    }
  }
  assert.deepEqual(missing.slice(0, 15), [], `${missing.length} broken local links`);
});

test("html: in-page anchors (#…) point to an id on the page", () => {
  const bad = [];
  for (const p of PAGES) {
    const s = read(p), ids = new Set(attrs(s, "id"));
    for (const h of attrs(s, "href")) if (/^#./.test(h) && !ids.has(decodeEntities(h.slice(1)))) bad.push(p + " " + h);
  }
  assert.deepEqual(bad.slice(0, 10), [], bad.length + " dangling anchors");
});

test("html: aria references point to existing ids", () => {
  const bad = [];
  for (const p of PAGES) {
    const s = read(p), ids = new Set(attrs(s, "id"));
    for (const a of ["aria-controls", "aria-labelledby", "aria-describedby"])
      for (const v of attrs(s, a)) for (const id of v.split(/\s+/)) if (!ids.has(id)) bad.push(`${p} ${a}=${id}`);
  }
  assert.deepEqual(bad, []);
});

test("html: images have alt text attributes and external new-tab links have rel=noopener", () => {
  const bad = [];
  for (const p of PAGES) {
    const s = read(p);
    for (const img of s.match(/<img\b[^>]*>/g) || []) if (!/\salt="/.test(img)) bad.push(p + " img without alt");
    for (const a of s.match(/<a\b[^>]*target="_blank"[^>]*>/g) || []) if (!/rel="[^"]*noopener/.test(a)) bad.push(p + " " + a.slice(0, 60));
  }
  assert.deepEqual(bad.slice(0, 10), []);
});

test("html: page content never links to the site by its full address (links stay relative)", () => {
  // the canonical / language / sharing tags in <!-- seo --> are meant to hold the full address
  const bad = PAGES.filter((p) => /(href|src)="https?:\/\/(www\.)?christianity-science\.gr\//i.test(
    read(p).replace(/<!-- seo -->[\s\S]*?<!-- \/seo -->/g, "")));
  assert.deepEqual(bad, []);
});

test("html: stylesheet and scripts carry the current version stamp", () => {
  const ver = (f) => crypto.createHash("sha1").update(fs.readFileSync(path.join(ROOT, f))).digest("hex").slice(0, 10);
  const want = { "css/site.css": ver("css/site.css"), "js/page.js": ver("js/page.js"), "js/app.js": ver("js/app.js"), "js/broadcasts.js": ver("js/broadcasts.js") };
  const bad = [];
  for (const p of PAGES) {
    const s = read(p);
    for (const [f, v] of Object.entries(want)) {
      const refs = [...s.matchAll(new RegExp(`(?:\\.\\./)*${f.replace(".", "\\.")}(\\?v=[0-9a-f]+)?"`, "g"))];
      for (const r of refs) if (r[1] !== "?v=" + v) bad.push(`${p}: ${f}${r[1] || ""}`);
    }
  }
  assert.deepEqual(bad.slice(0, 5), [], bad.length + " stale or missing stamps (run python tools/stamp.py)");
});

test("html: redirect stubs for old addresses point to existing pages", () => {
  for (const [old, target] of [["faq.htm", "faq.html"], ["articles.htm", "articles.html"], ["material.htm", "material.html"],
    ["media.htm", "media.html"], ["links.htm", "links.html"], ["contact.htm", "contact.html"], ["welcome.htm", "about.html"],
    ["index.htm", "index.html"], ["radio.htm", "index.html#archive"], ["search.htm", "index.html#archive"]]) {
    assert.ok(read(old).includes(`url=${target}"`), old);
    assert.ok(fs.existsSync(path.join(ROOT, target.split("#")[0])), target);
  }
});

/* =====================================================================
   5. CSS
   ===================================================================== */
test("css: braces and comments are balanced", () => {
  const css = read("css/site.css");
  assert.equal((css.match(/\/\*/g) || []).length, (css.match(/\*\//g) || []).length);
  let depth = 0;
  for (const ch of css.replace(/\/\*[\s\S]*?\*\//g, "")) {
    if (ch === "{") depth++;
    if (ch === "}") { depth--; assert.ok(depth >= 0, "extra }"); }
  }
  assert.equal(depth, 0);
});

test("css: every var(--x) without a fallback is defined somewhere", () => {
  const css = read("css/site.css");
  const pages = PAGES.map(read).join("\n");
  const defined = new Set([...(css + pages).matchAll(/(--[\w-]+)\s*:/g)].map((m) => m[1]));
  const used = [...css.matchAll(/var\((--[\w-]+)\s*\)/g)].map((m) => m[1]);
  assert.deepEqual([...new Set(used.filter((v) => !defined.has(v)))], []);
});

test("css: every class used in the page templates and scripts is styled", () => {
  const css = read("css/site.css");
  const sources = [read("index.html"), read("material.html"), read("faq.html"), read("media.html"), read("js/app.js")].join("\n");
  const classes = new Set();
  for (const m of sources.matchAll(/class="([^"]+)"/g)) m[1].split(/\s+/).forEach((c) => c && /^[a-z][\w-]*$/i.test(c) && classes.add(c));
  const unstyled = [...classes].filter((c) => !new RegExp(`\\.${c}(?![\\w-])`).test(css));
  // utility hooks that are intentionally unstyled
  const ok = new Set(["i-play", "i-pause", "sr", "ep__links", "embed", "hero__text", "list", "video", "part"]);
  assert.deepEqual(unstyled.filter((c) => !ok.has(c)), []);
});

/* =====================================================================
   6. tools/stamp.py
   ===================================================================== */
test("tools/stamp.py: stamps nested pages correctly and is idempotent", () => {
  const tmp = fs.mkdtempSync(path.join(os.tmpdir(), "stamp-"));
  fs.mkdirSync(path.join(tmp, "tools")); fs.mkdirSync(path.join(tmp, "css")); fs.mkdirSync(path.join(tmp, "js")); fs.mkdirSync(path.join(tmp, "material"));
  fs.copyFileSync(path.join(ROOT, "tools/stamp.py"), path.join(tmp, "tools/stamp.py"));
  for (const f of ["css/site.css", "js/app.js", "js/page.js", "js/broadcasts.js", "js/broadcasts-en.js"]) fs.writeFileSync(path.join(tmp, f), "x" + f);
  fs.writeFileSync(path.join(tmp, "a.html"), '<link href="css/site.css"><script src="js/page.js?v=0000000000"></script>');
  fs.writeFileSync(path.join(tmp, "material/b.htm"), '<link href="../css/site.css">');
  const py = process.env.PYTHON || "python";
  const out1 = execFileSync(py, [path.join(tmp, "tools/stamp.py")]).toString();
  const out2 = execFileSync(py, [path.join(tmp, "tools/stamp.py")]).toString();
  const v = crypto.createHash("sha1").update("xcss/site.css").digest("hex").slice(0, 10);
  assert.match(fs.readFileSync(path.join(tmp, "a.html"), "utf8"), new RegExp(`href="css/site\\.css\\?v=${v}"`));
  assert.match(fs.readFileSync(path.join(tmp, "material/b.htm"), "utf8"), new RegExp(`href="\\.\\./css/site\\.css\\?v=${v}"`));
  assert.doesNotMatch(fs.readFileSync(path.join(tmp, "a.html"), "utf8"), /0000000000/);
  assert.match(out1, /stamped 2 pages/);
  assert.match(out2, /stamped 0 pages/);
  fs.rmSync(tmp, { recursive: true, force: true });
});

/* =====================================================================
   7. English version (en/)
   ===================================================================== */
const MAIN = ["index.html", "about.html", "articles.html", "material.html", "faq.html", "media.html", "links.html", "contact.html"];

test("english: every main page has an English version and they point to each other", () => {
  for (const p of MAIN) {
    const el = read(p), en = read("en/" + p);
    assert.match(en, /<html lang="en">/, p);
    assert.ok(el.includes(`href="en/${p}" hreflang="en"`), p + ": EN button");
    assert.ok(en.includes(`href="../${p}" hreflang="el"`), "en/" + p + ": ΕΛ button");
    const site = (read("tools/seo.py").match(/SITE_URL = "([^"]+)"/) || [])[1];
    const full = (x) => site + (x === "index.html" ? "" : x);
    for (const s of [el, en]) {
      assert.ok(s.includes(`<link rel="alternate" hreflang="el" href="${full(p)}">`), p + ": hreflang el (full address)");
      assert.ok(s.includes(`<link rel="alternate" hreflang="en" href="${full("en/" + p)}">`), p + ": hreflang en (full address)");
    }
  }
});

test("english: no untranslated Greek text on the English pages", () => {
  const bad = [];
  for (const p of MAIN) {
    const text = read("en/" + p).replace(/<(script|style)\b[\s\S]*?<\/\1>/g, " ").replace(/<[^>]+>/g, " ");
    const greek = (text.match(/[\u0370-\u03ff\u1f00-\u1fff][^\n]{0,40}/g) || []).filter((g) => !/^ΕΛ(\s|$)/.test(g));     // the language button itself (\b does not work with Greek letters)
    if (greek.length) bad.push(`en/${p}: ${greek.slice(0, 3).join(" | ")}`);
  }
  assert.deepEqual(bad, []);
});

test("english: every broadcast has an English title", () => {
  const ctx = { window: {} };
  vm.runInNewContext(read("js/broadcasts.js") + "\n" + read("js/broadcasts-en.js"), ctx);
  const dates = [];
  for (const s of ctx.window.BROADCASTS) for (const e of s.episodes) dates.push(e.date);
  const en = ctx.window.BROADCAST_TITLES_EN;
  assert.deepEqual(dates.filter((d) => !en[d] || /[\u0370-\u03ff]/.test(en[d])), []);
  assert.deepEqual(Object.keys(en).filter((d) => !dates.includes(d)), []);
});

test("english: Scripture quotations use the King James wording", () => {
  const home = read("en/index.html"), about = read("en/about.html");
  assert.ok(home.includes("And ye shall know the truth, and the truth shall make you free"));
  assert.ok(about.includes("all scripture") || about.includes("given by inspiration of God"));
  assert.doesNotMatch(read("en/articles.html") + about, /divine inspiration/i);
});

test("english: Greek pages without a translation offer the English section instead", () => {
  const bad = [];
  for (const p of PAGES.filter((x) => /^(material|categories|articles|files|mp3)\//.test(x))) {
    const s = read(p);
    if (/http-equiv="refresh"/.test(s)) continue;
    const m = s.match(/<a class="iconbtn langbtn"[^>]*href="([^"]+)"/);
    if (!m || !fs.existsSync(path.join(ROOT, path.dirname(p), m[1]))) bad.push(p);
  }
  assert.deepEqual(bad.slice(0, 5), [], bad.length + " pages without a working EN button");
});

/* =====================================================================
   8. Search engines, sharing, not-found page
   ===================================================================== */
const SITE = (read("tools/seo.py").match(/SITE_URL = "([^"]+)"/) || [])[1];

test("seo: every content page has its full canonical address and sharing tags", () => {
  const bad = [];
  for (const p of PAGES) {
    const s = read(p);
    if (p === "404.html") continue;
    if (/http-equiv="refresh"/.test(s)) { if (!/name="robots" content="noindex"/.test(s)) bad.push(p + ": redirect without noindex"); continue; }
    const want = SITE + (p === "index.html" ? "" : p);
    if (!s.includes(`<link rel="canonical" href="${want}">`)) bad.push(p + ": canonical");
    if (!s.includes(`<meta property="og:image" content="${SITE}pictures/share.png">`)) bad.push(p + ": og:image");
    if (/hreflang="[^"]*" href="(?!https?:)/.test(s)) bad.push(p + ": relative hreflang address");
  }
  assert.deepEqual(bad.slice(0, 10), [], bad.length + " pages");
});

test("seo: sitemap.xml lists existing pages with full addresses, robots.txt points to it", () => {
  const xml = read("sitemap.xml");
  const locs = [...xml.matchAll(/<loc>([^<]+)<\/loc>/g)].map((m) => m[1].replace(/&amp;/g, "&"));
  assert.ok(locs.length > 150, locs.length + " entries");
  for (const l of locs) {
    assert.ok(l.startsWith(SITE), l);
    const rel = l.slice(SITE.length) || "index.html";
    assert.ok(fs.existsSync(path.join(ROOT, rel)), "sitemap lists a missing page: " + rel);
    assert.ok(!/http-equiv="refresh"/.test(read(rel)), "sitemap lists a redirect: " + rel);
  }
  assert.ok(locs.some((l) => l.endsWith("/en/faq.html")));
  assert.ok(!locs.some((l) => l.includes("/files/")), "copies of other publishers' articles are not promoted");
  assert.match(read("robots.txt"), new RegExp("Sitemap: " + SITE.replace(/\./g, "\.") + "sitemap\.xml"));
});

test("404 page: bilingual, not indexed, and every link starts at the site root", () => {
  const s = read("404.html");
  assert.match(s, /Η σελίδα δεν βρέθηκε/);
  assert.match(s, /Page not found/);
  assert.match(s, /name="robots" content="noindex"/);
  const relative = attrs(s, "href").concat(attrs(s, "src")).filter((u) => !/^([a-z]+:|#|\/)/i.test(u));
  assert.deepEqual(relative, []);
});

test("share image is a 1200×630 PNG", () => {
  const b = fs.readFileSync(path.join(ROOT, "pictures/share.png"));
  assert.equal(b.toString("ascii", 1, 4), "PNG");
  assert.equal(b.readUInt32BE(16), 1200);
  assert.equal(b.readUInt32BE(20), 630);
});
