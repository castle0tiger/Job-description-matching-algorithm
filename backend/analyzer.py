import json
import os
import re
import time
import requests
from .experience import finalize_experience
from .models import JDRequirements, CandidateProfile

API_KEY = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
# 키를 URL 쿼리에 넣으면 HTTPError 메시지(→ API 응답·DB)에 그대로 노출되므로 헤더로 전달
GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent"

_RETRY_STATUS = {429, 500, 502, 503, 504}
_MAX_RETRIES = 5
_RETRY_BASE_DELAY = 2  # 초, 2→4→8→16 지수 백오프

# 같은 이력서가 실행마다 다르게 추출·채점되지 않도록 샘플링 무작위성 최소화
_GENERATION_CONFIG = {"temperature": 0, "seed": 42}


def _call_gemini(prompt: str) -> str:
    last_error = None
    for attempt in range(_MAX_RETRIES):
        try:
            response = requests.post(
                GEMINI_URL,
                headers={"x-goog-api-key": API_KEY},
                json={"contents": [{"parts": [{"text": prompt}]}], "generationConfig": _GENERATION_CONFIG},
                timeout=120,
            )
            if response.status_code in _RETRY_STATUS:
                raise requests.HTTPError(f"Gemini 일시 오류 {response.status_code}", response=response)
            response.raise_for_status()
            return response.json()["candidates"][0]["content"]["parts"][0]["text"]
        except (requests.HTTPError, requests.ConnectionError, requests.Timeout, KeyError, IndexError) as e:
            if isinstance(e, requests.HTTPError) and e.response is not None and e.response.status_code not in _RETRY_STATUS:
                raise
            last_error = e
            if attempt < _MAX_RETRIES - 1:
                time.sleep(_RETRY_BASE_DELAY * 2 ** attempt)
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
  "domain_elements": ["업종 요소1", "업종 요소2"],
  "key_responsibilities": ["주요업무1", "주요업무2"],
  "job_description": "직무 한 줄 요약"
}}
```
domain_elements: 이 일자리의 업종·산업 분야를 1~3개의 핵심 요소로 나눈 목록 (예: 디지털병리 → ["의료·병리", "IT·AI·디지털"], 핀테크 → ["금융", "IT"]).
직무 종류(사무, 행사기획 등)나 기관 형태(협회, 스타트업, 공공기관 등)는 넣지 말고 산업 분야만 넣으세요."""
    text = _call_gemini(prompt)
    data = _extract_json(text)
    jd = JDRequirements(**data)
    jd.domain_elements = jd.domain_elements[:3]
    return jd


def analyze_resume(resume_text: str, filename: str = "") -> CandidateProfile:
    prompt = f"""다음 이력서를 분석하여 후보자 정보를 정확히 JSON 형식으로 추출하세요.
숫자는 반드시 숫자 타입으로, 없는 정보는 null로 표기하세요.
경력 연수는 소수점 허용 (예: 3.5), 연봉은 만원 단위 정수.
나이·생년월일은 추출하지 말고, career_summary 등 어떤 필드에도 포함하지 마세요.

이력서:
{resume_text}

반드시 아래 JSON 형식으로만 응답하세요 (다른 설명 없이):
```json
{{
  "name": "홍길동",
  "education": "대졸",
  "education_major": "컴퓨터공학",
  "total_experience_years": 5.0,
  "skills": ["Python", "SQL", "React"],
  "certifications": ["정보처리기사"],
  "last_salary": 4500,
  "companies": ["회사명1", "회사명2"],
  "projects": ["프로젝트 한 줄 설명"],
  "career_summary": "경력 3줄 요약",
  "toeic_score": 850,
  "opic_grade": "IH",
  "toeic_speaking_grade": null,
  "cover_letter": "자기소개서 전체 원문 (없으면 빈 문자열)",
  "careers": [
    {{"company": "회사명", "role": "직무/직위", "employment_type": "정규직", "industry": "업종 한 줄 (예: 대학병원, 의료기기 제조, IT 스타트업)", "start": "2019-03", "end": "2021-02"}},
    {{"company": "회사명", "role": "직무/직위", "employment_type": "계약직", "industry": "업종 한 줄", "start": "2021-09", "end": "현재"}}
  ]
}}
```
toeic_score는 숫자 또는 null, opic_grade/toeic_speaking_grade는 AL/IH/IM3/IM2/IM1/IL/NH/NM/NL 중 하나 또는 null.
careers 작성 규칙:
- 이력서의 경력사항을 빠짐없이 회사(근무처)마다 하나씩 넣으세요. 학력·교육 이수·대외활동은 넣지 마세요.
- start/end는 이력서에 적힌 연월을 "YYYY-MM"으로 옮기고, 재직 중이면 end를 "현재"로 쓰세요. 월이 없으면 "YYYY"만 쓰세요.
- 기간을 계산하거나 추측하지 말고 적힌 그대로 옮기세요. 기간이 없으면 null.
- employment_type은 정규직/계약직/프리랜서/인턴/아르바이트 중 하나. 인턴·아르바이트는 이력서에 그렇게 명시된 경우에만 쓰고, 표기가 없으면 정규직으로 쓰세요."""
    try:
        text = _call_gemini(prompt)
        data = _extract_json(text)
        profile = CandidateProfile(**data)
        profile.filename = filename
        return finalize_experience(profile)
    except Exception as e:
        return CandidateProfile(filename=filename, parse_error=str(e))
