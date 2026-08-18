import glob
import re

import requests


base = "http://127.0.0.1:54451/"
handles = [open(path, "rb") for path in glob.glob("서류샘플/*.png")]
files = [("files", (handle.name, handle, "image/png")) for handle in handles]
ocr_response = requests.post(base, files=files, timeout=600)
for handle in handles:
    handle.close()
print("OCR_POST", ocr_response.status_code)
print("OCR_TEXT_PRESENT", "김용성" in ocr_response.content.decode("utf-8", "ignore"))
match = re.search(r'name="analysis_id" value="([^"]+)"', ocr_response.text)
print("ANALYSIS_ID", bool(match))
if match:
    qwen_response = requests.post(
        base + "analyze", data={"analysis_id": match.group(1)}, timeout=600
    )
    print("QWEN_POST", qwen_response.status_code)
    print(
        "QWEN_JSON_PRESENT",
        all(value in qwen_response.text for value in ["researcher_name", "김용성", "충남대학교"]),
    )
    with open("e2e_response.html", "w", encoding="utf-8") as output:
        output.write(qwen_response.text)
