/*
 * Forgiving search shared by the broadcast archive (js/app.js) and the lists with a search box
 * (js/page.js: articles, newspaper column, questions): typos, word forms, Greeklish, partial matches.
 *
 *   SiteSearch.prepare(text)     → {norm, words} for one item (title, date …)
 *   SiteSearch.search(items, q)  → {list: [{ep: item, hits: [words]}], approx}
 *                                  items need .norm and .words (from prepare) and an .id to break ties
 */
(function () {
  "use strict";

  /* Greek-aware normalisation: no accents, lowercase, final sigma */
  function norm(s) { return String(s).normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase().replace(/ς/g, "σ"); }
  function words(s) { return norm(s).split(/[^0-9a-zα-ω]+/).filter(Boolean); }

  var STOP = {};
  ("και ο η το οι τα του της των τον την τη στο στη στην στον στα στις στους σε με για απο προς " +
   "κατα μετα ενα μια ενας ως οτι ποσ πωσ τι ειναι δεν μη αλλα ή αυτο αυτη μεροσ ο " +
   "the and of a an in on to for with is are what how why part")
    .split(" ").forEach(function (w) { STOP[norm(w)] = true; });

  // Greeklish → Greek, so "genesi" finds "Γένεση" ("th" → θ, "ps" → ψ …)
  var GL = [["th", "θ"], ["ch", "χ"], ["ps", "ψ"], ["ks", "ξ"], ["ou", "ου"], ["mp", "μπ"],
    ["a", "α"], ["b", "β"], ["v", "β"], ["g", "γ"], ["d", "δ"], ["e", "ε"], ["z", "ζ"], ["h", "η"], ["i", "ι"],
    ["k", "κ"], ["l", "λ"], ["m", "μ"], ["n", "ν"], ["x", "ξ"], ["o", "ο"], ["p", "π"], ["r", "ρ"], ["s", "σ"],
    ["t", "τ"], ["y", "υ"], ["u", "υ"], ["f", "φ"], ["w", "ω"], ["c", "κ"], ["j", "τζ"], ["q", "κ"]];
  function greeklish(t) {
    var out = "", i = 0;
    while (i < t.length) {
      var hit = null;
      for (var k = 0; k < GL.length && !hit; k++) if (t.substr(i, GL[k][0].length) === GL[k][0]) hit = GL[k];
      if (hit) { out += hit[1]; i += hit[0].length; } else { out += t[i]; i++; }
    }
    return out;
  }

  // edit distance with transpositions, giving up beyond `max`
  function editDist(a, b, max) {
    if (Math.abs(a.length - b.length) > max) return max + 1;
    var prev2 = null, prev = [], cur, i, j;
    for (j = 0; j <= b.length; j++) prev[j] = j;
    for (i = 1; i <= a.length; i++) {
      cur = [i]; var rowMin = i;
      for (j = 1; j <= b.length; j++) {
        var c = a[i - 1] === b[j - 1] ? 0 : 1;
        cur[j] = Math.min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + c);
        if (prev2 && i > 1 && j > 1 && a[i - 1] === b[j - 2] && a[i - 2] === b[j - 1]) cur[j] = Math.min(cur[j], prev2[j - 2] + 1);
        if (cur[j] < rowMin) rowMin = cur[j];
      }
      if (rowMin > max) return max + 1;
      prev2 = prev; prev = cur;
    }
    return prev[b.length];
  }

  function trigrams(w) { var s = " " + w + " ", out = {}; for (var i = 0; i < s.length - 2; i++) out[s.substr(i, 3)] = 1; return out; }
  function dice(a, b) {
    var n = 0, na = 0, nb = 0, k;
    for (k in a) { na++; if (b[k]) n++; }
    for (k in b) nb++;
    return na + nb ? 2 * n / (na + nb) : 0;
  }

  /* How well one query word matches an item: {s: score 0–10, hit: matched word}. */
  function matchWord(q, ep) {
    var best = { s: 0, hit: null };
    function take(s, hit) { if (s > best.s) best = { s: s, hit: hit }; }
    if (ep.norm.indexOf(q) !== -1) take(7, q);                     // anywhere in title/date
    var lim = q.length >= 6 ? 2 : 1, qt = q.length >= 3 ? trigrams(q) : null;
    ep.words.forEach(function (w) {
      if (w === q) return take(10, w);
      if (q.length >= 2 && w.indexOf(q) === 0) take(8, w);                    // start of a word
      if (w.length >= 4 && q.indexOf(w) === 0) take(7 * Math.min(1, w.length / q.length / 0.7), w);  // a short word only partly covers the query
      var cp = 0; while (cp < w.length && cp < q.length && w[cp] === q[cp]) cp++;
      if (cp >= 4 && cp >= 0.7 * Math.min(w.length, q.length)) take(6, w);    // other word form
      if (q.length >= 4 && w.length >= 3) { var d = editDist(w, q, lim); if (d <= lim) take(5 - d, w); }  // typo
      if (qt && w.length >= 3) { var t = dice(qt, trigrams(w)); if (t >= 0.35) take(4 * t, w); }        // looks similar
    });
    return best;
  }

  /* Score a whole query against an item; returns {score, hits[]}. */
  function scoreItem(ep, tokens, phrase) {
    var total = 0, strong = 0, hits = [];
    tokens.forEach(function (t) {
      var m = matchWord(t, ep);
      if (/^[a-z]{3,}$/.test(t)) { var g = matchWord(greeklish(t), ep); if (g.s > m.s) m = g; }
      total += m.s;
      if (m.s >= 4.5) strong++;
      if (m.hit && m.s >= 2) hits.push(m.hit);
    });
    if (tokens.length > 1 && strong === tokens.length) total += 4;            // every word matched
    if (phrase && phrase.indexOf(" ") > 0 && ep.norm.indexOf(phrase) !== -1) total += 6;  // exact phrase
    return { score: total, hits: hits };
  }

  /* Ranked results for a query; `approx` when nothing matched well. */
  function search(eps, q) {
    var all = words(q), tokens = all.filter(function (t) { return !STOP[t]; });
    if (!tokens.length) tokens = all;
    if (!tokens.length) return { list: eps.map(function (e) { return { ep: e, hits: [] }; }), approx: false };
    var phrase = norm(q).replace(/\s+/g, " ").trim();
    var scored = eps.map(function (e) { var r = scoreItem(e, tokens, phrase); return { ep: e, score: r.score, hits: r.hits }; })
      .filter(function (r) { return r.score > 0; })
      .sort(function (a, b) { return b.score - a.score || (a.ep.id < b.ep.id ? 1 : -1); });
    if (!scored.length) return { list: [], approx: false };
    var top = scored[0].score, good = 4.5 * Math.max(1, Math.ceil(tokens.length / 2));
    if (top >= good) {
      // keep everything reasonably close to the best match
      return { list: scored.filter(function (r) { return r.score >= Math.max(4, top * 0.35); }), approx: false };
    }
    return { list: scored.slice(0, 12), approx: true };                       // nothing good: closest ones
  }

  function prepare(text) { return { norm: norm(text), words: words(text) }; }

  window.SiteSearch = { norm: norm, words: words, stop: STOP, prepare: prepare, search: search };
})();
