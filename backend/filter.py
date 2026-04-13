from .models import CandidateProfile, FilterCriteria, FilterResult, EDUCATION_LEVELS, OPIC_LEVELS, TOEIC_SPEAKING_LEVELS


def _parse_education_level(edu_text: str) -> int:
    """자유형식 학력 텍스트를 EDUCATION_LEVELS 숫자로 변환합니다."""
    if not edu_text:
        return 0
    t = edu_text.strip()

    # 정확히 매핑되는 키 우선
    if t in EDUCATION_LEVELS:
        return EDUCATION_LEVELS[t]

    # 박사
    if any(k in t for k in ["박사"]):
        return EDUCATION_LEVELS["박사"]

    # 석사 / 대학원졸 / 대학원 (졸업, 졸업예정, 수료, 재학 모두 포함)
    if any(k in t for k in ["석사", "대학원"]):
        return EDUCATION_LEVELS["석사"]

    # 전문대
    if any(k in t for k in ["전문대", "2년제", "3년제"]):
        return EDUCATION_LEVELS["전문대졸"]

    # 대졸 (4년제 대학교)
    if any(k in t for k in ["대졸", "대학교", "대학(교)", "4년제", "학사"]):
        return EDUCATION_LEVELS["대졸"]

    # 고졸
    if any(k in t for k in ["고졸", "고등학교", "고등"]):
        return EDUCATION_LEVELS["고졸"]

    return 0


def apply_filter(profile: CandidateProfile, criteria: FilterCriteria) -> FilterResult:
    """
    후보자 프로필을 필터 기준에 적용합니다.
    모든 기준을 통과해야 passed=True.
    """
    reasons = []

    # 파싱 오류가 있는 경우
    if profile.parse_error:
        return FilterResult(passed=False, reasons=[f"이력서 파싱 오류: {profile.parse_error}"])

    # 최소 경력 연수
    if criteria.min_experience_years is not None:
        exp = profile.total_experience_years
        if exp is None or exp < criteria.min_experience_years:
            actual = f"{exp}년" if exp is not None else "미확인"
            reasons.append(
                f"경력 미달: 기준 {criteria.min_experience_years}년 이상, 실제 {actual}"
            )

    # 나이 범위 (정보 없으면 통과)
    if criteria.min_age is not None or criteria.max_age is not None:
        age = profile.age
        if age is not None:
            if criteria.min_age is not None and age < criteria.min_age:
                reasons.append(f"나이 미달: 기준 {criteria.min_age}세 이상, 실제 {age}세")
            if criteria.max_age is not None and age > criteria.max_age:
                reasons.append(f"나이 초과: 기준 {criteria.max_age}세 이하, 실제 {age}세")

    # 최소 학력
    if criteria.min_education:
        min_level = EDUCATION_LEVELS.get(criteria.min_education, 0)
        candidate_level = _parse_education_level(profile.education or "")
        if candidate_level < min_level:
            actual = profile.education or "미확인"
            reasons.append(
                f"학력 미달: 기준 {criteria.min_education} 이상, 실제 {actual}"
            )

    # 필수 자격 조건 (키워드 통합 검색)
    if criteria.required_qualifications:
        # 후보자의 모든 텍스트를 하나로 합쳐서 키워드 검색
        candidate_text = " ".join(filter(None, [
            " ".join(profile.certifications or []),
            " ".join(profile.skills or []),
            profile.career_summary or "",
            " ".join(profile.projects or []),
        ])).lower()
        missing = []
        for kw in criteria.required_qualifications:
            kw = kw.strip()
            if kw and kw.lower() not in candidate_text:
                missing.append(kw)
        if missing:
            reasons.append(f"필수 자격 조건 미충족: {', '.join(missing)}")

    # 최소 전직장 연봉 (정보 없으면 통과)
    if criteria.min_last_salary is not None:
        salary = profile.last_salary
        if salary is not None and salary < criteria.min_last_salary:
            reasons.append(
                f"전직장 연봉 미달: 기준 {criteria.min_last_salary}만원 이상, 실제 {salary}만원"
            )

    # 토익 최소 점수 (정보 없으면 통과)
    if criteria.min_toeic is not None:
        score = profile.toeic_score
        if score is not None and score < criteria.min_toeic:
            reasons.append(f"토익 점수 미달: 기준 {criteria.min_toeic}점 이상, 실제 {score}점")

    # 오픽 최소 등급 (정보 없으면 통과)
    if criteria.min_opic:
        grade = (profile.opic_grade or "").upper().strip()
        min_level = OPIC_LEVELS.get(criteria.min_opic.upper(), 0)
        candidate_level = OPIC_LEVELS.get(grade, -1)
        if grade and candidate_level < min_level:
            reasons.append(f"오픽 등급 미달: 기준 {criteria.min_opic} 이상, 실제 {grade}")

    # 토익스피킹 최소 등급 (정보 없으면 통과)
    if criteria.min_toeic_speaking:
        grade = (profile.toeic_speaking_grade or "").upper().strip()
        min_level = TOEIC_SPEAKING_LEVELS.get(criteria.min_toeic_speaking.upper(), 0)
        candidate_level = TOEIC_SPEAKING_LEVELS.get(grade, -1)
        if grade and candidate_level < min_level:
            reasons.append(f"토익스피킹 등급 미달: 기준 {criteria.min_toeic_speaking} 이상, 실제 {grade}")

    return FilterResult(passed=len(reasons) == 0, reasons=reasons)
