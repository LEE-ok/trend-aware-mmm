import tempfile
import unittest
from pathlib import Path
from trend_mmm.data.validation import validate_csv

HEADER = "week,revenue,meta_spend,google_spend,naver_spend,influencer_spend\n"


class ValidationTests(unittest.TestCase):
    def check_csv(self, body):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "input.csv"
            path.write_text(body, encoding="utf-8")
            return validate_csv(path)

    def test_valid_zero_spend(self):
        self.assertEqual(self.check_csv(HEADER + "2025-01-06,100,0,1,2,3\n"), [])

    def test_missing_column(self):
        self.assertTrue(self.check_csv("week,revenue\n2025-01-06,100\n"))

    def test_invalid_numeric_values(self):
        for value in ("-1", "NaN", "inf", ""):
            with self.subTest(value=value):
                self.assertTrue(self.check_csv(HEADER + f"2025-01-06,100,{value},1,2,3\n"))

    def test_duplicate_and_gap(self):
        self.assertTrue(self.check_csv(HEADER + "2025-01-06,100,1,1,1,1\n" * 2))
        self.assertTrue(self.check_csv(HEADER + "2025-01-06,100,1,1,1,1\n2025-01-20,100,1,1,1,1\n"))

    def test_empty_data(self):
        self.assertTrue(self.check_csv(HEADER))

    def test_invalid_date(self):
        self.assertTrue(self.check_csv(HEADER + "invalid,100,1,1,1,1\n"))


if __name__ == "__main__":
    unittest.main()

