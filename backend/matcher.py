import json
import os
import re
from dotenv import load_dotenv
from google import genai
from .models import JDRequirements, CandidateProfile, MatchResult

load_dotenv()

def _get_client():
    api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY") or "AIzaSyBO6CSBamN_iUJL-fWoD4WcQyuPyxyDi6A"
    return genai.Client(api_key=api_key)


def _extract_json(text: str) -> dict:
    match = re.search(r"```json\s*([\s\S]*?)\s*```", text)
    if match:
        return json.loads(match.group(1))
    match = re.search(r"\{[\s\S]*\}", text)
    if match:
        return json.loads(match.group(0))
    raise ValueError("JSON을 찾을 수 없습니다.")


def match_candidate(jd: JDRequirements, candidate: CandidateProfile) -> MatchResult:
    jd_summary = f"""
직무: {jd.position}
도메인: {jd.domain}
필수 스킬: {', '.join(jd.required_skills)}
우대 스킬: {', '.join(jd.preferred_skills)}
최소 경력: {jd.min_experience_years}년 {'~ ' + str(jd.max_experience_years) + '년' if jd.max_experience_years else '이상'}
요구 학력: {jd.education or '무관'}
필수 자격증: {', '.join(jd.required_certifications) or '없음'}
주요 업무: {', '.join(jd.key_responsibilities[:5])}
""".strip()

    candidate_summary = f"""
이름: {candidate.name}
나이: {candidate.age or '미확인'}세
학력: {candidate.education or '미확인'} ({candidate.education_major})
경력: {candidate.total_experience_years or '미확인'}년
보유 스킬: {', '.join(candidate.skills)}
자격증: {', '.join(candidate.certifications) or '없음'}
경력 요약: {candidate.career_summary}
프로젝트: {'; '.join(candidate.projects[:3]) if candidate.projects else '없음'}
""".strip()

    prompt = f"""당신은 채용 전문가입니다. 아래 채용공고와 후보자 이력서를 꼼꼼히 비교하여 적합도를 평가하세요.

=== 채용공고 ===
{jd_summary}

=== 후보자 정보 ===
{candidate_summary}

평가 기준:
- skill_match_score: 필수/우대 스킬 보유 여부 (0-100)
- experience_score: 경력 연수 및 관련 경험 적합도 (0-100)
- education_score: 학력 요건 충족 여부 (0-100)
- total_score: 종합 점수 (스킬 40% + 경력 35% + 학력 15% + 기타 10%)

반드시 아래 JSON 형식으로만 응답하세요:
```json
{{
  "total_score": 85,
  "skill_match_score": 90,
  "experience_score": 80,
  "education_score": 100,
  "overall_fit": "상",
  "strengths": ["강점1", "강점2", "강점3"],
  "weaknesses": ["약점1", "약점2"],
  "recommendation": "적극 추천",
  "reasoning": "종합 평가 3~5문장"
}}
```

overall_fit은 반드시 "상"/"중"/"하" 중 하나.
recommendation은 반드시 "적극 추천"/"추천"/"검토 필요"/"미추천" 중 하나."""

    response = _get_client().models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt,
    )
    text = response.text
    data = _extract_json(text)
    return MatchResult(
        filename=candidate.filename,
        candidate_name=candidate.name,
        **data,
    )
