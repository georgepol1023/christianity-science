"""Build the English pages (en/*.html) from the Greek pages and translation/en.json.

    python tools/build_en.py            build en/ pages; fails if any Greek text has no translation
    python tools/build_en.py --extract  write translation/_todo.json with every Greek unit still untranslated

Each paragraph, heading, list item, button, label etc. is one translation unit, keyed by its Greek
inner HTML (whitespace collapsed), so links and bold text inside it are translated together.
Greek attribute values (title, aria-label, placeholder, alt, meta content) are translated separately.
"""
import json, os, re, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PAGES = ["index.html", "about.html", "articles.html", "material.html", "faq.html", "media.html", "links.html", "contact.html"]
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


def units(src):
    """(start, end, key) for every translatable piece of text, outermost-first, non-overlapping."""
    root, out, taken = tree(src), [], []
    def inside(a, b):
        return any(s <= a and b <= e for s, e in taken)
    for el in walk(root):
        if el.tag in ("script", "style") or el.inner_end is None:
            continue
        inner = src[el.inner_start:el.inner_end]
        text = re.sub(r"<[^>]+>", "", inner)
        # elements holding an icon are not units: only their text is translated, the <svg> stays as it is
        if el.tag in UNIT and GREEK.search(text) and not has_block(el) and "<svg" not in inner and not inside(el.inner_start, el.inner_end):
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


def translate_page(src, d, missing):
    edits = []
    for a, b, key in list(units(src)) + list(attr_units(src)):
        if key in d:
            # keep surrounding whitespace of the original slice
            lead = re.match(r"\s*", src[a:b]).group(0); trail = re.search(r"\s*$", src[a:b]).group(0)
            edits.append((a, b, lead + d[key] + trail if src[a:b].strip() else d[key]))
        else:
            missing.append(key)
    for a, b, rep in sorted(edits, reverse=True):
        src = src[:a] + rep + src[b:]
    return src


def localise(src, page):
    """Paths, language, scripts and the language switch for a page that lives in en/."""
    src = src.replace('<html lang="el">', '<html lang="en">', 1)
    # every relative URL now needs ../ (en/ is one level down), except links to the other English pages
    def fix(m):
        attr, url = m.group(1), m.group(2)
        if re.match(r"([a-z]+:|#|//|\.\./)", url, re.I):
            return m.group(0)
        base = url.split("#")[0].split("?")[0]
        if base in PAGES:                      # English page exists: stay inside en/
            return m.group(0)
        return '%s="../%s"' % (attr, url)
    src = re.sub(r'\b(href|src)="([^"]*)"', fix, src)
    if page == "index.html":
        src = src.replace('<script src="../js/app.js', '<script src="../js/broadcasts-en.js"></script>\n  <script src="../js/app.js', 1)
    return src


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


# Greek pages without an English version yet: the EN button opens the English page of their section
SECTION_EN = {"material": "material.html", "categories": "material.html", "articles": "articles.html",
              "files": "articles.html", "mp3": "media.html"}


def link_detail_pages():
    for folder, target in SECTION_EN.items():
        for dirpath, _, files in os.walk(os.path.join(ROOT, folder)):
            for f in files:
                if not f.endswith((".htm", ".html")):
                    continue
                path = os.path.join(dirpath, f)
                src = open(path, encoding="utf-8").read()
                if 'http-equiv="refresh"' in src or '<div class="topbar__tools">' not in src:
                    continue
                depth = os.path.relpath(path, ROOT).replace("\\", "/").count("/")
                href = "../" * depth + "en/" + target
                new = lang_switch(src, href, "EN", "en", "English (this page is in Greek)")
                if new != src:
                    open(path, "w", encoding="utf-8", newline="\n").write(new)


def main():
    extract = "--extract" in sys.argv
    d = json.load(open(DICT_PATH, encoding="utf-8")) if os.path.exists(DICT_PATH) else {}
    missing = []
    os.makedirs(os.path.join(ROOT, "en"), exist_ok=True)
    for page in PAGES:
        src = open(os.path.join(ROOT, page), encoding="utf-8").read()
        # Greek page: switch to the English counterpart
        el_src = alternates(lang_switch(src, "en/" + page, "EN", "en", "English"), page, "en/" + page)
        if el_src != src:
            open(os.path.join(ROOT, page), "w", encoding="utf-8", newline="\n").write(el_src)
        en = localise(translate_page(el_src, d, missing), page)
        en = alternates(lang_switch(en, "../" + page, "ΕΛ", "el", "Ελληνικά"), "../" + page, page)
        if not extract:
            open(os.path.join(ROOT, "en", page), "w", encoding="utf-8", newline="\n").write(en)
    if not extract:
        link_detail_pages()
    todo = sorted(set(missing), key=missing.index)
    if extract:
        json.dump(todo, open(os.path.join(ROOT, "translation", "_todo.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        print("%d units still need an English translation -> translation/_todo.json" % len(todo))
        return
    if todo:
        print("MISSING %d translations, e.g.:" % len(todo))
        for t in todo[:10]:
            print("  ", t[:100])
        sys.exit(1)
    print("built %d English pages in en/" % len(PAGES))


if __name__ == "__main__":
    main()
