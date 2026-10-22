"""Greek titles from Greeklish file names ("1_EPISTIMI_PAGKOSMIA_MERA_PSYXIKIS_YGEIAS.mp3"), spelled right.

    python tools/greeklish.py PAGKOSMIA_MERA_PSYXIKIS_YGEIAS     the Greek, word by word, and whether it is sure
    python tools/greeklish.py --evaluate                         measured on the site's own broadcasts (their mp3
                                                                 names against their titles)

Greeklish loses what Greek spelling needs (i may be ι, η, υ, ει or οι; o may be ο or ω; the accents), so letters
alone cannot give the right word. The words are looked up instead, in every Greek word this site has ever printed
(its pages: articles, the column, studies, titles: about 250,000 words): a Greeklish word is matched by how it
sounds to the site's words, and the form the site uses most is taken. A word the site never used is not guessed:
then the title is not sure, and a person completes it («Από email»). Only the Python standard library is used.
"""
import argparse, glob, html, os, re, sys, unicodedata
from collections import Counter, defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

# Greek → a "sound key": letters that Greeklish writes the same are made the same
GREEK_PAIRS = [("ου", "u"), ("ει", "i"), ("οι", "i"), ("υι", "i"), ("αι", "e"), ("αυ", "av"), ("ευ", "ev"), ("ηυ", "iv"),
               ("μπ", "b"), ("ντ", "d"), ("γκ", "g"), ("γγ", "g"), ("γχ", "gx"), ("τσ", "ts"), ("τζ", "dz")]
GREEK_ONE = dict(zip("αβγδεζηθικλμνξοπρσςτυφχψω",
                     ["a", "v", "g", "d", "e", "z", "i", "8", "i", "k", "l", "m", "n", "ks", "o", "p", "r", "s", "s", "t",
                      "i", "f", "x", "ps", "o"]))
# Greeklish → the same key (several ways of writing one sound)
LATIN_PAIRS = [("th", "8"), ("ch", "x"), ("kh", "x"), ("ph", "f"), ("ps", "ps"), ("ks", "ks"), ("ou", "u"), ("oy", "u"),
               ("ei", "i"), ("oi", "i"), ("yi", "i"), ("ui", "i"), ("ai", "e"), ("au", "av"), ("eu", "ev"), ("ay", "av"),
               ("ey", "ev"), ("mp", "b"), ("nt", "d"), ("gk", "g"), ("gg", "g"), ("ts", "ts"), ("tz", "dz")]
LATIN_ONE = {"a": "a", "b": "v", "c": "k", "d": "d", "e": "e", "f": "f", "g": "g", "h": "i", "i": "i", "j": "g", "k": "k",
             "l": "l", "m": "m", "n": "n", "o": "o", "p": "p", "q": "k", "r": "r", "s": "s", "t": "t", "u": "u", "v": "v",
             "w": "o", "x": "x", "y": "i", "z": "z", "8": "8", "3": "ks", "9": "8"}
PROGRAMME = {"epistimi", "episthmh", "episthmi", "xristianismos", "christianismos", "cs", "ekpompi", "ekpomph"}


def plain(s):
    return "".join(c for c in unicodedata.normalize("NFD", s.lower()) if unicodedata.category(c) != "Mn")


def squeeze(key):
    return re.sub(r"(.)\1+", r"\1", key)                    # λλ / ll: one letter


def greek_key(word):
    w, out, i = plain(word), "", 0
    while i < len(w):
        two = w[i:i + 2]
        hit = next((k for g, k in GREEK_PAIRS if g == two), None)
        if hit:
            out, i = out + hit, i + 2
        else:
            out, i = out + GREEK_ONE.get(w[i], ""), i + 1
    return squeeze(out)


# letter pairs that may also be two separate sounds: "oi" is οι, but also ω+ι/η (zois: ζωής); "ai" is αι, or α+ι
TWO_WAYS = {"oi": ["i", "oi"], "ei": ["i", "ei"], "ai": ["e", "ai"], "yi": ["i", "ii"], "ui": ["i", "ui"]}
ONE_WAYS = {"h": ["i", "x"], "x": ["x", "ks"], "b": ["v", "b"], "d": ["d", "8"]}


def latin_keys(word):
    """The sound keys a Greeklish word may stand for (h: η or χ; x: χ or ξ; b: β or μπ; oi: οι or ωι; af: αυ or αφ)."""
    w = word.lower()
    keys = [""]
    i = 0
    while i < len(w):
        two = w[i:i + 2]
        hit = next((k for g, k in LATIN_PAIRS if g == two), None)
        if hit:
            alts, i = TWO_WAYS.get(two, [hit]), i + 2
        else:
            alts, i = ONE_WAYS.get(w[i], [LATIN_ONE.get(w[i], "")]), i + 1
        keys = [k + a for k in keys for a in alts][:256]
    out = set()
    for k in keys:
        k = squeeze(k)
        out.add(k)
        out.add(k.replace("af", "av").replace("ef", "ev"))   # αυ/ευ written af/ef
    return out


_LEXICON = {}


def lexicon(root=ROOT, with_titles=True):
    """{sound key: Counter(Greek word forms as the site prints them)} from all the site's pages (cached)."""
    if (root, with_titles) in _LEXICON:
        return _LEXICON[(root, with_titles)]
    by_key = defaultdict(Counter)
    paths = [p for p in glob.glob(os.path.join(root, "**", "*.htm*"), recursive=True)
             if not os.path.relpath(p, root).replace("\\", "/").startswith(("en/", "mp3/", "files/", "tests/", "node_modules/"))]
    if with_titles:
        paths.append(os.path.join(root, "js", "broadcasts.js"))
    for p in paths:
        try:
            t = open(p, encoding="utf-8", errors="replace").read()
        except OSError:
            continue
        if p.endswith(".js"):
            t = " ".join(re.findall(r'ep\("[^"]*", "([^"]*)"', t))
        else:
            t = re.sub(r"(?is)<(script|style)\b.*?</\1>", " ", t)
            t = re.sub(r"(?is)<a\b[^>]*class=\"[^\"]*(?:ep|broadcast)[^\"]*\"[^>]*>.*?</a>", " ", t)
            t = html.unescape(re.sub(r"<[^>]+>", " ", t))
        for m in re.finditer(r"[α-ωάέήίόύώϊϋΐΰΑ-ΩΆΈΉΊΌΎΏ]+", t):
            w = m.group(0)
            if len(w) > 1 and w.isupper():
                continue                                         # written in capitals: no accents to learn from
            by_key[greek_key(w)][w.lower()] += 1
            before = t[:m.start()].rstrip()[-1:]
            if before and (before.isalpha() or before in ",«“"):  # mid-sentence: a capital there is the word's own
                CAPS[w.lower()][w[0].isupper()] += 1
    _LEXICON[(root, with_titles)] = by_key
    return by_key


CAPS = defaultdict(lambda: [0, 0])          # word → [times written small, times written with a capital] mid-sentence


def cased(w):
    """The word with a capital if the site writes it so mid-sentence (Χριστός, Θεός, Χριστούγεννα, Γένεση)."""
    small, big = CAPS.get(w.lower(), (0, 0))
    return w[:1].upper() + w[1:] if big >= 3 and big > 3 * small else w   # clearly a name; else small (sentence case)


CLEAR = 0.8          # the site's most used form must be this share of all forms that sound the same (else: not sure)


def word(latin, lex, first=False):
    """(Greek word, sure) for one Greeklish word. Sure when the site clearly uses one form for that sound: "psyxikis"
    → ψυχικής; not "ti" (τη or τι), not a word the site never printed. Roman numerals and capital abbreviations
    (II, DNA) stay as they are."""
    if re.fullmatch(r"(?i)[ivx]+", latin) and len(latin) <= 4 and latin.isupper():
        return latin, True                                       # «Άρτεμις ΙΙ»: a numeral, not a word
    found = Counter()
    for k in latin_keys(latin):
        found.update(lex.get(k, {}))
    if not found:
        if latin.isupper() and 2 <= len(latin) <= 4:
            return latin, True                                   # DNA, CERN, LHC: written as they are
        return latin.lower(), False
    # the station's own spelling says more than how often the site uses a form: "ysi" is -υση, "eis" is -εις
    typed = spelled(latin)
    matching = Counter({f: c for f, c in found.items() if greek_spelled(f) == typed})
    pool = matching or found
    (best, n), total = pool.most_common(1)[0], sum(pool.values())
    accented = lambda f: plain(f) != f
    floor = 2 if first else max(2, 0.1 * n)              # a title's first word may be a question word (Τι, Πού)
    rivals = [f for f in pool if f != best and pool[f] >= floor and (plain(f) != plain(best) or accented(f))]
    if len(plain(best)) <= 4 and rivals:
        return best, False                                       # τη/τι, που/πού: short words need the sentence
    return best, n >= 2 and n / total >= CLEAR                   # one form clearly the site's (and the station's)


# How Greeklish is usually typed, letter by letter (y for υ, ei for ει, w for ω, h for η…), to compare the station's
# spelling with each candidate's: consonants the same way as in latin_keys, vowels kept apart.
G_SPELL_PAIRS = [("ου", "ou"), ("ει", "ei"), ("οι", "oi"), ("αι", "ai"), ("υι", "yi"), ("αυ", "ay"), ("ευ", "ey"),
                 ("μπ", "mp"), ("ντ", "nt"), ("γκ", "gk"), ("γγ", "gg")]
G_SPELL_ONE = dict(zip("αβγδεζηθικλμνξοπρσςτυφχψω",
                       ["a", "v", "g", "d", "e", "z", "i", "th", "i", "k", "l", "m", "n", "ks", "o", "p", "r", "s", "s", "t",
                        "y", "f", "x", "ps", "o"]))


def greek_spelled(word):
    w, out, i = plain(word), "", 0
    while i < len(w):
        hit = next((k for g, k in G_SPELL_PAIRS if g == w[i:i + 2]), None)
        out, i = (out + hit, i + 2) if hit else (out + G_SPELL_ONE.get(w[i], ""), i + 1)
    return squeeze(out)


def spelled(latin):
    w = latin.lower().replace("ch", "x").replace("kh", "x").replace("ph", "f").replace("w", "o").replace("ks", "ks")
    w = w.replace("au", "ay").replace("eu", "ey").replace("af", "ay").replace("ef", "ey").replace("av", "ay").replace("ev", "ey")
    w = w.replace("b", "v").replace("h", "i").replace("u", "y").replace("oy", "ou")
    return squeeze(w)


def tokens(name):
    """The words of a file name: "1_EPISTIMI_PAGKOSMIA_MERA.mp3" → ["PAGKOSMIA", "MERA"] (part number, programme, extension out)."""
    s = os.path.splitext(os.path.basename(name))[0]
    parts = [p for p in re.split(r"[\s_\-.()\[\]]+", s) if p]
    parts = [p for p in parts if not p.isdigit() and not re.fullmatch(r"(?i)(part|meros|cs)\d*", p)]
    while parts and parts[0].lower() in PROGRAMME:
        parts = parts[1:]
    return parts


def candidates(latin, lex):
    found = Counter()
    for k in latin_keys(latin):
        found.update(lex.get(k, {}))
    return found


def title(name, root=ROOT):
    """(Greek title, sure) from a Greeklish name; sure only if every word was found among the site's words."""
    lex = lexicon(root)
    toks = tokens(name)
    ws = [word(t, lex, first=(i == 0)) for i, t in enumerate(toks)]
    if not ws:
        return "", False
    text = " ".join(cased(w) for w, _ in ws)
    return text[:1].upper() + text[1:], all(ok for _, ok in ws)


def evaluate(root=ROOT):
    """The site's broadcasts: their mp3 names (Greeklish) turned into Greek and compared with their titles.

    Fair: the broadcast titles themselves are left out of the dictionary (as for a title never printed before), and
    only words that are the same word form in the name and in the title are counted (a name often shortens the title:
    "Genesi" for «της Γένεσης» is a different form, not a mistake). Returns (share of sure words spelled exactly right,
    share of words sure, share of names fully sure that came out exactly right)."""
    sys.path.insert(0, HERE)
    import inbox
    site = inbox.load_site(root)
    lex = lexicon(root, with_titles=False)
    total = sure = right = right_caps = names_sure = names_right = names_caps = 0
    same = lambda x: x.replace("Ι", "I").replace("Χ", "X")       # «ΙΙ» and "II" look the same
    for d, e in site["by_date"].items():
        title_words = [w for w in re.findall(r"[^\W\d_]+", e["title"])]
        rows = []
        toks = tokens(e["slug"])
        matches = [[w for w in title_words if greek_key(w) in latin_keys(t)] for t in toks]
        if not toks or not all(matches):
            continue                                          # the name is not a faithful copy of the title: skip it
        ws = [word(t, lex, first=(i == 0)) for i, t in enumerate(toks)]
        for (g, ok), match in zip(ws, matches):
            g = g if len(rows) == 0 else cased(g)
            rows.append((ok, same(g.lower()) == same(match[0].lower()), len(rows) == 0 or same(g) == same(match[0])))
        if not rows:
            continue
        for ok, exact, caps in rows:
            total += 1
            sure += ok
            right += ok and exact
            right_caps += ok and exact and caps
        if all(ok for ok, _, _ in rows):
            names_sure += 1
            names_right += all(exact for _, exact, _ in rows)
            names_caps += all(exact and caps for _, exact, caps in rows)
    print("words compared: %d; sure %.0f%%; of the sure ones spelled right (letters, accents) %.1f%%, "
          "with the same capitals as the title %.1f%%" % (total, 100 * sure / total, 100 * right / max(1, sure),
                                                           100 * right_caps / max(1, sure)))
    print("names with every word sure (would be published by themselves): %d; spelled right %.1f%%; "
          "same capitals as the title too %.1f%% (older titles use Title Case)"
          % (names_sure, 100 * names_right / max(1, names_sure), 100 * names_caps / max(1, names_sure)))
    return right / max(1, sure), sure / max(1, total), names_right / max(1, names_sure)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("name", nargs="?")
    ap.add_argument("--evaluate", action="store_true")
    a = ap.parse_args()
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass
    if a.evaluate:
        evaluate()
        return
    lex = lexicon()
    for t in tokens(a.name):
        g, ok = word(t, lex)
        print("  %-14s → %s%s" % (t, g, "" if ok else "  (not on the site: not sure)"))
    print("title: %r, sure: %s" % title(a.name))


if __name__ == "__main__":
    main()
