import json
import tempfile
import unittest
from pathlib import Path

from trend_mmm.workflows.chat import TOOLS
from trend_mmm.workflows.chat_eval import (
    expected_value,
    extract_numbers,
    load_cases,
    number_found,
    run_eval,
    score_answer,
)

CASES = Path(__file__).resolve().parents[1] / "configs" / "chat_eval.json"
OPTIMUM = {
    "total_spend": 16_200_000.0,
    "expected_optimum": {"shares": {"mdsp_sem": 0.514, "mdsp_vidtr": 0.311},
                         "sales_mean": 1_828_000_000.0, "sales_interval": [1_610_000_000.0, 2_050_000_000.0]},
    "s0": {"sales_mean": 1_513_000_000.0, "sales_interval": [1_371_000_000.0, 1_652_000_000.0]},
    "uplift_vs_s0": {"mean": 315_000_000.0, "interval": [143_000_000.0, 486_000_000.0], "prob_positive": 0.993},
}
UPLIFT_CASE = {
    "id": "uplift",
    "tools": [{"name": "get_optimum", "input": {"variant": "trend_bounded"}}],
    "numbers": [
        {"label": "mean", "source": "opt.json", "path": "uplift_vs_s0.mean"},
        {"label": "lo", "source": "opt.json", "path": "uplift_vs_s0.interval.0"},
        {"label": "p", "source": "opt.json", "path": "uplift_vs_s0.prob_positive", "kind": "fraction", "abs_tol": 0.001},
    ],
    "keywords_any": ["13주", "13-week"],
}
CALL = [{"name": "get_optimum", "input": {"variant": "trend_bounded"}, "is_error": False}]


class NumberParsingTests(unittest.TestCase):
    def test_units_are_applied(self):
        nums = extract_numbers("증분 +3.15억 USD, 총액 $16.2M, 1,620만 달러, 확률 99.3%")
        self.assertIn((3.15, 1e8), nums)
        self.assertIn((16.2, 1e6), nums)
        self.assertIn((1620.0, 1e4), nums)
        self.assertIn((99.3, "pct"), nums)

    def test_money_in_any_common_format(self):
        for text in ("+3.15억", "$315M", "315,000,000 USD", "0.315 billion", "3.15억 [1.43, 4.86]"):
            self.assertTrue(number_found(text, 315_000_000.0, "money"), text)
        self.assertTrue(number_found("+3.15억 [1.43, 4.86]", 143_000_000.0, "money"))
        self.assertFalse(number_found("+3.5억", 315_000_000.0, "money"))
        self.assertFalse(number_found("3.15%", 315_000_000.0, "money"))

    def test_percent_fraction_plain(self):
        self.assertTrue(number_found("sem 51.4%", 51.4, "percent"))
        self.assertFalse(number_found("sem 51.4", 51.4, "percent"))
        self.assertTrue(number_found("P = 0.993", 0.993, "fraction", abs_tol=0.001))
        self.assertTrue(number_found("확률 99.3%", 0.993, "fraction", abs_tol=0.001))
        self.assertTrue(number_found("R-hat 1.004", 1.0043, "plain", rel_tol=0, abs_tol=0.0015))
        self.assertFalse(number_found("R-hat 1.01", 1.0043, "plain", rel_tol=0, abs_tol=0.0015))

    def test_words_are_not_units(self):
        self.assertIn((5.0, None), extract_numbers("5 mdsp channels"))


class ScoringTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.art = Path(self.tmp.name)
        (self.art / "opt.json").write_text(json.dumps(OPTIMUM), encoding="utf-8")

    def tearDown(self):
        self.tmp.cleanup()

    def test_expected_values_come_from_artifacts(self):
        self.assertEqual(expected_value({"source": "opt.json", "path": "uplift_vs_s0.interval.1"}, self.art), 486e6)
        pct = expected_value({"source": "opt.json", "path": "expected_optimum.sales_mean",
                              "pct_change_from": "s0.sales_mean"}, self.art)
        self.assertAlmostEqual(pct, 100 * (1828 / 1513 - 1))
        share = expected_value({"source": "opt.json", "path": "expected_optimum.shares.mdsp_sem", "scale": 100}, self.art)
        self.assertAlmostEqual(share, 51.4)

    def test_good_answer_passes(self):
        answer = "최근 13주 합 기준 S0 대비 +3.15억 USD [1.43억, 4.86억], 증분이 양수일 확률 99.3%입니다."
        res = score_answer(UPLIFT_CASE, answer, CALL, self.art)
        self.assertEqual(res["status"], "pass", res)

    def test_annual_wording_fails_even_with_right_numbers(self):
        answer = "연간 매출이 13주 기준 +3.15억 USD [1.43, 4.86] 늘고 확률은 0.993입니다."
        res = score_answer(UPLIFT_CASE, answer, CALL, self.art)
        self.assertEqual(res["status"], "fail")
        self.assertEqual(res["forbidden_hits"], ["연간"])
        self.assertTrue(all(n["found"] for n in res["numbers"]))

    def test_wrong_number_wrong_tool_and_missing_keyword(self):
        answer = "S0 대비 +3.5억 USD [1.43, 4.86], 확률 0.993."
        res = score_answer(UPLIFT_CASE, answer, [{"name": "get_optimum", "input": {"variant": "base"}}], self.art)
        self.assertEqual(res["status"], "fail")
        self.assertEqual([n["found"] for n in res["numbers"]], [False, True, True])
        self.assertEqual([t["ok"] for t in res["tools"]], [False])
        self.assertEqual(res["keywords_missing"], ["13주|13-week"])

    def test_missing_artifact_is_skipped(self):
        case = {**UPLIFT_CASE, "numbers": [{"source": "nope.json", "path": "x"}]}
        self.assertEqual(score_answer(case, "", CALL, self.art)["status"], "skipped")

    def test_run_eval_with_fake_agent(self):
        answers = {
            "q1": {"answer": "13주 합 기준 +3.15억 USD [1.43, 4.86], 확률 99.3%.", "tool_calls": CALL},
            "q2": {"answer": "연간 +3.15억", "tool_calls": CALL},
        }

        def fake_ask(question):
            if question == "q3":
                raise RuntimeError("api down")
            return answers[question]

        cases = [{**UPLIFT_CASE, "id": q, "question": q} for q in ("q1", "q2", "q3")]
        report = run_eval(cases, self.art, fake_ask)
        self.assertEqual([r["status"] for r in report["results"]], ["pass", "fail", "fail"])
        summary = report["summary"]
        self.assertEqual((summary["cases"], summary["passed"], summary["forbidden_answers"]), (3, 1, 1))


class EvalSetTests(unittest.TestCase):
    def test_eval_set_is_well_formed(self):
        cases = load_cases(CASES)
        self.assertTrue(10 <= len(cases) <= 20)
        self.assertEqual(len({c["id"] for c in cases}), len(cases))
        tool_names = {t["name"] for t in TOOLS}
        for case in cases:
            self.assertTrue(case["question"])
            for tool in case.get("tools", []):
                self.assertIn(tool["name"], tool_names, case["id"])
            for check in case.get("numbers", []):
                self.assertIn(check.get("kind", "money"), ("money", "percent", "fraction", "plain"))
                self.assertTrue(check["source"].endswith(".json") and check["path"])


if __name__ == "__main__":
    unittest.main()
