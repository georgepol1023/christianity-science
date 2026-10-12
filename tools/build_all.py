"""Run every page tool in the right order:

    python tools/build_all.py

0. related.py   «Σχετικά» links between broadcasts, articles, topics and questions
0. site_search.py  the site-wide search (index, top-bar button and script on every page)
1. build_en.py  English pages from the Greek ones (fails if a translation is missing)
2. seo.py       canonical / language / sharing tags, sitemap.xml, robots.txt
3. podcast.py   podcast.xml, the podcast feed Spotify reads (all broadcasts, newest first)
4. stamp.py     version stamps (?v=…) on CSS and JS links
"""
import os, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
for tool in ("related.py", "site_search.py", "build_en.py", "seo.py", "podcast.py", "stamp.py"):
    print("==", tool)
    r = subprocess.run([sys.executable, os.path.join(HERE, tool)])
    if r.returncode:
        sys.exit(r.returncode)
