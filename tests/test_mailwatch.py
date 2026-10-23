"""Tests of tools/mailwatch.py: recordings that arrive by email (WeTransfer links, attachments).

    python -m unittest discover -s tests -p "test_*.py" -v

A stand-in for WeTransfer (a small web server answering like wetransfer.com's download page does) and
scripted emails; the requests made are then published by the real tools/inbox.py. Needs ffmpeg and node.
"""
import datetime, email.message, email.utils, http.server, io, json, os, re, shutil, subprocess, sys, tempfile, threading
import time, unittest, zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import inbox, mailwatch, serverfs
from test_inbox import make_mp3, DATA_FILES

TRUST = ["radio@christianity.gr", "@studio.example"]


def mp3_bytes(freq):
    p = os.path.join(tempfile.gettempdir(), "cs-mw-%d.mp3" % freq)
    make_mp3(p, freq)
    with open(p, "rb") as f:
        return f.read()


class FakeWeTransfer(http.server.ThreadingHTTPServer):
    """Transfers: {id: {"hash", "files": [(name, bytes)], "title", "zip": bool, "expired", "changed"}}."""
    def __init__(self):
        self.transfers, self.calls = {}, []
        super().__init__(("127.0.0.1", 0), self.Handler)
        threading.Thread(target=self.serve_forever, daemon=True).start()
        self.base = "http://127.0.0.1:%d" % self.server_address[1]

    class Handler(http.server.BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def send(self, code, body=b"", ctype="application/json", headers=()):
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            for k, v in headers:
                self.send_header(k, v)
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            srv = self.server
            srv.calls.append(("GET", self.path))
            if self.path == "/":
                return self.send(200, b'<html><meta name="csrf-token" content="tok123"></html>', "text/html",
                                 [("Set-Cookie", "session=abc; Path=/")])
            m = re.match(r"^/t-(\w+)$", self.path)              # we.tl/t-XXXX → the download page
            if m:
                t = srv.transfers.get(m.group(1))
                if not t:
                    return self.send(404, b"gone", "text/html")
                return self.send(302, b"", "text/html", [("Location", "/downloads/%s/%s" % (m.group(1), t["hash"]))])
            m = re.match(r"^/downloads/(\w+)/", self.path)
            if m:
                return self.send(200, b"<html>download page</html>", "text/html")
            m = re.match(r"^/file/(\w+)$", self.path)
            if m:
                t = srv.transfers[m.group(1)]
                if t.get("zip", True):
                    buf = io.BytesIO()
                    with zipfile.ZipFile(buf, "w") as z:
                        for name, data in t["files"]:
                            z.writestr(name, data)
                    return self.send(200, buf.getvalue(), "application/zip")
                name, data = t["files"][0]
                import urllib.parse                        # as real servers send non-Latin names (RFC 5987)
                return self.send(200, data, "audio/mpeg", [("Content-Disposition", "attachment; filename*=UTF-8''%s"
                                                             % urllib.parse.quote(name))])
            self.send(404)

        def do_POST(self):
            srv = self.server
            body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or b"{}")
            srv.calls.append(("POST", self.path, body, self.headers.get("X-CSRF-Token"), self.headers.get("Cookie")))
            m = re.match(r"^/api/v4/transfers/(\w+)/(prepare-download|download)$", self.path)
            t = srv.transfers.get(m.group(1)) if m else None
            if not t or t.get("expired"):
                return self.send(404, b'{"message":"not found"}')
            if body.get("security_hash") != t["hash"] or self.headers.get("X-CSRF-Token") != "tok123":
                return self.send(403, b'{"message":"forbidden"}')
            if m.group(2) == "prepare-download":
                return self.send(200, json.dumps({"state": "downloadable", "display_name": t.get("title", ""),
                                                  "files": [{"name": n} for n, _ in t["files"]]}).encode())
            if t.get("changed"):
                return self.send(200, b'{"something":"else"}')
            return self.send(200, json.dumps({"direct_link": srv.base + "/file/" + m.group(1)}).encode())


class FakeMailbox:
    def __init__(self):
        self.messages = []

    def recent(self, days=10):
        return list(self.messages)

    def headers(self, days=3):
        return [raw.split(b"\n\n", 1)[0] for raw in self.messages]


def make_email(frm="Ραδιόφωνο <radio@christianity.gr>", subject="", body="", date=None, attach=(), headers=()):
    m = email.message.EmailMessage()
    m["From"] = frm
    m["To"] = "science@christianity.gr"
    m["Subject"] = subject
    m["Date"] = email.utils.format_datetime(date or datetime.datetime(2026, 10, 16, 10, 0, tzinfo=datetime.timezone.utc))
    m["Message-ID"] = email.utils.make_msgid()
    for k, v in headers:
        m[k] = v
    m.set_content(body or "Καλημέρα, σας στέλνω την εκπομπή.")
    for name, data in attach:
        m.add_attachment(data, maintype="audio", subtype="mpeg", filename=name)
    return m.as_bytes()


class AnnounceTest(unittest.TestCase):
    """--announce: the contributor is told the sender and the subject of each new email, and nothing else."""
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="cs-announce-test-")
        self.srv = serverfs.connect(os.path.join(self.tmp, "server"))
        self.box = FakeMailbox()
        self.sent = []
        self.ok = True

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def send(self, to, subject, text):
        if self.ok:
            self.sent.append((to, subject, text))
        return self.ok

    def run_once(self):
        return mailwatch.announce(self.srv, self.box, ["contributor@example.com"], send=self.send, log=lambda *a: None)

    def test_only_new_emails_with_sender_and_subject(self):
        self.box.messages.append(make_email(subject="Παλιό email"))
        self.assertEqual(self.run_once(), 0)                  # the first time: what is there is only noted
        self.assertEqual(self.sent, [])
        self.box.messages.append(make_email(frm="Γιάννης <giannis@example.com>", subject="Ερώτηση για την εκπομπή",
                                            body="Προσωπικό κείμενο που δεν πρέπει να σταλεί",
                                            attach=[("1_EPISTIMI.mp3", b"ID3 audio")]))
        self.assertEqual(self.run_once(), 1)
        [(to, subject, text)] = self.sent
        self.assertEqual(to, ["contributor@example.com"])
        self.assertEqual(subject, "Νέο email στο science@: Ερώτηση για την εκπομπή")
        self.assertEqual(text, "Από: Γιάννης <giannis@example.com>\nΘέμα: Ερώτηση για την εκπομπή")
        self.assertEqual(self.run_once(), 0)                  # each email once
        self.assertEqual(len(self.sent), 1)

    def test_no_subject_and_a_failed_send_is_tried_again(self):
        self.run_once()
        self.box.messages.append(make_email(subject=""))
        self.ok = False
        self.assertEqual(self.run_once(), 0)
        self.ok = True
        self.assertEqual(self.run_once(), 1)
        self.assertIn("Θέμα: (χωρίς θέμα)", self.sent[0][2])


class MailWatchTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="cs-mail-test-")
        self.root = os.path.join(self.tmp, "repo")
        for f in DATA_FILES:
            os.makedirs(os.path.dirname(os.path.join(self.root, f)), exist_ok=True)
            shutil.copyfile(os.path.join(ROOT, f), os.path.join(self.root, f))
        # the site's next broadcast as on 1 Oct 2026, so that the 15th is a broadcast day
        js = os.path.join(self.root, "js", "broadcasts.js")
        s = open(js, encoding="utf-8").read()
        s = re.sub(r'nextBroadcast: "[^"]*"', 'nextBroadcast: "2026-10-15T22:00:00+03:00"', s)
        open(js, "w", encoding="utf-8", newline="\n").write(s)
        self.srv = serverfs.connect(os.path.join(self.tmp, "server"))
        self.wt = FakeWeTransfer()
        os.environ["WETRANSFER_BASE"] = self.wt.base
        self.box = FakeMailbox()
        self.told = []
        self.logs = []
        self.watch = mailwatch.Watch(self.srv, self.box, TRUST, root=self.root, log=self.logs.append,
                                     notify=lambda subject, text: self.told.append((subject, text)),
                                     verify=lambda raw, msg: self.signature)
        self.signature = True          # as if every email's DKIM signature were valid (the real check: SignatureTest)

    def tearDown(self):
        os.environ.pop("WETRANSFER_BASE", None)
        self.wt.shutdown()
        shutil.rmtree(self.tmp, ignore_errors=True)

    def transfer(self, tid, files, **kw):
        self.wt.transfers[tid] = dict({"hash": "a1b2c3" + tid, "files": files}, **kw)
        return "https://we.tl/t-%s" % tid

    def requests(self, folder="inbox"):
        out = []
        d = os.path.join(self.tmp, "server", "private", folder)
        for ident in sorted(os.listdir(d)) if os.path.isdir(d) else []:
            if not ident.startswith("."):
                with open(os.path.join(d, ident, "request.json"), encoding="utf-8") as f:
                    out.append((ident, json.load(f)))
        return out

    # -- the normal case: published without anyone doing anything
    def test_a_wetransfer_email_is_published_automatically(self):
        parts = [mp3_bytes(1000 + i) for i in range(3)]
        link = self.transfer("abc", [("Εκπομπή (2).mp3", parts[1]), ("Εκπομπή (1).mp3", parts[0]), ("Εκπομπή (3).mp3", parts[2]),
                                     ("__MACOSX/._Εκπομπή (1).mp3", b"junk"), ("readme.txt", b"hello")])
        self.box.messages.append(make_email(subject="Fwd: Εκπομπή 15/10/2026 - Η Αγία Γραφή και η αρχαιολογία",
                                            body="Ορίστε η εκπομπή: %s\nΕυχαριστώ" % link))
        self.assertEqual(self.watch.run(), 0)
        (ident, req), = self.requests()
        self.assertEqual((req["date"], req["title"], req["user"]), ("2026-10-15", "Η Αγία Γραφή και η αρχαιολογία", "email"))
        self.assertEqual([f["original"] for f in req["files"]], ["Εκπομπή (1).mp3", "Εκπομπή (2).mp3", "Εκπομπή (3).mp3"])
        for i, f in enumerate(req["files"]):
            with open(os.path.join(self.tmp, "server", "private", "inbox", ident, f["name"]), "rb") as fh:
                self.assertEqual(fh.read(), parts[i])
        # WeTransfer was asked the way its page asks: with the page's token and cookie, and the link's hash
        post = [c for c in self.wt.calls if c[0] == "POST"][-1]
        self.assertEqual((post[2]["security_hash"], post[2]["intent"], post[3]), ("a1b2c3abc", "entire_transfer", "tok123"))
        self.assertIn("session=abc", post[4])
        # and the inbox publishes it
        box = inbox.Inbox(self.srv, self.root, push=False, build=False, keep_local=False, log=lambda *a: None)
        self.assertEqual(box.run(), 0)
        self.assertIn('ep("2026-10-15", "Η Αγία Γραφή και η αρχαιολογία"', open(os.path.join(self.root, "js", "broadcasts.js"), encoding="utf-8").read())
        self.assertEqual(self.told, [])

    def test_the_same_email_is_handled_once(self):
        link = self.transfer("once", [("a.mp3", mp3_bytes(1010))])
        self.box.messages.append(make_email(subject="Εκπομπή 15/10/2026 Δοκιμή μία φορά", body=link))
        self.watch.run()
        self.watch.run()
        self.assertEqual(len(self.requests()), 1)
        self.assertEqual(self.watch.new_emails(), [])

    def test_the_date_can_come_from_the_broadcast_schedule(self):
        link = self.transfer("sched", [("a.mp3", mp3_bytes(1020))])
        self.box.messages.append(make_email(subject="Η δημιουργία του κόσμου", body=link,
                                            date=datetime.datetime(2026, 10, 17, 9, 0, tzinfo=datetime.timezone.utc)))
        self.watch.run()
        (ident, req), = self.requests()
        self.assertEqual((req["date"], req["title"]), ("2026-10-15", "Η δημιουργία του κόσμου"))
        self.assertEqual(req["from_email"]["date_from"], "the broadcast day before the email")

    def test_the_title_can_come_from_the_transfer(self):
        link = self.transfer("titled", [("a.mp3", mp3_bytes(1030))], title="Εκπομπή 15/10 Οι άγγελοι")
        self.box.messages.append(make_email(subject="Ραδιόφωνο sent you files via WeTransfer", body=link))
        self.watch.run()
        (ident, req), = self.requests()
        self.assertEqual(req["title"], "Οι άγγελοι")

    # -- not sure: waits for the admin
    def test_without_a_title_it_waits_and_the_admin_is_told(self):
        link = self.transfer("notitle", [("a.mp3", mp3_bytes(1040))])
        self.box.messages.append(make_email(subject="Ραδιόφωνο σας έστειλε αρχεία μέσω WeTransfer", body=link))
        self.watch.run()
        self.assertEqual(self.requests("inbox"), [])
        (ident, req), = self.requests("drafts")
        self.assertEqual((req["date"], req["title"]), ("2026-10-15", ""))
        self.assertEqual(len(self.told), 1)
        self.assertIn("Από email", self.told[0][1])
        box = inbox.Inbox(self.srv, self.root, push=False, build=False, keep_local=False, log=lambda *a: None)
        box.run()                                           # drafts are never published by themselves
        self.assertNotIn('ep("2026-10-15"', open(os.path.join(self.root, "js", "broadcasts.js"), encoding="utf-8").read())

    # -- who is listened to
    def test_only_trusted_senders_and_never_forged_ones(self):
        link = self.transfer("who", [("a.mp3", mp3_bytes(1050))])
        self.box.messages += [
            make_email(frm="someone@example.com", subject="Εκπομπή 15/10/2026 Ψεύτικη", body=link),
            make_email(frm="radio@christianity.gr", subject="Εκπομπή 15/10/2026 Πλαστή", body=link,
                       headers=[("Authentication-Results", "mail.christianity.gr; spf=fail smtp.mailfrom=christianity.gr; dkim=none")]),
            make_email(frm="radio@christianity.gr", subject="Ερώτηση ακροατή", body="Χωρίς σύνδεσμο."),
            make_email(frm="Studio <tech@studio.example>", subject="Εκπομπή 15/10/2026 Από το στούντιο", body=link),
        ]
        self.watch.run()
        (ident, req), = self.requests()
        self.assertEqual(req["title"], "Από το στούντιο")
        self.assertTrue(any("not really from" in l for l in self.logs))

    def test_trust_rules(self):
        self.assertTrue(mailwatch.trusted("Radio@Christianity.gr", ["radio@christianity.gr"]))
        self.assertTrue(mailwatch.trusted("a@studio.example", ["@studio.example"]))
        self.assertFalse(mailwatch.trusted("a@evilstudio.example", ["@studio.example"]))
        self.assertFalse(mailwatch.trusted("radio@christianity.gr.evil.com", ["radio@christianity.gr"]))
        self.assertFalse(mailwatch.trusted("", ["@studio.example", ""]))

    # -- when WeTransfer does not cooperate
    def test_an_expired_link_is_tried_again_then_reported(self):
        link = self.transfer("old", [("a.mp3", mp3_bytes(1060))], expired=True)
        self.box.messages.append(make_email(subject="Εκπομπή 15/10/2026 Παλιό", body=link))
        self.assertEqual(self.watch.run(), 0)                   # not an alarm: tried again next time
        self.assertEqual(self.requests(), [])
        self.assertEqual(len(self.watch.new_emails()), 1)       # still to be tried
        self.assertEqual(self.told, [])
        seen = self.watch.load_seen()
        for v in seen.values():
            v["first"] -= 2 * 86400                             # a day and more later
        self.watch.save_seen(seen)
        self.watch.run()
        self.assertEqual(len(self.told), 1)
        self.assertIn("δεν μπόρεσαν να ληφθούν", self.told[0][0])
        self.assertEqual(self.watch.new_emails(), [])           # reported once, then left

    def test_wetransfer_changing_its_site_is_reported_clearly(self):
        link = self.transfer("chg", [("a.mp3", mp3_bytes(1070))], changed=True)
        self.box.messages.append(make_email(subject="Εκπομπή 15/10/2026 Αλλαγή", body=link))
        self.watch.run()
        self.assertTrue(any("changed its site" in l for l in self.logs), self.logs)

    def test_a_single_file_transfer(self):
        link = self.transfer("single", [("Ολόκληρη εκπομπή.mp3", mp3_bytes(1080))], zip=False)
        self.box.messages.append(make_email(subject="Εκπομπή 15/10/2026 Ένα αρχείο", body=link))
        self.watch.run()
        (ident, req), = self.requests()
        self.assertEqual([f["original"] for f in req["files"]], ["Ολόκληρη εκπομπή.mp3"])

    # -- attachments, other formats, odd archives
    def test_attached_recordings_and_other_formats(self):
        wav = os.path.join(self.tmp, "b.wav")
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "sine=frequency=1090:duration=61", wav], check=True)
        self.box.messages.append(make_email(subject="Εκπομπή 15/10/2026 Συνημμένα",
                                            attach=[("μέρος 2.wav", open(wav, "rb").read()), ("μέρος 1.mp3", mp3_bytes(1091))]))
        self.watch.run()
        (ident, req), = self.requests()
        self.assertEqual([f["original"] for f in req["files"]], ["μέρος 1.mp3", "μέρος 2.mp3"])
        secs, is_mp3 = inbox.probe(os.path.join(self.tmp, "server", "private", "inbox", ident, "part-2.mp3"))
        self.assertTrue(is_mp3)
        self.assertEqual(secs, 61)

    def test_an_archive_cannot_write_outside_its_folder(self):
        link = self.transfer("slip", [("../../../evil.mp3", mp3_bytes(1100)), ("/abs/also.mp3", mp3_bytes(1101))])
        self.box.messages.append(make_email(subject="Εκπομπή 15/10/2026 Παράξενο αρχείο", body=link))
        self.watch.run()
        (ident, req), = self.requests()
        self.assertEqual(sorted(f["original"] for f in req["files"]), ["also.mp3", "evil.mp3"])
        self.assertFalse(os.path.exists(os.path.join(self.tmp, "evil.mp3")))

    # -- the way WeTransfer's emails really look (as in science@christianity.gr, 15 Oct 2026)
    def wetransfer_email(self, reply_to, link, frm="WeTransfer <noreply@wetransfer.com>", name="1_EPISTIMI_X.mp3"):
        many = "%s?t_exp=1&t_lsid=a&utm_source=x  %s?t_exp=1&t_lsid=b  %s?utm_campaign=y" % (link, link, link)
        return make_email(frm=frm, subject="%s sent you %s via WeTransfer" % (reply_to, name),
                          body="%s sent you %s 4 items, 138 MB in total - Expires on 18 October, 2026 Get your files %s"
                               % (reply_to, name, many), headers=[("Reply-To", reply_to)])

    def test_a_real_wetransfer_email_counts_by_who_made_the_transfer(self):
        files = [("%d_EPISTIMI_PAGKOSMIA_MERA_PSYXIKIS_YGEIAS.mp3" % i, mp3_bytes(1200 + i)) for i in (2, 1, 4, 3)]
        self.transfer("a432523b", files)
        link = "https://wetransfer.com/downloads/a432523b/%s" % self.wt.transfers["a432523b"]["hash"]
        self.box.messages.append(self.wetransfer_email("radio@christianity.gr", link))
        self.watch.run()
        (ident, req), = self.requests("drafts")             # no title in such an email: it waits, date filled in
        self.assertEqual(req["date"], "2026-10-15")
        self.assertEqual(req["from_email"]["from"], "radio@christianity.gr")
        self.assertEqual([f["original"] for f in req["files"]],
                         ["%d_EPISTIMI_PAGKOSMIA_MERA_PSYXIKIS_YGEIAS.mp3" % i for i in (1, 2, 3, 4)])
        downloads = [c for c in self.wt.calls if c[0] == "POST" and c[1].endswith("/download")]
        self.assertEqual(len(downloads), 1)                 # the link three times in the email: fetched once
        self.assertIn("radio@christianity.gr", self.told[0][1])

    def test_a_cut_off_or_broken_link_does_not_spoil_the_good_one(self):
        self.transfer("b0b0", [("1_X.mp3", mp3_bytes(1240)), ("2_X.mp3", mp3_bytes(1241))])
        good = "https://wetransfer.com/downloads/b0b0/%s" % self.wt.transfers["b0b0"]["hash"]
        broken = "https://wetransfer.com/downloads/dead0000/ffff0000"          # a whole link, but to nothing
        raw = make_email(frm="WeTransfer <noreply@wetransfer.com>", subject="radio@christianity.gr sent you 1_X.mp3 via WeTransfer",
                         body="Get your files https://wetransfer.com/downloads/b0b\nmore text %s and %s" % (broken, good),
                         headers=[("Reply-To", "radio@christianity.gr")])
        self.assertEqual(mailwatch.wetransfer_links(mailwatch.parse(raw)), [broken, good])   # the cut-off one is not a link
        self.box.messages.append(raw)
        self.watch.run()
        (ident, req), = self.requests("drafts")
        self.assertEqual(len(req["files"]), 2)

    def test_wetransfer_emails_for_others_and_fake_wetransfer_emails_are_ignored(self):
        link = self.transfer("f00d", [("a.mp3", mp3_bytes(1210))])
        self.box.messages += [self.wetransfer_email("stranger@example.com", link),
                              self.wetransfer_email("radio@christianity.gr", link, frm="WeTransfer <info@romankitchens.uk>")]
        self.watch.run()
        self.assertEqual((self.requests(), self.requests("drafts")), ([], []))

    def test_a_forged_signature_is_ignored_and_an_unchecked_one_waits(self):
        link = self.transfer("beef", [("a.mp3", mp3_bytes(1220))])
        self.box.messages.append(make_email(subject="Εκπομπή 15/10/2026 Υπογραφή", body=link))
        self.signature = False
        self.watch.run()
        self.assertEqual((self.requests(), self.requests("drafts")), ([], []))
        self.assertTrue(any("not really from" in l for l in self.logs))
        self.signature = None                               # dkimpy missing: never published by itself
        self.watch.run()
        self.assertEqual(self.requests(), [])
        (ident, req), = self.requests("drafts")
        self.assertEqual(req["title"], "Υπογραφή")
        self.assertIn("υπογραφή", self.told[0][1])

    def test_titles_suggested_from_file_names(self):
        self.assertEqual(mailwatch.name_stem(["1_EPISTIMI_PAGKOSMIA_MERA.mp3", "2_EPISTIMI_PAGKOSMIA_MERA.mp3"]),
                         "EPISTIMI PAGKOSMIA MERA")
        self.assertEqual(mailwatch.name_stem(["Η δημιουργία - 1.mp3", "Η δημιουργία - 2.mp3"]), "Η δημιουργία")
        self.assertEqual(mailwatch.name_stem(["a.mp3", "b.mp3"]), "")
        site = inbox.load_site(self.root)
        os.environ.pop("ANTHROPIC_API_KEY", None)
        self.assertEqual(mailwatch.suggest_title(["Η δημιουργία (1).mp3", "Η δημιουργία (2).mp3"], site), "Η δημιουργία")
        self.assertEqual(mailwatch.suggest_title(["Εκπομπή (1).mp3", "Εκπομπή (2).mp3"], site), "")
        self.assertEqual(mailwatch.suggest_title(["1_EPISTIMI_X_Y.mp3"], site), "")      # Greeklish needs Claude
        self.transfer("cafe", [("Οι άγγελοι (%d).mp3" % i, mp3_bytes(1230 + i)) for i in (1, 2)])
        link = "https://wetransfer.com/downloads/cafe/%s" % self.wt.transfers["cafe"]["hash"]
        self.box.messages.append(self.wetransfer_email("radio@christianity.gr", link, name="2 files"))
        self.watch.run()
        (ident, req), = self.requests("drafts")
        self.assertEqual(req["title_suggestion"], "Οι άγγελοι")

    # -- reading titles and dates
    def test_titles_and_dates_from_subjects(self):
        d = datetime.date(2026, 10, 16)
        cases = [("Fwd: Εκπομπή 15/10/2026 - Η Αγία Γραφή", datetime.date(2026, 10, 15), "Η Αγία Γραφή"),
                 ("Re: Fwd: εκπομπή της 15ης: «Η δημιουργία»", datetime.date(2026, 10, 15), "Η δημιουργία"),
                 ("2026-10-15 Οι προφητείες", datetime.date(2026, 10, 15), "Οι προφητείες"),
                 ("Εκπομπή 15 Οκτωβρίου: Το DNA", datetime.date(2026, 10, 15), "Το DNA"),
                 ("Τα αρχεία", None, ""), ("Version 2.5 τελικό", None, "Version 2.5 τελικό"),
                 ("Maria sent you files via WeTransfer", None, "")]
        for subject, date, title in cases:
            found, txt = mailwatch.find_date(subject, d)
            self.assertEqual((found, mailwatch.clean_title(subject, txt)), (date, title), subject)

    def test_the_schedule(self):
        nb = "2026-10-15T22:00:00+03:00"
        self.assertEqual(mailwatch.schedule_day(datetime.date(2026, 10, 15), nb), datetime.date(2026, 10, 15))
        self.assertEqual(mailwatch.schedule_day(datetime.date(2026, 10, 28), nb), datetime.date(2026, 10, 15))
        self.assertEqual(mailwatch.schedule_day(datetime.date(2026, 10, 29), nb), datetime.date(2026, 10, 29))
        self.assertEqual(mailwatch.schedule_day(datetime.date(2026, 10, 10), nb), datetime.date(2026, 10, 1))


try:
    import base64, dkim
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
except ImportError:
    dkim = None


@unittest.skipUnless(dkim, "dkimpy is not installed")
class SignatureTest(unittest.TestCase):
    """The real DKIM check, with a key made here and its "DNS record" handed to the check."""

    def setUp(self):
        key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        self.private = key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.TraditionalOpenSSL,
                                         serialization.NoEncryption())
        pub = key.public_key().public_bytes(serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo)
        record = b"v=DKIM1; k=rsa; p=" + base64.b64encode(pub)
        self.dns = lambda name, timeout=5: record if name == b"s1._domainkey.wetransfer.com." else None

    def signed(self, raw, domain=b"wetransfer.com"):
        return dkim.sign(raw, b"s1", domain, self.private, include_headers=[b"from", b"subject", b"reply-to", b"date"]) + raw

    def test_signed_by_wetransfer(self):
        raw = make_email(frm="WeTransfer <noreply@wetransfer.com>", subject="a@b.gr sent you x.mp3 via WeTransfer",
                         headers=[("Reply-To", "a@b.gr")])
        good = self.signed(raw)
        self.assertTrue(mailwatch.genuine(good, mailwatch.parse(good), dnsfunc=self.dns))
        bad = good.replace(b"Reply-To: a@b.gr", b"Reply-To: x@y.gr")         # changed after signing
        self.assertFalse(mailwatch.genuine(bad, mailwatch.parse(bad), dnsfunc=self.dns))
        self.assertFalse(mailwatch.genuine(raw, mailwatch.parse(raw), dnsfunc=self.dns))   # not signed
        other = self.signed(make_email(frm="WeTransfer <info@romankitchens.uk>", subject="x"))
        self.assertFalse(mailwatch.genuine(other, mailwatch.parse(other), dnsfunc=self.dns))   # signed for another domain


@unittest.skipUnless(os.environ.get("CS_IMAP_TEST_HOST"), "no test mail server (CS_IMAP_TEST_HOST)")
class RealImapTest(unittest.TestCase):
    """Against a real mail server (GreenMail, in GitHub's tests): reading never marks anything as read."""

    def test_reading_changes_nothing(self):
        import imaplib, smtplib
        host = os.environ["CS_IMAP_TEST_HOST"]
        user = "science%d@christianity.test" % int(time.time())
        with smtplib.SMTP(host, 3025) as s:
            s.sendmail("radio@christianity.gr", [user], make_email(subject="Εκπομπή 15/10/2026 IMAP", body="https://we.tl/t-x"))
        time.sleep(1)
        box = mailwatch.Mailbox(host, 3143, user, user, use_ssl=False)
        raws = box.recent()
        self.assertEqual(len(raws), 1)
        msg = mailwatch.parse(raws[0])
        self.assertEqual(mailwatch.wetransfer_links(msg), ["https://we.tl/t-x"])
        imap = imaplib.IMAP4(host, 3143)
        imap.login(user, user)
        imap.select("INBOX")
        typ, data = imap.fetch("1", "(FLAGS)")
        self.assertNotIn(b"\\Seen", data[0])
        imap.logout()


if __name__ == "__main__":
    unittest.main()
