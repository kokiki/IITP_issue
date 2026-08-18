import re
from pathlib import Path

import requests
from bs4 import BeautifulSoup


base = "http://127.0.0.1:54451/"
path = Path("서류샘플/1. 과제수행결과 우수여부.png")
with path.open("rb") as handle:
    ocr_response = requests.post(
        base,
        files={"files": (path.name, handle, "image/png")},
        data={"researcher_name": "김용성", "organization": "충남대학교"},
        timeout=180,
    )
print("OCR_POST", ocr_response.status_code)
match = re.search(r'name="analysis_id" value="([^"]+)"', ocr_response.text)
print("ANALYSIS_ID", bool(match))
qwen_response = requests.post(
    base + "analyze", data={"analysis_id": match.group(1)}, timeout=300
)
print("QWEN_POST", qwen_response.status_code)
soup = BeautifulSoup(qwen_response.text, "html.parser")
comparison = soup.select_one(".comparison")
print("COMPARISON_PRESENT", comparison is not None)
print(comparison.get_text(" ", strip=True) if comparison else "")
Path("task1_response.html").write_text(qwen_response.text, encoding="utf-8")
