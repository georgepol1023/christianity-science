"""Build the English pages (en/*.html) from the Greek pages and translation/en.json.

    python tools/build_en.py            build en/ pages; fails if any Greek text has no translation
    python tools/build_en.py --extract  write translation/_todo.json with every Greek unit still untranslated

Each paragraph, heading, list item, button, label etc. is one translation unit, keyed by its Greek
inner HTML (whitespace collapsed), so links and bold text inside it are translated together.
Greek attribute values (title, aria-label, placeholder, alt, meta content) are translated separately.
"""
import json, os, posixpath, re, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PAGES = ["index.html", "about.html", "articles.html", "material.html", "faq.html", "media.html", "links.html", "contact.html", "column.html"]
DICT_PATH = os.path.join(ROOT, "translation", "en.json")
GREEK = re.compile(r"[Ͱ-Ͽἀ-῿]")
UNIT = {"title", "p", "li", "h1", "h2", "h3", "h4", "summary", "label", "button", "a", "span", "small", "strong", "em", "kbd", "td", "th"}
BLOCK = {"p", "li", "h1", "h2", "h3", "h4", "div", "ul", "ol", "section", "article", "details", "table", "nav", "header", "footer", "aside", "main"}
VOID = {"br", "img", "meta", "link", "input", "hr", "source", "wbr"}
ATTRS = ("title", "aria-label", "placeholder", "alt", "content")


def norm(s):
    return re.sub(r"\s+", " ", s).strip()


class El:
    def __init__(self, tag, start, parent):
        self.tag, self.start, self.inner_start, self.inner_end, self.parent, self.kids = tag, start, None, None, parent, []


def tree(src):
    """Elements with source offsets (the pages are generated, well-formed HTML)."""
    root = El("#root", 0, None); root.inner_start = 0; root.inner_end = len(src)
    cur = root
    for m in re.finditer(r"<!--.*?-->|<(/?)([a-zA-Z][\w-]*)\b[^>]*?(/?)>", src, re.S):
        if m.group(0).startswith("<!--") or not m.group(2):
            continue
        close, tag, selfclose = m.group(1), m.group(2).lower(), m.group(3)
        if tag in ("script", "style") and not close:
            end = src.find("</" + tag, m.end())
            el = El(tag, m.start(), cur); el.inner_start = m.end(); el.inner_end = end; cur.kids.append(el)
            continue
        if close:
            if tag in ("script", "style"):
                continue
            n = cur
            while n is not root and n.tag != tag:
                n = n.parent
            if n is not root:
                n.inner_end = m.start(); cur = n.parent
            continue
        el = El(tag, m.start(), cur); el.inner_start = m.end(); cur.kids.append(el)
        if tag not in VOID and not selfclose:
            cur = el
    return root


def walk(el):
    for k in el.kids:
        yield k
        yield from walk(k)


def has_block(el):
    return any(k.tag in BLOCK for k in walk(el))


def no_translate_ranges(src):
    """Elements marked translate="no" (e.g. Greek article titles) are kept as they are."""
    root, ranges = tree(src), []
    for el in walk(root):
        if el.inner_end is not None and 'translate="no"' in src[el.start:el.inner_start]:
            ranges.append((el.start, el.inner_end))
    return ranges


def units(src):
    """(start, end, key) for every translatable piece of text, outermost-first, non-overlapping."""
    root, out, taken = tree(src), [], list(no_translate_ranges(src))
    def inside(a, b):
        return any(s <= a and b <= e for s, e in taken)
    for el in walk(root):
        if el.tag in ("script", "style") or el.inner_end is None:
            continue
        inner = src[el.inner_start:el.inner_end]
        text = re.sub(r"<[^>]+>", "", inner)
        # elements holding an icon are not units: only their text is translated, the <svg> stays as it is
        # nor are elements with a part kept in Greek (translate="no"): their other parts are translated on their own
        if el.tag in UNIT and GREEK.search(text) and not has_block(el) and "<svg" not in inner and 'translate="no"' not in inner                 and not inside(el.inner_start, el.inner_end):
            out.append((el.inner_start, el.inner_end, norm(inner)))
            taken.append((el.inner_start, el.inner_end))
    # loose Greek text that sits directly in a block element
    for m in re.finditer(r">([^<>]+)<", src):
        a, b = m.start(1), m.end(1)
        if GREEK.search(m.group(1)) and not inside(a, b) and not in_script(src, a):
            out.append((a, b, norm(m.group(1))))
    return out


def in_script(src, pos):
    for tag in ("script", "style"):
        s = src.rfind("<" + tag, 0, pos)
        if s != -1 and src.rfind("</" + tag, 0, pos) < s:
            return True
    return False


def attr_units(src):
    for m in re.finditer(r'\s(%s)="([^"]*)"' % "|".join(ATTRS), src):
        if GREEK.search(m.group(2)):
            yield m.start(2), m.end(2), norm(m.group(2))


def lookup(d, key):
    """Exact translation, or one where every number is written as # (counts that change over time)."""
    if key in d:
        return d[key]
    generic = re.sub(r"\d+", "#", key)
    if generic != key and generic in d:
        nums = iter(re.findall(r"\d+", key))
        return re.sub("#", lambda _: next(nums, "#"), d[generic])
    return None


def translate_page(src, d, missing):
    edits = []
    for a, b, key in list(units(src)) + list(attr_units(src)):
        if lookup(d, key) is not None:
            # keep surrounding whitespace of the original slice
            lead = re.match(r"\s*", src[a:b]).group(0); trail = re.search(r"\s*$", src[a:b]).group(0)
            t = lookup(d, key)
            edits.append((a, b, lead + t + trail if src[a:b].strip() else t))
        else:
            missing.append(key)
    for a, b, rep in sorted(edits, reverse=True):
        src = src[:a] + rep + src[b:]
    return ordinals(src)


def ordinals(src):
    """A Greek ordinal ending on its own (19<sup>ος</sup>) is translated as empty: give it the English suffix."""
    def suffix(m):
        n = int(m.group(1))
        s = "th" if 10 <= n % 100 <= 20 else {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
        return "%s<sup>%s</sup>" % (m.group(1), s)
    return re.sub(r"(\d+)<sup></sup>", suffix, src)


MONTHS = dict(zip(["Ιανουάριος", "Φεβρουάριος", "Μάρτιος", "Απρίλιος", "Μάιος", "Ιούνιος", "Ιούλιος", "Αύγουστος",
                   "Σεπτέμβριος", "Οκτώβριος", "Νοέμβριος", "Δεκέμβριος"],
                  ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October",
                   "November", "December"]))


def target_of(page, url):
    """Root-relative path a relative URL on `page` points to (None for external, #, mailto …)."""
    if re.match(r"([a-z]+:|#|//)", url, re.I):
        return None
    base = url.split("#")[0].split("?")[0]
    if not base:
        return None
    return os.path.normpath(os.path.join(os.path.dirname(page), base)).replace("\\", "/")


def localise(src, page, english):
    """Paths, language, scripts for the English copy of `page`, which lives one folder deeper (en/…).

    Links to pages that have an English version stay relative (same folder structure inside en/);
    everything else (PDFs, pictures, audio, untranslated pages) gets one extra ../ to leave en/.
    """
    src = src.replace('<html lang="el">', '<html lang="en">', 1)
    if page.startswith("column/"):     # the newspaper column's articles are kept in Greek, as published
        src = src.replace("</h1>", '</h1>\n        <p class="pagehead__note">This article is in Greek, as it was published in the newspaper.</p>', 1)
    src = re.sub(r"(<time\b[^>]*>)(\S+)", lambda m: m.group(1) + MONTHS.get(m.group(2), m.group(2)), src)

    def fix(m):
        attr, url = m.group(1), m.group(2)
        t = target_of(page, html_unescape(url))
        if t is None:
            return m.group(0)
        if t in english:
            return m.group(0)                  # English page exists: stay inside en/
        rest = url[len(url.split("#")[0].split("?")[0]):]          # keep ?query / #fragment
        here = posixpath.dirname("en/" + page)
        return '%s="%s"' % (attr, posixpath.relpath(t, here) + rest)
    src = re.sub(r'\b(href|src)="([^"]*)"', fix, src)
    if page == "index.html":
        src = src.replace('<script src="../js/app.js', '<script src="../js/broadcasts-en.js"></script>\n  <script src="../js/app.js', 1)
    return src


def html_unescape(s):
    import html as _h
    return _h.unescape(s)


def lang_switch(src, href, label, lang, title):
    """Add (or update) the ΕΛ/EN button in the top bar, and hreflang alternates in <head>."""
    btn = '<a class="iconbtn langbtn" id="langSwitch" href="%s" hreflang="%s" lang="%s" title="%s">%s</a>' % (href, lang, lang, title, label)
    src = re.sub(r'\s*<a class="iconbtn langbtn"[^>]*>[^<]*</a>', "", src)
    src = src.replace('<div class="topbar__tools">', '<div class="topbar__tools">\n        ' + btn, 1)
    return src


def alternates(src, el_href, en_href):
    src = re.sub(r'\s*<link rel="alternate" hreflang="[^"]*" href="[^"]*">', "", src)
    tags = '\n  <link rel="alternate" hreflang="el" href="%s">\n  <link rel="alternate" hreflang="en" href="%s">' % (el_href, en_href)
    return src.replace("</title>", "</title>" + tags, 1)


# Folders whose pages are translated too. A page gets its English version once ALL of its text is
# translated; until then its EN button opens the English page of its section.
DETAIL_FOLDERS = ["categories", "articles", "mp3", "material", "column"]
SECTION_EN = {"material": "material.html", "categories": "material.html", "articles": "articles.html",
              "files": "articles.html", "mp3": "media.html"}


def detail_pages():
    out = []
    for folder in DETAIL_FOLDERS:
        for dirpath, _, files in os.walk(os.path.join(ROOT, folder)):
            for f in sorted(files):
                if f.endswith((".htm", ".html")):
                    rel = os.path.relpath(os.path.join(dirpath, f), ROOT).replace("\\", "/")
                    if 'http-equiv="refresh"' not in open(os.path.join(ROOT, rel), encoding="utf-8").read():
                        out.append(rel)
    return sorted(out)


def strip_seo(src):
    # the search/sharing tags are rebuilt for the English page by seo.py, so do not translate them
    return re.sub(r"\s*<!-- seo -->.*?<!-- /seo -->", "", src, flags=re.S)


def main():
    extract = "--extract" in sys.argv
    only = next((a.split("=", 1)[1] for a in sys.argv if a.startswith("--only=")), None)   # e.g. --only=categories/
    d = json.load(open(DICT_PATH, encoding="utf-8")) if os.path.exists(DICT_PATH) else {}

    # pass 1: which pages can be fully translated?
    pages = PAGES + detail_pages()
    missing_by_page = {}
    for page in pages:
        miss = []
        translate_page(strip_seo(open(os.path.join(ROOT, page), encoding="utf-8").read()), d, miss)
        missing_by_page[page] = miss
    english = {p for p in pages if not missing_by_page[p]}

    # pass 2: write English pages and set every page's language button
    for page in pages:
        src = open(os.path.join(ROOT, page), encoding="utf-8").read()
        depth = page.count("/")
        if page in english:
            el_src = lang_switch(src, "../" * depth + "en/" + page, "EN", "en", "English")
            en = localise(translate_page(strip_seo(el_src), d, []), page, english)
            en = lang_switch(en, "../" * (depth + 1) + page, "ΕΛ", "el", "Ελληνικά")
            if not extract:
                out = os.path.join(ROOT, "en", page)
                os.makedirs(os.path.dirname(out), exist_ok=True)
                open(out, "w", encoding="utf-8", newline="\n").write(en)
        else:
            section = SECTION_EN.get(page.split("/")[0], "index.html")
            el_src = lang_switch(src, "../" * depth + "en/" + section, "EN", "en", "English (this page is in Greek)")
        if el_src != src and not extract:
            open(os.path.join(ROOT, page), "w", encoding="utf-8", newline="\n").write(el_src)
    # untranslatable copies of other publishers' articles (files/): EN opens the English Articles page
    for dirpath, _, files in os.walk(os.path.join(ROOT, "files")):
        for f in files:
            if f.endswith((".htm", ".html")) and not extract:
                path = os.path.join(dirpath, f)
                src = open(path, encoding="utf-8").read()
                if '<div class="topbar__tools">' in src:
                    new = lang_switch(src, "../en/articles.html", "EN", "en", "English (this page is in Greek)")
                    if new != src:
                        open(path, "w", encoding="utf-8", newline="\n").write(new)

    # remove English copies of pages that are no longer fully translated (e.g. the Greek page changed)
    if not extract:
        for dirpath, _, files in os.walk(os.path.join(ROOT, "en")):
            for f in files:
                rel = os.path.relpath(os.path.join(dirpath, f), os.path.join(ROOT, "en")).replace("\\", "/")
                if rel.endswith((".htm", ".html")) and rel in pages and rel not in english:
                    os.remove(os.path.join(dirpath, f))

    main_missing = [k for p in PAGES for k in missing_by_page[p]]
    todo_pages = [p for p in pages if missing_by_page[p] and (only is None or p.startswith(only))]
    todo = []
    for p in todo_pages:
        for k in missing_by_page[p]:
            if k not in todo:
                todo.append(k)
    if extract:
        json.dump(todo, open(os.path.join(ROOT, "translation", "_todo.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        print("%d units still need an English translation (%d pages%s) -> translation/_todo.json"
              % (len(todo), len(todo_pages), ", " + only if only else ""))
        return
    if main_missing:
        print("MISSING %d translations on the main pages, e.g.:" % len(main_missing))
        for t in main_missing[:10]:
            print("  ", t[:100])
        sys.exit(1)
    waiting = len(pages) - len(english)
    print("built %d English pages in en/ (%d pages still waiting for translation)" % (len(english), waiting))


if __name__ == "__main__":
    main()
