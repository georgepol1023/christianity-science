# Setting up publishing on webleaders

This guide covers moving the site onto the webleaders server, and the upload page that lets an admin add
broadcasts without touching code. It's a one-off setup, done in this order. Nothing goes live until
step 4.

## How it fits together

```
 admin's browser ──► upload page (PHP, secret address) ──► private inbox on the server (cs-admin/inbox/)
                                                                     │
 GitHub Actions: inbox.yml ◄─────────── started at once by the page, and every 6 hours
   tools/inbox.py   check → mp3s into mp3/broadcasts/… → js/broadcasts.js → build → commit, push
   tools/deploy.py  changed pages → public_html (FTP)                 └► email + "Κατάσταση" tab
                                                                     │
 Spotify ◄──────────── podcast.xml on the site (Spotify checks it by itself every few hours)
```

On the server, next to each other:

```
domains/christianity-science.gr/
  public_html/          the site (pages from git; mp3/ and files/ only here)
    <ADMIN_PATH>/       the upload page (index.php …), at a secret address
  cs-admin/             PRIVATE, never served: config.php, inbox/, results/, deploy record, backups
```

The site stays plain files. If every automation stopped, the site would keep working exactly as it is.
See "When something goes wrong" below.

## 1. On webleaders (DirectAdmin, port 2222)

1. **Back up the old site.** In *System Info & Files → Create/Restore Backups*, make a full backup and
   download it. Keep it.
2. **Make the private folder.** In *File Manager*, next to `public_html` (not inside it), create
   `cs-admin`. The full path is usually `/domains/christianity-science.gr/cs-admin`.
3. **Make an FTP account for the robots.** In *FTP Management → Create FTP account*, create e.g.
   `deploy@christianity-science.gr` with a long random password and **Domain** access, so that it
   sees `public_html` and `cs-admin`. Note the paths it sees, e.g. `/domains/christianity-science.gr/public_html`.
   - Check that it accepts **FTP over TLS** (most DirectAdmin servers do). If it truly does not, set the
     secret `FTP_TLS` to `0` below.
4. **PHP**: in *PHP Version Selector* (or *Domain Setup*), use PHP 8.1 or newer. 7.4 also works.
5. **HTTPS**: under *SSL Certificates*, keep "Force SSL with https redirect" on.
6. **Email (optional)**: create e.g. `ekpompes@christianity-science.gr`, for sending the "published ✓"
   emails. Note its SMTP server, port (465) and password.

## 2. The upload page's settings file

On your own computer:

```
python tools/admin_user.py new --out config.php
```

It asks for the first admin's user name, name, email and a password of at least 12 characters. It
prints a **secret for an authenticator app** (Google Authenticator, Microsoft Authenticator, 2FAS). Add it
to the admin's phone. To add more people later, run `python tools/admin_user.py add config.php --out config.php`.

Upload `config.php` to **`cs-admin/config.php`** with the File Manager. Keep a copy in a password manager.
**Never put it in git.**

The tool also prints the **device link** (`…/<ADMIN_PATH>/?k=…`). Each computer or phone that will use the
page must open it once. Without it, the page answers "not found", like an address that doesn't exist.

Optional: so the page can start publishing straight away (otherwise it starts within 6 hours):
1. On GitHub, go to *Settings → Developer settings → Fine-grained tokens*.
2. Create a token for this repository only, with **Actions: Read and write** and nothing else.
3. Give that token when `admin_user.py` asks for it.

## 3. GitHub secrets

In the repository, open *Settings → Secrets and variables → Actions → New repository secret*:

| Secret | Example | Needed |
|---|---|---|
| `FTP_HOST` | `ftp.christianity-science.gr` (or the server's name) | yes |
| `FTP_USER` | `deploy@christianity-science.gr` | yes |
| `FTP_PASSWORD` | the FTP account's password | yes |
| `FTP_SITE_DIR` | `/domains/christianity-science.gr/public_html` | yes |
| `FTP_PRIVATE_DIR` | `/domains/christianity-science.gr/cs-admin` | yes |
| `ADMIN_PATH` | a folder name only you know, e.g. `kx7-ekpompes-2026` | for the upload page |
| `FTP_TLS` | `0` only if the server has no FTP over TLS | no |
| `ANTHROPIC_API_KEY` | for suggested English titles and topics | no |
| `SMTP_HOST` `SMTP_PORT` `SMTP_USER` `SMTP_PASSWORD` `MAIL_FROM` | the email account from step 1.6 | no |
| `MAIL_TO` | your own address: you get a copy of every result | no |

**Before the switch, try it in a test folder:**
1. Set `FTP_SITE_DIR` to `/domains/christianity-science.gr/public_html/new-site-test`.
2. Run *Actions → Deploy to the web server → Run workflow*.
3. Look at `https://www.christianity-science.gr/new-site-test/`.

The mp3s won't play there (they are one level up), but everything else can be checked, including the
upload page at `…/new-site-test/<ADMIN_PATH>/`.

## 4. Switch day

1. In `js/broadcasts.js`, set `podcastSite` to `"https://www.christianity-science.gr/"` and `podcastAudio`
   to `""`. Then run `python tools/build_all.py`, commit and push.
2. Set `FTP_SITE_DIR` back to `…/public_html` and run *Deploy to the web server*. The first deploy:
   - **sets aside every old-site file it replaces** in `cs-admin/old-site/`, so nothing is lost;
   - leaves alone `mp3/`, `files/` and old pages the new site doesn't have, so old links keep working.
3. **Spotify:** in Spotify for Creators, change the show's RSS address to
   `https://www.christianity-science.gr/podcast.xml`. Keep the Render site running for a few weeks, so
   anyone still reading the old feed address finds it, then turn Render off.
4. Set the repository **variable** `LIVE_URL` to `https://www.christianity-science.gr/`. The weekly check
   then watches the live site and emails you if anything breaks.
5. Upload a test broadcast through the page, check it, then delete it by hand (see below), or simply
   replace it with the real one.

## 5. Make it last

- **Make the repository private** (*Settings → General → Danger zone*). The upload page's code and
  everything else then stops being public. There's a second benefit: GitHub turns off scheduled jobs in
  *public* repositories after 60 days without commits, which would silently stop the column updates in
  a quiet summer.
- **Two people** should have the logins: GitHub, DirectAdmin, the domain registrar, and `config.php`'s
  copy. Keep them in a shared password manager.
- **Domain and hosting**: turn on auto-renew, with a payment card that won't expire unnoticed. Renewal
  emails should go to an address two people read.
- **Second copy of the audio**: now and then (e.g. monthly) run `python tools/sync_mp3.py`. It copies new
  broadcasts from the server into `mp3/` on this computer. Also keep DirectAdmin's scheduled backups on.
- **Alerts**: GitHub emails the repository's owner when a workflow fails. Make sure those emails arrive
  (*GitHub → Settings → Notifications → Actions*).

## When something goes wrong

| What | What happens | What to do |
|---|---|---|
| A broadcast is refused (date already there, wrong file…) | Nothing is published; the admin gets the reason by email and in «Κατάσταση» | Fix and send again |
| The server or network fails while publishing | Nothing half-done is published; the request goes back to the inbox and is tried again | Nothing. After 4 failed tries the owner is emailed |
| A deploy fails half-way | The next run (within 6 hours, or any push) finishes it | Nothing, or *Run workflow* on *Deploy* |
| The upload page itself breaks | Put the files in `cs-admin/inbox/<new folder>/` with File Manager (the format is in `tools/inbox.py`), or add the broadcast by hand as below | |
| GitHub Actions is unavailable | Run the same tools from a computer: `python tools/inbox.py` then `python tools/deploy.py`, with the `FTP_…` settings as environment variables | |
| Everything is unavailable | Put the mp3s in `public_html/mp3/broadcasts/Season_NN/YYYY_MM_DD/` by FTP, add one line to `js/broadcasts.js` (the comments at the top of that file explain it), run `python tools/build_all.py`, and upload the changed files | |

**Removing a broadcast** (rare, so there's no button for it):
1. Delete its line in `js/broadcasts.js` and in `js/broadcasts-en.js`.
2. Run `python tools/build_all.py`, commit and push.
3. Move its mp3 folder on the server into `cs-admin/replaced/`.

## The tests

```
python -m unittest discover -s tests -p "test_*.py" -v     inbox, deploy, upload page (needs ffmpeg, node; php for the page)
node --test tests/static.test.js                           the site's data and pages
```

They run on GitHub on every push that touches the tools (*Publishing tests*). They cover:
- the same broadcast sent twice;
- a broadcast added by hand while another is being published;
- the same recordings under another date;
- replacements;
- failed uploads and retries;
- the upload page's sign-in, device key, two-factor login and lockout.
