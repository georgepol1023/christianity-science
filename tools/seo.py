"""Search-engine and sharing tags for every page, plus sitemap.xml and robots.txt.

    python tools/seo.py

For each page it sets:
  - <link rel="canonical">            the one official address of the page
  - <link rel="alternate" hreflang>   Greek / English versions, as FULL addresses (Google ignores relative ones)
  - og:url, og:image, twitter:card    the card shown when a link is shared on Viber, WhatsApp, Facebook …
Redirect stubs (old addresses) get noindex instead, and are left out of the sitemap.

Run after tools/build_en.py and before tools/stamp.py (tools/build_all.py does all three).
"""
import os, re, datetime, html

# The official address of the site. If you choose the address without "www", change it here and re-run.
SITE_URL = "https://www.christianity-science.gr/"

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKIP_DIRS = {"mp3", "pictures", "tests", "tools", "translation", "docs", "node_modules", ".git"}
SHARE_IMAGE = "pictures/share.png"
MAIN = ["index.html", "about.html", "articles.html", "material.html", "faq.html", "media.html", "links.html", "contact.html", "column.html"]


def pages():
    for d, dirs, files in os.walk(ROOT):
        dirs[:] = [x for x in dirs if not (os.path.normpath(d) == os.path.normpath(ROOT) and x in SKIP_DIRS)]
        for f in files:
            if f.endswith((".html", ".htm")):
                yield os.path.relpath(os.path.join(d, f), ROOT).replace("\\", "/")


def url(rel):
    return SITE_URL + ("" if rel == "index.html" else rel)


def counterpart(rel):
    """(greek, english) addresses for pages that exist in both languages, else None."""
    if rel.startswith("en/"):
        return (rel[3:], rel) if os.path.exists(os.path.join(ROOT, rel[3:])) else None
    return (rel, "en/" + rel) if os.path.exists(os.path.join(ROOT, "en", rel)) else None


def head_tags(rel, src):
    if 'http-equiv="refresh"' in src:
        return ['<meta name="robots" content="noindex">']
    tags = ['<link rel="canonical" href="%s">' % url(rel)]
    pair = counterpart(rel)
    if pair:
        el, en = pair
        tags += ['<link rel="alternate" hreflang="el" href="%s">' % url(el),
                 '<link rel="alternate" hreflang="en" href="%s">' % url(en),
                 '<link rel="alternate" hreflang="x-default" href="%s">' % url(el)]
    title = re.search(r"<title>(.*?)</title>", src, re.S)
    desc = re.search(r'<meta name="description" content="([^"]*)"', src)
    lang = "en_GB" if '<html lang="en">' in src else "el_GR"
    tags += ['<meta property="og:url" content="%s">' % url(rel),
             '<meta property="og:image" content="%s">' % (SITE_URL + SHARE_IMAGE),
             '<meta property="og:image:width" content="1200">', '<meta property="og:image:height" content="630">',
             '<meta property="og:locale" content="%s">' % lang,
             '<meta name="twitter:card" content="summary_large_image">']
    if not re.search(r'property="og:title"', src) and title:
        tags.append('<meta property="og:title" content="%s">' % html.escape(html.unescape(title.group(1).strip()), quote=True))
    if not re.search(r'property="og:description"', src) and desc:
        tags.append('<meta property="og:description" content="%s">' % desc.group(1))
    return tags


MARK_START, MARK_END = "<!-- seo -->", "<!-- /seo -->"


def apply(rel):
    path = os.path.join(ROOT, rel)
    src = open(path, encoding="utf-8").read()
    # remove what an earlier run (or build_en.py) added
    src = re.sub(r"\s*%s.*?%s" % (re.escape(MARK_START), re.escape(MARK_END)), "", src, flags=re.S)
    src = re.sub(r'\s*<link rel="alternate" hreflang="[^"]*" href="[^"]*">', "", src)
    src = re.sub(r'\s*<link rel="canonical" href="[^"]*">', "", src)
    block = "\n  " + MARK_START + "\n  " + "\n  ".join(head_tags(rel, src)) + "\n  " + MARK_END
    if "</title>" in src:
        src = src.replace("</title>", "</title>" + block, 1)
    else:
        src = src.replace("</head>", block + "\n</head>", 1)
    open(path, "w", encoding="utf-8", newline="\n").write(src)
    return 'http-equiv="refresh"' not in src


def sitemap(listed):
    today = datetime.date.today().isoformat()
    out = ['<?xml version="1.0" encoding="UTF-8"?>',
           '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" xmlns:xhtml="http://www.w3.org/1999/xhtml">']
    for rel in sorted(listed, key=lambda r: (r.count("/"), r)):
        mod = datetime.date.fromtimestamp(os.path.getmtime(os.path.join(ROOT, rel))).isoformat()
        out.append("  <url>")
        out.append("    <loc>%s</loc>" % html.escape(url(rel)))
        out.append("    <lastmod>%s</lastmod>" % min(mod, today))
        pair = counterpart(rel)
        if pair:
            out.append('    <xhtml:link rel="alternate" hreflang="el" href="%s"/>' % html.escape(url(pair[0])))
            out.append('    <xhtml:link rel="alternate" hreflang="en" href="%s"/>' % html.escape(url(pair[1])))
        out.append("  </url>")
    out.append("</urlset>")
    open(os.path.join(ROOT, "sitemap.xml"), "w", encoding="utf-8", newline="\n").write("\n".join(out) + "\n")


def robots():
    txt = ("User-agent: *\n"
           "Disallow: /tests/\nDisallow: /tools/\nDisallow: /translation/\n"
           "Disallow: /material/printable/\n\n"
           "Sitemap: %ssitemap.xml\n" % SITE_URL)
    open(os.path.join(ROOT, "robots.txt"), "w", encoding="utf-8", newline="\n").write(txt)


def main():
    # files/ holds copies of other publishers' articles: reachable, but not promoted in the sitemap
    listed = [rel for rel in pages() if rel != "404.html" and apply(rel) and not rel.startswith("files/")]
    sitemap(listed)
    robots()
    print("seo: %d pages tagged, %d in sitemap.xml (site address %s)" % (len(list(pages())), len(listed), SITE_URL))


if __name__ == "__main__":
    main()
