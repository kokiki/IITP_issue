import { POST } from '../app/api/export/route.js';

export default async function handler(request, response) {
  try {
    const chunks = [];
    for await (const chunk of request) chunks.push(chunk);
    const result = await POST(new Request(`https://${request.headers.host || 'vercel.local'}${request.url}`, {
      method: 'POST',
      headers: { 'content-type': request.headers['content-type'] || 'application/json' },
      body: Buffer.concat(chunks)
    }));
    response.writeHead(result.status, Object.fromEntries(result.headers));
    response.end(Buffer.from(await result.arrayBuffer()));
  } catch {
    response.statusCode = 500;
    response.end(JSON.stringify({ error: 'HWPX 생성 요청을 처리하지 못했습니다.' }));
  }
}
