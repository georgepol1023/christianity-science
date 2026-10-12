"""The podcast feed: podcast.xml, which Spotify (and Apple Podcasts, YouTube Music, Amazon Music) read.

    python tools/podcast.py          (run by tools/build_all.py)

Every broadcast in js/broadcasts.js becomes an episode, newest first: its whole-broadcast mp3
(mp3/broadcasts/…/<date>_full.mp3, made by tools/join_broadcasts.py; the single part when there is only
one), its date and season, its topics and a link back to it on the site. Spotify copies the episodes from
the feed by itself, and adds each new broadcast once it is in the feed: nothing is uploaded by hand.

Settings are in SITE_CONFIG in js/broadcasts.js: podcastEmail (Spotify sends its "is this your show?" code
there; it is readable in the feed) and podcastSite (the address the site is at now; links, cover and mp3s). The cover is pictures/podcast-cover.jpg (tools/podcast_cover.js).

Each mp3's size and length are measured here (ffprobe) and kept in data/podcast-audio.json, so the feed can
be made where the mp3s are not (the weekly GitHub run): a broadcast whose mp3 is neither here nor in that
file is left out of the feed until it is.
"""
import concurrent.futures, datetime, json, os, subprocess, sys, tempfile
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
const C = ctx.window.SITE_CONFIG, tags = {}, out = [];
for (const t of ctx.window.BROADCAST_TAGS || []) tags[t.id] = t.name;
for (const s of ctx.window.BROADCASTS) for (const e of s.episodes) {
  const id = e.date.replace(/-/g, "_"), parts = [];
  for (let n = 1; n <= e.parts; n++) parts.push(e.files ? e.files[n - 1] :
    (C.mp3Base || "") + "Season_" + (s.n < 10 ? "0" : "") + s.n + "/" + id + "/" + (e.cs ? "CS_" : "") + id + "_(" + n + ")_" + e.slug + ".mp3");
  out.push({ id, date: e.date, title: e.title, season: s.n, parts, link: e.link, tags: (e.tags || []).map((t) => tags[t] || t) });
}
console.log(JSON.stringify({ config: { email: C.podcastEmail || "", site: C.podcastSite || "" }, episodes: out }));
"""


def load():
    with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8") as f:
        f.write(LIST_JS)
    try:
        r = subprocess.run(["node", f.name, os.path.join(ROOT, "js", "broadcasts.js")], capture_output=True, check=True)
    finally:
        os.remove(f.name)
    return json.loads(r.stdout.decode("utf-8"))


def audio_file(e):
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


def measure(episodes):
    """Size and length of each mp3 that is here; the rest from data/podcast-audio.json."""
    known = json.load(open(AUDIO, encoding="utf-8")) if os.path.exists(AUDIO) else {}
    todo = []
    for e in episodes:
        rel = audio_file(e)
        path = os.path.join(ROOT, rel)
        if not os.path.exists(path):
            continue
        k = known.get(e["id"])
        if not k or k.get("file") != rel or k.get("bytes") != os.path.getsize(path) or not k.get("seconds"):
            todo.append((e["id"], rel, path))
    if todo:
        with concurrent.futures.ThreadPoolExecutor(8) as pool:
            for (eid, rel, path), s in zip(todo, pool.map(lambda t: seconds(t[2]), todo)):
                if s:
                    known[eid] = {"file": rel, "bytes": os.path.getsize(path), "seconds": s}
        with open(AUDIO, "w", encoding="utf-8", newline="\n") as f:
            json.dump(dict(sorted(known.items(), reverse=True)), f, ensure_ascii=False, indent=0)
            f.write("\n")
    return known, len(todo)


def athens(date):
    """22:00 Athens time on that day (summer time from the last Sunday of March to the last Sunday of October)."""
    y, m, d = map(int, date.split("-"))
    def last_sunday(month):
        day = datetime.date(y, month, 31)
        return day - datetime.timedelta(days=(day.weekday() + 1) % 7)
    summer = last_sunday(3) <= datetime.date(y, m, d) < last_sunday(10)
    tz = datetime.timezone(datetime.timedelta(hours=3 if summer else 2))
    return datetime.datetime(y, m, d, 22, 0, tzinfo=tz)


def duration(s):
    return "%d:%02d:%02d" % (s // 3600, s % 3600 // 60, s % 60)


def item(e, a, SITE_URL):
    y, m, d = map(int, e["date"].split("-"))
    page = SITE_URL + "index.html#e-" + e["id"]
    text = ["%s. Εκπομπή της %d %s %d (%dος κύκλος) από τη ραδιοφωνική σειρά «%s» του ράδιο «Χριστιανισμός»."
            % (e["title"].rstrip(".;"), d, MONTHS[m - 1], y, e["season"], NAME)]
    if e["tags"]:
        text.append("Θέματα: " + ", ".join(e["tags"]) + ".")
    if e.get("link") and not e["link"].startswith("http"):
        text.append("Άρθρα και πηγές: " + SITE_URL + e["link"])
    text.append("Στην ιστοσελίδα: " + page)
    return """    <item>
      <title>%s</title>
      <description>%s</description>
      <link>%s</link>
      <guid isPermaLink="false">christianity-science-%s</guid>
      <pubDate>%s</pubDate>
      <enclosure url="%s" length="%d" type="audio/mpeg"/>
      <itunes:duration>%s</itunes:duration>
      <itunes:season>%d</itunes:season>
      <itunes:episodeType>full</itunes:episodeType>
      <itunes:explicit>false</itunes:explicit>
    </item>
""" % (escape(e["title"]), escape("\n\n".join(text)), escape(page), e["id"], format_datetime(athens(e["date"])),
       escape(SITE_URL + a["file"]), a["bytes"], duration(a["seconds"]), e["season"])


def main():
    data = load()
    episodes, email = data["episodes"], data["config"]["email"]
    # where the site is now (SITE_CONFIG.podcastSite), else its own address (tools/seo.py)
    SITE_URL = (data["config"]["site"] or seo.SITE_URL).rstrip("/") + "/"
    known, measured = measure(episodes)
    items, left_out = [], []
    for e in episodes:                                   # js/broadcasts.js is newest first, as feeds should be
        a = known.get(e["id"])
        if a and a.get("file") == audio_file(e):
            items.append(item(e, a, SITE_URL))
        else:
            left_out.append(e["date"])
    owner = ("    <itunes:owner>\n      <itunes:name>%s</itunes:name>\n      <itunes:email>%s</itunes:email>\n    </itunes:owner>\n"
             % (escape(NAME), escape(email))) if email else ""
    feed = """<?xml version="1.0" encoding="UTF-8"?>
<!-- Made by tools/podcast.py from js/broadcasts.js: do not edit by hand. -->
<rss version="2.0" xmlns:itunes="http://www.itunes.com/dtds/podcast-1.0.dtd" xmlns:atom="http://www.w3.org/2005/Atom">
  <channel>
    <title>%(name)s</title>
    <link>%(site)s</link>
    <atom:link href="%(site)spodcast.xml" rel="self" type="application/rss+xml"/>
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
""" % {"name": escape(NAME), "site": SITE_URL, "desc": escape(DESCRIPTION % SITE_URL), "owner": owner, "cover": COVER,
       "items": "".join(items)}
    old = open(OUT, encoding="utf-8").read() if os.path.exists(OUT) else None
    if feed != old:
        with open(OUT, "w", encoding="utf-8", newline="\n") as f:
            f.write(feed)
    print("podcast: %d episodes in podcast.xml%s%s" % (len(items), " (%d mp3s measured)" % measured if measured else "",
          "; left out, no mp3 known: " + ", ".join(left_out) if left_out else ""))


if __name__ == "__main__":
    main()
