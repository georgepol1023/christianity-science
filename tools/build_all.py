"""Run every page tool in the right order:

    python tools/build_all.py

1. build_en.py  English pages from the Greek ones (fails if a translation is missing)
2. seo.py       canonical / language / sharing tags, sitemap.xml, robots.txt
3. stamp.py     version stamps (?v=…) on CSS and JS links
"""
import os, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
for tool in ("build_en.py", "seo.py", "stamp.py"):
    print("==", tool)
    r = subprocess.run([sys.executable, os.path.join(HERE, tool)])
    if r.returncode:
        sys.exit(r.returncode)
