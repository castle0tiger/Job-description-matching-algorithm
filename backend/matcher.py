import json
import re
from .models import JDRequirements, CandidateProfile, MatchResult
from .analyzer import _call_gemini


def _extract_json(text: str) -> dict:
    match = re.search(r"```json\s*([\s\S]*?)\s*```", text)
    if match:
        return json.loads(match.group(1))
    match = re.search(r"\{[\s\S]*\}", text)
    if match:
        return json.loads(match.group(0))
    raise ValueError("JSON을 찾을 수 없습니다.")


def match_candidate(
    jd: JDRequirements,
    candidate: CandidateProfile,
    weight_skill: int = 35,
    weight_experience: int = 30,
    weight_education: int = 15,
    weight_other: int = 10,
    weight_cover_letter: int = 10,
) -> MatchResult:
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

    has_cover_letter = bool(candidate.cover_letter and candidate.cover_letter.strip())

    candidate_summary = f"""
이름: {candidate.name}
나이: {candidate.age or '미확인'}세
학력: {candidate.education or '미확인'} ({candidate.education_major})
경력: {candidate.total_experience_years or '미확인'}년
보유 스킬: {', '.join(candidate.skills or [])}
자격증: {', '.join(candidate.certifications or []) or '없음'}
경력 요약: {candidate.career_summary}
프로젝트: {'; '.join((candidate.projects or [])[:3]) if candidate.projects else '없음'}
""".strip()

    cover_letter_section = f"""
=== 자기소개서 ===
{candidate.cover_letter}
""" if has_cover_letter else ""

    cover_letter_criteria = """
- cover_letter_relevance: 자기소개서에서 지원 직무와의 연관성이 얼마나 명확하게 드러나는가 (0-100)
- cover_letter_growth: 학습 의지, 도전 경험, 성장 가능성이 구체적 사례로 드러나는가 (0-100)
- cover_letter_logic: 두루뭉술한 표현 없이 구체적 사례와 수치로 논리적으로 작성됐는가 (0-100)""" if has_cover_letter else ""

    cover_letter_json = """
  "cover_letter_relevance": 80,
  "cover_letter_growth": 75,
  "cover_letter_logic": 85,""" if has_cover_letter else """
  "cover_letter_relevance": 0,
  "cover_letter_growth": 0,
  "cover_letter_logic": 0,"""

    prompt = f"""당신은 채용 전문가입니다. 아래 채용공고와 후보자 이력서를 꼼꼼히 비교하여 적합도를 평가하세요.

=== 채용공고 ===
{jd_summary}

=== 후보자 정보 ===
{candidate_summary}
{cover_letter_section}
평가 기준:
- skill_match_score: 필수/우대 스킬 보유 여부 (0-100)
- experience_score: 경력 연수 및 관련 직무 경험 적합도 (0-100) — 무슨 일을 했는가
- education_score: 학력 요건 충족 여부 (0-100)
- domain_fit_score: 후보자가 일했던 업종/산업군이 JD 도메인과 일치하는 정도 (0-100){cover_letter_criteria}
※ total_score는 별도 계산하므로 JSON에 포함하지 마세요.

반드시 아래 JSON 형식으로만 응답하세요:
```json
{{
  "skill_match_score": 90,
  "experience_score": 80,
  "education_score": 100,
  "domain_fit_score": 75,{cover_letter_json}
  "overall_fit": "상",
  "strengths": ["강점1", "강점2", "강점3"],
  "weaknesses": ["약점1", "약점2"],
  "recommendation": "적극 추천",
  "reasoning": "종합 평가 3~5문장"
}}
```

overall_fit은 반드시 "상"/"중"/"하" 중 하나.
recommendation은 반드시 "적극 추천"/"추천"/"검토 필요"/"미추천" 중 하나."""

    text = _call_gemini(prompt)
    data = _extract_json(text)

    # 자기소개서 종합 점수 먼저 계산 (total_score에 반영하기 위해)
    if has_cover_letter:
        cl_r = data.get("cover_letter_relevance", 0)
        cl_g = data.get("cover_letter_growth", 0)
        cl_l = data.get("cover_letter_logic", 0)
        data["cover_letter_score"] = round((cl_r + cl_g + cl_l) / 3)

    # total_score를 Python에서 직접 계산
    skill  = data.get("skill_match_score", 0)
    exp    = data.get("experience_score", 0)
    edu    = data.get("education_score", 0)
    domain = data.get("domain_fit_score", 0)
    cl     = data.get("cover_letter_score", 0) if has_cover_letter else 0
    total  = round(
        skill  * weight_skill          / 100
        + exp  * weight_experience     / 100
        + edu  * weight_education      / 100
        + domain * weight_other        / 100
        + cl   * weight_cover_letter   / 100
    )
    data["total_score"] = min(total, 100)
    if not has_cover_letter:
        data["cover_letter_score"] = 0
    data["has_cover_letter"] = has_cover_letter

    return MatchResult(
        filename=candidate.filename,
        candidate_name=candidate.name,
        **data,
    )
