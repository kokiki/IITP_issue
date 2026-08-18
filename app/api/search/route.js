export const runtime = 'nodejs';

const REQUEST_TIMEOUT_MS = 120_000;
const MAX_SOURCES = 20;

const DOMAIN_MAP = {
  '정부·공공기관': ['korea.kr', 'go.kr', 'msit.go.kr', 'nia.or.kr', 'kisa.or.kr'],
  '연구·학술': ['arxiv.org', 'nature.com', 'science.org', 'sciencedirect.com', 'ncbi.nlm.nih.gov'],
  뉴스: ['yna.co.kr', 'reuters.com', 'bbc.com', 'apnews.com', 'nytimes.com'],
  기업: ['openai.com', 'google.com', 'microsoft.com', 'navercorp.com', 'kakaocorp.com'],
  국제기구: ['eur-lex.europa.eu', 'un.org', 'oecd.org', 'who.int', 'worldbank.org']
};

const SOURCE_LABELS = {
  '정부·공공기관': '정부·공공기관 공식 자료',
  '연구·학술': '연구·학술 원문',
  뉴스: '신뢰할 수 있는 뉴스 기사 원문',
  기업: '기업 공식 발표·기술 문서',
  국제기구: '국제기구 공식 보고서·정책 문서'
};

function json(data, status = 200) {
  return new Response(JSON.stringify(data), { status, headers: { 'content-type': 'application/json; charset=utf-8' } });
}

function cleanUrl(raw) {
  try {
    const url = new URL(raw);
    [...url.searchParams.keys()].forEach((key) => { if (/^(utm_|fbclid$|gclid$)/i.test(key)) url.searchParams.delete(key); });
    url.hash = '';
    url.pathname = url.pathname.replace(/\/+$/, '') || '/';
    return url.toString();
  } catch { return null; }
}

function collectUrls(value, urls = []) {
  if (!value || typeof value !== 'object') return urls;
  if (Array.isArray(value)) { value.forEach((item) => collectUrls(item, urls)); return urls; }
  Object.entries(value).forEach(([key, item]) => {
    if ((key === 'url' || key === 'uri') && typeof item === 'string') urls.push(item);
    else if (key === 'annotations' && Array.isArray(item)) item.forEach((annotation) => { if (annotation?.type === 'url_citation' && annotation.url) urls.push(annotation.url); collectUrls(annotation, urls); });
    else collectUrls(item, urls);
  });
  return urls;
}

function dedupeSources(items) {
  const seen = new Set();
  return items.map((item) => {
    const url = cleanUrl(typeof item === 'string' ? item : item.url || item.uri);
    if (!url) return null;
    const key = url.toLowerCase();
    if (seen.has(key)) return null;
    seen.add(key);
    return { url, title: typeof item === 'string' ? url : item.title || url };
  }).filter(Boolean).slice(0, MAX_SOURCES);
}

function getText(payload) {
  if (typeof payload?.output_text === 'string') return payload.output_text;
  const parts = [];
  collectText(payload?.output, parts);
  return parts.join('\n').trim();
}

function collectText(value, parts) {
  if (!value) return;
  if (Array.isArray(value)) { value.forEach((item) => collectText(item, parts)); return; }
  if (typeof value === 'object') {
    if (value.type === 'output_text' && typeof value.text === 'string') parts.push(value.text);
    else Object.values(value).forEach((item) => collectText(item, parts));
  }
}

function buildPrompt({ query, reportType, period, sources, templateMarkdown, templateFilename }) {
  const sourceInstruction = sources.length ? sources.map((source) => SOURCE_LABELS[source] || source).join(', ') : '선택된 소스 없음';
  const templateInstruction = templateMarkdown ? `\n\n업로드된 문서 양식(${templateFilename || '양식 파일'})을 보고서 구조의 기준으로 사용하라. 아래 Markdown의 제목·항목·문단 순서·표 구조를 최대한 유지하고, 새 보고서 내용은 해당 위치에 채워 넣어라. 양식에만 있는 결재란·작성일·부서·담당자 같은 메타 항목도 임의로 삭제하지 말고 빈칸 또는 [입력 필요]로 유지하라.\n\n[분석된 양식]\n${templateMarkdown.slice(0, 30000)}\n[/분석된 양식]` : '\n\n업로드된 양식은 없다. 기본 보고서 구조를 사용하라.';
  return `당신은 정책·이슈 대응 보고서 작성자다. 아래 주제를 ${period} 기간의 최신 공개 자료로 조사하라.\n\n주제 또는 기사 본문:\n${query}\n\n보고서 유형: ${reportType}\n검색 소스 유형: ${sourceInstruction}\n${templateInstruction}\n\n반드시 한국어 보고서 초안을 작성하라. 업로드 양식이 있으면 양식의 제목·항목·문단 순서를 최우선으로 따른다. 양식이 없으면 다음 형식을 사용한다: 제목, 핵심 요약, 현황, 문제점, 대응방향, 효과성, 시사점, 참고 출처. 각 항목은 4~5개의 짧은 문장으로 작성하고, 검색 결과에 근거한 문장 뒤에는 제공된 출처 번호를 [1], [2] 형태로 붙여라. 존재하지 않는 출처 번호를 만들지 마라. 마지막에는 '참고 출처' 제목 아래 [번호] 출처 제목 — URL 형식으로 정리하라.`;
}

async function fetchWithTimeout(url, options) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);
  try { return await fetch(url, { ...options, signal: controller.signal }); }
  finally { clearTimeout(timer); }
}

async function callOpenAI({ apiKey, prompt, allowedDomains }) {
  if (!apiKey) return { provider: 'openai', status: 'skipped', error: 'OpenAI API 키가 입력되지 않았습니다.' };
  try {
    const response = await fetchWithTimeout('https://api.openai.com/v1/responses', {
      method: 'POST', headers: { 'content-type': 'application/json', authorization: `Bearer ${apiKey}` },
      body: JSON.stringify({ model: 'gpt-5.6-luna', tools: [{ type: 'web_search', filters: allowedDomains.length ? { allowed_domains: allowedDomains } : undefined }], input: prompt })
    });
    const data = await response.json().catch(() => ({}));
    if (!response.ok) return { provider: 'openai', status: 'error', error: data?.error?.message || `OpenAI API 오류 (${response.status})` };
    const urls = dedupeSources(collectUrls(data));
    return { provider: 'openai', status: 'success', text: getText(data), sources: urls };
  } catch (error) { return { provider: 'openai', status: 'error', error: error.name === 'AbortError' ? 'OpenAI 요청 시간이 초과되었습니다(120초).' : 'OpenAI 요청 중 네트워크 오류가 발생했습니다.' }; }
}

async function callGemini({ apiKey, prompt }) {
  if (!apiKey) return { provider: 'gemini', status: 'skipped', error: 'Gemini API 키가 입력되지 않았습니다.' };
  try {
    const endpoint = `https://generativelanguage.googleapis.com/v1beta/models/gemini-3.5-flash-lite:generateContent?key=${encodeURIComponent(apiKey)}`;
    const response = await fetchWithTimeout(endpoint, {
      method: 'POST', headers: { 'content-type': 'application/json' },
      body: JSON.stringify({ contents: [{ role: 'user', parts: [{ text: prompt }] }], tools: [{ google_search: {} }] })
    });
    const data = await response.json().catch(() => ({}));
    if (!response.ok) return { provider: 'gemini', status: 'error', error: data?.error?.message || `Gemini API 오류 (${response.status})` };
    const text = data?.candidates?.[0]?.content?.parts?.map((part) => part.text || '').join('') || '';
    const chunks = data?.candidates?.[0]?.groundingMetadata?.groundingChunks || [];
    const sources = dedupeSources(chunks.map((chunk) => ({ url: chunk?.web?.uri, title: chunk?.web?.title })));
    return { provider: 'gemini', status: 'success', text, sources };
  } catch (error) { return { provider: 'gemini', status: 'error', error: error.name === 'AbortError' ? 'Gemini 요청 시간이 초과되었습니다(120초).' : 'Gemini 요청 중 네트워크 오류가 발생했습니다.' }; }
}

export async function POST(request) {
  try {
    const body = await request.json();
    const query = String(body.query || '').trim();
    const sources = Array.isArray(body.sources) ? body.sources.filter((source) => SOURCE_LABELS[source]) : [];
    if (!query) return json({ error: '키워드 또는 기사 본문을 입력해 주세요.' }, 400);
    const prompt = buildPrompt({ query, reportType: body.reportType || '보고용 1장 페이퍼', period: body.period || '최근 30일', sources, templateMarkdown: body.templateMarkdown, templateFilename: body.templateFilename });
    const allowedDomains = [...new Set(sources.flatMap((source) => DOMAIN_MAP[source] || []))];
    const [openai, gemini] = await Promise.all([
      callOpenAI({ apiKey: body.openaiKey, prompt, allowedDomains }),
      callGemini({ apiKey: body.geminiKey, prompt })
    ]);
    return json({ results: { openai, gemini }, meta: { maxSources: MAX_SOURCES, timeoutSeconds: REQUEST_TIMEOUT_MS / 1000 } });
  } catch (error) { return json({ error: '검색 요청을 처리하지 못했습니다. 입력값을 확인하고 다시 시도해 주세요.' }, 500); }
}
