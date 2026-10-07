"""Turn the article reading lists (articles/*.htm) into cards.

    python tools/restyle_articles.py

The old pages list each article as  <strong>Title link(s)</strong> - description (source link),
one per line. This rewrites each list into  <ul class="refs"> with one card per article:
title, description, an icon and a label (PDF / site name / "Άρθρο"). Safe to run again.
"""
import glob, html, os, re
from urllib.parse import urlparse

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ICON = {
    "pdf": '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8z"/><path d="M14 3v5h5M9 13h6M9 17h4"/></svg>',
    "web": '<svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="9"/><path d="M3 12h18M12 3a14 14 0 0 1 0 18M12 3a14 14 0 0 0 0 18"/></svg>',
    "page": '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M5 4.5h9.5A2.5 2.5 0 0 1 17 7v13H7.5A2.5 2.5 0 0 1 5 17.5z"/><path d="M5 17.5A2.5 2.5 0 0 1 7.5 15H17"/></svg>',
}


def kind(title_html):
    """What the first link points to: (icon, label)."""
    m = re.search(r'href="([^"]+)"', title_html)
    if not m:
        return "page", ""
    href = html.unescape(m.group(1))
    if href.lower().split("?")[0].endswith(".pdf"):
        return "pdf", "PDF"
    if re.match(r"https?://", href):
        host = urlparse(href).netloc.lower()
        return "web", host[4:] if host.startswith("www.") else host
    return "page", "Άρθρο"


def card(line):
    m = re.match(r"\s*<strong>(.*?)</strong>(.*)$", line, re.S)
    title, rest = m.group(1).strip(), m.group(2).strip()
    rest = re.sub(r"^(<br>\s*)+", "", rest)
    rest = re.sub(r"^[-–—]\s*", "", rest).strip()
    rest = re.sub(r"(\s*<br>)+$", "", rest)
    # tidy spaces inside links left by the old markup
    title = re.sub(r'(<a [^>]*>)\s+', r"\1", title)
    rest = re.sub(r'(<a [^>]*>)\s+', r"\1", rest)
    rest = re.sub(r"<em>\s+", "<em>", rest)
    icon, label = kind(title)
    out = ['<li class="ref">',
           '  <span class="ref__icon ref__icon--%s">%s</span>' % (icon, ICON[icon]),
           '  <div class="ref__body">',
           '    <p class="ref__title">%s</p>' % title]
    if re.sub(r"<[^>]+>|\s", "", rest):
        out.append('    <p class="ref__desc">%s</p>' % rest)
    out.append("  </div>")
    if label:
        out.append('  <span class="ref__badge">%s</span>' % html.escape(label))
    out.append("</li>")
    return "\n".join("          " + x for x in out)


def restyle(path):
    src = open(path, encoding="utf-8").read()
    if 'class="refs"' in src:
        return 0
    a = src.find('<article class="prose prose--wide">')
    if a == -1:
        return 0
    start = src.index(">", a) + 1
    end = src.index("</article>", start)
    # headings are sometimes split over two lines ("<h2>* * *" / "</h2>"): join them first
    content = re.sub(r"\s*\n\s*(</h[2-4]>)", r"\1", src[start:end])
    lines = [l for l in content.split("\n") if l.strip()]
    out, group, n = [], [], 0

    def flush():
        if group:
            out.append('        <ul class="refs">\n' + "\n".join(group) + "\n        </ul>")
            group.clear()

    for line in lines:
        # a few entries have the bold inside the link: <a …><strong>Title</strong></a> → <strong><a …>Title</a></strong>
        line = re.sub(r'^\s*(<a [^>]*>)\s*<strong>(.*?)</strong>\s*</a>', r"<strong>\1\2</a></strong>", line)
        text = re.sub(r"<[^>]+>|\s", "", line)
        if text and set(text) <= set("*·•"):           # old "* * *" divider between groups
            flush(); out.append('        <p class="refs__sep" aria-hidden="true"></p>'); continue
        if line.lstrip().startswith("<strong>") and "</strong>" in line and "<a " in line:
            group.append(card(line)); n += 1
        else:
            flush(); out.append("        " + line.strip())
    flush()
    src = src[:start] + "\n" + "\n".join(out) + "\n        " + src[end:]
    src = src.replace('<article class="prose prose--wide">', '<article class="prose prose--wide reflist">', 1)
    open(path, "w", encoding="utf-8", newline="\n").write(src)
    return n


if __name__ == "__main__":
    total = pages = 0
    for path in sorted(glob.glob(os.path.join(ROOT, "articles", "*.htm"))):
        n = restyle(path)
        if n:
            pages += 1; total += n
    print("restyled %d article lists (%d articles)" % (pages, total))
