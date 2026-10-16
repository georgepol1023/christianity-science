"""Make the settings file of the upload page (config.php), or add a person to it. Run on your own computer.

    python tools/admin_user.py new                 a new config.php: device key + the first person
    python tools/admin_user.py add config.php      add a person to an existing config.php (prints the new file)

It asks for the person's user name, full name, email and password, and makes a secret for their
authenticator app (Google Authenticator, Microsoft Authenticator, 2FAS…): scan the printed otpauth://
address as a QR code, or type the secret in by hand. The password is stored only as a slow, salted hash.

The file goes to the PRIVATE folder on the server (cs-admin/config.php, next to public_html — never inside
public_html), by DirectAdmin's File Manager or FTP. Keep a copy in a password manager, not in git.
It is printed to the screen (and to a file if --out is given); nothing is sent anywhere.
"""
import argparse, base64, getpass, hashlib, re, secrets, sys, urllib.parse

ITERATIONS = 600_000


def password_hash(password):
    salt = secrets.token_bytes(16)
    h = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, ITERATIONS, 32)
    return "pbkdf2-sha256$%d$%s$%s" % (ITERATIONS, base64.b64encode(salt).decode(), base64.b64encode(h).decode())


def php(s):
    return "'" + str(s).replace("\\", "\\\\").replace("'", "\\'") + "'"


def render(cfg):
    lines = ["<?php", "// Settings of the upload page (made by tools/admin_user.py). Keep private; never put it in git.",
             "return [",
             "    'device_key' => %s," % php(cfg["device_key"]),
             "    'users' => ["]
    for uid, u in cfg["users"].items():
        lines.append("        %s => ['name' => %s, 'email' => %s, 'password' => %s, 'totp' => %s]," %
                     (php(uid), php(u["name"]), php(u["email"]), php(u["password"]), php(u["totp"])))
    lines.append("    ],")
    g = cfg.get("github") or {}
    lines.append("    // optional: lets the page start the publishing at once (a fine-grained token with Actions: write)")
    lines.append("    'github' => ['repo' => %s, 'workflow' => 'inbox.yml', 'ref' => 'main', 'token' => %s]," %
                 (php(g.get("repo", "georgepol1023/christianity-science")), php(g.get("token", ""))))
    lines.append("];")
    return "\n".join(lines) + "\n"


def parse(text):
    """Read back a config.php made by this tool."""
    s = lambda v: v.replace("\\'", "'").replace("\\\\", "\\")
    cfg = {"device_key": s(re.search(r"'device_key' => '((?:[^'\\]|\\.)*)'", text).group(1)), "users": {}}
    for m in re.finditer(r"'((?:[^'\\]|\\.)*)' => \['name' => '((?:[^'\\]|\\.)*)', 'email' => '((?:[^'\\]|\\.)*)', "
                         r"'password' => '((?:[^'\\]|\\.)*)', 'totp' => '((?:[^'\\]|\\.)*)'\]", text):
        cfg["users"][s(m.group(1))] = {"name": s(m.group(2)), "email": s(m.group(3)), "password": s(m.group(4)), "totp": s(m.group(5))}
    g = re.search(r"'github' => \['repo' => '([^']*)'.*'token' => '([^']*)'\]", text)
    if g:
        cfg["github"] = {"repo": g.group(1), "token": g.group(2)}
    return cfg


def ask_person(cfg):
    while True:
        uid = input("User name (letters, digits; used to sign in): ").strip().lower()
        if re.fullmatch(r"[a-z0-9._-]{3,32}", uid) and uid not in cfg["users"]:
            break
        print("  3–32 letters/digits, not already used.")
    name = input("Full name (shown on the page): ").strip() or uid
    email = input("Email (results are sent there; may be empty): ").strip()
    while True:
        pw = getpass.getpass("Password (at least 12 characters): ")
        if len(pw) >= 12 and pw == getpass.getpass("Password again: "):
            break
        print("  At least 12 characters, typed the same twice.")
    totp = base64.b32encode(secrets.token_bytes(20)).decode().rstrip("=")
    cfg["users"][uid] = {"name": name, "email": email, "password": password_hash(pw), "totp": totp}
    uri = "otpauth://totp/%s?secret=%s&issuer=%s" % (urllib.parse.quote("christianity-science.gr:" + uid), totp,
                                                    urllib.parse.quote("Χριστιανισμός & Επιστήμη"))
    print("\nAuthenticator app for %s: add an account with this secret (or make a QR code of the address):" % uid)
    print("  secret:  " + " ".join(totp[i:i + 4] for i in range(0, len(totp), 4)))
    print("  address: " + uri + "\n")


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("what", choices=["new", "add"])
    ap.add_argument("config", nargs="?")
    ap.add_argument("--out")
    a = ap.parse_args()
    if a.what == "new":
        cfg = {"device_key": secrets.token_urlsafe(32), "users": {}}
    else:
        if not a.config:
            sys.exit("Give the existing config.php.")
        cfg = parse(open(a.config, encoding="utf-8").read())
    ask_person(cfg)
    token = input("GitHub token for starting the publishing at once (optional; Enter to skip): ").strip()
    if token:
        cfg.setdefault("github", {})["token"] = token
    text = render(cfg)
    if a.out:
        with open(a.out, "w", encoding="utf-8", newline="\n") as f:
            f.write(text)
        print("Written to " + a.out)
    else:
        print(text)
    print("Device link (open it once on each computer/phone that may use the page):")
    print("  https://www.christianity-science.gr/<ADMIN_PATH>/?k=" + cfg["device_key"])


if __name__ == "__main__":
    main()
