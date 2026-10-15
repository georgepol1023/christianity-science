<?php
/*
 * The upload page of christianity-science.gr (Greek). Served at a secret address (ADMIN_PATH, see docs/SETUP.md).
 * It receives broadcasts, corrections and home page settings into the private inbox; tools/inbox.py publishes them.
 */
declare(strict_types=1);
require __DIR__ . '/lib.php';

// warnings go to the server's log, never into the page's answers (the tests turn them back on: CS_SHOW_ERRORS)
ini_set('display_errors', getenv('CS_SHOW_ERRORS') ? '1' : '0');
ini_set('log_errors', '1');
error_reporting(E_ALL);

header('X-Robots-Tag: noindex, nofollow');
header('Cache-Control: no-store');
header('X-Frame-Options: DENY');
header('Referrer-Policy: no-referrer');
header('X-Content-Type-Options: nosniff');

cs_gate();
cs_session();
$action = (string)($_GET['a'] ?? '');
$method = $_SERVER['REQUEST_METHOD'] ?? 'GET';
$user = cs_user();

/* ------------------------------------------------------------ sign-in and sign-out */
if ($action === 'login' && $method === 'POST') {
    cs_check_csrf();
    $in = json_decode((string)file_get_contents('php://input'), true) ?: [];
    $err = cs_sign_in((string)($in['name'] ?? ''), (string)($in['password'] ?? ''), (string)($in['code'] ?? ''));
    $err ? cs_error($err, 401) : cs_json(['ok' => true, 'csrf' => $_SESSION['csrf']]);
}
if ($action === 'logout' && $method === 'POST') {
    cs_check_csrf();
    cs_log('signed out');
    $_SESSION = [];
    session_regenerate_id(true);
    cs_json(['ok' => true]);
}
if ($action !== '' && !$user) {
    cs_error('Έχετε αποσυνδεθεί. Ανανεώστε τη σελίδα και συνδεθείτε ξανά.', 401);
}
if ($method === 'POST' && $action !== '') {
    cs_check_csrf();
}

/* ------------------------------------------------------------ what the page shows */
if ($action === 'state') {
    $en = cs_titles_en();
    $list = [];
    foreach (cs_broadcasts() as $date => $b) {
        $list[] = ['date' => $date, 'title' => $b['title'], 'tags' => $b['tags'], 'en' => $en[$date] ?? '', 'fixed' => $b['files']];
    }
    session_write_close();
    cs_json(['ok' => true, 'broadcasts' => $list, 'topics' => cs_topics(), 'pending' => cs_pending(), 'results' => cs_results(),
             'drafts' => cs_drafts(), 'youtube' => cs_site_setting('youtubeId'), 'next' => cs_site_setting('nextBroadcast'),
             'chunk' => cs_chunk_size()]);
}

/* ------------------------------------------------------------ recordings that came by email and wait to be completed */
function cs_draft(string $id): array
{
    $f = cs_private() . '/drafts/' . $id . '/request.json';
    $r = (cs_valid_id($id) && is_file($f)) ? json_decode((string)file_get_contents($f), true) : null;
    if (!is_array($r)) cs_error('Αυτές οι ηχογραφήσεις δεν περιμένουν πια (δημοσιεύτηκαν ή απορρίφθηκαν).', 404);
    return $r;
}

if ($action === 'draft_audio') {
    $id = (string)($_GET['id'] ?? '');
    $r = cs_draft($id);
    $n = (int)($_GET['n'] ?? 0);
    $f = $r['files'][$n - 1] ?? null;
    $path = $f ? cs_private() . '/drafts/' . $id . '/' . basename((string)$f['name']) : '';
    if (!$f || !is_file($path)) cs_error('Δεν βρέθηκε.', 404);
    session_write_close();
    header('Content-Type: audio/mpeg');
    header('Content-Length: ' . filesize($path));
    readfile($path);
    exit;
}

if ($action === 'draft_publish' && $method === 'POST') {
    $in = cs_input();
    $id = (string)($in['id'] ?? '');
    $r = cs_draft($id);
    [$date, $title, $title_en, $tags, $replace] = cs_check_broadcast($in);
    $r = array_merge($r, ['date' => $date, 'title' => $title, 'title_en' => $title_en, 'tags' => $tags, 'replace' => $replace,
                          'approved_by' => cs_user()['id'], 'email' => cs_user()['email'] ?? '']);
    $dir = cs_private() . '/drafts/' . $id;
    file_put_contents("$dir/request.json", json_encode($r, JSON_UNESCAPED_UNICODE | JSON_PRETTY_PRINT));
    if (!@rename($dir, cs_inbox() . '/' . $id)) cs_error('Η αποθήκευση απέτυχε στον server. Δοκιμάστε ξανά.', 500);
    cs_log('draft approved', "$id $date $title");
    cs_wake_publisher();
    cs_json(['ok' => true]);
}

if ($action === 'draft_discard' && $method === 'POST') {
    $id = (string)(cs_input()['id'] ?? '');
    cs_draft($id);
    @mkdir(cs_private() . '/discarded', 0700, true);
    if (!@rename(cs_private() . '/drafts/' . $id, cs_private() . '/discarded/' . $id)) cs_error('Δεν έγινε. Δοκιμάστε ξανά.', 500);
    cs_log('draft discarded', $id);
    cs_json(['ok' => true]);
}

/** The fields of a broadcast, checked; stops with the reason if they are not right. Never twice: a date already on
 *  the site (unless replacing), or already waiting in the inbox, is refused. */
function cs_check_broadcast(array $in): array
{
    $date = (string)($in['date'] ?? '');
    $title = cs_clean_text($in['title'] ?? '');
    $title_en = cs_clean_text($in['title_en'] ?? '');
    $tags = cs_clean_tags($in['tags'] ?? []);
    $replace = !empty($in['replace']);
    if (!cs_valid_date($date)) cs_error('Η ημερομηνία δεν είναι έγκυρη.');
    if ($title === null || $title === '') cs_error('Γράψτε τον τίτλο της εκπομπής (έως 200 χαρακτήρες, χωρίς < >).');
    if ($title_en === null) cs_error('Ο αγγλικός τίτλος δεν είναι έγκυρος.');
    if ($tags === null) cs_error('Επιλέξτε έως 3 θέματα.');
    $existing = cs_broadcasts()[$date] ?? null;
    if ($existing && !$replace) {
        cs_error('Η εκπομπή αυτής της ημερομηνίας υπάρχει ήδη: «' . $existing['title'] . '». Αν θέλετε να την αντικαταστήσετε, επιλέξτε «Αντικατάσταση».', 409);
    }
    foreach (cs_pending() as $p) {
        if ($p['type'] === 'broadcast' && $p['date'] === $date) {
            cs_error('Μια εκπομπή αυτής της ημερομηνίας έχει ήδη σταλεί και περιμένει δημοσίευση.', 409);
        }
    }
    return [$date, $title, $title_en, $tags, $replace];
}

function cs_chunk_size(): int
{
    $limit = PHP_INT_MAX;
    $post = trim((string)ini_get('post_max_size'));
    if ($post !== '' && $post !== '0') {
        $n = (int)$post;
        $unit = strtoupper(substr($post, -1));
        $n *= ['K' => 1024, 'M' => 1048576, 'G' => 1073741824][$unit] ?? 1;
        $limit = $n;
    }
    return max(256 * 1024, min(CS_MAX_CHUNK, $limit - 64 * 1024));
}

function cs_input(): array
{
    $in = json_decode((string)file_get_contents('php://input'), true);
    return is_array($in) ? $in : [];
}

/* ------------------------------------------------------------ a new broadcast: start, pieces, finish */
if ($action === 'start' && $method === 'POST') {
    $in = cs_input();
    $files = is_array($in['files'] ?? null) ? $in['files'] : [];
    if (count($files) < 1 || count($files) > CS_MAX_PARTS) cs_error('Επιλέξτε 1 έως ' . CS_MAX_PARTS . ' αρχεία mp3.');
    $list = [];
    $total = 0;
    foreach (array_values($files) as $i => $f) {
        $name = cs_clean_text($f['name'] ?? '', 255);
        $size = (int)($f['size'] ?? 0);
        if (!$name || !preg_match('/\.mp3$/i', $name)) cs_error('Μόνο αρχεία .mp3 γίνονται δεκτά («' . ($name ?: '?') . '»).');
        if ($size < 1 || $size > CS_MAX_FILE) cs_error('Το αρχείο «' . $name . '» είναι πολύ μεγάλο ή κενό.');
        $list[] = ['name' => 'part-' . ($i + 1) . '.mp3', 'original' => $name, 'bytes' => $size];
        $total += $size;
    }
    [$date, $title, $title_en, $tags, $replace] = cs_check_broadcast($in);
    @mkdir(cs_inbox() . '/.staging', 0700, true);
    cs_clear_old_staging();
    $free = @disk_free_space(cs_private());
    if ($free !== false && $free < 2 * $total + 200 * 1048576) {
        cs_error('Δεν υπάρχει αρκετός χώρος στον server. Ενημερώστε τον διαχειριστή της ιστοσελίδας.', 507);
    }
    $id = cs_new_id();
    $dir = cs_staging($id);
    if (!@mkdir($dir, 0700)) cs_error('Ο server δεν δέχτηκε την αποστολή. Δοκιμάστε ξανά.', 500);
    $u = cs_user();
    $request = ['type' => 'broadcast', 'id' => $id, 'created' => date('c'), 'user' => $u['id'], 'email' => $u['email'] ?? '',
                'date' => $date, 'title' => $title, 'title_en' => $title_en, 'tags' => $tags, 'replace' => $replace, 'files' => $list];
    file_put_contents("$dir/meta.json", json_encode($request, JSON_UNESCAPED_UNICODE));
    cs_log('upload started', "$id $date $title");
    cs_json(['ok' => true, 'id' => $id, 'chunk' => cs_chunk_size()]);
}

function cs_meta(string $id): array
{
    if (!cs_valid_id($id)) cs_error('Άγνωστη αποστολή.', 404);
    $f = cs_staging($id) . '/meta.json';
    $m = is_file($f) ? json_decode((string)file_get_contents($f), true) : null;
    if (!is_array($m) || ($m['user'] ?? '') !== cs_user()['id']) cs_error('Άγνωστη αποστολή. Ξεκινήστε από την αρχή.', 404);
    return $m;
}

if ($action === 'piece' && $method === 'POST') {
    $id = (string)($_GET['id'] ?? '');
    $m = cs_meta($id);
    session_write_close();
    $n = (int)($_GET['n'] ?? 0);
    $offset = (int)($_GET['offset'] ?? -1);
    $f = $m['files'][$n - 1] ?? null;
    if (!$f) cs_error('Άγνωστο αρχείο.', 404);
    $path = cs_staging($id) . '/' . $f['name'];
    clearstatcache(true, $path);
    $have = is_file($path) ? (int)filesize($path) : 0;
    if ($offset !== $have) {
        cs_json(['ok' => true, 'size' => $have]);       // a repeated piece: tell the page where to go on from
    }
    $data = (string)file_get_contents('php://input');
    $test_limit = (int)getenv('CS_MAX_PIECE_FOR_TESTS');     // only set by tests/admin_browser.test.js
    if (($data === '' && (int)($_SERVER['CONTENT_LENGTH'] ?? 0) > 0) || ($test_limit > 0 && strlen($data) > $test_limit)) {
        cs_error('Το κομμάτι ήταν μεγαλύτερο από όσο δέχεται ο server.', 413);   // the page sends smaller ones
    }
    if ($data === '' || strlen($data) > CS_MAX_CHUNK || $have + strlen($data) > (int)$f['bytes']) {
        cs_error('Λάθος κομμάτι αρχείου.', 400);
    }
    if ($have === 0 && !cs_looks_like_mp3($data)) {
        cs_error('Το αρχείο «' . $f['original'] . '» δεν είναι mp3.', 415);
    }
    $h = fopen($path, 'ab');
    if (!$h || !flock($h, LOCK_EX) || fwrite($h, $data) !== strlen($data)) {
        cs_error('Ο server δεν μπόρεσε να αποθηκεύσει το αρχείο (χώρος;).', 507);
    }
    fflush($h);
    flock($h, LOCK_UN);
    fclose($h);
    clearstatcache(true, $path);
    cs_json(['ok' => true, 'size' => (int)filesize($path)]);
}

if ($action === 'finish' && $method === 'POST') {
    $id = (string)(cs_input()['id'] ?? '');
    $m = cs_meta($id);
    foreach ($m['files'] as $f) {
        $path = cs_staging($id) . '/' . $f['name'];
        clearstatcache(true, $path);
        if (!is_file($path) || filesize($path) !== (int)$f['bytes']) {
            cs_error('Το αρχείο «' . $f['original'] . '» δεν ανέβηκε ολόκληρο. Στείλτε ξανά.', 400);
        }
    }
    foreach (cs_pending() as $p) {                           // checked again: two windows open at once
        if ($p['type'] === 'broadcast' && $p['date'] === $m['date']) {
            cs_error('Μια εκπομπή αυτής της ημερομηνίας έχει ήδη σταλεί και περιμένει δημοσίευση.', 409);
        }
    }
    cs_submit($id, cs_staging($id), $m);
    cs_json(['ok' => true]);
}

if ($action === 'cancel' && $method === 'POST') {
    $id = (string)(cs_input()['id'] ?? '');
    $m = cs_meta($id);
    foreach (glob(cs_staging($id) . '/*') ?: [] as $f) @unlink($f);
    @rmdir(cs_staging($id));
    cs_json(['ok' => true]);
}

/* ------------------------------------------------------------ corrections and home page settings */
function cs_simple_request(array $fields): void
{
    $id = cs_new_id();
    $dir = cs_staging($id);
    @mkdir(cs_inbox() . '/.staging', 0700, true);
    if (!@mkdir($dir, 0700)) cs_error('Ο server δεν δέχτηκε την αποστολή. Δοκιμάστε ξανά.', 500);
    $u = cs_user();
    cs_submit($id, $dir, $fields + ['id' => $id, 'created' => date('c'), 'user' => $u['id'], 'email' => $u['email'] ?? '']);
    cs_json(['ok' => true]);
}

if ($action === 'correct' && $method === 'POST') {
    $in = cs_input();
    $date = (string)($in['date'] ?? '');
    $b = cs_broadcasts()[$date] ?? null;
    if (!$b) cs_error('Επιλέξτε μια εκπομπή.');
    if (!empty($b['files'])) cs_error('Αυτή η εκπομπή έχει ειδική λίστα αρχείων· τη διορθώνει ο διαχειριστής του κώδικα.');
    $req = ['type' => 'correction', 'date' => $date];
    if (isset($in['title'])) {
        $t = cs_clean_text($in['title']);
        if (!$t) cs_error('Ο τίτλος δεν είναι έγκυρος.');
        $req['title'] = $t;
    }
    if (isset($in['title_en'])) {
        $t = cs_clean_text($in['title_en']);
        if (!$t) cs_error('Ο αγγλικός τίτλος δεν είναι έγκυρος.');
        $req['title_en'] = $t;
    }
    if (isset($in['tags'])) {
        $t = cs_clean_tags($in['tags']);
        if ($t === null || !$t) cs_error('Επιλέξτε 1 έως 3 θέματα.');
        $req['tags'] = $t;
    }
    if (count($req) === 2) cs_error('Δεν αλλάξατε τίποτα.');
    cs_simple_request($req);
}

if ($action === 'settings' && $method === 'POST') {
    $in = cs_input();
    $req = ['type' => 'settings'];
    $video = trim((string)($in['youtube'] ?? ''));
    if ($video !== '') {
        if (!preg_match('~(?:youtu\.be/|[?&]v=|/embed/|/shorts/|/live/)([\w-]{11})|^([\w-]{11})$~', $video)) {
            cs_error('Αυτός δεν είναι σύνδεσμος βίντεο του YouTube.');
        }
        $req['youtube'] = $video;
    }
    $next = trim((string)($in['next'] ?? ''));
    if ($next !== '') {
        if (!preg_match('/^(\d{4}-\d{2}-\d{2})T(\d{2}):(\d{2})$/', $next, $mm) || !cs_valid_date($mm[1]) || (int)$mm[2] > 23 || (int)$mm[3] > 59) {
            cs_error('Η ημερομηνία ή η ώρα δεν είναι έγκυρη.');
        }
        $req['next_broadcast'] = $next;
    }
    if (count($req) === 1) cs_error('Δεν αλλάξατε τίποτα.');
    cs_simple_request($req);
}

if ($action !== '') {
    cs_error('Άγνωστη ενέργεια.', 404);
}

/* ------------------------------------------------------------ the page */
$nonce = base64_encode(random_bytes(16));
header("Content-Security-Policy: default-src 'none'; script-src 'nonce-$nonce'; style-src 'nonce-$nonce'; "
     . "img-src 'self' https://i.ytimg.com; media-src 'self'; connect-src 'self'; form-action 'self'; base-uri 'none'; frame-ancestors 'none'");
header('Content-Type: text/html; charset=utf-8');
$csrf = htmlspecialchars((string)$_SESSION['csrf'], ENT_QUOTES);
$name = $user ? htmlspecialchars((string)($user['name'] ?? $user['id']), ENT_QUOTES) : '';
require __DIR__ . '/page.php';
