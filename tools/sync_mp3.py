"""Copy to this computer the broadcast mp3s that are on the server but not here (a second copy of the archive).

    python tools/sync_mp3.py            download what is missing (new broadcasts from the upload page)
    python tools/sync_mp3.py --check    only list what is missing

The server is the copy the site plays from; this folder (mp3/, about 40 GB) is the backup. Broadcasts
published through the upload page reach the server only, so run this now and then (e.g. monthly) to keep
the backup complete. Nothing on the server is changed. Server settings: see tools/serverfs.py.
"""
import argparse, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import serverfs
from inbox import load_site

ROOT = os.path.dirname(HERE)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args()
    site = load_site(ROOT)
    wanted = []
    for s in site["seasons"]:
        for e in s["episodes"]:
            files = list(e["parts"])
            if len(files) > 1:
                files.append(os.path.dirname(files[0]) + "/" + e["date"].replace("-", "_") + "_full.mp3")
            wanted += [f for f in files if not os.path.exists(os.path.join(ROOT, f))]
    print("%d mp3 files missing on this computer" % len(wanted))
    if a.check or not wanted:
        for f in wanted[:30]:
            print("  " + f)
        return
    srv = serverfs.connect()
    try:
        for f in wanted:
            if srv.size("site", f) is None:
                print("  not on the server either: " + f)
                continue
            os.makedirs(os.path.dirname(os.path.join(ROOT, f)), exist_ok=True)
            srv.download("site", f, os.path.join(ROOT, f))
            print("  copied " + f)
    finally:
        srv.close()


if __name__ == "__main__":
    main()
