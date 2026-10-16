"""Randomised tests of the code that edits the site's data (js/broadcasts.js, js/broadcasts-en.js).

    python -m unittest discover -s tests -p "test_*.py" -v

A broken character in js/broadcasts.js stops the whole archive from loading, so the editing is tried here with
random dates (across season boundaries, new seasons, the oldest of a season), awkward titles (quotes, backslashes,
«», emoji, every Greek accent), replacements and corrections; after each change the file is loaded by node, as the
site loads it, and checked: it loads, each season is newest first, every title reads back exactly, nothing else moved.
The random seed is printed on failure, so a failing case can be repeated.
"""
import datetime, os, random, re, shutil, sys, tempfile, unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))
import inbox

AWKWARD = ['Τίτλος με "εισαγωγικά"', "Ο Κύριος's \\ backslash", "«Εξ ενός αίματος» – Μέρος 2ο", "Ϊ ΐ ΰ ϋ ά έ ή ί ό ύ ώ",
           "Emoji 🎙️ και σύμβολα & % $ #", "Ερώτηση;", "Τέλος με τελεία.", "  κενά   πολλά  ", "Τίτλος: υπότιτλος – Μέρος 10ο",
           "x" * 190, "Ναι/Όχι (1/2) [σημ.] {α}"]


def seasons_of(site):
    return {s["n"]: [e["date"] for e in s["episodes"]] for s in site["seasons"]}


class EditingStressTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="cs-stress-")
        for f in ("js/broadcasts.js", "js/broadcasts-en.js", "js/tags.js"):
            os.makedirs(os.path.dirname(os.path.join(self.tmp, f)), exist_ok=True)
            shutil.copyfile(os.path.join(ROOT, f), os.path.join(self.tmp, f))
        self.seed = random.randrange(1 << 30)
        self.rnd = random.Random(self.seed)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def add(self, date, title, parts, tags, link=None):
        site = inbox.load_site(self.tmp)
        season, span, new = inbox.season_for(date, site)
        line = inbox.ep_line(date, title, inbox.slugify(title), parts, tags, link=link)
        js = inbox.read_text(self.tmp, "js/broadcasts.js")
        js = inbox.put_broadcast(js, date, line, season, span, new and not any(s["n"] == season for s in site["seasons"]))
        inbox.write_text(self.tmp, "js/broadcasts.js", js)
        en = inbox.read_text(self.tmp, "js/broadcasts-en.js")
        inbox.write_text(self.tmp, "js/broadcasts-en.js", inbox.put_en_title(en, date, "EN " + title))
        return season

    def check(self, expected, before):
        site = inbox.load_site(self.tmp)                       # fails if the file no longer loads
        msg = "seed %d" % self.seed
        for n, dates in seasons_of(site).items():
            self.assertEqual(dates, sorted(dates, reverse=True), "season %d not newest first (%s)" % (n, msg))
        for s in site["seasons"]:
            first, last = inbox.season_window(s["span"])
            for e in s["episodes"]:
                d = datetime.date.fromisoformat(e["date"])
                self.assertTrue(first <= d <= last, "%s in season %d (%s) %s" % (e["date"], s["n"], s["span"], msg))
        for date, (title, parts, tags) in expected.items():
            e = site["by_date"].get(date)
            self.assertIsNotNone(e, "%s missing (%s)" % (date, msg))
            self.assertEqual((e["title"], len(e["parts"]), e["tags"]), (title, parts, tags), msg)
            self.assertEqual(site["en"][date], "EN " + title, msg)
        for date, e in before.items():                           # what was there before is untouched
            if date not in expected:
                got = site["by_date"][date]
                self.assertEqual((got["title"], got["slug"], got["tags"], got["link"], got["parts"]),
                                 (e["title"], e["slug"], e["tags"], e["link"], e["parts"]), "%s changed (%s)" % (date, msg))

    def test_many_random_broadcasts(self):
        before = inbox.load_site(self.tmp)["by_date"]
        expected = {}
        topics = inbox.load_site(self.tmp)["tags"]
        start = datetime.date(2026, 8, 1)
        # dates from August 2026 to mid 2029 (inside season 20, at its edges, and in seasons that do not exist yet),
        # in date order as broadcasts arrive; within that, an older date of the current season now and then
        days = sorted(self.rnd.sample(range(0, 1050), 40))
        dates = []
        for k in days:
            dates.append((start + datetime.timedelta(days=k)).isoformat())
            if self.rnd.random() < 0.3 and len(dates) > 2:
                dates.insert(len(dates) - 1, dates.pop())      # swap the last two: not strictly in order
        for i, date in enumerate(dates):
            if datetime.date.fromisoformat(date).year > 2026 and inbox.season_for(date, inbox.load_site(self.tmp))[2] \
                    and any(x > date for x in expected):
                continue                                         # would open a season out of order (see below)
            if date in before or date in expected:
                continue
            title = re.sub(r"\s+", " ", self.rnd.choice(AWKWARD)).strip() + " %d" % i
            parts = self.rnd.choice([1, 2, 3, 4, 5])
            tags = self.rnd.sample(topics, self.rnd.choice([0, 1, 2, 3]))
            self.add(date, title, parts, tags)
            expected[date] = (title, parts, tags)
            if i % 5 == 4:
                self.check(expected, before)
        self.check(expected, before)
        self.assertGreaterEqual(len(inbox.load_site(self.tmp)["seasons"]), 22, "new seasons were made")

    def test_season_boundaries(self):
        site = inbox.load_site(self.tmp)
        self.assertEqual(inbox.season_for("2026-07-31", site)[0], 19)
        self.assertEqual(inbox.season_for("2026-08-01", site)[0], 20)
        self.assertEqual(inbox.season_for("2027-07-31", site)[:3], (20, "2026 – 2027", False))
        self.assertEqual(inbox.season_for("2027-08-01", site)[:3], (21, "2027 – 2028", True))
        self.assertEqual(inbox.season_for("2018-03-01", site)[0], 11)  # the half season "2018" (after a break)
        self.assertEqual(inbox.season_for("2008-02-14", site)[0], 1)   # the first half season "2008"
        self.assertEqual(inbox.season_for("2018-09-13", site)[0], 12)
        # a season missing in between (2028–2029 made before 2027–2028): refused, as season numbers follow each other
        self.add("2028-10-05", "Νέος κύκλος", 1, [])
        with self.assertRaises(inbox.Reject):
            inbox.season_for("2028-02-10", inbox.load_site(self.tmp))
        for gap in ("2007-10-01", "2017-10-05"):                    # before the programme; the 2017–2018 break
            with self.assertRaises(inbox.Reject):
                inbox.season_for(gap, site)

    def test_replacing_keeps_the_link_and_the_neighbours(self):
        before = inbox.load_site(self.tmp)["by_date"]
        date = "2009-01-15"                                         # has a link: material/2009_01_15.htm
        old = before[date]
        line = inbox.ep_line(date, "Νέος τίτλος", "Neos", 2, ["creation"], link=old["link"])
        js = inbox.put_broadcast(inbox.read_text(self.tmp, "js/broadcasts.js"), date, line, 2, "2008 – 2009", False)
        inbox.write_text(self.tmp, "js/broadcasts.js", js)
        after = inbox.load_site(self.tmp)["by_date"]
        self.assertEqual((after[date]["title"], after[date]["link"], len(after[date]["parts"])), ("Νέος τίτλος", old["link"], 2))
        self.assertEqual(len(after), len(before))
        for d, e in before.items():
            if d != date:
                self.assertEqual(after[d]["title"], e["title"])

    def test_the_last_broadcast_of_the_oldest_season(self):
        # the very end of the list: no comma may be left dangling or missing
        before = inbox.load_site(self.tmp)["by_date"]
        oldest = min(before)
        d = (datetime.date.fromisoformat(oldest) - datetime.timedelta(days=1)).isoformat()
        line = inbox.ep_line(d, "Πριν από όλα", "Prin", 1, [])
        js = inbox.put_broadcast(inbox.read_text(self.tmp, "js/broadcasts.js"), d, line, 1, "2008", False)
        inbox.write_text(self.tmp, "js/broadcasts.js", js)
        self.assertEqual(min(inbox.load_site(self.tmp)["by_date"]), d)

    def test_odd_input_never_crashes_the_title_tools(self):
        """A crash would leave a broadcast stuck in retries: random text (Greek, Latin, symbols, empty, long) must
        always give an answer."""
        import greeklish, mailwatch, titles
        site = inbox.load_site(ROOT)
        topics = titles.Topics(site, inbox.topic_names(ROOT))
        letters = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZαβγδεζηθικλμνξοπρστυφχψωάέήίόύώϊΐΑΒΓΔΩ0123456789 _-.()[]«»'–:;!?/&%#@\t\n🎙️"
        for i in range(400):
            s = "".join(self.rnd.choice(letters) for _ in range(self.rnd.randrange(0, 80)))
            t, sure = greeklish.title(s + self.rnd.choice([".mp3", ".MP3", "", ".wav"]))
            self.assertIsInstance(t, str)
            self.assertIsInstance(titles.sentence_case(titles.house_style(s), site), str)
            self.assertIsInstance(topics.suggest(s, s)[0], list)
            d, txt = mailwatch.find_date(s, datetime.date(2026, 10, 16))
            mailwatch.clean_title(s, txt)
            mailwatch.name_stem([s + ".mp3", s + "2.mp3"])
            self.assertTrue(inbox.slugify(s))

    def test_text_checks(self):
        for bad in ("<script>", "a\x00b", "x" * 201, "a > b"):
            with self.assertRaises(inbox.Reject):
                inbox.clean_text(bad, "ο τίτλος")
        self.assertEqual(inbox.clean_text("  πολλά   κενά\n", "ο τίτλος"), "πολλά κενά")
        with self.assertRaises(inbox.Reject):
            inbox.clean_tags(["bible", "bible"], {"bible"})


if __name__ == "__main__":
    unittest.main()
