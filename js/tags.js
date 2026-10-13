/*
 * ΘΕΜΑΤΑ — the topics of the broadcasts (js/broadcasts.js, tags: "…") and of the newspaper column
 * (data/column-tags.json). One line per topic: key, Greek name, English name, colour (hue 0–360;
 * -1 = grey). The topics window, the coloured pills and the filters on the home page and the column
 * page are all made from this list.
 */
window.BROADCAST_TAGS = [
  { id: "bible",       name: "Αγία Γραφή",                 en: "The Bible",                 hue: 42 },
  { id: "prophecy",    name: "Προφητείες & εσχατολογία",   en: "Prophecy & eschatology",    hue: 12 },
  { id: "christ",      name: "Ιησούς Χριστός",             en: "Jesus Christ",              hue: 352 },
  { id: "apologetics", name: "Πίστη & αθεϊσμός",           en: "Faith & atheism",           hue: 268 },
  { id: "religions",   name: "Θρησκείες & αποκρυφισμός",   en: "Religions & the occult",    hue: 300 },
  { id: "creation",    name: "Δημιουργία & εξέλιξη",       en: "Creation & evolution",      hue: 128 },
  { id: "cosmos",      name: "Αστρονομία & διάστημα",      en: "Astronomy & space",         hue: 222 },
  { id: "body",        name: "Ανθρώπινος οργανισμός",      en: "The human body",            hue: 335 },
  { id: "soul",        name: "Πνευματική υπόσταση",        en: "The human spirit",          hue: 250 },
  { id: "bioethics",   name: "Βιοηθική",                   en: "Bioethics",                 hue: 188 },
  { id: "gender",      name: "Φύλο & σεξουαλικότητα",      en: "Gender & sexuality",        hue: 318 },
  { id: "family",      name: "Οικογένεια & νέοι",          en: "Family & young people",     hue: 24 },
  { id: "mind",        name: "Ψυχική υγεία",               en: "Mental health",             hue: 168 },
  { id: "health",      name: "Υγεία & εξαρτήσεις",         en: "Health & addiction",        hue: 145 },
  { id: "tech",        name: "Τεχνολογία & διαδίκτυο",     en: "Technology & the internet", hue: 205 },
  { id: "society",     name: "Κοινωνία",                   en: "Society",                   hue: 58 },
  { id: "environment", name: "Περιβάλλον & κλίμα",         en: "Environment & climate",     hue: 98 },
  { id: "science",     name: "Επιστημονική επικαιρότητα",  en: "Science news",              hue: 236 },
  { id: "feasts",      name: "Γιορτές & έθιμα",            en: "Feasts & traditions",       hue: 32 },
  { id: "life",        name: "Χριστιανική ζωή",            en: "Christian life",            hue: 48 },
  { id: "show",        name: "Η εκπομπή",                  en: "About the programme",       hue: -1 }
];
