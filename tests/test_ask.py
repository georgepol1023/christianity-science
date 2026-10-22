"""The question form's script (ask.php) with PHP's built-in web server, and a stand-in for the server's mail.

    python -m unittest tests.test_ask -v

Needs php (skipped without it; GitHub's test machines have it). The stand-in for sendmail keeps each email in a
file instead of sending it, or fails when told to (a file "fail" next to it).
"""
import base64, email, email.policy, glob, http.client, json, os, shutil, socket, subprocess, sys, tempfile, time, unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PHP = shutil.which("php")

SENDMAIL = r'''import os, sys, time
here = os.path.dirname(os.path.abspath(__file__))
if os.path.exists(os.path.join(here, "fail")):
    sys.exit(1)
with open(os.path.join(here, "mail", "%d.eml" % time.time_ns()), "wb") as f:
    f.write(sys.stdin.buffer.read())
'''


@unittest.skipUnless(PHP, "php is not installed")
class AskTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp(prefix="cs-ask-test-")
        cls.site = os.path.join(cls.tmp, "site")
        cls.private = os.path.join(cls.tmp, "private")
        os.makedirs(cls.site)
        os.makedirs(cls.private)
        os.makedirs(os.path.join(cls.tmp, "mail"))
        shutil.copyfile(os.path.join(ROOT, "ask.php"), os.path.join(cls.site, "ask.php"))
        with open(os.path.join(cls.tmp, "sendmail.py"), "w") as f:
            f.write(SENDMAIL)
        s = socket.socket()
        s.bind(("127.0.0.1", 0))
        cls.port = s.getsockname()[1]
        s.close()
        env = dict(os.environ, CS_PRIVATE_DIR=cls.private, CS_SHOW_ERRORS="1")
        cls.php = subprocess.Popen([PHP, "-d", "display_errors=1", "-d", "error_reporting=-1",
                                    "-d", "sendmail_path=%s %s" % (sys.executable, os.path.join(cls.tmp, "sendmail.py")),
                                    "-S", "127.0.0.1:%d" % cls.port, "-t", cls.site],
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

    def setUp(self):
        for f in glob.glob(os.path.join(self.tmp, "mail", "*")) + glob.glob(os.path.join(self.private, "questions", "*")):
            os.remove(f)
        limits = os.path.join(self.private, "questions", ".limits.json")
        if os.path.exists(limits):
            os.remove(limits)

    def ask(self, body, method="POST", origin=None):
        c = http.client.HTTPConnection("127.0.0.1", self.port, timeout=30)
        h = {"Content-Type": "application/json", "Host": "127.0.0.1:%d" % self.port}
        if origin is not None:
            h["Origin"] = origin
        c.request(method, "/ask.php", body=json.dumps(body).encode() if body is not None else None, headers=h)
        r = c.getresponse()
        raw = r.read()
        c.close()
        return r.status, json.loads(raw.decode("utf-8"))

    def question(self, **kw):
        q = {"question": "Πώς συμβιβάζεται η Μεγάλη Έκρηξη με τη Γένεση;", "name": "Ελένη Π.", "email": "eleni@example.com",
             "page": "https://www.christianity-science.gr/contact.html"}
        q.update(kw)
        return q

    def mails(self):
        out = []
        for p in sorted(glob.glob(os.path.join(self.tmp, "mail", "*.eml"))):
            with open(p, "rb") as f:
                out.append(email.message_from_bytes(f.read(), policy=email.policy.default))
        return out

    def copies(self):
        out = []
        for p in sorted(glob.glob(os.path.join(self.private, "questions", "*.json"))):
            with open(p, encoding="utf-8") as f:
                out.append(json.load(f))
        return out

    def test_a_question_is_emailed_and_kept(self):
        st, r = self.ask(self.question(), origin="http://127.0.0.1:%d" % self.port)
        self.assertEqual((st, r), (200, {"success": True}))
        [m] = self.mails()
        self.assertEqual(m["To"], "science@christianity.gr")
        self.assertIn("eleni@example.com", m["Reply-To"])
        self.assertIn("Ελένη Π.", str(m["Reply-To"]))
        self.assertIn("Ελένη Π.", str(m["Subject"]))
        self.assertIn("website@christianity-science.gr", m["From"])
        text = m.get_content()
        self.assertIn("Πώς συμβιβάζεται η Μεγάλη Έκρηξη με τη Γένεση;", text)
        self.assertIn("eleni@example.com", text)
        [copy] = self.copies()
        self.assertEqual((copy["email"], copy["emailed"]), ("eleni@example.com", True))
        self.assertNotIn("127.0.0.1", open(os.path.join(self.private, "questions", ".limits.json")).read())

    def test_the_spam_trap_sends_nothing(self):
        st, r = self.ask(self.question(botcheck=True))
        self.assertEqual((st, r), (200, {"success": True}))
        self.assertEqual((self.mails(), self.copies()), ([], []))

    def test_what_is_refused(self):
        for body, status in ((self.question(question="Γιατί;"), 400),
                             (self.question(email="not an address"), 400),
                             (self.question(email="a@example.com\r\nBcc: everyone@example.com"), 400),   # no extra headers
                             (self.question(question=["not", "text"]), 400),
                             ("just a string", 400)):
            st, r = self.ask(body)
            self.assertEqual(st, status, body)
            self.assertFalse(r["success"])
        self.assertEqual(self.ask(None, method="GET")[0], 405)
        self.assertEqual(self.ask(self.question(), origin="https://elsewhere.example")[0], 403)
        self.assertEqual(self.mails(), [])

    def test_english_page_answers_in_english(self):
        st, r = self.ask(self.question(question="Why?", page="https://www.christianity-science.gr/en/contact.html"))
        self.assertEqual(st, 400)
        self.assertIn("at least 10 characters", r["message"])

    def test_at_most_five_an_hour_from_one_address(self):
        for i in range(5):
            self.assertEqual(self.ask(self.question(question="Ερώτηση αριθμός %d για το σύμπαν" % i))[0], 200)
        st, r = self.ask(self.question())
        self.assertEqual(st, 429)
        self.assertEqual(len(self.mails()), 5)

    def test_a_failed_email_is_reported_and_the_copy_kept(self):
        open(os.path.join(self.tmp, "fail"), "w").close()
        try:
            st, r = self.ask(self.question())
        finally:
            os.remove(os.path.join(self.tmp, "fail"))
        self.assertEqual(st, 500)
        self.assertIn("Δοκιμάστε ξανά", r["message"])
        [copy] = self.copies()
        self.assertFalse(copy["emailed"])

    def test_long_text_is_cut_not_refused(self):
        st, _ = self.ask(self.question(question="α" * 5000, name="β" * 500))
        self.assertEqual(st, 200)
        [copy] = self.copies()
        self.assertEqual((len(copy["question"]), len(copy["name"])), (2000, 100))


if __name__ == "__main__":
    unittest.main()
