<?php
/*
 * The upload page of christianity-science.gr: shared functions. Not reachable from the web (admin/.htaccess).
 *
 * The page only RECEIVES: it saves what the admin sends into the private inbox (outside the public web
 * folder) and nothing else. Publishing is done by tools/inbox.py, which checks everything again.
 * Plain PHP 7.4+ with built-in functions only, so it keeps working through PHP upgrades.
 *
 * Settings: <private>/config.php, made with  python tools/admin_user.py  (see docs/SETUP.md).
 * <private> is the folder next to public_html called cs-admin (or the CS_PRIVATE_DIR environment variable).
 */
declare(strict_types=1);

const CS_MAX_FILE = 400 * 1024 * 1024;      // one mp3 (a half-hour is ~35 MB)
const CS_MAX_PARTS = 8;
const CS_MAX_CHUNK = 8 * 1024 * 1024;       // uploads go in pieces, so the host's upload limits do not matter
const CS_IDLE = 4 * 3600;                   // signed out after 4 hours without use
const CS_FAILS = 5;                          // wrong sign-ins allowed per 15 minutes (per address and per user)

/** The private folder: CS_PRIVATE_DIR, or the first "cs-admin" with a config.php next to the site or above it. */
function cs_private(): string
{
    static $dir = null;
    if ($dir !== null) {
        return $dir;
    }
    $env = getenv('CS_PRIVATE_DIR');
    if ($env) {
        return $dir = rtrim($env, '/');
    }
    $up = dirname(cs_site());
    for ($i = 0; $i < 4; $i++) {               // the site may be in a test folder inside public_html
        if (is_file("$up/cs-admin/config.php")) {
            return $dir = "$up/cs-admin";
        }
        $up = dirname($up);
    }
    return $dir = dirname(cs_site()) . '/cs-admin';
}

/** The site's folder: the page lives in <site>/<secret address>/. */
function cs_site(): string
{
    return dirname(__DIR__);
}

function cs_base(): string
{
    return rtrim(dirname((string)$_SERVER['SCRIPT_NAME']), '/') . '/';
}

function cs_config(): array
{
    static $c = null;
    if ($c === null) {
        $f = cs_private() . '/config.php';
        $c = is_file($f) ? (require $f) : [];
        if (!is_array($c)) {
            $c = [];
        }
    }
    return $c;
}

function cs_not_found(): void
{
    http_response_code(404);
    header('Content-Type: text/html; charset=utf-8');
    $page = cs_site() . '/404.html';
    if (is_file($page)) {
        readfile($page);
    } else {
        echo '<!doctype html><title>404</title><h1>404</h1>';
    }
    exit;
}

/* ------------------------------------------------------------ invisible to the public
 * Without this device's key the page answers "not found", like an address that does not exist.
 * The key is given once per device through a private link: <page address>?k=<device_key>.
 */
function cs_gate(): void
{
    $key = (string)(cs_config()['device_key'] ?? '');
    if (strlen($key) < 24) {
        cs_not_found();                       // not set up yet: the page does not exist
    }
    $want = hash('sha256', 'cs-device|' . $key);
    $have = (string)($_COOKIE['cs_device'] ?? '');
    if ($have !== '' && hash_equals($want, $have)) {
        return;
    }
    $given = (string)($_GET['k'] ?? '');
    if ($given !== '' && hash_equals($key, $given)) {
        setcookie('cs_device', $want, ['expires' => time() + 400 * 86400, 'path' => cs_base(), 'secure' => true,
                                      'httponly' => true, 'samesite' => 'Lax']);
        header('Location: ' . cs_base(), true, 303);
        exit;
    }
    cs_not_found();
}

/* ------------------------------------------------------------ sessions and sign-in */
function cs_session(): void
{
    $dir = cs_private() . '/state/sessions';
    if (!is_dir($dir)) {
        @mkdir($dir, 0700, true);
    }
    if (is_dir($dir) && is_writable($dir)) {
        session_save_path($dir);
    }
    ini_set('session.use_strict_mode', '1');
    ini_set('session.gc_maxlifetime', (string)CS_IDLE);
    session_name('cs_session');
    session_set_cookie_params(['lifetime' => 0, 'path' => cs_base(), 'secure' => true, 'httponly' => true, 'samesite' => 'Lax']);
    session_start();
    if (!empty($_SESSION['user']) && time() - (int)($_SESSION['seen'] ?? 0) > CS_IDLE) {
        $_SESSION = [];
        session_regenerate_id(true);
    }
    $_SESSION['seen'] = time();
    if (empty($_SESSION['csrf'])) {
        $_SESSION['csrf'] = bin2hex(random_bytes(32));
    }
}

function cs_user(): ?array
{
    $name = (string)($_SESSION['user'] ?? '');
    $users = cs_config()['users'] ?? [];
    return ($name !== '' && isset($users[$name])) ? ['id' => $name] + $users[$name] : null;
}

/** Password check against "pbkdf2-sha256$<iterations>$<salt, base64>$<hash, base64>" (tools/admin_user.py). */
function cs_password_ok(string $stored, string $password): bool
{
    $p = explode('$', $stored);
    if (count($p) !== 4 || $p[0] !== 'pbkdf2-sha256' || (int)$p[1] < 100000) {
        return false;
    }
    $calc = hash_pbkdf2('sha256', $password, (string)base64_decode($p[2], true), (int)$p[1], 32, true);
    return hash_equals((string)base64_decode($p[3], true), $calc);
}

function cs_base32_decode(string $s): string
{
    $alphabet = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ234567';
    $s = strtoupper(preg_replace('/[\s=]/', '', $s));
    $bits = '';
    for ($i = 0; $i < strlen($s); $i++) {
        $v = strpos($alphabet, $s[$i]);
        if ($v === false) {
            return '';
        }
        $bits .= str_pad(decbin($v), 5, '0', STR_PAD_LEFT);
    }
    $out = '';
    for ($i = 0; $i + 8 <= strlen($bits); $i += 8) {
        $out .= chr(bindec(substr($bits, $i, 8)));
    }
    return $out;
}

/** The 6-digit code of an authenticator app (RFC 6238), allowing 30 seconds of clock difference. */
function cs_totp(string $secret, int $step): string
{
    $h = hash_hmac('sha1', pack('N2', 0, $step), cs_base32_decode($secret), true);
    $o = ord($h[19]) & 0xf;
    $v = ((ord($h[$o]) & 0x7f) << 24) | (ord($h[$o + 1]) << 16) | (ord($h[$o + 2]) << 8) | ord($h[$o + 3]);
    return sprintf('%06d', $v % 1000000);
}

function cs_totp_ok(string $secret, string $code, ?int $now = null): bool
{
    $code = preg_replace('/\s+/', '', $code);
    if (!preg_match('/^\d{6}$/', $code) || cs_base32_decode($secret) === '') {
        return false;
    }
    $step = intdiv($now ?? time(), 30);
    foreach ([0, -1, 1] as $d) {
        if (hash_equals(cs_totp($secret, $step + $d), $code)) {
            return true;
        }
    }
    return false;
}

/* Wrong sign-ins: at most CS_FAILS per 15 minutes per address and per user name. */
function cs_fail_file(string $who): string
{
    return cs_private() . '/state/fails-' . hash('sha256', $who) . '.json';
}

function cs_fails(string $who): array
{
    $f = cs_fail_file($who);
    $list = is_file($f) ? json_decode((string)file_get_contents($f), true) : [];
    return array_values(array_filter(is_array($list) ? $list : [], function ($t) {
        return is_int($t) && $t > time() - 900;
    }));
}

function cs_blocked(string ...$whos): bool
{
    foreach ($whos as $w) {
        if (count(cs_fails($w)) >= CS_FAILS) {
            return true;
        }
    }
    return false;
}

function cs_record_fail(string ...$whos): void
{
    @mkdir(cs_private() . '/state', 0700, true);
    foreach ($whos as $w) {
        $list = cs_fails($w);
        $list[] = time();
        file_put_contents(cs_fail_file($w), json_encode($list), LOCK_EX);
    }
}

function cs_sign_in(string $name, string $password, string $code): ?string
{
    $ip = 'ip:' . ($_SERVER['REMOTE_ADDR'] ?? '?');
    $who = 'user:' . strtolower($name);
    if (cs_blocked($ip, $who)) {
        return 'Πολλές λανθασμένες προσπάθειες. Δοκιμάστε ξανά σε 15 λεπτά.';
    }
    $users = cs_config()['users'] ?? [];
    $u = $users[$name] ?? null;
    // the same work whether or not the user exists, so the answer time reveals nothing
    $ok = cs_password_ok((string)($u['password'] ?? 'pbkdf2-sha256$600000$AAAA$AAAA'), $password) && $u !== null;
    if ($ok && !empty($u['totp'])) {
        $ok = cs_totp_ok((string)$u['totp'], $code);
    }
    if (!$ok) {
        cs_record_fail($ip, $who);
        cs_log('sign-in failed', $name);
        return 'Λάθος όνομα, κωδικός ή κωδικός επιβεβαίωσης.';
    }
    session_regenerate_id(true);
    $_SESSION['user'] = $name;
    $_SESSION['csrf'] = bin2hex(random_bytes(32));
    cs_log('signed in', $name);
    return null;
}

/* ------------------------------------------------------------ answers */
function cs_json($data, int $status = 200): void
{
    http_response_code($status);
    header('Content-Type: application/json; charset=utf-8');
    echo json_encode($data, JSON_UNESCAPED_UNICODE | JSON_HEX_TAG | JSON_HEX_AMP);
    exit;
}

function cs_error(string $message, int $status = 400): void
{
    cs_json(['ok' => false, 'error' => $message], $status);
}

function cs_check_csrf(): void
{
    $sent = (string)($_SERVER['HTTP_X_CSRF'] ?? '');
    if ($sent === '' || !hash_equals((string)($_SESSION['csrf'] ?? ''), $sent)) {
        cs_error('Η σελίδα έληξε. Ανανεώστε τη σελίδα και δοκιμάστε ξανά.', 403);
    }
}

function cs_log(string $what, string $detail = ''): void
{
    $dir = cs_private() . '/state';
    @mkdir($dir, 0700, true);
    $line = sprintf("%s\t%s\t%s\t%s\t%s\n", date('c'), $_SERVER['REMOTE_ADDR'] ?? '?',
                    (string)($_SESSION['user'] ?? '-'), $what, str_replace(["\t", "\n"], ' ', $detail));
    @file_put_contents($dir . '/log.txt', $line, FILE_APPEND | LOCK_EX);
}

/* ------------------------------------------------------------ the site's data (read only) */
function cs_js_string(string $raw): string
{
    $v = json_decode('"' . $raw . '"');
    return is_string($v) ? $v : $raw;
}

/** date => ['title' => ..., 'tags' => [...]] of every broadcast on the site, newest first. */
function cs_broadcasts(): array
{
    $js = (string)@file_get_contents(cs_site() . '/js/broadcasts.js');
    preg_match_all('/^\s*ep\("(\d{4}-\d{2}-\d{2})", "((?:[^"\\\\]|\\\\.)*)", "[^"]*"(?:, \{(.*)\})?\),?\s*$/mu', $js, $m, PREG_SET_ORDER);
    $out = [];
    foreach ($m as $e) {
        $tags = [];
        if (isset($e[3]) && preg_match('/tags: "([^"]*)"/', $e[3], $t)) {
            $tags = array_values(array_filter(explode(' ', $t[1])));
        }
        $out[$e[1]] = ['title' => cs_js_string($e[2]), 'tags' => $tags, 'files' => isset($e[3]) && strpos($e[3], 'files:') !== false];
    }
    krsort($out);
    return $out;
}

function cs_titles_en(): array
{
    $js = (string)@file_get_contents(cs_site() . '/js/broadcasts-en.js');
    preg_match_all('/^\s*"(\d{4}-\d{2}-\d{2})": "((?:[^"\\\\]|\\\\.)*)",?\s*$/mu', $js, $m, PREG_SET_ORDER);
    $out = [];
    foreach ($m as $e) {
        $out[$e[1]] = cs_js_string($e[2]);
    }
    return $out;
}

/** [[id, Greek name], ...] of the topics, in the site's order. */
function cs_topics(): array
{
    $js = (string)@file_get_contents(cs_site() . '/js/tags.js');
    preg_match_all('/id: "([a-z]+)",\s*name: "([^"]+)"/u', $js, $m, PREG_SET_ORDER);
    return array_map(function ($e) { return [$e[1], $e[2]]; }, $m);
}

function cs_site_setting(string $key): string
{
    $js = (string)@file_get_contents(cs_site() . '/js/broadcasts.js');
    return preg_match('/^\s*' . preg_quote($key, '/') . ': "([^"]*)"/m', $js, $m) ? $m[1] : '';
}

/* ------------------------------------------------------------ checks of what is sent */
function cs_valid_date(string $d): bool
{
    return (bool)preg_match('/^(\d{4})-(\d{2})-(\d{2})$/', $d, $m) && checkdate((int)$m[2], (int)$m[3], (int)$m[1]);
}

function cs_clean_text($s, int $longest = 200): ?string
{
    $s = trim(preg_replace('/\s+/u', ' ', (string)$s) ?? '');              // null (→ '') if not valid UTF-8
    $letters = (int)preg_match_all('/./su', $s);                            // no mbstring needed
    if ($letters > $longest || preg_match('/[\x00-\x1f<>]/', $s)) {
        return null;
    }
    return $s;
}

function cs_clean_tags($tags): ?array
{
    if (!is_array($tags)) {
        return null;
    }
    $known = array_column(cs_topics(), 0);
    $tags = array_values(array_filter(array_map('strval', $tags)));
    if (count($tags) > 3 || count(array_unique($tags)) !== count($tags) || array_diff($tags, $known)) {
        return null;
    }
    return $tags;
}

/** The start of an mp3: an ID3 tag, or an MPEG audio frame. */
function cs_looks_like_mp3(string $head): bool
{
    if (strlen($head) < 4) {
        return false;
    }
    if (substr($head, 0, 3) === 'ID3') {
        return true;
    }
    return ord($head[0]) === 0xFF && (ord($head[1]) & 0xE0) === 0xE0;
}

/* ------------------------------------------------------------ the inbox */
function cs_inbox(): string
{
    return cs_private() . '/inbox';
}

function cs_new_id(): string
{
    return date('Ymd-His') . '-' . bin2hex(random_bytes(4));
}

function cs_valid_id(string $id): bool
{
    return (bool)preg_match('/^\d{8}-\d{6}-[0-9a-f]{8}$/', $id);
}

/** Requests waiting or being published: [['id', 'type', 'date', 'title', 'state'], ...] */
function cs_pending(): array
{
    $out = [];
    foreach (['inbox' => 'waiting', 'processing' => 'publishing'] as $dir => $state) {
        foreach (@scandir(cs_private() . '/' . $dir) ?: [] as $id) {
            $f = cs_private() . "/$dir/$id/request.json";
            if ($id === '' || $id[0] === '.' || !is_file($f)) {
                continue;
            }
            $r = json_decode((string)file_get_contents($f), true) ?: [];
            $out[] = ['id' => $id, 'type' => $r['type'] ?? '', 'date' => $r['date'] ?? '', 'title' => $r['title'] ?? '',
                      'state' => $state];
        }
    }
    return $out;
}

/** The latest outcomes written by tools/inbox.py, newest first. */
function cs_results(int $n = 15): array
{
    $files = glob(cs_private() . '/results/*.json') ?: [];
    rsort($files);
    $out = [];
    foreach (array_slice($files, 0, $n) as $f) {
        $r = json_decode((string)file_get_contents($f), true);
        if (is_array($r)) {
            $out[] = array_intersect_key($r, array_flip(['id', 'type', 'status', 'message', 'time', 'user', 'date', 'title', 'link']));
        }
    }
    return $out;
}

/** Put a finished request into the inbox: written in a hidden folder, then moved in one step. */
function cs_submit(string $id, string $staging, array $request): void
{
    file_put_contents("$staging/request.json", json_encode($request, JSON_UNESCAPED_UNICODE | JSON_PRETTY_PRINT));
    @unlink("$staging/meta.json");
    if (!@rename($staging, cs_inbox() . '/' . $id)) {
        cs_error('Η αποθήκευση απέτυχε στον server. Δοκιμάστε ξανά.', 500);
    }
    cs_log('handed in', $id . ' ' . ($request['type'] ?? '') . ' ' . ($request['date'] ?? ''));
    cs_wake_publisher();
}

function cs_staging(string $id): string
{
    return cs_inbox() . '/.staging/' . $id;
}

function cs_clear_old_staging(): void
{
    foreach (glob(cs_inbox() . '/.staging/*', GLOB_ONLYDIR) ?: [] as $d) {
        if (filemtime($d) < time() - 86400) {
            foreach (glob("$d/*") ?: [] as $f) {
                @unlink($f);
            }
            @rmdir($d);
        }
    }
}

/** Ask GitHub to start publishing now (otherwise it starts by itself within a few hours). Best effort. */
function cs_wake_publisher(): void
{
    $g = cs_config()['github'] ?? [];
    if (empty($g['token']) || empty($g['repo'])) {
        return;
    }
    $url = 'https://api.github.com/repos/' . $g['repo'] . '/actions/workflows/' . ($g['workflow'] ?? 'inbox.yml') . '/dispatches';
    $body = json_encode(['ref' => $g['ref'] ?? 'main']);
    $headers = ['Authorization: Bearer ' . $g['token'], 'Accept: application/vnd.github+json', 'User-Agent: cs-upload-page',
                'X-GitHub-Api-Version: 2022-11-28', 'Content-Type: application/json'];
    if (function_exists('curl_init')) {
        $c = curl_init($url);
        curl_setopt_array($c, [CURLOPT_POST => true, CURLOPT_POSTFIELDS => $body, CURLOPT_HTTPHEADER => $headers,
                               CURLOPT_RETURNTRANSFER => true, CURLOPT_TIMEOUT => 8]);
        curl_exec($c);
        curl_close($c);
        return;
    }
    @file_get_contents($url, false, stream_context_create(['http' => ['method' => 'POST', 'content' => $body,
        'header' => implode("\r\n", $headers), 'timeout' => 8, 'ignore_errors' => true]]));
}
