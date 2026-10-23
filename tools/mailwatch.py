"""Recordings that arrive by email: WeTransfer links (or attached recordings) sent to science@christianity.gr.

    python tools/mailwatch.py            fetch new recordings and hand them to the inbox (tools/inbox.py publishes)
    python tools/mailwatch.py --check    only say how many new emails with recordings there are (for the workflow)
    python tools/mailwatch.py --announce tell MAIL_NOTIFY about every new email in the mailbox: its sender and
                                         subject only (one short email each; nothing else is read or sent)
    python tools/mailwatch.py --local DIR   use a folder standing in for the server (tests)

The mailbox is opened READ-ONLY: the server itself then refuses any change, so nothing is ever marked as
read, moved or deleted, and nobody's mail is touched. Only emails from trusted senders (MAIL_TRUSTED_SENDERS)
are looked at, and among those, any that the receiving server found to be forged (SPF/DKIM/DMARC "fail") are
ignored. Each email is handled once (private/state/mail-seen.json on the server).

For each new email with recordings:
  1. the recordings are downloaded (WeTransfer link, or attachments); other audio (wav, m4a, flac…) is
     converted to mp3; the parts are put in order by their file names;
  2. the title and the date are read from the email (subject, the transfer's title, the text). The date may
     also be the broadcast day just before the email (broadcasts are every second Thursday). Without a title in
     the email, it is read from the recordings' Greeklish names ("1_EPISTIMI_PAGKOSMIA_MERA_PSYXIKIS_YGEIAS.mp3" →
     «Παγκόσμια μέρα ψυχικής υγείας», tools/greeklish.py), if every word is one the site clearly spells that way;
  3. if both are clear, the broadcast goes to the inbox and is published automatically (with all of
     inbox.py's checks: never twice, real recordings…). If not, it waits in private/drafts/ and the admin
     is emailed to finish it on the upload page («Από email») with one click.
A WeTransfer link that cannot be downloaded (expired, or WeTransfer changed its site: its download interface is
not an official one) is tried again on the next runs; after a day the admin is emailed to upload by hand.

Settings (GitHub secrets):
  MAIL_IMAP_USER        science@christianity.gr
  MAIL_IMAP_PASSWORD    its password
  MAIL_IMAP_HOST        mail.christianity.gr (default: the name in the mail server's certificate)
  MAIL_IMAP_PORT        993 (default)        MAIL_IMAP_SSL   1 (default)
  MAIL_TRUSTED_SENDERS  who may send recordings: addresses or whole domains, e.g. "radio@christianity.gr, @christianity.gr"
  MAIL_NOTIFY           optional: who to tell about every new email (--announce), commas between several
plus the server settings (tools/serverfs.py) and, for the emails to the admin, the SMTP settings (tools/inbox.py).
"""
import argparse, datetime, email, email.policy, email.utils, hashlib, html, http.cookiejar, imaplib, json, os, re
import shutil, ssl, subprocess, sys, tempfile, time, unicodedata, urllib.error, urllib.parse, urllib.request, zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import greeklish, inbox, serverfs

ROOT = os.path.dirname(HERE)
SEEN = "state/mail-seen.json"
ANNOUNCED = "state/mail-announced.json"       # the emails MAIL_NOTIFY was told about (--announce)
DAYS = 10                        # emails older than this are not looked at (WeTransfer links expire anyway)
GIVE_UP_HOURS = 24               # a link that keeps failing for this long is reported to the admin
AUDIO = (".mp3", ".wav", ".m4a", ".aac", ".flac", ".ogg", ".opus", ".wma", ".aif", ".aiff")
MAX_BYTES = 3 * 1024 ** 3        # a broadcast's recordings, all together
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0 Safari/537.36"


class Unusable(Exception):
    """This email's recordings cannot be fetched now; the message says why."""


# ---------------------------------------------------------------- the mailbox (read-only)
class Mailbox:
    def __init__(self, host, port, user, password, use_ssl=True, folder="INBOX"):
        self.args = (host, port, user, password, use_ssl, folder)

    def recent(self, days=DAYS):
        """[raw email bytes] received in the last `days` days. The mailbox is opened read-only."""
        host, port, user, password, use_ssl, folder = self.args
        try:
            imap = imaplib.IMAP4_SSL(host, port, ssl_context=serverfs.tls_context(), timeout=60) if use_ssl \
                else imaplib.IMAP4(host, port, timeout=60)
        except ssl.SSLCertVerificationError as ex:
            raise SystemExit("The mail server's certificate is not for %s (%s); set MAIL_IMAP_HOST to the name it is for "
                             "(e.g. mail.christianity.gr)." % (host, ex.verify_message))
        except OSError as ex:
            raise serverfs.ServerError("could not reach the mail server %s: %s" % (host, ex))
        try:
            try:
                imap.login(user, password)
            except imaplib.IMAP4.error as ex:
                raise SystemExit("The mail server refused the login for %s: %s" % (user, ex))
            typ, _ = imap.select('"%s"' % folder, readonly=True)          # EXAMINE: no change is possible
            if typ != "OK":
                raise SystemExit("The mailbox has no folder %s." % folder)
            since = (datetime.date.today() - datetime.timedelta(days=days)).strftime("%d-%b-%Y")
            typ, data = imap.uid("SEARCH", None, "SINCE", since)
            out = []
            for uid in (data[0] or b"").split():
                typ, parts = imap.uid("FETCH", uid, "(BODY.PEEK[])")
                for p in parts:
                    if isinstance(p, tuple):
                        out.append(p[1])
            return out
        finally:
            try:
                imap.logout()
            except Exception:
                pass


    def headers(self, days=3):
        """[raw From/Subject/Message-ID/Date lines] of the emails of the last `days` days; nothing else is read."""
        host, port, user, password, use_ssl, folder = self.args
        try:
            imap = imaplib.IMAP4_SSL(host, port, ssl_context=serverfs.tls_context(), timeout=60) if use_ssl                 else imaplib.IMAP4(host, port, timeout=60)
        except OSError as ex:
            raise serverfs.ServerError("could not reach the mail server %s: %s" % (host, ex))
        try:
            try:
                imap.login(user, password)
            except imaplib.IMAP4.error as ex:
                raise SystemExit("The mail server refused the login for %s: %s" % (user, ex))
            if imap.select('"%s"' % folder, readonly=True)[0] != "OK":     # EXAMINE: no change is possible
                raise SystemExit("The mailbox has no folder %s." % folder)
            since = (datetime.date.today() - datetime.timedelta(days=days)).strftime("%d-%b-%Y")
            typ, data = imap.uid("SEARCH", None, "SINCE", since)
            out = []
            for uid in (data[0] or b"").split():
                typ, parts = imap.uid("FETCH", uid, "(BODY.PEEK[HEADER.FIELDS (FROM SUBJECT MESSAGE-ID DATE)])")
                out += [p[1] for p in parts if isinstance(p, tuple)]
            return out
        finally:
            try:
                imap.logout()
            except Exception:
                pass


def parse(raw):
    return email.message_from_bytes(raw, policy=email.policy.default)


def sender(msg):
    """The address in From (for a WeTransfer email: WeTransfer's own)."""
    return (email.utils.parseaddr(str(msg.get("From", "")))[1] or "").lower()


WETRANSFER = "wetransfer.com"


def real_sender(msg):
    """Who sent the recordings. WeTransfer's emails come from noreply@wetransfer.com; the person who made the
    transfer is in Reply-To (WeTransfer puts the address it checked there), and in the subject ("x@y sent you")."""
    frm = sender(msg)
    if not frm.endswith("@" + WETRANSFER):
        return frm
    rt = (email.utils.parseaddr(str(msg.get("Reply-To", "")))[1] or "").lower()
    if rt:
        return rt
    m = re.match(r"\s*([^\s@]+@[^\s@]+)\s+(?:sent you|σας έστειλε)", str(msg.get("Subject", "")), re.I)
    return m.group(1).lower() if m else ""


def genuine(raw, msg, dnsfunc=None):
    """Whether the email really comes from the domain in its From: a valid DKIM signature of that domain.
    True / False, or None if it cannot be checked here (the dkimpy library is not installed)."""
    try:
        import dkim
    except ImportError:
        return None
    try:
        d = dkim.DKIM(raw)
        ok = d.verify(dnsfunc=dnsfunc) if dnsfunc else d.verify()
    except Exception:                                  # a broken or missing signature
        return False
    signed = (d.domain or b"").decode("ascii", "replace").lower()
    domain = sender(msg).rsplit("@", 1)[-1]
    return bool(ok and signed and (domain == signed or domain.endswith("." + signed)))


def trusted(address, trust):
    """Whether the address is among the trusted ones (exact addresses, or "@domain" for a whole domain)."""
    address = address.lower().strip()
    for t in trust:
        t = t.lower().strip()
        if t and (address == t or (t.startswith("@") and address.endswith(t))):
            return True
    return False


def forged(msg):
    """True if the receiving server's checks (Authentication-Results) say the sender is forged."""
    for h in msg.get_all("Authentication-Results") or []:
        if re.search(r"\b(spf|dkim|dmarc)=fail\b", str(h), re.I):
            return True
    return False


def message_id(msg, raw):
    mid = str(msg.get("Message-ID", "")).strip()
    return mid or "sha256:" + hashlib.sha256(raw).hexdigest()


def received_date(msg):
    try:
        return email.utils.parsedate_to_datetime(str(msg.get("Date"))).date()
    except (TypeError, ValueError):
        return datetime.date.today()


def texts(msg):
    """The email's text, plain and from HTML (links kept)."""
    out = []
    for part in msg.walk():
        if part.get_content_maintype() != "text" or part.get_filename():
            continue
        try:
            body = part.get_content()
        except (LookupError, ValueError):
            body = part.get_payload(decode=True).decode("utf-8", "replace") if part.get_payload(decode=True) else ""
        if part.get_content_subtype() == "html":
            body = re.sub(r'(?is)<a\b[^>]*href="([^"]+)"[^>]*>', r" \1 ", body)
            body = html.unescape(re.sub(r"(?s)<[^>]+>", " ", body))
        out.append(body)
    return out


LINK = re.compile(r"https?://(?:we\.tl|(?:www\.)?wetransfer\.com|[a-z0-9-]+\.wetransfer\.com)/[^\s<>\"')\]]+", re.I)


def wetransfer_links(msg):
    """The transfers linked in the email, each once (WeTransfer's emails repeat the link with other tracking codes)."""
    seen, keys = [], set()
    for t in texts(msg):
        for m in LINK.finditer(t):
            u = m.group(0).rstrip(".,;")
            p = urllib.parse.urlparse(u)
            tid = re.search(r"/downloads/([0-9A-Za-z]+)/[0-9A-Za-z]+", p.path)
            if not tid and not re.match(r"(?i)^/t-[0-9A-Za-z]+", p.path or ""):
                continue                                   # not a whole download link (e.g. one cut off by a line break)
            key = tid.group(1) if tid else p.netloc.lower() + p.path
            if key not in keys:
                keys.add(key)
                seen.append(u)
    return seen


def attachments(msg):
    """[(file name, bytes)] of the audio files attached to the email."""
    out = []
    for part in msg.walk():                       # also inside a forwarded email
        if part.is_multipart() or part.get_content_type() == "message/rfc822":
            continue
        name = os.path.basename(part.get_filename() or "")
        if name.lower().endswith(AUDIO):
            out.append((name, part.get_payload(decode=True) or b""))
    return out


def contents(msg):
    """What an email holds, for the log when no recordings are found in it: the websites it links to and the kinds
    of files attached (never an address, a name or any text: the workflow's logs are public)."""
    hosts = sorted({urllib.parse.urlparse(u).netloc.lower() for t in texts(msg)
                    for u in re.findall(r"https?://[^\s<>\"')\]]+", t)} - {""})
    files = sorted({(os.path.splitext(part.get_filename())[1].lower() or "?") + " " + part.get_content_type()
                    for part in msg.walk() if part.get_filename()})
    return "links to %s; attached: %s" % (", ".join(hosts[:12]) or "nothing", ", ".join(files) or "nothing")


# ---------------------------------------------------------------- WeTransfer (its website's own interface)
class WeTransfer:
    """Downloads a transfer the way wetransfer.com's download page does. Not an official interface: if WeTransfer
    changes its site this stops working, and the admin is told (nothing else breaks)."""

    def __init__(self, base=None):
        self.base = (base or os.environ.get("WETRANSFER_BASE") or "https://wetransfer.com").rstrip("/")
        self.jar = http.cookiejar.CookieJar()
        self.web = urllib.request.build_opener(urllib.request.HTTPSHandler(context=serverfs.tls_context()),
                                               urllib.request.HTTPCookieProcessor(self.jar))
        self.web.addheaders = [("User-Agent", UA)]
        self.token = None

    def _get(self, url):
        try:
            with self.web.open(url, timeout=60) as r:
                return r.geturl(), r.read().decode("utf-8", "replace")
        except urllib.error.HTTPError as ex:
            raise Unusable("WeTransfer: %s answered %s" % (url, ex.code) + (" (expired?)" if ex.code in (404, 410) else ""))
        except (urllib.error.URLError, OSError) as ex:
            raise Unusable("WeTransfer could not be reached (%s)" % getattr(ex, "reason", ex))

    def _post(self, path, data):
        req = urllib.request.Request(self.base + path, data=json.dumps(data).encode(), method="POST")
        req.add_header("Content-Type", "application/json")
        req.add_header("Accept", "application/json")
        req.add_header("X-Requested-With", "XMLHttpRequest")
        if self.token:
            req.add_header("X-CSRF-Token", self.token)
        try:
            with self.web.open(req, timeout=60) as r:
                return json.loads(r.read().decode("utf-8") or "{}")
        except urllib.error.HTTPError as ex:
            raise Unusable("WeTransfer refused the download (%s)%s" % (
                ex.code, ": the link has expired" if ex.code in (404, 410) else ": perhaps it changed its site"))
        except (urllib.error.URLError, OSError, ValueError) as ex:
            raise Unusable("WeTransfer: %s" % getattr(ex, "reason", ex))

    def locate(self, link):
        """(transfer id, recipient id or None, security hash) of a link (short we.tl links are followed)."""
        if os.environ.get("WETRANSFER_BASE"):              # tests: WeTransfer's links lead to the stand-in
            p = urllib.parse.urlparse(link)
            link = self.base + p.path + ("?" + p.query if p.query else "")
        url, page = (link, "") if "/downloads/" in link else self._get(link)
        if "/downloads/" not in url:
            m = re.search(r'https?://[^"\s]*/downloads/[^"\s]+', page)
            url = m.group(0) if m else url
        m = re.search(r"/downloads/([0-9A-Za-z]+)/(?:([0-9A-Za-z]+)/)?([0-9A-Za-z]+)", urllib.parse.urlparse(url).path)
        if not m:
            raise Unusable("WeTransfer: the link %s does not lead to a download (expired?)" % link)
        return m.group(1), m.group(2), m.group(3)

    def fetch(self, link, folder):
        """Download every file of the transfer into `folder`. Returns ([file paths], the transfer's title or "")."""
        transfer, recipient, secret = self.locate(link)
        _, home = self._get(self.base + "/")
        m = re.search(r'name="csrf-token" content="([^"]+)"', home)
        self.token = m.group(1) if m else None
        ask = {"security_hash": secret}
        if recipient:
            ask["recipient_id"] = recipient
        info = {}
        try:
            info = self._post("/api/v4/transfers/%s/prepare-download" % transfer, ask)
        except Unusable:
            pass                                          # only the title comes from here; the download may still work
        if info.get("state") == "expired":
            raise Unusable("The WeTransfer link has expired.")
        got = self._post("/api/v4/transfers/%s/download" % transfer, dict(ask, intent="entire_transfer"))
        url = got.get("direct_link")
        if not url:
            raise Unusable("WeTransfer gave no download (perhaps it changed its site): %s" % str(got)[:200])
        title = str(info.get("display_name") or info.get("message") or "").strip()
        names = [str(f.get("name") or "") for f in info.get("files") or info.get("items") or []]
        return self._save(url, folder, names), title

    def _save(self, url, folder, names):
        path = os.path.join(folder, "transfer.download")
        total = 0
        try:
            with self.web.open(url, timeout=600) as r, open(path, "wb") as f:
                disposition = r.headers.get("Content-Disposition", "")
                for block in iter(lambda: r.read(1 << 20), b""):
                    total += len(block)
                    if total > MAX_BYTES:
                        raise Unusable("The transfer is larger than %d GB." % (MAX_BYTES >> 30))
                    f.write(block)
        except (urllib.error.URLError, OSError) as ex:
            raise Unusable("WeTransfer download failed (%s)" % getattr(ex, "reason", ex))
        if zipfile.is_zipfile(path):
            return unzip(path, folder)
        m = re.search(r"filename\*?=(?:UTF-8'')?\"?([^\";]+)", disposition)
        name = urllib.parse.unquote(m.group(1)) if m else (names[0] if len(names) == 1 else "recording.mp3")
        final = os.path.join(folder, safe_name(name))
        os.replace(path, final)
        return [final]


def safe_name(name):
    name = os.path.basename(name.replace("\\", "/")).strip() or "recording"
    return re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", name)


def unzip(path, folder):
    """The audio files in a zip (folders inside it flattened; nothing written outside `folder`)."""
    out = []
    with zipfile.ZipFile(path) as z:
        for info in z.infolist():
            name = safe_name(info.filename)
            if info.is_dir() or not name.lower().endswith(AUDIO) or name.startswith("._"):
                continue                                   # also the "._" files macOS adds
            dest = os.path.join(folder, name)
            n = 1
            while os.path.exists(dest):
                stem, ext = os.path.splitext(name)
                dest = os.path.join(folder, "%s-%d%s" % (stem, n, ext))
                n += 1
            with z.open(info) as src, open(dest, "wb") as f:
                shutil.copyfileobj(src, f)
            out.append(dest)
    os.remove(path)
    return out


def natural(name):
    return [int(t) if t.isdigit() else t.lower() for t in re.split(r"(\d+)", os.path.basename(name))]


def as_mp3(paths, folder):
    """mp3s, in order: others converted (192 kbit/s)."""
    out = []
    for p in sorted(paths, key=natural):
        if p.lower().endswith(".mp3"):
            out.append(p)
            continue
        mp3 = os.path.splitext(p)[0] + ".mp3"
        r = subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", p, "-vn", "-c:a", "libmp3lame", "-b:a", "192k", mp3],
                           capture_output=True)
        if r.returncode:
            raise Unusable("The file %s could not be converted to mp3." % os.path.basename(p))
        out.append(mp3)
    return out


# ---------------------------------------------------------------- title and date from the email
MONTHS = {m: i for i, ms in enumerate([("ιανουαρ",), ("φεβρουαρ",), ("μαρτ", "μαρτι"), ("απριλ",), ("μαι", "μαΐ", "μαϊ"),
                                        ("ιουν",), ("ιουλ",), ("αυγουστ",), ("σεπτεμβρ",), ("οκτωβρ",), ("νοεμβρ",),
                                        ("δεκεμβρ",)], 1) for m in ms}
NOISE = re.compile(r"(?i)^\s*((fwd?|re|προώθηση|απ|πρθ|σχετ)\s*:\s*)+|\bvia wetransfer\b|\bwetransfer\b|"
                   r"\byou(?:'ve)? received (?:some )?files?\b|\bsent you (?:some )?files?\b|\bhas sent you\b|"
                   r"^\s*(η\s+)?εκπομπ[ήη]\s*(της)?\s*[:\-–]?|^\s*της\s*[:\-–]?|\bχριστιανισμός\s*&\s*επιστήμη\b\s*[:\-–]?")


def plain(s):
    return "".join(c for c in unicodedata.normalize("NFD", s.lower()) if unicodedata.category(c) != "Mn")


def nearest_year(day, month, around):
    """The date with that day and month nearest to `around` (a date written without its year)."""
    best = None
    for y in (around.year - 1, around.year, around.year + 1):
        try:
            d = datetime.date(y, month, day)
        except ValueError:
            continue
        if best is None or abs((d - around).days) < abs((best - around).days):
            best = d
    return best


def find_date(text, around):
    """(date, the matched text) of the first date written in the text, or (None, None)."""
    full = [r"\b(20\d\d)[-_./](\d{1,2})[-_./](\d{1,2})\b",                      # 2026-10-15
            r"\b(\d{1,2})[-_./](\d{1,2})[-_./]((?:20)?\d\d)\b"]                  # 15/10/2026, 15.10.26
    for i, pat in enumerate(full):
        for m in re.finditer(pat, text):
            y, mo, d = (m[1], m[2], m[3]) if i == 0 else (m[3], m[2], m[1])
            try:
                return datetime.date(int(y) + (2000 if len(y) == 2 else 0), int(mo), int(d)), m.group(0)
            except ValueError:
                continue
    for m in re.finditer(r"(?<![\d/.\-])(\d{1,2})[/.](\d{1,2})(?![\d/.\-])", text):   # 15/10
        d = nearest_year(int(m[1]), int(m[2]), around) if 1 <= int(m[2]) <= 12 else None
        if d and abs((d - around).days) <= 30:          # "2.5" or "1/2 ώρα" are not dates
            return d, m.group(0)
    for m in re.finditer(r"(?<![\d/.\-])(\d{1,2})(?:ης|η)\b", text):               # της 15ης
        for back in range(0, 31):
            d = around - datetime.timedelta(days=back)
            if d.day == int(m[1]):
                return d, m.group(0)
    low = plain(text)                                                            # 15 Οκτωβρίου (2026)
    for m in re.finditer(r"\b(\d{1,2})\s+([α-ω]+)(?:\s+(20\d\d))?", low):
        month = next((n for stem, n in MONTHS.items() if m.group(2).startswith(plain(stem))), None)
        if not month:
            continue
        d = None
        if m.group(3):
            try:
                d = datetime.date(int(m.group(3)), month, int(m.group(1)))
            except ValueError:
                d = None
        else:
            d = nearest_year(int(m.group(1)), month, around)
            d = d if d and abs((d - around).days) <= 60 else None
        if d:
            return d, text[m.start():m.end()]
    return None, None


SENT_FILES = re.compile(r"(?i)\bsent you\b|\bvia wetransfer\b|\byou(?:'ve)? received\b|\bhas shared\b|"
                        r"σας έστειλε|σου έστειλε|έλαβες|λάβατε|μέσω wetransfer")


GENERIC = set("""η ο το τα οι τη την της του των και με για σε στο στη στην απο νεα νεο νεες νεος αρχεια αρχειο αρχειων
εκπομπη εκπομπης εκπομπες εκπομπων ηχογραφηση ηχογραφησεις ηχογραφησης ηχητικο ηχητικα μερη μερος μερους ημιωρο ημιωρα
τελικο τελικη τελικα εδω οριστε σας στελνω files file recording recordings audio mp3 wav new the final part parts show
broadcast here""".split())


def clean_title(s, date_text=None):
    s = s or ""
    if SENT_FILES.search(s):                           # WeTransfer's own subject ("Maria sent you files"): no title in it
        return ""
    if date_text:
        s = s.replace(date_text, " ")
    s = re.sub(r"\.(mp3|wav|m4a|zip)\b", " ", s, flags=re.I)
    while True:                                        # "Fwd: Εκπομπή – Τίτλος": each removal can uncover the next
        before = s
        s = re.sub(r"\s+", " ", NOISE.sub(" ", s)).strip(" -–—:|,._()[]")
        if s == before:
            break
    if s.startswith("«") and s.endswith("»") and s.count("»") == 1:
        s = s[1:-1].strip()
    words = re.findall(r"[^\W_]+", plain(s))
    if all(w.isdigit() or w in GENERIC for w in words):   # "Τα αρχεία", "Η ηχογράφηση": not a title
        return ""
    return s if len(re.findall(r"[^\W\d_]", s)) >= 4 else ""


def schedule_day(received, next_broadcast):
    """The broadcast day (every second Thursday, counted from SITE_CONFIG.nextBroadcast) on or just before `received`."""
    try:
        anchor = datetime.date.fromisoformat(next_broadcast[:10])
    except (TypeError, ValueError):
        return None
    days = (received - anchor).days
    day = anchor + datetime.timedelta(days=days - days % 14)
    return day if 0 <= (received - day).days <= 13 else None


def title_and_date(msg, transfer_title, site, names=()):
    """(title or "", date or None, how the date was found).

    WeTransfer's own emails are a template ("x@y sent you file.mp3 via WeTransfer … Expires on 18 October"): only the
    transfer's title is read from them, and only if it is not just one of the file names (WeTransfer uses the first
    file's name when the sender gives no title)."""
    received = received_date(msg)
    stems = {os.path.splitext(os.path.basename(n))[0].lower() for n in names} | {os.path.basename(n).lower() for n in names}
    if transfer_title and transfer_title.strip().lower() in stems:
        transfer_title = ""
    if sender(msg).endswith("@" + WETRANSFER):
        candidates = [transfer_title or ""]
    else:
        candidates = [str(msg.get("Subject", "")), transfer_title or ""] + texts(msg)[:1]
    date, how = None, ""
    for c in candidates:
        d, txt = find_date(c, received)
        if d:
            date, how = d, "written in the email"
            break
    if not date:
        date = schedule_day(received, site["config"].get("nextBroadcast"))
        how = "the broadcast day before the email" if date else ""
    title = ""
    for c in candidates[:2]:
        _, txt = find_date(c, received)
        title = clean_title(c, txt)
        if title:
            break
    return title, date, how


# ---------------------------------------------------------------- handing over to the inbox
def name_stem(files):
    """What the recordings' file names have in common, as words: "1_EPISTIMI_PAGKOSMIA_MERA.mp3",
    "2_EPISTIMI_PAGKOSMIA_MERA.mp3" → "EPISTIMI PAGKOSMIA MERA". "" if they have nothing in common."""
    stems = set()
    for f in files:
        s = os.path.splitext(os.path.basename(f))[0]
        s = re.sub(r"(?i)^\s*(part|meros|μέρος)?[\s_.\-]*\(?\d{1,2}\)?[\s_.\-]+", "", s)       # leading part numbers
        s = re.sub(r"(?i)[\s_.\-]*\(?(part|meros|μέρος)?[\s_.\-]*\d{1,2}\)?\s*$", "", s)       # trailing ones
        stems.add(re.sub(r"\s+", " ", re.sub(r"[_\-.]+", " ", s)).strip())
    return stems.pop() if len(stems) == 1 else ""


def suggest_title(files, site):
    """A Greek title suggested from the file names, for the admin to check («Από email»); "" if there is none.
    Greek names are used as they are; names in Latin letters ("Greeklish") are put into proper Greek by Claude
    (only with ANTHROPIC_API_KEY; never required)."""
    stem = name_stem(files)
    if not stem or len(re.findall(r"[^\W\d_]", stem)) < 4:
        return ""
    if re.search(r"[α-ωΑ-Ωά-ώ]", stem):
        stem = clean_title(stem)                         # "Εκπομπή" alone is not a title
        return stem[:1].upper() + stem[1:]
    if not os.environ.get("ANTHROPIC_API_KEY"):
        return ""
    try:
        import anthropic
    except ImportError:
        return ""
    examples = "\n".join("- " + e["title"] for e in list(site["by_date"].values())[:15])
    prompt = ("These are the recordings of a broadcast of the Greek radio programme «Χριστιανισμός & Επιστήμη». "
              "Their file names, written in Latin letters (Greeklish), have this in common: %r.\n"
              "Write the broadcast's title in proper Greek, with accents, in the same style as these earlier titles:\n%s\n\n"
              "A leading EPISTIMI (Επιστήμη) or XRISTIANISMOS is the programme's name, not part of the title: leave it "
              "out. If you cannot tell what the title is, answer with an empty title." % (stem, examples))
    schema = {"type": "object", "additionalProperties": False, "required": ["title"], "properties": {"title": {"type": "string"}}}
    try:
        client = anthropic.Anthropic(timeout=120, max_retries=2)
        r = client.beta.messages.create(
            model="claude-opus-5-5", max_tokens=16000,
            betas=["server-side-fallback-2026-07-01"], fallbacks="default",
            output_config={"effort": "low", "format": {"type": "json_schema", "schema": schema}},
            messages=[{"role": "user", "content": prompt}])
        if r.stop_reason != "end_turn":
            return ""
        title = json.loads("".join(b.text for b in r.content if b.type == "text")).get("title", "")
        return inbox.clean_text(title, "title", required=False)
    except Exception as ex:                              # a suggestion is never required
        print("  Claude: no title suggestion (%s)" % ex)
        return ""


def hand_over(srv, files, fields, folder):
    """Put a broadcast request (as the upload page makes it) into private/<folder>/<id>/, appearing in one step."""
    ident = time.strftime("%Y%m%d-%H%M%S-") + os.urandom(4).hex()
    staging = "inbox/.staging/" + ident
    listed = []
    for i, p in enumerate(files, 1):
        name = "part-%d.mp3" % i
        srv.upload(p, "private", staging + "/" + name)
        listed.append({"name": name, "original": os.path.basename(p), "bytes": os.path.getsize(p)})
    req = dict(fields, type="broadcast", id=ident, created=datetime.datetime.now().isoformat(timespec="seconds"),
               user="email", files=listed)
    srv.write("private", staging + "/request.json", json.dumps(req, ensure_ascii=False, indent=1).encode())
    srv.move("private", staging, "private", folder + "/" + ident)
    return ident


class Watch:
    def __init__(self, srv, mailbox, trust, root=ROOT, log=print, wetransfer=None, notify=None, verify=None, words_root=None):
        self.srv, self.mailbox, self.trust, self.root, self.log = srv, mailbox, trust, root, log
        self.words_root = words_root or root                  # whose pages teach Greek spelling (tools/greeklish.py)
        self.verify = verify or genuine
        self.wetransfer = wetransfer or WeTransfer
        self.notify = notify or tell_admin

    def load_seen(self):
        return json.loads(self.srv.read("private", SEEN) or b"{}")

    def save_seen(self, seen):
        cutoff = time.time() - 60 * 86400
        seen = {k: v for k, v in seen.items() if v.get("time", 0) > cutoff}
        self.srv.write("private", SEEN, json.dumps(seen, ensure_ascii=False, indent=1).encode())

    def new_emails(self):
        """[(message id, message, verified)] of not yet handled emails with recordings from trusted senders.

        For an email to count, the person behind it must be trusted (for WeTransfer's emails: the transfer's sender),
        and the email must not be forged: its DKIM signature must be valid for the domain it comes from (WeTransfer's
        own, for its emails). If signatures cannot be checked here, `verified` is None: such recordings are never
        published automatically, they wait for the admin."""
        seen, out = self.load_seen(), []
        for raw in self.mailbox.recent():
            msg = parse(raw)
            mid = message_id(msg, raw)
            if seen.get(mid, {}).get("done"):
                continue
            who = real_sender(msg)
            if not trusted(who, self.trust):
                continue
            if not (wetransfer_links(msg) or attachments(msg)):
                self.log("an email from a trusted sender without recordings found in it: " + contents(msg))
                continue
            verified = self.verify(raw, msg)
            if verified is False or forged(msg):
                self.log("ignored (not really from %s): %s" % (sender(msg).rsplit("@", 1)[-1], msg.get("Subject")))
                continue
            out.append((mid, msg, verified))
        return out

    def run(self):
        emails = self.new_emails()
        if not emails:
            return 0
        seen, problems = self.load_seen(), 0
        site = inbox.load_site(self.root)
        for mid, msg, verified in emails:
            entry = seen.setdefault(mid, {"first": time.time()})
            entry["time"] = time.time()
            subject = str(msg.get("Subject", ""))
            who = real_sender(msg)
            self.log("email from %s: %s" % (who, subject))
            work = tempfile.mkdtemp(prefix="cs-mail-")
            try:
                files, transfer_title = [], ""
                for name, data in attachments(msg):
                    p = os.path.join(work, safe_name(name))
                    with open(p, "wb") as f:
                        f.write(data)
                    files.append(p)
                failed = []
                for link in wetransfer_links(msg):
                    try:
                        got, t = self.wetransfer().fetch(link, work)
                    except Unusable as ex:                  # another link of the email may still work
                        failed.append(str(ex))
                        continue
                    files += got
                    transfer_title = transfer_title or t
                if not files:
                    raise Unusable(failed[0] if failed else "No recordings were found in the transfer.")
                files = as_mp3(files, work)[:inbox.MAX_PARTS]
                title, date, how = title_and_date(msg, transfer_title, site, names=files)
                fields = {"date": date.isoformat() if date else "", "title": title, "title_en": "", "tags": [],
                          "replace": False, "email": "", "from_email": {"from": who, "subject": subject, "date_from": how}}
                if not title:                               # e.g. "1_EPISTIMI_PAGKOSMIA_MERA_PSYXIKIS_YGEIAS.mp3"
                    named, named_sure = greeklish.title(os.path.basename(files[0]), self.words_root)
                    if named_sure:                          # every word one the site spells this way: the title
                        title = fields["title"] = named
                        fields["from_email"]["title_from"] = "the file names"
                        self.log("  title from the file names: %s" % named)
                    else:
                        fields["title_suggestion"] = named or suggest_title(files, site) or ""
                # published by itself only when everything is clear: a Greek title (like every title on the site),
                # a date, and an email whose signature was checked
                sure = bool(title and re.search(r"[α-ωά-ώΑ-Ω]", title) and date and verified)
                where = "inbox" if sure else "drafts"
                ident = hand_over(self.srv, files, fields, where)
                entry.update(done=True, outcome=where, request=ident)
                self.log("  -> %s (%d recordings, date %s, title %r)" % (where, len(files), fields["date"] or "?", title))
                if not sure:
                    why = ("δεν βρέθηκε ο τίτλος" if not title else "δεν βρέθηκε η ημερομηνία" if not date
                           else "η υπογραφή του email δεν μπόρεσε να ελεγχθεί")
                    self.notify("Ηχογραφήσεις από email περιμένουν να συμπληρωθούν",
                                "Ήρθαν %d ηχογραφήσεις με email από %s («%s»), αλλά %s. Ανοίξτε τη σελίδα διαχείρισης, "
                                "καρτέλα «Από email», για να τις δημοσιεύσετε με ένα κλικ." % (len(files), who, subject, why))
            except Unusable as ex:                        # tried again next time; the admin is told after a day
                entry["error"] = str(ex)
                self.log("  could not fetch the recordings: %s" % ex)
                if time.time() - entry["first"] > GIVE_UP_HOURS * 3600:
                    entry.update(done=True, outcome="failed")
                    self.notify("Οι ηχογραφήσεις από email δεν μπόρεσαν να ληφθούν",
                                "Το email από %s («%s») έχει σύνδεσμο WeTransfer, αλλά οι ηχογραφήσεις δεν μπόρεσαν να "
                                "ληφθούν αυτόματα (%s). Ανεβάστε τις από τη σελίδα διαχείρισης, «Νέα εκπομπή»." % (who, subject, ex))
            finally:
                shutil.rmtree(work, ignore_errors=True)
                self.save_seen(seen)
        return problems


def announce(srv, mailbox, to, send=None, log=print):
    """Tell `to` about each email not announced before: its sender and subject, nothing else. The first time, the
    emails already there are only noted, so nobody is sent the last days' mail at once. Returns how many were told."""
    send = send or inbox.send_mail
    raw = srv.read("private", ANNOUNCED)
    first = raw is None
    done = json.loads(raw or b"{}")
    told = 0
    for head in mailbox.headers():
        msg = parse(head)
        mid = message_id(msg, head)
        if mid in done:
            continue
        if not first:
            who = " ".join(str(msg.get("From", "")).split()) or "(άγνωστος αποστολέας)"
            subject = " ".join(str(msg.get("Subject", "")).split()) or "(χωρίς θέμα)"
            if not send(to, "Νέο email στο science@: " + subject[:150], "Από: %s\nΘέμα: %s" % (who, subject)):
                log("  could not tell about an email; trying again next time")
                continue
            told += 1
        done[mid] = time.time()
    cutoff = time.time() - 30 * 86400
    srv.write("private", ANNOUNCED, json.dumps({k: v for k, v in done.items() if v > cutoff}).encode())
    log("first look: %d emails noted, none announced" % len(done) if first else "%d new emails announced" % told)
    return told


def tell_admin(subject, text):
    """An email to MAIL_TO (the inbox's SMTP settings); printed if they are not set."""
    result = {"status": "info", "message": text, "title": subject, "type": "broadcast"}
    if os.environ.get("SMTP_HOST") and os.environ.get("MAIL_TO"):
        inbox.notify(result, {"email": ""})
    print("  (admin told: %s)" % subject)


def from_env():
    user = os.environ.get("MAIL_IMAP_USER")
    if not (user and os.environ.get("MAIL_IMAP_PASSWORD")):
        return None, []
    box = Mailbox(os.environ.get("MAIL_IMAP_HOST") or "mail.christianity.gr", int(os.environ.get("MAIL_IMAP_PORT") or 993),
                  user, os.environ["MAIL_IMAP_PASSWORD"], os.environ.get("MAIL_IMAP_SSL", "1") != "0",
                  os.environ.get("MAIL_IMAP_FOLDER") or "INBOX")
    trust = [t for t in re.split(r"[,\s;]+", os.environ.get("MAIL_TRUSTED_SENDERS", "")) if t]
    return box, trust


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--announce", action="store_true")
    ap.add_argument("--local")
    a = ap.parse_args(argv)
    box, trust = from_env()
    if not box:
        print("Email is not set up (MAIL_IMAP_USER / MAIL_IMAP_PASSWORD); nothing to do.")
        return 0
    if a.announce:
        to = [t for t in re.split(r"[,\s;]+", os.environ.get("MAIL_NOTIFY", "")) if "@" in t]
        if not to or not os.environ.get("SMTP_HOST"):
            print("Nobody to tell about new emails (MAIL_NOTIFY), or no way to send (SMTP_…); nothing to do.")
            return 0
        if not a.local and not serverfs.configured():
            print("The server is not set up yet; nothing to do.")
            return 0
        srv = serverfs.connect(a.local)
        try:
            announce(srv, box, to)
        finally:
            srv.close()
        return 0
    if not trust:
        print("No trusted senders (MAIL_TRUSTED_SENDERS); nothing is fetched from email.")
        return 0
    if not a.local and not serverfs.configured():
        print("The server is not set up yet; nothing to do.")
        return 0
    srv = serverfs.connect(a.local)
    try:
        w = Watch(srv, box, trust)
        if a.check:
            n = len(w.new_emails())
            print(n)
            if os.environ.get("GITHUB_OUTPUT"):
                with open(os.environ["GITHUB_OUTPUT"], "a") as f:
                    f.write("mail=%d\n" % n)
            return 0
        return 1 if w.run() else 0
    finally:
        srv.close()


if __name__ == "__main__":
    sys.exit(main())
