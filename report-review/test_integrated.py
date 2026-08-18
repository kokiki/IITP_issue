from pathlib import Path
import time

import requests


base = "http://127.0.0.1:54451"
paths = sorted(Path("서류샘플").glob("*.png"))
with requests.Session() as session:
    handles = [path.open("rb") for path in paths]
    files = [("files", (path.name, handle, "image/png")) for path, handle in zip(paths, handles)]
    response = session.post(
        base + "/review",
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
    import re
    job_id = re.search(r"const jobId = (\"[^\"]+\")", response.text).group(1).strip('"')
    while True:
        state = session.get(f"{base}/review/{job_id}", timeout=30).json()
        print(state["completed"], "/", state["total"], state["current"])
        if state["status"] in {"complete", "error"}:
            break
        time.sleep(1)
    print("STATUS", state["status"])
    print("SCORE_TOTAL", state.get("score_total"))
    print("ROWS", [(row.get("item"), row.get("score"), row.get("status")) for row in state.get("rows", [])])
    if state["status"] == "complete":
        download = session.get(base + state["download_url"], timeout=30)
        Path("integrated_review.xlsx").write_bytes(download.content)
        print("XLSX", download.status_code, len(download.content))
