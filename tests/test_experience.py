import unittest
from datetime import date

from backend.experience import compute_experience, finalize_experience, format_months
from backend.models import CandidateProfile, CareerEntry

TODAY = date(2026, 10, 28)


def C(start, end, etype="정규직", company="회사"):
    return CareerEntry(company=company, start=start, end=end, employment_type=etype)


def months(careers):
    return compute_experience(careers, TODAY)[0]


class ExperienceTest(unittest.TestCase):
    def test_gaps_are_excluded(self):
        # A 2년 + (공백 6개월) + B 3년 6개월 + C 1년 6개월 = 7년
        careers = [C("2017-03", "2019-02"), C("2019-09", "2023-02"), C("2023-03", "2024-08")]
        self.assertEqual(months(careers), 84)

    def test_overlap_counted_once(self):
        # 2020.01~2021.12(24개월)와 2021.01~2022.12(24개월)가 12개월 겹침 → 36개월
        self.assertEqual(months([C("2020-01", "2021-12"), C("2021-01", "2022-12")]), 36)

    def test_nested_period(self):
        self.assertEqual(months([C("2018-01", "2022-12"), C("2019-01", "2019-06")]), 60)

    def test_start_and_end_months_inclusive(self):
        self.assertEqual(months([C("2019-03", "2021-02")]), 24)
        self.assertEqual(months([C("2024-05", "2024-05")]), 1)

    def test_current_job_uses_today(self):
        self.assertEqual(months([C("2025-11", "현재")]), 12)
        self.assertEqual(months([C("2025-11", "재직중")]), 12)

    def test_various_date_formats(self):
        self.assertEqual(months([C("2019.3", "2019년 5월")]), 3)
        self.assertEqual(months([C("2019/03", "2019-05")]), 3)

    def test_year_only_is_mid_year_and_flagged(self):
        total, estimated, details = compute_experience([C("2019", "2026")], TODAY)
        self.assertEqual(total, 84)          # 2019.07 ~ 2026.06
        self.assertTrue(estimated)
        self.assertEqual(details[0]["note"], "기간 일부 추정")

    def test_intern_and_part_time_excluded(self):
        careers = [C("2018-01", "2018-06", "인턴"), C("2018-07", "2018-12", "아르바이트"), C("2019-01", "2019-12")]
        total, _, details = compute_experience(careers, TODAY)
        self.assertEqual(total, 12)
        self.assertFalse(details[0]["included"])
        self.assertEqual(details[0]["months"], 6)   # 기간 자체는 표시용으로 남김

    def test_contract_and_freelance_included(self):
        self.assertEqual(months([C("2020-01", "2020-12", "계약직"), C("2021-01", "2021-12", "프리랜서")]), 24)

    def test_only_interns_gives_zero_not_unknown(self):
        self.assertEqual(months([C("2023-01", "2023-06", "인턴")]), 0)

    def test_invalid_or_unreadable_periods_skipped(self):
        total, _, details = compute_experience([C("2022-05", "2021-01"), C("모름", "현재"), C("2020-01", "2020-12")], TODAY)
        self.assertEqual(total, 12)
        self.assertEqual(details[0]["note"], "기간 오류")
        self.assertEqual(details[1]["note"], "기간 확인 불가")

    def test_future_end_capped_at_today(self):
        self.assertEqual(months([C("2026-01", "2027-12")]), 10)

    def test_no_readable_period_falls_back_to_ai(self):
        p = CandidateProfile(total_experience_years=7, careers=[{"company": "A", "start": None, "end": None}])
        finalize_experience(p, TODAY)
        self.assertEqual(p.total_experience_years, 7)
        self.assertIsNone(p.experience_months)
        self.assertIn("AI 추정", p.experience_note)

    def test_finalize_overrides_ai_total(self):
        p = CandidateProfile(total_experience_years=8.9,
                             careers=[{"company": "A", "start": "2017-09", "end": "현재"},
                                      {"company": "B", "start": "2015-01", "end": "2017-08"}])
        finalize_experience(p, TODAY)
        self.assertEqual(p.experience_months, 142)   # 11년 10개월
        self.assertEqual(p.total_experience_years, 11.83)
        self.assertEqual(format_months(p.experience_months), "11년 10개월")

    def test_format_months(self):
        self.assertEqual(format_months(84), "7년")
        self.assertEqual(format_months(5), "5개월")
        self.assertEqual(format_months(None), "미확인")


if __name__ == "__main__":
    unittest.main()
