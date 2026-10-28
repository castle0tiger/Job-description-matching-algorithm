import unittest

from backend.domain import compute_domain_score

ELEMENTS = ["의료·병리", "IT·AI·디지털"]


def J(career, **verdicts):
    return {"career": career, "verdicts": {k.replace("_", "·"): v for k, v in verdicts.items()}}


def score(judgments, months, included=None):
    return compute_domain_score(ELEMENTS, judgments, months, included or [True] * len(months))


class DomainTest(unittest.TestCase):
    def test_hospital_plus_it_covers_both_elements(self):
        s, b = score([J(1, 의료_병리="직접", IT_AI_디지털="없음"), J(2, 의료_병리="없음", IT_AI_디지털="직접")], [36, 48])
        self.assertEqual(s, 100)
        self.assertEqual([x["verdict"] for x in b], ["직접", "직접"])

    def test_single_field_gets_half(self):
        s, _ = score([J(1, 의료_병리="직접", IT_AI_디지털="없음")], [96])
        self.assertEqual(s, 50)

    def test_indirect_is_half_credit(self):
        s, b = score([J(1, 의료_병리="간접", IT_AI_디지털="없음")], [60])
        self.assertEqual(s, 25)
        self.assertEqual(b[0]["verdict"], "간접")

    def test_short_direct_steps_down_to_indirect(self):
        s, b = score([J(1, 의료_병리="직접", IT_AI_디지털="없음")], [8])
        self.assertEqual(b[0]["verdict"], "간접")
        self.assertEqual(s, 25)

    def test_short_indirect_steps_down_to_none(self):
        s, _ = score([J(1, 의료_병리="간접", IT_AI_디지털="없음")], [8])
        self.assertEqual(s, 0)

    def test_short_jobs_in_same_field_are_summed(self):
        # IT 회사 8개월 두 곳 = 16개월 → 직접 인정
        s, b = score([J(1, 의료_병리="없음", IT_AI_디지털="직접"), J(2, 의료_병리="없음", IT_AI_디지털="직접")], [8, 8])
        self.assertEqual(b[1]["verdict"], "직접")
        self.assertEqual(s, 50)

    def test_excluded_careers_ignored(self):
        s, _ = score([J(1, 의료_병리="직접", IT_AI_디지털="직접")], [24], included=[False])
        self.assertEqual(s, 0)

    def test_unknown_duration_treated_as_enough(self):
        s, _ = score([J(1, 의료_병리="직접", IT_AI_디지털="없음")], [None])
        self.assertEqual(s, 50)

    def test_element_name_variations_matched(self):
        s, _ = score([{"career": "1", "verdicts": {"의료 · 병리": "직접(병원)", "IT·AI·디지털": "직접"}}], [24])
        self.assertEqual(s, 100)

    def test_malformed_judgments_ignored(self):
        s, _ = score([{"career": "x"}, {"career": 9, "verdicts": {}}, "bad"], [24])
        self.assertEqual(s, 0)

    def test_no_elements_is_neutral(self):
        self.assertEqual(compute_domain_score([], [], [], []), (100, []))


if __name__ == "__main__":
    unittest.main()
