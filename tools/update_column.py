"""The team's column in the newspaper «Χριστιανισμός»: keep the list on the site up to date.

    python tools/update_column.py          fetch new articles, rebuild column.html, the block in articles.html,
                                           and the "latest column" box on the home page
    python tools/update_column.py --offline    rebuild from data/column.json without fetching

Only titles, dates and links are stored; reading happens on the newspaper's website (christianity.gr).
Older columns that were published in the newspaper and are kept as PDFs on this site are added too
(articles whose description says "από την εφημερίδα «Χριστιανισμός»").
Afterwards run  python tools/build_all.py  (English page, search tags, version stamps).
"""
import html, json, os, re, subprocess, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data", "column.json")
LIST_URL = "https://www.christianity.gr/ephemerida/christianismos-kai-episteme"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0 Safari/537.36"

# Pages in the newspaper's category that are not column articles (radio, churches, about pages).
EXCLUDE = {1620, 1621, 1622, 1663, 2129, 2130, 2143, 2144, 2145, 2146, 2147, 2148, 2149, 2150, 2151, 2174}
# Probably not part of the column (published outside the monthly rhythm); left out until confirmed.
UNSURE = {1688, 2239, 2240, 2241}
CONFIRMED = set()   # (kept for compatibility; the RSS feed contains only column articles)

MONTHS_GEN = ["Ιανουαρίου", "Φεβρουαρίου", "Μαρτίου", "Απριλίου", "Μαΐου", "Ιουνίου", "Ιουλίου",
              "Αυγούστου", "Σεπτεμβρίου", "Οκτωβρίου", "Νοεμβρίου", "Δεκεμβρίου"]
MONTHS_NOM = ["Ιανουάριος", "Φεβρουάριος", "Μάρτιος", "Απρίλιος", "Μάιος", "Ιούνιος", "Ιούλιος",
              "Αύγουστος", "Σεπτέμβριος", "Οκτώβριος", "Νοέμβριος", "Δεκέμβριος"]


def get(url):
    r = subprocess.run(["curl", "-sfL", "--retry", "2", "-A", UA, url], capture_output=True, timeout=120)
    if r.returncode:
        raise SystemExit("Could not read %s (curl %d). Is the internet connection working?" % (url, r.returncode))
    return r.stdout.decode("utf-8", "replace")


# ---------------------------------------------------------------- 1. newspaper articles (online)
def fetch_online(known, review):
    """Every article of the column, from the newspaper's own RSS feed of the category.

    The feed lists all articles (8 per page) and nothing else, unlike the web pages, whose
    layout hides half of each page's articles and also carries menu links (radio, churches…).
    Only titles, dates, links and preview pictures are kept.
    """
    found, start = {}, 0
    while start <= 2000:
        feed = get(LIST_URL + "?format=feed&type=rss&start=%d" % start)
        ids = {int(i): u for u, i in re.findall(r"<link>(https://www\.christianity\.gr/ephemerida/christianismos-kai-episteme/(\d+)-[^<]+)</link>", feed)}
        if not ids or set(ids) <= set(found):
            break
        found.update(ids)
        start += 8
    if len(found) < 50:
        raise SystemExit("The column's RSS feed returned only %d articles; not updating (has the newspaper's site changed?)" % len(found))
    items = {e["id"]: e for e in known if e["id"] in found or e["id"] not in EXCLUDE | UNSURE}
    for i, url in sorted(found.items()):
        if i in EXCLUDE or i in UNSURE or i in items:
            continue
        s = get(url)
        t = re.search(r'property="og:title" content="([^"]*)"', s)
        d = re.search(r'article:published_time" content="([^"]*)"', s)
        if not t or not d:
            print("  skipped (no title/date):", url)
            continue
        title = re.sub(r"\s+", " ", html.unescape(t.group(1)).replace(" - Ραδιόφωνο Χριστιανισμός", "")).strip()
        items[i] = {"id": i, "title": title, "date": d.group(1)[:10], "url": url, "image": preview_image(s)}
        print("  new:", items[i]["date"], title)
    for i in EXCLUDE | UNSURE:
        items.pop(i, None)
    # articles listed before pictures were collected: read just their preview picture
    for e in items.values():
        if "image" not in e:
            e["image"] = preview_image(get(e["url"]))
    return sorted(items.values(), key=lambda e: (e["date"], e["id"]), reverse=True)


def preview_image(page):
    """The article's own preview picture on christianity.gr (linked, not copied); "" if none."""
    m = re.search(r'property="og:image" content="([^"]+)"', page)
    url = html.unescape(m.group(1)) if m else ""
    return url if re.match(r"https://www\.christianity\.gr/images/", url) else ""


# ---------------------------------------------------------------- 2. older columns kept as PDFs on this site
def local_archive():
    out, seen = [], set()
    import glob
    for f in sorted(glob.glob(os.path.join(ROOT, "articles", "*.htm"))):
        s = open(f, encoding="utf-8").read()
        for li in re.findall(r'(?s)<li class="ref">(.*?)</li>', s):
            desc = re.search(r'(?s)<p class="ref__desc">(.*?)</p>', li)
            text = html.unescape(re.sub(r"<[^>]+>", "", desc.group(1))) if desc else ""
            if not re.search(r"από την εφημερίδα\s*[\"«]Χριστιανισμός", text, re.I):
                continue
            title_html = re.search(r'(?s)<p class="ref__title">(.*?)</p>', li).group(1)
            href = html.unescape(re.search(r'href="([^"]+)"', title_html).group(1))   # "&amp;" in file names → "&"
            path = os.path.normpath(os.path.join("articles", href)).replace("\\", "/")
            if path in seen:
                continue
            seen.add(path)
            title = re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", title_html))).strip()
            title = re.sub(r"\s*(\[\d+\]\s*)+$", "", title).strip(" -–")
            m = re.search(r"(19|20)\d\d_(0[1-9]|1[0-2])", os.path.basename(path))
            author = re.search(r"(Αλέκου Περάκη|Α\. Περάκη)", text)
            out.append({"title": title, "path": path, "date": m.group(0).replace("_", "-") + "-01" if m else "",
                        "author": "Αλέκος Περάκης" if author else ""})
    return sorted(out, key=lambda e: (e["date"] or "0000", e["title"]), reverse=True)


# ---------------------------------------------------------------- 3. pages
DOC = '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8z"/><path d="M14 3v5h5M9 13h6M9 17h4"/></svg>'
NEWS = '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 5.5A1.5 1.5 0 0 1 5.5 4h11A1.5 1.5 0 0 1 18 5.5V18a2 2 0 0 0 2 2H6a2 2 0 0 1-2-2z"/><path d="M18 8h1.5A1.5 1.5 0 0 1 21 9.5V18a2 2 0 0 1-2 2M8 8h6M8 12h6M8 16h4"/></svg>'


def month_label(date):
    if not date:
        return ""
    y, m = int(date[:4]), int(date[5:7])
    return "%s %d" % (MONTHS_NOM[m - 1], y)


def card(e, prefix=""):
    online = "url" in e
    href = e["url"] if online else prefix + e["path"]
    ext = ' target="_blank" rel="noopener"' if online else ""
    meta = ('<time datetime="%s">%s</time>' % (e["date"][:7], month_label(e["date"]))) if e["date"] else "Χωρίς ημερομηνία"
    if e.get("author"):
        meta += " · " + html.escape(e["author"], quote=False)
    if online and e.get("image"):
        # the article's own picture, shown from christianity.gr (decorative: the title says what it is)
        visual = '<span class="ref__thumb"><img src="%s" alt="" loading="lazy" decoding="async" width="96" height="72"></span>' % html.escape(e["image"], quote=True)
    else:
        visual = '<span class="ref__icon ref__icon--%s">%s</span>' % ("web" if online else "pdf", NEWS if online else DOC)
    return ('          <li class="ref%s" data-filter>\n' % (" ref--thumb" if "ref__thumb" in visual else "") +
            '            ' + visual + '\n'
            '            <div class="ref__body">\n'
            '              <p class="ref__title" translate="no"><a href="%s"%s>%s</a></p>\n'
            '              <p class="ref__desc" translate="no">%s</p>\n'
            '            </div>\n'
            '            <span class="ref__badge">%s</span>\n'
            '          </li>') % (html.escape(href, quote=True), ext, html.escape(e["title"], quote=False), meta,
                                   "christianity.gr" if online else "PDF")


def column_page(online, archive):
    shell = open(os.path.join(ROOT, "articles.html"), encoding="utf-8").read()
    shell = re.sub(r"\s*<!-- column -->.*?<!-- /column -->", "", shell, flags=re.S)
    shell = re.sub(r"\s*<!-- seo -->.*?<!-- /seo -->", "", shell, flags=re.S)
    shell = re.sub(r"(?s)<title>.*?</title>", "<title>Η στήλη μας στην εφημερίδα «Χριστιανισμός» — Χριστιανισμός & Επιστήμη</title>", shell)
    shell = re.sub(r'<meta name="description" content="[^"]*">',
                   '<meta name="description" content="Όλα τα άρθρα της ομάδας «Χριστιανισμός &amp; Επιστήμη» στη μηνιαία στήλη της εφημερίδας «Χριστιανισμός».">', shell)
    shell = re.sub(r'(?s)<section class="pagehead">.*?</section>', '''<section class="pagehead">
      <div class="wrap">
        <p class="pagehead__kicker">Άρθρα</p>
        <h1 class="pagehead__title">Η στήλη μας στην εφημερίδα «Χριστιανισμός»</h1>
        <p class="pagehead__lede">Τα άρθρα της ομάδας «Χριστιανισμός &amp; Επιστήμη» στη μηνιαία στήλη της εφημερίδας. Τα νεότερα διαβάζονται στον ιστότοπο της εφημερίδας, τα παλαιότερα ως PDF.</p>
      </div>
    </section>''', shell)
    groups, cur = [], None
    for e in online:
        y = e["date"][:4]
        if y != cur:
            groups.append((y, [])); cur = y
        groups[-1][1].append(card(e))
    body = ['''        <div class="page__tools">
          <p class="page__count">%d άρθρα</p>
          <label class="search">
            <span class="sr">Αναζήτηση άρθρου…</span>
            <svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="11" cy="11" r="6.5"/><path d="m16 16 4.5 4.5"/></svg>
            <input id="filter" type="search" placeholder="Αναζήτηση άρθρου…" autocomplete="off">
          </label>
        </div>
        <article class="prose prose--wide reflist">''' % (len(online) + len(archive))]
    for y, cards in groups:
        body.append('        <h2 class="refs__year">%s</h2>\n        <ul class="refs">\n%s\n        </ul>' % (y, "\n".join(cards)))
    if archive:
        body.append('        <h2 class="refs__year">Παλαιότερα άρθρα της στήλης (PDF)</h2>\n        <ul class="refs">\n%s\n        </ul>'
                    % "\n".join(card(e) for e in archive))
    body.append('''        </article>
        <p class="empty" id="filterEmpty" hidden>Δεν βρέθηκε άρθρο. Δοκιμάστε άλλη λέξη.</p>
        <p class="note"><a href="%s" target="_blank" rel="noopener">Η στήλη στον ιστότοπο της εφημερίδας «Χριστιανισμός»</a></p>''' % LIST_URL)
    page = re.sub(r'(?s)(<div class="page">\s*<div class="wrap">).*?(</div>\s*</div>\s*</main>)',
                  lambda m: m.group(1) + "\n" + "\n".join(body) + "\n      " + m.group(2), shell)
    open(os.path.join(ROOT, "column.html"), "w", encoding="utf-8", newline="\n").write(page)


def articles_block(online, total):
    path = os.path.join(ROOT, "articles.html")
    src = open(path, encoding="utf-8").read()
    src = re.sub(r"\s*<!-- column -->.*?<!-- /column -->", "", src, flags=re.S)
    block = '''        <!-- column -->
        <section class="colblock" aria-labelledby="colblockTitle">
          <div class="colblock__head">
            <h2 class="group__title" id="colblockTitle">Η στήλη μας στην εφημερίδα «Χριστιανισμός»</h2>
            <a class="colblock__all" href="column.html">Όλα τα άρθρα της στήλης (%d) →</a>
          </div>
          <ul class="refs">
%s
          </ul>
        </section>
        <h2 class="group__title">Άρθρα ανά κατηγορία</h2>
        <!-- /column -->''' % (total, "\n".join(card(e) for e in online[:4]).replace(" data-filter", ""))
    src = src.replace('<div class="page__tools">', block.strip() + '\n        <div class="page__tools">', 1)
    open(path, "w", encoding="utf-8", newline="\n").write(src)


def latest_box(e):
    """SITE_CONFIG.latestColumn in js/broadcasts.js → the home page box."""
    path = os.path.join(ROOT, "js", "broadcasts.js")
    s = open(path, encoding="utf-8").read()
    y, m = int(e["date"][:4]), int(e["date"][5:7])
    new = ('latestColumn: {\n      month: "%s %d",\n      title: %s,\n      url: "%s"\n    }'
           % (MONTHS_GEN[m - 1], y, json.dumps(e["title"], ensure_ascii=False), e["url"]))
    s2 = re.sub(r"latestColumn: \{.*?\n    \}", lambda _: new, s, count=1, flags=re.S)
    if s2 != s:
        open(path, "w", encoding="utf-8", newline="\n").write(s2)
        print("home page box: latest column is now", e["title"])


def main():
    os.makedirs(os.path.dirname(DATA), exist_ok=True)
    old = json.load(open(DATA, encoding="utf-8")) if os.path.exists(DATA) else {}
    known = old.get("online", [])
    review = [r for r in old.get("review", []) if r["id"] not in EXCLUDE | UNSURE | CONFIRMED]
    online = known if "--offline" in sys.argv else fetch_online(known, review)
    archive = local_archive()
    json.dump({"online": online, "archive": archive, "review": review},
              open(DATA, "w", encoding="utf-8", newline="\n"), ensure_ascii=False, indent=1)
    if review:
        print("NEEDS REVIEW (not added): " + "; ".join("%s %s" % (r["id"], r["title"]) for r in review))
    column_page(online, archive)
    articles_block(online, len(online) + len(archive))
    if online:
        latest_box(online[0])
    print("column: %d newspaper articles online, %d older ones as PDF; left out as unsure: %s"
          % (len(online), len(archive), ", ".join(map(str, sorted(UNSURE)))))


if __name__ == "__main__":
    main()
