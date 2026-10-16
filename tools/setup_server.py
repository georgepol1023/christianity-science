"""Set up publishing on the webleaders server in one go: answer a few questions, the rest is done for you.

    python tools/setup_server.py               first-time setup, ending with a trial in a test folder
    python tools/setup_server.py --go-live     switch the real site over, once the trial looks right
    python tools/setup_server.py --add-person  let another person use the upload page

What the first-time setup does (each step says what it is doing, and stops with advice if something fails):
  1. an FTP account for publishing: made for you with your DirectAdmin login (used once, never stored),
     or one you already have;
  2. finds the site's folder on the server and makes the private folder next to it (cs-admin);
  3. your sign-in for the upload page: name, password, and a code for your phone's authenticator app;
  4. optional: result emails (a mailbox is made for you), recordings emailed to science@christianity.gr
     (its login is checked now, read-only), and suggested English titles (a Claude API key);
  5. puts everything GitHub needs into the repository's secrets (with the GitHub CLI, gh);
  6. puts the new site into a TEST folder on the server (the live site is not touched) and checks over
     the internet that the pages load and the upload page works. You get the addresses to look at.
Needs: the GitHub CLI (gh), signed in (gh auth login), and this repository's folder.
"""
import argparse, base64, getpass, json, os, re, secrets, smtplib, ssl, string, subprocess, sys, time
from email.message import EmailMessage
import urllib.error, urllib.parse, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import admin_user, deploy, mailwatch, serverfs

ROOT = os.path.dirname(HERE)
DOMAIN = "christianity-science.gr"
TEST_FOLDER = "new-site-test"
FTP_NAME = "publish"           # → publish@christianity-science.gr
MAIL_NAME = "ekpompes"         # → ekpompes@christianity-science.gr
INCOMING = "science@christianity.gr"           # where the station emails the recordings
INCOMING_HOST = "mail.christianity.gr"         # its mail server (the name in its certificate)


class Stop(Exception):
    """Setup cannot go on; the message says what to do."""


# ---------------------------------------------------------------- talking to the person
class Console:
    def ask(self, question, default="", secret=False, optional=False):
        """The answer; an empty answer gives the default. Asked again if empty and required."""
        prompt = "%s%s: " % (question, " [%s]" % default if default and not secret else "")
        while True:
            answer = (getpass.getpass(prompt) if secret else input(prompt)).strip()
            if answer or default or optional:
                return answer or default

    def yes(self, question, default=True):
        a = self.ask(question + (" (Y/n)" if default else " (y/N)"), "y" if default else "n").lower()
        return a[:1] in ("y", "ν")             # Greek ν (ναι) too

    def say(self, text=""):
        print(text)


def strong_password(n=24):
    abc = string.ascii_letters + string.digits
    while True:
        p = "".join(secrets.choice(abc) for _ in range(n))
        if any(c.isdigit() for c in p) and any(c.isupper() for c in p) and any(c.islower() for c in p):
            return p


# ---------------------------------------------------------------- DirectAdmin (making accounts)
def directadmin(base, user, password, command, fields, verify=True):
    """Call DirectAdmin's API (e.g. CMD_API_FTP). Returns its answer as a dict; raises Stop on failure."""
    data = urllib.parse.urlencode(fields).encode()
    req = urllib.request.Request(base.rstrip("/") + "/" + command, data=data, method="POST")
    req.add_header("Authorization", "Basic " + base64.b64encode(("%s:%s" % (user, password)).encode()).decode())
    ctx = None if verify else ssl._create_unverified_context()
    try:
        with urllib.request.urlopen(req, timeout=60, context=ctx) as r:
            text = r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as ex:
        raise Stop("DirectAdmin refused (%s). Check the user name and password%s." %
                   (ex.code, "; if you use two-step login in DirectAdmin, create the account by hand" if ex.code in (401, 403) else ""))
    except (urllib.error.URLError, OSError) as ex:
        raise Stop("Could not reach DirectAdmin at %s (%s)." % (base, getattr(ex, "reason", ex)))
    answer = dict(urllib.parse.parse_qsl(text.strip()))
    if answer.get("error") != "0":
        detail = answer.get("details") or answer.get("text") or text[:200]
        raise Stop("DirectAdmin said: " + urllib.parse.unquote_plus(detail))
    return answer


def directadmin_base(con, domain):
    """The DirectAdmin address, and whether its certificate can be checked."""
    base = "https://%s:2222" % domain
    try:
        urllib.request.urlopen(base + "/", timeout=20)
        return base, True
    except urllib.error.HTTPError:
        return base, True
    except urllib.error.URLError as ex:
        if isinstance(getattr(ex, "reason", None), ssl.SSLError):
            con.say("  DirectAdmin's certificate is not for %s (common on shared hosting)." % domain)
            if con.yes("  Connect anyway? It is your own server; the connection is still encrypted", True):
                return base, False
        raise Stop("Could not reach DirectAdmin at %s." % base)


def cert_names(host, port=21):
    """The names in the FTP server's TLS certificate (on shared hosting it is often the server's own name,
    not the domain's: then FTP over TLS works with that name). [] if none can be read."""
    import ftplib, tempfile
    try:
        ftp = ftplib.FTP_TLS(timeout=30, context=ssl._create_unverified_context())
        ftp.connect(host, port)
        ftp.auth()
        der = ftp.sock.getpeercert(binary_form=True)
        ftp.close()
    except (OSError, EOFError, ftplib.Error):
        return []
    with tempfile.NamedTemporaryFile("w", suffix=".pem", delete=False) as f:
        f.write(ssl.DER_cert_to_PEM_cert(der))
    try:
        info = ssl._ssl._test_decode_cert(f.name)
    except Exception:
        return []
    finally:
        os.remove(f.name)
    return [v for k, v in info.get("subjectAltName", ()) if k == "DNS" and not v.startswith("*")]


# ---------------------------------------------------------------- the server's folders
def find_site_dirs(srv, domain):
    """(site folder, private folder) as the FTP account sees them, or None if not found."""
    top = srv.list("site", "")
    if "public_html" in top:
        return "/public_html", "/cs-admin"
    if "domains" in top and domain in srv.list("site", "domains"):
        return "/domains/%s/public_html" % domain, "/domains/%s/cs-admin" % domain
    return None


def connect(host, user, password, tls, port=21):
    return serverfs.FtpServer(host, user, password, "/", "/", tls=tls, port=port)


def check_private(srv):
    """The private folder exists, and files can be written, read and removed there."""
    for d in ("", "inbox", "inbox/.staging", "results", "state"):
        srv.mkdirs("private", d)
    probe = "setup-check-%s.txt" % secrets.token_hex(4)
    srv.write("private", probe, b"ok")
    ok = srv.read("private", probe) == b"ok"
    srv.remove("private", probe)
    if not ok:
        raise Stop("The private folder on the server cannot be written to (permissions?).")


# ---------------------------------------------------------------- GitHub
def gh(args, input_text=None, runner=subprocess.run):
    r = runner(["gh", *args], input=input_text.encode() if input_text is not None else None, capture_output=True)
    if r.returncode:
        raise Stop("GitHub: gh %s failed: %s" % (args[0], (r.stderr or b"").decode("utf-8", "replace").strip()[-300:]))
    return (r.stdout or b"").decode("utf-8", "replace").strip()


def github_repo(runner=subprocess.run):
    try:
        gh(["auth", "status"], runner=runner)
    except FileNotFoundError:
        raise Stop("The GitHub CLI (gh) is not installed: https://cli.github.com/ — then run: gh auth login")
    except Stop:
        raise Stop("The GitHub CLI is not signed in. Run: gh auth login")
    return gh(["repo", "view", "--json", "nameWithOwner", "-q", ".nameWithOwner"], runner=runner)


def set_secrets(repo, secrets_, variables, runner=subprocess.run):
    for k, v in secrets_.items():
        if v is not None and v != "":
            gh(["secret", "set", k, "--repo", repo], input_text=v, runner=runner)
    for k, v in variables.items():
        gh(["variable", "set", k, "--repo", repo, "--body", v], runner=runner)


def get_variable(repo, name, runner=subprocess.run):
    try:
        return gh(["variable", "get", name, "--repo", repo], runner=runner)
    except Stop:
        return ""


# ---------------------------------------------------------------- checks over the internet
class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *a, **kw):
        return None


def fetch(url, cookie=None):
    """(status, headers, body) without following redirects."""
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (setup check)", **({"Cookie": cookie} if cookie else {})})
    opener = urllib.request.build_opener(NoRedirect)
    try:
        with opener.open(req, timeout=60) as r:
            return r.status, r.headers, r.read()
    except urllib.error.HTTPError as ex:
        return ex.code, ex.headers, ex.read()
    except (urllib.error.URLError, OSError) as ex:
        return None, {}, str(ex).encode()


def check_online(base, admin_path, device_key):
    """[(what, ok, advice)] for the site at `base` and its upload page."""
    out = []
    st, _, body = fetch(base + "index.html")
    out.append(("the home page loads", st == 200 and "Χριστιανισμός".encode() in body,
                "got %s; check FTP_SITE_DIR" % st))
    st, _, body = fetch(base + "css/site.css")
    out.append(("the styles load", st == 200, "got %s" % st))
    st, _, _ = fetch(base + "podcast.xml")
    out.append(("the podcast feed loads", st == 200, "got %s" % st))
    page = base + admin_path + "/"
    st, _, body = fetch(page)
    out.append(("the upload page is invisible without the device key", st == 404, "got %s" % st))
    st, headers, body = fetch(page + "?k=" + urllib.parse.quote(device_key))
    php_ok = st == 303
    out.append(("PHP runs and finds its settings (cs-admin/config.php)", php_ok,
                "got %s: %s" % (st, "PHP does not run there (PHP version in DirectAdmin?)" if st == 200 and b"<?php" in body
                                else "config.php not found or the device key differs" if st == 404 else "unexpected answer")))
    if php_ok:
        cookie = "; ".join(c.split(";")[0] for c in headers.get_all("Set-Cookie") or [])
        st, _, body = fetch(page, cookie)
        out.append(("the sign-in page shows with the device key", st == 200 and "Σύνδεση".encode() in body, "got %s" % st))
    return out


def send_test_mail(settings, to):
    """Send one email with the given SMTP settings. Returns None, or what went wrong."""
    msg = EmailMessage()
    msg["Subject"] = "✓ Δοκιμαστικό μήνυμα: τα email της ιστοσελίδας λειτουργούν"
    msg["From"], msg["To"] = settings["MAIL_FROM"], to
    msg.set_content("Αυτό το μήνυμα στάλθηκε από την εγκατάσταση (tools/setup_server.py). "
                    "Με τον ίδιο τρόπο θα έρχεται ένα email κάθε φορά που δημοσιεύεται μια εκπομπή.")
    try:
        port = int(settings.get("SMTP_PORT") or 465)
        s = smtplib.SMTP_SSL(settings["SMTP_HOST"], port, timeout=60) if port == 465 else smtplib.SMTP(settings["SMTP_HOST"], port, timeout=60)
        with s:
            if port != 465:
                s.starttls()
            s.login(settings["SMTP_USER"], settings["SMTP_PASSWORD"])
            s.send_message(msg)
        return None
    except (OSError, smtplib.SMTPException) as ex:
        return str(ex) or type(ex).__name__


# ---------------------------------------------------------------- the steps
class Setup:
    def __init__(self, con=None, runner=subprocess.run, domain=DOMAIN, ftp_port=21, site_url=None, root=ROOT,
                 ftp_host=None, da_base=None, mailer=send_test_mail, mailbox_factory=None):
        self.con = con or Console()
        self.runner, self.domain, self.ftp_port, self.root = runner, domain, ftp_port, root
        self.site_url = site_url or "https://www.%s/" % domain
        self.ftp_host = ftp_host or domain                # the tests use their own servers
        self.da_base = da_base
        self.mailer = mailer
        self.mailbox_factory = mailbox_factory or mailwatch.Mailbox
        self.notes = []                                   # what the person must keep (shown at the end)
        self.da = None                                  # (base, user, password, verify) once given

    def say(self, *a):
        self.con.say(*a)

    def step(self, n, total, text):
        self.say("\n[%d/%d] %s" % (n, total, text))

    def ask_directadmin(self):
        if not self.da:
            base, verify = (self.da_base, True) if self.da_base else directadmin_base(self.con, self.domain)
            user = self.con.ask("  DirectAdmin user name (as on %s)" % base)
            pw = self.con.ask("  DirectAdmin password (used now only, not stored)", secret=True)
            self.da = (base, user, pw, verify)
        return self.da

    def ftp_account(self):
        """(host, user, password, tls) of a working FTP account."""
        con = self.con
        if con.yes("  Make a new FTP account for publishing now, with your DirectAdmin login?", True):
            base, da_user, da_pw, verify = self.ask_directadmin()
            password = strong_password()
            user = "%s@%s" % (FTP_NAME, self.domain)
            try:
                directadmin(base, da_user, da_pw, "CMD_API_FTP", {"action": "create", "domain": self.domain, "user": FTP_NAME,
                            "type": "domain", "passwd": password, "passwd2": password}, verify)
                made = True
            except Stop as ex:
                if "refused" in str(ex) or "reach" in str(ex):
                    raise
                self.say("  DirectAdmin did not make it (%s); perhaps it exists from an earlier run." % ex)
                made = False
            if made:
                self.say("  ✓ made the FTP account %s" % user)
                self.notes.append("FTP account: %s   password: %s" % (user, password))
                host, fresh = self.ftp_host, True
            else:
                host = con.ask("  FTP server", self.ftp_host)
                user = con.ask("  FTP user name", user)
                password = con.ask("  FTP password", secret=True)
                fresh = False
        else:
            host = con.ask("  FTP server", self.ftp_host)
            user = con.ask("  FTP user name")
            password = con.ask("  FTP password", secret=True)
            fresh = False
        tried = []
        for host_, tls in [(host, True)] + [(n, True) for n in cert_names(host, self.ftp_port) if n != host] + [(host, False)]:
            if host_ in [h for h, t in tried if t == tls]:
                continue
            tried.append((host_, tls))
            if not tls and not con.yes("  The server did not accept FTP over TLS. Use plain FTP (not encrypted)?", False):
                raise Stop("Ask webleaders to enable FTP over TLS (FTPS), or answer yes to use plain FTP.")
            for attempt in range(4 if fresh else 1):
                try:
                    connect(host_, user, password, tls, self.ftp_port).close()
                    self.say("  ✓ connected to %s%s" % (host_, " (encrypted)" if tls else ""))
                    return host_, user, password, tls
                except SystemExit as ex:              # login refused: a new account can take a moment
                    if attempt == (3 if fresh else 0):
                        raise Stop("The server refused the FTP login (%s)." % ex)
                    self.say("  the new account is not active yet; waiting…")
                    time.sleep(15)
                except serverfs.ServerError as ex:
                    self.say("  could not connect to %s%s: %s" % (host_, " with TLS" if tls else "", ex))
                    break
        raise Stop("Could not connect by FTP to %s." % host)

    def folders(self, host, user, password, tls):
        srv = connect(host, user, password, tls, self.ftp_port)
        try:
            found = find_site_dirs(srv, self.domain)
            if not found:
                site = self.con.ask("  The site's folder (public_html) as this FTP account sees it")
                found = (site, site.rstrip("/").rsplit("/", 1)[0] + "/cs-admin")
            site, private = found
            srv.roots = {"site": site, "private": private}
            n = len(srv.list("site", ""))
            if not n:
                raise Stop("The folder %s is empty or not readable; is it the site's folder?" % site)
            self.say("  ✓ the site's folder: %s (%d items)" % (site, n))
            check_private(srv)
            self.say("  ✓ the private folder: %s" % private)
            return site, private, srv
        except BaseException:
            srv.close()
            raise

    def page_settings(self, srv):
        """The upload page's config.php on the server: made now, or the existing one kept. Returns its settings."""
        existing = srv.read("private", "config.php")
        if existing:
            cfg = admin_user.parse(existing.decode("utf-8"))
            self.say("  ✓ the upload page already has settings (%d people); keeping them" % len(cfg["users"]))
            return cfg
        cfg = {"device_key": secrets.token_urlsafe(32), "users": {}}
        self.add_person(cfg)
        srv.write("private", "config.php", admin_user.render(cfg).encode())
        self.say("  ✓ saved in the private folder")
        return cfg

    def add_person(self, cfg):
        con = self.con
        while True:
            uid = con.ask("  User name for signing in (small letters/digits)").lower()
            if re.fullmatch(r"[a-z0-9._-]{3,32}", uid) and uid not in cfg["users"]:
                break
            self.say("  3–32 small letters or digits, not already used.")
        name = con.ask("  Full name (shown on the page)", uid)
        email = con.ask("  Email for the results (Enter for none)", optional=True)
        while True:
            pw = con.ask("  Password (at least 12 characters)", secret=True)
            if len(pw) >= 12 and pw == con.ask("  Password again", secret=True):
                break
            self.say("  At least 12 characters, the same twice.")
        totp = base64.b32encode(secrets.token_bytes(20)).decode().rstrip("=")
        cfg["users"][uid] = {"name": name, "email": email, "password": admin_user.password_hash(pw), "totp": totp}
        self.say("\n  ► On %s's phone, in an authenticator app (Google Authenticator, Microsoft Authenticator, 2FAS):" % name)
        self.say("    add an account by typing this key:  %s" % " ".join(totp[i:i + 4] for i in range(0, len(totp), 4)))
        self.say("    (or make a QR code of: otpauth://totp/%s?secret=%s&issuer=%s)\n" % (
            urllib.parse.quote("%s:%s" % (self.domain, uid)), totp, urllib.parse.quote("Χριστιανισμός & Επιστήμη")))
        return uid

    def email(self):
        con = self.con
        if not con.yes("  Send an email after each broadcast is published (from %s@%s)?" % (MAIL_NAME, self.domain), True):
            return {}
        if self.da or con.yes("  Make that mailbox now with your DirectAdmin login?", True):
            base, da_user, da_pw, verify = self.ask_directadmin()
            password = strong_password()
            try:
                directadmin(base, da_user, da_pw, "CMD_API_POP", {"action": "create", "domain": self.domain, "user": MAIL_NAME,
                            "passwd": password, "passwd2": password, "quota": "100", "limit": "0"}, verify)
            except Stop as ex:
                self.say("  mailbox not made (%s); no emails for now (run the setup again later)" % ex)
                return {}
            addr = "%s@%s" % (MAIL_NAME, self.domain)
            self.say("  ✓ made the mailbox %s" % addr)
            self.notes.append("Mailbox: %s   password: %s" % (addr, password))
            return {"SMTP_HOST": "mail." + self.domain, "SMTP_PORT": "465", "SMTP_USER": addr, "SMTP_PASSWORD": password,
                    "MAIL_FROM": addr}
        host = con.ask("  SMTP server", "mail." + self.domain)
        addr = con.ask("  Email address to send from")
        return {"SMTP_HOST": host, "SMTP_PORT": con.ask("  SMTP port", "465"), "SMTP_USER": addr,
                "SMTP_PASSWORD": con.ask("  Its password", secret=True), "MAIL_FROM": addr}

    def email_inbox(self):
        """Recordings emailed to science@christianity.gr: the mailbox's login, checked now (read-only)."""
        con = self.con
        if not con.yes("  Fetch recordings emailed to %s (WeTransfer links) and publish them?" % INCOMING, True):
            return {}
        addr = con.ask("  The mailbox", INCOMING)
        host = con.ask("  Its mail server (the name in its certificate)", INCOMING_HOST)
        trust = con.ask("  Who may send recordings (addresses, or @domain for a whole domain; comma between them)")
        trust_list = [t for t in re.split(r"[,\s;]+", trust) if t]
        while True:
            password = con.ask("  Password of %s (used by the robot only to read; nothing is changed)" % addr, secret=True)
            try:
                raws = self.mailbox_factory(host, 993, addr, password).recent()
                break
            except SystemExit as ex:
                self.say("  ✗ %s" % ex)
                if not con.yes("  Try another password?", True):
                    return {}
            except serverfs.ServerError as ex:
                self.say("  ✗ %s; email fetching is left out for now (run the setup again later)" % ex)
                return {}
        msgs = [mailwatch.parse(r) for r in raws]
        ours = [m for m in msgs if mailwatch.trusted(mailwatch.sender(m), trust_list)]
        links = [m for m in ours if mailwatch.wetransfer_links(m) or mailwatch.attachments(m)]
        self.say("  ✓ signed in to %s (read-only): %d emails in the last %d days, %d from the trusted senders, %d with recordings"
                 % (addr, len(msgs), mailwatch.DAYS, len(ours), len(links)))
        if msgs and not ours:
            senders = sorted({mailwatch.sender(m) for m in msgs})[:8]
            self.say("    (none from the trusted senders; recent senders were: %s)" % ", ".join(senders))
        return {"MAIL_IMAP_HOST": host, "MAIL_IMAP_USER": addr, "MAIL_IMAP_PASSWORD": password,
                "MAIL_TRUSTED_SENDERS": ", ".join(trust_list)}

    def try_mail(self, mail, to):
        problem = self.mailer(mail, to)
        if problem:
            self.say("  ✗ the test email could not be sent (%s): publishing still works, without emails" % problem)
        else:
            self.say("  ✓ a test email was sent to %s (check that it arrived, also in spam)" % to)

    # -- the whole first-time setup
    def first_time(self):
        T = 6
        if not os.path.isfile(os.path.join(self.root, "admin", "index.php")):
            raise Stop("This copy of the site has no upload page (admin/): switch to the publishing branch, or merge it first.")
        self.step(1, T, "Checking the GitHub CLI")
        repo = github_repo(self.runner)
        self.say("  ✓ repository %s" % repo)
        live = bool(get_variable(repo, "LIVE_URL", self.runner))
        if live:
            self.say("  the site is already live: it stays as it is; this run renews the settings")

        self.step(2, T, "FTP account for publishing")
        host, user, password, tls = self.ftp_account()

        self.step(3, T, "The site's folders on the server")
        site, private, srv = self.folders(host, user, password, tls)
        try:
            self.step(4, T, "The upload page: who may use it")
            cfg = self.page_settings(srv)
            admin_path = "diaxeirisi-" + "".join(secrets.choice(string.ascii_lowercase + string.digits) for _ in range(10))

            self.step(5, T, "Optional extras, and GitHub's settings")
            mail = self.email()
            me = [u.get("email") for u in cfg["users"].values() if u.get("email")]
            if mail and me:
                mail["MAIL_TO"] = me[0]
                self.try_mail(mail, me[0])
            incoming = self.email_inbox()
            key = self.con.ask("  Claude API key for suggested English titles and topics (Enter to skip)", secret=True, optional=True)
            test_dir = site.rstrip("/") + "/" + TEST_FOLDER
            target = site if live else test_dir
            set_secrets(repo, dict({"FTP_HOST": host, "FTP_USER": user, "FTP_PASSWORD": password, "FTP_SITE_DIR": target,
                                    "FTP_PRIVATE_DIR": private, "FTP_TLS": "1" if tls else "0", "ADMIN_PATH": admin_path,
                                    "ANTHROPIC_API_KEY": key}, **mail, **incoming),
                        {"CS_FTP_HOST": host, "CS_FTP_USER": user, "CS_FTP_TLS": "1" if tls else "0",
                         "CS_SITE_DIR": site, "CS_PRIVATE_DIR": private}, self.runner)
            self.say("  ✓ GitHub secrets set" + ("" if live else " (publishing goes to the test folder until --go-live)"))

            self.step(6, T, "Checking the live site" if live else "Trial: the new site in the test folder %s/" % TEST_FOLDER)
            srv.roots = {"site": target, "private": private}
            n = [0]

            def progress(line):
                n[0] += 1
                if line.startswith(("deploy:", "  ")) and (n[0] % 4 == 0 or line.startswith("deploy:")):
                    self.say("  " + line.strip())
            if not live:                                # once live, GitHub deploys (the page moves to its new address)
                deploy.deploy(srv, root=self.root, admin_path=admin_path, log=progress)
        finally:
            srv.close()
        base = self.site_url if live else self.site_url + TEST_FOLDER + "/"
        if live:
            self.say("  the upload page moves to its new address with the next deploy (any push, or Actions → Deploy → Run)")
            results = []
        else:
            results = check_online(base, admin_path, cfg["device_key"])
        for what, ok, advice in results:
            self.say("  %s %s%s" % ("✓" if ok else "✗", what, "" if ok else "  (" + advice + ")"))
        link = base + admin_path + "/?k=" + cfg["device_key"]
        self.say("\nDone." + ("" if live else " Look at the trial:  %s" % base))
        self.say("The upload page (open this link once on each computer/phone that will use it):\n  %s" % link)
        if not live:
            self.say("After going live the page's address is %s%s/ (same key)." % (self.site_url, admin_path))
        self.say("\nKeep these in a password manager (they are not shown again):")
        for n in self.notes + ["Upload page device link: " + link]:
            self.say("  " + n)
        if not live:
            self.say("\nWhen the trial looks right:  python tools/setup_server.py --go-live")
        return all(ok for _, ok, _ in results)

    def go_live(self):
        repo = github_repo(self.runner)
        site = get_variable(repo, "CS_SITE_DIR", self.runner)
        if not site:
            raise Stop("Run the first-time setup first: python tools/setup_server.py")
        git = lambda *a: subprocess.run(["git", *a], cwd=self.root, capture_output=True, text=True)
        branch = git("rev-parse", "--abbrev-ref", "HEAD").stdout.strip()
        if branch != "main":
            raise Stop("Going live is done from the main branch (now on %s): merge the publishing branch, then: git checkout main" % branch)
        if git("status", "--porcelain").stdout.strip():
            raise Stop("This copy has uncommitted changes; commit or put them aside first.")
        git("pull", "-q", "--ff-only")
        if not os.path.isfile(os.path.join(self.root, ".github", "workflows", "deploy.yml")):
            raise Stop("The deploy workflow is not on main yet: merge the publishing branch first.")
        self.say("This puts the new site on %s (the old site's replaced files are kept in cs-admin/old-site/)." % self.site_url)
        if not self.con.yes("Go live now?", False):
            return False
        set_secrets(repo, {"FTP_SITE_DIR": site}, {"LIVE_URL": self.site_url}, self.runner)
        p = os.path.join(self.root, "js", "broadcasts.js")
        js = open(p, encoding="utf-8").read()
        js = re.sub(r'(podcastSite: )"[^"]*"', lambda m: m.group(1) + '"%s"' % self.site_url, js, count=1)
        js = re.sub(r'(podcastAudio: )"[^"]*"', lambda m: m.group(1) + '""', js, count=1)
        with open(p, "w", encoding="utf-8", newline="\n") as f:
            f.write(js)
        r = subprocess.run([sys.executable, os.path.join(self.root, "tools", "build_all.py")], cwd=self.root,
                           capture_output=True, text=True)
        if r.returncode:
            git("checkout", "--", ".")
            raise Stop("The rebuild failed, so nothing was changed:\n" + (r.stdout + r.stderr)[-800:])
        git("add", "-A")
        git("commit", "-q", "-m", "Go live on %s: the podcast feed and audio from the site's own address" % self.site_url)
        r = git("push", "-q")
        if r.returncode:
            raise Stop("Could not push: " + r.stderr[-300:])
        self.say("  ✓ pushed; GitHub is deploying the site now (a few minutes): gh run watch")
        self.say("\nLast step, by hand (Spotify needs your login): Spotify for Creators → Settings → RSS feed →\n"
                 "  %spodcast.xml\nKeep the Render site for a few weeks, then turn it off." % self.site_url)
        return True

    def add_someone(self):
        repo = github_repo(self.runner)
        host, user = get_variable(repo, "CS_FTP_HOST", self.runner), get_variable(repo, "CS_FTP_USER", self.runner)
        private = get_variable(repo, "CS_PRIVATE_DIR", self.runner)
        if not host:
            raise Stop("Run the first-time setup first: python tools/setup_server.py")
        password = self.con.ask("FTP password of %s (from your password manager)" % user, secret=True)
        srv = serverfs.FtpServer(host, user, password, "/", private, tls=get_variable(repo, "CS_FTP_TLS", self.runner) != "0",
                                 port=self.ftp_port)
        try:
            raw = srv.read("private", "config.php")
            if not raw:
                raise Stop("The upload page has no settings yet; run the first-time setup.")
            cfg = admin_user.parse(raw.decode("utf-8"))
            uid = self.add_person(cfg)
            srv.write("private", "config.php", admin_user.render(cfg).encode())
        finally:
            srv.close()
        self.say("✓ %s can now sign in. Give them the device link (the same for everyone) from your password manager." % uid)
        return True


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--go-live", action="store_true")
    ap.add_argument("--add-person", action="store_true")
    a = ap.parse_args()
    s = Setup()
    try:
        ok = s.go_live() if a.go_live else s.add_someone() if a.add_person else s.first_time()
    except Stop as ex:
        print("\n✗ " + str(ex))
        return 1
    except KeyboardInterrupt:
        print("\nStopped. Nothing half-done is harmful: run it again whenever you like.")
        return 1
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
