from __future__ import annotations

import io
import json
import os
import re
import subprocess
import tempfile
import threading
import time
import uuid
from datetime import date
from pathlib import Path

import fitz
import requests
from flask import Flask, jsonify, redirect, render_template, request, send_file
from PIL import Image


BASE_DIR = Path(os.environ.get("APP_ROOT", Path(__file__).resolve().parent)).resolve()
MODEL_DIR = Path(os.environ.get("PADDLE_OCR_BASE_DIR", BASE_DIR / "models" / "paddleocr"))
MODEL_DIR.mkdir(exist_ok=True)
os.environ.setdefault("PADDLE_OCR_BASE_DIR", str(MODEL_DIR))
os.environ.setdefault("FLAGS_use_mkldnn", "0")
os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("MKL_NUM_THREADS", "1")

from paddleocr import PaddleOCR


app = Flask(__name__, template_folder=str(BASE_DIR / "templates"))
app.json.ensure_ascii = False
app.config["MAX_CONTENT_LENGTH"] = 50 * 1024 * 1024
LLAMA_SERVER_URL = os.environ.get("LLAMA_SERVER_URL", "http://127.0.0.1:8080")
DEFAULT_RESEARCHER_NAME = "김용성"
DEFAULT_ORGANIZATION = "충남대학교"
DEFAULT_DEADLINE = "2026-08-20"
DEFAULT_PERIOD_START = "2023-08-20"
DEFAULT_PERIOD_END = "2026-08-20"
OCR_STORE: dict[str, dict] = {}
REVIEW_JOBS: dict[str, dict] = {}
REVIEW_LOCK = threading.Lock()
EXPORT_DIR = BASE_DIR / "exports"
EXPORT_DIR.mkdir(exist_ok=True)
NODE_BIN = os.environ.get(
    "CODEX_NODE_BIN",
    str(BASE_DIR / "tools" / "node" / "node.exe"),
)
DEFAULT_XLSX_EXPORTER = BASE_DIR / "tools" / "node" / "xlsx_exporter.mjs"
if not DEFAULT_XLSX_EXPORTER.exists():
    DEFAULT_XLSX_EXPORTER = BASE_DIR / "xlsx_exporter.mjs"
XLSX_EXPORTER = Path(os.environ.get("XLSX_EXPORTER", DEFAULT_XLSX_EXPORTER))

FILE_CRITERIA = {
    "project": ("과제수행결과 우수여부", "연구책임자명·주관기관명 일치"),
    "outstanding_researcher": ("우수 연구자", "연구자명·소속기관명 일치 및 증빙일 3년 이내"),
    "female_ceo": ("대표이사 여성기업 여부", "사업자등록증·재직증명서 대표자명 일치 및 여성 확인"),
    "job_invention": ("직무발명보상 우수기업", "기관명 일치 및 인증 유효기간 확인"),
    "family_friendly": ("가족친화인증기관", "기관명 일치 및 인증 유효기간 확인"),
    "research_lab": ("우수 기업부설연구소", "등급과 연구소 보유 기관명 확인"),
}


def classify_filename(filename: str) -> str | None:
    if "1. 과제수행결과" in filename:
        return "project"
    if "2. 우수 연구자" in filename:
        return "outstanding_researcher"
    if "5. 대표이사 여성 기업 여부" in filename:
        return "female_ceo"
    if "8. 직무발명보상 우수기업" in filename:
        return "job_invention"
    if "9. 가족친화인증기관" in filename:
        return "family_friendly"
    if "10. 우수 기업부설연구소" in filename:
        return "research_lab"
    return None

JSON_SCHEMA = {
    "type": "object",
    "properties": {
        "researcher_name": {"type": ["string", "null"]},
        "organization": {"type": ["string", "null"]},
        "outstanding_researcher_name": {"type": ["string", "null"]},
        "outstanding_researcher_organization": {"type": ["string", "null"]},
        "outstanding_researcher_evidence_date": {"type": ["string", "null"]},
        "business_registration_representative_name": {"type": ["string", "null"]},
        "employment_certificate_representative_name": {"type": ["string", "null"]},
        "representative_gender": {"type": ["string", "null"]},
        "job_invention_certificate_organization": {"type": ["string", "null"]},
        "job_invention_valid_from": {"type": ["string", "null"]},
        "job_invention_valid_until": {"type": ["string", "null"]},
        "job_invention_issue_date": {"type": ["string", "null"]},
        "family_friendly_certificate_organization": {"type": ["string", "null"]},
        "family_friendly_valid_from": {"type": ["string", "null"]},
        "family_friendly_valid_until": {"type": ["string", "null"]},
        "family_friendly_issue_date": {"type": ["string", "null"]},
        "gender": {"type": ["string", "null"]},
        "outstanding_researcher": {"type": ["boolean", "null"]},
        "project_performance_outstanding": {"type": ["boolean", "null"]},
        "female_ceo_company": {"type": ["boolean", "null"]},
        "family_friendly_certified": {"type": ["boolean", "null"]},
        "job_invention_reward_company": {"type": ["boolean", "null"]},
        "excellent_corporate_research_lab": {"type": ["boolean", "null"]},
        "corporate_research_lab_grade": {"type": ["string", "null"]},
        "corporate_research_lab_organization": {"type": ["string", "null"]},
        "research_period": {"type": ["string", "null"]},
        "evidence_date": {"type": ["string", "null"]},
        "research_topic": {"type": ["string", "null"]},
        "evidence": {"type": "array", "items": {"type": "string"}},
    },
    "required": [
        "researcher_name", "organization",
        "outstanding_researcher_name", "outstanding_researcher_organization",
        "outstanding_researcher_evidence_date",
        "business_registration_representative_name",
        "employment_certificate_representative_name", "representative_gender",
        "job_invention_certificate_organization", "job_invention_valid_from",
        "job_invention_valid_until", "job_invention_issue_date",
        "family_friendly_certificate_organization", "family_friendly_valid_from",
        "family_friendly_valid_until", "family_friendly_issue_date",
        "gender", "outstanding_researcher",
        "project_performance_outstanding", "female_ceo_company",
        "family_friendly_certified", "job_invention_reward_company",
        "excellent_corporate_research_lab", "research_period", "evidence_date",
        "corporate_research_lab_grade", "corporate_research_lab_organization",
        "research_topic",
        "evidence",
    ],
    "additionalProperties": False,
}

ocr = PaddleOCR(
    lang="korean", use_angle_cls=False, use_gpu=False,
    enable_mkldnn=False, show_log=False,
)
OCR_LOCK = threading.Lock()


def pdf_pages(data: bytes):
    document = fitz.open(stream=data, filetype="pdf")
    try:
        for page in document:
            pixmap = page.get_pixmap(matrix=fitz.Matrix(2, 2), alpha=False)
            yield pixmap.tobytes("png")
    finally:
        document.close()


def ocr_image(data: bytes) -> str:
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as handle:
        handle.write(data)
        image_path = handle.name
    try:
        # PaddleOCR's CPU predictor is not safe for concurrent reuse in Flask.
        with OCR_LOCK:
            result = ocr.ocr(image_path, cls=False)
        lines = []
        for page in result or []:
            for _, (text, score) in page or []:
                # Confidence is kept internally by PaddleOCR, but the user-facing
                # OCR text should contain only the recognized words.
                lines.append(text)
        return "\n".join(lines) or "(텍스트를 찾지 못했습니다)"
    finally:
        os.unlink(image_path)


def extract_json(content: str) -> dict:
    content = content.strip()
    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", content, re.S)
    if fenced:
        content = fenced.group(1)
    else:
        start, end = content.find("{"), content.rfind("}")
        if start >= 0 and end > start:
            content = content[start : end + 1]
    return json.loads(content)


def analyze_with_qwen(ocr_results: list[dict[str, str]]) -> dict:
    normalized = []
    for item in ocr_results:
        seen = set()
        lines = []
        for raw_line in item["text"].splitlines():
            line = re.sub(r"\s+\(score:\s*[0-9.]+\)$", "", raw_line).strip()
            if line and line not in seen:
                seen.add(line)
                lines.append(line)
        normalized.append({"name": item["name"], "text": "\n".join(lines)})
    source = "\n\n".join(
        f"[파일: {item['name']}]\n{item['text']}" for item in normalized
    )
    prompt = f"""다음은 PaddleOCR로 추출한 문서 원문이다. OCR 오류는 문맥으로 보정하되, 원문에 근거가 없는 값은 null 또는 false로 둬라.
기관명, 연구자명, 우수 연구자 문서의 연구자명·소속기관·증빙일, 사업자등록증 대표자명, 재직증명서 대표이사명, 대표이사 성별, 직무발명보상 우수기업 인증서 기관명과 기간, 가족친화 인증서 기관명과 기간, 우수 기업부설연구소의 등급과 연구소 보유 기관명, 성별, 우수 연구자 여부, 과제수행결과 우수 여부, 여성 대표이사 기업 여부, 가족친화 인증기관 여부, 직무발명보상 우수기업 여부, 우수 기업부설연구소 소속 여부, 연구기간, 연구주제를 중복 없이 추출하라.
판정 규칙:
1. 제목에 우수/인증이라는 단어가 있다는 이유만으로 true로 만들지 말고, 해당 문서가 실제 증명하는지 판정하라.
2. '교육 실습용', '가상', '실제 ... 아님', '정부표창아님'이 있으면 그 문서의 자격·표창·인증 여부는 false다.
3. outstanding_researcher는 실제 표창/수상 증거가 있을 때만 true다. project_performance_outstanding은 평가결과가 우수일 때 true다.
4. female_ceo_company는 대표자 성별이 여성일 때만 true다. 나머지 인증 여부도 같은 방식으로 문서 근거가 있을 때만 true다.
5. research_period는 '총 연구기간'의 시작일과 종료일을 정확히 읽어 YYYY-MM-DD~YYYY-MM-DD 형식으로 작성하라.
6. evidence_date는 증빙 문서의 발급일·수여일·인증일 중 해당 문서에 표시된 날짜를 YYYY-MM-DD 형식으로 작성하라.
7. 사업자등록증 대표자명은 '대표자' 또는 '대표자명' 항목의 값만 추출하라. 개업연월일, 법인등록번호, 사업의 종류, 업태, 종목은 대표자명으로 절대 사용하지 마라.
8. 재직증명서 대표이사명은 성명/성명란의 값을 추출하라. 두 문서가 모두 있으면 파일명에 따라 각각의 필드에 넣어라.
9. 대표이사 성별은 문서에 명시된 성별만 사용하고, 이름만으로 추정하지 마라.
10. 직무발명보상 우수기업 인증서는 해당 파일의 기관명과 유효기간 시작일·종료일을 job_invention 필드에 넣고, 유효기간이 없으면 발급일을 issue_date에 넣어라.
11. 가족친화 인증서는 해당 파일의 기관명과 유효기간 시작일·종료일을 family_friendly 필드에 넣고, 유효기간이 없으면 발급일을 issue_date에 넣어라.
12. 파일명에 '우수 연구자'가 포함된 문서는 outstanding_researcher_* 전용 필드에 넣어라. 다른 문서의 기관명으로 덮어쓰지 마라.
13. '우수 기업부설연구소' 또는 '최우수 기업부설연구소' 문서는 등급을 원문 그대로 corporate_research_lab_grade에 넣고, 연구소를 보유한 기관명을 corporate_research_lab_organization에 넣어라.
14. evidence에는 파일명과 핵심 근거 문구를 넣고, JSON 객체만 반환하라.

OCR 원문:
{source}"""
    payload = {
        "model": "Qwen3-1.7B-Q8_0.gguf",
        "messages": [
            {"role": "system", "content": "너는 문서 적격성 검토용 정보 추출기다."},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.0,
        "max_tokens": 768,
        "chat_template_kwargs": {"enable_thinking": False},
        "response_format": {
            "type": "json_schema",
            "json_schema": {"name": "eligibility_review", "schema": JSON_SCHEMA},
        },
    }
    response = requests.post(
        f"{LLAMA_SERVER_URL}/v1/chat/completions", json=payload, timeout=300
    )
    response.raise_for_status()
    content = response.json()["choices"][0]["message"].get("content", "")
    return extract_json(content)


def compare_identity(input_researcher: str, input_organization: str, qwen_result: dict) -> dict:
    """Calculate the task score locally; Qwen never calculates this score."""
    ocr_researcher = qwen_result.get("researcher_name")
    ocr_organization = qwen_result.get("organization")
    researcher_match = (
        bool(ocr_researcher)
        and input_researcher.strip() == str(ocr_researcher).strip()
    )
    organization_match = (
        bool(ocr_organization)
        and input_organization.strip() == str(ocr_organization).strip()
    )
    score = 1 if researcher_match and organization_match else 0
    status = (
        "충족" if score == 1
        else "확인필요" if not ocr_researcher or not ocr_organization
        else "0점"
    )
    return {
        "input_researcher": input_researcher,
        "ocr_researcher": ocr_researcher,
        "researcher_match": researcher_match,
        "input_organization": input_organization,
        "ocr_organization": ocr_organization,
        "organization_match": organization_match,
        "score": score,
        "status": status,
    }


def parse_date_value(value: str | None) -> date | None:
    if not value:
        return None
    text = str(value).strip()
    try:
        return date.fromisoformat(text[:10])
    except ValueError:
        match = re.search(r"(20\d{2})\D+(\d{1,2})\D+(\d{1,2})", text)
        if not match:
            return None
        return date(int(match.group(1)), int(match.group(2)), int(match.group(3)))


def compare_outstanding_researcher(
    input_researcher: str,
    input_organization: str,
    deadline_text: str,
    period_start_text: str,
    period_end_text: str,
    qwen_result: dict,
) -> dict:
    researcher_name = qwen_result.get("outstanding_researcher_name") or qwen_result.get("researcher_name")
    organization = qwen_result.get("outstanding_researcher_organization") or qwen_result.get("organization")
    evidence_date = parse_date_value(
        qwen_result.get("outstanding_researcher_evidence_date")
        or qwen_result.get("evidence_date")
    )
    period_start = parse_date_value(period_start_text)
    period_end = parse_date_value(period_end_text)
    researcher_match = (
        bool(researcher_name)
        and input_researcher.strip() == str(researcher_name).strip()
    )
    organization_match = (
        bool(organization)
        and input_organization.strip() == str(organization).strip()
    )
    date_in_range = bool(evidence_date and period_start and period_end) and (
        period_start <= evidence_date <= period_end
    )
    score = 1 if researcher_match and organization_match and date_in_range else 0
    status = (
        "충족" if score == 1
        else "확인필요" if not researcher_name or not organization or not evidence_date
        else "0점"
    )
    return {
        "researcher_name": researcher_name,
        "organization": organization,
        "evidence_date": evidence_date.isoformat() if evidence_date else None,
        "period_start": period_start.isoformat() if period_start else period_start_text,
        "period_end": period_end.isoformat() if period_end else period_end_text,
        "researcher_match": researcher_match,
        "organization_match": organization_match,
        "date_in_range": date_in_range,
        "score": score,
        "status": status,
    }


def compare_female_ceo_company(qwen_result: dict) -> dict:
    """Compare the two document names and calculate the result in Python."""
    business_name = qwen_result.get("business_registration_representative_name")
    employment_name = qwen_result.get("employment_certificate_representative_name")
    gender = qwen_result.get("representative_gender")
    names_match = bool(business_name and employment_name) and (
        str(business_name).strip() == str(employment_name).strip()
    )
    gender_text = str(gender or "").strip().lower()
    female_confirmed = gender_text in {"여성", "female", "woman", "여자"}
    score = 1 if names_match and female_confirmed else 0
    status = (
        "충족" if score == 1
        else "확인필요" if not business_name or not employment_name or not gender
        else "0점"
    )
    return {
        "business_name": business_name,
        "employment_name": employment_name,
        "names_match": names_match,
        "gender": gender,
        "female_confirmed": female_confirmed,
        "score": score,
        "status": status,
    }


def compare_corporate_research_lab(qwen_result: dict, input_organization: str) -> dict:
    """Calculate research-lab grade points locally; Qwen only extracts fields."""
    grade = str(qwen_result.get("corporate_research_lab_grade") or "").strip()
    lab_organization = qwen_result.get("corporate_research_lab_organization")
    organization_match = bool(lab_organization) and (
        input_organization.strip() == str(lab_organization).strip()
    )
    if grade == "최우수":
        grade_score = 1.0
    elif grade == "우수":
        grade_score = 0.5
    else:
        grade_score = 0.0
    score = grade_score if organization_match else 0.0
    status = (
        "충족" if score > 0
        else "확인필요" if not grade or not lab_organization
        else "0점"
    )
    return {
        "grade": grade or None,
        "organization": lab_organization,
        "input_organization": input_organization,
        "organization_match": organization_match,
        "score": score,
        "status": status,
    }


def repair_document_fields_from_ocr(
    qwen_result: dict,
    ocr_results: list[dict[str, str]],
    input_organization: str,
) -> None:
    """Use document-scoped OCR evidence to repair ambiguous combined uploads."""
    person_pattern = re.compile(r"^[가-힣]{2,5}$")
    excluded = {"대표자", "대표이사", "대표유형", "사업자", "등록번호"}
    for item in ocr_results:
        filename = item.get("name", "")
        lines = [line.strip() for line in item.get("text", "").splitlines() if line.strip()]
        has_input_organization = input_organization in lines
        if "1. 과제수행결과" in filename and has_input_organization:
            qwen_result["organization"] = input_organization
        if "우수 연구자" in filename and has_input_organization:
            qwen_result["organization"] = input_organization
        if "직무발명" in filename and has_input_organization:
            qwen_result["job_invention_certificate_organization"] = input_organization
        if "가족친화" in filename and has_input_organization:
            qwen_result["family_friendly_certificate_organization"] = input_organization
        if "대표이사 여성 기업 여부_2" in filename:
            found_name = False
            for index, line in enumerate(lines):
                if "대표자" not in line:
                    continue
                for candidate in lines[index + 1:index + 5]:
                    if person_pattern.fullmatch(candidate) and candidate not in excluded:
                        qwen_result["business_registration_representative_name"] = candidate
                        found_name = True
                        break
                if found_name:
                    break
        if "우수 연구자" in filename:
            if input_organization in lines:
                organization_index = lines.index(input_organization)
                qwen_result["outstanding_researcher_organization"] = input_organization
                for candidate in lines[organization_index + 1:organization_index + 4]:
                    if person_pattern.fullmatch(candidate) and candidate not in excluded:
                        qwen_result["outstanding_researcher_name"] = candidate
                        break
            # The sample certificate puts the organization and researcher directly
            # after the title; keep these values separate from other uploaded files.
            if not qwen_result.get("outstanding_researcher_organization"):
                for index, line in enumerate(lines):
                    if line in {"표창장", "상장"} and index + 2 < len(lines):
                        organization = lines[index + 1]
                        researcher = lines[index + 2]
                        if organization and researcher:
                            qwen_result["outstanding_researcher_organization"] = organization
                            qwen_result["outstanding_researcher_name"] = researcher
                            break
            joined = " ".join(lines)
            for date_match in re.finditer(
                r"(20\d{2})\D{0,8}(\d{1,2})\D{0,8}(\d{1,2})", joined
            ):
                try:
                    qwen_result["outstanding_researcher_evidence_date"] = date(
                        int(date_match.group(1)),
                        int(date_match.group(2)),
                        int(date_match.group(3)),
                    ).isoformat()
                    break
                except ValueError:
                    continue
        if "기업부설연구소" in filename:
            title_text = " ".join(lines[:20])
            if re.search(r"최\s*우수\s*기업부설연구소", title_text):
                qwen_result["corporate_research_lab_grade"] = "최우수"
            elif re.search(r"우수\s*기업부설연구소", title_text):
                qwen_result["corporate_research_lab_grade"] = "우수"
            for index, line in enumerate(lines):
                if line == "기관" and index + 2 < len(lines) and lines[index + 1] == "명":
                    qwen_result["corporate_research_lab_organization"] = lines[index + 2]
                    break
            if not qwen_result.get("corporate_research_lab_organization"):
                for candidate in lines:
                    if candidate == input_organization:
                        qwen_result["corporate_research_lab_organization"] = candidate
                        break


def compare_certificate(
    qwen_result: dict,
    input_organization: str,
    deadline_text: str,
    prefix: str,
) -> dict:
    certificate_organization = qwen_result.get(f"{prefix}_certificate_organization")
    valid_from = parse_date_value(qwen_result.get(f"{prefix}_valid_from"))
    valid_until = parse_date_value(qwen_result.get(f"{prefix}_valid_until"))
    issue_date = parse_date_value(qwen_result.get(f"{prefix}_issue_date"))
    deadline = parse_date_value(deadline_text)
    organization_match = bool(certificate_organization) and (
        input_organization.strip() == str(certificate_organization).strip()
    )
    if valid_from and valid_until and deadline:
        period_ok = valid_from <= deadline <= valid_until
        date_basis = f"{valid_from.isoformat()} ~ {valid_until.isoformat()}"
        date_mode = "유효기간"
    elif issue_date and deadline:
        period_start = date(deadline.year - 3, deadline.month, deadline.day)
        period_ok = period_start <= issue_date <= deadline
        date_basis = issue_date.isoformat()
        date_mode = "발급일"
    else:
        period_ok = False
        date_basis = None
        date_mode = "확인불가"
    score = 1 if organization_match and period_ok else 0
    status = (
        "충족" if score == 1
        else "확인필요" if not certificate_organization or not date_basis
        else "0점"
    )
    return {
        "certificate_organization": certificate_organization,
        "input_organization": input_organization,
        "organization_match": organization_match,
        "date_basis": date_basis,
        "date_mode": date_mode,
        "period_ok": period_ok,
        "score": score,
        "status": status,
    }


def repair_certificate_dates_from_ocr(
    qwen_result: dict, ocr_results: list[dict[str, str]]
) -> None:
    """Repair split OCR dates when Qwen returns an incomplete date string.

    Certificate images commonly OCR a validity period as separate lines such as
    ``2026 / 08 / 16 / 2028 / 08 / 15``.  The explicit period in the source
    document has priority over a malformed Qwen date value.
    """
    certificate_specs = (
        ("직무발명", "job_invention"),
        ("가족친화", "family_friendly"),
    )
    triplet = re.compile(r"(20\d{2})\D{0,12}(\d{1,2})\D{0,12}(\d{1,2})")
    for filename_keyword, prefix in certificate_specs:
        for item in ocr_results:
            if filename_keyword not in item.get("name", ""):
                continue
            source = item.get("text", "")
            marker = re.search(r"유효\s*기간", source)
            if not marker:
                continue
            candidates = []
            for match in triplet.finditer(source[marker.end(): marker.end() + 500]):
                try:
                    candidates.append(date(
                        int(match.group(1)), int(match.group(2)), int(match.group(3))
                    ))
                except ValueError:
                    continue
            if len(candidates) >= 2:
                qwen_result[f"{prefix}_valid_from"] = candidates[0].isoformat()
                qwen_result[f"{prefix}_valid_until"] = candidates[1].isoformat()
            break


def calculate_all_comparisons(
    results: list[dict[str, str]],
    input_researcher: str,
    input_organization: str,
    deadline: str,
    period_start: str,
    period_end: str,
    update=None,
    qwen_result: dict | None = None,
) -> tuple[dict, list[dict]]:
    """Run the existing extraction and Python scoring logic for one review job."""
    if qwen_result is None:
        qwen_result = analyze_with_qwen(results)
        repair_document_fields_from_ocr(qwen_result, results, input_organization)
        repair_certificate_dates_from_ocr(qwen_result, results)
    comparisons = []
    checks = [
        (
            "과제수행결과 우수여부",
            "project",
            lambda: compare_identity(input_researcher, input_organization, qwen_result),
        ),
        (
            "우수 연구자",
            "outstanding_researcher",
            lambda: compare_outstanding_researcher(
                input_researcher, input_organization, deadline,
                period_start, period_end, qwen_result,
            ),
        ),
        ("대표이사 여성기업 여부", "female_ceo", lambda: compare_female_ceo_company(qwen_result)),
        (
            "직무발명보상 우수기업",
            "job_invention",
            lambda: compare_certificate(
                qwen_result, input_organization, deadline, "job_invention"
            ),
        ),
        (
            "가족친화인증기관",
            "family_friendly",
            lambda: compare_certificate(
                qwen_result, input_organization, deadline, "family_friendly"
            ),
        ),
        (
            "우수 기업부설연구소",
            "research_lab",
            lambda: compare_corporate_research_lab(qwen_result, input_organization),
        ),
    ]
    ocr_error_classes = {
        item.get("classification")
        for item in results
        if item.get("ocr_error") and item.get("classification")
    }
    for name, classification, check in checks:
        result = check()
        if classification in ocr_error_classes:
            result["status"] = "분석오류"
            result["score"] = 0
        result["item"] = name
        comparisons.append(result)
        if update:
            update(name, result, classification)
    for item in results:
        if item.get("classification") is None:
            result = {
                "item": item["name"],
                "status": "파일분류실패",
                "score": 0,
            }
            comparisons.append(result)
            if update:
                update(item["name"], result, None)
    return qwen_result, comparisons


def run_review_job(job_id: str, uploaded_files: list[tuple[str, bytes]], params: dict) -> None:
    started = time.perf_counter()
    job = REVIEW_JOBS[job_id]

    def set_state(**values):
        with REVIEW_LOCK:
            job.update(values)
            job["elapsed_seconds"] = round(time.perf_counter() - started, 1)

    results = []
    for index, (filename, data) in enumerate(uploaded_files, 1):
        classification = classify_filename(filename)
        set_state(
            current_file=filename, current_detail="OCR 실행",
            current=f"OCR: {filename}", phase="OCR", completed=0,
        )
        try:
            suffix = Path(filename).suffix.lower()
            if suffix == ".pdf":
                pages = list(pdf_pages(data))
                text = "\n\n".join(
                    f"[페이지 {n}]\n{ocr_image(page)}"
                    for n, page in enumerate(pages, 1)
                )
            else:
                Image.open(io.BytesIO(data)).verify()
                text = ocr_image(data)
        except Exception as exc:
            text = f"OCR 오류: {exc}"
        results.append({
            "name": filename, "text": text, "classification": classification,
            "ocr_error": text.startswith("OCR 오류:"),
        })
        set_state(
            ocr_results=results, current_file=filename,
            current_detail="OCR 완료", current=f"OCR 완료: {filename}",
        )

    set_state(current_file="전체 파일", current_detail="Qwen JSON 추출", current="Qwen JSON 분석 중", phase="Qwen JSON")
    try:
        qwen_result = analyze_with_qwen(results)
        repair_document_fields_from_ocr(qwen_result, results, params["input_organization"])
        repair_certificate_dates_from_ocr(qwen_result, results)
    except Exception as exc:
        error_rows = [
            {"item": name, "status": "분석오류", "score": 0}
            for name, _, _ in (
                ("과제수행결과 우수여부", None, None),
                ("우수 연구자", None, None),
                ("대표이사 여성기업 여부", None, None),
                ("직무발명보상 우수기업", None, None),
                ("가족친화인증기관", None, None),
                ("우수 기업부설연구소", None, None),
            )
        ]
        error_rows.extend(
            {"item": filename, "status": "파일분류실패", "score": 0}
            for filename, data in uploaded_files if classify_filename(filename) is None
        )
        with REVIEW_LOCK:
            job["rows"] = error_rows
            job["completed"] = job["total"]
            job["score_total"] = 0
        set_state(
            status="error", error=f"Qwen 분석 오류: {exc}",
            current_file="전체 파일", current_detail="Qwen 분석 오류", current="오류",
        )
        return

    with REVIEW_LOCK:
        job["qwen_result"] = qwen_result
        job["ocr_results"] = results

    def update_item(name, result, classification):
        with REVIEW_LOCK:
            job["completed"] += 1
            job["current"] = name
            job["current_file"] = "전체 파일"
            job["current_detail"] = f"{name} 판별"
            job["rows"] = job["rows"] + [result]
            job["score_total"] = sum(float(row.get("score") or 0) for row in job["rows"])
            job["elapsed_seconds"] = round(time.perf_counter() - started, 1)
        # Keep each completed row observable by the browser polling loop.
        time.sleep(0.25)

    try:
        _, comparisons = calculate_all_comparisons(
            results,
            params["input_researcher"], params["input_organization"],
            params["deadline"], params["period_start"], params["period_end"],
            update=update_item,
            qwen_result=qwen_result,
        )
        with REVIEW_LOCK:
            job["rows"] = comparisons
        export_input = EXPORT_DIR / f"{job_id}.json"
        export_input.write_text(json.dumps(job, ensure_ascii=False), encoding="utf-8")
        subprocess.run(
            [NODE_BIN, str(XLSX_EXPORTER), str(export_input),
             str(EXPORT_DIR / f"review_{job_id}.xlsx")],
            check=True, timeout=120,
        )
        set_state(
            status="complete", phase="완료", current_file="전체 파일",
            current_detail="모든 판별 완료", current="모든 항목 완료",
            download_url=f"/download/{job_id}",
        )
    except Exception as exc:
        set_state(status="error", error=f"결과 저장 오류: {exc}", current="오류")


@app.post("/review")
def start_review():
    input_researcher = request.form.get("researcher_name", DEFAULT_RESEARCHER_NAME).strip()
    input_organization = request.form.get("organization", DEFAULT_ORGANIZATION).strip()
    deadline = request.form.get("deadline", DEFAULT_DEADLINE).strip()
    period_start = request.form.get("period_start", DEFAULT_PERIOD_START).strip()
    period_end = request.form.get("period_end", DEFAULT_PERIOD_END).strip()
    files = [f for f in request.files.getlist("files") if f.filename]
    if not files:
        return render_template("index.html", error="파일을 하나 이상 선택하세요."), 400
    if len(files) > 10:
        return render_template("index.html", error="한 번에 최대 10개 파일까지 업로드할 수 있습니다."), 400
    job_id = uuid.uuid4().hex
    selected_files = [f.filename for f in files]
    unknown_file_count = sum(1 for filename in selected_files if classify_filename(filename) is None)
    with REVIEW_LOCK:
        REVIEW_JOBS[job_id] = {
            "status": "running", "phase": "준비", "current": "검토 준비",
            "current_file": "없음", "current_detail": "준비 중",
            "completed": 0, "total": 6 + unknown_file_count, "rows": [], "score_total": 0,
            "elapsed_seconds": 0, "ocr_results": [], "qwen_result": None,
            "selected_files": selected_files,
            "input_researcher": input_researcher,
            "input_organization": input_organization,
            "deadline": deadline, "period_start": period_start, "period_end": period_end,
        }
    uploaded_files = [(f.filename, f.read()) for f in files]
    params = {
        "input_researcher": input_researcher, "input_organization": input_organization,
        "deadline": deadline, "period_start": period_start, "period_end": period_end,
    }
    threading.Thread(target=run_review_job, args=(job_id, uploaded_files, params), daemon=True).start()
    return render_template(
        "index.html", review_job_id=job_id,
        selected_files=selected_files,
        input_researcher=input_researcher, input_organization=input_organization,
        deadline=deadline, period_start=period_start, period_end=period_end,
    )


@app.get("/review")
def review_page():
    return redirect("/")


@app.get("/system-status")
def system_status():
    llama_ready = False
    try:
        llama_ready = requests.get(f"{LLAMA_SERVER_URL}/health", timeout=2).ok
    except requests.RequestException:
        pass
    return jsonify({
        "paddleocr": "준비" if ocr is not None else "오류",
        "qwen": "준비" if llama_ready else "오류",
        "llama_server": "준비" if llama_ready else "오류",
    })


@app.get("/review/<job_id>")
def review_status(job_id):
    with REVIEW_LOCK:
        job = REVIEW_JOBS.get(job_id)
        if not job:
            return jsonify({"status": "missing"}), 404
        response = dict(job)
        response["progress"] = round((response["completed"] / response["total"]) * 100)
        response.pop("ocr_results", None)
        response.pop("qwen_result", None)
        return jsonify(response)


@app.get("/review/<job_id>/data")
def review_data(job_id):
    with REVIEW_LOCK:
        job = REVIEW_JOBS.get(job_id)
        if not job:
            return jsonify({"status": "missing"}), 404
        return jsonify({
            "ocr_results": job.get("ocr_results", []),
            "qwen_result": job.get("qwen_result"),
            "rows": job.get("rows", []),
        })


@app.get("/download/<job_id>")
def download_review(job_id):
    path = EXPORT_DIR / f"review_{job_id}.xlsx"
    if not path.exists():
        return "파일이 아직 준비되지 않았습니다.", 404
    return send_file(path, as_attachment=True, download_name="적격성_검토결과.xlsx")


@app.post("/reset")
def reset_review():
    job_id = request.form.get("job_id", "")
    with REVIEW_LOCK:
        job = REVIEW_JOBS.get(job_id)
        if job and job.get("status") == "running":
            return jsonify({"ok": False, "message": "검토 중에는 초기화할 수 없습니다."}), 409
        REVIEW_JOBS.pop(job_id, None)
    return jsonify({"ok": True})


@app.route("/", methods=["GET", "POST"])
def index():
    results, error, analysis_id = [], None, None
    input_researcher = DEFAULT_RESEARCHER_NAME
    input_organization = DEFAULT_ORGANIZATION
    deadline = DEFAULT_DEADLINE
    period_start = DEFAULT_PERIOD_START
    period_end = DEFAULT_PERIOD_END
    if request.method == "POST":
        input_researcher = request.form.get("researcher_name", DEFAULT_RESEARCHER_NAME).strip()
        input_organization = request.form.get("organization", DEFAULT_ORGANIZATION).strip()
        deadline = request.form.get("deadline", DEFAULT_DEADLINE).strip()
        period_start = request.form.get("period_start", DEFAULT_PERIOD_START).strip()
        period_end = request.form.get("period_end", DEFAULT_PERIOD_END).strip()
        files = [f for f in request.files.getlist("files") if f.filename]
        if not files:
            error = "파일을 하나 이상 선택하세요."
        elif len(files) > 10:
            error = "한 번에 최대 10개 파일까지 업로드할 수 있습니다."
        else:
            for uploaded in files:
                data = uploaded.read()
                try:
                    suffix = Path(uploaded.filename).suffix.lower()
                    if suffix == ".pdf":
                        pages = list(pdf_pages(data))
                        text = "\n\n".join(
                            f"[페이지 {n}]\n{ocr_image(page)}"
                            for n, page in enumerate(pages, 1)
                        )
                    else:
                        Image.open(io.BytesIO(data)).verify()
                        text = ocr_image(data)
                    results.append({"name": uploaded.filename, "text": text})
                except Exception as exc:
                    results.append({"name": uploaded.filename, "text": f"OCR 오류: {exc}"})
            analysis_id = uuid.uuid4().hex
            OCR_STORE[analysis_id] = {
                "results": results,
                "input_researcher": input_researcher,
                "input_organization": input_organization,
                "deadline": deadline,
                "period_start": period_start,
                "period_end": period_end,
            }
    return render_template(
        "index.html", results=results, error=error, analysis_id=analysis_id,
        input_researcher=input_researcher, input_organization=input_organization,
        deadline=deadline, period_start=period_start, period_end=period_end,
    )


@app.post("/analyze")
def analyze():
    analysis_id = request.form.get("analysis_id", "")
    stored = OCR_STORE.get(analysis_id)
    if not stored:
        return render_template("index.html", error="OCR 결과가 없습니다. 먼저 OCR을 실행하세요."), 400
    results = stored["results"]
    try:
        qwen_result = analyze_with_qwen(results)
        repair_document_fields_from_ocr(
            qwen_result, results, stored["input_organization"]
        )
        repair_certificate_dates_from_ocr(qwen_result, results)
        comparison = compare_identity(
            stored["input_researcher"], stored["input_organization"], qwen_result
        )
        researcher_comparison = compare_outstanding_researcher(
            stored["input_researcher"], stored["input_organization"],
            stored["deadline"], stored["period_start"], stored["period_end"],
            qwen_result,
        )
        female_ceo_comparison = compare_female_ceo_company(qwen_result)
        job_invention_comparison = compare_certificate(
            qwen_result, stored["input_organization"], stored["deadline"],
            "job_invention",
        )
        family_friendly_comparison = compare_certificate(
            qwen_result, stored["input_organization"], stored["deadline"],
            "family_friendly",
        )
        corporate_research_lab_comparison = compare_corporate_research_lab(
            qwen_result, stored["input_organization"]
        )
        return render_template(
            "index.html", results=results, analysis_id=analysis_id,
            qwen_result=qwen_result, comparison=comparison,
            researcher_comparison=researcher_comparison,
            female_ceo_comparison=female_ceo_comparison,
            job_invention_comparison=job_invention_comparison,
            family_friendly_comparison=family_friendly_comparison,
            corporate_research_lab_comparison=corporate_research_lab_comparison,
            input_researcher=stored["input_researcher"],
            input_organization=stored["input_organization"],
            deadline=stored["deadline"], period_start=stored["period_start"],
            period_end=stored["period_end"],
        )
    except Exception as exc:
        return render_template(
            "index.html", results=results, analysis_id=analysis_id,
            error=f"Qwen 분석 오류: {exc}"
        ), 502


if __name__ == "__main__":
    app.run(
        host="127.0.0.1", port=int(os.environ.get("PORT", "0")),
        debug=False, threaded=False,
    )
