"""Check the upload page on the live server as a signed-in person would use it, and print what the server answers.

    python tools/diagnose_upload.py        (GitHub: Actions → Check the upload page → Run workflow)

A temporary person is added to the page's settings (<private>/config.php), signs in, and starts a broadcast upload
the way the browser does (one small piece, never finished, so nothing is published). Afterwards the settings are
put back exactly as they were, byte for byte, whatever happens. Only status codes and the server's answers are
printed (the workflow's logs are public): never the page's address, its key or a password.
Needs the FTP_… settings and ADMIN_PATH (as the other workflows).
"""
import base64, hashlib, hmac, http.cookiejar, json, os, re, secrets, struct, sys, time, urllib.error, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import admin_user, serverfs

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36"


def totp(secret, t=None):
    key = base64.b32decode(secret + "=" * (-len(secret) % 8))
    h = hmac.new(key, struct.pack(">Q", int((t or time.time()) // 30)), hashlib.sha1).digest()
    o = h[19] & 15
    return "%06d" % ((struct.unpack(">I", h[o:o + 4])[0] & 0x7FFFFFFF) % 1000000)


def show(what, status, headers, body):
    kind = headers.get("Content-Type", "?")
    text = body.decode("utf-8", "replace")
    text = re.sub(r"\d{8}-\d{6}-[0-9a-f]{8}", "<id>", text)
    text = re.sub(r"[0-9a-f]{64}", "<code>", text)
    print("%-8s %s  %s  %s" % (what, status, kind, " ".join(text.split())[:600]))
    server = {k: v for k, v in headers.items() if k.lower() in ("server", "x-powered-by", "x-imunify", "x-mod-security")}
    if status >= 400 and server:
        print("         headers: %s" % server)


def main():
    admin_path = os.environ.get("ADMIN_PATH", "").strip("/")
    if not (serverfs.configured() and admin_path):
        print("Needs the FTP_… settings and ADMIN_PATH.")
        return 1
    site = (os.environ.get("LIVE_URL") or "https://www.christianity-science.gr/").rstrip("/") + "/"
    base = site + admin_path + "/"
    srv = serverfs.connect()
    original = srv.read("private", "config.php")
    if not original:
        print("The upload page has no settings (config.php) on the server.")
        return 1
    cfg = admin_user.parse(original.decode("utf-8"))
    uid = "check-" + secrets.token_hex(3)
    password = secrets.token_urlsafe(18)
    secret = base64.b32encode(secrets.token_bytes(20)).decode().rstrip("=")
    line = "        %s => ['name' => %s, 'email' => '', 'password' => %s, 'totp' => %s],\n" % (
        admin_user.php(uid), admin_user.php("Έλεγχος"), admin_user.php(admin_user.password_hash(password)), admin_user.php(secret))
    text = original.decode("utf-8")
    m = re.search(r"'users' => \[\n", text)
    if not m:
        print("The settings file does not look as expected; nothing changed.")
        return 1
    try:
        srv.write("private", "config.php", (text[:m.end()] + line + text[m.end():]).encode("utf-8"))
        jar = http.cookiejar.CookieJar()
        web = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))

        def call(what, path, body=None, raw=False, csrf=""):
            h = {"User-Agent": UA, "Accept": "*/*", "Origin": site.rstrip("/"), "Sec-Fetch-Site": "same-origin",
                 "Sec-Fetch-Mode": "cors", "Sec-Fetch-Dest": "empty"}
            data = None
            if body is not None:
                data = body if raw else json.dumps(body, ensure_ascii=False).encode("utf-8")
                h["Content-Type"] = "application/octet-stream" if raw else "application/json"
                h["X-CSRF"] = csrf
            req = urllib.request.Request(base + path, data=data, headers=h, method="POST" if body is not None else "GET")
            try:
                with web.open(req, timeout=60) as r:
                    status, headers, out = r.status, dict(r.headers), r.read()
            except urllib.error.HTTPError as ex:
                status, headers, out = ex.code, dict(ex.headers), ex.read()
            if what:
                show(what, status, headers, out)
            return status, out

        call("", "?k=" + urllib.request.quote(cfg["device_key"]))
        st, page = call("page", "")
        token = re.search(rb'name="csrf" content="([0-9a-f]+)"', page)
        if not token:
            print("The sign-in page did not show (status %s)." % st)
            return 1
        st, out = call("login", "?a=login", {"name": uid, "password": password, "code": totp(secret)}, csrf=token.group(1).decode())
        try:
            csrf = json.loads(out)["csrf"]
        except (ValueError, KeyError):
            print("Signing in did not work; see above.")
            return 1
        call("state", "?a=state")
        start = {"date": "2099-12-31", "title": "Έλεγχος της σελίδας (δεν δημοσιεύεται)", "title_en": "", "tags": [],
                 "replace": False, "files": [{"name": "1_EPISTIMI_ELEGXOS.mp3", "size": 4096}]}
        st, out = call("start", "?a=start", start, csrf=csrf)
        try:
            ident = json.loads(out).get("id")
        except ValueError:
            ident = None
        if ident:
            call("piece", "?a=piece&id=%s&n=1&offset=0" % ident, b"ID3" + os.urandom(4093), raw=True, csrf=csrf)
            for name in ("meta.json", "part-1.mp3"):
                srv.remove("private", "inbox/.staging/%s/%s" % (ident, name))
            srv.remove("private", "inbox/.staging/" + ident)
        call("logout", "?a=logout", {}, csrf=csrf)
    finally:
        srv.write("private", "config.php", original)
        back = srv.read("private", "config.php")
        print("settings put back as they were: %s" % ("yes" if back == original else "NO, CHECK config.php"))
        srv.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
