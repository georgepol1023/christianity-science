"""Join each broadcast's parts into one mp3 for the "whole broadcast" download.

    python tools/join_broadcasts.py            make every missing or outdated <date>_full.mp3
    python tools/join_broadcasts.py --check    only report what is missing (makes nothing)

The joined file sits in the broadcast's own folder next to its parts:
    mp3/broadcasts/Season_02/2008_10_09/2008_10_09_full.mp3
The site (js/app.js) uses the same rule, so nothing else needs to be recorded.

The audio is copied, not re-encoded (no loss, and fast). Only when the parts differ in sample
rate or channels is the joined file re-encoded, at the parts' highest bitrate. Needs ffmpeg/ffprobe.
Broadcasts with a single part need no joined file.
Like the parts, the joined files are not kept in git: upload mp3/ to the web host as before.
"""
import concurrent.futures, json, os, subprocess, sys, tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEAM = "Χριστιανισμός & Επιστήμη"

# Read the broadcast list exactly as the site does, by running js/broadcasts.js in node.
LIST_JS = r"""
const fs = require("fs"), vm = require("vm");
const ctx = { window: {} }; vm.runInNewContext(fs.readFileSync(process.argv[2], "utf8"), ctx);
const C = ctx.window.SITE_CONFIG, out = [];
for (const s of ctx.window.BROADCASTS) for (const e of s.episodes) {
  const id = e.date.replace(/-/g, "_"), parts = [];
  for (let n = 1; n <= e.parts; n++) parts.push(e.files ? e.files[n - 1] :
    (C.mp3Base || "") + "Season_" + (s.n < 10 ? "0" : "") + s.n + "/" + id + "/" + (e.cs ? "CS_" : "") + id + "_(" + n + ")_" + e.slug + ".mp3");
  out.push({ id, date: e.date, title: e.title, season: s.n, parts });
}
console.log(JSON.stringify(out));
"""


def episodes():
    with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8") as f:
        f.write(LIST_JS)
    try:
        r = subprocess.run(["node", f.name, os.path.join(ROOT, "js", "broadcasts.js")], capture_output=True, check=True)
    finally:
        os.remove(f.name)
    return json.loads(r.stdout.decode("utf-8"))


def full_path(e):
    """<folder of part 1>/<id>_full.mp3 — the same rule as fullFile() in js/app.js."""
    return os.path.dirname(e["parts"][0]) + "/" + e["id"] + "_full.mp3"


def probe(path):
    r = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "a:0", "-show_entries",
                        "stream=sample_rate,channels,bit_rate", "-of", "json", path], capture_output=True)
    s = json.loads(r.stdout.decode("utf-8") or "{}").get("streams", [{}])[0]
    return s.get("sample_rate"), s.get("channels"), int(s.get("bit_rate") or 0)


def join(e):
    parts = [os.path.join(ROOT, p) for p in e["parts"]]
    out = os.path.join(ROOT, full_path(e))
    if os.path.exists(out) and os.path.getmtime(out) >= max(os.path.getmtime(p) for p in parts):
        return "ok"
    info = [probe(p) for p in parts]
    same = len({(sr, ch) for sr, ch, _ in info}) == 1
    with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False, encoding="utf-8") as f:
        for p in parts:
            f.write("file '%s'\n" % p.replace("\\", "/").replace("'", r"'\''"))
        listing = f.name
    tmp = out + ".part"
    year = e["date"][:4]
    meta = ["-metadata", "title=" + e["title"], "-metadata", "artist=" + TEAM,
            "-metadata", "album=%s – Κύκλος %d" % (TEAM, e["season"]), "-metadata", "date=" + year,
            "-metadata", "comment=christianity-science.gr"]
    codec = ["-c", "copy"] if same else ["-c:a", "libmp3lame", "-b:a", "%dk" % max(64, max(b for _, _, b in info) // 1000)]
    try:
        r = subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", listing,
                            "-map", "0:a", "-map_metadata", "-1", *meta, *codec, "-id3v2_version", "3", "-f", "mp3", tmp],
                           capture_output=True)
        if r.returncode:
            if os.path.exists(tmp):
                os.remove(tmp)
            return "failed: " + r.stderr.decode("utf-8", "replace").strip().splitlines()[-1]
        os.replace(tmp, out)
        return "joined" if same else "joined (re-encoded: parts differ)"
    finally:
        os.remove(listing)


def main():
    eps = [e for e in episodes() if len(e["parts"]) > 1]
    missing_parts = [e for e in eps if not all(os.path.exists(os.path.join(ROOT, p)) for p in e["parts"])]
    todo = [e for e in eps if e not in missing_parts]
    if "--check" in sys.argv:
        no_full = [e["id"] for e in todo if not os.path.exists(os.path.join(ROOT, full_path(e)))]
        print("%d broadcasts with several parts; %d still need a joined file; %d have parts missing locally"
              % (len(eps), len(no_full), len(missing_parts)))
        return
    counts = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        for e, result in zip(todo, pool.map(join, todo)):
            key = result.split(":")[0]
            counts[key] = counts.get(key, 0) + 1
            if result != "ok":
                print(" ", e["id"], result)
    for e in missing_parts:
        print("  %s skipped: some parts are not in mp3/ on this computer" % e["id"])
    print("whole-broadcast files: " + ", ".join("%s %d" % kv for kv in sorted(counts.items())))


if __name__ == "__main__":
    main()
