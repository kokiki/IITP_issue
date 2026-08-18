# 적격성 검토 보고서 프로젝트

PaddleOCR로 업로드된 문서를 OCR 처리하고, 로컬 Qwen JSON 추출 결과를 기존 판별 로직으로 검증하는 Flask 프로젝트입니다.

## 실행

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
set PORT=54451
python app.py
```

브라우저에서 `http://127.0.0.1:54451`을 엽니다. Qwen 연동을 사용하려면 별도의 로컬 llama-server가 필요합니다.

`서류샘플/`에는 실제 검토용 샘플 이미지가 포함되어 있고, `test_integrated.py`는 샘플 전체를 한 번에 업로드해 진행률·판별 결과·XLSX 다운로드를 검증합니다.
