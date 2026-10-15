"""The inbox: publishes what the upload page (admin/) hands in. Nobody edits code to add a broadcast.

    python tools/inbox.py              publish everything waiting in the inbox on the server
    python tools/inbox.py --count      only say how many requests are waiting (for the workflow)
    python tools/inbox.py --local DIR  use the folder DIR as the "server" (tests, trial runs)
        --no-push    change the files here but do not commit or push    --no-build   skip tools/build_all.py

How it works. The upload page saves each request as a folder in the private inbox on the server
(private/inbox/<id>/: request.json, and the mp3s as part-1.mp3, part-2.mp3, ...). The folder only
appears there once it is complete. This tool then, for each one, oldest first:
  1. claims it by moving it to private/processing/<id> (a second run can no longer take it);
  2. checks it: the date, the title, the topics, that the files are real recordings, and that the
     broadcast is not already on the site (see "Never twice" below);
  3. for a broadcast: names the mp3s by the site's rule, joins them into the whole-broadcast mp3,
     uploads them to mp3/broadcasts/Season_NN/YYYY_MM_DD/ on the server, then adds the broadcast to
     js/broadcasts.js (and its English title to js/broadcasts-en.js, their sizes and lengths to
     data/podcast-audio.json), runs tools/build_all.py, commits and pushes; then tools/deploy.py puts the
     changed pages on the server. Spotify reads the new podcast.xml by itself.
  4. writes the outcome to private/results/<id>.json (the upload page shows it) and emails it, then
     moves the request to private/done/<id> (kept 30 days) or private/failed/<id> (kept until removed).
If anything goes wrong on the way (network, server), nothing half-done is published: the request goes
back to the inbox and is tried again on the next run; after 4 failed tries it is set aside and reported.

Never twice. A broadcast is known by its date (one broadcast per date, as in all 18 years so far):
  - a date already on the site is refused, unless the request says "replace" (the upload page asks);
  - a folder for that date already on the server with other files in it is refused;
  - recordings identical to an existing broadcast's (same SHA-256, or same size and length) are refused,
    whatever date they were given;
  - the same file twice in one request is refused;
  - right before the change is pushed, the newest version of the site is fetched and the date checked
    again, so a broadcast added meanwhile by hand (or by another run) is not added a second time.
Replacing keeps the date, the address and the podcast episode's id; the old files go to private/replaced/.

Requests of other kinds, from the same page: "settings" (the home page video, the next live broadcast)
and "correction" (a broadcast's title, English title or topics).

Optional: ANTHROPIC_API_KEY (an English title and topics are suggested by Claude when the admin leaves
them empty), SMTP_HOST / SMTP_PORT / SMTP_USER / SMTP_PASSWORD / MAIL_FROM / MAIL_TO (emails).
Server settings: see tools/serverfs.py.
"""
import argparse, datetime, hashlib, json, os, posixpath, re, shutil, smtplib, socket, subprocess, sys, tempfile, time
import unicodedata
from email.message import EmailMessage

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import serverfs
from join_broadcasts import join_files

ROOT = os.path.dirname(HERE)
MP3_BASE = "mp3/broadcasts/"
MAX_PARTS = 8
MIN_SECONDS = 60                 # a part shorter than a minute is not a recording of the broadcast
MAX_TRIES = 4
KEEP_DONE_DAYS = 30
STALE_HOURS = 3                  # a request "processing" for longer than this was left by a run that died
SITE_URL = "https://www.christianity-science.gr/"


class Reject(Exception):
    """The request cannot be published as it is; the message (Greek) tells the admin what to do."""


# ---------------------------------------------------------------- the site's broadcast list
LIST_JS = r"""
const fs = require("fs"), vm = require("vm"), path = require("path");
const ctx = { window: {} };
vm.runInNewContext(fs.readFileSync(path.join(process.argv[2], "js", "broadcasts.js"), "utf8"), ctx);
vm.runInNewContext(fs.readFileSync(path.join(process.argv[2], "js", "tags.js"), "utf8"), ctx);
const en = { window: {} };
vm.runInNewContext(fs.readFileSync(path.join(process.argv[2], "js", "broadcasts-en.js"), "utf8"), en);
const C = ctx.window.SITE_CONFIG, seasons = [];
for (const s of ctx.window.BROADCASTS) {
  const eps = [];
  for (const e of s.episodes) {
    const id = e.date.replace(/-/g, "_"), parts = [];
    for (let n = 1; n <= e.parts; n++) parts.push(e.files ? e.files[n - 1] :
      (C.mp3Base || "") + "Season_" + (s.n < 10 ? "0" : "") + s.n + "/" + id + "/" + (e.cs ? "CS_" : "") + id + "_(" + n + ")_" + e.slug + ".mp3");
    eps.push({ date: e.date, title: e.title, slug: e.slug, cs: e.cs, link: e.link, tags: e.tags, parts });
  }
  seasons.push({ n: s.n, span: s.span, episodes: eps });
}
console.log(JSON.stringify({ seasons, tags: (ctx.window.BROADCAST_TAGS || []).map((t) => t.id),
  en: en.window.BROADCAST_TITLES_EN || {}, config: { youtubeId: C.youtubeId, nextBroadcast: C.nextBroadcast } }));
"""


def load_site(root):
    with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8") as f:
        f.write(LIST_JS)
    try:
        r = subprocess.run(["node", f.name, root], capture_output=True)
    finally:
        os.remove(f.name)
    if r.returncode:
        raise RuntimeError("js/broadcasts.js could not be read: " + r.stderr.decode("utf-8", "replace")[-500:])
    d = json.loads(r.stdout.decode("utf-8"))
    d["by_date"] = {e["date"]: dict(e, season=s["n"]) for s in d["seasons"] for e in s["episodes"]}
    return d


def read_text(root, rel):
    with open(os.path.join(root, rel), encoding="utf-8") as f:
        return f.read()


def write_text(root, rel, text):
    with open(os.path.join(root, rel), "w", encoding="utf-8", newline="\n") as f:
        f.write(text)


def js_string(s):
    return json.dumps(s, ensure_ascii=False)


def ep_line(date, title, slug, parts, tags, link=None, cs=False):
    opts = []
    if cs:
        opts.append("cs: true")
    if parts != 4:
        opts.append("parts: %d" % parts)
    if link:
        opts.append("link: " + js_string(link))
    if tags:
        opts.append("tags: " + js_string(" ".join(tags)))
    return "ep(%s, %s, %s%s)" % (js_string(date), js_string(title), js_string(slug),
                                 ", { %s }" % ", ".join(opts) if opts else "")


EP_RE = r'^(?P<indent>\s*)ep\("%s", .*\)(?P<comma>,?)\s*$'


def put_broadcast(text, date, line, season, span, new_season):
    """js/broadcasts.js with `line` for `date`: replacing that date's line, or added to its season, newest first."""
    m = re.search(EP_RE % re.escape(date), text, re.M)
    if m:
        return text[:m.start()] + m.group("indent") + line + m.group("comma") + text[m.end():]
    if new_season:
        anchor = re.search(r"^\s*window\.BROADCASTS = \[\n", text, re.M)
        block = '    season(%d, %s, [\n      %s\n    ]),\n' % (season, js_string(span), line)
        return text[:anchor.end()] + block + text[anchor.end():]
    anchor = re.search(r'^\s*season\(%d, "[^"]*", \[\n' % season, text, re.M)
    if not anchor:
        raise RuntimeError("season %d not found in js/broadcasts.js" % season)
    close = re.compile(r"^\s*\]\)", re.M).search(text, anchor.end()).start()
    eps = list(re.finditer(r'^(\s*)ep\("(\d{4}-\d\d-\d\d)", .*?(,?)\n', text[anchor.end():close], re.M))
    for em in eps:
        if em.group(2) < date:                    # the first older broadcast: the new one goes before it
            pos = anchor.end() + em.start()
            return text[:pos] + "      " + line + ",\n" + text[pos:]
    if not eps:
        return text[:anchor.end()] + "      " + line + "\n" + text[anchor.end():]
    last = eps[-1]                                # older than all: after the last one, which then needs a comma
    end = anchor.end() + last.end() - 1
    return text[:end] + ("" if last.group(3) else ",") + "\n      " + line + text[end:]


def put_en_title(text, date, title):
    line = "  %s: %s," % (js_string(date), js_string(title))
    m = re.search(r'^\s*"%s": .*$' % re.escape(date), text, re.M)
    if m:
        return text[:m.start()] + line + text[m.end():]
    anchor = re.search(r"^window\.BROADCAST_TITLES_EN = \{\n", text, re.M)
    for em in re.finditer(r'^\s*"(\d{4}-\d\d-\d\d)": .*\n', text[anchor.end():], re.M):
        if em.group(1) < date:
            pos = anchor.end() + em.start()
            return text[:pos] + line + "\n" + text[pos:]
    pos = anchor.end()
    return text[:pos] + line + "\n" + text[pos:]


def put_config(text, key, value):
    new, n = re.subn(r'^(\s*%s: )"[^"]*"' % re.escape(key), lambda m: m.group(1) + js_string(value), text, count=1, flags=re.M)
    if not n:
        raise RuntimeError("SITE_CONFIG.%s not found" % key)
    return new


# ---------------------------------------------------------------- checks
def valid_date(s):
    try:
        return datetime.date.fromisoformat(s) if re.fullmatch(r"\d{4}-\d\d-\d\d", s or "") else None
    except ValueError:
        return None


def clean_text(s, what, required=True, longest=200):
    s = re.sub(r"\s+", " ", str(s or "")).strip()
    if not s:
        if required:
            raise Reject("Λείπει %s." % what)
        return ""
    if len(s) > longest or re.search(r"[\x00-\x1f<>]", s):
        raise Reject("Το πεδίο «%s» δεν είναι έγκυρο (πολύ μεγάλο ή με μη επιτρεπτούς χαρακτήρες)." % what)
    return s


def clean_tags(tags, known):
    tags = [t for t in (tags or []) if t]
    unknown = [t for t in tags if t not in known]
    if unknown:
        raise Reject("Άγνωστα θέματα: %s." % ", ".join(unknown))
    if len(tags) > 3 or len(set(tags)) != len(tags):
        raise Reject("Επιλέξτε έως 3 διαφορετικά θέματα.")
    return tags


def season_for(date, site):
    """(season number, span, is_new) for a broadcast date. A season runs from August to July."""
    d = datetime.date.fromisoformat(date)
    start = d.year if d.month >= 8 else d.year - 1
    for s in site["seasons"]:
        if s["span"].startswith(str(start) + " "):
            return s["n"], s["span"], False
    top = site["seasons"][0]
    top_start = int(top["span"][:4])
    if start > top_start:
        return top["n"] + 1, "%d – %d" % (start, start + 1), True
    raise Reject("Η ημερομηνία %s δεν ανήκει σε κανέναν κύκλο εκπομπών της ιστοσελίδας." % date)


GREEK = dict(zip("αβγδεζηθικλμνξοπρσςτυφχψω", ["a", "b", "g", "d", "e", "z", "i", "th", "i", "k", "l", "m", "n", "ks",
                                               "o", "p", "r", "s", "s", "t", "y", "f", "x", "ps", "o"]))


def slugify(title):
    """A file-name-safe Latin version of the title, like the site's other mp3 names ("Nous_se_kindyno")."""
    plain = "".join(c for c in unicodedata.normalize("NFD", title.lower()) if unicodedata.category(c) != "Mn")
    latin = "".join(GREEK.get(c, c) for c in plain.replace("ου", "ou"))
    words = re.findall(r"[a-z0-9]+", latin)[:4]
    slug = "_".join(words)[:40].strip("_")
    return (slug[:1].upper() + slug[1:]) if slug else "Ekpompi"


def probe(path):
    """(seconds, is_mp3) of an audio file, or (None, False) if it is not one."""
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration,format_name", "-of", "json", path],
                       capture_output=True)
    try:
        f = json.loads(r.stdout.decode("utf-8"))["format"]
        return round(float(f["duration"])), "mp3" in f.get("format_name", "")
    except (KeyError, ValueError, json.JSONDecodeError):
        return None, False


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def same_recording(audio, files, except_date=None):
    """The date of a broadcast whose mp3 is identical to one of `files` [(bytes, seconds, sha)], or None."""
    for rel, a in audio.items():
        m = re.search(r"/(\d{4})_(\d\d)_(\d\d)/", rel)
        date = "%s-%s-%s" % m.groups() if m else "?"
        if date == except_date:
            continue
        for size, secs, sha in files:
            if a.get("sha256") and a["sha256"] == sha:
                return date
            if a.get("bytes") == size and abs((a.get("seconds") or -9) - secs) <= 1:
                return date
    return None


# ---------------------------------------------------------------- Claude suggestions (optional)
def suggest(title, topics, examples):
    """{"title_en": ..., "tags": [...]} suggested by Claude for a Greek broadcast title, or None.

    Never required: without ANTHROPIC_API_KEY, without the anthropic package, or if the request fails,
    the broadcast is published without them (the Greek title is shown on the English site meanwhile).
    """
    if not os.environ.get("ANTHROPIC_API_KEY"):
        return None
    try:
        import anthropic
    except ImportError:
        return None
    topic_list = "\n".join("- %s: %s / %s" % t for t in topics)
    shots = "\n".join("%s => %s" % (g, e) for g, e in examples)
    prompt = (
        "You help publish broadcasts of «Χριστιανισμός & Επιστήμη» (Christianity & Science), a Greek Orthodox "
        "Christian radio programme about faith and science.\n\n"
        "Translate the broadcast title below into English, in the same style as these earlier titles "
        "(British English, sentence case, concise; keep «…» quotations and part numbers as \"– Part 2\"):\n"
        + shots + "\n\nThen choose 1 to 3 topics for it from this list, the most relevant first, by key:\n"
        + topic_list + "\n\nBroadcast title: " + title)
    schema = {"type": "object", "additionalProperties": False, "required": ["title_en", "tags"],
              "properties": {"title_en": {"type": "string"},
                             "tags": {"type": "array", "items": {"type": "string", "enum": [t[0] for t in topics]}}}}
    try:
        client = anthropic.Anthropic(timeout=120, max_retries=2)
        r = client.beta.messages.create(
            model="claude-opus-5-5", max_tokens=16000,
            betas=["server-side-fallback-2026-07-01"], fallbacks="default",
            output_config={"effort": "low", "format": {"type": "json_schema", "schema": schema}},
            messages=[{"role": "user", "content": prompt}])
        if r.stop_reason != "end_turn":
            print("  Claude: no suggestion (%s)" % r.stop_reason)
            return None
        text = "".join(b.text for b in r.content if b.type == "text")
        out = json.loads(text)
        tags = [t for t in out.get("tags", []) if t in {k for k, _, _ in topics}][:3]
        return {"title_en": clean_text(out.get("title_en"), "English title", required=False), "tags": tags}
    except anthropic.APIConnectionError as ex:
        print("  Claude: could not connect (%s); going on without a suggestion" % ex)
    except anthropic.APIStatusError as ex:
        print("  Claude: error %s (%s); going on without a suggestion" % (ex.status_code, ex.message))
    except (ValueError, Reject) as ex:
        print("  Claude: unusable answer (%s); going on without a suggestion" % ex)
    return None


def topic_names(root):
    names = re.findall(r'id: "([a-z]+)",\s*name: "([^"]+)",\s*en: "([^"]+)"', read_text(root, "js/tags.js"))
    return names


# ---------------------------------------------------------------- the site's git copy
class Git:
    def __init__(self, root, push):
        self.root, self.push = root, push
        self.branch = self.run("rev-parse", "--abbrev-ref", "HEAD").strip() if push else None

    def run(self, *args, check=True):
        r = subprocess.run(["git", *args], cwd=self.root, capture_output=True)
        if check and r.returncode:
            raise RuntimeError("git %s: %s" % (args[0], r.stderr.decode("utf-8", "replace").strip()[-400:]))
        return r.stdout.decode("utf-8", "replace")

    def ready(self):
        """Only work on a clean copy that has nothing unpushed (so nobody's own work is published or lost)."""
        if not self.push:
            return
        if self.run("status", "--porcelain").strip():
            raise SystemExit("This copy of the site has uncommitted changes; commit or put them aside first.")
        self.run("fetch", "origin", self.branch)
        if self.run("rev-list", "--count", "origin/%s..HEAD" % self.branch).strip() != "0":
            raise SystemExit("This copy has commits that are not pushed yet; push them first.")

    def refresh(self):
        if self.push:
            self.run("fetch", "origin", self.branch)
            self.run("reset", "--hard", "origin/" + self.branch)

    def commit_push(self, message):
        """True if pushed (or nothing to push); False if someone else pushed first (start again)."""
        if not self.push:
            return True
        self.run("add", "-A")
        if not self.run("status", "--porcelain").strip():
            return True
        self.run("commit", "-q", "-m", message)
        r = subprocess.run(["git", "push", "-q", "origin", "HEAD:" + self.branch], cwd=self.root, capture_output=True)
        if r.returncode == 0:
            return True
        self.run("reset", "-q", "--hard", "origin/" + self.branch)
        return False


# ---------------------------------------------------------------- one request
class Inbox:
    def __init__(self, srv, root, push=True, build=True, keep_local=None, log=print):
        self.srv, self.root, self.build, self.log = srv, root, build, log
        self.git = Git(root, push)
        self.keep_local = os.path.isdir(os.path.join(root, "mp3")) if keep_local is None else keep_local
        self.audio_path = os.path.join(root, "data", "podcast-audio.json")

    # -- changes to the site's files, built, committed and pushed; started again if someone pushed meanwhile
    def change_site(self, message, apply):
        for attempt in range(3):
            self.git.refresh()
            summary = apply(load_site(self.root))
            if self.build:
                r = subprocess.run([sys.executable, os.path.join(self.root, "tools", "build_all.py")],
                                   cwd=self.root, capture_output=True)
                if r.returncode:
                    raise RuntimeError("tools/build_all.py failed: " + r.stdout.decode("utf-8", "replace")[-800:]
                                       + r.stderr.decode("utf-8", "replace")[-800:])
            if self.git.commit_push(message):
                return summary
            self.log("  someone else changed the site meanwhile; starting again from the newest version")
        raise serverfs.ServerError("could not push the change (the site kept changing)")

    def load_audio(self):
        with open(self.audio_path, encoding="utf-8") as f:
            return json.load(f)

    def save_audio(self, audio):
        with open(self.audio_path, "w", encoding="utf-8", newline="\n") as f:
            f.write(json.dumps(dict(sorted(audio.items(), reverse=True)), ensure_ascii=False, indent=0) + "\n")

    # -- a new broadcast (or a replacement)
    def broadcast(self, req, folder, work):
        site = load_site(self.root)
        date = req.get("date", "")
        if not valid_date(date):
            raise Reject("Η ημερομηνία «%s» δεν είναι έγκυρη." % date)
        title = clean_text(req.get("title"), "ο τίτλος")
        title_en = clean_text(req.get("title_en"), "ο αγγλικός τίτλος", required=False)
        tags = clean_tags(req.get("tags"), set(site["tags"]))
        replace = bool(req.get("replace"))
        old = site["by_date"].get(date)
        if old and not replace:
            raise Reject("Η εκπομπή της %s υπάρχει ήδη στην ιστοσελίδα («%s»). Δεν προστέθηκε ξανά. "
                         "Αν θέλετε να την αντικαταστήσετε, στείλτε την ξανά με την επιλογή «Αντικατάσταση»."
                         % (greek_date(date), old["title"]))
        files = req.get("files") or []
        if not 1 <= len(files) <= MAX_PARTS:
            raise Reject("Χρειάζονται 1 έως %d αρχεία mp3 (στάλθηκαν %d)." % (MAX_PARTS, len(files)))

        # the recordings: fetched, checked, measured
        local, measured = [], []
        for i, f in enumerate(files, 1):
            name = "part-%d.mp3" % i
            if f.get("name") != name:
                raise Reject("Τα αρχεία του αιτήματος δεν είναι πλήρη.")
            path = os.path.join(work, name)
            self.srv.download("private", folder + "/" + name, path)
            if os.path.getsize(path) != f.get("bytes"):
                raise Reject("Το αρχείο «%s» δεν ανέβηκε ολόκληρο. Στείλτε την εκπομπή ξανά." % f.get("original", name))
            secs, is_mp3 = probe(path)
            if not secs or not is_mp3:
                raise Reject("Το αρχείο «%s» δεν είναι ηχογράφηση mp3." % f.get("original", name))
            if secs < MIN_SECONDS:
                raise Reject("Το αρχείο «%s» διαρκεί μόνο %d δευτερόλεπτα." % (f.get("original", name), secs))
            local.append(path)
            measured.append((os.path.getsize(path), secs, sha256(path)))
        if len({m[2] for m in measured}) != len(measured):
            raise Reject("Το ίδιο αρχείο στάλθηκε δύο φορές στην ίδια εκπομπή.")
        twin = same_recording(self.load_audio(), measured, except_date=date if replace else None)
        if twin:
            raise Reject("Αυτές οι ηχογραφήσεις είναι ίδιες με της εκπομπής της %s, που υπάρχει ήδη. Δεν προστέθηκαν."
                         % greek_date(twin))

        # names by the site's rule
        season, span, new_season = season_for(date, site)
        ident = date.replace("-", "_")
        slug = slugify(title)
        mp3_dir = "%sSeason_%02d/%s" % (MP3_BASE, season, ident)
        names = ["%s_(%d)_%s.mp3" % (ident, i, slug) for i in range(1, len(local) + 1)]
        uploads = list(zip(local, names, measured))
        if len(local) > 1:
            full = os.path.join(work, ident + "_full.mp3")
            out = join_files(local, full, title, season, date)
            if not out.startswith("joined"):
                raise RuntimeError("joining the parts: " + out)
            secs, _ = probe(full)
            uploads.append((full, ident + "_full.mp3", (os.path.getsize(full), secs, sha256(full))))

        # the server's folder for this date
        self.git.refresh()
        if load_site(self.root)["by_date"].get(date) and not replace:
            raise Reject("Η εκπομπή της %s προστέθηκε στο μεταξύ (από άλλον). Δεν προστέθηκε ξανά." % greek_date(date))
        there = {n: s for n, s in self.srv.list("site", mp3_dir).items() if s != "dir" and not n.endswith(".uploading")}
        set_aside = None
        if there:
            if old and replace:
                set_aside = "replaced/%s-%s" % (ident, time.strftime("%Y%m%d-%H%M%S"))
                self.log("  the old files go to private/" + set_aside)
                self.srv.move("site", mp3_dir, "private", set_aside)
                there = {}
            elif all(there.get(n) == m[0] for _, n, m in uploads) and set(there) == {n for _, n, _ in uploads}:
                self.log("  the files are already on the server (an earlier try); not uploading them again")
            else:
                raise Reject("Στον server υπάρχει ήδη φάκελος για την εκπομπή της %s με άλλα αρχεία, χωρίς να "
                             "υπάρχει η εκπομπή στην ιστοσελίδα. Ελέγξτε τον φάκελο %s (π.χ. από το File Manager) "
                             "πριν τη στείλετε ξανά." % (greek_date(date), mp3_dir))
        try:
            for path, name, m in uploads:
                if there.get(name) != m[0]:
                    self.log("  uploading %s (%.1f MB)" % (name, m[0] / 1e6))
                    self.srv.upload(path, "site", mp3_dir + "/" + name)
        except Exception:
            if set_aside:                         # put the old recordings back, so the site keeps working
                self.srv.remove("site", mp3_dir)
                self.srv.move("private", set_aside, "site", mp3_dir)
            raise
        if self.keep_local:
            os.makedirs(os.path.join(self.root, mp3_dir), exist_ok=True)
            for path, name, m in uploads:
                shutil.copyfile(path, os.path.join(self.root, mp3_dir, name))

        # English title and topics: the admin's, else Claude's suggestion
        if not title_en or not tags:
            topics = topic_names(self.root)
            examples = [(site["by_date"][d]["title"], t) for d, t in list(site["en"].items())[:20] if d in site["by_date"]]
            s = suggest(title, topics, examples) or {}
            title_en = title_en or s.get("title_en", "")
            tags = tags or s.get("tags", [])

        def apply(site):
            if site["by_date"].get(date) and not replace:
                raise Reject("Η εκπομπή της %s προστέθηκε στο μεταξύ (από άλλον). Δεν προστέθηκε ξανά." % greek_date(date))
            was = site["by_date"].get(date)
            line = ep_line(date, title, slug, len(local), tags, link=(was or {}).get("link"))
            js = read_text(self.root, "js/broadcasts.js")
            write_text(self.root, "js/broadcasts.js", put_broadcast(js, date, line, season, span, new_season and not
                                                                    any(s["n"] == season for s in site["seasons"])))
            if title_en:
                write_text(self.root, "js/broadcasts-en.js", put_en_title(read_text(self.root, "js/broadcasts-en.js"), date, title_en))
            audio = {k: v for k, v in self.load_audio().items() if not (was and "/%s/" % ident in k)}
            for _, name, (size, secs, sha) in uploads:
                audio[mp3_dir + "/" + name] = {"bytes": size, "seconds": secs, "sha256": sha}
            self.save_audio(audio)
            return None

        verb = "Αντικατάσταση" if old else "Νέα εκπομπή"
        self.change_site("%s %s: %s (from the upload page)" % ("Replace broadcast" if old else "Broadcast", date, title), apply)
        notes = []
        if not title_en:
            notes.append("δεν έχει αγγλικό τίτλο (στα αγγλικά φαίνεται ο ελληνικός)")
        if not tags:
            notes.append("δεν έχει θέματα")
        msg = "%s: «%s» (%s, %d ημίωρα) δημοσιεύτηκε. Η ιστοσελίδα ενημερώνεται σε λίγα λεπτά και το Spotify μέσα σε λίγες ώρες." \
              % (verb, title, greek_date(date), len(local))
        if notes:
            msg += " Σημείωση: " + " και ".join(notes) + "· μπορείτε να τα προσθέσετε με «Διόρθωση εκπομπής»."
        return msg, {"date": date, "title": title, "title_en": title_en, "tags": tags,
                     "link": SITE_URL + "index.html#e-" + ident}

    # -- corrections to a broadcast that is online
    def correction(self, req, folder, work):
        site = load_site(self.root)
        date = req.get("date", "")
        if date not in site["by_date"]:
            raise Reject("Δεν υπάρχει εκπομπή της %s για να διορθωθεί." % (greek_date(date) if valid_date(date) else date))
        title = clean_text(req.get("title"), "ο τίτλος", required=False)
        title_en = clean_text(req.get("title_en"), "ο αγγλικός τίτλος", required=False)
        tags = clean_tags(req.get("tags"), set(site["tags"])) if req.get("tags") is not None else None
        if not title and not title_en and tags is None:
            raise Reject("Δεν δόθηκε καμία αλλαγή.")

        def apply(site):
            e = site["by_date"].get(date)
            if not e:
                raise Reject("Η εκπομπή της %s δεν υπάρχει πια στην ιστοσελίδα." % greek_date(date))
            if title or tags is not None:
                js = read_text(self.root, "js/broadcasts.js")
                m = re.search(EP_RE % re.escape(date), js, re.M)
                line = m.group(0).strip().rstrip(",")
                files_opt = re.search(r"files: \[[^\]]*\]", line)
                if files_opt:
                    raise Reject("Αυτή η εκπομπή έχει ειδική λίστα αρχείων· η διόρθωση γίνεται από τον διαχειριστή του κώδικα.")
                new = ep_line(date, title or e["title"], e["slug"], len(e["parts"]),
                              e["tags"] if tags is None else tags, link=e.get("link"), cs=e.get("cs"))
                write_text(self.root, "js/broadcasts.js", js[:m.start()] + m.group("indent") + new + m.group("comma") + js[m.end():])
            if title_en:
                write_text(self.root, "js/broadcasts-en.js", put_en_title(read_text(self.root, "js/broadcasts-en.js"), date, title_en))

        self.change_site("Correct broadcast %s (from the upload page)" % date, apply)
        return "Η εκπομπή της %s διορθώθηκε. Η ιστοσελίδα ενημερώνεται σε λίγα λεπτά." % greek_date(date), {"date": date}

    # -- home page settings
    def settings(self, req, folder, work):
        video = (req.get("youtube") or "").strip()
        nxt = (req.get("next_broadcast") or "").strip()
        vid = None
        if video:
            m = re.search(r"(?:youtu\.be/|[?&]v=|/embed/|/shorts/|/live/)([\w-]{11})", video) or re.fullmatch(r"([\w-]{11})", video)
            if not m:
                raise Reject("Ο σύνδεσμος «%s» δεν είναι σύνδεσμος βίντεο του YouTube." % video)
            vid = m.group(1)
        when = None
        if nxt:
            m = re.fullmatch(r"(\d{4}-\d\d-\d\d)T(\d\d):(\d\d)", nxt)
            if not m or not valid_date(m.group(1)) or int(m.group(2)) > 23 or int(m.group(3)) > 59:
                raise Reject("Η ημερομηνία της επόμενης εκπομπής δεν είναι έγκυρη.")
            when = "%s:00%s" % (nxt, athens_offset(m.group(1)))
        if not vid and not when:
            raise Reject("Δεν δόθηκε καμία αλλαγή.")

        def apply(site):
            js = read_text(self.root, "js/broadcasts.js")
            if vid:
                js = put_config(js, "youtubeId", vid)
            if when:
                js = put_config(js, "nextBroadcast", when)
            write_text(self.root, "js/broadcasts.js", js)

        self.change_site("Home page settings (from the upload page)", apply)
        done = []
        if vid:
            done.append("το βίντεο της αρχικής σελίδας άλλαξε")
        if when:
            done.append("η επόμενη ζωντανή εκπομπή ορίστηκε στις %s %s" % (greek_date(nxt[:10]), nxt[11:]))
        return ("Έγινε: " + " και ".join(done) + ". Η ιστοσελίδα ενημερώνεται σε λίγα λεπτά."), {}

    # -- the inbox as a whole
    def run(self):
        self.git.ready()
        self.recover_stale()
        waiting = sorted(n for n, k in self.srv.list("private", "inbox").items() if k == "dir" and not n.startswith("."))
        failures = 0
        for ident in waiting:
            failures += not self.handle(ident)
        self.clean_up()
        return failures

    def handle(self, ident):
        """Process one request. False if it failed for a reason worth alerting the site's owner about."""
        try:
            self.srv.rename("private", "inbox/" + ident, "processing/" + ident)
        except serverfs.ServerError:
            self.log("%s: taken by another run" % ident)
            return True
        folder = "processing/" + ident
        self.srv.write("private", folder + "/claimed.json",
                       json.dumps({"time": time.time(), "by": socket.gethostname()}).encode())
        raw = self.srv.read("private", folder + "/request.json")
        tries = json.loads(self.srv.read("private", folder + "/tries.json") or b'{"tries": 0}')["tries"] + 1
        req = {}
        status, message, extra, ok = "error", "", {}, True
        work = tempfile.mkdtemp(prefix="cs-inbox-")
        try:
            req = json.loads(raw or b"null")
            if not isinstance(req, dict):
                raise Reject("Το αίτημα είναι κενό ή κατεστραμμένο.")
            kind = req.get("type")
            self.log("%s: %s %s %s" % (ident, kind, req.get("date", ""), req.get("title", "")))
            handler = {"broadcast": self.broadcast, "correction": self.correction, "settings": self.settings}.get(kind)
            if not handler:
                raise Reject("Άγνωστο είδος αιτήματος «%s»." % kind)
            message, extra = handler(req, folder, work)
            status, dest = "published", "done/" + ident
        except Reject as ex:
            status, message, dest = "rejected", str(ex), "failed/" + ident
        except Exception as ex:                               # network, server, a bug: try again later
            ok = False
            self.log("  ERROR: %s: %s" % (type(ex).__name__, ex))
            if tries >= MAX_TRIES:
                status, dest = "error", "failed/" + ident
                message = ("Η δημοσίευση απέτυχε %d φορές (%s). Ο διαχειριστής της ιστοσελίδας ειδοποιήθηκε. "
                           "Τα αρχεία κρατήθηκαν· δεν χρειάζεται να τα στείλετε ξανά." % (tries, ex))
            else:
                status, dest = "retrying", "inbox/" + ident
                message = "Προσωρινό πρόβλημα (%s). Θα ξαναδοκιμαστεί αυτόματα." % ex
                self.srv.write("private", folder + "/tries.json", json.dumps({"tries": tries}).encode())
        finally:
            shutil.rmtree(work, ignore_errors=True)
        self.log("  -> %s: %s" % (status, message))
        result = {"id": ident, "type": req.get("type"), "status": status, "message": message, "time": time.time(),
                  "user": req.get("user"), "date": req.get("date"), "title": req.get("title"), **extra}
        try:
            self.srv.write("private", "results/%s.json" % ident, json.dumps(result, ensure_ascii=False, indent=1).encode())
            self.srv.remove("private", folder + "/claimed.json")
            self.srv.rename("private", folder, dest)
        except serverfs.ServerError as ex:
            self.log("  could not file the request away: %s" % ex)
            ok = False
        if status != "retrying":
            notify(result, req)
        return ok

    def recover_stale(self):
        """Requests left in processing/ by a run that stopped half-way go back to the inbox."""
        for ident, kind in self.srv.list("private", "processing").items():
            if kind != "dir":
                continue
            claimed = json.loads(self.srv.read("private", "processing/%s/claimed.json" % ident) or b'{"time": 0}')
            if time.time() - claimed.get("time", 0) > STALE_HOURS * 3600:
                self.log("%s: left half-done by an earlier run; back to the inbox" % ident)
                self.srv.remove("private", "processing/%s/claimed.json" % ident)
                self.srv.rename("private", "processing/" + ident, "inbox/" + ident)

    def clean_up(self):
        """Requests published more than 30 days ago are removed (their mp3s are on the site by then)."""
        for ident, kind in self.srv.list("private", "done").items():
            m = re.match(r"(\d{8})-", ident)
            if kind == "dir" and m:
                age = datetime.date.today() - datetime.datetime.strptime(m.group(1), "%Y%m%d").date()
                if age.days > KEEP_DONE_DAYS:
                    self.srv.remove("private", "done/" + ident)


MONTHS = ["Ιανουαρίου", "Φεβρουαρίου", "Μαρτίου", "Απριλίου", "Μαΐου", "Ιουνίου", "Ιουλίου", "Αυγούστου",
          "Σεπτεμβρίου", "Οκτωβρίου", "Νοεμβρίου", "Δεκεμβρίου"]


def greek_date(date):
    y, m, d = map(int, date.split("-"))
    return "%d %s %d" % (d, MONTHS[m - 1], y)


def athens_offset(date):
    """+03:00 in Greek summer time (last Sunday of March to last Sunday of October), else +02:00."""
    y, m, d = map(int, date.split("-"))

    def last_sunday(month):
        day = datetime.date(y, month, 31)
        return day - datetime.timedelta(days=(day.weekday() + 1) % 7)
    return "+03:00" if last_sunday(3) <= datetime.date(y, m, d) < last_sunday(10) else "+02:00"


def notify(result, req):
    """Email the outcome to the admin who sent it (and MAIL_TO). Optional: needs the SMTP settings."""
    host = os.environ.get("SMTP_HOST")
    to = [a for a in {req.get("email"), *os.environ.get("MAIL_TO", "").split(",")} if a and "@" in a]
    if not host or not to:
        return
    icon = {"published": "✓", "rejected": "✗", "error": "✗"}.get(result["status"], "•")
    what = result.get("title") or {"settings": "Ρυθμίσεις αρχικής σελίδας", "correction": "Διόρθωση εκπομπής"}.get(result.get("type"), "Αίτημα")
    msg = EmailMessage()
    msg["Subject"] = "%s %s" % (icon, what)
    msg["From"] = os.environ.get("MAIL_FROM") or os.environ.get("SMTP_USER")
    msg["To"] = ", ".join(sorted(to))
    msg.set_content(result["message"] + ("\n\n" + result["link"] if result.get("link") else "")
                    + "\n\n— Χριστιανισμός & Επιστήμη, αυτόματο μήνυμα")
    port = int(os.environ.get("SMTP_PORT", "465"))
    try:
        if port == 465:
            s = smtplib.SMTP_SSL(host, port, timeout=60)
        else:
            s = smtplib.SMTP(host, port, timeout=60)
            s.starttls()
        with s:
            if os.environ.get("SMTP_USER"):
                s.login(os.environ["SMTP_USER"], os.environ.get("SMTP_PASSWORD", ""))
            s.send_message(msg)
    except (OSError, smtplib.SMTPException) as ex:
        print("  (email not sent: %s)" % ex)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--local", help="a folder standing in for the server")
    ap.add_argument("--root", default=ROOT, help=argparse.SUPPRESS)
    ap.add_argument("--count", action="store_true")
    ap.add_argument("--no-push", action="store_true")
    ap.add_argument("--no-build", action="store_true")
    a = ap.parse_args(argv)
    if not a.local and not serverfs.configured():
        print("The server is not set up yet (FTP settings missing); nothing to do.")
        return 0
    srv = serverfs.connect(a.local)
    try:
        if a.count:
            n = sum(1 for k, v in srv.list("private", "inbox").items() if v == "dir" and not k.startswith("."))
            n += sum(1 for v in srv.list("private", "processing").values() if v == "dir")
            print(n)
            if os.environ.get("GITHUB_OUTPUT"):
                with open(os.environ["GITHUB_OUTPUT"], "a") as f:
                    f.write("waiting=%d\n" % n)
            return 0
        box = Inbox(srv, a.root, push=not a.no_push, build=not a.no_build)
        return 1 if box.run() else 0
    finally:
        srv.close()


if __name__ == "__main__":
    sys.exit(main())
