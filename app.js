/* UI state is intentionally separate from the future API adapter. Replace generateDraft() with an OpenAI/Gemini request later. */
const state = { input: '', type: 'one-page', period: '30일', sources: ['정부·공공기관', '연구·학술', '뉴스'] };
const templateState = { filename: '', markdown: '', status: 'empty' };
const input = document.querySelector('#source-input');
const count = document.querySelector('#char-count');
const generateButton = document.querySelector('#generate-btn');
const reportTitle = document.querySelector('#report-title');
const reportSummary = document.querySelector('#report-summary');
const reportBlocks = document.querySelector('#report-blocks');
const reportBody = document.querySelector('#result-body');
const sourceList = document.querySelector('#source-list');
const providerResults = document.querySelector('#provider-results');
const providerGrid = document.querySelector('#provider-grid');
const openaiKeyInput = document.querySelector('#openai-key');
const geminiKeyInput = document.querySelector('#gemini-key');
const keyStatus = document.querySelector('#key-status');
const OPENAI_STORAGE_KEY = 'briefly.session.openaiKey';
const GEMINI_STORAGE_KEY = 'briefly.session.geminiKey';
const sourceCatalog = {
  '정부·공공기관': ['달라진 AI기본법, 우리에게 어떤 변화가 생길까? · 2026.07.17', 'https://www.korea.kr/news/policyNewsView.do?newsId=148968171'],
  '연구·학술': ['Generative AI regulation can learn from social media regulation · 2024.12.15', 'https://arxiv.org/abs/2412.11335'],
  '뉴스': ['[AI기본법] ② 규제냐 성장판이냐…AI산업 첫 시험대 · 2026.07.19', 'https://www.yna.co.kr/view/AKR20260717037800017'],
  기업: ['Responsible AI: Transparency and accountability · 2025.06.20', 'https://www.microsoft.com/en-us/ai/responsible-ai'],
  국제기구: ['Regulation (EU) 2024/1689 — Artificial Intelligence Act · 2024.06.13', 'https://eur-lex.europa.eu/eli/reg/2024/1689/oj?locale=en']
};
let lastProviderResults = null;
let lastReportMarkdown = '';
const templateFileInput = document.querySelector('#template-file');
const analyzeTemplateButton = document.querySelector('#analyze-template-btn');
const templateStatus = document.querySelector('#template-status');
const templatePreview = document.querySelector('#template-preview');
const templateFilename = document.querySelector('#template-filename');
const templateMarkdown = document.querySelector('#template-markdown');

function syncState() {
  state.input = input.value.trim();
  state.type = document.querySelector('input[name="report-type"]:checked').value;
  state.period = document.querySelector('#period').value;
  state.sources = [...document.querySelectorAll('#source-options input:checked')].map((item) => item.value);
}

function generateDraft(data) {
  const topic = data.input || '생성형 AI 규제 동향';
  const isStructured = data.type === 'status';
  const titleTopic = topic.length > 32 ? `${topic.slice(0, 32)}…` : topic;
  return {
    title: isStructured ? `${titleTopic}\n현황과 대응방향` : `${titleTopic}\n대응 방향`,
    summary: `${topic} 관련 최근 동향을 중심으로 핵심 맥락을 정리했다. ${data.sources.join(', ')} 자료를 바탕으로 주요 쟁점과 공공부문에서 우선 검토할 실행 과제를 도출할 필요가 있다.`,
    blocks: isStructured ? [
      ['01', '현황', `${data.period} 내 공개된 자료에서 관련 논의가 확대되고 있다.\n정책·산업 현장의 변화 속도가 빨라져 지속적인 모니터링이 필요한 상황이다.\n기관별로 대응 수준과 활용 사례에 차이가 나타나고 있다.\n공통 기준을 마련하기 위한 정책 협의가 필요한 시점이다.`],
      ['02', '문제점', '제도와 현장 적용 사이에 정보 격차가 있으며, 부처·기관별 대응 기준이 달라질 가능성이 있다.\n업무별 위험도와 데이터 품질을 판단할 공통 기준이 충분하지 않다.\n담당자 교육과 결과 검증 절차도 기관마다 다르게 운영될 수 있다.\n근거 자료와 책임 주체를 함께 정리해야 한다.'],
      ['03', '대응 방향', '① 핵심 지표 및 모니터링 주기를 설정한다.\n② 기관별 역할과 협업 체계를 정립한다.\n③ 시범 적용 후 성과와 위험을 함께 검증한다.\n④ 검증 결과를 바탕으로 운영 지침을 단계적으로 보완한다.']
    ] : [
      ['01', '현황', `${data.period} 기준 ${data.sources.slice(0, 2).join('·')} 자료를 종합하면, ${topic}에 대한 관심과 논의가 빠르게 확대되는 추세다.\n정책 변화와 산업 현장의 적용 사례가 동시에 늘고 있다.\n국내 공공부문에서도 업무 활용 가능성을 검토하는 움직임이 나타난다.\n향후 제도 변화에 맞춘 선제적인 점검이 필요하다.`],
      ['02', '핵심 포인트', '변화의 방향과 우리 조직에 미치는 영향을 분리해 판단해야 한다.\n단기 대응과 중장기 제도화 과제를 함께 관리하는 것이 중요하다.\n데이터 출처, 결과 검증, 책임 주체를 사전에 명확히 해야 한다.\n현장 담당자가 이해하고 실행할 수 있는 기준으로 구체화해야 한다.'],
      ['03', '대응 방향', '① 관련 동향을 정례적으로 모니터링한다.\n② 내부 영향과 잠재 리스크를 업무별로 점검한다.\n③ 이해관계자와 실행 가능한 후속 과제를 합의한다.\n④ 일정과 담당자를 지정해 다음 보고 시점까지 진행 상황을 확인한다.']
    ]
  };
}

function renderDraft(draft) {
  reportTitle.innerHTML = escapeHtml(draft.title).replace('\n', '<br />');
  reportSummary.textContent = draft.summary;
  reportBlocks.innerHTML = draft.blocks.map(([number, heading, copy]) => `<article class="${number === '03' ? 'direction' : ''}"><div class="block-number">${number}</div><div><h4>${heading}</h4><p>${escapeHtml(copy).replaceAll('\n', '<br />')}</p></div></article>`).join('');
  sourceList.innerHTML = state.sources.map((source) => { const [label, url] = sourceCatalog[source]; return `<a href="${url}" target="_blank" rel="noreferrer"><span class="source-type">${source}</span><span>${label} <b>↗</b></span></a>`; }).join('');
  document.querySelector('#source-count').textContent = `참고 소스 ${state.sources.length}개 · 최근 ${state.period}`;
  document.querySelector('#result-date').textContent = `${new Date().toLocaleDateString('ko-KR')} · 방금 생성됨`;
  document.querySelector('.result-status').innerHTML = '<i></i> 초안 생성 완료';
  const blocks = draft.blocks.map(([, heading, copy]) => `## ${heading}\n\n${copy}`).join('\n\n');
  lastReportMarkdown = `# ${draft.title.replace(/\n/g, ' ')}\n\n## 핵심 요약\n\n${draft.summary}\n\n${blocks}\n\n## 참고 출처\n\n${state.sources.map((source, index) => `[${index + 1}] ${sourceCatalog[source][0]} — ${sourceCatalog[source][1]}`).join('\n')}`;
  document.querySelector('#hwpx-btn').disabled = false;
}

function escapeHtml(value) { return value.replace(/[&<>'"]/g, (character) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;' }[character])); }

function setKeyStatus(message, tone = 'idle') {
  keyStatus.className = `key-status ${tone}`;
  keyStatus.innerHTML = `<span class="status-icon">${tone === 'error' ? '!' : tone === 'saved' ? '✓' : 'i'}</span><span>${message}</span>`;
}

function loadSessionKeys() {
  openaiKeyInput.value = sessionStorage.getItem(OPENAI_STORAGE_KEY) || '';
  geminiKeyInput.value = sessionStorage.getItem(GEMINI_STORAGE_KEY) || '';
  if (openaiKeyInput.value || geminiKeyInput.value) setKeyStatus('이 탭의 세션에서 API 키를 복원했습니다.', 'saved');
}

function saveSessionKeys() {
  const openaiKey = openaiKeyInput.value.trim();
  const geminiKey = geminiKeyInput.value.trim();
  if (!openaiKey && !geminiKey) {
    setKeyStatus('저장할 API 키가 없습니다. OpenAI 또는 Gemini 키를 하나 이상 입력해 주세요.', 'error');
    return;
  }
  if (openaiKey) sessionStorage.setItem(OPENAI_STORAGE_KEY, openaiKey); else sessionStorage.removeItem(OPENAI_STORAGE_KEY);
  if (geminiKey) sessionStorage.setItem(GEMINI_STORAGE_KEY, geminiKey); else sessionStorage.removeItem(GEMINI_STORAGE_KEY);
  setKeyStatus('API 키가 현재 탭의 세션에 저장되었습니다. 탭을 닫으면 삭제됩니다.', 'saved');
}

function clearSessionKeys() {
  sessionStorage.removeItem(OPENAI_STORAGE_KEY);
  sessionStorage.removeItem(GEMINI_STORAGE_KEY);
  openaiKeyInput.value = '';
  geminiKeyInput.value = '';
  setKeyStatus('세션을 비웠습니다. API 키가 삭제되었습니다.', 'cleared');
}

function resetContent() {
  input.value = '';
  input.dispatchEvent(new Event('input'));
  document.querySelector('input[name="report-type"][value="one-page"]').checked = true;
  document.querySelectorAll('.segment').forEach((item) => item.classList.toggle('active', item.querySelector('input').checked));
  document.querySelector('#period').value = '30일';
  document.querySelectorAll('#source-options input').forEach((checkbox, index) => { checkbox.checked = index < 3; checkbox.closest('.check').classList.toggle('selected', checkbox.checked); });
  syncState();
  renderDraft(generateDraft(state));
  providerResults.hidden = true;
  reportBody.hidden = false;
  document.querySelector('#hwpx-btn').disabled = false;
}

function setTemplateStatus(message, tone = 'idle') {
  templateStatus.className = `template-status ${tone}`;
  templateStatus.innerHTML = `<span class="status-icon">${tone === 'error' ? '!' : tone === 'success' ? '✓' : 'i'}</span><span>${message}</span>`;
}

async function analyzeTemplate() {
  const file = templateFileInput.files?.[0];
  if (!file) return;
  analyzeTemplateButton.disabled = true;
  analyzeTemplateButton.textContent = '분석 중…';
  templatePreview.hidden = true;
  setTemplateStatus(`${file.name}을(를) 분석하고 있습니다.`, 'loading');
  const formData = new FormData();
  formData.append('file', file, file.name);
  try {
    const response = await fetch('/api/template', { method: 'POST', body: formData });
    const data = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(data.error || '파일 분석에 실패했습니다.');
    templateState.filename = data.template.filename;
    templateState.markdown = data.template.markdown;
    templateState.status = 'success';
    templateFilename.textContent = data.template.filename;
    templateMarkdown.textContent = data.template.markdown.slice(0, 7000);
    templatePreview.hidden = false;
    setTemplateStatus(`${data.template.filename} · 분석 완료 · 보고서 생성 프롬프트에 반영됩니다.`, 'success');
  } catch (error) {
    templateState.filename = '';
    templateState.markdown = '';
    templateState.status = 'error';
    setTemplateStatus(error.message, 'error');
  } finally { analyzeTemplateButton.disabled = false; analyzeTemplateButton.textContent = '양식 분석하기'; }
}

function reportTypeLabel() { return document.querySelector('input[name="report-type"]:checked').value === 'status' ? '현황-문제점-대응방향' : '보고용 1장 페이퍼'; }

function renderProviderResults(results) {
  lastProviderResults = results;
  const successful = [results?.openai, results?.gemini].filter((result) => result?.status === 'success' && result.text);
  if (successful.length) {
    const sourceLines = successful.flatMap((result) => result.sources || []).filter((source, index, all) => all.findIndex((item) => item.url === source.url) === index);
    lastReportMarkdown = `# 이슈 대응 보고서\n\n${successful.map((result) => `## ${result.provider === 'openai' ? 'OpenAI 검색 결과' : 'Gemini 검색 결과'}\n\n${result.text}`).join('\n\n')}\n\n## 참고 출처\n\n${sourceLines.map((source, index) => `[${index + 1}] ${source.title} — ${source.url}`).join('\n')}`;
  } else {
    lastReportMarkdown = '';
  }
  const cards = [results?.openai, results?.gemini].map((result) => {
    const label = result?.provider === 'openai' ? 'OpenAI Web Search' : 'Gemini Google Search';
    const isSuccess = result?.status === 'success';
    const isSkipped = result?.status === 'skipped';
    const statusLabel = isSuccess ? '검색 완료' : isSkipped ? '키 미입력' : '검색 실패';
    const sourceMarkup = (result?.sources || []).map((source, index) => `<li><span>[${index + 1}]</span><a href="${source.url}" target="_blank" rel="noreferrer">${escapeHtml(source.title)} <b>↗</b></a></li>`).join('');
    const body = isSuccess ? `<div class="provider-copy">${escapeHtml(result.text || '검색 결과 본문이 없습니다.').replaceAll('\n', '<br />')}</div><div class="provider-sources"><h4>참고 출처 <small>${result.sources?.length || 0}개</small></h4><ol>${sourceMarkup || '<li class="no-source">검색된 URL 출처가 없습니다.</li>'}</ol></div>` : `<div class="provider-error"><strong>${isSkipped ? 'API 키가 필요합니다' : 'API 호출에 실패했습니다'}</strong><p>${escapeHtml(result?.error || '알 수 없는 오류가 발생했습니다.')}</p></div>`;
    return `<article class="provider-card ${isSuccess ? 'success' : 'failed'}"><div class="provider-card-head"><div><span class="provider-kicker">${result?.provider === 'openai' ? 'OPENAI' : 'GEMINI'}</span><h3>${label}</h3></div><span class="provider-status ${isSuccess ? 'ok' : 'bad'}"><i></i>${statusLabel}</span></div>${body}</article>`;
  }).join('');
  providerGrid.innerHTML = cards;
  reportBody.hidden = true;
  providerResults.hidden = false;
  document.querySelector('#hwpx-btn').disabled = !lastReportMarkdown;
}

async function downloadHwpx() {
  if (!lastReportMarkdown) { alert('먼저 이슈보고서 초안을 생성해 주세요.'); return; }
  try {
    const response = await fetch('/api/export', { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify({ markdown: lastReportMarkdown }) });
    if (!response.ok) { const data = await response.json().catch(() => ({})); throw new Error(data.error || 'HWPX 생성에 실패했습니다.'); }
    const blob = await response.blob();
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a'); link.href = url; link.download = '이슈보고서.hwpx'; link.click(); URL.revokeObjectURL(url);
  } catch (error) { alert(error.message); }
}

async function searchWithProviders() {
  syncState();
  const query = state.input;
  if (!query) { input.focus(); renderProviderResults({ openai: { provider: 'openai', status: 'error', error: '키워드 또는 기사 본문을 입력해 주세요.' }, gemini: { provider: 'gemini', status: 'error', error: '키워드 또는 기사 본문을 입력해 주세요.' } }); return; }
  generateButton.disabled = true;
  generateButton.querySelector('span:nth-child(2)').textContent = '두 검색엔진에 요청 중…';
  providerGrid.innerHTML = '<div class="provider-loading"><span class="loading-spinner"></span><p>OpenAI와 Gemini가 선택한 기간·소스를 검색하고 있습니다.</p><small>최대 120초까지 걸릴 수 있습니다.</small></div>';
  reportBody.hidden = true;
  providerResults.hidden = false;
  try {
    const response = await fetch('/api/search', { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify({ query, reportType: reportTypeLabel(), period: document.querySelector('#period').selectedOptions[0].textContent, sources: state.sources, templateFilename: templateState.filename, templateMarkdown: templateState.markdown, openaiKey: openaiKeyInput.value.trim(), geminiKey: geminiKeyInput.value.trim() }) });
    const data = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(data.error || '검색 요청을 처리하지 못했습니다.');
    renderProviderResults(data.results);
  } catch (error) {
    renderProviderResults({ openai: { provider: 'openai', status: 'error', error: error.message }, gemini: { provider: 'gemini', status: 'error', error: error.message } });
  } finally { generateButton.disabled = false; generateButton.querySelector('span:nth-child(2)').textContent = '보고서 초안 생성하기'; }
}

input.addEventListener('input', () => { count.textContent = input.value.length.toLocaleString('ko-KR'); });
document.querySelectorAll('input[name="report-type"]').forEach((radio) => radio.addEventListener('change', () => { document.querySelectorAll('.segment').forEach((item) => item.classList.toggle('active', item.querySelector('input').checked)); }));
document.querySelectorAll('#source-options input').forEach((checkbox) => checkbox.addEventListener('change', () => checkbox.closest('.check').classList.toggle('selected', checkbox.checked)));
document.querySelectorAll('.suggestion').forEach((button) => button.addEventListener('click', () => { input.value = button.dataset.fill; input.dispatchEvent(new Event('input')); input.focus(); }));
document.querySelectorAll('.key-input').forEach((keyInput) => keyInput.addEventListener('input', () => setKeyStatus('변경된 키가 있습니다. 세션 저장을 눌러 반영해 주세요.', 'idle')));
templateFileInput.addEventListener('change', () => { const file = templateFileInput.files?.[0]; analyzeTemplateButton.disabled = !file; if (file) { templateState.status = 'pending'; setTemplateStatus(`${file.name}이(가) 선택되었습니다. 양식 분석을 시작하세요.`, 'idle'); } });
analyzeTemplateButton.addEventListener('click', analyzeTemplate);
document.querySelector('#session-save-btn').addEventListener('click', saveSessionKeys);
document.querySelector('#session-clear-btn').addEventListener('click', clearSessionKeys);
document.querySelector('#content-reset-btn').addEventListener('click', resetContent);
generateButton.addEventListener('click', searchWithProviders);
document.querySelector('#copy-btn').addEventListener('click', async () => { await navigator.clipboard?.writeText(reportBody.innerText); const button = document.querySelector('#copy-btn'); button.textContent = '복사됨'; setTimeout(() => { button.textContent = '복사'; }, 1200); });
document.querySelector('#hwpx-btn').addEventListener('click', downloadHwpx);
document.querySelector('#refresh-btn').addEventListener('click', resetContent);
loadSessionKeys();
syncState();
renderDraft(generateDraft(state));
