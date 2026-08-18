# Briefly · 이슈 대응 보고서 초안 생성기

키워드·뉴스 본문과 검색 조건을 바탕으로 이슈 대응 보고서 초안을 만들고, OpenAI Web Search와 Gemini Google Search 결과를 별도로 보여주는 Node.js 웹 앱입니다. HWP/HWPX/DOCX/PDF/XLSX/XLS 양식 파일을 분석해 보고서 프롬프트에 반영할 수 있습니다.

## 실행

```bash
npm install
npm run dev
```

브라우저에서 `http://localhost:4173`을 엽니다. Node.js 20 이상이 필요합니다.

## 기능

- OpenAI Web Search 및 Gemini Google Search Grounding 병렬 요청
- 검색 기간·소스 유형 반영
- 출처 URL 정리·중복 제거·최대 20개 표시
- 생성 결과 영역에서 공문서 보고서 형식의 이슈보고서를 HWPX 파일로 다운로드
- HWP, HWPX, DOCX, PDF, XLSX, XLS 양식 분석
- API 키는 현재 브라우저 세션의 `sessionStorage`에만 저장
- API Route Handler는 Node.js 런타임을 사용하며 요청 제한시간은 120초

## 환경변수

`.env.example`을 참고하세요. 현재 API 키 입력은 웹 UI에서 이루어지고, 실제 키는 커밋하지 마세요. `.env*` 파일은 Git에서 제외됩니다.

## 빌드 확인

```bash
npm run build
```

현재 프로젝트는 별도 번들러 없이 Node.js Route Handler와 정적 프론트엔드로 구성되어 `build` 단계에서 모든 JavaScript 진입점의 문법을 검증합니다.
