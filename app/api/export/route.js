import { markdownToHwpx } from 'kordoc';

export const runtime = 'nodejs';

export async function POST(request) {
  try {
    const body = await request.json();
    const markdown = String(body.markdown || '').trim();
    if (!markdown) return new Response(JSON.stringify({ error: '내보낼 보고서 결과가 없습니다.' }), { status: 400, headers: { 'content-type': 'application/json; charset=utf-8' } });
    const output = await markdownToHwpx(markdown, {
      gongmun: {
        preset: '보고서',
        pageNumbers: true,
        endMark: false
      }
    });
    return new Response(Buffer.from(output), { status: 200, headers: { 'content-type': 'application/vnd.hancom.hwpx', 'content-disposition': 'attachment; filename="issue-report.hwpx"' } });
  } catch (error) {
    return new Response(JSON.stringify({ error: `HWPX 생성 실패: ${error?.message || '알 수 없는 오류'}` }), { status: 500, headers: { 'content-type': 'application/json; charset=utf-8' } });
  }
}
