"""Tests of tools/seo.py's sitemap dates: a page's <lastmod> is the day it last changed, also on GitHub, whose copy of
the site is made afresh (every file's own time is today) and has only the last commit.

    python -m unittest discover -s tests -p "test_*.py" -v
"""
import datetime, os, re, subprocess, tempfile, unittest

from helpers import wipe
import seo

TODAY = datetime.date.today().isoformat()


def git(cwd, *args, date=None):
    env = dict(os.environ, GIT_AUTHOR_DATE=date, GIT_COMMITTER_DATE=date) if date else None
    subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t", *args], cwd=cwd, check=True, capture_output=True, env=env)


class SitemapDatesTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="cs-seo-test-")
        self.repo = os.path.join(self.tmp, "repo")
        os.makedirs(self.repo)
        git(self.repo, "init", "-q", "-b", "main")
        for name in ("a.html", "b.html"):
            self.write(self.repo, name, "<p>%s</p>" % name)
        git(self.repo, "add", "-A")
        git(self.repo, "commit", "-q", "-m", "pages", date="2026-01-05T12:00:00Z")
        self.old_root = seo.ROOT

    def tearDown(self):
        seo.ROOT = self.old_root
        wipe(self.tmp)

    def write(self, folder, name, text):
        with open(os.path.join(folder, name), "w", encoding="utf-8") as f:
            f.write(text)

    def dates(self, root):
        seo.ROOT = root
        seo.sitemap(["a.html", "b.html"])
        with open(os.path.join(root, "sitemap.xml"), encoding="utf-8") as f:
            xml = f.read()
        return {loc[len(seo.SITE_URL):]: day for loc, day in re.findall(r"<loc>([^<]*)</loc>\s*<lastmod>([^<]*)<", xml)}

    def test_full_history_gives_each_page_its_last_commit(self):
        self.assertEqual(self.dates(self.repo), {"a.html": "2026-01-05", "b.html": "2026-01-05"})
        self.write(self.repo, "a.html", "<p>changed</p>")
        self.assertEqual(self.dates(self.repo), {"a.html": TODAY, "b.html": "2026-01-05"})

    def test_a_page_rebuilt_without_its_version_stamps_has_not_changed(self):
        self.write(self.repo, "a.html", '<link href="css/site.css?v=0123abcd">')
        git(self.repo, "commit", "-q", "-am", "stamped", date="2026-02-07T12:00:00Z")
        self.write(self.repo, "a.html", '<link href="css/site.css">')      # tools/stamp.py runs after seo.py
        self.assertEqual(self.dates(self.repo)["a.html"], "2026-02-07")

    def test_a_fresh_shallow_copy_keeps_the_dates_of_unchanged_pages(self):
        self.dates(self.repo)                                  # the sitemap as committed
        git(self.repo, "add", "-A")
        git(self.repo, "commit", "-q", "-m", "sitemap")
        copy = os.path.join(self.tmp, "copy")
        git(self.tmp, "clone", "-q", "--depth", "1", "file://" + self.repo.replace("\\", "/"), copy)
        self.assertEqual(self.dates(copy), {"a.html": "2026-01-05", "b.html": "2026-01-05"})
        self.write(copy, "b.html", "<p>changed</p>")
        self.assertEqual(self.dates(copy), {"a.html": "2026-01-05", "b.html": TODAY})


if __name__ == "__main__":
    unittest.main()
