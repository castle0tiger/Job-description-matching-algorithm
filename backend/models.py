from pydantic import BaseModel, Field, field_validator
from typing import Optional


def _to_list(v):
    """문자열이나 None이 들어오면 리스트로 변환."""
    if v is None:
        return []
    if isinstance(v, str):
        return [v] if v.strip() else []
    return v


class FilterCriteria(BaseModel):
    min_experience_years: Optional[float] = None      # 최소 경력 연수
    min_age: Optional[int] = None                     # 최소 나이
    max_age: Optional[int] = None                     # 최대 나이
    min_education: Optional[str] = None               # 최소 학력
    required_qualifications: list[str] = Field(default_factory=list)  # 필수 자격 조건 (키워드)
    min_last_salary: Optional[int] = None             # 최소 전직장 연봉 (만원)
    min_toeic: Optional[int] = None                   # 최소 토익 점수
    min_opic: Optional[str] = None                    # 최소 오픽 등급
    min_toeic_speaking: Optional[str] = None          # 최소 토익스피킹 등급


class JDRequirements(BaseModel):
    position: Optional[str] = ""
    required_skills: list[str] = Field(default_factory=list)
    preferred_skills: list[str] = Field(default_factory=list)
    min_experience_years: Optional[float] = None
    max_experience_years: Optional[float] = None
    education: Optional[str] = None
    required_certifications: list[str] = Field(default_factory=list)
    domain: Optional[str] = ""
    key_responsibilities: list[str] = Field(default_factory=list)
    job_description: Optional[str] = ""


class CandidateProfile(BaseModel):
    filename: str = ""
    name: Optional[str] = ""
    age: Optional[int] = None
    education: Optional[str] = None
    education_major: Optional[str] = ""
    total_experience_years: Optional[float] = None
    skills: Optional[list[str]] = Field(default_factory=list)
    certifications: Optional[list[str]] = Field(default_factory=list)
    last_salary: Optional[int] = None                # 만원 단위
    companies: Optional[list[str]] = Field(default_factory=list)
    projects: Optional[list[str]] = Field(default_factory=list)
    career_summary: Optional[str] = ""
    toeic_score: Optional[int] = None                # 토익 점수
    opic_grade: Optional[str] = None                 # 오픽 등급
    toeic_speaking_grade: Optional[str] = None       # 토익스피킹 등급
    cover_letter: Optional[str] = ""                 # 자기소개서 원문 (있는 경우)
    parse_error: str = ""                             # 파싱 오류 메시지

    @field_validator('skills', 'certifications', 'companies', 'projects', mode='before')
    @classmethod
    def coerce_to_list(cls, v):
        return _to_list(v)


class FilterResult(BaseModel):
    passed: bool
    reasons: list[str] = Field(default_factory=list)  # 탈락 사유 (failed일 때)


class MatchResult(BaseModel):
    filename: str = ""
    candidate_name: str = ""
    total_score: int = 0
    skill_match_score: int = 0
    experience_score: int = 0
    education_score: int = 0
    domain_fit_score: int = 0        # 도메인/업종 적합도
    cover_letter_relevance: int = 0  # 자기소개서 - 직무 연관성
    cover_letter_growth: int = 0     # 자기소개서 - 성장 가능성
    cover_letter_logic: int = 0      # 자기소개서 - 논리성/구체성
    cover_letter_score: int = 0      # 자기소개서 종합 점수
    has_cover_letter: bool = False   # 자기소개서 존재 여부
    overall_fit: str = ""            # 상/중/하
    strengths: list[str] = Field(default_factory=list)
    weaknesses: list[str] = Field(default_factory=list)
    recommendation: str = ""         # 적극 추천/추천/검토 필요/미추천
    reasoning: str = ""


class CandidateResult(BaseModel):
    profile: CandidateProfile
    filter_result: FilterResult
    match_result: Optional[MatchResult] = None


class AnalysisResponse(BaseModel):
    jd_requirements: JDRequirements
    filter_criteria: FilterCriteria
    total_resumes: int
    filtered_out_count: int
    analyzed_count: int
    results: list[CandidateResult]


# 오픽 등급 수준 매핑 (높을수록 좋음)
OPIC_LEVELS = {
    "AL": 7, "IH": 6, "IM3": 5, "IM2": 4, "IM1": 3, "IL": 2, "NH": 1, "NM": 0, "NL": 0,
}

# 토익스피킹 등급 수준 매핑
TOEIC_SPEAKING_LEVELS = {
    "AL": 6, "IH": 5, "IL": 4, "NH": 3, "NM": 2, "NL": 1,
}

# 학력 수준 매핑 (비교용)
EDUCATION_LEVELS = {
    "고졸": 1,
    "전문대졸": 2,
    "대졸": 3,
    "대학원졸": 4,
    "석사": 4,
    "박사": 5,
}
