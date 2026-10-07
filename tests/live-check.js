/*
 * After-upload check: does the live site match this folder, and does everything load?
 *
 *   node tests/live-check.js                         checks https://www.christianity-science.gr/
 *   node tests/live-check.js http://127.0.0.1:8081/  checks another address (e.g. the local preview)
 *   node tests/live-check.js --all-mp3               also checks every part of every broadcast (1,419 files)
 *
 * It asks like a browser does (the server refuses requests that do not look like one), and reports:
 *   - pages that are missing, or still the OLD version (their ?v= stamps differ from this folder)
 *   - links, images, PDFs and mp3s that do not load
 *   - the "page not found" page, sitemap.xml and robots.txt
 *   - (for information) how http:// and the address without www behave
 * Exit code 1 if anything is wrong.
 */
"use strict";
const fs = require("fs");
const path = require("path");
const vm = require("vm");

const ROOT = path.resolve(__dirname, "..");
const args = process.argv.slice(2);
const BASE = (args.find((a) => /^https?:\/\//.test(a)) || "https://www.christianity-science.gr/").replace(/\/?$/, "/");
const ALL_MP3 = args.includes("--all-mp3");
const HEADERS = {
  "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0 Safari/537.36",
  "Referer": BASE,
};
const problems = [], notes = [];

function localPages() {
  const out = [];
  (function walk(dir) {
    for (const f of fs.readdirSync(dir, { withFileTypes: true })) {
      if (dir === ROOT && ["mp3", "pictures", "tests", "tools", "translation", "docs", "node_modules", ".git"].includes(f.name)) continue;
      const p = path.join(dir, f.name);
      if (f.isDirectory()) walk(p);
      else if (/\.html?$/.test(f.name)) out.push(path.relative(ROOT, p).replace(/\\/g, "/"));
    }
  })(ROOT);
  return out;
}

async function get(url, { range = false, redirect = "follow" } = {}) {
  for (let attempt = 0; attempt < 3; attempt++) {
    try {
      const r = await fetch(url, { headers: range ? { ...HEADERS, Range: "bytes=0-0" } : HEADERS, redirect });
      const body = range || redirect === "manual" ? "" : await r.text();
      return { status: r.status, body, location: r.headers.get("location") || "" };
    } catch (e) {
      if (attempt === 2) return { status: "network error: " + (e.cause?.code || e.message), body: "" };
      await new Promise((ok) => setTimeout(ok, 1000 * (attempt + 1)));
    }
  }
}

async function pool(items, n, fn) {
  let i = 0;
  await Promise.all(Array.from({ length: n }, async () => { while (i < items.length) await fn(items[i++]); }));
}

const stamps = (s) => [...s.matchAll(/(css\/site\.css|js\/[\w-]+\.js)\?v=([0-9a-f]+)/g)].map((m) => m[1] + "=" + m[2]).sort().join(" ");

(async () => {
  console.log("Checking " + BASE + "\n");
  const pages = localPages();
  const assets = new Set();

  // 1. every page exists and is the NEW version
  let ok = 0;
  await pool(pages, 6, async (p) => {
    const local = fs.readFileSync(path.join(ROOT, p), "utf8");
    const r = await get(BASE + encodeURI(p));
    if (r.status !== 200) return problems.push(`page ${p}: HTTP ${r.status}`);
    if (stamps(r.body) !== stamps(local)) return problems.push(`page ${p}: the server has a different version (upload it again)`);
    ok++;
    for (const m of local.matchAll(/(?:href|src)="([^"]+)"/g)) {
      // decode entities (&amp; &#x27; …) and %20 first: encodeURI() below must not encode them twice
      let u = m[1].replace(/&#x([0-9a-f]+);/gi, (_, h) => String.fromCharCode(parseInt(h, 16)))
        .replace(/&#(\d+);/g, (_, n) => String.fromCharCode(+n)).replace(/&amp;/g, "&").split("#")[0];
      try { u = decodeURI(u); } catch (e) { /* leave as is */ }
      if (!u) continue;
      if (/^([a-z]+:|\/\/)/i.test(u)) continue;
      u = u.startsWith("/") ? u.slice(1) : path.posix.normalize(path.posix.join(path.posix.dirname(p), u));
      if (!/\.html?(\?|$)/.test(u)) assets.add(u.split("?")[0]);
    }
  });
  console.log(`pages: ${ok}/${pages.length} up to date`);

  // 2. every linked file (CSS, JS, images, PDFs, mp3) loads
  const files = [...assets].filter((u) => ALL_MP3 || !/\.mp3$/i.test(u) || /polls|interviews/.test(u));
  let fine = 0;
  await pool(files, 6, async (u) => {
    const r = await get(BASE + encodeURI(u), { range: true });
    if (r.status === 200 || r.status === 206) fine++;
    else problems.push(`file ${u}: HTTP ${r.status}`);
  });
  console.log(`linked files: ${fine}/${files.length} load`);

  // 3. broadcast audio: part 1 of every broadcast (or every part with --all-mp3)
  const ctx = { window: {} };
  vm.runInNewContext(fs.readFileSync(path.join(ROOT, "js/broadcasts.js"), "utf8"), ctx);
  const cfg = ctx.window.SITE_CONFIG, mp3 = [];
  for (const s of ctx.window.BROADCASTS) for (const e of s.episodes) {
    const id = e.date.replace(/-/g, "_");
    for (let n = 1; n <= (ALL_MP3 ? e.parts : 1); n++)
      mp3.push(e.files ? e.files[n - 1] : cfg.mp3Base + "Season_" + (s.n < 10 ? "0" : "") + s.n + "/" + id + "/" + (e.cs ? "CS_" : "") + id + "_(" + n + ")_" + e.slug + ".mp3");
  }
  const known = [1, 2, 3, 4].map((n) => `mp3/broadcasts/Season_06/2013_03_07/CS_2013_03_07_(${n})_Nisteia.mp3`);   // missing on the old server too
  let playable = 0;
  await pool(mp3, 6, async (u) => {
    const r = await get(BASE + encodeURI(u), { range: true });
    if (r.status === 200 || r.status === 206) playable++;
    else if (known.includes(u)) notes.push(`known gap: ${u}`);
    else problems.push(`audio ${u}: HTTP ${r.status}`);
  });
  console.log(`broadcast audio: ${playable}/${mp3.length} ${ALL_MP3 ? "parts" : "broadcasts (part 1)"} play`);

  // 4. not-found page, sitemap, robots
  const nf = await get(BASE + "this-page-does-not-exist-" + Date.now() + ".html");
  if (nf.status !== 404) problems.push(`missing pages answer HTTP ${nf.status} instead of 404`);
  else if (!/Η σελίδα δεν βρέθηκε/.test(nf.body)) notes.push("missing pages give 404, but not with the site's own 404.html (server setting)");
  for (const f of ["sitemap.xml", "robots.txt", "pictures/share.png"]) {
    const r = await get(BASE + f, { range: f.endsWith(".png") });
    if (r.status !== 200 && r.status !== 206) problems.push(`${f}: HTTP ${r.status}`);
  }

  // 5. for information: http:// and the other host name
  const u = new URL(BASE);
  if (u.protocol === "https:") {
    const h = await get("http://" + u.host + "/", { redirect: "manual" });
    notes.push(`http://${u.host}/ → ${h.status}${h.location ? " " + h.location : ""}` + (String(h.status).startsWith("30") ? "" : "  (should redirect to https)"));
    const other = u.host.startsWith("www.") ? u.host.slice(4) : "www." + u.host;
    const o = await get("https://" + other + "/", { redirect: "manual" });
    notes.push(`https://${other}/ → ${o.status}${o.location ? " " + o.location : ""}` + (String(o.status).startsWith("30") ? "" : "  (should redirect to " + BASE + ")"));
  }

  console.log("");
  if (notes.length) console.log("Notes:\n  " + notes.join("\n  ") + "\n");
  if (problems.length) {
    console.log(`PROBLEMS (${problems.length}):\n  ` + problems.slice(0, 60).join("\n  ") + (problems.length > 60 ? "\n  …" : ""));
    process.exit(1);
  }
  console.log("Everything checked is in place.");
})();
