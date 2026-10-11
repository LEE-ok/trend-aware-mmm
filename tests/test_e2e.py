"""End-to-end CLI run on the real weekly data (skipped when the data is absent).

Sampling is deliberately tiny: this checks that every stage hands a usable
artifact to the next one, not that the posterior is any good.
Point TREND_MMM_DATA_DIR at the folder holding data_GIT.csv to run it elsewhere.
"""
import contextlib
import io
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from trend_mmm.__main__ import main
from trend_mmm.data.validation import SPEND_COLUMNS

DATA_DIR = Path(os.environ.get("TREND_MMM_DATA_DIR", Path(__file__).resolve().parents[1] / "data" / "raw"))
CSV = DATA_DIR / "data_GIT.csv"
TRENDS = DATA_DIR / "trends_google.csv"


def run(*argv) -> str:
    out = io.StringIO()
    with mock.patch.object(sys, "argv", ["trend_mmm", *map(str, argv)]), contextlib.redirect_stdout(out):
        main()
    return out.getvalue()


@unittest.skipUnless(CSV.exists(), f"real data not found at {CSV}")
class EndToEndTests(unittest.TestCase):
    def pipeline(self, out: Path, trend: tuple = ()):
        run("bayes", CSV, "--draws", 40, "--tune", 40, "--chains", 2, "--out", out, *trend)
        summary = json.loads((out / "bayes_summary.json").read_text(encoding="utf-8"))
        self.assertGreater(summary["test_metrics"]["mape"], 0.0)
        trace = out / "bayes_trace.nc"
        self.assertTrue(trace.exists())

        run("scenarios", CSV, "--trace", trace, "--out", out / "scen.json", *trend)
        scen = json.loads((out / "scen.json").read_text(encoding="utf-8"))
        self.assertEqual(len(scen), 13)
        for res in scen.values():
            self.assertLessEqual(res["sales_lo"], res["sales_mean"])
            self.assertLessEqual(res["sales_mean"], res["sales_hi"])

        run("optimize-draws", CSV, "--trace", trace, "--out", out / "opt.json", *trend)
        opt = json.loads((out / "opt.json").read_text(encoding="utf-8"))
        self.assertEqual(opt["n_draws"], 80)
        self.assertAlmostEqual(sum(opt["expected_optimum"]["shares"].values()), 1.0, places=6)
        # The expected optimum maximizes mean sales, so it cannot lose to S0 on average.
        self.assertGreaterEqual(opt["uplift_vs_s0"]["mean"], 0.0)
        self.assertAlmostEqual(opt["s0"]["sales_mean"], scen["S0"]["sales_mean"], delta=1.0)
        return summary

    def test_base_pipeline(self):
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            out = Path(tmp)
            self.assertIn("weeks: 209", run("eda", CSV))
            run("baseline", CSV, "--out", out)
            self.assertTrue((out / "baseline_model.json").exists())
            self.pipeline(out)
            run("optimize", CSV, "--summary", out / "bayes_summary.json",
                "--total", 16_200_000, "--out", out / "point.json")
            point = json.loads((out / "point.json").read_text(encoding="utf-8"))
            self.assertEqual(set(point["shares"]), set(SPEND_COLUMNS))

    @unittest.skipUnless(TRENDS.exists(), f"trend data not found at {TRENDS}")
    def test_trend_pipeline(self):
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            summary = self.pipeline(Path(tmp), trend=("--trend", TRENDS))
            self.assertEqual(summary["settings"]["aux_columns"][-1], "trend_demand")


if __name__ == "__main__":
    unittest.main()
