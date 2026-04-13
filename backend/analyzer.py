import json
import os
import re
import time
import requests
from .models import JDRequirements, CandidateProfile

API_KEY = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY") or "AIzaSyBO6CSBamN_iUJL-fWoD4WcQyuPyxyDi6A"
GEMINI_URL = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={API_KEY}"

_RETRY_STATUS = {429, 500, 502, 503, 504}
_MAX_RETRIES = 3
_RETRY_DELAY = 5  # 초


def _call_gemini(prompt: str) -> str:
    last_error = None
    for attempt in range(_MAX_RETRIES):
        try:
            response = requests.post(
                GEMINI_URL,
                json={"contents": [{"parts": [{"text": prompt}]}]},
                timeout=120,
            )
            if response.status_code in _RETRY_STATUS:
                raise requests.HTTPError(response=response)
            response.raise_for_status()
            return response.json()["candidates"][0]["content"]["parts"][0]["text"]
        except (requests.HTTPError, requests.ConnectionError, requests.Timeout) as e:
            last_error = e
            if attempt < _MAX_RETRIES - 1:
                time.sleep(_RETRY_DELAY)
    raise last_error


def _extract_json(text: str) -> dict:
    match = re.search(r"```json\s*([\s\S]*?)\s*```", text)
    if match:
        return json.loads(match.group(1))
    match = re.search(r"\{[\s\S]*\}", text)
    if match:
        return json.loads(match.group(0))
    raise ValueError("JSON을 찾을 수 없습니다.")


def analyze_jd(jd_text: str) -> JDRequirements:
    prompt = f"""다음 채용공고(JD)를 분석하여 요구사항을 정확히 JSON 형식으로 추출하세요.
숫자는 반드시 숫자 타입으로, 없는 정보는 null로 표기하세요.

채용공고:
{jd_text}

반드시 아래 JSON 형식으로만 응답하세요 (다른 설명 없이):
```json
{{
  "position": "직무명",
  "required_skills": ["필수스킬1", "필수스킬2"],
  "preferred_skills": ["우대스킬1"],
  "min_experience_years": 3,
  "max_experience_years": null,
  "education": "대졸",
  "required_certifications": [],
  "domain": "업종/도메인",
  "key_responsibilities": ["주요업무1", "주요업무2"],
  "job_description": "직무 한 줄 요약"
}}
```"""
    text = _call_gemini(prompt)
    data = _extract_json(text)
    return JDRequirements(**data)


def analyze_resume(resume_text: str, filename: str = "") -> CandidateProfile:
    prompt = f"""다음 이력서를 분석하여 후보자 정보를 정확히 JSON 형식으로 추출하세요.
숫자는 반드시 숫자 타입으로, 없는 정보는 null로 표기하세요.
경력 연수는 소수점 허용 (예: 3.5), 연봉은 만원 단위 정수.

이력서:
{resume_text}

반드시 아래 JSON 형식으로만 응답하세요 (다른 설명 없이):
```json
{{
  "name": "홍길동",
  "age": 30,
  "education": "대졸",
  "education_major": "컴퓨터공학",
  "total_experience_years": 5.0,
  "skills": ["Python", "SQL", "React"],
  "certifications": ["정보처리기사"],
  "last_salary": 4500,
  "companies": ["회사명1", "회사명2"],
  "projects": ["프로젝트 한 줄 설명"],
  "career_summary": "경력 3줄 요약",
  "cover_letter": "자기소개서 전체 원문 (없으면 빈 문자열)"
}}
```"""
    try:
        text = _call_gemini(prompt)
        data = _extract_json(text)
        profile = CandidateProfile(**data)
        profile.filename = filename
        return profile
    except Exception as e:
        return CandidateProfile(filename=filename, parse_error=str(e))
