"""Tests of tools/deploy.py: only changed files go up, nothing of mp3/, files/ or the old site is lost.

    python -m unittest discover -s tests -p "test_*.py" -v
"""
import json, os, shutil, sys, tempfile, unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))
import deploy, serverfs


class DeployTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="cs-deploy-test-")
        self.srv = serverfs.connect(self.tmp)
        self.site = os.path.join(self.tmp, "site")
        self.logs = []
        # what the old site left on the server
        self.put("index.html", b"old home page")
        self.put("old_page.htm", b"an old page the new site does not have")
        self.put("mp3/broadcasts/Season_20/2026_10_01/x.mp3", b"audio")
        self.put("files/x.pdf", b"pdf")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def put(self, rel, data):
        p = os.path.join(self.site, *rel.split("/"))
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "wb") as f:
            f.write(data)

    def get(self, *parts):
        p = os.path.join(self.tmp, *parts)
        if not os.path.exists(p):
            return None
        with open(p, "rb") as f:
            return f.read()

    def manifest(self):
        return json.loads(self.get("private", deploy.MANIFEST))

    def run_deploy(self, **kw):
        return deploy.deploy(self.srv, root=ROOT, log=self.logs.append, **kw)

    def test_first_deploy(self):
        up, rm = self.run_deploy(admin_path="secret-place")
        with open(os.path.join(ROOT, "index.html"), "rb") as f:
            self.assertEqual(self.get("site", "index.html"), f.read())
        self.assertEqual(self.get("private", "old-site", "index.html"), b"old home page")
        self.assertEqual(self.get("site", "old_page.htm"), b"an old page the new site does not have")
        self.assertEqual(self.get("site", "mp3", "broadcasts", "Season_20", "2026_10_01", "x.mp3"), b"audio")
        self.assertEqual(self.get("site", "files", "x.pdf"), b"pdf")
        for not_site in (("tools", "deploy.py"), ("tests", "test_deploy.py"), ("README.md",), ("admin", "index.php"),
                         (".github",)):
            self.assertIsNone(self.get("site", *not_site), not_site)
        self.assertIsNotNone(self.get("site", "secret-place", "index.php"))
        self.assertIsNotNone(self.get("site", ".htaccess"))
        self.assertIn("podcast.xml", self.manifest())
        self.assertEqual(rm, [])
        # pages after the files they use; .htaccess last
        self.assertLess(up.index("css/site.css"), up.index("index.html"))
        self.assertEqual(up[-1], ".htaccess")

    def test_nothing_changed_nothing_uploaded(self):
        self.run_deploy()
        up, rm = self.run_deploy()
        self.assertEqual((up, rm), ([], []))

    def test_only_changed_files_go_up(self):
        self.run_deploy()
        m = self.manifest()
        m["css/site.css"] = "0" * 64
        self.srv.write("private", deploy.MANIFEST, json.dumps(m).encode())
        up, rm = self.run_deploy()
        self.assertEqual(up, ["css/site.css"])

    def test_files_the_site_no_longer_has_are_removed_but_nothing_else(self):
        self.run_deploy()
        self.put("gone.html", b"a page an earlier deploy put here")
        m = self.manifest()
        m["gone.html"] = "1" * 64
        self.srv.write("private", deploy.MANIFEST, json.dumps(m).encode())
        up, rm = self.run_deploy()
        self.assertEqual(rm, ["gone.html"])
        self.assertIsNone(self.get("site", "gone.html"))
        self.assertIsNotNone(self.get("site", "old_page.htm"))
        self.assertNotIn("gone.html", self.manifest())

    def test_a_deploy_that_would_empty_the_site_stops(self):
        self.run_deploy()
        m = self.manifest()
        for i in range(deploy.MAX_REMOVALS + 1):
            m["ghost/%d.html" % i] = "2" * 64
        self.srv.write("private", deploy.MANIFEST, json.dumps(m).encode())
        with self.assertRaises(SystemExit):
            self.run_deploy()
        up, rm = self.run_deploy(allow_removals=True)
        self.assertEqual(len(rm), deploy.MAX_REMOVALS + 1)

    def test_dry_run_changes_nothing(self):
        up, rm = self.run_deploy(dry_run=True)
        self.assertGreater(len(up), 100)
        self.assertEqual(self.get("site", "index.html"), b"old home page")
        self.assertIsNone(self.get("private", deploy.MANIFEST))

    def test_the_upload_page_needs_a_proper_secret_address(self):
        for bad in ("admin", "../x", "a/b", "with space"):
            with self.assertRaises(SystemExit):
                self.run_deploy(admin_path=bad)

    def test_moving_the_upload_page_removes_it_from_the_old_address(self):
        self.run_deploy(admin_path="first-place")
        up, rm = self.run_deploy(admin_path="second-place")
        self.assertIsNone(self.get("site", "first-place", "index.php"))
        self.assertIsNotNone(self.get("site", "second-place", "index.php"))


if __name__ == "__main__":
    unittest.main()
