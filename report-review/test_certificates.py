from pathlib import Path
import re

import requests
from bs4 import BeautifulSoup


base = "http://127.0.0.1:54451/"
paths = [
    Path("서류샘플/8. 직무발명보상 우수기업.png"),
    Path("서류샘플/9. 가족친화인증기관.png"),
]
handles = [path.open("rb") for path in paths]
files = [("files", (path.name, handle, "image/png")) for path, handle in zip(paths, handles)]
ocr_response = requests.post(
    base,
    files=files,
    data={
        "researcher_name": "김용성",
        "organization": "충남대학교",
        "deadline": "2026-08-20",
        "period_start": "2023-08-20",
        "period_end": "2026-08-20",
    },
    timeout=180,
)
for handle in handles:
    handle.close()
match = re.search(r'name="analysis_id" value="([^"]+)"', ocr_response.text)
qwen_response = requests.post(
    base + "analyze", data={"analysis_id": match.group(1)}, timeout=300
)
soup = BeautifulSoup(qwen_response.text, "html.parser")
sections = soup.select(".comparison")
print("OCR_POST", ocr_response.status_code)
print("QWEN_POST", qwen_response.status_code)
print("CERTIFICATE_SECTIONS", len(sections) >= 4)
for section in sections[-2:]:
    print(section.get_text(" ", strip=True))
Path("certificates_response.html").write_text(qwen_response.text, encoding="utf-8")
