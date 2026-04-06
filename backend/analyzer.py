import json
import os
import re
from google import genai
from .models import JDRequirements, CandidateProfile

def _get_client():
    return genai.Client(api_key=os.environ["GEMINI_API_KEY"])


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

    response = _get_client().models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt,
    )
    text = response.text
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
  "career_summary": "경력 3줄 요약"
}}
```"""

    try:
        response = _get_client().models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
        )
        text = response.text
        data = _extract_json(text)
        profile = CandidateProfile(**data)
        profile.filename = filename
        return profile
    except Exception as e:
        return CandidateProfile(filename=filename, parse_error=str(e))
