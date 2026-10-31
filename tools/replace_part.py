"""Replace the mp3 of ONE half-hour of an existing broadcast, keeping everything else exactly as it is.

    python tools/replace_part.py --date 2010-01-28 --part 1 --file new.mp3

Unlike the upload page's «Αντικατάσταση» (which replaces the whole broadcast and renames the files from the
title), this swaps a single part's file in place: same file name, same date, same podcast episode id, so Spotify
just refreshes that one episode. The whole-broadcast "_full.mp3" is rebuilt from the parts (the replaced one
included) and its episode refreshes too. The old part and old full are kept in private/replaced/ on the server.

It changes the server's mp3s and data/podcast-audio.json; it does NOT rebuild podcast.xml or commit — run
tools/podcast.py and commit/deploy afterwards (the replace-part workflow does this).

Server settings: tools/serverfs.py (FTP_* environment variables). --server <dir> uses a local folder as the
server instead (for a dry run or a test).
"""
import argparse, json, os, shutil, sys, tempfile, time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import serverfs
from inbox import load_site, probe, sha256, MIN_SECONDS   # from-import: this tool needs only the FTP settings
from join_broadcasts import join_files

ROOT = os.environ.get("CS_REPLACE_ROOT") or os.path.dirname(HERE)   # the override is only for tests
AUDIO = os.path.join(ROOT, "data", "podcast-audio.json")


def load_audio():
    with open(AUDIO, encoding="utf-8") as f:
        return json.load(f)


def save_audio(audio):                                  # same layout tools/inbox.py writes
    with open(AUDIO, "w", encoding="utf-8", newline="\n") as f:
        f.write(json.dumps(dict(sorted(audio.items(), reverse=True)), ensure_ascii=False, indent=0) + "\n")


def measure(path):
    secs, is_mp3 = probe(path)
    if not secs or not is_mp3:
        raise SystemExit("error: %s is not an mp3 recording" % path)
    if secs < MIN_SECONDS:
        raise SystemExit("error: %s lasts only %d seconds" % (path, secs))
    return {"bytes": os.path.getsize(path), "seconds": secs, "sha256": sha256(path)}


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--date", required=True, help="the broadcast's date, YYYY-MM-DD")
    ap.add_argument("--part", required=True, type=int, help="which half-hour (1, 2, …)")
    ap.add_argument("--file", required=True, help="the new mp3")
    ap.add_argument("--server", help="a local folder to use as the server (dry run / test)")
    a = ap.parse_args()

    if not os.path.isfile(a.file):
        raise SystemExit("error: no such file: " + a.file)
    site = load_site(ROOT)
    e = site["by_date"].get(a.date)
    if not e:
        raise SystemExit("error: no broadcast on %s" % a.date)
    parts = e["parts"]
    if not 1 <= a.part <= len(parts):
        raise SystemExit("error: this broadcast has %d part(s); --part %d is out of range" % (len(parts), a.part))
    ident = a.date.replace("-", "_")
    mp3_dir = os.path.dirname(parts[0])
    rel_part = parts[a.part - 1]
    full_rel = mp3_dir + "/" + ident + "_full.mp3"

    new_meta = measure(a.file)
    print("new part %d: %.1f MB, %d s" % (a.part, new_meta["bytes"] / 1e6, new_meta["seconds"]))

    srv = serverfs.connect(a.server) if a.server else serverfs.connect()
    try:
        if srv.size("site", rel_part) is None:
            raise SystemExit("error: the current file is not on the server: " + rel_part)

        # rebuild the whole-broadcast file from the parts, with the new one in place
        tmp = tempfile.mkdtemp(prefix="cs-replace-")
        try:
            ordered = []
            for i, rel in enumerate(parts, 1):
                dst = os.path.join(tmp, os.path.basename(rel))
                if i == a.part:
                    shutil.copyfile(a.file, dst)
                else:
                    srv.download("site", rel, dst)
                ordered.append(dst)
            full_meta = None
            full_local = None
            if len(parts) > 1:
                full_local = os.path.join(tmp, ident + "_full.mp3")
                out = join_files(ordered, full_local, e["title"], e["season"], a.date)
                if not out.startswith("joined"):
                    raise SystemExit("error: joining the parts failed: " + out)
                full_meta = measure(full_local)
                print("rebuilt full: %.1f MB, %d s" % (full_meta["bytes"] / 1e6, full_meta["seconds"]))

            # keep the old files, then put the new ones in their place
            backup = "replaced/%s-part%d-%s" % (ident, a.part, time.strftime("%Y%m%d-%H%M%S"))
            srv.mkdirs("private", backup)
            moved, put = [], []

            def undo():
                try:
                    for root_to, rel in put:
                        srv.remove("site", rel)
                    for rel, name in moved:
                        srv.move("private", backup + "/" + name, "site", rel)
                except Exception as ex:
                    print("  WARNING: could not undo cleanly (%s); check %s on the server" % (ex, mp3_dir))

            try:
                srv.move("site", rel_part, "private", backup + "/" + os.path.basename(rel_part))
                moved.append((rel_part, os.path.basename(rel_part)))
                if full_local and srv.size("site", full_rel) is not None:
                    srv.move("site", full_rel, "private", backup + "/" + os.path.basename(full_rel))
                    moved.append((full_rel, os.path.basename(full_rel)))
                srv.upload(a.file, "site", rel_part); put.append(("site", rel_part))
                if full_local:
                    srv.upload(full_local, "site", full_rel); put.append(("site", full_rel))
            except Exception:
                undo()
                raise
            print("  old files kept in private/%s" % backup)

            # the metadata the podcast feed reads
            audio = load_audio()
            audio[rel_part] = new_meta
            if full_meta is not None:
                audio[full_rel] = full_meta
            save_audio(audio)
            print("  updated data/podcast-audio.json")

            # the second copy of the archive on this computer, if it is here
            for rel, src in [(rel_part, a.file)] + ([(full_rel, full_local)] if full_local else []):
                here = os.path.join(ROOT, rel)
                if os.path.isdir(os.path.dirname(here)):
                    shutil.copyfile(src, here)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
    finally:
        srv.close()
    print("done. Now rebuild podcast.xml (python tools/podcast.py) and commit/deploy.")


if __name__ == "__main__":
    main()
