/*
 * Minimal static server for local preview and tests, with HTTP Range support
 * (needed for seeking inside mp3s — Python's http.server does not support it).
 *
 *   node tests/server.js [port]      → http://127.0.0.1:8081/
 */
"use strict";
const http = require("http");
const fs = require("fs");
const path = require("path");

const ROOT = path.resolve(__dirname, "..");
const PORT = +process.argv[2] || 8081;
const TYPES = {
  ".html": "text/html; charset=utf-8", ".htm": "text/html; charset=utf-8", ".css": "text/css; charset=utf-8",
  ".js": "text/javascript; charset=utf-8", ".json": "application/json", ".mp3": "audio/mpeg", ".pdf": "application/pdf",
  ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png", ".gif": "image/gif", ".svg": "image/svg+xml",
  ".ico": "image/x-icon", ".txt": "text/plain; charset=utf-8", ".xml": "application/xml; charset=utf-8", ".ppt": "application/vnd.ms-powerpoint", ".pps": "application/vnd.ms-powerpoint",
};

http.createServer((req, res) => {
  let rel;
  try { rel = decodeURIComponent(new URL(req.url, "http://x").pathname); } catch { res.writeHead(400).end(); return; }
  let file = path.normalize(path.join(ROOT, rel));
  if (!file.startsWith(ROOT)) { res.writeHead(403).end(); return; }
  if (fs.existsSync(file) && fs.statSync(file).isDirectory()) file = path.join(file, "index.html");
  fs.stat(file, (err, st) => {
    if (err || !st.isFile()) {
      // like the live server once configured: the site's own "page not found" page, with status 404
      const page = path.join(ROOT, "404.html");
      if (fs.existsSync(page)) { res.writeHead(404, { "Content-Type": TYPES[".html"] }); fs.createReadStream(page).pipe(res); }
      else res.writeHead(404, { "Content-Type": "text/plain" }).end("Not found");
      return;
    }
    const type = TYPES[path.extname(file).toLowerCase()] || "application/octet-stream";
    const headers = { "Content-Type": type, "Accept-Ranges": "bytes", "Cache-Control": "no-cache" };
    const m = /^bytes=(\d*)-(\d*)$/.exec(req.headers.range || "");
    if (m && (m[1] || m[2])) {
      let start = m[1] ? +m[1] : st.size - +m[2], end = m[1] && m[2] ? +m[2] : st.size - 1;
      if (start >= st.size || start > end) { res.writeHead(416, { "Content-Range": `bytes */${st.size}` }).end(); return; }
      end = Math.min(end, st.size - 1);
      res.writeHead(206, { ...headers, "Content-Range": `bytes ${start}-${end}/${st.size}`, "Content-Length": end - start + 1 });
      if (req.method === "HEAD") return res.end();
      fs.createReadStream(file, { start, end }).pipe(res);
    } else {
      res.writeHead(200, { ...headers, "Content-Length": st.size });
      if (req.method === "HEAD") return res.end();
      fs.createReadStream(file).pipe(res);
    }
  });
}).listen(PORT, "127.0.0.1", () => console.log(`Serving ${ROOT} at http://127.0.0.1:${PORT}/`));
