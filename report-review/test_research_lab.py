from pathlib import Path
import re

import requests
from bs4 import BeautifulSoup


base = "http://127.0.0.1:54451/"
path = Path("서류샘플/10. 우수 기업부설연구소 소속 기업.png")
with path.open("rb") as handle:
    response = requests.post(
        base,
        files=[("files", (path.name, handle, "image/png"))],
        data={
            "researcher_name": "김용성",
            "organization": "충남대학교",
            "deadline": "2026-08-20",
            "period_start": "2023-08-20",
            "period_end": "2026-08-20",
        },
        timeout=180,
    )
analysis_id = re.search(r'name="analysis_id" value="([^"]+)"', response.text).group(1)
result = requests.post(base + "analyze", data={"analysis_id": analysis_id}, timeout=300)
soup = BeautifulSoup(result.text, "html.parser")
section = [s for s in soup.select(".comparison") if "기업부설연구소" in s.get_text()][-1]
print("OCR_POST", response.status_code)
print("QWEN_POST", result.status_code)
print(section.get_text(" ", strip=True))
Path("research_lab_response.html").write_text(result.text, encoding="utf-8")
