"""도메인 적합도 계산.

AI는 경력마다 JD 도메인 요소(예: 의료·병리, IT·AI)별로 직접/간접/없음만 고르고,
점수는 여기서 계산한다. 요소마다 여러 경력 중 가장 좋은 판정을 쓰므로
병원 경력 + IT 경력처럼 융합 도메인을 나눠 갖춘 후보도 제대로 인정된다.
"""
MIN_MONTHS = 12          # 이 기간 미만이면 한 단계 낮춤 (직접 → 간접, 간접 → 없음)
UNKNOWN_MONTHS = MIN_MONTHS   # 기간을 못 읽은 경력은 기준 충족으로 간주


def normalize_verdict(v) -> str:
    v = str(v or "")
    if "직접" in v:
        return "직접"
    if "간접" in v:
        return "간접"
    return "없음"


def _key(s) -> str:
    return "".join(str(s).split()).lower()


def _lookup(verdicts: dict, element: str):
    """AI가 요소 이름을 살짝 바꿔 쓴 경우(공백 차이 등)도 찾는다."""
    if element in verdicts:
        return verdicts[element]
    k = _key(element)
    for name, v in verdicts.items():
        if _key(name) == k or k in _key(name) or _key(name) in k:
            return v
    return None


def compute_domain_score(elements, judgments, career_months, career_included):
    """→ (도메인 점수 0~100, 요소별 판정 목록).

    elements: JD 도메인 요소 목록
    judgments: AI 응답 [{"career": 1, "verdicts": {"의료·병리": "직접", ...}}, ...] (career는 1부터)
    career_months / career_included: 경력별 기간(개월, 모르면 None)과 경력 연수 포함 여부
    """
    if not elements:
        return 100, []      # 평가할 도메인이 없으면 모두 동일하게 취급

    per_career = {}
    for j in judgments or []:
        try:
            idx = int(j.get("career")) - 1
        except (TypeError, ValueError, AttributeError):
            continue
        if 0 <= idx < len(career_months) and isinstance(j.get("verdicts"), dict):
            per_career[idx] = j["verdicts"]

    breakdown, credits = [], []
    for el in elements:
        direct = indirect = 0
        for idx, verdicts in per_career.items():
            if not career_included[idx]:
                continue    # 인턴·아르바이트 등 경력 연수에서 뺀 경력은 도메인에서도 제외
            months = career_months[idx] if career_months[idx] is not None else UNKNOWN_MONTHS
            v = normalize_verdict(_lookup(verdicts, el))
            if v == "직접":
                direct += months
            elif v == "간접":
                indirect += months
        if direct >= MIN_MONTHS:
            credit, label, months = 1.0, "직접", direct
        elif direct > 0 or indirect >= MIN_MONTHS:
            credit, label, months = 0.5, "간접", direct or indirect
        else:
            credit, label, months = 0.0, "없음", 0
        credits.append(credit)
        breakdown.append({"element": el, "verdict": label, "months": months, "credit": credit})

    return round(sum(credits) / len(credits) * 100), breakdown
