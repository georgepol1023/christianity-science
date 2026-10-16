"""The web server's files, for the publishing tools (inbox.py, deploy.py, sync_mp3.py).

Two kinds of "server", with the same methods:
  FtpServer    the real one at webleaders, by FTP over TLS (settings from environment variables, below)
  LocalServer  a folder on this computer that stands in for it (tests, trial runs)

Paths are always written with "/" and are relative to one of two roots:
  site:     the public web folder (public_html): pages, mp3/, files/
  private:  a folder next to it that the web never serves (cs-admin): the inbox, the upload page's
            settings, the deploy record. Not reachable from a browser.

Environment variables for FtpServer (GitHub secrets in the workflows):
  FTP_HOST, FTP_USER, FTP_PASSWORD
  FTP_SITE_DIR      e.g. /domains/christianity-science.gr/public_html
  FTP_PRIVATE_DIR   e.g. /domains/christianity-science.gr/cs-admin
  FTP_TLS           1 (default) = FTP over TLS; 0 = plain FTP (only if the host offers nothing else)
  FTP_PORT          21 (default)
  FTP_TLS_CAFILE    only for tests: a certificate to trust besides the usual ones
Only the Python standard library is used, so these tools keep working for years without updates.
"""
import ftplib, io, os, posixpath, shutil, ssl, time


CA_BUNDLES = [                                   # where else trusted certificates are found, if Python has none
    "/etc/ssl/certs/ca-certificates.crt", "/etc/pki/tls/certs/ca-bundle.crt", "/etc/ssl/cert.pem",
    "C:/Program Files/Git/mingw64/etc/ssl/certs/ca-bundle.crt", "C:/Program Files/Git/usr/ssl/certs/ca-bundle.crt",
    "C:/msys64/usr/ssl/certs/ca-bundle.crt", "C:/msys64/mingw64/etc/ssl/certs/ca-bundle.crt",
]


def tls_context(cafile=None):
    """A TLS context that checks certificates. Some Python builds (e.g. MSYS2 on Windows) come without a list of
    trusted certificates and would trust no server: then the computer's other lists are used."""
    ctx = ssl.create_default_context(cafile=cafile)
    if not ctx.cert_store_stats().get("x509_ca"):
        try:
            import certifi                          # if installed
            ctx.load_verify_locations(certifi.where())
        except ImportError:
            for bundle in CA_BUNDLES:
                if os.path.isfile(bundle):
                    ctx.load_verify_locations(bundle)
                    break
    return ctx


def configured():
    return all(os.environ.get(k) for k in ("FTP_HOST", "FTP_USER", "FTP_PASSWORD", "FTP_SITE_DIR", "FTP_PRIVATE_DIR"))


def connect(local=None):
    """The server to work on: a local stand-in folder, or the real one by FTP."""
    if local:
        return LocalServer(os.path.join(local, "site"), os.path.join(local, "private"))
    if not configured():
        raise SystemExit("The server is not set up: FTP_HOST, FTP_USER, FTP_PASSWORD, FTP_SITE_DIR and "
                         "FTP_PRIVATE_DIR are needed (see docs/SETUP.md).")
    return FtpServer(os.environ["FTP_HOST"], os.environ["FTP_USER"], os.environ["FTP_PASSWORD"],
                     os.environ["FTP_SITE_DIR"], os.environ["FTP_PRIVATE_DIR"],
                     os.environ.get("FTP_TLS", "1") != "0", int(os.environ.get("FTP_PORT") or 21))


ANSWER = (ftplib.error_perm, ftplib.error_temp)    # the server said no (a file or folder problem, not the connection)


class ServerError(Exception):
    """The server could not do something (network, permissions, full disk). Worth trying again later."""


class LocalServer:
    def __init__(self, site, private):
        self.roots = {"site": site, "private": private}
        for r in self.roots.values():
            os.makedirs(r, exist_ok=True)

    def _p(self, root, path):
        return os.path.join(self.roots[root], *[p for p in path.split("/") if p])

    def list(self, root, path):
        """{name: "dir" | size in bytes} of a folder; {} if it does not exist."""
        d = self._p(root, path)
        if not os.path.isdir(d):
            return {}
        return {n: ("dir" if os.path.isdir(os.path.join(d, n)) else os.path.getsize(os.path.join(d, n)))
                for n in os.listdir(d)}

    def size(self, root, path):
        p = self._p(root, path)
        return os.path.getsize(p) if os.path.isfile(p) else None

    def is_dir(self, root, path):
        return os.path.isdir(self._p(root, path))

    def mtime(self, root, path):
        p = self._p(root, path)
        return os.path.getmtime(p) if os.path.exists(p) else None

    def mkdirs(self, root, path):
        os.makedirs(self._p(root, path), exist_ok=True)

    def read(self, root, path):
        p = self._p(root, path)
        if not os.path.isfile(p):
            return None
        with open(p, "rb") as f:
            return f.read()

    def write(self, root, path, data):
        self.mkdirs(root, posixpath.dirname(path))
        p = self._p(root, path)
        with open(p + ".uploading", "wb") as f:
            f.write(data)
        os.replace(p + ".uploading", p)

    def upload(self, local_file, root, path):
        self.mkdirs(root, posixpath.dirname(path))
        p = self._p(root, path)
        shutil.copyfile(local_file, p + ".uploading")
        os.replace(p + ".uploading", p)
        if os.path.getsize(p) != os.path.getsize(local_file):
            raise ServerError("%s: the copy on the server has the wrong size" % path)

    def download(self, root, path, local_file):
        shutil.copyfile(self._p(root, path), local_file)

    def rename(self, root, old, new):
        """Move a file or folder. Fails (ServerError) if `old` is gone, e.g. another run took it first."""
        self.mkdirs(root, posixpath.dirname(new))
        try:
            os.rename(self._p(root, old), self._p(root, new))
        except OSError as ex:
            raise ServerError("could not move %s to %s: %s" % (old, new, ex))

    def move(self, root_from, path_from, root_to, path_to):
        """Move a file or folder from one root to the other (e.g. old recordings into the private folder)."""
        self.mkdirs(root_to, posixpath.dirname(path_to))
        try:
            os.rename(self._p(root_from, path_from), self._p(root_to, path_to))
        except OSError as ex:
            raise ServerError("could not move %s: %s" % (path_from, ex))

    def remove(self, root, path):
        p = self._p(root, path)
        if os.path.isdir(p):
            shutil.rmtree(p)
        elif os.path.exists(p):
            os.remove(p)

    def close(self):
        pass


class _TLS(ftplib.FTP_TLS):
    """FTP over TLS that reuses the TLS session on data connections (many servers insist on it)."""
    def ntransfercmd(self, cmd, rest=None):
        conn, size = ftplib.FTP.ntransfercmd(self, cmd, rest)
        if self._prot_p:
            conn = self.context.wrap_socket(conn, server_hostname=self.host, session=self.sock.session)
        return conn, size


class FtpServer:
    def __init__(self, host, user, password, site_dir, private_dir, tls=True, port=21):
        self.args = (host, user, password, tls, port)
        self.roots = {"site": site_dir.rstrip("/") or "/", "private": private_dir.rstrip("/") or "/"}
        self.known_dirs = set()                         # folders known to exist (fewer questions to the server)
        self.ftp = None
        self._connect()

    def _connect(self):
        host, user, password, tls, port = self.args
        for attempt in range(3):
            try:
                if tls:
                    ftp = _TLS(timeout=120, context=tls_context(os.environ.get("FTP_TLS_CAFILE")))
                    ftp.connect(host, port)
                    try:
                        ftp.auth()
                    except ftplib.error_perm as ex:
                        raise ServerError("the server does not offer FTP over TLS (%s)" % ex)
                    ftp.login(user, password)
                    ftp.prot_p()
                else:
                    ftp = ftplib.FTP(timeout=120)
                    ftp.connect(host, port)
                    ftp.login(user, password)
                ftp.set_pasv(True)
                self.ftp = ftp
                return
            except ftplib.error_perm as ex:
                raise SystemExit("The server refused the FTP login: %s" % ex)
            except ssl.SSLCertVerificationError as ex:      # will not change by trying again
                raise ServerError("the server's certificate is not for %s (%s)" % (host, ex.verify_message))
            except (OSError, EOFError, ftplib.Error) as ex:  # EOFError: it hung up straight away
                if attempt == 2:
                    raise ServerError("could not connect to %s: %s" % (host, ex or type(ex).__name__))
                time.sleep(5 * (attempt + 1))

    def _p(self, root, path):
        return posixpath.join(self.roots[root], *[p for p in path.split("/") if p])

    def _do(self, fn):
        """Run fn() (which uses self.ftp); if the connection dropped, reconnect and run it once more."""
        try:
            return fn()
        except (OSError, EOFError, ftplib.error_temp) as ex:
            if isinstance(ex, ftplib.error_temp) and not str(ex).startswith("421"):
                raise                                  # an answer about the file, not a lost connection
            try:
                self.ftp.close()
            except Exception:
                pass
            self._connect()
            try:
                return fn()
            except (OSError, EOFError) as ex2:
                raise ServerError(str(ex2)) from ex

    def _dir_exists(self, d):
        """Whether d is a folder: by trying to enter it (works on every server, whatever its error codes)."""
        def go():
            try:
                self.ftp.cwd(d)
            except (ftplib.error_perm, ftplib.error_temp):
                return False
            self.ftp.cwd("/")
            return True
        return self._do(go)

    def list(self, root, path):
        d = self._p(root, path)
        if not getattr(self, "no_mlsd", False):
            try:
                entries = self._do(lambda: list(self.ftp.mlsd(d, ["type", "size"])))
            except (ftplib.error_perm, ftplib.error_temp) as ex:
                # servers answer "no such folder" and "MLSD not supported" with various codes: find out which
                if not self._dir_exists(d):
                    return {}
                self.no_mlsd = True
            else:
                out = {}
                for name, facts in entries:
                    if name in (".", "..") or facts.get("type") in ("cdir", "pdir"):
                        continue
                    out[name] = "dir" if facts.get("type") == "dir" else int(facts.get("size", 0))
                return out
        if not self._dir_exists(d):
            return {}
        return self._list_plain(d)

    def _list_plain(self, d):
        """For servers without MLSD: the names, then each one's size (a folder has none)."""
        try:
            names = [posixpath.basename(n.rstrip("/")) for n in self._do(lambda: self.ftp.nlst(d))]
        except (ftplib.error_perm, ftplib.error_temp):
            return {}                                  # some servers answer an empty folder with an error
        out = {}
        for n in names:
            if n in (".", "..", ""):
                continue
            p = posixpath.join(d, n)
            out[n] = "dir" if self._dir_exists(p) else (self.size_abs(p) or 0)
        return out

    def size_abs(self, p):
        try:
            return self._do(lambda: (self.ftp.voidcmd("TYPE I"), self.ftp.size(p))[1])
        except (ftplib.error_perm, ftplib.error_temp):
            return None

    def size(self, root, path):
        return self.size_abs(self._p(root, path))

    def is_dir(self, root, path):
        return self._dir_exists(self._p(root, path))

    def mtime(self, root, path):
        try:
            r = self._do(lambda: self.ftp.sendcmd("MDTM " + self._p(root, path)))
            t = time.strptime(r.split()[1][:14], "%Y%m%d%H%M%S")
            return time.mktime(t) - time.timezone
        except ANSWER + (IndexError, ValueError):
            return None

    def mkdirs(self, root, path):
        """Make the folder and any missing folder above it, the root included."""
        full = self._p(root, path)
        cur = "/" if full.startswith("/") else ""
        for part in [p for p in full.split("/") if p]:
            cur = posixpath.join(cur, part)
            if cur in self.known_dirs:
                continue
            try:
                self._do(lambda: self.ftp.mkd(cur))
            except ANSWER as ex:                        # often just "it exists" (each server says it differently)
                if not self._dir_exists(cur):
                    raise ServerError("could not make folder %s: %s" % (cur, ex))
            self.known_dirs.add(cur)

    def _forget(self, p):
        """A folder was moved or removed: forget it, and everything in it, as existing."""
        self.known_dirs = {d for d in self.known_dirs if d != p and not d.startswith(p.rstrip("/") + "/")}

    def read(self, root, path):
        buf = io.BytesIO()
        try:
            self._do(lambda: (buf.seek(0), buf.truncate(), self.ftp.retrbinary("RETR " + self._p(root, path), buf.write)))
        except ANSWER:
            return None
        return buf.getvalue()

    def _store(self, src, root, path, size):
        """Upload to a temporary name, check the size, then rename into place (never a half file)."""
        self.mkdirs(root, posixpath.dirname(path))
        p = self._p(root, path)
        tmp = p + ".uploading"
        for attempt in range(3):
            try:
                src.seek(0)
                self.ftp.storbinary("STOR " + tmp, src, blocksize=256 * 1024)
                break
            except (OSError, EOFError) as ex:
                if attempt == 2:
                    raise ServerError("upload of %s failed: %s" % (path, ex))
                try:
                    self.ftp.close()
                except Exception:
                    pass
                time.sleep(5 * (attempt + 1))
                self._connect()
            except ANSWER as ex:
                raise ServerError("upload of %s refused: %s" % (path, ex))
        got = self.size_abs(tmp)
        if got is not None and got != size:
            raise ServerError("%s: the server has %d bytes, should be %d" % (path, got, size))
        self._replace(tmp, p)

    def _replace(self, tmp, p):
        try:
            self._do(lambda: self.ftp.rename(tmp, p))
        except ANSWER:
            # some servers will not rename over an existing file: remove it, then rename
            try:
                self._do(lambda: self.ftp.delete(p))
            except ANSWER:
                pass
            try:
                self._do(lambda: self.ftp.rename(tmp, p))
            except ANSWER as ex:
                raise ServerError("could not put %s in place: %s" % (p, ex))

    def write(self, root, path, data):
        self._store(io.BytesIO(data), root, path, len(data))

    def upload(self, local_file, root, path):
        with open(local_file, "rb") as f:
            self._store(f, root, path, os.path.getsize(local_file))

    def download(self, root, path, local_file):
        tmp = local_file + ".part"
        def get():
            with open(tmp, "wb") as f:
                self.ftp.retrbinary("RETR " + self._p(root, path), f.write, 256 * 1024)
        try:
            self._do(get)
        except ANSWER as ex:
            raise ServerError("could not download %s: %s" % (path, ex))
        os.replace(tmp, local_file)

    def rename(self, root, old, new):
        self.mkdirs(root, posixpath.dirname(new))
        try:
            self._do(lambda: self.ftp.rename(self._p(root, old), self._p(root, new)))
            self._forget(self._p(root, old))
        except ANSWER as ex:
            raise ServerError("could not move %s to %s: %s" % (old, new, ex))

    def move(self, root_from, path_from, root_to, path_to):
        self.mkdirs(root_to, posixpath.dirname(path_to))
        try:
            self._do(lambda: self.ftp.rename(self._p(root_from, path_from), self._p(root_to, path_to)))
            self._forget(self._p(root_from, path_from))
        except ANSWER as ex:
            raise ServerError("could not move %s: %s" % (path_from, ex))

    def remove(self, root, path):
        p = self._p(root, path)
        try:
            self._do(lambda: self.ftp.delete(p))
            return
        except ANSWER:
            pass                                        # a folder, or nothing there
        if self._dir_exists(p):
            for name, kind in self.list(root, path).items():
                self.remove(root, posixpath.join(path, name))
            try:
                self._do(lambda: self.ftp.rmd(p))
            except ANSWER as ex:
                raise ServerError("could not remove folder %s: %s" % (path, ex))
            self._forget(p)
        elif self.size_abs(p) is not None:
            raise ServerError("could not remove %s" % path)

    def close(self):
        try:
            self.ftp.quit()
        except Exception:
            pass
