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

## Setting it up: one command

You need the [GitHub CLI](https://cli.github.com/), signed in once with `gh auth login`, and your
DirectAdmin user name and password.

1. **Back up the old site** first. In DirectAdmin go to *System Info & Files → Create/Restore Backups*,
   make a full backup and download it.
2. **Run the setup** from this folder, on the publishing branch:
   ```
   python tools/setup_server.py
   ```
   It asks for your DirectAdmin login (used once, not stored), then your name, email and a password for
   the upload page, whether to send result emails, and whether to fetch the recordings emailed to
   science@christianity.gr. For that it needs that mailbox's password and who may send recordings. It
   then:
   - makes an FTP account just for publishing (`publish@…`), and a mailbox for the emails (`ekpompes@…`);
   - finds the site's folder and makes the private folder `cs-admin` next to it;
   - makes the upload page's settings (with a code for your phone's authenticator app);
   - sets all of GitHub's secrets;
   - puts the new site into a **test folder**, `…/new-site-test/`, while the live site stays as it is;
   - checks the science@ login straight away, read-only, and reports how many recent emails carry recordings;
   - checks over the internet that the pages load and the upload page works, and sends you a test email.

   At the end it prints the trial address and the **device link** for the upload page, plus the
   passwords it made. Keep them in a password manager.
3. **Look at the trial** in a browser, including the upload page (open the device link first). The mp3s
   won't play there, because they are one level up. Sending a broadcast is refused in the trial, on
   purpose.
4. **Merge the branch** into `main` on GitHub. Then:
   ```
   git checkout main
   git pull
   python tools/setup_server.py --go-live
   ```
   It points publishing at the real site, switches the podcast feed to the site's own address and pushes.
   GitHub then deploys the new site. The first deploy keeps every old-site file it replaces in
   `cs-admin/old-site/`, and leaves `mp3/`, `files/` and old pages alone.
5. **Spotify** (it needs your login): in Spotify for Creators, change the show's RSS address to
   `https://www.christianity-science.gr/podcast.xml`. Keep Render running for a few weeks, then turn it off.

To let someone else use the upload page later: `python tools/setup_server.py --add-person`.
Running `python tools/setup_server.py` again is safe:
- it keeps the existing users;
- if the site is already live, it renews the settings without touching the site.

If a step fails, the setup stops and says what to do. Running it again picks up from there.

### By hand, if the setup cannot be used

1. In DirectAdmin, create:
   - an FTP account with **Domain** access;
   - the folder `cs-admin` next to `public_html`.
2. Make the page's settings with `python tools/admin_user.py new --out config.php` and upload the file as
   `cs-admin/config.php`.
3. In GitHub, add these secrets (*Settings → Secrets and variables → Actions*):

| Secret | Example |
|---|---|
| `FTP_HOST`, `FTP_USER`, `FTP_PASSWORD` | the FTP account |
| `FTP_SITE_DIR` | `/public_html` (or `/public_html/new-site-test` for a trial) |
| `FTP_PRIVATE_DIR` | `/cs-admin` |
| `ADMIN_PATH` | a folder name only you know, e.g. `diaxeirisi-x7k2m9q4ab` |
| `FTP_TLS` | `0` only if the server has no FTP over TLS |
| `ANTHROPIC_API_KEY` | optional: suggested English titles and topics |
| `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `MAIL_FROM`, `MAIL_TO` | optional: result emails |

4. On switch day:
   - set `podcastSite` in `js/broadcasts.js` to `https://www.christianity-science.gr/`, and `podcastAudio` to `""`;
   - run `python tools/build_all.py` and push;
   - change the Spotify RSS address;
   - set the repository variable `LIVE_URL`.

## Recordings by email

Every hour, the publishing robot reads `science@christianity.gr` (`tools/mailwatch.py`).

- **Read-only.** The mailbox is opened in read-only mode, so the server itself refuses any change: nothing
  is marked as read, moved or deleted.
- **Trusted senders only.** It looks only at emails from the trusted senders, and skips any that the mail
  server marks as forged.
- **Recordings.** It downloads WeTransfer transfers (or attached recordings), converts other audio formats
  to mp3, and orders the parts by file name.
- **Title and date.** The title and the date come from the email: the subject, the transfer's title, or
  "15/10/2026", "15 Οκτωβρίου" or "της 15ης". Failing that, the date is the broadcast day just before the
  email (every second Thursday). When both are clear, the broadcast is **published automatically**,
  through all the usual checks: never twice, real recordings, and so on.
- **When unsure, it waits.** If the title or the date is unclear, the recordings wait in the upload page's
  **«Από email»** tab, and the admin is emailed. There they can be played, completed and published with
  one click, or discarded.
- **Expired links.** A WeTransfer link that can't be downloaded is tried again every hour. After a day, the
  admin is emailed to upload the recordings by hand. WeTransfer's download interface isn't an official
  one, so if WeTransfer changes its site, this is what happens, and nothing else breaks.
- **Each email only once.** Every email is handled once, and the robot remembers which.

The settings are the secrets `MAIL_IMAP_USER`, `MAIL_IMAP_PASSWORD`, `MAIL_IMAP_HOST`
(`mail.christianity.gr`) and `MAIL_TRUSTED_SENDERS` (e.g. `radio@christianity.gr, @studio.gr`). The setup
sets them.

## Make it last

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
python -m unittest discover -s tests -p "test_*.py" -v     inbox, deploy, FTP, setup, upload page
node --test tests/admin_browser.test.js                     the upload page in Chrome
node --test tests/static.test.js                            the site's data and pages
```

The first two need ffmpeg and node. Some parts need more:
- the FTP tests: `pip install pyftpdlib pyopenssl`;
- the upload page: php;
- the browser test: Chrome and `npm install --prefix tests puppeteer-core`.

Tests whose needs are missing are skipped. GitHub runs all of them on every push that touches the tools
(*Publishing tests*). They cover:
- **never twice:** the same broadcast sent twice; one added by hand meanwhile; the same recordings under
  another date; the same size but different recordings;
- **replacing** a broadcast, and **undoing** an upload when publishing fails;
- **retries:** failed uploads and stale requests;
- **FTP:** a plain server, one without MLSD, and FTP over TLS, with dropped connections;
- **the setup** from start to finish, with scripted answers;
- **the upload page:** sign-in, device key, authenticator code and lockout; uploads checked byte for
  byte, with small-piece servers and dropped connections, in a real browser.
