"""What several test files share: the site's data files as they were before the tests' broadcast, short generated
recordings, a stand-in FTP server, and removing a test folder. Not a test file itself (unittest only collects test_*.py).
"""
import json, os, re, shutil, stat, subprocess, sys, tempfile, threading

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))

DATA_FILES = ["js/broadcasts.js", "js/broadcasts-en.js", "js/tags.js", "data/podcast-audio.json"]

# The day of the made-up broadcast the tests publish. The real site has a broadcast that day too (published after the
# tests were written), so copy_site_data() leaves it out: the copy is the site as it was just before that day.
TEST_DATE = "2026-10-15"

_mp3_cache = {}


def copy_site_data(dest, files=DATA_FILES):
    """Copy the site's data files into `dest` as the site was just before TEST_DATE: every broadcast dated on or
    after TEST_DATE is left out, so a test's made-up broadcast of that day is reliably the newest (and real
    broadcasts added later never break the tests). Dates compare as text (ISO YYYY-MM-DD / YYYY_MM_DD)."""
    under = TEST_DATE.replace("-", "_")
    for rel in files:
        path = os.path.join(dest, rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(os.path.join(ROOT, rel), encoding="utf-8") as f:
            text = f.read()
        if rel == "js/broadcasts.js":
            text = re.sub(r'(?m)^\s*ep\("(\d{4}-\d\d-\d\d)",.*\n', lambda m: "" if m.group(1) >= TEST_DATE else m.group(0), text)
        elif rel == "js/broadcasts-en.js":
            text = re.sub(r'(?m)^\s*"(\d{4}-\d\d-\d\d)": .*\n', lambda m: "" if m.group(1) >= TEST_DATE else m.group(0), text)
        elif rel == "data/podcast-audio.json":            # keys are mp3 paths with a .../YYYY_MM_DD/... segment
            def before_test_date(key):
                m = re.search(r"/(\d{4}_\d\d_\d\d)/", key)
                return not m or m.group(1) < under
            audio = {k: v for k, v in json.loads(text).items() if before_test_date(k)}
            text = json.dumps(dict(sorted(audio.items(), reverse=True)), ensure_ascii=False, indent=0) + "\n"
        with open(path, "w", encoding="utf-8", newline="\n") as f:
            f.write(text)


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


def wipe(path):
    """Remove a test folder, git's read-only files too (Windows), so no test leaves anything behind."""
    def again(func, p, _):
        os.chmod(p, stat.S_IWRITE)
        func(p)
    shutil.rmtree(path, onerror=again)


def start_ftp(handler):
    """A pyftpdlib server on a free local port, in its own thread. Returns (server, port, thread); stop it with
    server.close_all() and thread.join()."""
    from pyftpdlib.servers import ThreadedFTPServer
    server = ThreadedFTPServer(("127.0.0.1", 0), handler)
    # pyftpdlib's threaded server shares one stop signal between all its servers: give this one its own,
    # or stopping the previous test's server can stop this one half-way through a test
    server._exit = threading.Event()
    server._lock = threading.Lock()
    thread = threading.Thread(target=server.serve_forever, kwargs={"timeout": 0.5}, daemon=True)
    thread.start()
    return server, server.socket.getsockname()[1], thread
