/*
 * Browser tests (headless Chrome via puppeteer-core).
 *
 * Needs: a local server on BASE (default http://127.0.0.1:8081) serving the project folder,
 *        e.g.  python -m http.server 8081 --bind 127.0.0.1
 *        puppeteer-core installed (npm i puppeteer-core) and Chrome/Edge installed.
 * Run:   node --test tests/browser.test.js
 */
"use strict";
const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("fs");
const path = require("path");
const puppeteer = require("puppeteer-core");

const ROOT = path.resolve(__dirname, "..");
const BASE = process.env.BASE || "http://127.0.0.1:8081/";
const CHROME = process.env.CHROME || [
  "C:/Program Files/Google/Chrome/Application/chrome.exe",
  "C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe",
  "/usr/bin/google-chrome", "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
].find((p) => fs.existsSync(p));

let browser;
test.before(async () => {
  browser = await puppeteer.launch({ executablePath: CHROME, headless: true, args: ["--autoplay-policy=no-user-gesture-required", "--mute-audio"] });
});
test.after(async () => { if (browser) await browser.close(); });

/** Open a fresh page (own storage), collecting console errors and failed same-origin requests. */
async function open(url, { width = 1280, height = 900, before } = {}) {
  const ctx = await browser.createBrowserContext();
  const page = await ctx.newPage();
  await page.setViewport({ width, height });
  page.problems = [];
  page.on("pageerror", (e) => page.problems.push("JS error: " + e.message));
  page.on("console", (m) => { if (m.type() === "error" && !/youtube|ytimg|googleapis|gstatic|doubleclick/i.test(m.text() + (m.location().url || ""))) page.problems.push("console: " + m.text()); });
  page.on("requestfailed", (r) => { if (r.url().startsWith(BASE) && !/\.mp3/.test(r.url())) page.problems.push("failed: " + r.url()); });
  page.on("response", (r) => { if (r.url().startsWith(BASE) && r.status() >= 400) page.problems.push(r.status() + " " + r.url()); });
  if (before) await before(page);
  await page.goto(BASE + url, { waitUntil: "load" });
  page.close2 = () => ctx.close();
  return page;
}

function allPages() {
  const out = [];
  (function walk(dir) {
    for (const f of fs.readdirSync(dir, { withFileTypes: true })) {
      if (dir === ROOT && ["mp3", "pictures", "tests", "tools", "node_modules"].includes(f.name)) continue;
      const p = path.join(dir, f.name);
      if (f.isDirectory()) walk(p);
      else if (/\.html?$/.test(f.name)) out.push(path.relative(ROOT, p).replace(/\\/g, "/"));
    }
  })(ROOT);
  return out.filter((p) => !/http-equiv="refresh"/.test(fs.readFileSync(path.join(ROOT, p), "utf8")));
}

/* =====================================================================
   Every page: loads cleanly, no JS errors, no broken assets, fits a phone
   ===================================================================== */
test("every page loads without JS errors or broken local assets, and fits a 375px phone", async () => {
  const pages = allPages(), problems = [];
  const ctx = await browser.createBrowserContext();
  const page = await ctx.newPage();
  await page.setViewport({ width: 375, height: 800, isMobile: true, hasTouch: true });
  let current = "", list = [];
  page.on("pageerror", (e) => list.push("JS error: " + e.message));
  page.on("response", (r) => { if (r.url().startsWith(BASE) && r.status() >= 400 && !/\.mp3/.test(r.url())) list.push(r.status() + " " + r.url().slice(BASE.length)); });
  for (const p of pages) {
    current = p; list = [];
    await page.goto(BASE + p, { waitUntil: "load" });
    const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
    if (overflow > 1) list.push(`horizontal scroll ${overflow}px`);
    const css = await page.evaluate(() => getComputedStyle(document.querySelector(".topbar") || document.body).position);
    if (css !== "sticky") list.push("stylesheet not applied");
    if (list.length) problems.push(current + ": " + list.join(" | "));
  }
  await ctx.close();
  assert.deepEqual(problems.slice(0, 15), [], `${problems.length} of ${pages.length} pages have problems`);
});

/* =====================================================================
   Home page: archive, search, filters, deep links
   ===================================================================== */
test("home: archive lists all 355 broadcasts in 20 seasons", async () => {
  const page = await open("index.html");
  assert.equal(await page.$$eval("#list .ep", (e) => e.length), 355);
  assert.equal(await page.$$eval("#list .season", (e) => e.length), 20);
  assert.match(await page.$eval("#archiveStats", (e) => e.textContent), /355 εκπομπές σε 20 κύκλους/);
  assert.match(await page.$eval("#latest .latest__title", (e) => e.textContent), /αθεϊστικά/);
  assert.deepEqual(page.problems, []);
  await page.close2();
});

/** Type a query into the archive search and return the ranked titles and the status line. */
async function searchFor(page, q) {
  await page.$eval("#q", (i, v) => { i.value = v; i.dispatchEvent(new Event("input")); }, q);
  await new Promise((r) => setTimeout(r, 300));               // input is debounced by 120 ms
  return page.evaluate(() => ({
    titles: [...document.querySelectorAll("#list .ep__title")].map((x) => x.textContent),
    msg: document.querySelector("#results").textContent,
    empty: !document.querySelector("#empty").hidden,
  }));
}

test("search: ignores accents, ranks the best matches first and highlights them", async () => {
  const page = await open("index.html");
  const r = await searchFor(page, "γενεση");
  assert.ok(r.titles.length >= 4, r.titles.join(" / "));
  assert.ok(r.titles.slice(0, 4).every((t) => /Γένεσ/.test(t)), r.titles.slice(0, 4).join(" / "));
  assert.ok(await page.$("#list mark"));
  assert.match(r.msg, /Βρέθηκαν \d+ εκπομπές για «γενεση», οι πιο σχετικές πρώτα/);
  await page.close2();
});

test("search: tolerates typos", async () => {
  const page = await open("index.html");
  for (const [q, want] of [["γενσεη", /Γένεσ/], ["αστρονομεια", /^Αστρονομία/], ["εγκεφαλς", /Εγκέφαλος/], ["τεχνιτη νοιμοσινη", /Τεχνητή νοημοσύνη/i]]) {
    const r = await searchFor(page, q);
    assert.match(r.titles[0] || "", want, `«${q}» → ${r.titles[0]}`);
  }
  await page.close2();
});

test("search: finds other word forms and Greeklish", async () => {
  const page = await open("index.html");
  let r = await searchFor(page, "εξελιξεως");
  assert.ok(r.titles.filter((t) => /Εξέλιξη/.test(t)).length >= 3, r.titles.join(" / "));
  r = await searchFor(page, "genesi");
  assert.match(r.titles[0], /Γένεσ/);
  r = await searchFor(page, "exelixi");
  assert.match(r.titles.slice(0, 5).join(" "), /Εξέλιξη/);
  await page.close2();
});

test("search: several vague words still find broadcasts matching only some of them", async () => {
  const page = await open("index.html");
  const r = await searchFor(page, "ψυχολογια εφηβων");
  assert.ok(r.titles.length >= 3);
  assert.ok(r.titles.slice(0, 4).some((t) => /εφήβων/i.test(t)) && r.titles.some((t) => /ψυχολογία/i.test(t)), r.titles.join(" / "));
  await page.close2();
});

test("search: with no good match shows the closest broadcasts and says so", async () => {
  const page = await open("index.html");
  const r = await searchFor(page, "γενσεη");
  assert.ok(r.titles.length > 0);
  assert.match(r.msg, /Δεν βρέθηκε ακριβής αντιστοιχία/);
  assert.equal(await page.$eval("#list .season__title", (e) => e.textContent), "Πλησιέστερες εκπομπές");
  await page.close2();
});

test("search: one result uses the singular, and the season filter still applies", async () => {
  const page = await open("index.html");
  let r = await searchFor(page, "bullying");
  assert.equal(r.titles.length, 1);
  assert.equal(r.msg, "Βρέθηκε 1 εκπομπή για «bullying».");
  await page.click('#seasonBar [data-season="2"]');
  r = await page.evaluate(() => [...document.querySelectorAll("#list .ep__season")].map((x) => x.textContent));
  assert.ok(r.every((s) => s === "2ος κύκλος"), r.join(", "));
  await page.close2();
});

test("home: search with no match shows the empty state; clearing restores everything", async () => {
  const page = await open("index.html");
  await page.type("#q", "ζζζζζζ");
  await page.waitForFunction(() => !document.querySelector("#empty").hidden);
  assert.equal(await page.$$eval("#list .ep", (e) => e.length), 0);
  await page.click("#clearSearch");
  await page.waitForFunction(() => document.querySelectorAll("#list .ep").length === 355);
  assert.equal(await page.$eval("#empty", (e) => e.hidden), true);
  await page.close2();
});

test("home: season chips filter the list", async () => {
  const page = await open("index.html");
  await page.click('#seasonBar [data-season="1"]');
  assert.equal(await page.$$eval("#list .season", (e) => e.length), 1);
  assert.equal(await page.$$eval("#list .ep", (e) => e.length), 12);
  assert.equal(await page.$eval('#seasonBar [data-season="1"]', (e) => e.getAttribute("aria-pressed")), "true");
  await page.click('#seasonBar [data-season="all"]');
  assert.equal(await page.$$eval("#list .ep", (e) => e.length), 355);
  await page.close2();
});

test("home: '/' jumps to search; Escape leaves it", async () => {
  const page = await open("index.html");
  await page.keyboard.press("/");
  await page.waitForFunction(() => document.activeElement && document.activeElement.id === "q", { timeout: 2000 });
  await page.keyboard.press("Escape");
  assert.notEqual(await page.evaluate(() => document.activeElement.id), "q");
  await page.close2();
});

test("home: deep link #e-2013_11_14 shows and highlights that broadcast even when filtered", async () => {
  const page = await open("index.html#e-2013_11_14");
  assert.equal(await page.$eval("#e-2013_11_14", (e) => e.classList.contains("is-target")), true);
  // filter to another season, then navigate to the hash
  await page.click('#seasonBar [data-season="1"]');
  await page.evaluate(() => { location.hash = ""; location.hash = "#e-2013_11_14"; });
  await page.waitForSelector("#e-2013_11_14.is-target");
  await page.close2();
});

/* =====================================================================
   Player
   ===================================================================== */
const audioState = (page) => page.evaluate(() => {
  const a = document.querySelector("#audio");
  return { src: decodeURI(a.getAttribute("src") || ""), t: a.currentTime, paused: a.paused, rate: a.playbackRate, ready: a.readyState };
});

test("player: play button loads part 1 from the local mp3 folder and plays", async () => {
  const page = await open("index.html");
  await page.click('#e-2008_01_31 .ep__play');
  await page.waitForFunction(() => document.querySelector("#audio").readyState >= 1, { timeout: 15000 });
  const s = await audioState(page);
  assert.equal(s.src, "mp3/broadcasts/Season_01/2008_01_31/CS_2008_01_31_(1)_Eisagogiki.mp3");
  assert.equal(await page.$eval("#player", (e) => e.hidden), false);
  assert.match(await page.$eval("#pTitle", (e) => e.textContent), /Εισαγωγική/);
  assert.deepEqual(page.problems, []);
  await page.close2();
});

test("player: speed button cycles and the choice survives a reload", async () => {
  const page = await open("index.html");
  await page.click('#e-2008_01_31 .ep__play');
  await page.click("#speed");
  assert.equal(await page.$eval("#speed", (e) => e.textContent), "1,25×");
  assert.equal((await audioState(page)).rate, 1.25);
  await page.reload({ waitUntil: "load" });
  assert.equal(await page.$eval("#speed", (e) => e.textContent), "1,25×");
  await page.close2();
});

test("player: switching parts quickly does not jump to the previous part's saved position", async () => {
  // Part 1 has saved progress at 10:00; part 3 has none and must start at 0.
  const page = await open("index.html", {
    before: (p) => p.evaluateOnNewDocument(() => localStorage.setItem("cs-progress", JSON.stringify({ "2008_01_31": { t: [600], d: [1800] } }))),
  });
  await page.evaluate(() => {
    document.querySelector('#e-2008_01_31 .part[data-part="0"]').click();
    document.querySelector('#e-2008_01_31 .part[data-part="2"]').click();
  });
  await page.waitForFunction(() => document.querySelector("#audio").readyState >= 1, { timeout: 15000 });
  await new Promise((r) => setTimeout(r, 300));
  const s = await audioState(page);
  assert.match(s.src, /_\(3\)_/);
  assert.ok(s.t < 5, `part 3 started at ${s.t.toFixed(1)}s instead of 0`);
  await page.close2();
});

test("player: progress is remembered and offered as 'Συνέχεια' after reload", async () => {
  const page = await open("index.html");
  await page.click('#e-2008_01_31 .ep__play');
  await page.waitForFunction(() => document.querySelector("#audio").readyState >= 1, { timeout: 15000 });
  await page.evaluate(() => { const a = document.querySelector("#audio"); a.currentTime = 125; a.dispatchEvent(new Event("timeupdate")); a.pause(); });
  await page.reload({ waitUntil: "load" });
  assert.equal(await page.$eval("#resume", (e) => e.hidden), false);
  assert.match(await page.$eval("#resume", (e) => e.textContent), /1ο ημίωρο, 2:0[45]/);
  await page.click("#resumeBtn");
  await page.waitForFunction(() => document.querySelector("#audio").currentTime > 100, { timeout: 15000 });
  await page.close2();
});

test("player: close button hides the player and stops audio", async () => {
  const page = await open("index.html");
  await page.click('#e-2008_01_31 .ep__play');
  await page.click("#pClose");
  assert.equal(await page.$eval("#player", (e) => e.hidden), true);
  assert.equal((await audioState(page)).src, "");
  await page.close2();
});

test("player: download menu lists 4 existing mp3s and closes with Escape", async () => {
  const page = await open("index.html");
  await page.click('#e-2008_01_31 [data-dl]');
  const links = await page.$$eval("#e-2008_01_31 .dlmenu a", (e) => e.map((a) => a.getAttribute("href")));
  assert.equal(links.length, 4);
  for (const l of links) assert.ok(fs.existsSync(path.join(ROOT, decodeURI(l))), l);
  assert.equal(await page.$eval('#e-2008_01_31 [data-dl]', (e) => e.getAttribute("aria-expanded")), "true");
  await page.keyboard.press("Escape");
  assert.equal(await page.$("#e-2008_01_31 .dlmenu"), null);
  await page.close2();
});

test("home: 'Αντιγραφή συνδέσμου' copies the broadcast link", async () => {
  const page = await open("index.html");
  await browser.defaultBrowserContext().overridePermissions(BASE, ["clipboard-read", "clipboard-write", "clipboard-sanitized-write"]);
  await page.evaluate(() => { window.__copied = null; navigator.clipboard.writeText = (t) => { window.__copied = t; return Promise.resolve(); }; });
  await page.click('#e-2008_01_31 [data-share]');
  await page.waitForFunction(() => window.__copied);
  assert.equal(await page.evaluate(() => window.__copied), BASE + "index.html#e-2008_01_31");
  await page.waitForFunction(() => document.querySelector("#toast").classList.contains("is-on"));
  await page.close2();
});

/* =====================================================================
   Next live broadcast: countdown and calendar file
   ===================================================================== */
async function openAt(isoNow) {
  return open("index.html", {
    before: (p) => p.evaluateOnNewDocument((now) => {
      const offset = Date.parse(now) - Date.now();
      window.__shift = (ms) => { window.__extra = (window.__extra || 0) + ms; };
      const real = Date.now;
      Date.now = () => real() + offset + (window.__extra || 0);
    }, isoNow),
  });
}

test("countdown: shows the next Thursday 22:00 broadcast", async () => {
  const page = await openAt("2026-10-12T10:00:00Z");
  assert.match(await page.$eval("#nextDate", (e) => e.textContent), /Πέμπτη 15 Οκτωβρίου/);
  assert.equal(await page.$$eval("#countdown div", (e) => e.length), 4);
  await page.close2();
});

test("countdown: after the live show ends it moves on to the next broadcast (no reload)", async () => {
  const page = await openAt("2026-10-15T19:30:00Z");                 // during the show
  await page.waitForFunction(() => document.querySelector(".onair").classList.contains("is-live"));
  await page.evaluate(() => window.__shift(3 * 3600e3));            // 3 hours later
  await new Promise((r) => setTimeout(r, 1500));
  assert.equal(await page.$eval(".onair", (e) => e.classList.contains("is-live")), false, "still says 'live' after the show ended");
  assert.match(await page.$eval("#nextDate", (e) => e.textContent), /29 Οκτωβρίου/);
  await page.close2();
});

test("calendar file: valid iCalendar that repeats every 2 weeks at 22:00 Athens time all year", async () => {
  const page = await openAt("2026-10-12T10:00:00Z");
  const href = await page.$eval("#calLink", (e) => e.getAttribute("href"));
  const ics = decodeURIComponent(href.replace(/^data:text\/calendar;charset=utf-8,/, ""));
  for (const line of ["BEGIN:VCALENDAR", "VERSION:2.0", "BEGIN:VEVENT", "RRULE:FREQ=WEEKLY;INTERVAL=2", "END:VEVENT", "END:VCALENDAR"])
    assert.ok(ics.includes(line), line);
  assert.ok(ics.split("\r\n").every((l) => l.length > 0), "CRLF line endings");
  const event = ics.slice(ics.indexOf("BEGIN:VEVENT"));          // skip the VTIMEZONE block
  const start = (event.match(/^DTSTART[^\r\n]*/m) || [""])[0];
  // A repeating event stored in UTC moves to 21:00 when the clocks go back.
  assert.match(start, /^DTSTART;TZID=Europe\/Athens:20261015T220000$/, "DTSTART must be in Athens local time, got " + start);
  assert.ok(/BEGIN:VTIMEZONE[\s\S]*TZID:Europe\/Athens/.test(ics), "VTIMEZONE for Europe/Athens");
  const stamp = (ics.match(/^DTSTAMP:(\S+)/m) || [])[1];
  assert.ok(stamp && !start.endsWith(stamp), "DTSTAMP should be the creation time, not the event time");
  await page.close2();
});

/* =====================================================================
   Inner pages
   ===================================================================== */
test("theme: toggle switches dark/light and is remembered on other pages", async () => {
  const page = await open("faq.html", { before: (p) => p.emulateMediaFeatures([{ name: "prefers-color-scheme", value: "light" }]) });
  const bg = () => page.evaluate(() => getComputedStyle(document.body).backgroundColor);
  const light = await bg();
  await page.click("#themeToggle");
  assert.equal(await page.evaluate(() => document.documentElement.getAttribute("data-theme")), "dark");
  assert.notEqual(await bg(), light);
  await page.goto(BASE + "material/2012_11_15.htm", { waitUntil: "load" });
  assert.equal(await page.evaluate(() => document.documentElement.getAttribute("data-theme")), "dark");
  await page.goto(BASE + "index.html", { waitUntil: "load" });
  assert.equal(await page.evaluate(() => document.documentElement.getAttribute("data-theme")), "dark");
  await page.close2();
});

test("theme: saved dark theme is applied before the page is first painted (no white flash)", async () => {
  const page = await open("about.html", {
    before: async (p) => {
      await p.emulateMediaFeatures([{ name: "prefers-color-scheme", value: "light" }]);
      await p.evaluateOnNewDocument(() => {
        localStorage.setItem("cs-theme", JSON.stringify("dark"));
        // record the theme at the moment the <body> element first appears
        // <html> does not exist yet when this runs, so watch the whole document
        new MutationObserver((_, o) => { if (document.body) { window.__themeAtBody = document.documentElement.getAttribute("data-theme"); o.disconnect(); } })
          .observe(document, { childList: true, subtree: true });
      });
    },
  });
  assert.equal(await page.evaluate(() => window.__themeAtBody), "dark");
  await page.close2();
});

test("mobile menu opens and closes", async () => {
  const page = await open("articles.html", { width: 375, height: 800 });
  assert.equal(await page.$eval("#nav", (e) => getComputedStyle(e).display), "none");
  await page.click("#menuToggle");
  assert.equal(await page.$eval("#nav", (e) => getComputedStyle(e).display), "flex");
  assert.equal(await page.$eval("#menuToggle", (e) => e.getAttribute("aria-expanded")), "true");
  await page.click("#menuToggle");
  assert.equal(await page.$eval("#nav", (e) => getComputedStyle(e).display), "none");
  await page.close2();
});

test("mobile menu closes with Escape", async () => {
  const page = await open("articles.html", { width: 375, height: 800 });
  await page.click("#menuToggle");
  await page.keyboard.press("Escape");
  assert.equal(await page.$eval("#nav", (e) => getComputedStyle(e).display), "none");
  await page.close2();
});

test("articles: filter is accent-insensitive and shows an empty message", async () => {
  const page = await open("articles.html");
  const visible = () => page.$$eval(".linklist li", (e) => e.filter((x) => !x.hidden).length);
  assert.equal(await visible(), 51);
  await page.type("#filter", "εξαρτησεις");
  assert.equal(await visible(), 5);
  await page.click("#filter", { count: 3 }); await page.keyboard.type("qqqq");
  assert.equal(await visible(), 0);
  assert.equal(await page.$eval("#filterEmpty", (e) => e.hidden), false);
  await page.close2();
});

test("faq: link #q-3 opens that question; filter works", async () => {
  const page = await open("faq.html#q-3");
  assert.equal(await page.$eval("#q-3", (e) => e.open), true);
  assert.equal(await page.$eval("#q-1", (e) => e.open), false);
  await page.type("#filter", "ηλιου");
  const shown = await page.$$eval(".faq details", (e) => e.filter((x) => !x.hidden).map((x) => x.id));
  assert.deepEqual(shown, ["q-5", "q-7"]);
  await page.close2();
});

test("topics: 13 tiles render as a grid", async () => {
  const page = await open("material.html");
  assert.equal(await page.$$eval(".topic", (e) => e.length), 13);
  assert.equal(await page.$eval(".topics", (e) => getComputedStyle(e).display), "grid");
  const h = await page.$$eval(".topic", (e) => e.map((x) => x.getBoundingClientRect().height));
  assert.ok(h.every((x) => x >= 150), "tiles are tall cards");
  await page.close2();
});

test("media: the poll audio player can load its mp3", async () => {
  const page = await open("media.html");
  const src = await page.$eval("audio", (a) => a.getAttribute("src"));
  assert.ok(fs.existsSync(path.join(ROOT, src)), src);
  await page.$eval("audio", (a) => { a.preload = "metadata"; a.load(); });
  await page.waitForFunction(() => document.querySelector("audio").readyState >= 1, { timeout: 15000 });
  await page.close2();
});

test("converted pages: videos use privacy-friendly YouTube embeds and pager links work", async () => {
  const page = await open("material/2012_11_15.htm");
  const pager = await page.$$eval(".pager a", (e) => e.map((a) => a.href));
  assert.ok(pager.length >= 1);
  for (const href of pager) {
    const r = await page.evaluate((u) => fetch(u).then((x) => x.status), href);
    assert.equal(r, 200, href);
  }
  const v = await open("material/AschExperiment.htm");
  assert.match(await v.$eval(".embed iframe", (e) => e.src), /^https:\/\/www\.youtube-nocookie\.com\/embed\//);
  await v.close2();
  await page.close2();
});

/* =====================================================================
   English version
   ===================================================================== */
test("english home: interface, titles and dates are in English; audio plays from the shared mp3 folder", async () => {
  const page = await open("en/index.html");
  assert.equal(await page.$$eval("#list .ep", (e) => e.length), 355);
  assert.match(await page.$eval("#archiveStats", (e) => e.textContent), /^355 broadcasts in 20 seasons, .*Audio in Greek\.$/);
  assert.equal(await page.$eval("#seasonBar .chip", (e) => e.textContent), "All seasons");
  assert.match(await page.$eval("#latest .latest__meta", (e) => e.textContent), /^\d{1,2} [A-Z][a-z]+ \d{4}, Season \d+, \d parts$/);
  assert.match(await page.$eval("#list .ep__title", (e) => e.textContent), /^[\x00-\u024f“”‘’–—…·]+$/);   // Latin text only
  await page.click("#list .ep .ep__play");
  await page.waitForFunction(() => document.querySelector("#audio").readyState >= 1, { timeout: 15000 });
  assert.match(await page.$eval("#audio", (a) => decodeURI(a.getAttribute("src"))), /^\.\.\/mp3\/broadcasts\//);
  assert.match(await page.$eval("#pMeta", (e) => e.textContent), /, part 1 of \d$/);
  assert.deepEqual(page.problems, []);
  await page.close2();
});

test("english home: search works with English and with Greek words", async () => {
  const page = await open("en/index.html");
  let r = await searchFor(page, "genesis");
  assert.match(r.titles[0], /Genesis/);
  assert.match(r.msg, /^Found \d+ broadcasts for “genesis”, most relevant first\.$/);
  r = await searchFor(page, "γενεση");
  assert.match(r.titles[0], /Genesis/);
  r = await searchFor(page, "evolushun");
  assert.ok(r.titles.length > 0);
  await page.close2();
});

test("language button switches between the Greek and English page and keeps the theme", async () => {
  const page = await open("faq.html");
  await page.click("#themeToggle");
  await Promise.all([page.waitForNavigation(), page.click("#langSwitch")]);
  assert.ok(page.url().endsWith("/en/faq.html"));
  assert.equal(await page.evaluate(() => document.documentElement.lang), "en");
  assert.equal(await page.evaluate(() => document.documentElement.getAttribute("data-theme")), "dark");
  assert.equal(await page.$eval("h1", (e) => e.textContent), "Answers to listeners' questions");
  await Promise.all([page.waitForNavigation(), page.click("#langSwitch")]);
  assert.ok(page.url().endsWith("/faq.html") && !page.url().includes("/en/"));
  await page.goto(BASE + "material/2012_11_15.htm", { waitUntil: "load" });
  await Promise.all([page.waitForNavigation(), page.click("#langSwitch")]);
  assert.ok(page.url().endsWith("/en/material/2012_11_15.htm"), "a translated study page opens its English copy");
  assert.equal(await page.evaluate(() => document.documentElement.lang), "en");
  await Promise.all([page.waitForNavigation(), page.click("#langSwitch")]);
  assert.ok(page.url().endsWith("/material/2012_11_15.htm") && !page.url().includes("/en/"));
  await page.close2();
});

test("home: the Broadcasts tab is underlined only once the archive is reached", async () => {
  for (const u of ["index.html", "en/index.html"]) {
    const page = await open(u);
    const cur = () => page.$eval('.nav a[href="#archive"]', (a) => a.getAttribute("aria-current"));
    assert.equal(await cur(), null, u + ": not underlined at the top");
    await page.click(".brand"); await new Promise((r) => setTimeout(r, 400));
    assert.equal(await cur(), null, u + ": not underlined after clicking the logo");
    await page.click('.nav a[href="#archive"]'); await new Promise((r) => setTimeout(r, 1000));
    assert.equal(await cur(), "page", u + ": underlined after clicking Broadcasts");
    await page.evaluate(() => window.scrollTo(0, 0)); await new Promise((r) => setTimeout(r, 300));
    assert.equal(await cur(), null, u + ": cleared again back at the top");
    await page.close2();
  }
});

test("a missing address shows the site's own not-found page, at any folder depth", async () => {
  for (const u of ["no-such-page.html", "material/old/missing.htm"]) {
    const page = await open(u);
    assert.equal(await page.$eval("h1", (e) => e.textContent), "Η σελίδα δεν βρέθηκε");
    assert.equal(await page.evaluate(() => getComputedStyle(document.querySelector(".topbar")).position), "sticky", "styles load from a nested path");
    await Promise.all([page.waitForNavigation(), page.click('a[href="/en/index.html"]')]);
    assert.ok(page.url().endsWith("/en/index.html"));
    await page.close2();
  }
});

test("column page: filter finds articles, links open the newspaper or the PDF", async () => {
  const page = await open("column.html");
  const visible = () => page.$$eval(".refs .ref", (e) => e.filter((x) => !x.hidden).length);
  const all = await visible();
  assert.ok(all > 80, all + " cards");
  await page.type("#filter", "αναστασ");
  const n = await visible();
  assert.ok(n >= 1 && n < all, n + " cards for «αναστασ»");
  const hrefs = await page.$$eval(".refs .ref__title a", (e) => e.map((a) => a.getAttribute("href")));
  assert.ok(hrefs.every((h) => /^https:\/\/www\.christianity\.gr\//.test(h) || /^files\/.+\.pdf$/i.test(h)), "links go to the newspaper or a PDF");
  const en = await open("en/column.html");
  assert.match(await en.$eval(".refs .ref__desc time", (e) => e.textContent), /^[A-Z][a-z]+ \d{4}$/);
  await en.close2();
  await page.close2();
});

test("question form: checks the fields, then opens the e-mail app with the question ready", async () => {
  const page = await open("faq.html");
  await page.click(".ask__submit");
  assert.equal(await page.$eval("#askQuestionError", (e) => e.hidden), false);
  assert.equal(await page.$eval("#askEmailError", (e) => e.hidden), false);
  assert.equal(await page.evaluate(() => document.activeElement.id), "askQuestion", "focus moves to the first problem");
  await page.type("#askQuestion", "Πώς συμβιβάζεται η Μεγάλη Έκρηξη με τη Γένεση;");
  await page.type("#askEmail", "listener@example.com");
  // the browser will not let a test intercept the jump to the e-mail app, so read the link the form recorded
  await page.click(".ask__submit");
  await page.waitForFunction(() => document.querySelector("#askForm").hasAttribute("data-mailto"));
  const href = await page.$eval("#askForm", (f) => f.getAttribute("data-mailto"));
  assert.ok(href && href.startsWith("mailto:science@christianity.gr?"), "mailto link: " + href);
  assert.ok(decodeURIComponent(href).includes("Μεγάλη Έκρηξη") && decodeURIComponent(href).includes("listener@example.com"));
  assert.match(await page.$eval("#askStatus", (e) => e.textContent), /πρόγραμμα e-mail/);
  await page.close2();
});

test("question form: with a form service configured it sends the question and thanks the visitor", async () => {
  const page = await open("en/faq.html");
  await page.evaluate(() => {
    document.querySelector("#askForm").setAttribute("data-endpoint", "https://forms.example/submit");
    window.__sent = null;
    window.fetch = (url, opt) => { window.__sent = { url, body: JSON.parse(opt.body) }; return Promise.resolve({ ok: true }); };
  });
  await page.type("#askQuestion", "How do you reconcile the Big Bang with Genesis?");
  await page.type("#askEmail", "listener@example.com");
  await page.click(".ask__submit");
  await page.waitForFunction(() => /Thank you/.test(document.querySelector("#askStatus").textContent));
  const sent = await page.evaluate(() => window.__sent);
  assert.equal(sent.url, "https://forms.example/submit");
  assert.equal(sent.body.email, "listener@example.com");
  assert.match(sent.body.question, /Big Bang/);
  assert.equal(await page.$eval("#askQuestion", (e) => e.value), "", "form is cleared after sending");
  await page.close2();
});
