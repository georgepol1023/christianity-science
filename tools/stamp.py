"""Add a content hash to CSS/JS links (site.css?v=…) so browsers never use a stale copy.

Run after changing anything in css/ or js/:   python tools/stamp.py
"""
import hashlib, os, re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ASSETS = ["css/site.css", "js/app.js", "js/page.js", "js/search.js", "js/broadcasts.js", "js/broadcasts-en.js"]
SKIP = {"mp3", "pictures", "tools", "translation", ".git"}

versions = {}
for a in ASSETS:
    with open(os.path.join(ROOT, a), "rb") as f:
        versions[a] = hashlib.sha1(f.read()).hexdigest()[:10]

changed = 0
for d, dirs, files in os.walk(ROOT):
    dirs[:] = [x for x in dirs if not (d == ROOT and x in SKIP) and x != ".git"]  # en/mp3/ holds pages too
    for name in files:
        if not name.endswith((".html", ".htm")):
            continue
        path = os.path.join(d, name)
        with open(path, encoding="utf-8") as f:
            s = f.read()
        new = s
        for a, v in versions.items():
            new = re.sub(r'((?:\.\./)*%s)(\?v=[0-9a-f]+)?"' % re.escape(a), r'\1?v=%s"' % v, new)
        if new != s:
            with open(path, "w", encoding="utf-8", newline="\n") as f:
                f.write(new)
            changed += 1
print("stamped %d pages: %s" % (changed, ", ".join("%s=%s" % kv for kv in versions.items())))
