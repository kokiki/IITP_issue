import fs from 'node:fs/promises';
import { markdownToHwpx } from 'kordoc';

const [inputPath, outputPath] = process.argv.slice(2);
if (!inputPath || !outputPath) throw new Error('Usage: node hwpx_exporter.mjs input.json output.hwpx');

const data = JSON.parse(await fs.readFile(inputPath, 'utf8'));
const score = (value) => Number.isInteger(Number(value)) ? `${value}점` : `${Number(value || 0).toFixed(1)}점`;
const rows = data.rows || [];
const tableRows = rows.map((row) => `| ${row.item || ''} | ${row.status || ''} | ${score(row.score)} |`).join('\n');
const ocrAppendix = (data.ocr_results || []).map((item) => `### ${item.name || '파일'}\n\n${String(item.text || '').slice(0, 5000)}`).join('\n\n');
const qwenJson = JSON.stringify(data.qwen_result || {}, null, 2);
const markdown = `# 적격성 검토 요약보고서

## 검토 개요

- 연구책임자명: ${data.input_researcher || ''}
- 주관기관명: ${data.input_organization || ''}
- 접수마감일: ${data.deadline || ''}
- 판단기간: ${data.period_start || ''} ~ ${data.period_end || ''}
- 총 소요시간: ${Math.floor(Number(data.elapsed_seconds || 0) / 60)}분 ${Math.floor(Number(data.elapsed_seconds || 0) % 60)}초

## 우대사항 판별 결과

| 검토 항목 | 최종 판별 | 점수 |
| --- | --- | --- |
${tableRows}

**최종 점수 합계: ${score(data.score_total)}**

## 종합 의견

업로드된 증빙자료를 OCR로 확인하고 Qwen JSON 추출 결과와 기존 판별 기준을 적용해 항목별 결과를 산출했습니다. 세부 판정은 위 표의 항목별 결과와 점수를 기준으로 확인합니다.

## OCR 원문 부록

${ocrAppendix || 'OCR 원문이 없습니다.'}

## Qwen JSON 부록

\`\`\`json
${qwenJson}
\`\`\`
`;

const output = await markdownToHwpx(markdown, { gongmun: { preset: '보고서' } });
await fs.writeFile(outputPath, Buffer.from(output));
