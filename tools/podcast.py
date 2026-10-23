"""The podcast feed: podcast.xml, which Spotify (and Apple Podcasts, YouTube Music, Amazon Music) read.

    python tools/podcast.py          (run by tools/build_all.py)
    python tools/podcast.py --check  also check that every mp3 in the feed can be downloaded (slow)

Every broadcast in js/broadcasts.js goes into the feed, newest first, with its date and season, its topics
and a link back to it on the site. Spotify copies the episodes from the feed by itself, and adds each new
broadcast once it is in the feed: nothing is uploaded by hand. Settings (SITE_CONFIG in js/broadcasts.js):

  podcastParts  true: each half-hour part is its own episode («… (1ο ημίωρο)»), using the part mp3s that are
                already online. false: one episode per broadcast, its whole-broadcast mp3
                (<date>_full.mp3, tools/join_broadcasts.py), once those are online. Switching keeps the show
                and its followers on Spotify; only the episode list changes.
  podcastSite   the address the site is at now (feed address, cover, links to the broadcasts)
  podcastAudio  where the mp3 folder is online, if not at podcastSite
  podcastEmail  Spotify sends its "is this your show?" code there; it is readable in the feed

Each mp3's size and length are measured here (ffprobe) and kept in data/podcast-audio.json, so the feed can
be made where the mp3s are not (the weekly GitHub run): an mp3 that is neither here nor in that file is left
out of the feed until it is. The cover is pictures/podcast-cover.jpg (tools/podcast_cover.js).
"""
import concurrent.futures, datetime, json, os, shutil, subprocess, sys, tempfile, urllib.parse, urllib.request
from email.utils import format_datetime
from xml.sax.saxutils import escape

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import seo

AUDIO = os.path.join(ROOT, "data", "podcast-audio.json")
OUT = os.path.join(ROOT, "podcast.xml")
COVER = "pictures/podcast-cover.jpg"
NAME = "Χριστιανισμός & Επιστήμη"
MONTHS = ["Ιανουαρίου", "Φεβρουαρίου", "Μαρτίου", "Απριλίου", "Μαΐου", "Ιουνίου", "Ιουλίου", "Αυγούστου",
          "Σεπτεμβρίου", "Οκτωβρίου", "Νοεμβρίου", "Δεκεμβρίου"]
DESCRIPTION = ("Ραδιοφωνική εκπομπή από το ράδιο «Χριστιανισμός». Μέσα από τις νεότερες ανακαλύψεις και τα "
               "θαύματα της Δημιουργίας που η σύγχρονη επιστήμη έρχεται να εξιχνιάσει, δείχνουμε ότι η Αγία Γραφή "
               "είναι ο Λόγος του Θεού. Ζωντανά κάθε δεύτερη Πέμπτη στις 22:00 (ώρα Ελλάδας). "
               "Όλες οι εκπομπές, με άρθρα και πηγές: %s")

LIST_JS = r"""
const fs = require("fs"), vm = require("vm");
const ctx = { window: {} }; vm.runInNewContext(fs.readFileSync(process.argv[2], "utf8"), ctx);
vm.runInNewContext(fs.readFileSync(process.argv[2].replace(/broadcasts\.js$/, "tags.js"), "utf8"), ctx);
const C = ctx.window.SITE_CONFIG, tags = {}, out = [];
for (const t of ctx.window.BROADCAST_TAGS || []) tags[t.id] = t.name;
for (const s of ctx.window.BROADCASTS) for (const e of s.episodes) {
  const id = e.date.replace(/-/g, "_"), parts = [];
  for (let n = 1; n <= e.parts; n++) parts.push(e.files ? e.files[n - 1] :
    (C.mp3Base || "") + "Season_" + (s.n < 10 ? "0" : "") + s.n + "/" + id + "/" + (e.cs ? "CS_" : "") + id + "_(" + n + ")_" + e.slug + ".mp3");
  out.push({ id, date: e.date, title: e.title, season: s.n, parts, link: e.link, tags: (e.tags || []).map((t) => tags[t] || t) });
}
console.log(JSON.stringify({ config: { email: C.podcastEmail || "", site: C.podcastSite || "", audio: C.podcastAudio || "",
  parts: !!C.podcastParts }, episodes: out }));
"""


def load():
    with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8") as f:
        f.write(LIST_JS)
    try:
        r = subprocess.run(["node", f.name, os.path.join(ROOT, "js", "broadcasts.js")], capture_output=True, check=True)
    finally:
        os.remove(f.name)
    return json.loads(r.stdout.decode("utf-8"))


def full_file(e):
    """The whole broadcast in one mp3 (the same rule as js/app.js and tools/join_broadcasts.py)."""
    if len(e["parts"]) == 1:
        return e["parts"][0]
    return os.path.dirname(e["parts"][0]) + "/" + e["id"] + "_full.mp3"


def seconds(path):
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "json", path], capture_output=True)
    try:
        return round(float(json.loads(r.stdout.decode("utf-8"))["format"]["duration"]))
    except (KeyError, ValueError):
        return None


def measure(files):
    """Size and length of each mp3 that is here, by its path; the rest from data/podcast-audio.json."""
    known = json.load(open(AUDIO, encoding="utf-8")) if os.path.exists(AUDIO) else {}
    if any("file" in v for v in known.values()):            # the first version kept one entry per broadcast
        known = {v["file"]: {"bytes": v["bytes"], "seconds": v["seconds"]} for v in known.values()}
    todo = []
    for rel in files:
        path = os.path.join(ROOT, rel)
        if os.path.exists(path):
            k = known.get(rel)
            if not k or k.get("bytes") != os.path.getsize(path) or not k.get("seconds"):
                todo.append((rel, path))
    with concurrent.futures.ThreadPoolExecutor(8) as pool:
        for (rel, path), s in zip(todo, pool.map(lambda t: seconds(t[1]), todo)):
            if s:
                known[rel] = {"bytes": os.path.getsize(path), "seconds": s}
    text = json.dumps(dict(sorted(known.items(), reverse=True)), ensure_ascii=False, indent=0) + "\n"
    if not os.path.exists(AUDIO) or open(AUDIO, encoding="utf-8").read() != text:
        with open(AUDIO, "w", encoding="utf-8", newline="\n") as f:
            f.write(text)
    return known, len(todo)


def athens(date, minutes):
    """22:00 Athens time on that day, plus some minutes (summer time from the last Sunday of March to the last
    Sunday of October)."""
    y, m, d = map(int, date.split("-"))
    def last_sunday(month):
        day = datetime.date(y, month, 31)
        return day - datetime.timedelta(days=(day.weekday() + 1) % 7)
    summer = last_sunday(3) <= datetime.date(y, m, d) < last_sunday(10)
    tz = datetime.timezone(datetime.timedelta(hours=3 if summer else 2))
    return datetime.datetime(y, m, d, 22, 0, tzinfo=tz) + datetime.timedelta(minutes=minutes)


def duration(s):
    return "%d:%02d:%02d" % (s // 3600, s % 3600 // 60, s % 60)


def item(e, rel, a, site, audio, n=None):
    """One episode: the whole broadcast, or (n = 1, 2, …) one of its half-hour parts."""
    y, m, d = map(int, e["date"].split("-"))
    page = site + "index.html#e-" + e["id"]
    of = len(e["parts"])
    title = e["title"] + (" (%dο ημίωρο)" % n if n and of > 1 else "")
    text = ["%s. Εκπομπή της %d %s %d (%dος κύκλος) από τη ραδιοφωνική σειρά «%s» του ράδιο «Χριστιανισμός»."
            % (e["title"].rstrip(".;"), d, MONTHS[m - 1], y, e["season"], NAME)]
    if n and of > 1:
        text.append("%dο από %d ημίωρα." % (n, of))
    if e["tags"]:
        text.append("Θέματα: " + ", ".join(e["tags"]) + ".")
    if e.get("link") and not e["link"].startswith("http"):
        text.append("Άρθρα και πηγές: " + site + e["link"])
    text.append("Ολόκληρη η εκπομπή στην ιστοσελίδα: " + page)
    # parts: part 1 gets the latest time, so the newest-first lists of the apps show 1, 2, 3, 4 in order
    when = athens(e["date"], 30 * (of - n) if n else 0)
    guid = "christianity-science-" + e["id"] + ("-%d" % n if n else "")
    return """    <item>
      <title>%s</title>
      <description>%s</description>
      <link>%s</link>
      <guid isPermaLink="false">%s</guid>
      <pubDate>%s</pubDate>
      <enclosure url="%s" length="%d" type="audio/mpeg"/>
      <itunes:duration>%s</itunes:duration>
      <itunes:season>%d</itunes:season>
      <itunes:episodeType>full</itunes:episodeType>
      <itunes:explicit>false</itunes:explicit>
    </item>
""" % (escape(title), escape("\n\n".join(text)), escape(page), guid, format_datetime(when),
       escape(audio + urllib.parse.quote(rel)), a["bytes"], duration(a["seconds"]), e["season"])


def check(urls):
    """Every mp3 in the feed answers, with the size the feed gives."""
    def head(u):
        if shutil.which("curl"):        # curl uses the system's certificates (Python's list can lag behind)
            r = subprocess.run(["curl", "-s", "-I", "-L", "--max-time", "120", u[0]], capture_output=True)
            code, size = None, -1
            for line in r.stdout.decode("latin-1").splitlines():
                k, _, v = line.partition(" ")
                if k.upper().startswith("HTTP/"):
                    code = v.split(" ")[0]
                elif k.lower() == "content-length:":
                    size = int(v.strip() or -1)
            if code != "200":
                return "%s: HTTP %s" % (u[0], code)
            return None if size in (-1, u[1]) else "%s: %d bytes online, %d in the feed" % (u[0], size, u[1])
        try:
            req = urllib.request.Request(u[0], method="HEAD", headers={"User-Agent": "Mozilla/5.0 podcast-check"})
            with urllib.request.urlopen(req, timeout=60) as r:
                size = int(r.headers.get("Content-Length") or -1)
                return None if size in (-1, u[1]) else "%s: %d bytes online, %d in the feed" % (u[0], size, u[1])
        except Exception as ex:
            return "%s: %s" % (u[0], ex)
    with concurrent.futures.ThreadPoolExecutor(8) as pool:
        bad = [b for b in pool.map(head, urls) if b]
    print("check: %d of %d mp3s answer as expected" % (len(urls) - len(bad), len(urls)))
    for b in bad[:20]:
        print("  " + b)
    return not bad


def main():
    data = load()
    cfg, episodes = data["config"], data["episodes"]
    # where the site is now (podcastSite), else its own address (tools/seo.py); the mp3s, if elsewhere
    site = (cfg["site"] or seo.SITE_URL).rstrip("/") + "/"
    audio = (cfg["audio"] or site).rstrip("/") + "/"
    # a broadcast's parts are listed last to first (4, 3, 2, 1), and part 1 has the latest time: the apps that sort
    # by time list 1, 2, 3, 4, and so does Spotify, which puts a day's episodes in reverse order of the feed
    wanted = [(e, n, rel) for e in episodes for n, rel in
              (list(enumerate(e["parts"], 1))[::-1] if cfg["parts"] else [(None, full_file(e))])]
    known, measured = measure([rel for _, _, rel in wanted])
    items, urls, left_out = [], [], []
    for e, n, rel in wanted:                             # js/broadcasts.js is newest first, as feeds should be
        a = known.get(rel)
        if a:
            items.append(item(e, rel, a, site, audio, n))
            urls.append((audio + urllib.parse.quote(rel), a["bytes"]))
        elif e["date"] not in left_out:
            left_out.append(e["date"])
    owner = ("    <itunes:owner>\n      <itunes:name>%s</itunes:name>\n      <itunes:email>%s</itunes:email>\n    </itunes:owner>\n"
             % (escape(NAME), escape(cfg["email"]))) if cfg["email"] else ""
    feed = """<?xml version="1.0" encoding="UTF-8"?>
<!-- Made by tools/podcast.py from js/broadcasts.js: do not edit by hand. -->
<rss version="2.0" xmlns:itunes="http://www.itunes.com/dtds/podcast-1.0.dtd" xmlns:atom="http://www.w3.org/2005/Atom">
  <channel>
    <title>%(name)s</title>
    <link>%(site)s</link>
    <atom:link href="%(site)spodcast.xml" rel="self" type="application/rss+xml"/>
    <itunes:new-feed-url>%(site)spodcast.xml</itunes:new-feed-url>
    <description>%(desc)s</description>
    <language>el</language>
    <copyright>%(name)s</copyright>
    <itunes:author>%(name)s</itunes:author>
%(owner)s    <itunes:image href="%(site)s%(cover)s"/>
    <image>
      <url>%(site)s%(cover)s</url>
      <title>%(name)s</title>
      <link>%(site)s</link>
    </image>
    <itunes:category text="Religion &amp; Spirituality">
      <itunes:category text="Christianity"/>
    </itunes:category>
    <itunes:explicit>false</itunes:explicit>
    <itunes:type>episodic</itunes:type>
%(items)s  </channel>
</rss>
""" % {"name": escape(NAME), "site": site, "desc": escape(DESCRIPTION % site), "owner": owner, "cover": COVER,
       "items": "".join(items)}
    old = open(OUT, encoding="utf-8").read() if os.path.exists(OUT) else None
    if feed != old:
        with open(OUT, "w", encoding="utf-8", newline="\n") as f:
            f.write(feed)
    print("podcast: %d episodes (%s) in podcast.xml%s%s" % (
        len(items), "half-hour parts" if cfg["parts"] else "whole broadcasts",
        " (%d mp3s measured)" % measured if measured else "",
        "; left out, no mp3 known: " + ", ".join(left_out) if left_out else ""))
    if "--check" in sys.argv and not check(urls):
        sys.exit(1)


if __name__ == "__main__":
    main()
