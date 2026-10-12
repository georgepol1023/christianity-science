""""Related" links: connect broadcasts, newspaper articles, topic studies, media pages and questions
that are about the same subject.

    python tools/related.py          (run by tools/build_all.py, before the English pages are built)

How items are matched: every item is turned into a list of word stems (Greek accents removed,
words cut to their first 6 letters so that word forms match: «κατακλυσμός», «κατακλυσμού»),
weighted by how rare the word is on the whole site (TF-IDF); titles count three times.
Two items are related when they share enough rare words (cosine similarity).

What it writes:
  * a «Σχετικά» block in each newspaper article (column/*.htm), topic study and media page
    (material/*.htm), and under each question in faq.html, between <!-- related:… --> markers;
  * data/related.json  the English version of each block (tools/build_en.py puts it in the
    English page in place of the Greek block);
  * js/related.js      for the home page archive: related items of each broadcast (the «Σχετικά»
    menu next to «Άρθρα & πηγές»).
Running it again replaces the blocks, so it is safe to run on every build.
"""
import html, json, math, os, re, subprocess, tempfile
from collections import Counter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SITE_EL, SITE_EN = "Χριστιανισμός & Επιστήμη", "Christianity & Science"

MIN_SCORE = 0.09          # below this two items are not considered related
MIN_SCORE_BB = 0.15       # two broadcasts: a higher bar (one shared word like «σύγχρονος» is not enough)
MONTHS_EL = ["Ιαν", "Φεβ", "Μαρ", "Απρ", "Μαΐ", "Ιουν", "Ιουλ", "Αυγ", "Σεπ", "Οκτ", "Νοε", "Δεκ"]
MONTHS_EN = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
LABEL = {
    "el": {"title": "Σχετικά", "B": "Ακούστε σχετικές εκπομπές", "C": "Από τη στήλη μας στην εφημερίδα",
           "T": "Σχετικά θέματα", "M": "Σχετικά βίντεο & πολυμέσα", "Q": "Σχετικές ερωτήσεις", "broadcast": "Εκπομπή"},
    "en": {"title": "Related", "B": "Listen to related broadcasts", "C": "From our newspaper column",
           "T": "Related topics", "M": "Related videos & media", "Q": "Related questions", "broadcast": "Broadcast"},
}

# ---------------------------------------------------------------- text → weighted stems
STOP = set("""
αλλα αλλη αλλο αλλοι αλλεσ αλλων ακομη ακομα αυτο αυτοσ αυτη αυτα αυτοι αυτεσ αυτον αυτην αυτων αυτουσ αυτου αυτησ
γιατι δηλαδη διοτι εδω εκει εκεινο εκεινοσ εκεινη εκεινα εναν ενασ ενοσ επισησ επειδη ειναι εισαι ειμαι ειμαστε ηταν
ητανε ειχε εχει εχουν εχουμε θελει θελουν καθε καθωσ κατα κανει κανουν κατι λοιπον μαζι μεσα μεσω μεταξυ μετα μπορει
μπορουν μονο μονον οποιοσ οποια οποιο οποιοι οποιεσ οποιων οποιου οποιασ ομωσ οπωσ οπου οταν ουτε οχι παντα πολυ πολλα
πολλοι πολλεσ πολλων πριν προσ πωσ σημερα σχεδον τωρα τοτε τουσ τησ των στον στην στουσ στισ στων στου στησ οτιδηποτε
ωστε ετσι επομενωσ εντουτοισ παρολα παροτι αφου ενω οσο οσα οσοι επι υπο απο δεν μην πρεπει γινεται υπαρχει υπαρχουν
αποτελει θελουσι θελομεν ειπε λεγει μασ σασ ημων υμων εαυτο εαυτου εαυτον ολοι ολα ολεσ ολων ολουσ ολη ολο ολοκληρο
αρθρο αρθρα στηλη εφημεριδα ομαδα χριστιανισμοσ επιστημη επιστημησ μεροσ μερουσ συνεχιζεται κεφαλαιο εδαφιο εδαφια
και του τησ τον την των τουσ τισ τα τη το τι ποσ πωσ που για απο στο στη στα στι μια ενα εισ οτι ουδ αλλ δια μετ
παρ υπ επ ηδη ναι ανα ως εσυ εγω μου σου τουσ τισ οσο ολα θεε ενω the and for with are was from that this not but you
""".split())


def norm(s):
    s = html.unescape(re.sub(r"<[^>]+>", " ", s))
    s = re.sub(r"[̀-ͯ]", "", __import__("unicodedata").normalize("NFD", s)).lower()
    return s.replace("ς", "σ")


def stems(text):
    text = norm(text).replace("christianity-science", " ")
    text = re.sub(r"(υπο|στο|μεσα απο) το φωσ|υπο το πρισμα", " ", text)   # "in the light of" is not about light
    out = []
    for w in re.findall(r"[a-zα-ω0-9]+", text):
        if len(w) < 3 or w in STOP or w.isdigit():
            continue
        out.append(w[:6])
    return out


# ---------------------------------------------------------------- collecting the items
def broadcasts():
    js = r"""
const fs = require("fs"), vm = require("vm"), ctx = { window: {} };
vm.runInNewContext(fs.readFileSync(process.argv[2], "utf8"), ctx);
vm.runInNewContext(fs.readFileSync(process.argv[3], "utf8"), ctx);
const en = ctx.window.BROADCAST_TITLES_EN || {}, out = [];
for (const s of ctx.window.BROADCASTS) for (const e of s.episodes)
  out.push({ date: e.date, title: e.title, link: e.link, en: en[e.date] || null, tags: e.tags || [] });
console.log(JSON.stringify(out));
"""
    with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8") as f:
        f.write(js)
    try:
        r = subprocess.run(["node", f.name, os.path.join(ROOT, "js", "broadcasts.js"),
                            os.path.join(ROOT, "js", "broadcasts-en.js")], capture_output=True, check=True)
    finally:
        os.remove(f.name)
    return json.loads(r.stdout.decode("utf-8"))


def main_of(src):
    m = src[src.find("<main"):src.find("</main>")]
    return re.sub(r"(?s)<!-- related:[\w-]+ -->.*?<!-- /related:[\w-]+ -->", "", m)


def en_dict():
    path = os.path.join(ROOT, "translation", "en.json")
    d = json.load(open(path, encoding="utf-8")) if os.path.exists(path) else {}
    return {re.sub(r"\s+", " ", k).strip(): v for k, v in d.items()}


def collect():
    EN = en_dict()
    items = []
    material_text = {}

    # topic studies and media pages
    for f in sorted(os.listdir(os.path.join(ROOT, "material"))):
        if not f.endswith(".htm"):
            continue
        rel = "material/" + f
        src = open(os.path.join(ROOT, rel), encoding="utf-8").read()
        if 'http-equiv="refresh"' in src:
            continue
        kicker = re.search(r'pagehead__kicker">(.*?)</p>', src)
        h1 = re.search(r'<h1 class="pagehead__title"[^>]*>(.*?)</h1>', src, re.S)
        if not h1:
            continue
        title = re.sub(r"\s+", " ", h1.group(1)).strip()
        body = main_of(src)
        material_text[rel] = body
        kind = "T" if kicker and "Θέματα" in kicker.group(1) else "M"
        items.append({"kind": kind, "key": rel, "url": rel, "el": title, "en": EN.get(title),
                      "text": title, "body": body, "page": rel})

    # broadcasts (a broadcast also takes the text of its own topic page, if it has one)
    for b in broadcasts():
        bid = b["date"].replace("-", "_")
        link = b["link"] or ""
        body = material_text.get(link.split("#")[0], "") if link.startswith("material/") else ""
        y, m, d = map(int, b["date"].split("-"))
        items.append({"kind": "B", "key": bid, "url": "index.html#e-" + bid, "el": html.escape(b["title"], quote=False),
                      "en": html.escape(b["en"], quote=False) if b["en"] else None,
                      "text": b["title"], "body": body, "own": link.split("#")[0] if body else None, "tags": set(b.get("tags") or []),
                      "date_el": "%d %s %d" % (d, MONTHS_EL[m - 1], y), "date_en": "%d %s %d" % (d, MONTHS_EN[m - 1], y)})

    # newspaper column articles
    data = json.load(open(os.path.join(ROOT, "data", "column.json"), encoding="utf-8"))
    for e in data["online"]:
        tr = os.path.join(ROOT, "translation", "column", "%s.html" % e["id"])
        en = None
        if os.path.exists(tr):
            h = re.search(r"<h1>(.*?)</h1>", open(tr, encoding="utf-8").read(), re.S)
            en = h.group(1).strip() if h else None
        rel = "column/%s.htm" % e["id"]
        items.append({"kind": "C", "key": rel, "url": rel, "el": html.escape(e["title"], quote=False), "en": en,
                      "text": e["title"], "body": e["body"], "page": rel})

    # questions
    faq = open(os.path.join(ROOT, "faq.html"), encoding="utf-8").read()
    for qid, inner in re.findall(r'(?s)<details id="(q-\d+)"[^>]*>(.*?)</details>', faq):
        s = re.search(r"<summary>(.*?)</summary>", inner, re.S)
        title = re.sub(r"\s+", " ", s.group(1)).strip()
        body = re.sub(r"(?s)<!-- related:[\w-]+ -->.*?<!-- /related:[\w-]+ -->", "", inner)
        items.append({"kind": "Q", "key": qid, "url": "faq.html#" + qid, "el": title, "en": EN.get(title),
                      "text": title, "body": body, "page": "faq.html"})
    return items


# ---------------------------------------------------------------- similarity
def vectors(items):
    """Two unit vectors per item: the whole text (title counted three times), and the title alone."""
    docs, titles = [], []
    for it in items:
        c = Counter(stems(it["body"]))
        t = Counter(stems(it["text"]))
        for k, n in t.items():
            c[k] += 3 * n
        docs.append(c)
        titles.append(t)
    df = Counter()
    for c in docs:
        df.update(set(c))
    n = len(docs)

    def unit(c):
        v = {t: (1 + math.log(f)) * math.log(n / df[t]) for t, f in c.items() if df[t] > 1}
        norm_ = math.sqrt(sum(x * x for x in v.values())) or 1
        return {t: x / norm_ for t, x in v.items()}
    return [(unit(c), unit(t)) for c, t in zip(docs, titles)]


def score(a, b):
    """How related two items are: shared words in the whole text, plus extra when the titles share words."""
    return cosine(a[0], b[0]) + 0.5 * cosine(a[1], b[1])


def cosine(a, b):
    if len(a) > len(b):
        a, b = b, a
    return sum(x * b.get(t, 0) for t, x in a.items())


def series(title):
    """«Κατακλυσμός – Μέρος 2ο: …» → «κατακλυσμός»: the name shared by the parts of a series."""
    t = re.split(r"\s*[–:\-]*\s*\(?\d*ο?\s*[Μμ]έρος\b", html.unescape(title))[0]
    return re.sub(r"[«»\"'.,:;–\-\s]+", " ", t).strip().lower()


def days_apart(a, b):
    import datetime
    d = lambda k: datetime.date(*map(int, k.split("_")))
    return abs((d(a) - d(b)).days)


def related_to(i, items, vecs, kinds, per_kind):
    scored = {}
    for j, it in enumerate(items):
        if j == i or it["kind"] not in kinds:
            continue
        both_b = items[i]["kind"] == "B" and it["kind"] == "B"
        if both_b and not (it["tags"] & items[i]["tags"]):
            continue                                   # two broadcasts must share a topic (js/broadcasts.js)
        if both_b and it["el"] != items[i]["el"] and series(it["el"]) == series(items[i]["el"]) \
                and days_apart(it["key"], items[i]["key"]) < 400:
            continue                                   # another part of the same series: it is right next to it
        # (a broadcast of the same name in another year stays: «Ευθανασία» 2012 → «Ευθανασία» 2018;
        #  below, only one of several with one name is kept)
        s = score(vecs[i], vecs[j])
        if it.get("own") and it["own"] == items[i].get("key"):
            s += 1                                     # the broadcast of this very topic page comes first
        if s >= (MIN_SCORE_BB if both_b else MIN_SCORE):
            scored.setdefault(it["kind"], []).append((s, j))
    out = {}
    for k in kinds:
        seen, picks = set(), []
        for s, j in sorted(scored.get(k, []), reverse=True):
            name = items[j]["el"]
            if name in seen:                           # e.g. a broadcast repeated in a later season
                continue
            seen.add(name)
            picks.append(j)
            if len(picks) == per_kind:
                break
        if picks:
            out[k] = picks
    return out


# ---------------------------------------------------------------- output
def block(groups, items, lang, prefix, slot):
    L = LABEL[lang]
    parts = []
    for kind, idxs in groups.items():
        lis = []
        for j in idxs:
            it = items[j]
            title = it[lang] if lang == "en" and it["en"] else it["el"]
            greek = lang == "en" and not it["en"]
            meta = ('<span class="related__meta">%s · %s</span>' % (L["broadcast"], it["date_" + lang])) if kind == "B" else ""
            lis.append('<li><a href="%s%s"%s>%s</a>%s</li>' % (prefix, it["url"], ' lang="el"' if greek else "", title, meta))
        parts.append('<div class="related__group"><h3 class="related__head">%s</h3><ul class="related__list">%s</ul></div>'
                     % (L[kind], "".join(lis)))
    small = slot.startswith("q-")
    return ('<!-- related:%s -->\n<section class="related%s" translate="no" aria-label="%s">%s<div class="related__groups">%s</div></section>\n<!-- /related:%s -->'
            % (slot, " related--small" if small else "", L["title"],
               "" if small else '<h2 class="related__title">%s</h2>' % L["title"], "".join(parts), slot))


def put(src, slot, html_block, before):
    # the old block goes with the line break after it (put back below), so running this again changes
    # nothing, and a page fresh from tools/update_column.py (the weekly GitHub run) comes out the same
    src = re.sub(r"(?s)<!-- related:%s -->.*?<!-- /related:%s -->\n?" % (slot, slot), "", src)
    i = src.find(before)
    if i < 0:
        return src
    return src[:i] + html_block + "\n" + src[i:]


def main():
    items = collect()
    vecs = vectors(items)
    english = {}
    pages = {}

    def add(page, slot, groups, prefix, before):
        if not groups:
            return
        pages.setdefault(page, []).append((slot, block(groups, items, "el", prefix, slot), before))
        english.setdefault(page, {})[slot] = block(groups, items, "en", prefix, slot)

    js = {}
    for i, it in enumerate(items):
        k = it["kind"]
        if k == "C":
            add(it["page"], "page", related_to(i, items, vecs, ["B", "C", "T"], 3), "../", '<nav class="colart__nav"')
        elif k in ("T", "M"):
            add(it["page"], "page", related_to(i, items, vecs, ["B", "C", "T"], 3), "../", "</main>")
        elif k == "Q":
            add("faq.html", it["key"], related_to(i, items, vecs, ["B", "C"], 2), "",
                '<!-- end:%s -->' % it["key"])
        elif k == "B":
            # «Σχετικά» in the archive: up to 3 other broadcasts first, then up to 4 articles, topics, questions
            g = related_to(i, items, vecs, ["B", "C", "T", "M", "Q"], 3)
            flat = g.get("B", [])[:3] + [j for kind in ("C", "T", "M", "Q") for j in g.get(kind, []) if items[j]["key"] != it.get("own")][:4]
            if flat:
                js[it["key"]] = [[items[j]["kind"], items[j]["url"], items[j]["el"], items[j]["en"] or ""] for j in flat]

    # pages: material pages get the block at the end of the page content
    for page, blocks in pages.items():
        path = os.path.join(ROOT, page)
        src = open(path, encoding="utf-8").read()
        new = src
        for slot, b, before in blocks:
            if before == "</main>":
                # inside the page's .wrap, after the article
                new = re.sub(r"(?s)\n?<!-- related:page -->.*?<!-- /related:page -->", "", new)
                m = list(re.finditer(r"</article>", new))
                if m:
                    p = m[-1].end()
                    new = new[:p] + "\n" + b + new[p:]
                continue
            if before.startswith("<!-- end:"):
                qid = slot
                new = re.sub(r"(?s)\n?<!-- related:%s -->.*?<!-- /related:%s -->" % (qid, qid), "", new)
                m = re.search(r'(?s)(<details id="%s"[^>]*>.*?)(\s*</div>\s*</div>\s*</details>)' % qid, new)
                if m:
                    new = new[:m.end(1)] + "\n" + b + new[m.end(1):]
                continue
            new = put(new, slot, b, before)
        if new != src:
            open(path, "w", encoding="utf-8", newline="\n").write(new)

    json.dump(english, open(os.path.join(ROOT, "data", "related.json"), "w", encoding="utf-8", newline="\n"),
              ensure_ascii=False, indent=0)
    with open(os.path.join(ROOT, "js", "related.js"), "w", encoding="utf-8", newline="\n") as f:
        f.write("/* Made by tools/related.py: for each broadcast, related items on the site\n"
                " * [kind (C column article, T topic, M media page, Q question), address, Greek title, English title]. */\n")
        f.write("window.RELATED = " + json.dumps(js, ensure_ascii=False, separators=(",", ":")) + ";\n")
    n = sum(len(v) for v in pages.values())
    print("related: %d blocks on %d pages; %d broadcasts with related items" % (n, len(pages), len(js)))


if __name__ == "__main__":
    main()
