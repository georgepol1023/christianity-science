"""See the upload page on this computer, with a demo login, before it goes on the server.

    python tools/preview_admin.py                 opens http://127.0.0.1:8090/… in the browser
    python tools/preview_admin.py --php C:/php/php.exe --port 8091

Everything happens in a throwaway copy (in the system's temp folder): the page, a copy of the site's
broadcast list, and an inbox. What you send is "published" into that copy every few seconds by the real
tools/inbox.py, so the «Κατάσταση» tab shows the outcome as it will on the server. Nothing real is
touched: not this folder's files, not git, not the server. Stop with Ctrl+C.

Demo sign-in: user  demo   password  preview-password   (no authenticator code in the preview).
Needs PHP (any recent version) and ffmpeg.
"""
import argparse, json, os, shutil, socket, subprocess, sys, tempfile, threading, time, webbrowser

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import admin_user, inbox, serverfs

ROOT = os.path.dirname(HERE)
PAGE = "diaxeirisi-preview"
KEY = "preview-device-key-not-for-real-use-0123456789"
USER, PASSWORD = "demo", "preview-password"


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")      # Greek in any Windows console
    except (AttributeError, ValueError):
        pass
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--php", default=os.environ.get("PHP") or shutil.which("php"))
    ap.add_argument("--port", type=int, default=8090)
    ap.add_argument("--no-browser", action="store_true")
    a = ap.parse_args()
    if not a.php:
        sys.exit("PHP is needed: install it, or give its place with --php (e.g. --php C:/php/php.exe).")
    if not shutil.which("ffmpeg"):
        print("(ffmpeg not found: the page works, but sent broadcasts cannot be published in the preview)")

    tmp = tempfile.mkdtemp(prefix="cs-upload-preview-")
    site, private, repo = (os.path.join(tmp, d) for d in ("site", "private", "repo"))
    for rel in ("js/broadcasts.js", "js/broadcasts-en.js", "js/tags.js", "data/podcast-audio.json", "404.html"):
        for base in (site, repo):
            os.makedirs(os.path.dirname(os.path.join(base, rel)), exist_ok=True)
            shutil.copyfile(os.path.join(ROOT, rel), os.path.join(base, rel))
    shutil.copytree(os.path.join(ROOT, "admin"), os.path.join(site, PAGE))
    os.makedirs(private)
    cfg = {"device_key": KEY, "users": {USER: {"name": "Δοκιμαστικός χρήστης", "email": "", "totp": "",
                                             "password": admin_user.password_hash(PASSWORD)}}}
    with open(os.path.join(private, "config.php"), "w", encoding="utf-8") as f:
        f.write(admin_user.render(cfg))
    if shutil.which("ffmpeg"):                     # an example of recordings that came by email without a title
        d = os.path.join(private, "drafts", time.strftime("%Y%m%d-%H%M%S-") + "0000demo")
        os.makedirs(d)
        files = []
        for i, freq in enumerate((330, 440), 1):
            p = os.path.join(d, "part-%d.mp3" % i)
            subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "sine=frequency=%d:duration=61" % freq,
                            "-ac", "1", "-b:a", "48k", p], check=True)
            files.append({"name": "part-%d.mp3" % i, "original": "Ekpompi (%d).mp3" % i, "bytes": os.path.getsize(p)})
        with open(os.path.join(d, "request.json"), "w", encoding="utf-8") as f:
            json.dump({"type": "broadcast", "user": "email", "date": "", "title": "", "tags": [], "files": files,
                       "from_email": {"from": "radio@christianity.gr", "subject": "Maria sent you files via WeTransfer"}},
                      f, ensure_ascii=False)

    with socket.socket() as s:
        if s.connect_ex(("127.0.0.1", a.port)) == 0:
            sys.exit("Port %d is in use; choose another with --port." % a.port)
    env = dict(os.environ, CS_PRIVATE_DIR=private)
    php = subprocess.Popen([a.php, "-S", "127.0.0.1:%d" % a.port, "-t", site], env=env,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    url = "http://127.0.0.1:%d/%s/" % (a.port, PAGE)
    stop = threading.Event()

    def publisher():
        """The inbox, run every few seconds on the throwaway copy (as GitHub does on the server)."""
        srv = serverfs.LocalServer(site, private)
        box = inbox.Inbox(srv, repo, push=False, build=False, keep_local=False, log=lambda m: print("  [inbox] " + m))
        while not stop.wait(4):
            try:
                if [n for n, k in srv.list("private", "inbox").items() if k == "dir" and not n.startswith(".")]:
                    box.run()
                    for rel in ("js/broadcasts.js", "js/broadcasts-en.js"):     # what the deploy would do
                        shutil.copyfile(os.path.join(repo, rel), os.path.join(site, rel))
            except Exception as ex:                         # keep the preview going whatever happens
                print("  [inbox] error: %s" % ex)
    threading.Thread(target=publisher, daemon=True).start()

    time.sleep(1)
    if php.poll() is not None:
        sys.exit("PHP did not start.")
    print("\nThe upload page (preview):  %s?k=%s" % (url, KEY))
    print("Sign in with  %s / %s   (no authenticator code in the preview)" % (USER, PASSWORD))
    print("Without the ?k=… part the page answers «not found», as it will for everyone else.")
    print("Throwaway copy: %s\nStop with Ctrl+C.\n" % tmp)
    if not a.no_browser:
        webbrowser.open(url + "?k=" + KEY)
    try:
        php.wait()
    except KeyboardInterrupt:
        pass
    finally:
        stop.set()
        php.terminate()
        shutil.rmtree(tmp, ignore_errors=True)
        print("Preview stopped; the throwaway copy is removed.")


if __name__ == "__main__":
    main()
