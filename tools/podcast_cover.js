/* Saves tools/podcast-cover.html as pictures/podcast-cover.jpg (3000×3000, what Spotify and Apple ask for).
 *
 *   node tools/podcast_cover.js
 *
 * Needs puppeteer-core (as the browser tests do) and Chrome or Edge; set CHROME to the browser's path if
 * it is not found. Only needed when the cover's design changes. */
const fs = require("fs"), path = require("path");
const puppeteer = require("puppeteer-core");
const ROOT = path.resolve(__dirname, "..");
const CHROME = process.env.CHROME || [
  "C:/Program Files/Google/Chrome/Application/chrome.exe", "C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe",
  "/usr/bin/google-chrome", "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
].find((p) => fs.existsSync(p));

(async () => {
  const browser = await puppeteer.launch({ executablePath: CHROME });
  const page = await browser.newPage();
  await page.setViewport({ width: 1000, height: 1000, deviceScaleFactor: 3 });
  await page.goto("file://" + path.join(ROOT, "tools", "podcast-cover.html").replace(/\\/g, "/"), { waitUntil: "networkidle0" });
  await page.evaluate(() => document.fonts.ready);
  const out = path.join(ROOT, "pictures", "podcast-cover.jpg");
  await (await page.$("#cover")).screenshot({ path: out, type: "jpeg", quality: 90 });
  await browser.close();
  console.log("podcast cover: " + path.relative(ROOT, out) + " (" + Math.round(fs.statSync(out).size / 1024) + " KB)");
})();
