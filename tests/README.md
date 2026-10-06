# Έλεγχοι (tests)

Δύο σειρές αυτόματων ελέγχων. Χρειάζεται [Node.js](https://nodejs.org) 18+ και Python (για το `tools/stamp.py`).

## 1. Στατικοί έλεγχοι (χωρίς browser), 31 έλεγχοι
Δεδομένα εκπομπών, συναρτήσεις του `js/app.js`, HTML όλων των σελίδων, σύνδεσμοι, CSS, `tools/stamp.py`.
```
node --test tests/static.test.js
```

## 2. Έλεγχοι στον browser, 26 έλεγχοι
Ανοίγουν κάθε σελίδα σε headless Chrome/Edge: αναζήτηση, player, αντίστροφη μέτρηση, θέμα, μενού, φίλτρα, κινητό.
```
npm install --prefix tests puppeteer-core     # μία φορά
node tests/server.js                           # σε ξεχωριστό παράθυρο (σερβίρει τον φάκελο στο :8081)
node --test tests/browser.test.js
```
Το `tests/server.js` υποστηρίζει HTTP Range, απαραίτητο για μεταπήδηση μέσα στα mp3
(ο `python -m http.server` δεν το υποστηρίζει, οπότε το «Συνέχεια ακρόασης» δεν δουλεύει με αυτόν).

## Γνωστό κενό
Η εκπομπή της 7/3/2013 («Νηστεία») δεν έχει mp3: λείπουν και από τον παλιό server.
Ο έλεγχος τα καταγράφει στο `KNOWN_MISSING_MP3`. Αν βρεθούν τα αρχεία, προσθέστε τα στο
`mp3/broadcasts/Season_06/2013_03_07/` και αφαιρέστε τα από τη λίστα.

Οι φάκελοι `tests/` και `tools/` δεν χρειάζεται να ανέβουν στον server.
