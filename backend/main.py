import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, File, Form, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse

load_dotenv()

from .analyzer import analyze_jd, analyze_resume
from .database import delete_analysis, get_analysis, get_history, init_db, save_analysis
from .filter import apply_filter
from .matcher import match_candidate
from .models import (
    AnalysisResponse,
    CandidateProfile,
    CandidateResult,
    FilterCriteria,
    JDRequirements,
)
from .parser import extract_text, SUPPORTED_EXTENSIONS

app = FastAPI(title="JD 후보자 매칭 시스템")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

FRONTEND_DIR = Path(__file__).parent.parent / "frontend"

init_db()


@app.get("/", response_class=HTMLResponse)
async def serve_index():
    return FileResponse(FRONTEND_DIR / "index.html")


@app.get("/results", response_class=HTMLResponse)
async def serve_results():
    return FileResponse(FRONTEND_DIR / "results.html")


@app.get("/history", response_class=HTMLResponse)
async def serve_history():
    return FileResponse(FRONTEND_DIR / "history.html")


# ── 이력 API ──────────────────────────────────────────────

@app.get("/api/history")
async def api_get_history():
    return JSONResponse(content=get_history())


@app.get("/api/history/{analysis_id}")
async def api_get_analysis(analysis_id: int):
    result = get_analysis(analysis_id)
    if result is None:
        return JSONResponse(status_code=404, content={"error": "분석 이력을 찾을 수 없습니다."})
    return JSONResponse(content=result)


@app.delete("/api/history/{analysis_id}")
async def api_delete_analysis(analysis_id: int):
    ok = delete_analysis(analysis_id)
    if not ok:
        return JSONResponse(status_code=404, content={"error": "분석 이력을 찾을 수 없습니다."})
    return JSONResponse(content={"ok": True})


@app.post("/api/analyze")
async def analyze(
    resume_files: list[UploadFile] = File(...),
    jd_file: UploadFile = File(None),
    jd_text_position: str = Form(""),
    jd_text_responsibilities: str = Form(""),
    jd_text_requirements: str = Form(""),
    jd_text_preferred: str = Form(""),
    position_override: str = Form(""),
    domain_override: str = Form(""),
    min_experience_years: str = Form(""),
    min_age: str = Form(""),
    max_age: str = Form(""),
    min_education: str = Form(""),
    required_certifications: str = Form(""),
    min_last_salary: str = Form(""),
    weight_skill: str = Form("35"),
    weight_experience: str = Form("30"),
    weight_education: str = Form("15"),
    weight_other: str = Form("10"),
    weight_cover_letter: str = Form("10"),
):
    def to_float(v):
        v = v.strip()
        return float(v) if v else None

    def to_int(v):
        v = v.strip()
        return int(v) if v else None

    def to_weight(v, default):
        try:
            return max(0, min(100, int(v.strip())))
        except Exception:
            return default

    w_skill = to_weight(weight_skill, 35)
    w_experience = to_weight(weight_experience, 30)
    w_education = to_weight(weight_education, 15)
    w_other = to_weight(weight_other, 10)
    w_cover_letter = to_weight(weight_cover_letter, 10)

    certs = [c.strip() for c in required_certifications.split(",") if c.strip()]
    filter_criteria = FilterCriteria(
        min_experience_years=to_float(min_experience_years),
        min_age=to_int(min_age),
        max_age=to_int(max_age),
        min_education=min_education.strip() or None,
        required_certifications=certs,
        min_last_salary=to_int(min_last_salary),
    )

    resume_data = [(f.filename or f"resume_{i+1}.pdf", await f.read()) for i, f in enumerate(resume_files)]

    # JD 분석 (PDF 또는 텍스트 직접 입력)
    try:
        has_pdf = jd_file is not None and jd_file.filename
        if has_pdf:
            jd_bytes = await jd_file.read()
            jd_text = extract_text(jd_bytes, jd_file.filename)
        else:
            parts = []
            if jd_text_position.strip():
                parts.append(f"[직무]\n{jd_text_position.strip()}")
            if jd_text_responsibilities.strip():
                parts.append(f"[주요 업무]\n{jd_text_responsibilities.strip()}")
            if jd_text_requirements.strip():
                parts.append(f"[지원 자격]\n{jd_text_requirements.strip()}")
            if jd_text_preferred.strip():
                parts.append(f"[우대사항]\n{jd_text_preferred.strip()}")
            if not parts:
                return JSONResponse(status_code=400, content={"error": "JD PDF 또는 텍스트 입력이 필요합니다."})
            jd_text = "\n\n".join(parts)

        jd_requirements: JDRequirements = analyze_jd(jd_text)
        if position_override.strip():
            jd_requirements.position = position_override.strip()
        if domain_override.strip():
            jd_requirements.domain = domain_override.strip()
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": f"JD 분석 실패: {e}"})

    all_results: list[CandidateResult] = []
    filtered_out_count = 0

    # 이력서 파싱 + 필터링
    for filename, resume_bytes in resume_data:
        try:
            resume_text = extract_text(resume_bytes, filename)
            profile = analyze_resume(resume_text, filename)
        except Exception as e:
            profile = CandidateProfile(filename=filename, parse_error=str(e))

        filter_result = apply_filter(profile, filter_criteria)
        if not filter_result.passed:
            filtered_out_count += 1
        all_results.append(CandidateResult(profile=profile, filter_result=filter_result))

    # 필터 통과자 매칭
    passed_results = [r for r in all_results if r.filter_result.passed]
    analyzed_count = 0

    for result in passed_results:
        try:
            match_result = match_candidate(
                jd_requirements, result.profile,
                weight_skill=w_skill,
                weight_experience=w_experience,
                weight_education=w_education,
                weight_other=w_other,
                weight_cover_letter=w_cover_letter,
            )
            result.match_result = match_result
            analyzed_count += 1
        except Exception:
            pass

    passed_results.sort(key=lambda r: r.match_result.total_score if r.match_result else 0, reverse=True)

    final_response = AnalysisResponse(
        jd_requirements=jd_requirements,
        filter_criteria=filter_criteria,
        total_resumes=len(resume_data),
        filtered_out_count=filtered_out_count,
        analyzed_count=analyzed_count,
        results=passed_results + [r for r in all_results if not r.filter_result.passed],
    )

    result_dict = final_response.model_dump()
    analysis_id = save_analysis(result_dict)
    result_dict["analysis_id"] = analysis_id

    return JSONResponse(content=result_dict)
