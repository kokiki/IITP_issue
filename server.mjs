import { createServer } from 'node:http';
import { readFile } from 'node:fs/promises';
import { extname, join, normalize } from 'node:path';
import { fileURLToPath } from 'node:url';
import { POST } from './app/api/search/route.js';
import { POST as TEMPLATE_POST } from './app/api/template/route.js';
import { POST as EXPORT_POST } from './app/api/export/route.js';

const root = fileURLToPath(new URL('.', import.meta.url));
const port = Number(process.env.PORT || 4173);
const types = { '.html': 'text/html; charset=utf-8', '.js': 'text/javascript; charset=utf-8', '.css': 'text/css; charset=utf-8', '.json': 'application/json; charset=utf-8' };

createServer(async (request, response) => {
  try {
    if (request.url === '/api/search' && request.method === 'POST') {
      const chunks = [];
      for await (const chunk of request) chunks.push(chunk);
      const body = Buffer.concat(chunks).toString('utf8');
      const result = await POST(new Request(`http://${request.headers.host || 'localhost'}${request.url}`, { method: 'POST', headers: { 'content-type': request.headers['content-type'] || 'application/octet-stream' }, body }));
      response.writeHead(result.status, Object.fromEntries(result.headers));
      response.end(await result.text());
      return;
    }
    if (request.url === '/api/template' && request.method === 'POST') {
      const chunks = [];
      for await (const chunk of request) chunks.push(chunk);
      const body = Buffer.concat(chunks);
      const result = await TEMPLATE_POST(new Request(`http://${request.headers.host || 'localhost'}${request.url}`, { method: 'POST', headers: { 'content-type': request.headers['content-type'] || 'application/octet-stream' }, body }));
      response.writeHead(result.status, Object.fromEntries(result.headers));
      response.end(await result.text());
      return;
    }
    if (request.url === '/api/export' && request.method === 'POST') {
      const chunks = [];
      for await (const chunk of request) chunks.push(chunk);
      const body = Buffer.concat(chunks).toString('utf8');
      const result = await EXPORT_POST(new Request(`http://${request.headers.host || 'localhost'}${request.url}`, { method: 'POST', headers: { 'content-type': 'application/json' }, body }));
      response.writeHead(result.status, Object.fromEntries(result.headers));
      response.end(Buffer.from(await result.arrayBuffer()));
      return;
    }
    const requested = decodeURIComponent(new URL(request.url, 'http://localhost').pathname);
    const file = requested === '/' ? 'index.html' : requested.replace(/^\/+/, '');
    const safePath = normalize(join(root, file));
    if (!safePath.startsWith(normalize(root))) { response.writeHead(403); response.end('Forbidden'); return; }
    const content = await readFile(safePath);
    response.writeHead(200, { 'content-type': types[extname(safePath)] || 'application/octet-stream' });
    response.end(content);
  } catch { response.writeHead(404); response.end('Not found'); }
}).listen(port, () => console.log(`Briefly running at http://localhost:${port}`));
