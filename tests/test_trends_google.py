import importlib.util
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path

HAS_PANDAS = importlib.util.find_spec("pandas") is not None


def write_trend_csv(path, weeks=8):
    start = date(2014, 8, 3)
    with open(path, "w", encoding="utf-8", newline="") as stream:
        stream.write("wk_strt_dt,sale,deals,coupons,gift\n")
        for i in range(weeks):
            day = (start + timedelta(weeks=i)).isoformat()
            stream.write(f"{day},{30 + i},{5 + i},{40 + i},{20 + 2 * i}\n")
    return path


class TrendGoogleTests(unittest.TestCase):
    def test_load_and_composite(self):
        from trend_mmm.trends.google import composite, load_series

        with tempfile.TemporaryDirectory() as tmp:
            data = load_series(write_trend_csv(Path(tmp) / "t.csv"))
            self.assertEqual(set(data), {"sale", "deals", "coupons", "gift"})
            comp = composite(data)
            self.assertEqual(len(comp), 8)
            days = [d for d, _ in comp]
            self.assertEqual(days, sorted(days))

    def test_load_rejects_missing_column(self):
        from trend_mmm.trends.google import TREND_KEYWORDS, load_series

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "t.csv"
            path.write_text("wk_strt_dt,sale\n2014-08-03,30\n", encoding="utf-8")
            with self.assertRaises(ValueError):
                load_series(path, columns=list(TREND_KEYWORDS))

    def test_zscores_standardized_on_train(self):
        from trend_mmm.trends.google import trend_zscores

        with tempfile.TemporaryDirectory() as tmp:
            write_trend_csv(Path(tmp) / "t.csv", weeks=10)
            train = [date(2014, 8, 3) + timedelta(weeks=i) for i in range(8)]
            test = [date(2014, 8, 3) + timedelta(weeks=i) for i in range(8, 10)]
            trz, tez, mu, sd = trend_zscores(train, test, Path(tmp) / "t.csv")
            self.assertEqual((len(trz), len(tez)), (8, 2))
            self.assertAlmostEqual(sum(trz) / len(trz), 0.0, places=9)
            self.assertGreater(sd, 0)

    def test_zscores_missing_week(self):
        from trend_mmm.trends.google import trend_zscores

        with tempfile.TemporaryDirectory() as tmp:
            write_trend_csv(Path(tmp) / "t.csv", weeks=4)
            with self.assertRaises(KeyError):
                trend_zscores([date(2020, 1, 5)], [], Path(tmp) / "t.csv")

    @unittest.skipUnless(HAS_PANDAS, "pandas not installed")
    def test_save_roundtrip(self):
        import pandas as pd

        from trend_mmm.trends.google import load_series, save_weekly_csv

        frame = pd.DataFrame(
            {"sale": [30, 31], "gift": [20, 25]},
            index=pd.to_datetime(["2014-08-03", "2014-08-10"]),
        )
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "t.csv"
            save_weekly_csv(frame, out)
            data = load_series(out, columns=["sale"])
            self.assertEqual(data["sale"][0], (date(2014, 8, 3), 30.0))


if __name__ == "__main__":
    unittest.main()
