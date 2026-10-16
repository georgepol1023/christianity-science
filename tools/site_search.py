"""Site-wide search: the magnifying glass in the top bar of every page.

    python tools/site_search.py      (run by tools/build_all.py, after related.py and before build_en.py)

It writes
  * js/search-index.js   every broadcast, newspaper column article, topic, media page, question and
                         «Άρθρα & πηγές» page: title (Greek and English), address, date, and a few
                         distinctive words from its text, so a search finds it by subject too;
and makes sure every Greek page has
  * the search button in its top bar (before the light/dark button), and
  * <script src="…js/sitesearch.js" data-index="<version>">, which opens the search panel and loads
    js/search.js (the matching) and js/search-index.js only when the panel is first opened.
The English pages get both from the Greek ones (tools/build_en.py). Safe to run again.
"""
import hashlib, html, json, math, os, re, sys
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import related as R

ROOT = R.ROOT
KEYWORDS = 12          # distinctive words kept per item
BUTTON = ('<button class="iconbtn" id="siteSearch" aria-label="Αναζήτηση στον ιστότοπο" aria-haspopup="dialog">\n'
          '          <svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="11" cy="11" r="6.5"/><path d="m16 16 4.5 4.5"/></svg>\n'
          '        </button>\n        ')
SKIP_DIRS = {"en", "pictures", "tools", "tests", "translation", "node_modules", ".git", "docs", "data"}


def words(text):
    """Distinctive whole words (normalised: no accents, final sigma), for matching by subject."""
    out = []
    for w in re.findall(r"[a-zα-ω0-9]+", R.norm(text).replace("christianity-science", " ")):
        if len(w) >= 5 and w not in R.STOP and not w.isdigit():
            out.append(w)
    return out


def keywords(docs):
    """Top words of each text by TF-IDF (rare on the site, frequent in the item)."""
    counts = [Counter(words(d)) for d in docs]
    df = Counter()
    for c in counts:
        df.update(set(c))
    n = len(docs) or 1
    out = []
    for c in counts:
        scored = sorted(((1 + math.log(f)) * math.log(n / df[w]), w) for w, f in c.items() if df[w] > 1)
        out.append(" ".join(w for _, w in reversed(scored[-KEYWORDS:])))
    return out


def plain(s):
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", "", s or ""))).strip()


def article_pages(en_dict):
    """«Άρθρα & πηγές» pages (articles/), and the topic categories (categories/, listed under Topics)."""
    items = []
    for folder_name, kind in (("articles", "A"), ("categories", "T")):
        items += pages_in(folder_name, kind, en_dict)
    return items


def pages_in(folder_name, kind, en_dict):
    items = []
    folder = os.path.join(ROOT, folder_name)
    for f in sorted(os.listdir(folder)):
        if not f.endswith(".htm"):
            continue
        src = open(os.path.join(folder, f), encoding="utf-8").read()
        if 'http-equiv="refresh"' in src:
            continue
        h1 = re.search(r'<h1 class="pagehead__title"[^>]*>(.*?)</h1>', src, re.S)
        if not h1:
            continue
        title = re.sub(r"\s+", " ", h1.group(1)).strip()
        items.append({"kind": kind, "url": folder_name + "/" + f, "el": title, "en": en_dict.get(title),
                      "body": R.main_of(src)})
    return items


def build_index():
    items = R.collect()
    items += article_pages(R.en_dict())
    kw = keywords([(it["text"] if "text" in it else it["el"]) + " " + it["body"] for it in items])
    # English words for the column articles (their English text lives in translation/column/)
    en_body = {}
    for it in items:
        if it["kind"] == "C":
            p = os.path.join(ROOT, "translation", "column", it["url"].split("/")[1].replace(".htm", ".html"))
            if os.path.exists(p):
                en_body[it["url"]] = open(p, encoding="utf-8").read()
    en_kw = dict(zip(en_body, keywords(list(en_body.values()))))
    out = []
    for it, k in zip(items, kw):
        url = it["url"]
        page = url.split("#")[0]
        row = {"k": it["kind"], "u": url, "t": plain(it["el"])}
        if it.get("en"):
            row["e"] = plain(it["en"])
        if it["kind"] == "B":
            row["d"] = it["key"].replace("_", "-")
        if k:
            row["w"] = k
        if en_kw.get(url):
            row["x"] = en_kw[url]
        if os.path.exists(os.path.join(ROOT, "en", page)):
            row["h"] = 1                                  # has an English page
        out.append(row)
    order = {"B": 0, "C": 1, "T": 2, "M": 3, "Q": 4, "A": 5}
    out.sort(key=lambda r: (order[r["k"]], r.get("d", "") and -int(r["d"].replace("-", "")), r["t"]))
    return out


def pages():
    for d, dirs, files in os.walk(ROOT):
        if os.path.normpath(d) == os.path.normpath(ROOT):
            dirs[:] = [x for x in dirs if x not in SKIP_DIRS]
        for f in files:
            if f.endswith((".html", ".htm")):
                yield os.path.join(d, f)


def main():
    index = build_index()
    data = json.dumps(index, ensure_ascii=False, separators=(",", ":"))
    # The pages carry the version of the search's code only (js/search.js, which rarely changes), not of the list:
    # a new broadcast changes the list, and if its version were in every page, every page would change with it
    # (592 files to upload instead of a dozen). The list is fetched afresh at most once an hour (js/sitesearch.js).
    with open(os.path.join(ROOT, "js", "search.js"), "rb") as f:
        version = hashlib.sha1(f.read()).hexdigest()[:10]
    with open(os.path.join(ROOT, "js", "search-index.js"), "w", encoding="utf-8", newline="\n") as f:
        f.write("/* Made by tools/site_search.py: everything the site-wide search can find.\n"
                " * k kind (B broadcast, C column article, T topic, M media, Q question, A articles & sources),\n"
                " * u address from the site root, t Greek title, e English title, d date, w/x Greek/English\n"
                " * words from the text, h 1 when there is an English page. */\n")
        f.write("window.SITE_INDEX = " + data + ";\n")

    changed = 0
    for path in pages():
        src = open(path, encoding="utf-8").read()
        if '<div class="topbar__tools">' not in src or 'http-equiv="refresh"' in src:
            continue
        new = src
        # the home page's old button only jumped to the archive's own search box
        new = re.sub(r'\s*<button class="iconbtn" id="searchJump"[^>]*>.*?</button>', "", new, flags=re.S)
        m = re.search(r'<script src="([^"]*)js/(?:page|app)\.js', new)
        if m:                                   # pages without the site's scripts get no button
            if 'id="siteSearch"' not in new:
                new = new.replace('<button class="iconbtn" id="themeToggle"', BUTTON + '<button class="iconbtn" id="themeToggle"', 1)
            tag = '<script src="%sjs/sitesearch.js" data-index="%s"></script>' % (m.group(1), version)
            if "js/sitesearch.js" in new:
                new = re.sub(r'(<script src="[^"]*js/sitesearch\.js[^"]*" data-index=")\w*"?', lambda m: m.group(1) + version + '"', new)
            else:
                new = new.replace(m.group(0), tag + "\n  " + m.group(0), 1)
        if new != src:
            open(path, "w", encoding="utf-8", newline="\n").write(new)
            changed += 1
    print("site search: %d items in js/search-index.js (%d KB); %d pages updated"
          % (len(index), len(data.encode("utf-8")) // 1024, changed))


if __name__ == "__main__":
    main()
