<?php
/*
 * The question form of contact.html (and en/contact.html): each question is emailed to science@christianity.gr,
 * with Reply-To the person who asked, so a reply goes straight to them. A copy is kept in <private>/questions/
 * (outside the public web folder; "emailed": false if the email did not go out, and the person was told so).
 *
 * Sent with the server's own mail (PHP mail()): no mailbox password is stored anywhere. christianity.gr's mail is
 * on this same server, and christianity-science.gr's SPF record names it, so the email is delivered as genuine.
 * Answers {"success": true} or {"success": false, "message": …} (js/page.js reads it).
 *
 * Settings (optional) in <private>/config.php: 'questions_to' => 'someone@…' (comma between several).
 * Plain PHP 7.4+ with built-in functions only.
 */
declare(strict_types=1);

const ASK_TO = 'science@christianity.gr';
const ASK_FROM = 'website@christianity-science.gr';
const ASK_PER_HOUR = 5;                     // questions per hour from one internet address
const ASK_PER_DAY = 100;                    // and from everyone together (a runaway bot stops here)

if (!getenv('CS_SHOW_ERRORS')) {
    ini_set('display_errors', '0');
}

function ask_answer(bool $ok, string $message = '', int $status = 200): void
{
    http_response_code($status);
    header('Content-Type: application/json; charset=utf-8');
    header('Cache-Control: no-store');
    echo json_encode($ok ? ['success' => true] : ['success' => false, 'message' => $message], JSON_UNESCAPED_UNICODE);
    exit;
}

/** The private folder, found as the upload page finds it (admin/lib.php): CS_PRIVATE_DIR, or a cs-admin next to the site. */
function ask_private(): string
{
    $env = getenv('CS_PRIVATE_DIR');
    if ($env) {
        return rtrim($env, '/');
    }
    $up = dirname(__DIR__);
    for ($i = 0; $i < 4; $i++) {
        if (is_file("$up/cs-admin/config.php")) {
            return "$up/cs-admin";
        }
        $up = dirname($up);
    }
    return dirname(__DIR__) . '/cs-admin';
}

/** The first $n characters of UTF-8 text (without the optional mbstring extension). */
function ask_cut(string $s, int $n): string
{
    return preg_match('/^.{0,' . $n . '}/us', $s, $m) ? $m[0] : '';
}

function ask_length(string $s): int
{
    return (int)preg_match_all('/./us', $s);
}

/** One line of plain text, at most $longest characters ("" if it is not text). */
function ask_line($s, int $longest): string
{
    if (!is_string($s) || !preg_match('//u', $s)) {
        return '';
    }
    $s = trim(preg_replace('/[\x00-\x1F\x7F]+/u', ' ', $s));
    return ask_cut($s, $longest);
}

/** The question itself: line breaks kept, other control characters removed. */
function ask_text($s, int $longest): string
{
    if (!is_string($s) || !preg_match('//u', $s)) {
        return '';
    }
    $s = preg_replace('/[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]+/u', '', str_replace("\r\n", "\n", $s));
    return trim(ask_cut($s, $longest));
}

/** Whether this address (and everyone) may send another question now; counts it if so. */
function ask_allowed(string $dir): bool
{
    $now = time();
    $who = substr(hash('sha256', (string)($_SERVER['REMOTE_ADDR'] ?? '')), 0, 16);   // the address itself is not kept
    $file = "$dir/.limits.json";
    $fp = fopen($file, 'c+');
    if (!$fp) {
        return true;                          // never refuse a question because of the counter
    }
    flock($fp, LOCK_EX);
    $limits = json_decode((string)stream_get_contents($fp), true);
    $limits = is_array($limits) ? $limits : [];
    foreach ($limits as $k => $times) {
        $limits[$k] = array_values(array_filter((array)$times, function ($t) use ($now) { return $t > $now - 86400; }));
        if (!$limits[$k]) {
            unset($limits[$k]);
        }
    }
    $mine = array_filter($limits[$who] ?? [], function ($t) use ($now) { return $t > $now - 3600; });
    $all = array_sum(array_map('count', $limits));
    $ok = count($mine) < ASK_PER_HOUR && $all < ASK_PER_DAY;
    if ($ok) {
        $limits[$who][] = $now;
    }
    ftruncate($fp, 0);
    rewind($fp);
    fwrite($fp, json_encode($limits));
    flock($fp, LOCK_UN);
    fclose($fp);
    return $ok;
}

function ask_header(string $s): string
{
    return '=?UTF-8?B?' . base64_encode($s) . '?=';
}

// ---------- the request
if (($_SERVER['REQUEST_METHOD'] ?? '') !== 'POST') {
    ask_answer(false, 'POST only', 405);
}
$origin = (string)($_SERVER['HTTP_ORIGIN'] ?? '');
$host = preg_replace('/:\d+$/', '', (string)($_SERVER['HTTP_HOST'] ?? ''));
if ($origin !== '' && parse_url($origin, PHP_URL_HOST) !== $host) {
    ask_answer(false, 'Only from this website.', 403);          // other websites cannot send through this form
}
$in = json_decode((string)file_get_contents('php://input', false, null, 0, 64 * 1024), true);
if (!is_array($in)) {
    ask_answer(false, 'Not a question.', 400);
}
$english = isset($in['page']) && is_string($in['page']) && strpos($in['page'], '/en/') !== false;
$say = $english
    ? ['short' => 'Please write your question (at least 10 characters).', 'mail' => 'Please give a valid e-mail address.',
       'many' => 'Too many questions in a short time. Please try again later.', 'fail' => 'Sending did not work. Please try again in a moment.']
    : ['short' => 'Γράψτε την ερώτησή σας (τουλάχιστον 10 χαρακτήρες).', 'mail' => 'Δώστε ένα σωστό e-mail.',
       'many' => 'Πάρα πολλές ερωτήσεις σε λίγο χρόνο. Δοκιμάστε ξανά αργότερα.', 'fail' => 'Η αποστολή δεν έγινε. Δοκιμάστε ξανά σε λίγο.'];

if (!empty($in['botcheck'])) {
    ask_answer(true);                         // the hidden trap was filled in: a bot; pretend it worked, send nothing
}
$question = ask_text($in['question'] ?? '', 2000);
$name = ask_line($in['name'] ?? '', 100);
$email = ask_line($in['email'] ?? '', 200);
if (ask_length($question) < 10) {
    ask_answer(false, $say['short'], 400);
}
if (!filter_var($email, FILTER_VALIDATE_EMAIL)) {
    ask_answer(false, $say['mail'], 400);
}

$dir = ask_private() . '/questions';
if (!is_dir($dir) && !@mkdir($dir, 0700, true)) {
    ask_answer(false, $say['fail'], 500);
}
if (!ask_allowed($dir)) {
    ask_answer(false, $say['many'], 429);
}

// ---------- keep a copy, then email it
$when = date('Y-m-d H:i');
$id = date('Ymd-His-') . bin2hex(random_bytes(3));
$copy = ['date' => date('c'), 'name' => $name, 'email' => $email, 'question' => $question,
         'page' => ask_line($in['page'] ?? '', 300), 'emailed' => false];
$saved = @file_put_contents("$dir/$id.json", json_encode($copy, JSON_UNESCAPED_UNICODE | JSON_PRETTY_PRINT)) !== false;

$cfg = is_file(ask_private() . '/config.php') ? (require ask_private() . '/config.php') : [];
$to = is_array($cfg) && !empty($cfg['questions_to']) ? (string)$cfg['questions_to'] : ASK_TO;
$who = $name !== '' ? $name : $email;
$body = "Νέα ερώτηση από την ιστοσελίδα christianity-science.gr" . ($english ? " (αγγλική σελίδα)" : "") . "\n\n"
      . "Από: " . ($name !== '' ? "$name <$email>" : $email) . "\n"
      . "Πότε: $when\n\n"
      . $question . "\n\n"
      . "--\nΑπαντήστε σε αυτό το e-mail: η απάντηση πηγαίνει κατευθείαν στον αποστολέα.\n";
$headers = "From: " . ask_header('Χριστιανισμός & Επιστήμη (ιστοσελίδα)') . " <" . ASK_FROM . ">\r\n"
         . "Reply-To: " . ($name !== '' ? ask_header($name) . " " : "") . "<$email>\r\n"
         . "MIME-Version: 1.0\r\n"
         . "Content-Type: text/plain; charset=UTF-8\r\n"
         . "Content-Transfer-Encoding: base64";
$sent = @mail($to, ask_header("Ερώτηση από την ιστοσελίδα: " . ask_cut($who, 60)), chunk_split(base64_encode($body)), $headers);

if (!$sent) {
    ask_answer(false, $say['fail'], 500);     // the person is told, and can use the address on the page; the copy stays
}
if ($saved) {
    $copy['emailed'] = true;
    @file_put_contents("$dir/$id.json", json_encode($copy, JSON_UNESCAPED_UNICODE | JSON_PRETTY_PRINT));
}
ask_answer(true);
