"""Tests of tools/titles.py: English titles (the site's memory, DeepL, house style) and topics from the site itself.

    python -m unittest discover -s tests -p "test_*.py" -v

DeepL is a stand-in here (a small web server answering as DeepL does); the topics are measured on the real site.
"""
import http.server, json, os, shutil, sys, tempfile, threading, unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import inbox, serverfs, titles

SITE = inbox.load_site(ROOT)
NAMES = inbox.topic_names(ROOT)


class FakeDeepL(http.server.ThreadingHTTPServer):
    """Answers /v2/translate with self.answers[greek], or an error code if self.fail is set."""
    def __init__(self):
        self.answers, self.calls, self.fail, self.bad_keys = {}, [], None, set()
        super().__init__(("127.0.0.1", 0), self.Handler)
        threading.Thread(target=self.serve_forever, daemon=True).start()
        self.base = "http://127.0.0.1:%d" % self.server_address[1]

    class Handler(http.server.BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def do_POST(self):
            srv = self.server
            body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            srv.calls.append((self.path, self.headers.get("Authorization"), body))
            if srv.fail or self.headers.get("Authorization") in srv.bad_keys:
                self.send_response(srv.fail or 403)
                self.end_headers()
                return
            out = {"translations": [{"detected_source_language": "EL", "text": srv.answers.get(t, "?")} for t in body["text"]]}
            data = json.dumps(out).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)


class EnglishTest(unittest.TestCase):
    def setUp(self):
        self.deepl = FakeDeepL()
        os.environ["DEEPL_BASE"] = self.deepl.base
        os.environ["DEEPL_API_KEY"] = "test-key:fx"
        self.logs = []

    def tearDown(self):
        self.deepl.shutdown()
        for k in ("DEEPL_BASE", "DEEPL_API_KEY"):
            os.environ.pop(k, None)

    def test_a_new_part_of_a_series_reads_like_the_earlier_parts(self):
        en, how, note = titles.english("Η προέλευση των πάντων – Μέρος 3ο", SITE)
        self.assertEqual((en, how), ("The origin of all things – Part 3", "memory"))
        en, how, note = titles.english("Χριστιανισμός και Ισλάμ – Μέρος 4ο", SITE)
        self.assertEqual(en, "Christianity and Islam – Part 4")
        self.assertEqual(self.deepl.calls, [])                       # DeepL was not even asked

    def test_a_title_already_translated_is_reused(self):
        en, how, _ = titles.english("Απαντήσεις σε αθεϊστικά επιχειρήματα", SITE)
        self.assertEqual((en, how), ("Answers to atheist arguments", "memory"))

    def test_deepl_is_asked_for_british_english_with_the_context(self):
        self.deepl.answers["Παγκόσμια ημέρα ψυχικής υγείας"] = "World Mental Health Day."
        en, how, note = titles.english("Παγκόσμια ημέρα ψυχικής υγείας", SITE)
        self.assertEqual((en, how, note), ("World Mental Health Day", "deepl", ""))
        path, auth, body = self.deepl.calls[0]
        self.assertEqual((path, auth), ("/v2/translate", "DeepL-Auth-Key test-key:fx"))
        self.assertEqual((body["source_lang"], body["target_lang"], body["text"]), ("EL", "EN-GB", ["Παγκόσμια ημέρα ψυχικής υγείας"]))
        self.assertIn("Christian radio programme", body["context"])

    def test_a_quotation_is_marked_for_the_admin(self):
        self.deepl.answers["«Ο Κύριος ποιμαίνει με»: η ελπίδα"] = '"The Lord is my shepherd": hope'
        en, how, note = titles.english("«Ο Κύριος ποιμαίνει με»: η ελπίδα", SITE)
        self.assertEqual(en, "“The Lord is my shepherd”: hope")
        self.assertIn("King James", note)

    def test_a_quotation_the_site_already_uses_keeps_its_wording(self):
        g = "«Υψώνω τους οφθαλμούς μου προς τα όρη»: Η ελπίδα σήμερα"
        self.deepl.answers[g] = "‘I lift up my eyes to the hills’: Hope today"          # as DeepL really answered
        en, how, note = titles.english(g, SITE)
        self.assertEqual(en, "“I will lift up mine eyes unto the hills”: Hope today")
        self.assertEqual(note, "")

    def test_title_case_becomes_sentence_case_but_names_stay(self):
        cases = {"“From One Blood”: The Races Of Mankind": "“From one blood”: the races of mankind",   # as DeepL answered
                 "The Big Bang And The Creator": "The Big Bang and the Creator",
                 "World Mental Health Day": "World Mental Health Day",                              # a named day
                 "International Day Of Peace And The Gospel": "International Day of Peace and the Gospel",
                 "God’s Creation – Part 2": "God’s Creation – Part 2",
                 "DNA and the design of life": "DNA and the design of life",                      # already right
                 "The Resurrection of Jesus Christ and the historical evidence":
                     "The Resurrection of Jesus Christ and the historical evidence"}
        for given, wanted in cases.items():
            self.assertEqual(titles.house_style(titles.sentence_case(titles.house_style(given), SITE)), wanted, given)

    def test_when_deepl_fails_the_title_is_left_empty(self):
        for code, words in ((403, "key is wrong"), (456, "used up"), (500, "error 500")):
            self.deepl.fail = code
            self.logs.clear()
            en, how, note = titles.english("Νέος τίτλος για δοκιμή %d" % code, SITE, log=self.logs.append)
            self.assertEqual(en, "")
            self.assertIn(words, " ".join(self.logs))
        os.environ["DEEPL_API_KEY"] = ""
        self.assertEqual(titles.english("Άλλος τίτλος", SITE)[0], "")

    def test_house_style(self):
        cases = {"The origin of everything - part 3.": "The origin of everything – Part 3",
                 "The origin of everything, second part": "The origin of everything – Part 2",
                 "The origin of everything 3rd part": "The origin of everything – Part 3",
                 "The wonder of the body - Part 3: the immune system": "The wonder of the body – Part 3: the immune system",
                 '"Of one blood" - Part 1': "“Of one blood” – Part 1",
                 "‘I lift up my eyes’: hope": "“I lift up my eyes”: hope",
                 "The Lord’s Supper and God's word": "The Lord’s Supper and God's word",
                 "«Of one blood»": "“Of one blood”",
                 "world mental health day": "World mental health day"}
        for given, wanted in cases.items():
            self.assertEqual(titles.house_style(given), wanted, given)


class TopicsTest(unittest.TestCase):
    def test_typical_titles(self):
        t = titles.Topics(SITE, NAMES)
        self.assertEqual(t.suggest("Παγκόσμια ημέρα ψυχικής υγείας")[0][0], "mind")
        self.assertEqual(t.suggest("Τεχνητή νοημοσύνη και ανθρώπινη συνείδηση")[0][0], "tech")
        self.assertEqual(t.suggest("Η προέλευση των πάντων – Μέρος 3ο")[0][0], "creation")
        self.assertEqual(t.suggest("Ξξξ ψψψ ζζζ")[0], [])                      # nothing like it: left for a person

    def test_accuracy_does_not_fall(self):
        """Measured on the site with each broadcast's whole series hidden; this guards against a change making it worse."""
        right, guessed = titles.evaluate(SITE, NAMES)
        self.assertGreaterEqual(right, 0.80)
        self.assertGreaterEqual(guessed, 0.70)


class SetupTest(unittest.TestCase):
    def test_the_setup_tries_the_deepl_key(self):
        import setup_server
        from test_setup import Script
        deepl = FakeDeepL()
        deepl.bad_keys.add("DeepL-Auth-Key wrong:fx")
        deepl.answers["Παγκόσμια ημέρα ψυχικής υγείας"] = "World Mental Health Day"
        os.environ["DEEPL_BASE"] = deepl.base
        try:
            s = setup_server.Setup(con=Script([("DeepL API key", "wrong:fx"), ("Try another key", "y"),
                                               ("DeepL API key", "right:fx")]))
            self.assertEqual(s.deepl_key(), "right:fx")
            said = "\n".join(s.con.said)
            self.assertIn("key is wrong", said)
            self.assertIn("✓ DeepL works", said)
        finally:
            os.environ.pop("DEEPL_BASE", None)
            deepl.shutdown()


class InboxIntegrationTest(unittest.TestCase):
    """A broadcast sent without English title and topics gets both, and is published."""

    def test_filled_in_by_themselves(self):
        from test_inbox import make_mp3, DATA_FILES
        tmp = tempfile.mkdtemp()
        deepl = FakeDeepL()
        deepl.answers["Παγκόσμια ημέρα ψυχικής υγείας"] = "World Mental Health Day"
        os.environ.update(DEEPL_BASE=deepl.base, DEEPL_API_KEY="k:fx")
        try:
            root = os.path.join(tmp, "repo")
            for f in DATA_FILES:
                os.makedirs(os.path.dirname(os.path.join(root, f)), exist_ok=True)
                shutil.copyfile(os.path.join(ROOT, f), os.path.join(root, f))
            srv = serverfs.connect(os.path.join(tmp, "server"))
            d = os.path.join(tmp, "server", "private", "inbox", "20261016-120000-0000aaaa")
            os.makedirs(d)
            make_mp3(os.path.join(d, "part-1.mp3"), 1300)
            with open(os.path.join(d, "request.json"), "w", encoding="utf-8") as fh:
                json.dump({"type": "broadcast", "date": "2026-10-15", "title": "Παγκόσμια ημέρα ψυχικής υγείας",
                           "files": [{"name": "part-1.mp3", "bytes": os.path.getsize(os.path.join(d, "part-1.mp3"))}]},
                          fh, ensure_ascii=False)
            box = inbox.Inbox(srv, root, push=False, build=False, keep_local=False, log=lambda *a: None)
            self.assertEqual(box.run(), 0)
            site = inbox.load_site(root)
            self.assertEqual(site["en"]["2026-10-15"], "World Mental Health Day")
            self.assertEqual(site["by_date"]["2026-10-15"]["tags"][0], "mind")
            with open(os.path.join(tmp, "server", "private", "results", "20261016-120000-0000aaaa.json"), encoding="utf-8") as fh:
                r = json.load(fh)
            self.assertEqual(r["status"], "published")
            self.assertNotIn("Σημείωση", r["message"])                    # nothing left for a person
        finally:
            os.environ.pop("DEEPL_BASE", None)
            os.environ.pop("DEEPL_API_KEY", None)
            deepl.shutdown()
            shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
