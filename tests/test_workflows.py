"""The GitHub workflows give every tool the settings it reads, in the step that runs it.

    python -m unittest discover -s tests -p "test_*.py" -v

A setting missing in a step fails silently in production (the tool sees "not set up" and does less), so this
reads which environment variables each tool uses and checks them against each workflow step that runs the tool.
"""
import glob, os, re, unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOOLS = os.path.join(ROOT, "tools")
# only for tests, or with good defaults: not needed from the workflows
OPTIONAL = {"FTP_TLS_CAFILE", "WETRANSFER_BASE", "DEEPL_BASE", "GITHUB_OUTPUT", "CS_PRIVATE_DIR", "CS_SHOW_ERRORS",
            "FTP_PORT", "MAIL_IMAP_PORT", "MAIL_IMAP_SSL", "MAIL_IMAP_FOLDER", "PHP", "FTP_TLS", "MAIL_IMAP_HOST",
            "CS_REPLACE_ROOT"}


def reads(script, seen=None):
    """Environment variables a tool reads, also through the tools it imports."""
    seen = seen if seen is not None else set()
    if script in seen or not os.path.exists(os.path.join(TOOLS, script)):
        return set()
    seen.add(script)
    src = open(os.path.join(TOOLS, script), encoding="utf-8").read()
    out = {a or b for a, b in re.findall(r'os\.environ(?:\.get)?\(\s*"([A-Z_]+)"|os\.environ\["([A-Z_]+)"\]', src)}
    for mods in re.findall(r"^import ([\w, ]+)$", src, re.M):
        for m in mods.split(","):
            out |= reads(m.strip() + ".py", seen)
    return out


def steps(path):
    """[(name, run commands, the env it gets)] of a workflow (simple YAML reading, enough for these files)."""
    text = open(path, encoding="utf-8").read()
    secrets = lambda block: set(re.findall(r"^\s+([A-Z_]+): \$\{\{ (?:secrets|vars)\.[A-Z_]+(?: \|\| (?:secrets|vars)\.[A-Z_]+)* \}\}", block, re.M))
    top = re.search(r"^env:\n((?:  .*\n)+)", text, re.M)
    job_env = secrets(top.group(1)) if top else set()
    out = []
    for block in re.split(r"\n      - ", text)[1:]:
        name = re.match(r"(?:name: )?(.*)", block).group(1)
        run = re.search(r"run: (\|\n(?:          .*\n?)+|.*)", block)
        if run:
            out.append((name, run.group(1), job_env | secrets(block)))
    return out


class WorkflowSettingsTest(unittest.TestCase):
    def test_every_tool_gets_what_it_reads(self):
        problems = []
        for wf in sorted(glob.glob(os.path.join(ROOT, ".github", "workflows", "*.yml"))):
            for name, run, env in steps(wf):
                for script in re.findall(r"tools/(\w+\.py)", run):
                    if script in ("build_all.py", "update_column.py", "podcast.py"):
                        continue                                  # need no settings
                    missing = sorted(reads(script) - env - OPTIONAL)
                    if missing:
                        problems.append("%s, step «%s», %s: %s" % (os.path.basename(wf), name, script, ", ".join(missing)))
        self.assertEqual(problems, [])

    def test_the_setup_stores_what_the_workflows_ask_for(self):
        setup = open(os.path.join(TOOLS, "setup_server.py"), encoding="utf-8").read()
        stored = set(re.findall(r'"([A-Z][A-Z0-9_]{3,})"', setup))
        asked = set()
        for wf in glob.glob(os.path.join(ROOT, ".github", "workflows", "*.yml")):
            asked |= set(re.findall(r"\bsecrets\.([A-Z_]+)", open(wf, encoding="utf-8").read()))
        self.assertEqual(sorted(asked - stored), [])


if __name__ == "__main__":
    unittest.main()
