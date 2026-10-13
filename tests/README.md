# Tests

Two sets of automatic tests. They need [Node.js](https://nodejs.org) 18+ and Python (for `tools/stamp.py`).

## 1. Static tests (no browser), 53 tests
Broadcast data and topics, functions of `js/app.js`, the HTML of every page, every internal link, CSS,
the English pages and translations, «Σχετικά» (Related), the site search index, the podcast feed, `tools/stamp.py`.
```
node --test tests/static.test.js
```

## 2. Browser tests, 58 tests
They open the pages in headless Chrome or Edge: search, player, keep-playing-while-browsing, topics,
countdown, theme, menu, filters, share and lock-screen controls, phone layout.
```
npm install --prefix tests puppeteer-core     # once
node tests/server.js                           # in a separate window (serves the folder at :8081)
node --test tests/browser.test.js
```
`tests/server.js` supports HTTP Range requests, which jumping within an mp3 needs
(`python -m http.server` does not, so «Συνέχεια» (resume) does not work with it).

## After going live
```
node tests/live-check.js
```
Checks that every page on the live site is the new version and that all files and mp3s load.

## Known gap
The broadcast of 7 March 2013 («Νηστεία», *Fasting*) has no mp3s: they are missing on the old server too.
The tests list them in `KNOWN_MISSING_MP3`. If the files turn up, add them to
`mp3/broadcasts/Season_06/2013_03_07/` and remove them from that list.

The `tests/` and `tools/` folders do not need to be uploaded to the web host.
