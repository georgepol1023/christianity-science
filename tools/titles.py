"""English titles and topics for a new broadcast, without anyone typing them.

    python tools/titles.py "Η προέλευση των πάντων – Μέρος 3ο"     what would be chosen for this title
    python tools/titles.py --evaluate                            how often the topics come out right on the
                                                                 site's own tagged broadcasts (each one hidden,
                                                                 with its whole series, and guessed)

English title, the most reliable way first:
  1. the site's memory: a title already translated, or a new part of a series ("… – Μέρος 3ο" when Part 2
     exists in English) gets exactly the English already used, so a series always reads the same;
  2. DeepL (DEEPL_API_KEY; the free plan is plenty): British English, told that this is the title of a broadcast
     of a Christian radio programme about faith and science;
  3. the site's style on top: "– Part 2", “quotes”, no full stop at the end.
  A title that quotes Scripture («…») is translated, but the English site uses the King James wording for
  quotations, which no translator gives: such a title is marked for the admin to check.

Topics: from the site's own broadcasts. The new title is compared with every title already on the site (in Greek,
and in English when known) and with the topics' names; the topics of the most similar ones are taken, if they are
similar enough. Measured on the site (October 2026, each broadcast hidden with its whole series): topics guessed for
79% of broadcasts, the first topic right for 83% of those; the rest are left for a person. No outside service,
nothing to pay, nothing to keep up: it learns from each broadcast added.
Only the Python standard library is used.
"""
import argparse, json, math, os, re, sys, unicodedata, urllib.error, urllib.parse, urllib.request
from collections import Counter, defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
ROOT = os.path.dirname(HERE)

PART = re.compile(r"\s*[–—-]\s*Μέρος\s+(\d+)ο?(?=\s*$|\s*:)", re.I)
PART_EN = re.compile(r"\s*[–—-]\s*Part\s+(\d+)(?=\s*$|\s*:)", re.I)
CONTEXT = ("The title of one broadcast of «Χριστιανισμός & Επιστήμη» (Christianity & Science), a weekly Greek "
           "Christian radio programme about faith and science: the Bible, creation, the human body, the mind, "
           "society and modern science. It is a title, so keep it short.")


# ---------------------------------------------------------------- English titles
def pairs(site):
    """[(Greek title, English title)] of the broadcasts already translated."""
    return [(e["title"], site["en"][d]) for d, e in site["by_date"].items() if site["en"].get(d)]


def from_memory(greek, site):
    """The English this site already uses for this title, or for its series. None if there is none."""
    norm = lambda s: re.sub(r"\s+", " ", s).strip().lower()
    known = pairs(site)
    for g, e in known:
        if norm(g) == norm(greek):
            return e
    m = PART.search(greek)
    if not m:
        return None
    base, rest = greek[:m.start()], greek[m.end():]
    for g, e in known:
        gm, em = PART.search(g), PART_EN.search(e)
        if gm and em and norm(g[:gm.start()]) == norm(base) and not rest.strip() and not g[gm.end():].strip():
            return "%s – Part %s" % (e[:em.start()].rstrip(), m.group(1))
    return None


ORDINALS = {"first": 1, "second": 2, "third": 3, "fourth": 4, "fifth": 5, "sixth": 6, "seventh": 7, "eighth": 8,
            "ninth": 9, "tenth": 10}


def house_style(en):
    """The site's way of writing English titles."""
    en = re.sub(r"\s+", " ", en).strip().rstrip(".")
    en = re.sub(r"[«“]\s*", "“", en)
    en = re.sub(r"\s*[»”]", "”", en)
    en = re.sub(r'"([^"]+)"', r"“\1”", en)
    # single quotes around a quotation (‘…’ or '…') become double ones; apostrophes (Lord’s, God's) stay
    en = re.sub(r"(^|[\s(\[–—:])[‘']([^‘’']+?)[’'](?=$|[\s.,;:!?)\]–—])", r"\1“\2”", en)
    # parts: "- Part 2", "Part 2nd", "2nd part", "Part Two" → " – Part 2"
    en = re.sub(r"(?i)\b(?:the\s+)?(first|second|third|fourth|fifth|sixth|seventh|eighth|ninth|tenth)\s+part\b",
                lambda m: "Part %d" % ORDINALS[m.group(1).lower()], en)
    en = re.sub(r"(?i)\b(\d+)(?:st|nd|rd|th)\s+part\b", r"Part \1", en)
    en = re.sub(r"(?i)\bpart\s+(\d+)(?:st|nd|rd|th)\b", r"Part \1", en)
    en = re.sub(r"(?i)\s*[–—,:-]?\s*\bpart\s+(\d+)\s*$", r" – Part \1", en)
    en = re.sub(r"(?i)\s*[–—,-]?\s*\bpart\s+(\d+)\s*:", r" – Part \1:", en)
    en = re.sub(r"\s+-\s+", " – ", en)
    return en[:1].upper() + en[1:]


def deepl(greek, key, log=print):
    """DeepL's English for a Greek title, or None (no key, or the service failed)."""
    if not key:
        return None
    base = os.environ.get("DEEPL_BASE") or ("https://api-free.deepl.com" if key.endswith(":fx") else "https://api.deepl.com")
    body = {"text": [greek], "source_lang": "EL", "target_lang": "EN-GB", "context": CONTEXT,
            "preserve_formatting": True, "split_sentences": "0"}
    req = urllib.request.Request(base.rstrip("/") + "/v2/translate", data=json.dumps(body).encode(), method="POST")
    req.add_header("Authorization", "DeepL-Auth-Key " + key)
    req.add_header("Content-Type", "application/json")
    try:
        import serverfs
        opener = urllib.request.build_opener(urllib.request.HTTPSHandler(context=serverfs.tls_context()))
        with opener.open(req, timeout=60) as r:
            out = json.loads(r.read().decode("utf-8"))
        return out["translations"][0]["text"]
    except urllib.error.HTTPError as ex:
        log("  DeepL: error %s%s; going on without it" % (ex.code, {403: " (the key is wrong)", 456: " (the month's free characters are used up)"}.get(ex.code, "")))
    except (urllib.error.URLError, OSError, ValueError, KeyError, IndexError) as ex:
        log("  DeepL: %s; going on without it" % (getattr(ex, "reason", None) or ex))
    return None


def known_quotations(site):
    """{Greek quotation: its English on the site} from titles already translated («…» ↔ “…”)."""
    out = {}
    for g, e in pairs(site):
        gq, eq = re.findall(r"«([^»]+)»", g), re.findall(r"“([^”]+)”", e)
        if len(gq) == len(eq):
            for a, b in zip(gq, eq):
                out[re.sub(r"\s+", " ", a).strip().lower()] = b
    return out


SMALL = set("a an and as at but by for from in into of on or the to with nor via vs".split())


def capitalised_words(site):
    """Words the site's English titles capitalise in the middle of a title: names (God, Christ, Genesis…)."""
    caps, lower = Counter(), Counter()
    for _, e in pairs(site):
        for m in re.finditer(r"[A-Za-z][A-Za-z’']*", e):
            before = e[:m.start()].rstrip()
            if not before or before[-1] in ":–—“(?!.":      # a title's or a part's first word: capital anyway
                continue
            (caps if m.group(0)[0].isupper() else lower)[m.group(0).lower()] += 1
    return {w for w, n in caps.items() if n > lower.get(w, 0)}


def sentence_case(en, site):
    """'The Races Of Mankind' → 'The races of mankind' (the site writes titles in sentence case); names stay."""
    words_ = re.findall(r"[A-Za-z][A-Za-z’']*", en)
    long_words = [w for w in words_[1:] if w.lower() not in SMALL]
    if len(long_words) < 2 or sum(w[0].isupper() for w in long_words) < 0.7 * len(long_words):
        return en                                          # not Title Case: leave it as DeepL wrote it
    keep = capitalised_words(site)
    first = [True]

    def fix(m):
        w = m.group(0)
        if first[0]:
            first[0] = False
            return w
        if w.lower() in keep or (w.isupper() and len(w) > 1):   # names, and abbreviations like DNA, CERN
            return w
        return w.lower()
    return re.sub(r"[A-Za-z][A-Za-z’']*", fix, en)


def english(greek, site, log=print):
    """(English title or "", how it was found, a note for the admin or "")."""
    known = from_memory(greek, site)
    if known:
        return known, "memory", ""
    t = deepl(greek, os.environ.get("DEEPL_API_KEY", ""), log)
    if not t:
        return "", "", ""
    en, how, note = house_style(sentence_case(house_style(t), site)), "deepl", ""
    quotes = re.findall(r"«([^»]+)»", greek)
    if quotes:
        known_q = known_quotations(site)
        found = [known_q.get(re.sub(r"\s+", " ", q).strip().lower()) for q in quotes]
        translated = re.findall(r"“[^”]+”", en)
        if all(found) and len(translated) == len(quotes):
            for old, new in zip(translated, found):          # the wording the site already uses (King James)
                en = en.replace(old, "“%s”" % new, 1)
            how = "deepl + the site's quotation"
        else:
            note = "ο αγγλικός τίτλος περιέχει παράθεμα: ελέγξτε ότι ακολουθεί τη μετάφραση King James"
    return en, how, note


# ---------------------------------------------------------------- topics, learnt from the site itself
STOP = set("""και η ο το τα οι τη την της του των στο στη στην στον στις στους σε με για απο από ως ενα ένα μια μία
ειναι είναι που πως ποιος ποια ποιο τι μας σας τους δεν μη μην αλλα αλλά ή αν θα να μερος μέρος μερη the of and a an in
on to for is are with from by its it at as or be part how what why who""".split())


def plain(s):
    return "".join(c for c in unicodedata.normalize("NFD", s.lower()) if unicodedata.category(c) != "Mn")


def words(text):
    """Word stems of a title: lower case, no accents, the first 6 letters (Greek endings vary a lot)."""
    out = []
    for w in re.findall(r"[^\W\d_]+", plain(text or "")):
        if len(w) >= 3 and w not in STOP:
            out.append(w[:6])
    return out


class Topics:
    """Nearest neighbours over the site's titles (TF-IDF, cosine). Built from the site each time: always up to date."""
    MIN_SIMILARITY = 0.24            # below this, nothing on the site is like it: no topics guessed (measured: --evaluate)
    SECOND = 0.8                     # a second topic only if it scores this much of the first (measured too)

    def __init__(self, site, names=(), exclude=None):
        self.docs = []
        for d, e in site["by_date"].items():
            if d == exclude or not e["tags"]:
                continue
            self.docs.append((Counter(words(e["title"]) + words(site["en"].get(d, ""))), e["tags"], d))
        for tid, greek_name, english_name in names:      # the topics' own names count as examples too
            self.docs.append((Counter(words(greek_name) + words(english_name)), [tid], "topic:" + tid))
        df = Counter(w for c, _, _ in self.docs for w in c)
        n = len(self.docs)
        self.idf = {w: math.log((n + 1) / (k + 0.5)) for w, k in df.items()}
        self.vecs = [(self.vec(c), tags, d) for c, tags, d in self.docs]

    def vec(self, counts):
        v = {w: (1 + math.log(k)) * self.idf.get(w, math.log(len(self.docs) + 1)) for w, k in counts.items()}
        norm = math.sqrt(sum(x * x for x in v.values())) or 1
        return {w: x / norm for w, x in v.items()}

    def suggest(self, greek, english_title="", k=5):
        """([topic ids], similarity of the closest broadcast)."""
        q = self.vec(Counter(words(greek) + words(english_title)))
        sims = sorted(((sum(x * v.get(w, 0) for w, x in q.items()), tags) for v, tags, _ in self.vecs), reverse=True)[:k]
        if not sims or sims[0][0] < self.MIN_SIMILARITY:
            return [], sims[0][0] if sims else 0
        score = defaultdict(float)
        for s, tags in sims:
            for i, t in enumerate(tags):
                score[t] += s * (1.0 if i == 0 else 0.6)          # a broadcast's first topic counts most
        ranked = sorted(score.items(), key=lambda kv: -kv[1])
        out = [ranked[0][0]] + [t for t, s in ranked[1:3] if s >= self.SECOND * ranked[0][1]]
        return out[:2], sims[0][0]


def series(title):
    return re.sub(r"[«»]", "", PART.split(title)[0]).split(":")[0].strip().lower()


def evaluate(site, names=()):
    """Each broadcast hidden in turn, with its whole series (as a new series would be), its topics guessed
    from the rest. Returns (share of guesses whose first topic is right, share of broadcasts guessed)."""
    rows = []
    for d, e in site["by_date"].items():
        if not e["tags"]:
            continue
        b = series(e["title"])
        rest = {"by_date": {k: v for k, v in site["by_date"].items() if series(v["title"]) != b}, "en": site["en"]}
        guess, sim = Topics(rest, names).suggest(e["title"], site["en"].get(d, ""))
        rows.append((guess, e["tags"], sim))
    given = [r for r in rows if r[0]]
    first_right = sum(1 for g, t, _ in given if g[0] in t)
    any_wrong = sum(1 for g, t, _ in given if any(x not in t for x in g))
    print("broadcasts: %d; topics guessed for %d (%.0f%%), left for a person: %d"
          % (len(rows), len(given), 100 * len(given) / len(rows), len(rows) - len(given)))
    print("of the guessed: first topic right %.0f%%; every guessed topic right %.0f%%"
          % (100 * first_right / max(1, len(given)), 100 * (len(given) - any_wrong) / max(1, len(given))))
    return first_right / max(1, len(given)), len(given) / max(1, len(rows))


def main():
    import inbox
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("title", nargs="?")
    ap.add_argument("--evaluate", action="store_true")
    a = ap.parse_args()
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass
    site = inbox.load_site(ROOT)
    names = inbox.topic_names(ROOT)
    if a.evaluate:
        evaluate(site, names)
        return
    en, how, note = english(a.title, site)
    tags, sim = Topics(site, names).suggest(a.title, en)
    print("English: %r (%s)%s" % (en, how or "none", " — " + note if note else ""))
    print("topics:  %s (closest similarity %.2f)" % (tags, sim))


if __name__ == "__main__":
    main()
