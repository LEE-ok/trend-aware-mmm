import tempfile
import unittest
from pathlib import Path

from trend_mmm.trends.collect import aggregate_weekly, clean_docs, collect_csv, week_start_sunday
from datetime import date

HEADER = "source_url,published_at,collected_at,category,score\n"
ROW = "https://example.com/a,2014-08-04,2014-08-05,seasonal-demand,0.6\n"


class TrendsTests(unittest.TestCase):
    def write_csv(self, tmp, body):
        path = Path(tmp) / "docs.csv"
        path.write_text(body, encoding="utf-8")
        return path

    def test_collect_and_aggregate(self):
        with tempfile.TemporaryDirectory() as tmp:
            docs = collect_csv(self.write_csv(tmp, HEADER + ROW))
            self.assertEqual(len(docs), 1)
            self.assertEqual(docs[0]["score"], 0.6)
            weekly = aggregate_weekly(clean_docs(docs))
            self.assertEqual(weekly["2014-08-03"], {"n_docs": 1, "mean_score": 0.6})

    def test_week_start_sunday(self):
        self.assertEqual(week_start_sunday(date(2014, 8, 4)), date(2014, 8, 3))
        self.assertEqual(week_start_sunday(date(2014, 8, 3)), date(2014, 8, 3))

    def test_rejects_bad_schema(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ValueError):
                collect_csv(self.write_csv(tmp, "source_url,published_at\nhttps://x,2014-08-04\n"))

    def test_rejects_bad_score(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ValueError):
                collect_csv(
                    self.write_csv(tmp, HEADER + "https://x,2014-08-04,2014-08-05,c,1.5\n")
                )

    def test_clean_drops_empty(self):
        docs = [
            {
                "source_url": "",
                "published_at": date(2014, 8, 4),
                "collected_at": date(2014, 8, 5),
                "category": "c",
                "score": 0.5,
            },
            {
                "source_url": "https://x",
                "published_at": date(2014, 8, 4),
                "collected_at": date(2014, 8, 5),
                "category": "c",
                "score": 0.5,
            },
        ]
        self.assertEqual(len(clean_docs(docs)), 1)


if __name__ == "__main__":
    unittest.main()
