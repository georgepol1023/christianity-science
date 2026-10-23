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
    """Copy the site's data files into the folder `dest`, without any broadcast of TEST_DATE."""
    for rel in files:
        path = os.path.join(dest, rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(os.path.join(ROOT, rel), encoding="utf-8") as f:
            text = f.read()
        if rel == "js/broadcasts.js":
            text = re.sub(r'(?m)^\s*ep\("%s",.*\n' % TEST_DATE, "", text)
        elif rel == "js/broadcasts-en.js":
            text = re.sub(r'(?m)^\s*"%s": .*\n' % TEST_DATE, "", text)
        elif rel == "data/podcast-audio.json":            # written as tools/inbox.py writes it
            folder = "/%s/" % TEST_DATE.replace("-", "_")
            audio = {k: v for k, v in json.loads(text).items() if folder not in k}
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
