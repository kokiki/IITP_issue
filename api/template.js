import { POST } from '../app/api/template/route.js';

export const config = { api: { bodyParser: false } };

async function readBody(request) {
  const chunks = [];
  for await (const chunk of request) chunks.push(chunk);
  return Buffer.concat(chunks);
}

export default async function handler(request, response) {
  try {
    const body = await readBody(request);
    const result = await POST(new Request(`https://${request.headers.host || 'vercel.local'}${request.url}`, {
      method: 'POST',
      headers: { 'content-type': request.headers['content-type'] || 'multipart/form-data' },
      body
    }));
    response.writeHead(result.status, Object.fromEntries(result.headers));
    response.end(await result.text());
  } catch {
    response.statusCode = 500;
    response.end(JSON.stringify({ error: '양식 분석 요청을 처리하지 못했습니다.' }));
  }
}
