import json
import os
from pathlib import Path
from typing import AsyncGenerator

from dotenv import load_dotenv
from fastapi import FastAPI, File, Form, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

load_dotenv()

# 환경변수 확인 로그
import sys
_api_key = os.environ.get("GEMINI_API_KEY")
print(f"[startup] GEMINI_API_KEY 존재 여부: {'YES' if _api_key else 'NO'}", file=sys.stderr)
print(f"[startup] 환경변수 목록: {[k for k in os.environ.keys() if 'GEMINI' in k or 'GOOGLE' in k or 'API' in k]}", file=sys.stderr)

from .analyzer import analyze_jd, analyze_resume
from .filter import apply_filter
from .matcher import match_candidate
from .models import (
    AnalysisResponse,
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


def _sse(event: str, data: dict) -> str:
    """SSE 포맷 문자열 생성."""
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


@app.post("/api/analyze-stream")
async def analyze_stream(
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
    """JD와 이력서를 분석하는 SSE 스트리밍 엔드포인트."""

    # 필터 조건 파싱
    def to_float(v: str):
        v = v.strip()
        return float(v) if v else None

    def to_int(v: str):
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

    async def stream() -> AsyncGenerator[str, None]:
        # 1단계: JD 분석
        yield _sse("progress", {"step": "jd", "message": "JD 분석 중...", "current": 0, "total": len(resume_data)})

        try:
            jd_text = extract_text_from_pdf(jd_bytes)
            jd_requirements: JDRequirements = analyze_jd(jd_text)
            if position_override.strip():
                jd_requirements.position = position_override.strip()
            if domain_override.strip():
                jd_requirements.domain = domain_override.strip()
        except Exception as e:
            yield _sse("error", {"message": f"JD 분석 실패: {e}"})
            return

        yield _sse("jd_done", {
            "message": f"JD 분석 완료: {jd_requirements.position}",
            "jd": jd_requirements.model_dump(),
        })

        # 2단계: 이력서 파싱 및 필터링
        all_results: list[CandidateResult] = []
        filtered_out_count = 0

        for idx, (filename, resume_bytes) in enumerate(resume_data):
            yield _sse("progress", {
                "step": "resume",
                "message": f"이력서 분석 중: {filename} ({idx + 1}/{len(resume_data)})",
                "current": idx + 1,
                "total": len(resume_data),
            })

            try:
                resume_text = extract_text_from_pdf(resume_bytes)
                profile = analyze_resume(resume_text, filename)
            except Exception as e:
                from .models import CandidateProfile
                profile = CandidateProfile(filename=filename, parse_error=str(e))

            filter_result = apply_filter(profile, filter_criteria)

            if not filter_result.passed:
                filtered_out_count += 1
                all_results.append(CandidateResult(profile=profile, filter_result=filter_result))
                yield _sse("filter_result", {
                    "filename": filename,
                    "passed": False,
                    "reasons": filter_result.reasons,
                })
            else:
                all_results.append(CandidateResult(profile=profile, filter_result=filter_result))
                yield _sse("filter_result", {
                    "filename": filename,
                    "passed": True,
                    "reasons": [],
                })

        # 3단계: 필터 통과자 매칭 평가
        passed_results = [r for r in all_results if r.filter_result.passed]
        analyzed_count = 0

        for idx, result in enumerate(passed_results):
            yield _sse("progress", {
                "step": "matching",
                "message": f"매칭 평가 중: {result.profile.filename} ({idx + 1}/{len(passed_results)})",
                "current": idx + 1,
                "total": len(passed_results),
            })

            try:
                match_result = match_candidate(jd_requirements, result.profile)
                result.match_result = match_result
                analyzed_count += 1
                yield _sse("match_result", {
                    "filename": result.profile.filename,
                    "score": match_result.total_score,
                    "recommendation": match_result.recommendation,
                })
            except Exception as e:
                yield _sse("match_error", {"filename": result.profile.filename, "error": str(e)})

        # 4단계: 최종 결과 (점수 기준 내림차순 정렬)
        passed_results.sort(key=lambda r: r.match_result.total_score if r.match_result else 0, reverse=True)

        final_response = AnalysisResponse(
            jd_requirements=jd_requirements,
            filter_criteria=filter_criteria,
            total_resumes=len(resume_data),
            filtered_out_count=filtered_out_count,
            analyzed_count=analyzed_count,
            results=passed_results + [r for r in all_results if not r.filter_result.passed],
        )

        yield _sse("done", {"result": final_response.model_dump()})

    return StreamingResponse(stream(), media_type="text/event-stream")
