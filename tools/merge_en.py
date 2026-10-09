"""Pair translation/en_list.txt (index<TAB>English) with translation/_todo.json and add them to translation/en.json.

Checks that each translation keeps the same tags and link targets as its Greek original.
"""
import json, os, re, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
todo = json.load(open(os.path.join(ROOT, "translation", "_todo.json"), encoding="utf-8"))
lines = open(os.path.join(ROOT, "translation", "en_list.txt"), encoding="utf-8").read().splitlines()
path = os.path.join(ROOT, "translation", "en.json")
d = json.load(open(path, encoding="utf-8")) if os.path.exists(path) else {}

def skeleton(s):
    """Tags with their link/id/class attributes, in order: must match between Greek and English."""
    out = []
    for m in re.finditer(r"<(/?)(\w+)([^>]*)>", s):
        keep = " ".join(re.findall(r'\b(?:href|id|class|target|rel|style)="[^"]*"', m.group(3)))
        out.append(m.group(1) + m.group(2) + (" " + keep if keep else ""))
    return out

bad, added = [], 0
for line in lines:
    if not line.strip():
        continue
    i, _, en = line.partition("\t")  # "N" alone means an empty translation (e.g. a Greek ordinal suffix)
    i = i.strip()
    el = todo[int(i)]
    if skeleton(el) != skeleton(en):
        bad.append((i, skeleton(el), skeleton(en)))
        continue
    d[el] = en; added += 1
if bad:
    for b in bad[:10]:
        print("TAG MISMATCH in", b[0], "\n  el:", b[1], "\n  en:", b[2])
    sys.exit(1)
json.dump(d, open(path, "w", encoding="utf-8", newline="\n"), ensure_ascii=False, indent=1, sort_keys=True)
print("added %d translations; en.json now has %d" % (added, len(d)))
