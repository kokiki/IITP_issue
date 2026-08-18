# 외부 PC에서 실행하기

1. `LocalOCRQwen` 폴더 전체를 외부 PC로 복사합니다.
2. 폴더 안의 `LocalOCRQwen.exe`를 더블클릭합니다.
3. 별도 터미널 명령 없이 PaddleOCR, llama-server, 웹앱이 자동으로 시작되고 브라우저가 열립니다.

## 폴더 구성

- `LocalOCRQwen.exe`: 자동 실행 프로그램
- `models/paddleocr`: PaddleOCR 로컬 모델
- `models/slm/Qwen3-1.7B-Q8_0.gguf`: Qwen 로컬 모델
- `tools/llama`: llama-server와 필요한 DLL
- `tools/node`: XLSX 저장용 Node.js와 로컬 패키지
- `templates`: 웹 화면

## 사용 방법

웹 화면에서 파일을 최대 10개 선택하고 `분석 시작`을 누릅니다. OCR 원문과 중간 JSON은 화면에 노출하지 않고 최종 판정표와 점수만 표시합니다.

포트는 실행할 때 자동으로 선택하므로 다른 프로그램이 사용하는 포트가 있어도 실행할 수 있습니다. 모든 OCR과 Qwen 분석은 외부 API 없이 로컬에서 실행됩니다.

## 배포 시 주의

`LocalOCRQwen.exe`만 따로 복사하지 말고, `LocalOCRQwen` 폴더 전체를 복사해야 합니다. 모델과 llama-server가 폴더 안에 포함되어 있어 배포 폴더의 용량이 큽니다.
