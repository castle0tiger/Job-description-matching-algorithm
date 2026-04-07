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
from .filter import apply_filter
from .matcher import match_candidate
from .models import (
    AnalysisResponse,
    CandidateProfile,
    CandidateResult,
    FilterCriteria,
    JDRequirements,
)
from .parser import extract_text_from_pdf

app = FastAPI(title="JD 후보자 매칭 시스템")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

FRONTEND_DIR = Path(__file__).parent.parent / "frontend"


@app.get("/", response_class=HTMLResponse)
async def serve_index():
    return FileResponse(FRONTEND_DIR / "index.html")


@app.get("/results", response_class=HTMLResponse)
async def serve_results():
    return FileResponse(FRONTEND_DIR / "results.html")


@app.post("/api/analyze")
async def analyze(
    jd_file: UploadFile = File(...),
    resume_files: list[UploadFile] = File(...),
    position_override: str = Form(""),
    domain_override: str = Form(""),
    min_experience_years: str = Form(""),
    min_age: str = Form(""),
    max_age: str = Form(""),
    min_education: str = Form(""),
    required_certifications: str = Form(""),
    min_last_salary: str = Form(""),
):
    def to_float(v):
        v = v.strip()
        return float(v) if v else None

    def to_int(v):
        v = v.strip()
        return int(v) if v else None

    certs = [c.strip() for c in required_certifications.split(",") if c.strip()]
    filter_criteria = FilterCriteria(
        min_experience_years=to_float(min_experience_years),
        min_age=to_int(min_age),
        max_age=to_int(max_age),
        min_education=min_education.strip() or None,
        required_certifications=certs,
        min_last_salary=to_int(min_last_salary),
    )

    jd_bytes = await jd_file.read()
    resume_data = [(f.filename or f"resume_{i+1}.pdf", await f.read()) for i, f in enumerate(resume_files)]

    # JD 분석
    try:
        jd_text = extract_text_from_pdf(jd_bytes)
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
            resume_text = extract_text_from_pdf(resume_bytes)
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
            match_result = match_candidate(jd_requirements, result.profile)
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

    return JSONResponse(content=final_response.model_dump())
