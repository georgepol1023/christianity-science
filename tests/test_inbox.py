"""Tests of the publishing inbox (tools/inbox.py): new broadcasts, and that nothing is ever published twice.

    python -m unittest discover -s tests -p "test_*.py" -v

Each test works on a copy of the site's data files and a folder standing in for the server, with short
generated recordings (needs ffmpeg and node, like the tools themselves). Nothing real is touched.
"""
import json, os, re, shutil, subprocess, sys, tempfile, time, unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))
import inbox, serverfs

DATA_FILES = ["js/broadcasts.js", "js/broadcasts-en.js", "js/tags.js", "data/podcast-audio.json"]
_mp3_cache = {}


def make_mp3(path, freq, seconds=61):
    """A short mono mp3 (a tone); the same frequency gives the same file."""
    key = (freq, seconds)
    if key not in _mp3_cache:
        out = os.path.join(tempfile.gettempdir(), "cs-test-%d-%d.mp3" % key)
        if not os.path.exists(out):
            subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "sine=frequency=%d:duration=%d" % key,
                            "-ac", "1", "-b:a", "16k", out], check=True)
        _mp3_cache[key] = out
    shutil.copyfile(_mp3_cache[key], path)


class InboxTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="cs-inbox-test-")
        self.root = os.path.join(self.tmp, "repo")
        for f in DATA_FILES:
            os.makedirs(os.path.dirname(os.path.join(self.root, f)), exist_ok=True)
            shutil.copyfile(os.path.join(ROOT, f), os.path.join(self.root, f))
        self.srv = serverfs.connect(os.path.join(self.tmp, "server"))
        self.logs = []
        self.box = inbox.Inbox(self.srv, self.root, push=False, build=False, keep_local=False, log=self.logs.append)
        self.n = 0

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    # -- helpers
    def submit(self, req, freqs=(), files=None):
        """Put a complete request into the server's inbox, as the upload page does. Returns its id."""
        self.n += 1
        ident = time.strftime("%Y%m%d-%H%M%S-") + "t%03d" % self.n
        d = os.path.join(self.tmp, "server", "private", "inbox", ident)
        os.makedirs(d)
        listed = []
        for i, f in enumerate(files or [("tone", fr) for fr in freqs], 1):
            p = os.path.join(d, "part-%d.mp3" % i)
            if f[0] == "tone":
                make_mp3(p, f[1])
            else:
                with open(p, "wb") as fh:
                    fh.write(f[1])
            listed.append({"name": "part-%d.mp3" % i, "original": "recording-%d.mp3" % i, "bytes": os.path.getsize(p)})
        req = dict({"type": "broadcast", "user": "test"}, **req)
        if req["type"] == "broadcast":
            req.setdefault("files", listed)
        with open(os.path.join(d, "request.json"), "w", encoding="utf-8") as fh:
            json.dump(req, fh, ensure_ascii=False)
        return ident

    def result(self, ident):
        with open(os.path.join(self.tmp, "server", "private", "results", ident + ".json"), encoding="utf-8") as f:
            return json.load(f)

    def js(self):
        with open(os.path.join(self.root, "js", "broadcasts.js"), encoding="utf-8") as f:
            return f.read()

    def site_files(self, rel):
        d = os.path.join(self.tmp, "server", "site", rel)
        return sorted(os.listdir(d)) if os.path.isdir(d) else []

    def new(self, date="2026-10-15", title="Η Αγία Γραφή και η σύγχρονη αρχαιολογία", freqs=(300, 310, 320, 330), **kw):
        return self.submit(dict({"date": date, "title": title, "title_en": "The Bible and modern archaeology",
                                 "tags": ["bible", "science"]}, **kw), freqs=freqs)

    # -- a normal new broadcast
    def test_new_broadcast_is_published(self):
        ident = self.new()
        self.assertEqual(self.box.run(), 0)
        r = self.result(ident)
        self.assertEqual(r["status"], "published", r["message"])
        js = self.js()
        self.assertIn('season(20, "2026 – 2027", [\n      ep("2026-10-15", "Η Αγία Γραφή και η σύγχρονη αρχαιολογία", '
                      '"I_agia_grafi_kai", { tags: "bible science" }),\n      ep("2026-10-01"', js)
        self.assertEqual(self.site_files("mp3/broadcasts/Season_20/2026_10_15"),
                         ["2026_10_15_(%d)_I_agia_grafi_kai.mp3" % i for i in range(1, 5)] + ["2026_10_15_full.mp3"])
        en = open(os.path.join(self.root, "js", "broadcasts-en.js"), encoding="utf-8").read()
        self.assertIn('window.BROADCAST_TITLES_EN = {\n  "2026-10-15": "The Bible and modern archaeology",\n  "2026-10-01"', en)
        audio = json.load(open(os.path.join(self.root, "data", "podcast-audio.json"), encoding="utf-8"))
        a = audio["mp3/broadcasts/Season_20/2026_10_15/2026_10_15_(1)_I_agia_grafi_kai.mp3"]
        self.assertEqual(a["seconds"], 61)
        self.assertEqual(len(a["sha256"]), 64)
        self.assertIn("mp3/broadcasts/Season_20/2026_10_15/2026_10_15_full.mp3", audio)
        self.assertTrue(os.path.isdir(os.path.join(self.tmp, "server", "private", "done", ident)))
        self.assertEqual(inbox.load_site(self.root)["by_date"]["2026-10-15"]["parts"][0],
                         "mp3/broadcasts/Season_20/2026_10_15/2026_10_15_(1)_I_agia_grafi_kai.mp3")

    def test_single_part_has_no_joined_file(self):
        ident = self.new(freqs=(400,))
        self.box.run()
        self.assertEqual(self.result(ident)["status"], "published")
        self.assertIn("parts: 1", self.js())
        self.assertEqual(self.site_files("mp3/broadcasts/Season_20/2026_10_15"), ["2026_10_15_(1)_I_agia_grafi_kai.mp3"])

    def test_older_date_goes_in_date_order(self):
        before = len(inbox.load_site(self.root)["by_date"])
        self.new(date="2026-09-10", freqs=(410, 411))
        self.box.run()
        js = self.js()
        self.assertLess(js.index('ep("2026-09-17"'), js.index('ep("2026-09-10"'))
        self.assertLess(js.index('ep("2026-09-10"'), js.index('ep("2026-09-03"'))
        self.assertEqual(len(inbox.load_site(self.root)["by_date"]), before + 1)

    def test_oldest_date_of_a_season_goes_last(self):
        self.new(date="2026-08-20", freqs=(415,))
        self.box.run()
        js = self.js()
        self.assertIn('Nous_se_kindyno", { tags: "tech mind" }),\n      ep("2026-08-20"', js)
        self.assertEqual(inbox.load_site(self.root)["by_date"]["2026-08-20"]["season"], 20)

    def test_new_season_is_started(self):
        ident = self.new(date="2027-09-09", freqs=(420,))
        self.box.run()
        self.assertEqual(self.result(ident)["status"], "published")
        site = inbox.load_site(self.root)
        self.assertEqual((site["seasons"][0]["n"], site["seasons"][0]["span"]), (21, "2027 – 2028"))
        self.assertEqual(self.site_files("mp3/broadcasts/Season_21/2027_09_09"), ["2027_09_09_(1)_I_agia_grafi_kai.mp3"])

    def test_missing_english_and_topics_still_publish(self):
        os.environ.pop("ANTHROPIC_API_KEY", None)
        ident = self.submit({"date": "2026-10-15", "title": "Δοκιμή χωρίς θέματα"}, freqs=(430,))
        self.box.run()
        r = self.result(ident)
        self.assertEqual(r["status"], "published")
        self.assertIn("δεν έχει θέματα", r["message"])

    # -- never twice
    def test_existing_date_is_refused(self):
        ident = self.new(date="2026-10-01", freqs=(440,))
        self.box.run()
        r = self.result(ident)
        self.assertEqual(r["status"], "rejected")
        self.assertIn("υπάρχει ήδη", r["message"])
        self.assertEqual(self.js().count('ep("2026-10-01"'), 1)
        self.assertEqual(self.site_files("mp3/broadcasts/Season_20/2026_10_01"), [])
        self.assertTrue(os.path.isdir(os.path.join(self.tmp, "server", "private", "failed", ident)))

    def test_same_broadcast_sent_twice_is_published_once(self):
        first, second = self.new(), self.new()
        self.box.run()
        self.assertEqual(self.result(first)["status"], "published")
        self.assertEqual(self.result(second)["status"], "rejected")
        self.assertEqual(self.js().count('ep("2026-10-15"'), 1)

    def test_same_recordings_under_another_date_are_refused(self):
        self.new(date="2026-10-15", freqs=(500, 510))
        self.box.run()
        ident = self.new(date="2026-10-29", freqs=(510, 520))
        self.box.run()
        r = self.result(ident)
        self.assertEqual(r["status"], "rejected")
        self.assertIn("15 Οκτωβρίου 2026", r["message"])
        self.assertNotIn('ep("2026-10-29"', self.js())

    def test_recordings_matching_the_archive_by_size_and_length_are_refused(self):
        p = os.path.join(self.tmp, "x.mp3")
        make_mp3(p, 530)
        audio_path = os.path.join(self.root, "data", "podcast-audio.json")
        audio = json.load(open(audio_path, encoding="utf-8"))
        audio["mp3/broadcasts/Season_05/2012_01_12/CS_2012_01_12_(2)_X.mp3"] = {"bytes": os.path.getsize(p), "seconds": 61}
        json.dump(audio, open(audio_path, "w", encoding="utf-8"))
        ident = self.new(freqs=(530,))
        self.box.run()
        self.assertEqual(self.result(ident)["status"], "rejected")
        self.assertIn("12 Ιανουαρίου 2012", self.result(ident)["message"])

    def test_same_file_twice_in_one_request_is_refused(self):
        ident = self.new(freqs=(540, 540))
        self.box.run()
        self.assertEqual(self.result(ident)["status"], "rejected")

    def test_a_second_run_cannot_take_the_same_request(self):
        ident = self.new(freqs=(550,))
        other = inbox.Inbox(self.srv, self.root, push=False, build=False, keep_local=False, log=self.logs.append)
        # the first run claims it; the second finds it gone and leaves it alone
        self.srv.rename("private", "inbox/" + ident, "processing/" + ident)
        self.assertTrue(other.handle(ident))
        self.assertIn("%s: taken by another run" % ident, self.logs)
        self.assertNotIn('ep("2026-10-15"', self.js())

    def test_files_already_on_the_server_from_an_earlier_try_are_reused(self):
        ident = self.new(freqs=(560,))
        d = os.path.join(self.tmp, "server", "site", "mp3", "broadcasts", "Season_20", "2026_10_15")
        os.makedirs(d)
        make_mp3(os.path.join(d, "2026_10_15_(1)_I_agia_grafi_kai.mp3"), 560)
        self.box.run()
        self.assertEqual(self.result(ident)["status"], "published")
        self.assertTrue(any("already on the server" in l for l in self.logs))

    def test_a_folder_with_other_files_is_not_overwritten(self):
        ident = self.new(freqs=(570,))
        d = os.path.join(self.tmp, "server", "site", "mp3", "broadcasts", "Season_20", "2026_10_15")
        os.makedirs(d)
        make_mp3(os.path.join(d, "handmade.mp3"), 575)
        self.box.run()
        self.assertEqual(self.result(ident)["status"], "rejected")
        self.assertEqual(os.listdir(d), ["handmade.mp3"])
        self.assertNotIn('ep("2026-10-15"', self.js())

    def test_replace_swaps_the_recordings_and_keeps_the_old_ones(self):
        self.new(freqs=(600, 610))
        self.box.run()
        ident = self.new(freqs=(620, 630, 640), replace=True, title="Η Αγία Γραφή και η σύγχρονη αρχαιολογία")
        self.box.run()
        self.assertEqual(self.result(ident)["status"], "published", self.result(ident)["message"])
        js = self.js()
        self.assertEqual(js.count('ep("2026-10-15"'), 1)
        self.assertIn("parts: 3", js)
        self.assertEqual(len(self.site_files("mp3/broadcasts/Season_20/2026_10_15")), 4)
        kept = os.listdir(os.path.join(self.tmp, "server", "private", "replaced"))
        self.assertEqual(len(kept), 1)
        self.assertEqual(len(os.listdir(os.path.join(self.tmp, "server", "private", "replaced", kept[0]))), 3)
        audio = json.load(open(os.path.join(self.root, "data", "podcast-audio.json"), encoding="utf-8"))
        self.assertEqual(len([k for k in audio if "/2026_10_15/" in k]), 4)

    def test_replace_of_an_unchanged_recording_is_allowed(self):
        self.new(freqs=(650,))
        self.box.run()
        ident = self.new(freqs=(650,), replace=True, title="Νέος τίτλος της ίδιας εκπομπής")
        self.box.run()
        self.assertEqual(self.result(ident)["status"], "published", self.result(ident)["message"])

    # -- checks of what was sent
    def test_invalid_requests_are_refused_with_a_reason(self):
        cases = [({"date": "2026-02-30"}, (700,), "ημερομηνία"),
                 ({"date": "2026-10-15", "tags": ["nonsense"]}, (701,), "Άγνωστα θέματα"),
                 ({"date": "2026-10-15", "tags": ["bible", "christ", "cosmos", "body"]}, (702,), "έως 3"),
                 ({"date": "2026-10-15", "title": ""}, (703,), "τίτλος"),
                 ({"date": "2008-01-01"}, (704,), "κύκλο")]
        for fields, freqs, word in cases:
            req = dict({"title": "Τίτλος"}, **fields)
            ident = self.submit(req, freqs=freqs)
            self.box.run()
            r = self.result(ident)
            self.assertEqual(r["status"], "rejected", fields)
            self.assertIn(word, r["message"])

    def test_a_file_that_is_not_a_recording_is_refused(self):
        ident = self.submit({"date": "2026-10-15", "title": "Τίτλος"}, files=[("raw", b"<?php echo 'hello'; ?>" * 100)])
        self.box.run()
        self.assertEqual(self.result(ident)["status"], "rejected")
        self.assertIn("δεν είναι ηχογράφηση", self.result(ident)["message"])

    def test_a_too_short_recording_is_refused(self):
        p = os.path.join(self.tmp, "short.mp3")
        make_mp3(p, 710, seconds=5)
        ident = self.submit({"date": "2026-10-15", "title": "Τίτλος"}, files=[("raw", open(p, "rb").read())])
        self.box.run()
        self.assertIn("5 δευτερόλεπτα", self.result(ident)["message"])

    def test_an_incomplete_upload_is_refused(self):
        ident = self.new(freqs=(720,))
        path = os.path.join(self.tmp, "server", "private", "inbox", ident, "request.json")
        req = json.load(open(path, encoding="utf-8"))
        req["files"][0]["bytes"] += 1000
        json.dump(req, open(path, "w", encoding="utf-8"))
        self.box.run()
        self.assertIn("δεν ανέβηκε ολόκληρο", self.result(ident)["message"])

    # -- when something goes wrong on the way
    def test_a_temporary_failure_is_tried_again_then_set_aside(self):
        ident = self.new(freqs=(730,))
        real = self.srv.upload

        def broken(*a):
            raise serverfs.ServerError("connection lost")
        self.srv.upload = broken
        for attempt in range(1, inbox.MAX_TRIES):
            self.assertEqual(self.box.run(), 1)
            self.assertEqual(self.result(ident)["status"], "retrying")
            self.assertTrue(os.path.isdir(os.path.join(self.tmp, "server", "private", "inbox", ident)))
        self.box.run()
        self.assertEqual(self.result(ident)["status"], "error")
        self.assertTrue(os.path.isdir(os.path.join(self.tmp, "server", "private", "failed", ident)))
        self.srv.upload = real
        self.assertNotIn('ep("2026-10-15"', self.js())

    def test_a_request_left_half_done_goes_back_to_the_inbox(self):
        ident = self.new(freqs=(740,))
        self.srv.rename("private", "inbox/" + ident, "processing/" + ident)
        self.srv.write("private", "processing/%s/claimed.json" % ident, json.dumps({"time": time.time() - 4 * 3600}).encode())
        self.box.run()
        self.assertEqual(self.result(ident)["status"], "published")

    def test_a_recent_request_in_processing_is_left_alone(self):
        ident = self.new(freqs=(750,))
        self.srv.rename("private", "inbox/" + ident, "processing/" + ident)
        self.srv.write("private", "processing/%s/claimed.json" % ident, json.dumps({"time": time.time()}).encode())
        self.box.run()
        self.assertTrue(os.path.isdir(os.path.join(self.tmp, "server", "private", "processing", ident)))

    def test_old_done_requests_are_cleared(self):
        self.srv.mkdirs("private", "done/20200101-120000-old")
        self.srv.mkdirs("private", "done/%s-120000-new" % time.strftime("%Y%m%d"))
        self.box.run()
        self.assertEqual(list(self.srv.list("private", "done")), ["%s-120000-new" % time.strftime("%Y%m%d")])

    # -- the other kinds of request
    def test_home_page_settings(self):
        ident = self.submit({"type": "settings", "youtube": "https://www.youtube.com/watch?v=dQw4w9WgXcQ&t=10",
                             "next_broadcast": "2026-11-12T22:00"})
        self.box.run()
        self.assertEqual(self.result(ident)["status"], "published")
        js = self.js()
        self.assertIn('youtubeId: "dQw4w9WgXcQ"', js)
        self.assertIn('nextBroadcast: "2026-11-12T22:00:00+02:00"', js)

    def test_a_bad_video_link_is_refused(self):
        ident = self.submit({"type": "settings", "youtube": "https://example.com/video"})
        self.box.run()
        self.assertEqual(self.result(ident)["status"], "rejected")

    def test_correction_of_title_english_and_topics(self):
        ident = self.submit({"type": "correction", "date": "2026-09-17", "title": "Υπογεννητικότητα και οικογένεια",
                             "title_en": "Low birth rates and the family", "tags": ["family", "society"]})
        self.box.run()
        self.assertEqual(self.result(ident)["status"], "published", self.result(ident)["message"])
        e = inbox.load_site(self.root)["by_date"]["2026-09-17"]
        self.assertEqual((e["title"], e["tags"], e["slug"]), ("Υπογεννητικότητα και οικογένεια", ["family", "society"], "Ypogennitikotita"))
        self.assertEqual(inbox.load_site(self.root)["en"]["2026-09-17"], "Low birth rates and the family")

    def test_correction_keeps_cs_and_links(self):
        self.submit({"type": "correction", "date": "2008-04-24", "tags": ["christ", "bible"]})
        self.box.run()
        e = inbox.load_site(self.root)["by_date"]["2008-04-24"]
        self.assertEqual((e["cs"], e["link"], e["tags"]), (True, "material/2008_04_24.htm", ["christ", "bible"]))

    def test_correction_of_a_missing_broadcast_is_refused(self):
        ident = self.submit({"type": "correction", "date": "2026-10-16", "title": "Χ"})
        self.box.run()
        self.assertEqual(self.result(ident)["status"], "rejected")

    def test_unknown_request_is_refused(self):
        ident = self.submit({"type": "delete_everything"})
        self.box.run()
        self.assertEqual(self.result(ident)["status"], "rejected")

    # -- small parts
    def test_slugs(self):
        self.assertEqual(inbox.slugify("Απαντήσεις σε αθεϊστικά επιχειρήματα"), "Apantiseis_se_atheistika_epixeirimata")
        self.assertEqual(inbox.slugify("Ο νους μας σε κίνδυνο: περισσότερη πληροφορία"), "O_nous_mas_se")
        self.assertEqual(inbox.slugify("«Γονείς και Παιδιά» – Μέρος 6ο"), "Goneis_kai_paidia_meros")
        self.assertEqual(inbox.slugify("!!!"), "Ekpompi")

    def test_athens_offset(self):
        self.assertEqual(inbox.athens_offset("2026-10-24"), "+03:00")
        self.assertEqual(inbox.athens_offset("2026-10-25"), "+02:00")
        self.assertEqual(inbox.athens_offset("2027-03-28"), "+03:00")


class GitRaceTest(unittest.TestCase):
    """The checks against the newest version of the site, with a real git repository and two copies of it."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="cs-git-test-")
        self.remote = os.path.join(self.tmp, "remote.git")
        git = lambda *a, cwd=self.tmp: subprocess.run(["git", *a], cwd=cwd, check=True, capture_output=True)
        self.git = git
        git("init", "-q", "--bare", "-b", "main", self.remote)
        seed = os.path.join(self.tmp, "seed")
        git("clone", "-q", self.remote, seed)
        for f in DATA_FILES:
            os.makedirs(os.path.dirname(os.path.join(seed, f)), exist_ok=True)
            shutil.copyfile(os.path.join(ROOT, f), os.path.join(seed, f))
        for c in (seed,):
            git("-c", "user.name=t", "-c", "user.email=t@t", "checkout", "-q", "-b", "main", cwd=c)
            git("add", "-A", cwd=c)
            git("-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q", "-m", "seed", cwd=c)
            git("push", "-q", "origin", "main", cwd=c)
        self.a = os.path.join(self.tmp, "a")
        self.b = os.path.join(self.tmp, "b")
        for c in (self.a, self.b):
            git("clone", "-q", self.remote, c)
            git("config", "user.name", "t", cwd=c)
            git("config", "user.email", "t@t", cwd=c)
        self.srv = serverfs.connect(os.path.join(self.tmp, "server"))

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def request(self, date, freq):
        d = os.path.join(self.tmp, "server", "private", "inbox", "20261015-120000-%d" % freq)
        os.makedirs(d)
        make_mp3(os.path.join(d, "part-1.mp3"), freq)
        json.dump({"type": "broadcast", "date": date, "title": "Δοκιμή", "tags": ["bible"],
                   "files": [{"name": "part-1.mp3", "bytes": os.path.getsize(os.path.join(d, "part-1.mp3"))}]},
                  open(os.path.join(d, "request.json"), "w", encoding="utf-8"), ensure_ascii=False)
        return os.path.basename(d)

    def b_adds(self, date):
        """Someone else (by hand, or another run) adds a broadcast and pushes, while copy A is behind."""
        p = os.path.join(self.b, "js", "broadcasts.js")
        s = open(p, encoding="utf-8").read()
        s = s.replace('season(20, "2026 – 2027", [\n', 'season(20, "2026 – 2027", [\n      ep("%s", "Από άλλον", "Allos", { tags: "bible" }),\n' % date)
        open(p, "w", encoding="utf-8", newline="\n").write(s)
        self.git("commit", "-qam", "by hand", cwd=self.b)
        self.git("push", "-q", "origin", "main", cwd=self.b)

    def test_a_broadcast_added_by_hand_meanwhile_is_not_added_again(self):
        ident = self.request("2026-10-15", 800)
        self.b_adds("2026-10-15")
        box = inbox.Inbox(self.srv, self.a, push=True, build=False, keep_local=False, log=lambda *a: None)
        box.run()
        r = json.load(open(os.path.join(self.tmp, "server", "private", "results", ident + ".json"), encoding="utf-8"))
        self.assertEqual(r["status"], "rejected")
        self.assertIn("στο μεταξύ", r["message"])
        self.git("pull", "-q", cwd=self.b)
        self.assertEqual(open(os.path.join(self.b, "js", "broadcasts.js"), encoding="utf-8").read().count('ep("2026-10-15"'), 1)

    def test_other_changes_pushed_meanwhile_are_kept(self):
        ident = self.request("2026-10-15", 810)
        self.b_adds("2026-10-29")
        box = inbox.Inbox(self.srv, self.a, push=True, build=False, keep_local=False, log=lambda *a: None)
        self.assertEqual(box.run(), 0)
        self.git("pull", "-q", cwd=self.b)
        js = open(os.path.join(self.b, "js", "broadcasts.js"), encoding="utf-8").read()
        self.assertIn('ep("2026-10-29"', js)
        self.assertIn('ep("2026-10-15"', js)
        self.assertLess(js.index('ep("2026-10-29"'), js.index('ep("2026-10-15"'))

    def test_a_copy_with_unpushed_work_is_not_used(self):
        open(os.path.join(self.a, "note.txt"), "w").write("my own work")
        box = inbox.Inbox(self.srv, self.a, push=True, build=False, keep_local=False, log=lambda *a: None)
        with self.assertRaises(SystemExit):
            box.run()


if __name__ == "__main__":
    unittest.main()
