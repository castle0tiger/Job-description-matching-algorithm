from .models import JDRequirements, CandidateProfile, MatchResult
from .analyzer import _call_gemini, _extract_json
from .domain import compute_domain_score
from .experience import format_months


def _career_lines(candidate: CandidateProfile) -> str:
    details = candidate.career_details or [{} for _ in candidate.careers]
    lines = []
    for i, (c, d) in enumerate(zip(candidate.careers, details), 1):
        period = f"{c.start or '?'} ~ {c.end or '?'}"
        length = f" ({format_months(d['months'])})" if d.get("months") is not None else ""
        excluded = " — 경력 연수 제외" if d and not d.get("included", True) and d.get("months") is not None else ""
        lines.append(f"{i}. {c.company} / {c.role} / 업종: {c.industry or '미상'} / {period}{length}{excluded}")
    return "\n".join(lines) or "없음"


def match_candidate(
    jd: JDRequirements,
    candidate: CandidateProfile,
    weight_skill: int = 25,
    weight_experience: int = 25,
    weight_education: int = 25,
    weight_other: int = 25,
    weight_cover_letter: int = 0,
) -> MatchResult:
    elements = jd.domain_elements
    jd_summary = f"""
직무: {jd.position}
도메인: {jd.domain}
도메인 평가 요소: {', '.join(elements) or '없음'}
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
학력: {candidate.education or '미확인'} ({candidate.education_major})
순 경력: {format_months(candidate.experience_months) if candidate.experience_months is not None else (str(candidate.total_experience_years) + '년' if candidate.total_experience_years is not None else '미확인')}
보유 스킬: {', '.join(candidate.skills or [])}
자격증: {', '.join(candidate.certifications or []) or '없음'}
경력 요약: {candidate.career_summary}
프로젝트: {'; '.join((candidate.projects or [])[:3]) if candidate.projects else '없음'}
경력 목록:
{_career_lines(candidate)}
""".strip()

    judge_domain = bool(elements and candidate.careers)
    domain_criteria = f"""

- domain_judgments: 위 "경력 목록"의 각 경력(번호)이 도메인 평가 요소({', '.join(elements)}) 각각에 해당하는지 판정
  · 직접: 그 분야의 조직(회사·기관)에서 일함 (예: 의료 → 병원·의료기기 회사, IT → IT·소프트웨어 회사)
  · 간접: 다른 업종의 조직이지만 그 분야를 주로 다루는 업무를 함 (예: 헬스케어 고객사 전담 홍보대행)
  · 없음: 해당 없음
  · 직무 종류(사무, 행사 등)나 기관 형태(협회, 스타트업 등)가 아니라 "어떤 산업 분야에서 일했는가"만 판단하세요.
  · 요소 이름은 위에 적힌 그대로 쓰세요.""" if judge_domain else ""
    example_verdicts = ", ".join(f'"{e}": "직접"' for e in elements[:1]) + "".join(f', "{e}": "없음"' for e in elements[1:])
    domain_json = f"""
  "domain_judgments": [{{"career": 1, "verdicts": {{{example_verdicts}}}}}],""" if judge_domain else ""

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
평가 기준 — 각 점수는 먼저 아래 구간 중 하나를 고른 뒤, 그 구간 안에서 5점 단위(0, 5, 10 … 100)로 정하세요.

- skill_match_score: JD 필수·우대 스킬 대비 보유 정도
  · 90~100: 필수 스킬을 모두 보유하고 우대 스킬도 절반 이상 보유
  · 75~85: 필수 스킬을 모두 보유하고 우대 스킬 일부 보유
  · 60~70: 필수 스킬은 모두 보유하나 우대 스킬은 없음
  · 40~55: 필수 스킬 일부 누락
  · 0~35: 필수 스킬 대부분 누락

- experience_score: JD 주요 업무를 실제로 해본 경험 — "무슨 일을 했는가"
  · 90~100: 주요 업무 대부분을 직접 수행했고 경력 연수도 요구 이상
  · 75~85: 주요 업무의 절반 이상을 직접 수행
  · 60~70: 주요 업무 일부만 수행했거나 유사 업무 경험 위주
  · 40~55: 관련성이 낮은 업무 위주
  · 0~35: 관련 경험이 거의 없음

- education_score: 학력 요건 충족 여부 (요건 충족 또는 요건 없음 = 100, 미달이면 차이에 따라 감점){domain_criteria}{cover_letter_criteria}
※ 순 경력은 근무 기간을 이미 계산한 값이니 그대로 사용하세요.
※ total_score와 도메인 점수는 별도 계산하므로 JSON에 포함하지 마세요.
※ 후보자의 나이·생년은 평가에 사용하지 말고, strengths/weaknesses/reasoning에도 언급하지 마세요.

반드시 아래 JSON 형식으로만 응답하세요:
```json
{{
  "skill_match_score": 90,
  "experience_score": 80,
  "education_score": 100,{domain_json}{cover_letter_json}
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
    judgments = data.pop("domain_judgments", None)
    for k in ("total_score", "cover_letter_score", "domain_fit_score", "domain_breakdown", "has_cover_letter"):
        data.pop(k, None)   # Python이 계산하는 값은 AI 응답을 쓰지 않음

    # AI 응답을 모델로 먼저 정규화한 뒤("85점" → 85 등) 계산한다
    m = MatchResult(filename=candidate.filename, candidate_name=candidate.name, **data)

    details = candidate.career_details or []
    m.domain_fit_score, m.domain_breakdown = compute_domain_score(
        elements,
        judgments if isinstance(judgments, list) else [],
        [d.get("months") for d in details],
        [d.get("included", False) for d in details],
    )

    m.has_cover_letter = has_cover_letter
    m.cover_letter_score = (
        round((m.cover_letter_relevance + m.cover_letter_growth + m.cover_letter_logic) / 3) if has_cover_letter else 0
    )
    total = round(
        m.skill_match_score * weight_skill / 100
        + m.experience_score * weight_experience / 100
        + m.education_score * weight_education / 100
        + m.domain_fit_score * weight_other / 100
        + m.cover_letter_score * weight_cover_letter / 100
    )
    m.total_score = min(total, 100)
    return m
