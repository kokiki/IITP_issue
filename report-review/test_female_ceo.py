from pathlib import Path

import requests
from bs4 import BeautifulSoup
import re


base = "http://127.0.0.1:54451/"
paths = [
    Path("서류샘플/5. 대표이사 여성 기업 여부_2.png"),
    Path("서류샘플/5. 대표이사 여성 기업 여부_1.png"),
]
handles = [path.open("rb") for path in paths]
files = [("files", (path.name, handle, "image/png")) for path, handle in zip(paths, handles)]
ocr_response = requests.post(base, files=files, timeout=180)
for handle in handles:
    handle.close()
match = re.search(r'name="analysis_id" value="([^"]+)"', ocr_response.text)
qwen_response = requests.post(
    base + "analyze", data={"analysis_id": match.group(1)}, timeout=300
)
soup = BeautifulSoup(qwen_response.text, "html.parser")
sections = soup.select(".comparison")
female_section = next(
    (section for section in sections if section.find("h2") and "대표이사 여성 기업 여부" in section.find("h2").get_text()),
    None,
)
print("OCR_POST", ocr_response.status_code)
print("QWEN_POST", qwen_response.status_code)
print("FEMALE_CEO_SECTION", female_section is not None)
print(female_section.get_text(" ", strip=True) if female_section else "")
Path("female_ceo_response.html").write_text(qwen_response.text, encoding="utf-8")
