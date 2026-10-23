/*
 * The upload page in a real browser (headless Chrome), with PHP's built-in web server.
 *
 * Needs php, ffmpeg, Chrome or Edge, and puppeteer-core (npm install --prefix tests puppeteer-core).
 * Run:   node --test tests/admin_browser.test.js        (skipped when something is missing)
 *
 * Signs in with a password and an authenticator code, chooses three mp3s, sends them and checks that
 * they arrive complete in the inbox: also when the server only takes small pieces (the page must make
 * its pieces smaller by itself) and when the connection drops in the middle (the page must go on).
 */
"use strict";
const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("fs");
const os = require("os");
const path = require("path");
const crypto = require("crypto");
const net = require("net");
const { spawn, execFileSync } = require("child_process");

const ROOT = path.resolve(__dirname, "..");
const TEST_DATE = "2026-10-15";              // the made-up broadcast the tests send (TEST_DATE in tests/helpers.py)
const which = (cmd) => { try { execFileSync(process.platform === "win32" ? "where" : "which", [cmd], { stdio: "ignore" }); return true; } catch { return false; } };
const CHROME = process.env.CHROME || ["/usr/bin/google-chrome", "C:/Program Files/Google/Chrome/Application/chrome.exe",
  "C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe"].find((p) => fs.existsSync(p));
let puppeteer = null;
try { puppeteer = require("puppeteer-core"); } catch { /* not installed */ }
const missing = !which("php") ? "php" : !which("ffmpeg") ? "ffmpeg" : !CHROME ? "Chrome" : !puppeteer ? "puppeteer-core" : null;

const SECRET = "test-upload-page";
const KEY = "device-key-for-the-browser-test-0123456789";
const TOTP = "GEZDGNBVGY3TQOJQGEZDGNBVGY3TQOJQ";
const PASSWORD = "correct horse battery staple";

function totp(secret) {
  const alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZ234567";
  let bits = "";
  for (const c of secret) bits += alphabet.indexOf(c).toString(2).padStart(5, "0");
  const key = Buffer.from(bits.match(/.{8}/g).map((b) => parseInt(b, 2)));
  const counter = Buffer.alloc(8);
  counter.writeBigUInt64BE(BigInt(Math.floor(Date.now() / 30000)));
  const h = crypto.createHmac("sha1", key).update(counter).digest();
  const o = h[19] & 15;
  return String(((h.readUInt32BE(o) & 0x7fffffff) % 1000000)).padStart(6, "0");
}

function freePort() {
  return new Promise((ok) => { const s = net.createServer().listen(0, "127.0.0.1", () => { const p = s.address().port; s.close(() => ok(p)); }); });
}

async function startServer(env) {
  const tmp = fs.mkdtempSync(path.join(os.tmpdir(), "cs-admin-browser-"));
  const site = path.join(tmp, "site"), priv = path.join(tmp, "private");
  // the site as it was before TEST_DATE, whose broadcast the tests send (as copy_site_data in tests/helpers.py)
  const before = new RegExp(`^\\s*(ep\\(|)"${TEST_DATE}"[,:].*\\n`, "m");
  for (const rel of ["js/broadcasts.js", "js/broadcasts-en.js", "js/tags.js", "404.html"]) {
    fs.mkdirSync(path.dirname(path.join(site, rel)), { recursive: true });
    fs.writeFileSync(path.join(site, rel), fs.readFileSync(path.join(ROOT, rel), "utf8").replace(before, ""));
  }
  fs.cpSync(path.join(ROOT, "admin"), path.join(site, SECRET), { recursive: true });
  fs.mkdirSync(priv);
  const salt = crypto.randomBytes(16);
  const hash = crypto.pbkdf2Sync(PASSWORD, salt, 600000, 32, "sha256");
  fs.writeFileSync(path.join(priv, "config.php"), "<?php return ['device_key' => '" + KEY + "', 'users' => ['maria' => " +
    "['name' => 'Μαρία', 'email' => '', 'password' => 'pbkdf2-sha256$600000$" + salt.toString("base64") + "$" +
    hash.toString("base64") + "', 'totp' => '" + TOTP + "']]];\n");
  const port = await freePort();
  const php = spawn("php", ["-S", "127.0.0.1:" + port, "-t", site], { env: { ...process.env, CS_PRIVATE_DIR: priv, CS_SHOW_ERRORS: "1", ...env }, stdio: "ignore" });
  for (let i = 0; i < 50; i++) {
    const up = await new Promise((ok) => { const c = net.connect(port, "127.0.0.1", () => { c.end(); ok(true); }).on("error", () => ok(false)); });
    if (up) break;
    await new Promise((r) => setTimeout(r, 100));
  }
  return { tmp, priv, base: "http://127.0.0.1:" + port + "/" + SECRET + "/", stop: () => { php.kill(); fs.rmSync(tmp, { recursive: true, force: true }); } };
}

function makeMp3s(dir) {
  const files = [];
  for (const [i, f] of [[1, 300], [2, 400], [3, 500]].entries()) {
    const p = path.join(dir, `ekpompi-(${f[0]}).mp3`);
    // ~1.2 MB each: bigger than the small pieces some servers take
    execFileSync("ffmpeg", ["-v", "error", "-y", "-f", "lavfi", "-i", `sine=frequency=${f[1]}:duration=61`, "-b:a", "160k", p]);
    files.push(p);
  }
  return files;
}

const sha = (p) => crypto.createHash("sha256").update(fs.readFileSync(p)).digest("hex");

async function signIn(browser, srv) {
  const ctx = await browser.createBrowserContext();
  const page = await ctx.newPage();
  page.problems = [];
  page.on("pageerror", (e) => page.problems.push("JS error: " + e.message));
  page.on("console", (m) => { if (m.type() === "error" && !/ytimg|Failed to load resource/.test(m.text())) page.problems.push("console: " + m.text()); });
  await page.goto(srv.base + "?k=" + KEY, { waitUntil: "load" });
  await page.type("#lName", "maria");
  await page.type("#lPass", PASSWORD);
  await page.type("#lCode", totp(TOTP));
  await Promise.all([page.waitForNavigation({ waitUntil: "load" }), page.click("#loginForm button[type=submit]")]);
  await page.waitForSelector("#nTags .chip");
  return page;
}

async function sendBroadcast(page, files, date) {
  await page.$eval("#nDate", (el, d) => { el.value = d; el.dispatchEvent(new Event("change")); }, date);
  await page.type("#nTitle", "Δοκιμή από τον browser");
  await (await page.$("#nFiles")).uploadFile(...files.slice().reverse());   // chosen in any order: sorted by name
  await page.waitForFunction(() => document.querySelectorAll("#fileList .file").length === 3);
  const order = await page.$$eval("#fileList .file span", (s) => s.map((x) => x.textContent.split(" · ")[0]));
  assert.deepEqual(order, files.map((f) => path.basename(f)));
  await page.click("#send");
  await page.waitForFunction(() => { const m = document.getElementById("nMsg"); return !m.hidden && /ok|bad/.test(m.className); }, { timeout: 120000 });
  return page.$eval("#nMsg", (m) => ({ cls: m.className, text: m.textContent }));
}

function inboxRequest(srv) {
  const dir = path.join(srv.priv, "inbox");
  const ids = fs.readdirSync(dir).filter((d) => !d.startsWith("."));
  assert.equal(ids.length, 1, "one request in the inbox");
  return { dir: path.join(dir, ids[0]), req: JSON.parse(fs.readFileSync(path.join(dir, ids[0], "request.json"), "utf8")) };
}

test("upload page in a browser", missing ? { skip: "needs " + missing } : {}, async (t) => {
  const browser = await puppeteer.launch({ executablePath: CHROME, headless: true });
  const work = fs.mkdtempSync(path.join(os.tmpdir(), "cs-mp3-"));
  const files = makeMp3s(work);
  t.after(async () => { await browser.close(); fs.rmSync(work, { recursive: true, force: true }); });

  await t.test("three recordings arrive complete, in order", async () => {
    const srv = await startServer({});
    try {
      const page = await signIn(browser, srv);
      const msg = await sendBroadcast(page, files, TEST_DATE);
      assert.match(msg.cls, /ok/, msg.text);
      const { dir, req } = inboxRequest(srv);
      assert.equal(req.date, TEST_DATE);
      assert.deepEqual(req.files.map((f) => f.original), files.map((f) => path.basename(f)));
      req.files.forEach((f, i) => assert.equal(sha(path.join(dir, f.name)), sha(files[i])));
      assert.deepEqual(page.problems, []);
    } finally { srv.stop(); }
  });

  await t.test("a server that only takes small pieces: the page makes them smaller", async () => {
    const srv = await startServer({ CS_MAX_PIECE_FOR_TESTS: String(400 * 1024) });
    try {
      const page = await signIn(browser, srv);
      const msg = await sendBroadcast(page, files, TEST_DATE);
      assert.match(msg.cls, /ok/, msg.text);
      const { dir, req } = inboxRequest(srv);
      req.files.forEach((f, i) => assert.equal(sha(path.join(dir, f.name)), sha(files[i])));
    } finally { srv.stop(); }
  });

  await t.test("the connection drops twice in the middle: the upload goes on", async () => {
    const srv = await startServer({});
    try {
      const page = await signIn(browser, srv);
      await page.setRequestInterception(true);
      let pieces = 0;
      page.on("request", (r) => {
        if (r.url().includes("a=piece") && r.method() === "POST" && !r.url().includes("offset=-1")) {
          pieces++;
          if (pieces === 2 || pieces === 3) return r.abort("connectionreset");
        }
        r.continue();
      });
      const msg = await sendBroadcast(page, files, TEST_DATE);
      assert.match(msg.cls, /ok/, msg.text);
      const { dir, req } = inboxRequest(srv);
      req.files.forEach((f, i) => assert.equal(sha(path.join(dir, f.name)), sha(files[i])));
    } finally { srv.stop(); }
  });

  await t.test("pieces go as text, and one refused by the host's filter (nginx 403) is sent again", async () => {
    const srv = await startServer({});
    try {
      const page = await signIn(browser, srv);
      await page.setRequestInterception(true);
      let pieces = 0, asText = 0;
      page.on("request", (r) => {
        if (r.url().includes("a=piece") && r.method() === "POST" && !r.url().includes("offset=-1")) {
          pieces++;
          if (r.url().includes("enc=b64")) asText++;
          if (pieces === 2) return r.respond({ status: 403, contentType: "text/html", body: "<html><center><h1>403 Forbidden</h1></center><hr><center>nginx</center></html>" });
        }
        r.continue();
      });
      const msg = await sendBroadcast(page, files, TEST_DATE);
      assert.match(msg.cls, /ok/, msg.text);
      assert.equal(asText, pieces, "every piece goes as text");
      const { dir, req } = inboxRequest(srv);
      req.files.forEach((f, i) => assert.equal(sha(path.join(dir, f.name)), sha(files[i])));
    } finally { srv.stop(); }
  });

  await t.test("a date already on the site: warned, and sending is refused unless replacing", async () => {
    const srv = await startServer({});
    try {
      const page = await signIn(browser, srv);
      await page.$eval("#nDate", (el) => { el.value = "2026-10-01"; el.dispatchEvent(new Event("change")); });
      assert.match(await page.$eval("#nExists", (m) => (m.hidden ? "" : m.textContent)), /υπάρχει ήδη/);
      assert.equal(await page.$eval("#nReplaceBox", (b) => b.hidden), false);
      await page.type("#nTitle", "Ξανά");
      await (await page.$("#nFiles")).uploadFile(files[0]);
      await page.click("#send");
      assert.match(await page.$eval("#nMsg", (m) => m.textContent), /Αντικατάσταση/);
      const inbox = path.join(srv.priv, "inbox");
      assert.deepEqual(fs.existsSync(inbox) ? fs.readdirSync(inbox).filter((d) => !d.startsWith(".")) : [], []);
    } finally { srv.stop(); }
  });
});
