"""The publishing tools against a real FTP server (pyftpdlib), as they will talk to webleaders.

    pip install pyftpdlib pyopenssl          (pyopenssl only for the FTP-over-TLS tests)
    python -m unittest discover -s tests -p "test_*.py" -v

Three servers: plain FTP, plain FTP without MLSD (older servers), and FTP over TLS with TLS required on
every connection (as most hosts do). On each: every file operation, reconnecting after the connection
drops, and the deploy and the inbox from start to finish. Skipped where pyftpdlib is not installed.
"""
import datetime, json, os, shutil, sys, tempfile, threading, time, unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import deploy, inbox, serverfs
from test_inbox import make_mp3, DATA_FILES

try:
    from pyftpdlib.authorizers import DummyAuthorizer
    from pyftpdlib.handlers import FTPHandler
    from pyftpdlib.servers import ThreadedFTPServer
except ImportError:
    FTPHandler = None
try:
    from pyftpdlib.handlers import TLS_FTPHandler
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    import ipaddress
except ImportError:
    TLS_FTPHandler = None

USER, PASSWORD = "deploy", "a long test password"


def self_signed(folder):
    """A certificate for 127.0.0.1 (key and certificate in one file, as pyftpdlib wants)."""
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    name = x509.Name([x509.NameAttribute(x509.oid.NameOID.COMMON_NAME, "127.0.0.1")])
    now = datetime.datetime.now(datetime.timezone.utc)
    cert = (x509.CertificateBuilder().subject_name(name).issuer_name(name).public_key(key.public_key())
            .serial_number(x509.random_serial_number()).not_valid_before(now - datetime.timedelta(days=1))
            .not_valid_after(now + datetime.timedelta(days=2))
            .add_extension(x509.SubjectAlternativeName([x509.IPAddress(ipaddress.ip_address("127.0.0.1"))]), critical=False)
            .add_extension(x509.BasicConstraints(ca=True, path_length=None), critical=True)
            .sign(key, hashes.SHA256()))
    path = os.path.join(folder, "server.pem")
    with open(path, "wb") as f:
        f.write(key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.TraditionalOpenSSL,
                                  serialization.NoEncryption()))
        f.write(cert.public_bytes(serialization.Encoding.PEM))
    return path


class FtpBase:
    """The tests; each subclass runs them against one kind of server."""
    handler_kind = "plain"

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="cs-ftp-test-")
        self.home = os.path.join(self.tmp, "ftp")
        os.makedirs(os.path.join(self.home, "site"))
        os.makedirs(os.path.join(self.home, "private"))
        auth = DummyAuthorizer()
        auth.add_user(USER, PASSWORD, self.home, perm="elradfmwMT")
        env = {"FTP_TLS": "0"}
        if self.handler_kind == "tls":
            cert = self_signed(self.tmp)
            handler = type("H", (TLS_FTPHandler,), {"certfile": cert, "tls_control_required": True, "tls_data_required": True})
            env = {"FTP_TLS": "1", "FTP_TLS_CAFILE": cert}
        elif self.handler_kind == "no-mlsd":
            cmds = {k: v for k, v in FTPHandler.proto_cmds.items() if k not in ("MLSD", "MLST")}
            handler = type("H", (FTPHandler,), {"proto_cmds": cmds})
        else:
            handler = type("H", (FTPHandler,), {})
        handler.authorizer = auth
        handler.banner = "test"
        handler.permit_foreign_addresses = True
        self.server = ThreadedFTPServer(("127.0.0.1", 0), handler)
        self.port = self.server.socket.getsockname()[1]
        self.thread = threading.Thread(target=self.server.serve_forever, kwargs={"timeout": 0.5}, daemon=True)
        self.thread.start()
        self.env = dict(env, FTP_HOST="127.0.0.1", FTP_USER=USER, FTP_PASSWORD=PASSWORD, FTP_SITE_DIR="/site",
                        FTP_PRIVATE_DIR="/private", FTP_PORT=str(self.port))
        self.old_env = {k: os.environ.get(k) for k in self.env}
        os.environ.update(self.env)
        self.srv = serverfs.FtpServer("127.0.0.1", USER, PASSWORD, "/site", "/private",
                                      tls=self.handler_kind == "tls", port=self.port)

    def tearDown(self):
        self.srv.close()
        self.server.close_all()
        for k, v in self.old_env.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        shutil.rmtree(self.tmp, ignore_errors=True)

    def disk(self, *parts):
        return os.path.join(self.home, *parts)

    # -- every operation the tools use
    def test_files_and_folders(self):
        s = self.srv
        self.assertEqual(s.list("site", "nothing/here"), {})
        self.assertIsNone(s.read("site", "missing.txt"))
        self.assertIsNone(s.size("site", "missing.txt"))
        s.write("site", "a/b/c/hello.txt", "καλημέρα".encode())
        self.assertEqual(s.read("site", "a/b/c/hello.txt"), "καλημέρα".encode())
        self.assertEqual(s.size("site", "a/b/c/hello.txt"), len("καλημέρα".encode()))
        self.assertEqual(s.list("site", "a"), {"b": "dir"})
        self.assertEqual(s.list("site", "a/b/c"), {"hello.txt": len("καλημέρα".encode())})
        self.assertTrue(s.is_dir("site", "a/b"))
        self.assertFalse(s.is_dir("site", "a/b/c/hello.txt"))
        self.assertFalse(s.is_dir("site", "a/zzz"))
        self.assertIsNotNone(s.mtime("site", "a/b/c/hello.txt"))
        # replacing a file in place
        s.write("site", "a/b/c/hello.txt", b"second version")
        self.assertEqual(s.read("site", "a/b/c/hello.txt"), b"second version")
        self.assertFalse(any(n.endswith(".uploading") for n in s.list("site", "a/b/c")))
        # a big file both ways
        big = os.path.join(self.tmp, "big.bin")
        with open(big, "wb") as f:
            f.write(os.urandom(3 * 1024 * 1024 + 17))
        s.upload(big, "site", "mp3/x/big.bin")
        back = os.path.join(self.tmp, "back.bin")
        s.download("site", "mp3/x/big.bin", back)
        self.assertEqual(open(back, "rb").read(), open(big, "rb").read())
        # names with spaces, brackets and Greek letters, as mp3 names have
        s.write("site", "mp3/x/CS_2026_10_15_(1)_Δοκιμή με κενά.mp3", b"ok")
        self.assertIn("CS_2026_10_15_(1)_Δοκιμή με κενά.mp3", s.list("site", "mp3/x"))
        # moving: within a root, across roots, a whole folder
        s.rename("site", "a/b/c/hello.txt", "a/moved.txt")
        self.assertEqual(s.read("site", "a/moved.txt"), b"second version")
        s.move("site", "mp3/x", "private", "replaced/x-1")
        self.assertEqual(sorted(s.list("private", "replaced/x-1")), ["CS_2026_10_15_(1)_Δοκιμή με κενά.mp3", "big.bin"])
        self.assertEqual(s.list("site", "mp3/x"), {})
        with self.assertRaises(serverfs.ServerError):
            s.rename("site", "does/not/exist", "x")
        # removing a file and a folder tree
        s.remove("site", "a/moved.txt")
        self.assertIsNone(s.size("site", "a/moved.txt"))
        s.remove("private", "replaced")
        self.assertFalse(os.path.exists(self.disk("private", "replaced")))
        s.remove("site", "never/was")               # no error for something that is not there

    def test_reconnects_when_the_connection_drops(self):
        self.srv.write("site", "x.txt", b"1")
        self.srv.ftp.sock.close()                   # the server or the network hung up
        self.assertEqual(self.srv.read("site", "x.txt"), b"1")
        self.srv.ftp.sock.close()
        self.srv.write("site", "y.txt", b"2")
        self.assertEqual(self.srv.list("site", ""), {"x.txt": 1, "y.txt": 1})

    # -- the tools from start to finish
    def test_deploy_over_ftp(self):
        with open(self.disk("site", "index.html"), "w") as f:
            f.write("the old site")
        up, rm = deploy.deploy(self.srv, root=ROOT, admin_path="upload-place", log=lambda *a: None)
        self.assertGreater(len(up), 500)
        with open(os.path.join(ROOT, "index.html"), "rb") as f:
            self.assertEqual(open(self.disk("site", "index.html"), "rb").read(), f.read())
        self.assertEqual(open(self.disk("private", "old-site", "index.html")).read(), "the old site")
        self.assertTrue(os.path.isfile(self.disk("site", "upload-place", "index.php")))
        up, rm = deploy.deploy(self.srv, root=ROOT, admin_path="upload-place", log=lambda *a: None)
        self.assertEqual((up, rm), ([], []))

    def test_inbox_over_ftp(self):
        repo = os.path.join(self.tmp, "repo")
        for f in DATA_FILES:
            os.makedirs(os.path.dirname(os.path.join(repo, f)), exist_ok=True)
            shutil.copyfile(os.path.join(ROOT, f), os.path.join(repo, f))
        req = self.disk("private", "inbox", "20261015-120000-0000ftp1")
        os.makedirs(req)
        files = []
        for i, fr in enumerate((850, 860), 1):
            make_mp3(os.path.join(req, "part-%d.mp3" % i), fr)
            files.append({"name": "part-%d.mp3" % i, "bytes": os.path.getsize(os.path.join(req, "part-%d.mp3" % i))})
        with open(os.path.join(req, "request.json"), "w", encoding="utf-8") as f:
            json.dump({"type": "broadcast", "date": "2026-10-15", "title": "Δοκιμή μέσω FTP", "tags": ["bible"], "files": files},
                      f, ensure_ascii=False)
        box = inbox.Inbox(self.srv, repo, push=False, build=False, keep_local=False, log=lambda *a: None)
        self.assertEqual(box.run(), 0)
        result = json.load(open(self.disk("private", "results", "20261015-120000-0000ftp1.json"), encoding="utf-8"))
        self.assertEqual(result["status"], "published", result["message"])
        self.assertEqual(sorted(os.listdir(self.disk("site", "mp3", "broadcasts", "Season_20", "2026_10_15"))),
                         ["2026_10_15_(1)_Dokimi_meso_ftp.mp3", "2026_10_15_(2)_Dokimi_meso_ftp.mp3", "2026_10_15_full.mp3"])
        self.assertTrue(os.path.isdir(self.disk("private", "done", "20261015-120000-0000ftp1")))
        self.assertEqual(os.listdir(self.disk("private", "processing")), [])


@unittest.skipUnless(FTPHandler, "pyftpdlib is not installed")
class PlainFtpTest(FtpBase, unittest.TestCase):
    handler_kind = "plain"


@unittest.skipUnless(FTPHandler, "pyftpdlib is not installed")
class NoMlsdFtpTest(FtpBase, unittest.TestCase):
    handler_kind = "no-mlsd"


@unittest.skipUnless(FTPHandler and TLS_FTPHandler, "pyftpdlib with pyopenssl is not installed")
class TlsFtpTest(FtpBase, unittest.TestCase):
    handler_kind = "tls"


if __name__ == "__main__":
    unittest.main()
