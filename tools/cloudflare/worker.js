// goodlandlord-photos: photos attached to repair requests, in the private R2 bucket "goodlandlord-photos".
// Deployed by tools/cloudflare/deploy.py (wrangler). Address: https://goodlandlord-photos.<subdomain>.workers.dev/
//
// The photos are inside people's homes, so NOTHING here is public: every request needs a link the Anvil app signed
// (it signs only for the landlord and the tenant of that tenancy). Records are permanent, so a file is never
// overwritten; DELETE exists only for uploads that were never attached to a record (and the app's own clean-up).
//
//   GET/HEAD /<key>?exp&sig          the photo (cached privately for an hour; links are bucketed per hour by the app)
//   GET      /<key>?meta=1&exp&sig   {ok, size, type, sha256}: the app checks an upload arrived and seals its SHA-256
//   PUT      /<key>?max&exp&sig      the browser uploads one photo with a link the app signed (photo_tickets)
//   DELETE   /<key>?exp&sig          remove an unattached upload (signed by the app)
//
// Signing: sig = hex HMAC-SHA256(SIGNING_KEY, METHOD \n key \n exp \n extra), METHOD = GET | META | PUT | DELETE,
// extra = max for PUT, empty otherwise; exp = unix time the link stops working. SIGNING_KEY is a Worker secret; the
// Anvil app has the same value in its App Secret "cloudflare_photos" (https://<SIGNING_KEY>@goodlandlord-photos.<sub>.workers.dev).

const CORS = {
  'Access-Control-Allow-Origin': '*',
  'Access-Control-Allow-Methods': 'GET, HEAD, PUT, OPTIONS',
  'Access-Control-Allow-Headers': 'Content-Type',
  'Access-Control-Expose-Headers': 'Content-Length, ETag, Content-Type',
};
const KEY_RE = /^gl\/[0-9a-z]{1,40}\/[0-9a-f]{24,64}$/;
const TYPES = ['image/jpeg', 'image/png', 'image/webp'];

function json(status, body) {
  return new Response(JSON.stringify(body), { status, headers: { ...CORS, 'Content-Type': 'application/json', 'Cache-Control': 'no-store' } });
}

function hex(buf) {
  return [...new Uint8Array(buf)].map((b) => b.toString(16).padStart(2, '0')).join('');
}

async function hmac(secret, text) {
  const k = await crypto.subtle.importKey('raw', new TextEncoder().encode(secret), { name: 'HMAC', hash: 'SHA-256' }, false, ['sign']);
  return hex(await crypto.subtle.sign('HMAC', k, new TextEncoder().encode(text)));
}

function same(a, b) {
  if (typeof a !== 'string' || typeof b !== 'string' || a.length !== b.length) return false;
  let d = 0;
  for (let i = 0; i < a.length; i++) d |= a.charCodeAt(i) ^ b.charCodeAt(i);
  return d === 0;
}

async function signed(env, method, key, q, extra) {
  const exp = Number(q.get('exp') || 0);
  if (!env.SIGNING_KEY || !exp || exp < Date.now() / 1000) return false;
  return same(await hmac(env.SIGNING_KEY, [method, key, String(exp), extra || ''].join('\n')), q.get('sig') || '');
}

async function readCapped(body, max) {
  // the whole body, or null when it is bigger than max (Content-Length can be missing or wrong)
  const reader = body.getReader();
  const parts = [];
  let n = 0;
  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    n += value.length;
    if (n > max) { try { await reader.cancel(); } catch (e) { /* ignore */ } return null; }
    parts.push(value);
  }
  const out = new Uint8Array(n);
  let at = 0;
  for (const p of parts) { out.set(p, at); at += p.length; }
  return out;
}

export default {
  async fetch(request, env) {
    if (request.method === 'OPTIONS') {
      return new Response(null, { status: 204, headers: { ...CORS, 'Access-Control-Max-Age': '86400' } });
    }
    const url = new URL(request.url);
    const key = decodeURIComponent(url.pathname.slice(1));
    if (!KEY_RE.test(key)) return new Response('Not found', { status: 404, headers: CORS });
    const q = url.searchParams;

    if (request.method === 'GET' && q.has('meta')) {
      if (!(await signed(env, 'META', key, q))) return json(403, { ok: false, error: 'This link has expired.' });
      const obj = await env.PHOTOS.head(key);
      return obj ? json(200, { ok: true, size: obj.size, type: (obj.httpMetadata || {}).contentType || '',
                               sha256: (obj.customMetadata || {}).sha256 || '' })
                 : json(404, { ok: false });
    }

    if (request.method === 'GET' || request.method === 'HEAD') {
      if (!(await signed(env, 'GET', key, q))) return new Response('This photo link has expired. Reload the page.', { status: 403, headers: CORS });
      const obj = request.method === 'HEAD' ? await env.PHOTOS.head(key) : await env.PHOTOS.get(key);
      if (!obj) return new Response('Not found', { status: 404, headers: CORS });
      const headers = new Headers(CORS);
      obj.writeHttpMetadata(headers);
      headers.set('ETag', obj.httpEtag);
      headers.set('Cache-Control', 'private, max-age=3600');
      headers.set('X-Content-Type-Options', 'nosniff');
      headers.set('Content-Length', String(obj.size));
      return new Response(request.method === 'HEAD' ? null : obj.body, { status: 200, headers });
    }

    if (request.method === 'PUT') {
      const max = Number(q.get('max') || 0);
      if (!(await signed(env, 'PUT', key, q, String(max)))) return json(403, { ok: false, error: 'This upload link has expired. Please try again.' });
      const type = (request.headers.get('Content-Type') || '').split(';')[0].trim().toLowerCase();
      if (!TYPES.includes(type)) return json(415, { ok: false, error: 'Only photos (JPEG, PNG or WebP) can be added.' });
      if (Number(request.headers.get('Content-Length') || 0) > max) return json(413, { ok: false, error: 'That photo is too big.' });
      if (await env.PHOTOS.head(key)) return json(409, { ok: false, error: 'This photo is already uploaded.' });  // never overwrite
      const body = await readCapped(request.body, max);
      if (body === null) return json(413, { ok: false, error: 'That photo is too big.' });
      const sha256 = hex(await crypto.subtle.digest('SHA-256', body));
      await env.PHOTOS.put(key, body, { httpMetadata: { contentType: type }, customMetadata: { sha256 } });
      return json(200, { ok: true, key, size: body.length, type, sha256 });
    }

    if (request.method === 'DELETE') {
      if (!(await signed(env, 'DELETE', key, q))) return json(403, { ok: false, error: 'This link has expired.' });
      await env.PHOTOS.delete(key);
      return json(200, { ok: true });
    }
    return new Response('Method not allowed', { status: 405, headers: CORS });
  },
};
