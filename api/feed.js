// GET /api/feed?url=<site or feed url>
// Fetches a feed server side (browsers can't, because of CORS), finds the feed
// when given a website, and returns it as plain JSON.
const { XMLParser } = require('fast-xml-parser');

const UA = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130 Safari/537.36 BrainFodder/1.0';
const MAX_BYTES = 8 * 1024 * 1024;
const MAX_ITEMS = 60;
const FALLBACK_PATHS = ['/feed', '/rss', '/feed.xml', '/rss.xml', '/atom.xml', '/index.xml', '/feed/'];

async function get(url) {
  const ctrl = new AbortController();
  const timer = setTimeout(() => ctrl.abort(), 9000);
  try {
    const r = await fetch(url, {
      headers: { 'user-agent': UA, accept: 'application/rss+xml, application/atom+xml, application/xml;q=0.9, text/xml;q=0.9, text/html;q=0.8, */*;q=0.5' },
      redirect: 'follow',
      signal: ctrl.signal,
    });
    if (!r.ok) throw new Error('HTTP ' + r.status);
    const buf = await r.arrayBuffer();
    if (buf.byteLength > MAX_BYTES) throw new Error('Feed too large');
    let text = new TextDecoder('utf-8').decode(buf);
    const enc = text.slice(0, 300).match(/encoding=["']([\w-]+)["']/i);
    if (enc && !/utf-?8/i.test(enc[1])) {
      try { text = new TextDecoder(enc[1]).decode(buf); } catch (_) {}
    }
    return { text, url: r.url || url };
  } catch (e) {
    if (e.name === 'AbortError') throw new Error('Timed out');
    throw e;
  } finally {
    clearTimeout(timer);
  }
}

const isFeed = (s) => /<(rss|feed|rdf:RDF)[\s>]/i.test(s.slice(0, 8000));

const ENT = { amp: '&', lt: '<', gt: '>', quot: '"', apos: "'", nbsp: ' ', hellip: '…', mdash: '-', ndash: '-', rsquo: '’', lsquo: '‘', rdquo: '”', ldquo: '“' };
function decode(s) {
  return s.replace(/&(#x[0-9a-f]+|#\d+|[a-z]+);/gi, (m, e) => {
    if (e[0] === '#') {
      const n = e[1] === 'x' || e[1] === 'X' ? parseInt(e.slice(2), 16) : parseInt(e.slice(1), 10);
      try { return String.fromCodePoint(n); } catch (_) { return m; }
    }
    return ENT[e.toLowerCase()] ?? m;
  });
}
const plain = (html) => decode(String(html || '').replace(/<[^>]*>/g, ' ')).replace(/\s+/g, ' ').trim();

function discover(html, base) {
  const tags = html.match(/<link\b[^>]*>/gi) || [];
  const found = [];
  for (const tag of tags) {
    if (!/rel=["']?[^"'>]*alternate/i.test(tag)) continue;
    if (!/type=["']?application\/(rss|atom|feed)\+xml/i.test(tag)) continue;
    const h = tag.match(/href=["']([^"']+)["']/i);
    if (!h) continue;
    const title = (tag.match(/title=["']([^"']*)["']/i) || [])[1] || '';
    found.push({ href: new URL(decode(h[1]), base).href, comments: /comment/i.test(title + h[1]) });
  }
  const best = found.find((f) => !f.comments) || found[0];
  return best ? best.href : null;
}

const parser = new XMLParser({
  ignoreAttributes: false,
  attributeNamePrefix: '@_',
  textNodeName: '#text',
  processEntities: true,
  htmlEntities: true,
  trimValues: true,
  isArray: (name) => ['item', 'entry', 'link'].includes(name),
});

function txt(v) {
  if (v == null) return '';
  if (typeof v === 'string' || typeof v === 'number') return String(v);
  if (Array.isArray(v)) return txt(v[0]);
  if (typeof v === 'object') {
    if ('#text' in v) return String(v['#text']);
    if ('name' in v) return txt(v.name);
  }
  return '';
}

function atomLink(links) {
  if (!links) return '';
  const list = Array.isArray(links) ? links : [links];
  const pick = list.find((l) => typeof l === 'object' && (!l['@_rel'] || l['@_rel'] === 'alternate')) || list[0];
  return typeof pick === 'object' ? pick['@_href'] || '' : txt(pick);
}

function rssLink(links) {
  const list = Array.isArray(links) ? links : [links];
  for (const l of list) {
    if (typeof l === 'string' && l) return l;
    if (l && typeof l === 'object' && l['@_href']) return l['@_href'];
    if (l && typeof l === 'object' && l['#text']) return l['#text'];
  }
  return '';
}

// YouTube (and other media feeds) put the description and thumbnail in media:group
function mediaContent(e, link) {
  const g = e['media:group'];
  if (!g) return '';
  const th = g['media:thumbnail'];
  const thumb = th && (Array.isArray(th) ? th[0] : th)['@_url'];
  const desc = txt(g['media:description']).replace(/[&<>]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;' }[c]));
  return (thumb ? `<p><a href="${link}"><img src="${thumb}" alt=""></a></p>` : '') + (desc ? `<p>${desc.replace(/\n/g, '<br>')}</p>` : '');
}

function iso(s) {
  if (!s) return null;
  const d = new Date(txt(s));
  return isNaN(d) ? null : d.toISOString();
}

function abs(u, base) {
  try { return u ? new URL(u, base).href : ''; } catch (_) { return u || ''; }
}

function item({ guid, title, link, author, date, content }, base) {
  content = String(content || '');
  if (content.length > 200000) content = content.slice(0, 200000);
  const t = plain(title) || plain(content).slice(0, 90) || '(untitled)';
  return {
    guid: String(guid || link || t),
    title: t,
    link: abs(link, base),
    author: plain(author),
    date: iso(date),
    content,
    snippet: plain(content).slice(0, 220),
  };
}

function parse(xml, feedUrl) {
  const doc = parser.parse(xml);
  if (doc.rss || doc['rdf:RDF']) {
    const root = doc.rss || doc['rdf:RDF'];
    const ch = Array.isArray(root.channel) ? root.channel[0] : root.channel || {};
    const raw = root.item || ch.item || [];
    const siteUrl = abs(rssLink(ch.link), feedUrl);
    return {
      title: plain(txt(ch.title)),
      siteUrl,
      items: raw.slice(0, MAX_ITEMS).map((i) => item({
        guid: txt(i.guid) || i['@_rdf:about'],
        title: txt(i.title),
        link: rssLink(i.link) || (txt(i.guid).startsWith('http') ? txt(i.guid) : ''),
        author: txt(i['dc:creator']) || txt(i.author),
        date: i.pubDate || i['dc:date'] || i.published || i.updated,
        content: txt(i['content:encoded']) || txt(i.description),
      }, siteUrl || feedUrl)),
    };
  }
  if (doc.feed) {
    const f = doc.feed;
    const siteUrl = abs(atomLink(f.link), feedUrl);
    return {
      title: plain(txt(f.title)),
      siteUrl,
      items: (f.entry || [])
        .slice(0, MAX_ITEMS)
        .map((e) => {
          const it = item({
            guid: txt(e.id),
            title: txt(e.title),
            link: atomLink(e.link),
            author: txt(e.author),
            date: e.published || e.updated,
            content: txt(e.content) || txt(e.summary) || mediaContent(e, atomLink(e.link)),
          }, siteUrl || feedUrl);
          // YouTube entries carry the video id; Shorts link to /shorts/
          const vid = txt(e['yt:videoId']);
          if (vid) it.yt = { id: vid, short: /youtube\.com\/shorts\//.test(it.link) };
          return it;
        }),
    };
  }
  throw new Error('Not a feed');
}

async function resolve(url) {
  let r = await get(url);
  if (isFeed(r.text)) return r;
  const found = discover(r.text, r.url);
  if (found) {
    const f = await get(found).catch(() => null);
    if (f && isFeed(f.text)) return { text: f.text, url: found };
  }
  const origin = new URL(r.url).origin;
  for (const p of FALLBACK_PATHS) {
    const f = await get(origin + p).catch(() => null);
    if (f && isFeed(f.text)) return { text: f.text, url: origin + p };
  }
  throw new Error('No feed found at that address');
}

module.exports = async (req, res) => {
  let url = String(req.query.url || '').trim();
  if (url && !/^https?:\/\//i.test(url)) url = 'https://' + url;
  let parsed;
  try { parsed = new URL(url); } catch (_) {}
  if (!parsed || !/^https?:$/.test(parsed.protocol)) {
    res.status(400).json({ error: 'Give a website or feed address' });
    return;
  }
  try {
    const r = await resolve(parsed.href);
    const feed = parse(r.text, r.url);
    res.setHeader('Cache-Control', 's-maxage=900, stale-while-revalidate=3600');
    res.status(200).json({ feedUrl: r.url, ...feed });
  } catch (e) {
    res.setHeader('Cache-Control', 'no-store');
    res.status(502).json({ error: e.message || 'Could not load feed' });
  }
};

module.exports._parse = parse;
module.exports._discover = discover;
