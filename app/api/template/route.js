import { parse, blocksToMarkdown } from 'kordoc';

export const runtime = 'nodejs';

const MAX_FILE_BYTES = 25 * 1024 * 1024;
const SUPPORTED_EXTENSIONS = new Set(['.hwp', '.hwpx', '.docx', '.pdf', '.xlsx', '.xls']);

function json(data, status = 200) {
  return new Response(JSON.stringify(data), { status, headers: { 'content-type': 'application/json; charset=utf-8' } });
}

function extensionOf(filename) { return `.${filename.split('.').pop()?.toLowerCase() || ''}`; }

function compactStructure(blocks = []) {
  return blocks.slice(0, 120).map((block) => ({
    type: block?.type || 'text',
    text: typeof block?.text === 'string' ? block.text.slice(0, 500) : undefined,
    level: block?.level,
    pageNumber: block?.pageNumber,
    rows: block?.rows,
    cols: block?.cols
  })).filter((block) => block.text || block.type === 'table');
}

export async function POST(request) {
  let filename = '업로드 파일';
  try {
    const form = await request.formData();
    const file = form.get('file');
    if (!file || typeof file.arrayBuffer !== 'function') return json({ error: '분석할 파일을 선택해 주세요.' }, 400);
    filename = file.name || filename;
    const extension = extensionOf(filename);
    if (!SUPPORTED_EXTENSIONS.has(extension)) return json({ error: `지원하지 않는 파일 형식입니다: ${extension || '확장자 없음'}. HWP, HWPX, DOCX, PDF, XLSX, XLS만 업로드할 수 있습니다.` }, 415);
    if (file.size > MAX_FILE_BYTES) return json({ error: '파일 크기가 25MB를 초과했습니다. 더 작은 파일을 업로드해 주세요.' }, 413);
    const buffer = Buffer.from(await file.arrayBuffer());
    const result = await parse(buffer);
    if (!result?.success) {
      const reason = result?.error?.message || result?.error || result?.code || '문서 구조를 읽지 못했습니다.';
      return json({ error: `${filename} 분석 실패: ${reason}`, filename, extension }, 422);
    }
    const markdown = String(result.markdown || blocksToMarkdown(result.blocks || []) || '').slice(0, 120000);
    if (!markdown.trim()) return json({ error: `${filename} 분석 실패: 문서에서 읽을 수 있는 텍스트나 표를 찾지 못했습니다.`, filename, extension }, 422);
    return json({
      success: true,
      template: {
        filename,
        extension,
        status: '분석 완료',
        markdown,
        structure: compactStructure(result.blocks),
        metadata: { title: result.metadata?.title || filename, pageCount: result.metadata?.pageCount, pageMode: result.metadata?.pageMode }
      }
    });
  } catch (error) {
    const reason = error?.message || '알 수 없는 오류';
    return json({ error: `${filename} 분석 실패: ${reason}`, filename }, 422);
  }
}
