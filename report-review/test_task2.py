from pathlib import Path

import requests
from bs4 import BeautifulSoup
import re


base = "http://127.0.0.1:54451/"
path = Path("서류샘플/2. 우수 연구자.png")
with path.open("rb") as handle:
    ocr_response = requests.post(
        base,
        files={"files": (path.name, handle, "image/png")},
        data={
            "researcher_name": "김용성",
            "organization": "충남대학교",
            "deadline": "2026-08-20",
            "period_start": "2023-08-20",
            "period_end": "2026-08-20",
        },
        timeout=180,
    )
match = re.search(r'name="analysis_id" value="([^"]+)"', ocr_response.text)
qwen_response = requests.post(
    base + "analyze", data={"analysis_id": match.group(1)}, timeout=300
)
soup = BeautifulSoup(qwen_response.text, "html.parser")
sections = soup.select(".comparison")
task2_section = next(
    (section for section in sections if section.find("h2") and "2. 우수 연구자 판별" in section.find("h2").get_text()),
    None,
)
print("OCR_POST", ocr_response.status_code)
print("QWEN_POST", qwen_response.status_code)
print("TASK2_SECTION", task2_section is not None)
print(task2_section.get_text(" ", strip=True) if task2_section else "")
Path("task2_response.html").write_text(qwen_response.text, encoding="utf-8")
