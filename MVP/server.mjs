import http from 'node:http';
import { readFile } from 'node:fs/promises';

const files = new Map([
  ['/', ['index.html', 'text/html; charset=utf-8']],
  ['/styles.css', ['styles.css', 'text/css; charset=utf-8']],
  ['/app.js', ['app.js', 'text/javascript; charset=utf-8']],
  ['/analysis.js', ['analysis.js', 'text/javascript; charset=utf-8']],
]);
const port = Number(process.env.PORT ?? 3040);
if (!Number.isInteger(port) || port < 1 || port > 65535) throw new Error('Invalid PORT');

http.createServer(async (request, response) => {
  response.setHeader('X-Content-Type-Options', 'nosniff');
  response.setHeader('Cache-Control', 'no-store');
  response.setHeader('Content-Security-Policy', "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'");
  if (request.method !== 'GET') {
    response.writeHead(405).end('Method not allowed');
    return;
  }
  const pathname = new URL(request.url ?? '/', 'http://127.0.0.1').pathname;
  if (pathname === '/api/nasa/power') {
    try {
      const url = new URL('https://power.larc.nasa.gov/api/temporal/monthly/point');
      url.search = new URLSearchParams({
        parameters: 'T2M',
        community: 'SB',
        longitude: '11.52',
        latitude: '3.87',
        format: 'JSON',
        start: '2005',
        end: '2024',
      }).toString();
      const upstream = await fetch(url, { signal: AbortSignal.timeout(15000) });
      if (!upstream.ok) throw new Error(`NASA POWER responded with HTTP ${upstream.status}`);
      const payload = await upstream.json();
      response.writeHead(200, { 'Content-Type': 'application/json; charset=utf-8' }).end(JSON.stringify(payload));
    } catch (error) {
      console.error('Unable to retrieve NASA POWER data', error);
      response.writeHead(502, { 'Content-Type': 'application/json; charset=utf-8' })
        .end(JSON.stringify({ error: 'NASA POWER data could not be retrieved. Try again later.' }));
    }
    return;
  }
  const file = files.get(pathname);
  if (!file) {
    response.writeHead(404).end('Not found');
    return;
  }
  try {
    const content = await readFile(new URL(`./public/${file[0]}`, import.meta.url));
    response.writeHead(200, { 'Content-Type': file[1] }).end(content);
  } catch (error) {
    console.error('Unable to serve prototype file', error);
    response.writeHead(500).end('Unable to serve prototype');
  }
}).listen(port, '127.0.0.1', () => {
  console.log(`Geo Intelligence prototype: http://localhost:${port}`);
});
