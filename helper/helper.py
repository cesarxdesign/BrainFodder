#!/usr/bin/env python3
"""BrainFodder helper: runs on Cesar's Mac only, started by macOS when the page's
Fetch button connects, and quits as soon as that job is answered.

POST /run   fetch every feed, group stories that report the same news with Claude
            Haiku (through Claude Code, on the Max plan), stream results back
POST /feed  find and read one feed (for "Add a subscription")

macOS (launchd) holds the port and starts this program on the first connection,
so nothing runs between clicks. Bodies are sent as text/plain so the browser
needs no CORS preflight.
"""
import concurrent.futures as cf
import ctypes
import email.utils
import html
import html.entities
import json
import os
import re
import socket
import subprocess
import sys
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone, timedelta

PORT = 47823
ALLOWED_ORIGINS = re.compile(r'^(https://brainfodder\.vercel\.app|https://cesarxdesign\.github\.io|http://(localhost|127\.0\.0\.1)(:\d+)?)$')
CLAUDE = os.path.expanduser('~/.local/bin/claude')
WORKDIR = os.path.expanduser('~/Library/Application Support/BrainFodder/run')
LOGDIR = os.path.expanduser('~/Library/Logs/BrainFodder')
UA = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130 Safari/537.36 BrainFodder/1.0'
MAX_BYTES = 8 * 1024 * 1024
MAX_ITEMS = 60
FALLBACK_PATHS = ['/feed', '/rss', '/feed.xml', '/rss.xml', '/atom.xml', '/index.xml', '/feed/']
GROUP_HOURS = 48          # only news this fresh is grouped
ARTICLE_WORDS = 800       # per source, when choosing what to read further
HAIKU_PARALLEL = 4


def log(*a):
    try:
        os.makedirs(LOGDIR, exist_ok=True)
        with open(os.path.join(LOGDIR, 'helper.log'), 'a') as f:
            f.write(datetime.now().strftime('%Y-%m-%d %H:%M:%S ') + ' '.join(str(x) for x in a) + '\n')
    except Exception:
        pass


# ---------------------------------------------------------------- fetching

class Redirects(urllib.request.HTTPRedirectHandler):
    # Python 3.9 does not follow 308; feeds use it (Substack custom domains)
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if code == 308:
            code = 307
        return super().redirect_request(req, fp, code, msg, headers, newurl)
    http_error_308 = urllib.request.HTTPRedirectHandler.http_error_302


OPENER = urllib.request.build_opener(Redirects)


def get(url, accept='application/rss+xml, application/atom+xml, application/xml;q=0.9, text/xml;q=0.9, text/html;q=0.8, */*;q=0.5'):
    req = urllib.request.Request(url, headers={'User-Agent': UA, 'Accept': accept})
    try:
        r = OPENER.open(req, timeout=10)
    except urllib.error.HTTPError as e:
        raise Exception('HTTP %d' % e.code)
    except socket.timeout:
        raise Exception('Timed out')
    except urllib.error.URLError as e:
        raise Exception(str(e.reason))
    data = r.read(MAX_BYTES + 1)
    if len(data) > MAX_BYTES:
        raise Exception('Feed too large')
    return data, r.geturl()


def as_text(data):
    head = data[:300].decode('ascii', 'replace')
    m = re.search(r'encoding=["\']([\w-]+)["\']', head, re.I)
    enc = m.group(1) if m else 'utf-8'
    try:
        return data.decode(enc, 'replace')
    except LookupError:
        return data.decode('utf-8', 'replace')


def is_feed(text):
    return re.search(r'<(rss|feed|rdf:RDF)[\s>]', text[:8000], re.I) is not None


def discover(page, base):
    found = []
    for tag in re.findall(r'<link\b[^>]*>', page, re.I):
        if not re.search(r'rel=["\']?[^"\'>]*alternate', tag, re.I):
            continue
        if not re.search(r'type=["\']?application/(rss|atom|feed)\+xml', tag, re.I):
            continue
        h = re.search(r'href=["\']([^"\']+)["\']', tag, re.I)
        if not h:
            continue
        t = re.search(r'title=["\']([^"\']*)["\']', tag, re.I)
        title = t.group(1) if t else ''
        found.append((urllib.parse.urljoin(base, html.unescape(h.group(1))), bool(re.search('comment', title + h.group(1), re.I))))
    best = [f for f in found if not f[1]] or found
    return best[0][0] if best else None


def resolve(url):
    data, final = get(url)
    text = as_text(data)
    if is_feed(text):
        return data, final
    f = discover(text, final)
    if f:
        try:
            d2, _ = get(f)
            if is_feed(as_text(d2)):
                return d2, f
        except Exception:
            pass
    p = urllib.parse.urlsplit(final)
    origin = '%s://%s' % (p.scheme, p.netloc)
    for path in FALLBACK_PATHS:
        try:
            d2, _ = get(origin + path)
            if is_feed(as_text(d2)):
                return d2, origin + path
        except Exception:
            pass
    raise Exception('No feed found at that address')


# ---------------------------------------------------------------- parsing

XML_ENTS = {'amp', 'lt', 'gt', 'quot', 'apos'}


def to_tree(data):
    text = as_text(data)
    # expat 2.2 on this Mac has no guard against entity bombs; feeds never need their own entities
    if '<!ENTITY' in text[:65536]:
        raise Exception('Feed defines its own entities; skipped')
    text = re.sub(r'^\s*<\?xml[^>]*\?>', '', text)
    try:
        return ET.fromstring(text)
    except ET.ParseError:
        # HTML entities such as &nbsp; are not valid XML; turn them into numbers and retry
        def fix(m):
            n = m.group(1)
            if n in XML_ENTS:
                return m.group(0)
            cp = html.entities.name2codepoint.get(n)
            return '&#%d;' % cp if cp else '&amp;' + n + ';'
        return ET.fromstring(re.sub(r'&([A-Za-z][A-Za-z0-9]*);', fix, text))


def local(tag):
    return tag.rsplit('}', 1)[-1] if isinstance(tag, str) else ''


def child(el, name):
    for c in el:
        if local(c.tag) == name:
            return c
    return None


def children(el, name):
    return [c for c in el if local(c.tag) == name]


def text_of(el):
    if el is None:
        return ''
    if len(el) and (el.get('type') == 'xhtml'):
        return ''.join(ET.tostring(c, encoding='unicode') for c in el)
    return (el.text or '').strip()


def plain(s):
    s = re.sub(r'<[^>]*>', ' ', s or '')
    return re.sub(r'\s+', ' ', html.unescape(s)).strip()


def iso(s):
    s = (s or '').strip()
    if not s:
        return None
    d = None
    try:
        d = email.utils.parsedate_to_datetime(s)
    except Exception:
        try:
            d = datetime.fromisoformat(s.replace('Z', '+00:00'))
        except Exception:
            m = re.match(r'(\d{4}-\d{2}-\d{2})', s)
            if m:
                d = datetime.fromisoformat(m.group(1))
    if d is None:
        return None
    if d.tzinfo is None:
        d = d.replace(tzinfo=timezone.utc)
    return d.astimezone(timezone.utc).strftime('%Y-%m-%dT%H:%M:%S.000Z')


def absu(u, base):
    try:
        return urllib.parse.urljoin(base, u) if u else ''
    except Exception:
        return u or ''


def make_item(guid, title, link, author, date, content, base):
    content = content or ''
    if len(content) > 200000:
        content = content[:200000]
    t = plain(title) or plain(content)[:90] or '(untitled)'
    return {'guid': str(guid or link or t), 'title': t, 'link': absu(link, base), 'author': plain(author),
            'date': iso(date), 'content': content, 'snippet': plain(content)[:220]}


def atom_link(el):
    links = children(el, 'link')
    for l in links:
        if l.get('rel') in (None, 'alternate') and l.get('href'):
            return l.get('href')
    return links[0].get('href', '') if links else ''


def media_content(e, link):
    g = child(e, 'group')
    if g is None:
        return ''
    th = child(g, 'thumbnail')
    thumb = th.get('url') if th is not None else ''
    desc = html.escape(text_of(child(g, 'description')), quote=False)
    out = '<p><a href="%s"><img src="%s" alt=""></a></p>' % (html.escape(link), html.escape(thumb)) if thumb else ''
    return out + ('<p>%s</p>' % desc.replace('\n', '<br>') if desc else '')


def parse(data, feed_url):
    root = to_tree(data)
    kind = local(root.tag)
    if kind in ('rss', 'RDF'):
        ch = child(root, 'channel')
        if ch is None:
            ch = root
        raw = children(ch, 'item') or children(root, 'item')
        site = absu(text_of(child(ch, 'link')), feed_url)
        items = []
        for i in raw[:MAX_ITEMS]:
            guid = text_of(child(i, 'guid')) or i.get('{http://www.w3.org/1999/02/22-rdf-syntax-ns#}about')
            link = text_of(child(i, 'link')) or (guid if (guid or '').startswith('http') else '')
            date = text_of(child(i, 'pubDate')) or text_of(child(i, 'date')) or text_of(child(i, 'published')) or text_of(child(i, 'updated'))
            content = text_of(child(i, 'encoded')) or text_of(child(i, 'description'))
            author = text_of(child(i, 'creator')) or text_of(child(i, 'author'))
            items.append(make_item(guid, text_of(child(i, 'title')), link, author, date, content, site or feed_url))
        return {'title': plain(text_of(child(ch, 'title'))), 'siteUrl': site, 'items': items}
    if kind == 'feed':
        site = absu(atom_link(root), feed_url)
        items = []
        for e in children(root, 'entry')[:MAX_ITEMS]:
            link = atom_link(e)
            au = child(e, 'author')
            content = text_of(child(e, 'content')) or text_of(child(e, 'summary')) or media_content(e, link)
            it = make_item(text_of(child(e, 'id')), text_of(child(e, 'title')), link,
                           text_of(child(au, 'name')) if au is not None else '',
                           text_of(child(e, 'published')) or text_of(child(e, 'updated')), content, site or feed_url)
            vid = text_of(child(e, 'videoId'))
            if vid:
                it['yt'] = {'id': vid, 'short': '/shorts/' in it['link']}
            items.append(it)
        return {'title': plain(text_of(child(root, 'title'))), 'siteUrl': site, 'items': items}
    raise Exception('Not a feed')


def read_feed(url):
    data, final = resolve(url)
    out = parse(data, final)
    out['feedUrl'] = final
    return out


# ---------------------------------------------------------------- Haiku via Claude Code

def haiku(system, prompt, schema):
    """One call to Claude Haiku through Claude Code, on the signed-in Max plan."""
    os.makedirs(WORKDIR, exist_ok=True)
    env = {k: v for k, v in os.environ.items() if k not in ('ANTHROPIC_API_KEY', 'ANTHROPIC_AUTH_TOKEN', 'ANTHROPIC_BASE_URL')}
    env['PATH'] = '/usr/bin:/bin:/usr/sbin:/sbin:' + os.path.dirname(CLAUDE)
    cmd = [CLAUDE, '-p', '--model', 'haiku', '--tools', '', '--system-prompt', system,
           '--setting-sources', '', '--strict-mcp-config', '--no-session-persistence',
           '--disable-slash-commands', '--output-format', 'json', '--json-schema', json.dumps(schema)]
    r = subprocess.run(cmd, input=prompt, capture_output=True, text=True, cwd=WORKDIR, env=env, timeout=240)
    try:
        d = json.loads(r.stdout)
    except Exception:
        raise Exception('Claude Code gave no answer: ' + (r.stderr or r.stdout)[:300])
    if d.get('is_error') or d.get('structured_output') is None:
        raise Exception('Claude Code: ' + str(d.get('result'))[:300])
    u = d.get('usage') or {}
    tokens = sum(u.get(k, 0) or 0 for k in ('input_tokens', 'cache_creation_input_tokens', 'cache_read_input_tokens', 'output_tokens'))
    return d['structured_output'], tokens


GROUP_SYSTEM = """You sort news items into stories. Two items belong to the same story only when they report the same specific event: the same match result, the same announcement, the same launch, the same deal. Sharing a topic, a person or a company is not enough: two different matches by the same player are two stories. When unsure, keep items apart.
Lines starting with S are stories already made; lines starting with I are single items. Return only groups of 2 or more keys that belong together. A group may contain at most one S key."""

GROUP_SCHEMA = {'type': 'object', 'properties': {'groups': {'type': 'array', 'items': {'type': 'array', 'items': {'type': 'string'}}}}, 'required': ['groups']}

STORY_SYSTEM = """You write one entry for a news reader from several sources that report the same story. Use only facts stated in the sources; never add anything.
headline: plain, specific, under 90 characters, no clickbait.
summary: 2 to 3 short sentences with the key facts (who, what, result, numbers).
pick: the key of the source that gives the reader the most beyond your summary (analysis, quotes, context, detail). Prefer a source with real article text over one that only has a headline.
why: under 12 words describing what that source's content adds, e.g. "Set by set detail and quotes from both players".
Some sources have only a headline and a snippet. Then summarise what those say, and never mention what is missing or unavailable, in the summary or in why.
Write in British English. No em dashes."""

STORY_SCHEMA = {'type': 'object', 'properties': {'headline': {'type': 'string'}, 'summary': {'type': 'string'}, 'pick': {'type': 'string'}, 'why': {'type': 'string'}}, 'required': ['headline', 'summary', 'pick', 'why']}


def article_text(link, snippet):
    host = urllib.parse.urlsplit(link).netloc
    if not link or host.endswith('news.google.com'):
        return snippet or '', False
    try:
        data, _ = get(link, accept='text/html,application/xhtml+xml;q=0.9,*/*;q=0.5')
        page = as_text(data)
    except Exception:
        return snippet or '', False
    m = re.search(r'<article\b.*?</article>', page, re.S | re.I)
    body = m.group(0) if m else page
    body = re.sub(r'<(script|style|nav|header|footer|aside|figure|form)\b.*?</\1>', ' ', body, flags=re.S | re.I)
    paras = [plain(p) for p in re.findall(r'<p\b[^>]*>(.*?)</p>', body, re.S | re.I)]
    words = ' '.join(p for p in paras if len(p) > 40).split()
    if len(words) < 60:
        return snippet or '', False
    return ' '.join(words[:ARTICLE_WORDS]), True


# ---------------------------------------------------------------- the run

def run(job, emit):
    subs = job.get('subs') or []
    known = job.get('recent') or []          # page's items from the last GROUP_HOURS
    stories = {s['id']: s for s in (job.get('stories') or [])}
    t0 = time.time()
    emit({'type': 'progress', 'text': 'Fetching %d feeds' % len(subs)})

    fetched = {}

    def one(s):
        try:
            return s, read_feed(s['url']), None
        except Exception as e:
            return s, None, str(e) or 'Could not load feed'

    with cf.ThreadPoolExecutor(10) as ex:
        for s, data, err in ex.map(one, subs):
            if err:
                emit({'type': 'feedError', 'id': s['id'], 'error': err})
            else:
                fetched[s['id']] = data
                emit({'type': 'feed', 'id': s['id'], 'data': data})
    log('fetched', len(fetched), 'of', len(subs), 'feeds in %.1fs' % (time.time() - t0))

    # what to group: news from the last GROUP_HOURS, no videos
    cutoff = datetime.now(timezone.utc) - timedelta(hours=GROUP_HOURS)
    titles = {s['id']: s.get('title', '') for s in subs}
    pool = {}
    for k in known:
        pool[k['id']] = dict(k, new=not k.get('checked'))   # items no earlier run has grouped count as new
    for sid, data in fetched.items():
        for it in data['items']:
            if it.get('yt') or not it.get('date'):
                continue
            if datetime.fromisoformat(it['date'].replace('Z', '+00:00')) < cutoff:
                continue
            iid = sid + '|' + it['guid']
            if iid in pool:
                continue
            pool[iid] = {'id': iid, 'feed': sid, 'title': it['title'], 'snippet': it['snippet'], 'link': it['link'], 'story': None, 'new': True}
    new_ids = [i for i, v in pool.items() if v.get('new')]
    emit({'type': 'progress', 'text': '%d new items; grouping with Haiku' % len(new_ids)})
    if not new_ids:
        return {'stories': [], 'tokens': 0, 'calls': 0}

    # one line per existing story, one per item not in a story
    lines, keymap = [], {}
    for sid, s in stories.items():
        if any(pool.get(m) for m in s.get('members', [])):
            k = 'S%d' % (len(keymap) + 1)
            keymap[k] = ('story', sid)
            lines.append('%s | %s' % (k, s['headline']))
    for iid, v in pool.items():
        if v.get('story') and v['story'] in stories:
            continue
        k = 'I%d' % (len(keymap) + 1)
        keymap[k] = ('item', iid)
        lines.append('%s | %s | %s | %s' % (k, titles.get(v['feed'], ''), v['title'], (v.get('snippet') or '')[:160]))
    tokens = calls = 0
    try:
        out, t = haiku(GROUP_SYSTEM, '\n'.join(lines), GROUP_SCHEMA)
        tokens += t
        calls += 1
    except Exception as e:
        log('group failed', e)
        emit({'type': 'progress', 'text': 'Grouping failed: %s' % e})
        return {'stories': [], 'tokens': tokens, 'calls': calls, 'error': str(e)}

    # turn groups into stories; only groups that take in something new matter
    changed = []
    n = 0
    for g in out.get('groups') or []:
        g = [k for k in g if k in keymap]
        if len(g) < 2:
            continue
        sids = [keymap[k][1] for k in g if keymap[k][0] == 'story']
        iids = [keymap[k][1] for k in g if keymap[k][0] == 'item']
        if not any(pool[i].get('new') for i in iids):
            continue
        if sids:
            sid = sids[0]
            members = list(dict.fromkeys(stories[sid]['members'] + iids))
        else:
            n += 1
            sid = 'st%d%02d' % (int(time.time() * 1000), n)
            members = iids
        if len(members) < 2:
            continue
        changed.append({'id': sid, 'members': members})
    emit({'type': 'progress', 'text': '%d stories with more than one source; reading them' % len(changed)})

    def write(st):
        mem = [pool[m] for m in st['members'] if m in pool]
        parts, keys = [], {}
        for j, m in enumerate(mem, 1):
            txt, full = article_text(m['link'], m.get('snippet'))
            keys['A%d' % j] = m['id']
            parts.append('A%d | %s | %s\n%s%s' % (j, titles.get(m['feed'], ''), m['title'], txt, '' if full else '\n(headline and snippet only)'))
        res, t = haiku(STORY_SYSTEM, '\n\n'.join(parts), STORY_SCHEMA)
        pick = keys.get(res.get('pick')) or mem[0]['id']
        return {'id': st['id'], 'members': st['members'], 'headline': res['headline'], 'summary': res['summary'],
                'pick': pick, 'why': res['why'], 'made': int(time.time() * 1000)}, t

    done = []
    with cf.ThreadPoolExecutor(HAIKU_PARALLEL) as ex:
        futs = [ex.submit(write, st) for st in changed]
        for f in cf.as_completed(futs):
            try:
                st, t = f.result()
                tokens += t
                calls += 1
                done.append(st)
                emit({'type': 'progress', 'text': 'Wrote %d of %d stories' % (len(done), len(changed))})
            except Exception as e:
                log('story failed', e)
    log('run: %d new items, %d stories, %d Haiku calls, %d tokens, %.0fs' % (len(new_ids), len(done), calls, tokens, time.time() - t0))
    return {'stories': done, 'tokens': tokens, 'calls': calls}


# ---------------------------------------------------------------- tiny HTTP server

def read_request(conn):
    buf = b''
    while b'\r\n\r\n' not in buf:
        chunk = conn.recv(65536)
        if not chunk:
            return None
        buf += chunk
        if len(buf) > 1 << 20:
            return None
    head, body = buf.split(b'\r\n\r\n', 1)
    lines = head.decode('latin-1').split('\r\n')
    method, path, _ = (lines[0].split(' ') + ['', '', ''])[:3]
    headers = {}
    for l in lines[1:]:
        if ':' in l:
            k, v = l.split(':', 1)
            headers[k.strip().lower()] = v.strip()
    need = int(headers.get('content-length', '0') or 0)
    if need > 16 << 20:
        return None
    while len(body) < need:
        chunk = conn.recv(65536)
        if not chunk:
            break
        body += chunk
    return method, path, headers, body


def respond(conn, status, origin, ctype='application/json', body=b'', extra=''):
    h = 'HTTP/1.1 %s\r\nContent-Type: %s\r\nCache-Control: no-store\r\nConnection: close\r\n' % (status, ctype)
    if origin:
        h += 'Access-Control-Allow-Origin: %s\r\nVary: Origin\r\n' % origin
    h += extra
    if body is not None:
        h += 'Content-Length: %d\r\n' % len(body)
    conn.sendall(h.encode() + b'\r\n' + (body or b''))


def handle(conn):
    """Returns True when the helper should quit: after every request except the
    browser's pre-check (OPTIONS), which is always followed by the real request."""
    req = read_request(conn)
    if not req:
        return True
    method, path, headers, body = req
    origin = headers.get('origin', '')
    ok_origin = origin if ALLOWED_ORIGINS.match(origin or '') else ''
    path = path.split('?')[0]
    if method == 'OPTIONS':
        respond(conn, '204 No Content', ok_origin, extra='Access-Control-Allow-Methods: POST\r\nAccess-Control-Allow-Headers: content-type\r\nAccess-Control-Allow-Private-Network: true\r\nAccess-Control-Max-Age: 600\r\n')
        return False
    if not ok_origin:
        respond(conn, '403 Forbidden', '', body=b'{"error":"Not allowed from here"}')
        return True
    try:
        job = json.loads(body.decode('utf-8') or '{}')
    except Exception:
        respond(conn, '400 Bad Request', ok_origin, body=b'{"error":"Bad request"}')
        return True
    if method == 'POST' and path == '/feed':
        try:
            out = read_feed(str(job.get('url', '')).strip())
            respond(conn, '200 OK', ok_origin, body=json.dumps(out).encode())
        except Exception as e:
            respond(conn, '502 Bad Gateway', ok_origin, body=json.dumps({'error': str(e) or 'Could not load feed'}).encode())
        return True
    if method == 'POST' and path == '/run':
        # stream one JSON object per line, so the page shows progress and fills as feeds arrive
        respond(conn, '200 OK', ok_origin, ctype='application/x-ndjson', body=None)

        def emit(obj):
            try:
                conn.sendall((json.dumps(obj) + '\n').encode())
            except Exception:
                pass
        try:
            res = run(job, emit)
            emit(dict(res, type='done'))
        except Exception as e:
            log('run failed', e)
            emit({'type': 'done', 'stories': [], 'error': str(e)})
        return True
    respond(conn, '404 Not Found', ok_origin, body=b'{"error":"Unknown"}')
    return True


def launchd_socket():
    """The listening socket macOS opened for us (None when started by hand)."""
    try:
        lib = ctypes.CDLL('/usr/lib/libSystem.dylib')
        fds = ctypes.POINTER(ctypes.c_int)()
        cnt = ctypes.c_size_t(0)
        if lib.launch_activate_socket(b'Listener', ctypes.byref(fds), ctypes.byref(cnt)) != 0 or cnt.value < 1:
            return None
        return socket.socket(fileno=fds[0])
    except Exception:
        return None


def main():
    once = True
    srv = launchd_socket()
    if srv is None:
        # started by hand for testing: listen ourselves and keep serving
        once = '--once' in sys.argv
        srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        port = int(sys.argv[sys.argv.index('--port') + 1]) if '--port' in sys.argv else PORT
        srv.bind(('127.0.0.1', port))
        srv.listen(8)
    log('started', 'by hand' if '--port' in sys.argv else 'by macOS')
    while True:
        conn, _ = srv.accept()
        conn.settimeout(None)
        try:
            finished = handle(conn)
        except Exception as e:
            log('request failed', e)
            finished = True
        finally:
            try:
                conn.shutdown(socket.SHUT_RDWR)
            except Exception:
                pass
            conn.close()
        if finished and once:
            log('answered, quitting')
            return


if __name__ == '__main__':
    main()
