"""Tests of tools/greeklish.py: Greek titles from Greeklish file names, spelled as the site spells them.

    python -m unittest discover -s tests -p "test_*.py" -v
"""
import os, sys, unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))
import greeklish


class GreeklishTest(unittest.TestCase):
    def test_the_real_file_name_of_15_october_2026(self):
        self.assertEqual(greeklish.title("1_EPISTIMI_PAGKOSMIA_MERA_PSYXIKIS_YGEIAS.mp3"),
                         ("Παγκόσμια μέρα ψυχικής υγείας", True))

    def test_spelling_follows_what_the_station_typed(self):
        # "ysi" is -υση and "eis" is -εις, even where the site uses another form of the word more often
        self.assertEqual(greeklish.title("Dieisdysi_anatolikon_thriskeion")[0], "Διείσδυση ανατολικών θρησκειών")
        self.assertEqual(greeklish.title("Neoteres_ekselikseis"), ("Νεότερες εξελίξεις", True))
        self.assertEqual(greeklish.title("Atheistika_Epixeirimata"), ("Αθεϊστικά επιχειρήματα", True))

    def test_names_keep_their_capitals(self):
        self.assertEqual(greeklish.title("Anastasi_tou_Xristou"), ("Ανάσταση του Χριστού", True))

    def test_part_numbers_and_the_programme_name_are_left_out(self):
        self.assertEqual(greeklish.tokens("3_EPISTIMI_PAGKOSMIA_MERA.mp3"), ["PAGKOSMIA", "MERA"])
        self.assertEqual(greeklish.tokens("CS_2026_10_15_(2)_Nous_se_kindyno.mp3"), ["Nous", "se", "kindyno"])

    def test_not_sure_means_a_person_completes_it(self):
        self.assertFalse(greeklish.title("Ti_simainoun_Xristougenna")[1])        # Τι or τη?
        self.assertFalse(greeklish.title("Pou_psaxneis_odigia")[1])              # Πού or που?
        self.assertFalse(greeklish.title("Kvantiki_Xbrzlq_theoria")[1])           # a word the site never printed
        self.assertEqual(greeklish.title("a.mp3")[1], False)

    def test_accuracy_does_not_fall(self):
        """On the site's own mp3 names (titles left out of the dictionary): this guards against a change for the worse."""
        spelled_right, words_sure, names_right = greeklish.evaluate()
        self.assertGreaterEqual(names_right, 0.97)
        self.assertGreaterEqual(spelled_right, 0.98)
        self.assertGreaterEqual(words_sure, 0.80)


class EmailWithoutTitleTest(unittest.TestCase):
    """The real email of 15 Oct 2026 (WeTransfer, no title): published with nobody typing anything."""

    def test_published_by_itself(self):
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        import test_mailwatch as t
        case = t.MailWatchTest("test_the_schedule")
        case.setUp()
        try:
            case.watch.words_root = ROOT                         # the site's pages teach the spelling
            files = [("%d_EPISTIMI_PAGKOSMIA_MERA_PSYXIKIS_YGEIAS.mp3" % i, t.mp3_bytes(1400 + i)) for i in (1, 2)]
            case.transfer("ab12", files)
            link = "https://wetransfer.com/downloads/ab12/%s" % case.wt.transfers["ab12"]["hash"]
            case.box.messages.append(case.wetransfer_email("radio@christianity.gr", link))
            case.watch.run()
            (ident, req), = case.requests("inbox")                # straight to publishing, not to «Από email»
            self.assertEqual((req["date"], req["title"]), ("2026-10-15", "Παγκόσμια μέρα ψυχικής υγείας"))
            self.assertEqual(req["from_email"]["title_from"], "the file names")
            self.assertEqual(case.told, [])                       # nobody needs to be asked
        finally:
            case.tearDown()


if __name__ == "__main__":
    unittest.main()
