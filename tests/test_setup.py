"""Tests of tools/setup_server.py: the one-command setup, with scripted answers.

    python -m unittest discover -s tests -p "test_*.py" -v

The flow test runs the whole first-time setup against a real FTP server (pyftpdlib), a stand-in for
DirectAdmin that really creates the FTP account, a stand-in for the GitHub CLI that records the secrets,
and (where php is installed) PHP's web server, so the checks over "the internet" really run.
"""
import base64, http.server, os, re, shutil, socket, subprocess, sys, tempfile, threading, time, unittest
import urllib.parse

from helpers import start_ftp
import admin_user, serverfs, setup_server
from setup_server import Stop

try:
    from pyftpdlib.authorizers import DummyAuthorizer
    from pyftpdlib.handlers import FTPHandler
except ImportError:
    FTPHandler = None
PHP = shutil.which("php")


class Script:
    """A console that answers from a script: [(words the question must contain, answer), ...] in order."""
    def __init__(self, answers):
        self.answers, self.said, self.asked = list(answers), [], []

    def ask(self, question, default="", secret=False, optional=False):
        self.asked.append(question)
        if not self.answers:
            raise AssertionError("unexpected question: " + question)
        words, answer = self.answers.pop(0)
        if words.lower() not in question.lower():
            raise AssertionError("expected a question about %r, got: %s" % (words, question))
        return answer or default

    def yes(self, question, default=True):
        return self.ask(question).lower()[:1] in ("y", "ν")

    def say(self, text=""):
        self.said.append(text)


class FakeGh:
    """Answers like the GitHub CLI; keeps the secrets and variables it is given."""
    def __init__(self, variables=None, signed_in=True):
        self.secrets, self.variables, self.signed_in, self.calls = {}, dict(variables or {}), signed_in, []

    def __call__(self, cmd, input=None, capture_output=True):
        self.calls.append(cmd)
        args = cmd[1:]
        out, rc = b"", 0
        if args[:2] == ["auth", "status"]:
            rc = 0 if self.signed_in else 1
        elif args[:2] == ["repo", "view"]:
            out = b"owner/site"
        elif args[:2] == ["secret", "set"]:
            self.secrets[args[2]] = input.decode()
        elif args[:2] == ["variable", "set"]:
            self.variables[args[2]] = args[args.index("--body") + 1]
        elif args[:2] == ["variable", "get"]:
            if args[2] in self.variables:
                out = self.variables[args[2]].encode()
            else:
                rc = 1
        return subprocess.CompletedProcess(cmd, rc, out, b"not signed in" if rc else b"")


def free_port():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    p = s.getsockname()[1]
    s.close()
    return p


class FakeDirectAdmin(http.server.ThreadingHTTPServer):
    """Accepts admin/da-pass; CMD_API_FTP creates the FTP account on the test FTP server."""
    def __init__(self, authorizer=None, home=None, fail=None):
        self.authorizer, self.home, self.fail, self.made = authorizer, home, fail, []
        super().__init__(("127.0.0.1", 0), self.Handler)

    class Handler(http.server.BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def do_POST(self):
            srv = self.server
            auth = self.headers.get("Authorization", "")
            if auth != "Basic " + base64.b64encode(b"admin:da-pass").decode():
                self.send_response(401)
                self.end_headers()
                return
            form = dict(urllib.parse.parse_qsl(self.rfile.read(int(self.headers["Content-Length"])).decode()))
            cmd = self.path.strip("/")
            if srv.fail:
                body = "error=1&text=Error&details=" + urllib.parse.quote_plus(srv.fail)
            elif cmd == "CMD_API_FTP" and form.get("action") == "create" and srv.authorizer is not None and \
                    srv.authorizer.has_user("%s@%s" % (form["user"], form["domain"])):
                body = "error=1&text=Error&details=" + urllib.parse.quote_plus("That FTP account already exists")
            elif cmd == "CMD_API_FTP" and form.get("action") == "create" and form["passwd"] == form["passwd2"]:
                user = "%s@%s" % (form["user"], form["domain"])
                if srv.authorizer is not None:
                    srv.authorizer.add_user(user, form["passwd"], srv.home, perm="elradfmwMT")
                srv.made.append(("ftp", user))
                body = "error=0&text=Created"
            elif cmd == "CMD_API_POP" and form.get("action") == "create":
                srv.made.append(("mail", form["user"]))
                body = "error=0&text=Created"
            else:
                body = "error=1&text=Error&details=Unknown"
            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            self.end_headers()
            self.wfile.write(body.encode())

    def start(self):
        threading.Thread(target=self.serve_forever, daemon=True).start()
        return "http://127.0.0.1:%d" % self.server_address[1]


# ---------------------------------------------------------------- small parts
class PiecesTest(unittest.TestCase):
    def test_directadmin_calls(self):
        da = FakeDirectAdmin()
        base = da.start()
        try:
            r = setup_server.directadmin(base, "admin", "da-pass", "CMD_API_POP", {"action": "create", "domain": "x.gr", "user": "a",
                                                                                    "passwd": "p", "passwd2": "p"})
            self.assertEqual(r["error"], "0")
            with self.assertRaises(Stop) as e:
                setup_server.directadmin(base, "admin", "wrong", "CMD_API_POP", {"action": "create"})
            self.assertIn("refused", str(e.exception))
            da.fail = "That name is already used"
            with self.assertRaises(Stop) as e:
                setup_server.directadmin(base, "admin", "da-pass", "CMD_API_FTP", {"action": "create"})
            self.assertIn("That name is already used", str(e.exception))
            with self.assertRaises(Stop):
                setup_server.directadmin("http://127.0.0.1:%d" % free_port(), "a", "b", "CMD_API_FTP", {})
        finally:
            da.shutdown()

    def test_finding_the_site_folder(self):
        tmp = tempfile.mkdtemp()
        try:
            for layout, expected in ((["public_html/index.html", "private_html/x"], ("/public_html", "/cs-admin")),
                                     (["domains/christianity-science.gr/public_html/index.html"],
                                      ("/domains/christianity-science.gr/public_html", "/domains/christianity-science.gr/cs-admin")),
                                     (["www/index.html"], None)):
                home = tempfile.mkdtemp(dir=tmp)
                for f in layout:
                    os.makedirs(os.path.dirname(os.path.join(home, f)), exist_ok=True)
                    open(os.path.join(home, f), "w").close()
                srv = serverfs.LocalServer(home, os.path.join(tmp, "unused"))
                self.assertEqual(setup_server.find_site_dirs(srv, "christianity-science.gr"), expected, layout)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_secrets_never_go_on_the_command_line(self):
        gh = FakeGh()
        setup_server.set_secrets("owner/site", {"FTP_PASSWORD": "s3cret!", "EMPTY": ""}, {"CS_SITE_DIR": "/public_html"}, gh)
        self.assertEqual(gh.secrets, {"FTP_PASSWORD": "s3cret!"})
        self.assertEqual(gh.variables, {"CS_SITE_DIR": "/public_html"})
        self.assertFalse(any("s3cret!" in " ".join(c) for c in gh.calls))

    def test_github_cli_must_be_signed_in(self):
        with self.assertRaises(Stop) as e:
            setup_server.github_repo(FakeGh(signed_in=False))
        self.assertIn("gh auth login", str(e.exception))
        self.assertEqual(setup_server.github_repo(FakeGh()), "owner/site")

    def test_yes_and_no(self):
        c = setup_server.Console()
        for typed, default, expected in (("", True, True), ("", False, False), ("n", True, False), ("Yes", False, True),
                                         ("ναι", False, True), ("όχι", True, False)):
            setup_server.input = lambda prompt, t=typed: t
            try:
                self.assertEqual(c.yes("?", default), expected, (typed, default))
            finally:
                del setup_server.input

    def test_passwords_made_for_accounts_are_strong(self):
        ps = {setup_server.strong_password() for _ in range(50)}
        self.assertEqual(len(ps), 50)
        for p in ps:
            self.assertEqual(len(p), 24)
            self.assertTrue(re.search(r"\d", p) and re.search(r"[A-Z]", p) and re.search(r"[a-z]", p))

    def test_going_live_only_from_main_with_the_workflows(self):
        tmp = tempfile.mkdtemp()
        try:
            git = lambda *a: subprocess.run(["git", *a], cwd=tmp, check=True, capture_output=True)
            git("init", "-q", "-b", "other")
            git("-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q", "--allow-empty", "-m", "x")
            s = setup_server.Setup(con=Script([]), runner=FakeGh({"CS_SITE_DIR": "/public_html"}), root=tmp)
            with self.assertRaises(Stop) as e:
                s.go_live()
            self.assertIn("main branch", str(e.exception))
            git("checkout", "-q", "-b", "main")
            with self.assertRaises(Stop) as e:
                s.go_live()
            self.assertIn("deploy workflow", str(e.exception))
            s = setup_server.Setup(con=Script([]), runner=FakeGh(), root=tmp)
            with self.assertRaises(Stop) as e:
                s.go_live()
            self.assertIn("first-time setup", str(e.exception))
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


# ---------------------------------------------------------------- the whole first-time setup
@unittest.skipUnless(FTPHandler, "pyftpdlib is not installed")
class FlowTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="cs-setup-test-")
        self.home = os.path.join(self.tmp, "ftp")
        os.makedirs(os.path.join(self.home, "public_html"))
        with open(os.path.join(self.home, "public_html", "index.html"), "w") as f:
            f.write("the old site")
        self.auth = DummyAuthorizer()
        handler = type("H", (FTPHandler,), {"authorizer": self.auth})
        self.ftp, self.ftp_port, self.ftp_thread = start_ftp(handler)
        self.da = FakeDirectAdmin(self.auth, self.home)
        self.da_base = self.da.start()
        self.php = None
        if PHP:
            self.php_port = free_port()
            self.php = subprocess.Popen([PHP, "-S", "127.0.0.1:%d" % self.php_port, "-t", os.path.join(self.home, "public_html")],
                                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            for _ in range(50):
                try:
                    socket.create_connection(("127.0.0.1", self.php_port), timeout=1).close()
                    break
                except OSError:
                    time.sleep(0.1)

    def tearDown(self):
        self.ftp.close_all()
        self.ftp_thread.join(10)
        self.da.shutdown()
        if self.php:
            self.php.terminate()
            self.php.wait()
        shutil.rmtree(self.tmp, ignore_errors=True)

    def setup(self, answers, gh):
        site_url = "http://127.0.0.1:%d/" % self.php_port if self.php else "http://127.0.0.1:%d/" % free_port()
        self.mails = []
        return setup_server.Setup(con=Script(answers), runner=gh, ftp_port=self.ftp_port, site_url=site_url,
                                  ftp_host="127.0.0.1", da_base=self.da_base,
                                  mailer=lambda settings, to: self.mails.append((settings["SMTP_USER"], to)))

    def first_time_answers(self):
        return [("new FTP account", "y"), ("DirectAdmin user", "admin"), ("DirectAdmin password", "da-pass"),
                ("plain FTP", "y"),
                ("User name", "maria"), ("Full name", "Μαρία"), ("Email", "maria@example.com"),
                ("Password", "a very long password"), ("Password again", "a very long password"),
                ("Send an email", "y"), ("Fetch recordings emailed", "n"), ("DeepL API key", ""), ("Claude API key", "")]

    def test_first_time_setup_from_start_to_finish(self):
        gh = FakeGh()
        s = self.setup(self.first_time_answers(), gh)
        if not self.php:                        # without php the checks over the web cannot pass; the rest can
            real = setup_server.check_online
            setup_server.check_online = lambda *a: []
        try:
            ok = s.first_time()
        finally:
            if not self.php:
                setup_server.check_online = real
        said = "\n".join(s.con.said)
        self.assertTrue(ok, said)
        self.assertEqual(s.con.answers, [])
        # the accounts DirectAdmin was asked to make
        self.assertEqual(self.da.made, [("ftp", "publish@christianity-science.gr"), ("mail", "ekpompes")])
        # GitHub: everything the workflows need, publishing pointed at the test folder
        sec = gh.secrets
        self.assertEqual(sec["FTP_SITE_DIR"], "/public_html/new-site-test")
        self.assertEqual(sec["FTP_PRIVATE_DIR"], "/cs-admin")
        self.assertEqual((sec["FTP_HOST"], sec["FTP_USER"], sec["FTP_TLS"]), ("127.0.0.1", "publish@christianity-science.gr", "0"))
        self.assertRegex(sec["ADMIN_PATH"], r"^diaxeirisi-[a-z0-9]{10}$")
        self.assertEqual((sec["SMTP_USER"], sec["MAIL_TO"]), ("ekpompes@christianity-science.gr", "maria@example.com"))
        self.assertNotIn("ANTHROPIC_API_KEY", sec)
        self.assertEqual(gh.variables["CS_SITE_DIR"], "/public_html")
        # the server: private folder with the page's settings; the trial site; the live site untouched
        cfg = admin_user.parse(open(os.path.join(self.home, "cs-admin", "config.php"), encoding="utf-8").read())
        self.assertEqual(list(cfg["users"]), ["maria"])
        self.assertTrue(admin_user.password_hash and cfg["users"]["maria"]["password"].startswith("pbkdf2-sha256$600000$"))
        trial = os.path.join(self.home, "public_html", "new-site-test")
        self.assertTrue(os.path.isfile(os.path.join(trial, "index.html")))
        self.assertTrue(os.path.isfile(os.path.join(trial, sec["ADMIN_PATH"], "index.php")))
        self.assertEqual(open(os.path.join(self.home, "public_html", "index.html")).read(), "the old site")
        # a test email, and what the person must keep
        self.assertEqual(self.mails, [("ekpompes@christianity-science.gr", "maria@example.com")])
        self.assertIn("✓ a test email was sent", said)
        self.assertIn("FTP account: publish@christianity-science.gr   password: " + sec["FTP_PASSWORD"], said)
        self.assertIn("Mailbox: ekpompes@christianity-science.gr   password: " + sec["SMTP_PASSWORD"], said)
        # what the person is told
        self.assertIn("/new-site-test/" + sec["ADMIN_PATH"] + "/?k=" + cfg["device_key"], said)
        self.assertIn("--go-live", said)
        if self.php:
            self.assertEqual(said.count("✓ the upload page is invisible"), 1, said)
            self.assertIn("✓ PHP runs and finds its settings", said)
            self.assertNotIn("✗", said)

    def test_running_it_again_keeps_the_page_settings(self):
        self.test_first_time_setup_from_start_to_finish()
        before = open(os.path.join(self.home, "cs-admin", "config.php"), encoding="utf-8").read()
        gh = FakeGh()
        answers = [("new FTP account", "n"), ("FTP server", "127.0.0.1"), ("FTP user", "publish@christianity-science.gr"),
                   ("FTP password", self.ftp_password()), ("plain FTP", "y"),
                   ("Send an email", "n"), ("Fetch recordings emailed", "n"), ("DeepL API key", ""), ("Claude API key", "")]
        s = self.setup(answers, gh)
        if not self.php:
            setup_server.check_online, real = (lambda *a: []), setup_server.check_online
        try:
            self.assertTrue(s.first_time(), "\n".join(s.con.said))
        finally:
            if not self.php:
                setup_server.check_online = real
        self.assertEqual(open(os.path.join(self.home, "cs-admin", "config.php"), encoding="utf-8").read(), before)
        self.assertIn("keeping them", "\n".join(s.con.said))

    def test_running_it_again_when_the_ftp_account_exists(self):
        self.test_first_time_setup_from_start_to_finish()
        answers = [("new FTP account", "y"), ("DirectAdmin user", "admin"), ("DirectAdmin password", "da-pass"),
                   ("FTP server", "127.0.0.1"), ("FTP user", ""), ("FTP password", self.ftp_password()), ("plain FTP", "y"),
                   ("Send an email", "n"), ("Fetch recordings emailed", "n"), ("DeepL API key", ""), ("Claude API key", "")]
        s = self.setup(answers, FakeGh())
        if not self.php:
            setup_server.check_online, real = (lambda *a: []), setup_server.check_online
        try:
            self.assertTrue(s.first_time(), "\n".join(s.con.said))
        finally:
            if not self.php:
                setup_server.check_online = real
        self.assertIn("already exists", "\n".join(s.con.said))

    def test_running_it_again_after_going_live_keeps_the_live_site(self):
        self.test_first_time_setup_from_start_to_finish()
        gh = FakeGh({"LIVE_URL": "https://www.christianity-science.gr/"})
        answers = [("new FTP account", "n"), ("FTP server", "127.0.0.1"), ("FTP user", "publish@christianity-science.gr"),
                   ("FTP password", self.ftp_password()), ("plain FTP", "y"), ("Send an email", "n"), ("Fetch recordings emailed", "n"), ("DeepL API key", ""), ("Claude API key", "")]
        s = self.setup(answers, gh)
        trial = os.path.join(self.home, "public_html", "new-site-test")
        shutil.rmtree(trial)
        self.assertTrue(s.first_time(), "\n".join(s.con.said))
        self.assertEqual(gh.secrets["FTP_SITE_DIR"], "/public_html")
        self.assertFalse(os.path.exists(trial))                     # no trial deploy once live
        self.assertEqual(open(os.path.join(self.home, "public_html", "index.html")).read(), "the old site")

    def test_the_branch_without_the_upload_page_is_refused(self):
        tmp = tempfile.mkdtemp()
        try:
            s = setup_server.Setup(con=Script([]), runner=FakeGh(), root=tmp)
            with self.assertRaises(Stop) as e:
                s.first_time()
            self.assertIn("publishing branch", str(e.exception))
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def ftp_password(self):
        return self.auth.user_table["publish@christianity-science.gr"]["pwd"]

    def test_email_recordings_are_set_up_and_checked(self):
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        from test_mailwatch import make_email
        logins = []

        class FakeBox:
            def __init__(self, host, port, user, password):
                logins.append((host, user, password))
                self.password = password

            def recent(self):
                if self.password != "right":
                    raise SystemExit("The mail server refused the login")
                return [make_email(subject="Εκπομπή 15/10/2026 Α", body="https://we.tl/t-1"),
                        make_email(frm="listener@example.com", subject="Ερώτηση")]
        gh = FakeGh()
        answers = self.first_time_answers()
        answers[answers.index(("Send an email", "y")):] = [
            ("Send an email", "n"), ("Fetch recordings emailed", "y"), ("The mailbox", ""), ("mail server", ""),
            ("Who may send", "radio@christianity.gr, @studio.example"), ("Password of", "wrong"), ("Try another password", "y"),
            ("Password of", "right"), ("Who to tell about every new email", "contributor@example.com"),
            ("DeepL API key", ""), ("Claude API key", "")]
        s = self.setup(answers, gh)
        s.mailbox_factory = FakeBox
        if not self.php:
            setup_server.check_online, real = (lambda *a: []), setup_server.check_online
        try:
            self.assertTrue(s.first_time(), "\n".join(s.con.said))
        finally:
            if not self.php:
                setup_server.check_online = real
        self.assertEqual(logins, [("mail.christianity.gr", "science@christianity.gr", "wrong"),
                                  ("mail.christianity.gr", "science@christianity.gr", "right")])
        self.assertEqual((gh.secrets["MAIL_IMAP_USER"], gh.secrets["MAIL_IMAP_PASSWORD"], gh.secrets["MAIL_TRUSTED_SENDERS"]),
                         ("science@christianity.gr", "right", "radio@christianity.gr, @studio.example"))
        self.assertIn("2 emails in the last 10 days, 1 from the trusted senders, 1 with recordings", "\n".join(s.con.said))
        self.assertEqual(gh.secrets["MAIL_NOTIFY"], "contributor@example.com")

    def test_adding_a_person(self):
        self.test_first_time_setup_from_start_to_finish()
        gh = FakeGh({"CS_FTP_HOST": "127.0.0.1", "CS_FTP_USER": "publish@christianity-science.gr", "CS_FTP_TLS": "0",
                     "CS_PRIVATE_DIR": "/cs-admin"})
        s = self.setup([("FTP password", self.ftp_password()), ("User name", "nikos"), ("Full name", "Νίκος"), ("Email", ""),
                        ("Password", "another long password"), ("Password again", "another long password")], gh)
        self.assertTrue(s.add_someone())
        cfg = admin_user.parse(open(os.path.join(self.home, "cs-admin", "config.php"), encoding="utf-8").read())
        self.assertEqual(sorted(cfg["users"]), ["maria", "nikos"])

    def test_the_upload_pages_github_key(self):
        self.test_first_time_setup_from_start_to_finish()
        gh = FakeGh({"CS_FTP_HOST": "127.0.0.1", "CS_FTP_USER": "publish@christianity-science.gr", "CS_FTP_TLS": "0",
                     "CS_PRIVATE_DIR": "/cs-admin"})
        s = self.setup([("GitHub key", "github_pat_wrong"), ("Try another key", "y"), ("GitHub key", "github_pat_right"),
                        ("FTP password", self.ftp_password())], gh)
        s.github_check = lambda repo, key: key == "github_pat_right"
        self.assertTrue(s.github_key())
        cfg = admin_user.parse(open(os.path.join(self.home, "cs-admin", "config.php"), encoding="utf-8").read())
        self.assertEqual(cfg["github"], {"repo": "owner/site", "token": "github_pat_right"})
        self.assertEqual(sorted(cfg["users"]), ["maria"])          # the rest kept

    def test_a_wrong_directadmin_password_stops_with_advice(self):
        s = self.setup([("new FTP account", "y"), ("DirectAdmin user", "admin"), ("DirectAdmin password", "wrong")], FakeGh())
        with self.assertRaises(Stop) as e:
            s.first_time()
        self.assertIn("DirectAdmin refused", str(e.exception))


if __name__ == "__main__":
    unittest.main()
