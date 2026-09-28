import unittest

from trend_mmm.simulation.scenarios import (
    apply_shifts,
    check_extrapolation,
    historical_ranges,
    scenario_spends,
)

ROWS = [
    {"spends": {"mdsp_dm": 100.0, "mdsp_so": 50.0}},
    {"spends": {"mdsp_dm": 200.0, "mdsp_so": 150.0}},
]
CHS = ("mdsp_dm", "mdsp_so")


class ScenarioTests(unittest.TestCase):
    def test_ranges(self):
        ranges = historical_ranges(ROWS, CHS)
        self.assertEqual(ranges["mdsp_dm"], (100.0, 200.0))

    def test_apply_shifts(self):
        base = {"mdsp_dm": 0.6, "mdsp_so": 0.4}
        out = apply_shifts(base, {"mdsp_dm": -0.1, "mdsp_so": 0.1})
        self.assertAlmostEqual(out["mdsp_dm"], 0.5)
        self.assertAlmostEqual(sum(out.values()), 1.0)

    def test_shifts_must_sum_zero(self):
        with self.assertRaises(ValueError):
            apply_shifts({"mdsp_dm": 0.6, "mdsp_so": 0.4}, {"mdsp_dm": -0.1})

    def test_shifts_no_negative(self):
        with self.assertRaises(ValueError):
            apply_shifts({"mdsp_dm": 0.6, "mdsp_so": 0.4}, {"mdsp_dm": -0.7, "mdsp_so": 0.7})

    def test_scenario_spends_uniform(self):
        out = scenario_spends(1000.0, {"mdsp_dm": 0.6, "mdsp_so": 0.4}, 2)
        self.assertEqual(out["mdsp_dm"], [300.0, 300.0])
        self.assertEqual(out["mdsp_so"], [200.0, 200.0])

    def test_extrapolation_flag(self):
        ranges = historical_ranges(ROWS, CHS)
        ok = scenario_spends(500.0, {"mdsp_dm": 0.6, "mdsp_so": 0.4}, 2)
        self.assertEqual(check_extrapolation(ok, ranges), [])
        bad = {"mdsp_dm": [500.0], "mdsp_so": [100.0]}
        flags = check_extrapolation(bad, ranges)
        self.assertEqual(len(flags), 1)
        self.assertEqual(flags[0]["channel"], "mdsp_dm")


if __name__ == "__main__":
    unittest.main()
