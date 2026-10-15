"""End-to-end test of the upload page (admin/) with PHP's built-in web server, then tools/inbox.py.

    python -m unittest discover -s tests -p "test_*.py" -v

Needs php (skipped without it; GitHub's test machines have it), ffmpeg and node. Everything runs in a
temporary folder: a stand-in web folder (site/) and private folder (private/), like the real server.
"""
import base64, hashlib, hmac, http.client, json, os, re, shutil, socket, struct, subprocess, sys, tempfile, time, unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import admin_user, inbox, serverfs
from test_inbox import make_mp3

PHP = shutil.which("php")
SECRET = "test-upload-page"
TOTP = base64.b32encode(b"0123456789abcdefghij").decode().rstrip("=")


def totp(secret, t=None):
    key = base64.b32decode(secret + "=" * (-len(secret) % 8))
    h = hmac.new(key, struct.pack(">Q", int((t or time.time()) // 30)), hashlib.sha1).digest()
    o = h[19] & 15
    return "%06d" % ((struct.unpack(">I", h[o:o + 4])[0] & 0x7FFFFFFF) % 1000000)


class Browser:
    """Just enough of a browser: keeps cookies (by hand, as they are Secure) and the page's CSRF token."""
    def __init__(self, port):
        self.port, self.cookies, self.csrf = port, {}, ""

    def req(self, method, path, body=None, headers=None, raw=False):
        c = http.client.HTTPConnection("127.0.0.1", self.port, timeout=60)
        h = dict(headers or {})
        if self.cookies:
            h["Cookie"] = "; ".join("%s=%s" % kv for kv in self.cookies.items())
        if body is not None and not raw:
            body = json.dumps(body).encode()
            h["Content-Type"] = "application/json"
        if method == "POST":
            h.setdefault("X-CSRF", self.csrf)
        c.request(method, path, body=body, headers=h)
        r = c.getresponse()
        data = r.read()
        for k, v in r.getheaders():
            if k.lower() == "set-cookie":
                name, _, rest = v.partition("=")
                self.cookies[name.strip()] = rest.split(";")[0]
        c.close()
        return r.status, dict((k.lower(), v) for k, v in r.getheaders()), data

    def api(self, action, body=None, query="", raw=False):
        st, _, data = self.req("POST" if body is not None else "GET", "/%s/?a=%s%s" % (SECRET, action, query), body, raw=raw)
        return st, json.loads(data.decode("utf-8"))


@unittest.skipUnless(PHP, "php is not installed here")
class UploadPageTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp(prefix="cs-admin-test-")
        cls.site = os.path.join(cls.tmp, "server", "site")
        cls.private = os.path.join(cls.tmp, "server", "private")
        cls.repo = os.path.join(cls.tmp, "repo")
        for d in (cls.site, cls.private):
            os.makedirs(d)
        for rel in ("js/broadcasts.js", "js/broadcasts-en.js", "js/tags.js", "data/podcast-audio.json", "404.html"):
            for base in (cls.repo, cls.site):
                os.makedirs(os.path.dirname(os.path.join(base, rel)), exist_ok=True)
                shutil.copyfile(os.path.join(ROOT, rel), os.path.join(base, rel))
        shutil.copytree(os.path.join(ROOT, "admin"), os.path.join(cls.site, SECRET))
        cls.key = "k" * 10 + "device-key-for-tests-0123"
        cfg = {"device_key": cls.key, "users": {
            "maria": {"name": "Μαρία", "email": "", "password": admin_user.password_hash("correct horse battery"), "totp": TOTP},
            "nikos": {"name": "Νίκος", "email": "", "password": admin_user.password_hash("another long password"), "totp": ""}}}
        with open(os.path.join(cls.private, "config.php"), "w", encoding="utf-8") as f:
            f.write(admin_user.render(cfg))
        s = socket.socket()
        s.bind(("127.0.0.1", 0))
        cls.port = s.getsockname()[1]
        s.close()
        env = dict(os.environ, CS_PRIVATE_DIR=cls.private)
        cls.php = subprocess.Popen([PHP, "-d", "post_max_size=2M", "-S", "127.0.0.1:%d" % cls.port, "-t", cls.site],
                                   env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        for _ in range(50):
            try:
                socket.create_connection(("127.0.0.1", cls.port), timeout=1).close()
                break
            except OSError:
                time.sleep(0.1)

    @classmethod
    def tearDownClass(cls):
        cls.php.terminate()
        cls.php.wait()
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def signed_in(self, user="maria", password="correct horse battery", code=None):
        b = Browser(self.port)
        b.req("GET", "/%s/?k=%s" % (SECRET, self.key))
        st, _, page = b.req("GET", "/%s/" % SECRET)
        b.csrf = re.search(rb'name="csrf" content="([0-9a-f]+)"', page).group(1).decode()
        st, r = b.api("login", {"name": user, "password": password, "code": code if code is not None else totp(TOTP)})
        self.assertEqual(st, 200, r)
        b.csrf = r["csrf"]
        return b

    def mp3(self, freq):
        p = os.path.join(self.tmp, "%d.mp3" % freq)
        make_mp3(p, freq)
        return open(p, "rb").read()

    def upload(self, b, date, title, parts, replace=False, tags=("bible",)):
        st, r = b.api("start", {"date": date, "title": title, "title_en": "", "tags": list(tags), "replace": replace,
                                "files": [{"name": "rec-%d.mp3" % i, "size": len(p)} for i, p in enumerate(parts, 1)]})
        if st != 200:
            return st, r
        for n, data in enumerate(parts, 1):
            st2, r2 = b.api("piece", data, query="&id=%s&n=%d&offset=0" % (r["id"], n), raw=True)
            self.assertEqual((st2, r2.get("size")), (200, len(data)), r2)
        return b.api("finish", {"id": r["id"]})

    # -- invisible without the device key
    def test_without_the_device_key_the_page_does_not_exist(self):
        b = Browser(self.port)
        for path in ("/%s/" % SECRET, "/%s/?k=wrong" % SECRET, "/%s/?a=state" % SECRET):
            st, _, body = b.req("GET", path)
            self.assertEqual(st, 404, path)
        st, h, _ = b.req("GET", "/%s/?k=%s" % (SECRET, self.key))
        self.assertEqual(st, 303)
        self.assertIn("cs_device", b.cookies)
        st, h, page = b.req("GET", "/%s/" % SECRET)
        self.assertEqual(st, 200)
        self.assertIn("Σύνδεση".encode(), page)
        self.assertIn("noindex", h.get("x-robots-tag", ""))
        self.assertIn("frame-ancestors 'none'", h.get("content-security-policy", ""))

    def test_nothing_works_without_signing_in_or_without_the_token(self):
        b = Browser(self.port)
        b.req("GET", "/%s/?k=%s" % (SECRET, self.key))
        st, r = b.api("state")
        self.assertEqual(st, 401)
        b2 = self.signed_in()
        b2.csrf = "0" * 64
        st, r = b2.api("start", {"date": "2026-10-15"})
        self.assertEqual(st, 403)

    def test_sign_in_needs_the_authenticator_code(self):
        b = Browser(self.port)
        b.req("GET", "/%s/?k=%s" % (SECRET, self.key))
        _, _, page = b.req("GET", "/%s/" % SECRET)
        b.csrf = re.search(rb'name="csrf" content="([0-9a-f]+)"', page).group(1).decode()
        st, r = b.api("login", {"name": "maria", "password": "correct horse battery", "code": "000000"})
        self.assertEqual(st, 401)
        self.assertIn("Λάθος", r["error"])

    # -- a broadcast, all the way to the site
    def test_upload_then_publish_and_never_twice(self):
        b = self.signed_in()
        st, r = b.api("state")
        self.assertTrue(any(x["date"] == "2026-10-01" for x in r["broadcasts"]))
        self.assertEqual(len(r["topics"]), 21)
        # an existing date is refused at once
        st, r = self.upload(b, "2026-10-01", "Ξανά η ίδια", [self.mp3(900)])
        self.assertEqual(st, 409)
        self.assertIn("υπάρχει ήδη", r["error"])
        # a file that is not an mp3 is refused at its first piece
        st, r = b.api("start", {"date": "2026-10-22", "title": "Τ", "tags": [], "files": [{"name": "x.mp3", "size": 100}]})
        st2, r2 = b.api("piece", b"<?php system('id'); ?>" + b" " * 77, query="&id=%s&n=1&offset=0" % r["id"], raw=True)
        self.assertEqual(st2, 415)
        b.api("cancel", {"id": r["id"]})
        # a new one: two parts
        parts = [self.mp3(910), self.mp3(920)]
        st, r = self.upload(b, "2026-10-15", "Δοκιμαστική εκπομπή από τη σελίδα", parts)
        self.assertEqual((st, r.get("ok")), (200, True), r)
        waiting = []
        for d in os.listdir(os.path.join(self.private, "inbox")):
            if not d.startswith("."):
                with open(os.path.join(self.private, "inbox", d, "request.json"), encoding="utf-8") as f:
                    waiting.append(json.load(f))
        found = [w for w in waiting if w.get("date") == "2026-10-15"]
        self.assertEqual(len(found), 1)
        req = found[0]
        self.assertEqual((req["date"], req["user"], [f["bytes"] for f in req["files"]]), ("2026-10-15", "maria", [len(p) for p in parts]))
        # sent again while it waits: refused
        st, r = self.upload(b, "2026-10-15", "Δοκιμαστική εκπομπή από τη σελίδα", [self.mp3(930)])
        self.assertEqual(st, 409)
        self.assertIn("περιμένει", r["error"])
        # the inbox publishes it (and the deploy puts the new list on the site)
        srv = serverfs.connect(os.path.join(self.tmp, "server"))
        box = inbox.Inbox(srv, self.repo, push=False, build=False, keep_local=False, log=lambda *a: None)
        self.assertEqual(box.run(), 0)
        outcomes = []
        for f in sorted(os.listdir(os.path.join(self.private, "results"))):
            with open(os.path.join(self.private, "results", f), encoding="utf-8") as fh:
                r = json.load(fh)
            outcomes.append("%s %s %s: %s" % (r.get("type"), r.get("date"), r["status"], r["message"]))
        self.assertTrue(any(o.startswith("broadcast 2026-10-15 published") for o in outcomes), "\n".join(outcomes))
        for rel in ("js/broadcasts.js", "js/broadcasts-en.js"):
            shutil.copyfile(os.path.join(self.repo, rel), os.path.join(self.site, rel))
        self.assertEqual(sorted(os.listdir(os.path.join(self.site, "mp3", "broadcasts", "Season_20", "2026_10_15"))),
                         ["2026_10_15_(1)_Dokimastiki_ekpompi_apo_ti.mp3", "2026_10_15_(2)_Dokimastiki_ekpompi_apo_ti.mp3",
                          "2026_10_15_full.mp3"])
        st, r = b.api("state")
        self.assertEqual(r["results"][0]["status"], "published")
        self.assertEqual(r["pending"], [])
        self.assertTrue(any(x["date"] == "2026-10-15" for x in r["broadcasts"]))
        # and now it is on the site: a second upload is refused, a replacement is allowed
        st, r = self.upload(b, "2026-10-15", "Πάλι", [self.mp3(940)])
        self.assertEqual(st, 409)
        st, r = self.upload(b, "2026-10-15", "Δοκιμαστική εκπομπή από τη σελίδα", [self.mp3(950)], replace=True)
        self.assertEqual(st, 200, r)
        box.run()
        st, r = b.api("state")
        self.assertEqual(r["results"][0]["status"], "published", r["results"][0])

    def test_a_dropped_piece_resumes_where_it_stopped(self):
        b = self.signed_in(user="nikos", password="another long password", code="")
        data = self.mp3(960)
        st, r = b.api("start", {"date": "2026-11-05", "title": "Συνέχεια", "tags": [],
                                "files": [{"name": "a.mp3", "size": len(data)}]})
        ident = r["id"]
        half = len(data) // 2
        st, r = b.api("piece", data[:half], query="&id=%s&n=1&offset=0" % ident, raw=True)
        self.assertEqual(r["size"], half)
        # the page thinks the piece was lost and sends it again: the server says where it really is
        st, r = b.api("piece", data[:half], query="&id=%s&n=1&offset=0" % ident, raw=True)
        self.assertEqual(r["size"], half)
        st, r = b.api("finish", {"id": ident})
        self.assertEqual(st, 400)                     # not complete yet
        st, r = b.api("piece", data[half:], query="&id=%s&n=1&offset=%d" % (ident, half), raw=True)
        self.assertEqual(r["size"], len(data))
        st, r = b.api("finish", {"id": ident})
        self.assertEqual(st, 200, r)

    def test_a_piece_too_big_for_the_server_is_answered_413(self):
        b = self.signed_in(user="nikos", password="another long password", code="")
        data = self.mp3(970)
        big = data + b"\0" * (3 * 1024 * 1024)          # more than this server's post_max_size (2M)
        st, r = b.api("start", {"date": "2026-11-19", "title": "Μεγάλο", "tags": [], "files": [{"name": "a.mp3", "size": len(big)}]})
        self.assertLessEqual(r["chunk"], 2 * 1024 * 1024)
        st, r = b.api("piece", big, query="&id=%s&n=1&offset=0" % r["id"], raw=True)
        self.assertEqual(st, 413)

    def test_settings_and_corrections_go_to_the_inbox(self):
        b = self.signed_in()
        st, r = b.api("settings", {"youtube": "not a link"})
        self.assertEqual(st, 400)
        st, r = b.api("settings", {"youtube": "https://youtu.be/dQw4w9WgXcQ", "next": "2026-11-12T22:00"})
        self.assertEqual(st, 200, r)
        st, r = b.api("correct", {"date": "2026-09-17", "tags": ["family", "nonsense"]})
        self.assertEqual(st, 400)
        st, r = b.api("correct", {"date": "2026-09-17", "title_en": "Low birth rates"})
        self.assertEqual(st, 200, r)
        st, r = b.api("state")
        kinds = sorted(p["type"] for p in r["pending"])
        self.assertIn("settings", kinds)
        self.assertIn("correction", kinds)

    def test_zz_too_many_wrong_passwords_lock_the_sign_in(self):
        b = Browser(self.port)
        b.req("GET", "/%s/?k=%s" % (SECRET, self.key))
        _, _, page = b.req("GET", "/%s/" % SECRET)
        b.csrf = re.search(rb'name="csrf" content="([0-9a-f]+)"', page).group(1).decode()
        for _ in range(5):
            b.api("login", {"name": "nikos", "password": "wrong", "code": ""})
        st, r = b.api("login", {"name": "nikos", "password": "another long password", "code": ""})
        self.assertEqual(st, 401)
        self.assertIn("15 λεπτά", r["error"])


if __name__ == "__main__":
    unittest.main()
