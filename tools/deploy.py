"""Put the site on the web server (webleaders) by FTP: only what changed, never the mp3s or PDFs.

    python tools/deploy.py               upload what changed since the last deploy
    python tools/deploy.py --dry-run     only list what would be uploaded or removed
    python tools/deploy.py --local DIR   deploy into a folder standing in for the server (tests)

What goes up: every file that git keeps, except what is not part of the site (tools, tests, translations,
notes; see NOT_SITE). The upload page (admin/) goes to its secret address, ADMIN_PATH (a GitHub secret),
and only if that is set. Never touched: the recordings and PDFs in mp3/ and files/ (they live on the server
only; of those folders only the few web pages kept in git go up), and anything the deploys did not put there
themselves, so the old site's other pages keep working.

The record of what is on the server is private/deploy/<site folder>.json ({path: sha256}), one per
destination (the test folder and the live site each have their own); comparing it with the files here
gives what changed. A file a deploy put there and the site no longer has is removed. The
first time a file replaces one of the old site's, the old one is set aside in private/old-site/ (nothing
of the old site is lost). Pictures, styles and scripts go up first, pages and the podcast feed last, so a
page never points to something that is not there yet.

Safety: nothing happens if this copy looks incomplete (no index.html), and a deploy that would remove
more than 100 files stops and asks for --allow-removals (a damaged checkout must not empty the site).
Server settings: see tools/serverfs.py.
"""
import argparse, hashlib, json, os, re, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import serverfs

ROOT = os.path.dirname(HERE)
def manifest_path(srv):
    """The deploy record of the site folder srv points at (one record per destination folder)."""
    site = srv.roots["site"].replace("\\", "/").rstrip("/")
    return "deploy/" + (re.sub(r"[^A-Za-z0-9._-]+", "_", site).strip("_") or "root") + ".json"
NOT_SITE_DIRS = (".github/", "tests/", "tools/", "translation/", "docs/", "admin/")
MEDIA_DIRS = ("mp3/", "files/")           # recordings and PDFs: on the server only; only their web pages are in git
NOT_SITE_FILES = {"README.md", ".gitignore", ".gitattributes", "CLAUDE.md"}
LAST = (".html", ".htm", ".xml", ".txt", ".ics")       # pages and feeds after everything they point to
MAX_REMOVALS = 100


def site_files(root, admin_path):
    """{path on the server: path here} of everything that belongs on the server."""
    out = subprocess.run(["git", "ls-files", "-z"], cwd=root, capture_output=True, check=True).stdout.decode("utf-8")
    files = {}
    for rel in filter(None, out.split("\0")):
        if not os.path.isfile(os.path.join(root, rel)):
            continue                                    # deleted here but not yet committed
        if rel.startswith("admin/"):
            if admin_path:
                files[admin_path + "/" + rel[len("admin/"):]] = rel
            continue
        if rel in NOT_SITE_FILES or rel.startswith(NOT_SITE_DIRS):
            continue
        if rel.startswith(MEDIA_DIRS) and not rel.endswith((".htm", ".html")):
            continue
        files[rel] = rel
    return files


def sha256(path):
    """The SHA-256 of a file on this computer (hex)."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def order(path):
    if path == ".htaccess":
        return (3, path)
    return (2 if path.endswith(LAST) else 1, path)


def deploy(srv, root=ROOT, admin_path=None, dry_run=False, allow_removals=False, log=print):
    admin_path = (admin_path or "").strip("/")
    if admin_path and (not all(c.isalnum() or c in "-_" for c in admin_path) or admin_path.lower() in ("admin", "mp3", "files")):
        raise SystemExit("ADMIN_PATH must be one folder name of letters, digits, - and _ (and not an obvious one).")
    if not os.path.isfile(os.path.join(root, "index.html")) or not os.path.isfile(os.path.join(root, "js", "broadcasts.js")):
        raise SystemExit("This copy of the site looks incomplete (no index.html); not deploying.")
    want = {dest: sha256(os.path.join(root, src)) for dest, src in site_files(root, admin_path).items()}
    src_of = site_files(root, admin_path)
    record = manifest_path(srv)
    raw = srv.read("private", record)
    first = raw is None
    manifest = json.loads(raw) if raw else {}
    uploads = sorted((p for p in want if manifest.get(p) != want[p]), key=order)
    removals = sorted(p for p in manifest if p not in want)
    log("deploy: %d files on the site, %d to upload, %d to remove%s"
        % (len(want), len(uploads), len(removals), " (first deploy)" if first else ""))
    if len(removals) > MAX_REMOVALS and not allow_removals:
        raise SystemExit("This deploy would remove %d files from the server, which looks wrong; check, then run "
                         "again with --allow-removals if it is right." % len(removals))
    if dry_run:
        for p in uploads[:50]:
            log("  upload " + p)
        for p in removals[:50]:
            log("  remove " + p)
        return uploads, removals
    for i, p in enumerate(uploads, 1):
        if p not in manifest and srv.size("site", p) is not None:
            srv.move("site", p, "private", "old-site/" + p)     # the old site's file, set aside once
        srv.upload(os.path.join(root, src_of[p]), "site", p)
        manifest[p] = want[p]
        if i % 25 == 0:
            srv.write("private", record, json.dumps(manifest, indent=0, sort_keys=True).encode())
            log("  %d / %d" % (i, len(uploads)))
    for p in removals:
        srv.remove("site", p)
        manifest.pop(p, None)
    if uploads or removals or first:
        srv.write("private", record, json.dumps(manifest, indent=0, sort_keys=True).encode())
    log("deploy: done")
    return uploads, removals


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--local", help="a folder standing in for the server")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--allow-removals", action="store_true")
    a = ap.parse_args(argv)
    if not a.local and not serverfs.configured():
        print("The server is not set up yet (FTP settings missing); not deploying.")
        return 0
    srv = serverfs.connect(a.local)
    try:
        deploy(srv, admin_path=os.environ.get("ADMIN_PATH"), dry_run=a.dry_run, allow_removals=a.allow_removals)
    finally:
        srv.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
