import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path

from trend_mmm.data.preprocess import (
    control_matrix,
    discover_columns,
    holiday_flags,
    load_weekly,
    pearson,
    season_flags,
    standardize,
    summarize,
    time_split,
)

HEADER = "wk_strt_dt,sales,mdsp_dm,mdsp_so,mdsp_vidtr,mdsp_viddig,mdsp_sem\n"


def make_csv(weeks):
    body = HEADER
    start = date(2014, 8, 3)
    for i in range(weeks):
        day = (start + timedelta(weeks=i)).isoformat()
        body += f"{day},{100 + i},{10 + i},0,{20 + i},{5},{30 + i}\n"
    return body


class PreprocessTests(unittest.TestCase):
    def write_csv(self, tmp, body):
        path = Path(tmp) / "input.csv"
        path.write_text(body, encoding="utf-8")
        return path

    def test_load_and_split(self):
        with tempfile.TemporaryDirectory() as tmp:
            rows = load_weekly(self.write_csv(tmp, make_csv(30)))
            self.assertEqual(len(rows), 30)
            self.assertEqual(rows[0]["spends"]["mdsp_dm"], 10.0)
            train, test = time_split(rows, test_weeks=6)
            self.assertEqual((len(train), len(test)), (24, 6))
            self.assertLess(train[-1]["date"], test[0]["date"])

    def test_load_rejects_invalid(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ValueError):
                load_weekly(self.write_csv(tmp, "wk_strt_dt,sales\n2014-08-03,100\n"))

    def test_split_needs_more_rows(self):
        with tempfile.TemporaryDirectory() as tmp:
            rows = load_weekly(self.write_csv(tmp, make_csv(4)))
            with self.assertRaises(ValueError):
                time_split(rows, test_weeks=4)

    def test_summarize_and_pearson(self):
        with tempfile.TemporaryDirectory() as tmp:
            rows = load_weekly(self.write_csv(tmp, make_csv(10)))
            info = summarize(rows)
            self.assertEqual(info["n_weeks"], 10)
            self.assertIn("mdsp_sem", info["channels"])
            xs = [r["spends"]["mdsp_dm"] for r in rows]
            ys = [r["sales"] for r in rows]
            self.assertGreater(pearson(xs, ys), 0.99)
            self.assertEqual(pearson([1.0] * 5, [1.0, 2.0, 3.0, 4.0, 5.0]), 0.0)

    def test_standardize(self):
        z, mean, sd = standardize([1.0, 2.0, 3.0])
        self.assertAlmostEqual(mean, 2.0)
        self.assertAlmostEqual(sum(z) / len(z), 0.0)
        z0, _, sd0 = standardize([5.0, 5.0])
        self.assertEqual(sd0, 0.0)
        self.assertEqual(z0, [0.0, 0.0])

    def test_controls_holidays_seasons(self):
        rows = [
            {"extras": {"me_gas_dpg": "3.0", "me_ics_all": "80", "st_ct": "700"}},
            {"extras": {"me_gas_dpg": "4.0", "me_ics_all": "90", "st_ct": "720"}},
        ]
        cm = control_matrix(rows)
        self.assertEqual(cm["columns"], ["me_gas_dpg", "me_ics_all", "st_ct"])
        self.assertEqual(len(cm["values"]), 2)
        flags = holiday_flags(
            {"hldy_Christmas Day": "1", "hldy_Black Friday": "0"},
            ["hldy_Christmas Day", "hldy_Black Friday"],
        )
        self.assertEqual(flags, {"year_end": 1.0, "other_holiday": 0.0})
        flags = holiday_flags(
            {"hldy_Black Friday": "1"}, ["hldy_Christmas Day", "hldy_Black Friday"]
        )
        self.assertEqual(flags, {"year_end": 0.0, "other_holiday": 1.0})
        seas = season_flags({"seas_prd_1": "1", "seas_prd_2": "0"}, ["seas_prd_1", "seas_prd_2"])
        self.assertEqual(seas, {"seas_prd_1": 1.0, "seas_prd_2": 0.0})

    def test_discover_columns(self):
        with tempfile.TemporaryDirectory() as tmp:
            body = (
                "wk_strt_dt,sales,mdsp_dm,mdsp_so,mdsp_vidtr,mdsp_viddig,mdsp_sem,"
                "me_gas_dpg,hldy_Black Friday,seas_prd_1\n"
                "2014-08-03,100,1,1,1,1,1,3.5,0,1\n"
            )
            found = discover_columns(self.write_csv(tmp, body))
            self.assertEqual(found["controls"], ["me_gas_dpg"])
            self.assertEqual(found["holidays"], ["hldy_Black Friday"])
            self.assertEqual(found["seasons"], ["seas_prd_1"])


if __name__ == "__main__":
    unittest.main()
