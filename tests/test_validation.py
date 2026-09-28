import tempfile
import unittest
from pathlib import Path
from trend_mmm.data.validation import validate_csv

HEADER = "wk_strt_dt,sales,mdsp_dm,mdsp_so,mdsp_vidtr,mdsp_viddig,mdsp_sem\n"
ROW = "2014-08-03,72051457,678410,0,216725,45397,355954\n"


class ValidationTests(unittest.TestCase):
    def check_csv(self, body):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "input.csv"
            path.write_text(body, encoding="utf-8")
            return validate_csv(path)

    def test_valid_zero_spend(self):
        self.assertEqual(self.check_csv(HEADER + ROW), [])

    def test_extra_columns_allowed(self):
        body = (
            "wk_strt_dt,sales,mdsp_dm,mdsp_so,mdsp_vidtr,mdsp_viddig,mdsp_sem,"
            "mdsp_on,hldy_Black Friday,seas_prd_1\n"
            "2014-08-03,72051457,678410,0,216725,45397,355954,61364,0,1\n"
        )
        self.assertEqual(self.check_csv(body), [])

    def test_missing_column(self):
        self.assertTrue(self.check_csv("wk_strt_dt,sales\n2014-08-03,100\n"))

    def test_missing_core_spend(self):
        body = "wk_strt_dt,sales,mdsp_dm,mdsp_so,mdsp_vidtr,mdsp_viddig\n2014-08-03,100,1,1,1,1\n"
        self.assertTrue(self.check_csv(body))

    def test_invalid_numeric_values(self):
        for value in ("-1", "NaN", "inf", ""):
            with self.subTest(value=value):
                self.assertTrue(
                    self.check_csv(HEADER + f"2014-08-03,100,{value},1,1,1,1\n")
                )

    def test_duplicate_and_gap(self):
        self.assertTrue(self.check_csv(HEADER + ROW * 2))
        self.assertTrue(
            self.check_csv(HEADER + ROW + "2014-08-17,72051457,678410,0,216725,45397,355954\n")
        )

    def test_empty_data(self):
        self.assertTrue(self.check_csv(HEADER))

    def test_invalid_date(self):
        self.assertTrue(self.check_csv(HEADER + "invalid,100,1,1,1,1,1\n"))


if __name__ == "__main__":
    unittest.main()
