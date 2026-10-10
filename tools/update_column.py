"""The team's column in the newspaper «Χριστιανισμός»: keep the list on the site up to date.

    python tools/update_column.py          fetch new articles, rebuild column.html, the block in articles.html,
                                           and the "latest column" box on the home page
    python tools/update_column.py --offline    rebuild from data/column.json without fetching

Every article is kept on this site: its text goes into data/column.json and becomes a page
column/<id>.htm, and its pictures are copied into pictures/column/. Nothing links to the newspaper's
website; each page names the newspaper and the month in plain text.
Older columns that were published in the newspaper and are kept as PDFs on this site are added too
(articles whose description says "από την εφημερίδα «Χριστιανισμός»").
Afterwards run  python tools/build_all.py  (English pages, search tags, version stamps).

English: each article's translation is translation/column/<id>.html (see tools/build_en.py).
A new article appears in Greek on the English site until it is translated;
python tools/build_en.py --column-todo  lists the Greek still to translate.
"""
import html, json, os, re, subprocess, sys, urllib.parse

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data", "column.json")
PAGES = "column"                 # column/<id>.htm, one page per article
PICS = "pictures/column"         # copies of the articles' pictures
SITE = "https://www.christianity.gr"
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
        items[i] = {"id": i, "title": title, "date": d.group(1)[:10], "url": url,
                    "image": preview_image(s), "body": article_body(s)}
        print("  new:", items[i]["date"], title)
    for i in EXCLUDE | UNSURE:
        items.pop(i, None)
    # articles listed before their text was kept here: read the text (and picture) once
    for e in items.values():
        if not e.get("body"):
            s = get(e["url"])
            e["body"] = article_body(s)
            e["image"] = e.get("image") or preview_image(s)
            print("  text kept:", e["date"], e["title"])
    return sorted(items.values(), key=lambda e: (e["date"], e["id"]), reverse=True)


def article_body(page):
    """The article's text from its page on christianity.gr, cleaned to plain, safe HTML.

    Kept: paragraphs, lists, emphasis, footnote anchors, sub-/superscripts, pictures (copied here
    later by keep_pictures). Dropped: the newspaper's styling, scripts, and every link to its site;
    links to the old christianity-science.gr point to this site's home page instead.
    """
    m = re.search(r'(?s)<div class="uk-panel uk-text-large[^"]*">(.*?)</div>\s*<div class="uk-margin-medium">', page) \
        or re.search(r'(?s)<div class="uk-panel uk-text-large[^"]*">(.*?)</div>', page)
    if not m:
        raise SystemExit("Could not find the article text on the newspaper's page (has its layout changed?)")
    b = re.sub(r"(?is)<(style|script)\b.*?</\1>", "", m.group(1))
    b = re.sub(r"(?is)<!--.*?-->", "", b)
    b = b.replace("\xa0", " ").replace("&nbsp;", " ")

    def tag(t):
        close, name, attrs = t.group(1), t.group(2).lower(), t.group(3) or ""
        if name in ("span", "font", "div", "o:p"):
            return ""
        if name not in ("p", "br", "strong", "b", "em", "i", "u", "ul", "ol", "li", "sup", "sub", "a", "img", "h2", "h3", "h4", "blockquote"):
            return ""
        if close:
            return "</%s>" % name
        if name == "p":
            return '<p class="colart__right">' if re.search(r"text-align:\s*right", attrs) else "<p>"
        if name == "a":
            h = re.search(r'href="([^"]*)"', attrs)
            href = html.unescape(h.group(1)).strip() if h else ""
            anchor = re.search(r'\b(?:name|id)="([\w\-]+)"', attrs)        # footnote targets (Word: name="_ftn1")
            ident = ' id="%s"' % anchor.group(1) if anchor else ""
            if href.startswith("#"):
                return '<a%s href="%s">' % (ident, html.escape(href, quote=True))
            if ident and not href:
                return '<a%s>' % ident
            if re.match(r"https?://(www\.)?christianity-science\.gr/?$", href):
                return '<a href="../index.html">'
            if re.match(r"https?://", href) and "christianity.gr" not in href:
                return '<a href="%s" target="_blank" rel="noopener">' % html.escape(href, quote=True)
            return "<a>"                       # newspaper or unknown link: keep the words, drop the link
        if name == "img":
            s = re.search(r'src="([^"]+)"', attrs)
            if not s:
                return ""
            side = ' class="colart__float"' if re.search(r"float:\s*(right|left)", attrs) else ""
            return '<img%s src="%s" alt="" loading="lazy" decoding="async">' % (side, html.escape(urllib.parse.urljoin(SITE, html.unescape(s.group(1))), quote=True))
        return "<%s>" % name

    b = re.sub(r"<(/?)([\w:]+)([^>]*)>", tag, b)
    b = re.sub(r"<a>(.*?)</a>", r"\1", b, flags=re.S)                      # unlinked words
    ids = set(re.findall(r'id="([\w\-]+)"', b))                           # footnote links whose target is missing
    b = re.sub(r'<a(?: id="[\w\-]+")? href="#([\w\-]+)">(.*?)</a>', lambda m: m.group(0) if m.group(1) in ids else m.group(2), b, flags=re.S)
    b = re.sub(r"<(strong|em|b|i|u|sup|sub)>\s*</\1>", "", b)
    b = re.sub(r"<p(?: [^>]*)?>\s*(<br>\s*)*</p>", "", b)
    b = re.sub(r"[ \t]+", " ", b)
    b = re.sub(r"\s*\n\s*", "\n", b).strip()
    return b


def picture_name(url):
    """pictures/column/<name> for a picture on christianity.gr (names are unique on their site)."""
    path = urllib.parse.unquote(urllib.parse.urlparse(url).path)
    name = re.sub(r"^/?images/", "", path).replace("/", "-")
    return re.sub(r"[^\w.\-]", "_", name)


def keep_pictures(items, offline=False):
    """Copy each article's pictures to pictures/column/ (once) and point its text and card at them."""
    os.makedirs(os.path.join(ROOT, PICS), exist_ok=True)

    def local(url):
        name = picture_name(url)
        dest = os.path.join(ROOT, PICS, name)
        if not os.path.exists(dest) and not offline:
            r = subprocess.run(["curl", "-sfL", "--retry", "2", "-A", UA, "-o", dest, url], capture_output=True, timeout=120)
            if r.returncode:
                if os.path.exists(dest):
                    os.remove(dest)
                print("  picture not copied:", url)
                return ""
        return PICS + "/" + name if os.path.exists(dest) else ""

    for e in items:
        if e.get("image", "").startswith("http"):
            e["picture"] = local(e["image"]) or e.get("picture", "")
        e["body"] = re.sub(r'src="(https?://[^"]+)"', lambda m: 'src="../%s"' % (local(html.unescape(m.group(1))) or ""), e.get("body", ""))
        e["body"] = re.sub(r'<img[^>]* src="\.\./"[^>]*>', "", e["body"])        # a picture that could not be copied


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


def page_of(e):
    return "%s/%d.htm" % (PAGES, e["id"])


def card(e, prefix=""):
    online = "id" in e
    href = prefix + (page_of(e) if online else e["path"])
    meta = ('<time datetime="%s">%s</time>' % (e["date"][:7], month_label(e["date"]))) if e["date"] else "Χωρίς ημερομηνία"
    if e.get("author"):
        meta += " · " + html.escape(e["author"], quote=False)
    if online and e.get("picture"):
        # the article's own picture, kept on this site (decorative: the title says what it is)
        visual = '<span class="ref__thumb"><img src="%s" alt="" loading="lazy" decoding="async" width="96" height="72"></span>' % html.escape(prefix + e["picture"], quote=True)
    else:
        visual = '<span class="ref__icon ref__icon--%s">%s</span>' % ("web" if online else "pdf", NEWS if online else DOC)
    return ('          <li class="ref%s" data-filter>\n' % (" ref--thumb" if "ref__thumb" in visual else "") +
            '            ' + visual + '\n'
            '            <div class="ref__body">\n'
            '              <p class="ref__title" translate="no"><a href="%s">%s</a></p>\n'
            '              <p class="ref__desc" translate="no">%s</p>\n'
            '            </div>\n'
            '            <span class="ref__badge">%s</span>\n'
            '          </li>') % (html.escape(href, quote=True), html.escape(e["title"], quote=False), meta,
                                   "Άρθρο" if online else "PDF")


def shell_page(title, description):
    """The site's page frame (header, footer) taken from articles.html, with an empty page body."""
    shell = open(os.path.join(ROOT, "articles.html"), encoding="utf-8").read()
    shell = re.sub(r"\s*<!-- column -->.*?<!-- /column -->", "", shell, flags=re.S)
    shell = re.sub(r"\s*<!-- seo -->.*?<!-- /seo -->", "", shell, flags=re.S)
    shell = re.sub(r"(?s)<title>.*?</title>", lambda _: title, shell)
    shell = re.sub(r'<meta name="description" content="[^"]*">', lambda _: '<meta name="description" content="%s">' % description, shell)
    return shell


def nested(src):
    """Make a root-level page work one folder down (column/<id>.htm): prefix its relative links with ../."""
    def fix(m):
        url = m.group(2)
        if re.match(r"([a-z][a-z0-9+.-]*:|#|/|\.\./)", url, re.I) or not url:
            return m.group(0)
        return '%s="../%s"' % (m.group(1), url)
    return re.sub(r'\b(href|src)="([^"]*)"', fix, src)


def article_pages(online):
    """column/<id>.htm for every article, with previous / next links in date order."""
    folder = os.path.join(ROOT, PAGES)
    os.makedirs(folder, exist_ok=True)
    wanted = set()
    for n, e in enumerate(online):
        newer = online[n - 1] if n > 0 else None
        older = online[n + 1] if n + 1 < len(online) else None
        title = html.escape(e["title"], quote=False)
        page = nested(shell_page('<title translate="no">%s — Χριστιανισμός & Επιστήμη</title>' % title,
                                 "Άρθρο της ομάδας «Χριστιανισμός &amp; Επιστήμη» από τη στήλη της στην εφημερίδα «Χριστιανισμός»."))
        when = '<time datetime="%s" translate="no">%s</time>' % (e["date"][:7], month_label(e["date"]))   # month made English by build_en
        page = re.sub(r'(?s)<section class="pagehead">.*?</section>', lambda _: '''<section class="pagehead">
      <div class="wrap">
        <p class="pagehead__kicker"><a href="../column.html">Η στήλη μας στην εφημερίδα «Χριστιανισμός»</a></p>
        <h1 class="pagehead__title" translate="no">%s</h1>
        <p class="pagehead__lede">%s · Η ομάδα «Χριστιανισμός &amp; Επιστήμη»</p>
      </div>
    </section>''' % (title, when), page)
        figure = ('        <figure class="colart__figure"><img src="../%s" alt="" width="1200" height="800" decoding="async"></figure>\n'
                  % html.escape(e["picture"], quote=True)) if e.get("picture") else ""
        nav = []
        if older:
            nav.append('<a class="colart__prev" href="%d.htm"><span class="colart__dir">← Προηγούμενο άρθρο</span><span class="colart__navtitle" translate="no">%s</span></a>'
                       % (older["id"], html.escape(older["title"], quote=False)))
        if newer:
            nav.append('<a class="colart__next" href="%d.htm"><span class="colart__dir">Επόμενο άρθρο →</span><span class="colart__navtitle" translate="no">%s</span></a>'
                       % (newer["id"], html.escape(newer["title"], quote=False)))
        body = ('        <article class="prose colart">\n' + figure +
                '        <div class="colart__text" translate="no" lang="el">\n%s\n        </div>\n' % e["body"] +
                '        <p class="colart__source">Δημοσιεύθηκε στη στήλη της ομάδας στην εφημερίδα «Χριστιανισμός», %s.</p>\n' % when +
                '        </article>\n'
                '        <nav class="colart__nav" aria-label="Άλλα άρθρα της στήλης">%s</nav>\n' % "".join(nav) +
                '        <p class="colart__all"><a href="../column.html">Όλα τα άρθρα της στήλης</a></p>')
        page = re.sub(r'(?s)(<div class="page">\s*<div class="wrap">).*?(</div>\s*</div>\s*</main>)',
                      lambda m: m.group(1) + "\n" + body + "\n      " + m.group(2), page)
        name = "%d.htm" % e["id"]
        wanted.add(name)
        path = os.path.join(folder, name)
        old = open(path, encoding="utf-8").read() if os.path.exists(path) else None
        if old is None or re.sub(r"\?v=[0-9a-f]+", "", old) != re.sub(r"\?v=[0-9a-f]+", "", page):
            open(path, "w", encoding="utf-8", newline="\n").write(page)
    for name in os.listdir(folder):                      # articles no longer in the column
        if name.endswith(".htm") and name not in wanted:
            os.remove(os.path.join(folder, name))


def column_page(online, archive):
    shell = shell_page("<title>Η στήλη μας στην εφημερίδα «Χριστιανισμός» — Χριστιανισμός & Επιστήμη</title>",
                       "Όλα τα άρθρα της ομάδας «Χριστιανισμός &amp; Επιστήμη» στη μηνιαία στήλη της εφημερίδας «Χριστιανισμός».")
    shell = re.sub(r'(?s)<section class="pagehead">.*?</section>', '''<section class="pagehead">
      <div class="wrap">
        <p class="pagehead__kicker">Άρθρα</p>
        <h1 class="pagehead__title">Η στήλη μας στην εφημερίδα «Χριστιανισμός»</h1>
        <p class="pagehead__lede">Τα άρθρα της ομάδας «Χριστιανισμός &amp; Επιστήμη» στη μηνιαία στήλη της εφημερίδας, όλα διαθέσιμα εδώ. Τα παλαιότερα διαβάζονται ως PDF.</p>
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
        <p class="empty" id="filterEmpty" hidden>Δεν βρέθηκε άρθρο. Δοκιμάστε άλλη λέξη.</p>''')
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
           % (MONTHS_GEN[m - 1], y, json.dumps(e["title"], ensure_ascii=False), page_of(e)))
    s2 = re.sub(r"latestColumn: \{.*?\n    \}", lambda _: new, s, count=1, flags=re.S)
    s2 = re.sub(r'columnUrl: "[^"]*"', 'columnUrl: "column.html"', s2, count=1)
    if s2 != s:
        open(path, "w", encoding="utf-8", newline="\n").write(s2)
        print("home page box: latest column is now", e["title"])


def main():
    os.makedirs(os.path.dirname(DATA), exist_ok=True)
    old = json.load(open(DATA, encoding="utf-8")) if os.path.exists(DATA) else {}
    known = old.get("online", [])
    review = [r for r in old.get("review", []) if r["id"] not in EXCLUDE | UNSURE | CONFIRMED]
    offline = "--offline" in sys.argv
    online = known if offline else fetch_online(known, review)
    keep_pictures(online, offline)
    archive = local_archive()
    json.dump({"online": online, "archive": archive, "review": review},
              open(DATA, "w", encoding="utf-8", newline="\n"), ensure_ascii=False, indent=1)
    if review:
        print("NEEDS REVIEW (not added): " + "; ".join("%s %s" % (r["id"], r["title"]) for r in review))
    column_page(online, archive)
    article_pages(online)
    articles_block(online, len(online) + len(archive))
    if online:
        latest_box(online[0])
    print("column: %d newspaper articles online, %d older ones as PDF; left out as unsure: %s"
          % (len(online), len(archive), ", ".join(map(str, sorted(UNSURE)))))


if __name__ == "__main__":
    main()
