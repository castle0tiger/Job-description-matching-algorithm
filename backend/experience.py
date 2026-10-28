"""이력서 근무 기간 → 순 경력 계산.

AI는 회사별 시작·종료 연월만 추출하고, 합산은 여기서 한다.
- 회사 사이 공백 기간은 자연히 제외된다.
- 기간이 겹치면(병행 근무) 한 번만 센다.
- 시작 달과 종료 달을 모두 포함한다 (2019.03~2021.02 = 24개월).
- 인턴·아르바이트는 경력 연수에서 제외한다.
"""
import re
from datetime import date

EXCLUDED_TYPES = ("인턴", "아르바이트", "알바")
_CURRENT = ("현재", "재직", "present", "now", "current")


def _month_index(year: int, month: int) -> int:
    return year * 12 + (month - 1)


def parse_point(text, today: date, is_end: bool):
    """'2019-03' / '2019.3' / '2019년 3월' / '2019' / '현재' → (월 인덱스, 추정 여부). 못 읽으면 None."""
    if text is None:
        return None
    t = str(text).strip().lower()
    if not t:
        return None
    if is_end and any(k in t for k in _CURRENT):
        return _month_index(today.year, today.month), False
    m = re.search(r"(\d{4})\D{0,3}(\d{1,2})?", t)
    if not m:
        return None
    year = int(m.group(1))
    if m.group(2) and 1 <= int(m.group(2)) <= 12:
        return _month_index(year, int(m.group(2))), False
    # 연도만 있으면 연중으로 계산: 시작 7월·종료 6월 (2019~2026 → 정확히 7년)
    return _month_index(year, 6 if is_end else 7), True


def is_excluded(employment_type) -> bool:
    return any(k in (employment_type or "") for k in EXCLUDED_TYPES)


def compute_experience(careers, today: date = None):
    """경력 목록 → (순 경력 개월 수 또는 None, 추정 포함 여부, 경력별 상세).

    경력별 상세는 careers와 같은 순서의 dict 목록:
    {"company", "months"(해당 경력 기간, 못 읽으면 None), "included"(합산 포함 여부), "note"}.
    읽을 수 있는 기간이 하나도 없으면 None을 돌려 호출 측이 AI 추정값을 쓰게 한다.
    """
    today = today or date.today()
    now = _month_index(today.year, today.month)
    intervals, details, estimated = [], [], False
    all_excluded = bool(careers)

    for c in careers:
        d = {"company": c.company, "months": None, "included": False, "note": ""}
        start, end = parse_point(c.start, today, False), parse_point(c.end, today, True)
        excluded = is_excluded(c.employment_type)
        all_excluded = all_excluded and excluded
        if start is None or end is None:
            d["note"] = "기간 확인 불가"
        else:
            (s, s_est), (e, e_est) = start, end
            e = min(e, now)
            if e < s:
                d["note"] = "기간 오류"
            else:
                d["months"] = e - s + 1
                if excluded:
                    d["note"] = f"경력 연수 제외 ({c.employment_type})"
                else:
                    d["included"] = True
                    intervals.append((s, e))
                    if s_est or e_est:
                        d["note"] = "기간 일부 추정"
                        estimated = True
        details.append(d)

    if not intervals:
        return (0 if all_excluded else None), estimated, details

    intervals.sort()
    total, (cur_s, cur_e) = 0, intervals[0]
    for s, e in intervals[1:]:
        if s <= cur_e + 1:          # 겹치거나 바로 이어지면 하나의 구간으로 합침
            cur_e = max(cur_e, e)
        else:                       # 공백 → 이전 구간 확정
            total += cur_e - cur_s + 1
            cur_s, cur_e = s, e
    total += cur_e - cur_s + 1
    return total, estimated, details


def format_months(months) -> str:
    if months is None:
        return "미확인"
    y, m = divmod(int(months), 12)
    if y and m:
        return f"{y}년 {m}개월"
    return f"{y}년" if y else f"{m}개월"


def finalize_experience(profile, today: date = None):
    """AI가 추출한 경력 목록으로 순 경력을 계산해 profile에 반영한다."""
    months, estimated, details = compute_experience(profile.careers or [], today)
    profile.career_details = details
    if months is not None:
        profile.experience_months = months
        profile.total_experience_years = round(months / 12, 2)
        profile.experience_note = "기간 일부 추정" if estimated else ""
    elif profile.total_experience_years is not None:
        profile.experience_note = "AI 추정 (근무 기간 확인 불가)"
    return profile
