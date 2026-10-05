import importlib.util
import tempfile
import unittest
from pathlib import Path

HAS_CHROMA = importlib.util.find_spec("chromadb") is not None
HAS_LANGGRAPH = importlib.util.find_spec("langgraph") is not None

DOCS = [
    {
        "source_url": "https://example.com/a",
        "published_at": "2014-08-04",
        "collected_at": "2014-08-05",
        "category": "social-buzz",
        "score": 0.8,
        "text": "viral back to school shopping haul",
    },
    {
        "source_url": "https://example.com/b",
        "published_at": "2014-08-12",
        "collected_at": "2014-08-13",
        "category": "promotion",
        "score": 0.3,
        "text": "labor day sale preview circular",
    },
]


@unittest.skipUnless(HAS_CHROMA, "chromadb not installed")
class RetrievalTests(unittest.TestCase):
    def make_store(self, tmp):
        from trend_mmm.retrieval.store import TrendStore, fake_embed

        return TrendStore(None, embed_fn=fake_embed)

    def test_add_and_count(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = self.make_store(tmp)
            self.assertEqual(store.add(DOCS), 2)
            self.assertEqual(store.count(), 2)

    def test_search_returns_ranked(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = self.make_store(tmp)
            store.add(DOCS)
            hits = store.search("shopping haul", n=2)
            self.assertEqual(len(hits), 2)
            self.assertIn("source_url", hits[0])

    def test_available_before_filters(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = self.make_store(tmp)
            store.add(DOCS)
            hits = store.search("sale", available_before="2014-08-06", n=5)
            urls = [h["source_url"] for h in hits]
            self.assertIn("https://example.com/a", urls)
            self.assertNotIn("https://example.com/b", urls)

    def test_category_filter(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = self.make_store(tmp)
            store.add(DOCS)
            hits = store.search("sale", category="promotion", n=5)
            self.assertTrue(all(h["category"] == "promotion" for h in hits))


@unittest.skipUnless(HAS_LANGGRAPH, "langgraph not installed")
class WorkflowTests(unittest.TestCase):
    def test_pipeline_docs_csv(self):
        from trend_mmm.workflows.graph import run_trends_pipeline

        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "docs.csv"
            src.write_text(
                "source_url,published_at,collected_at,category,score\n"
                "https://example.com/a,2014-08-04,2014-08-05,social-buzz,0.8\n"
                "https://example.com/b,2014-08-12,2014-08-13,promotion,0.3\n",
                encoding="utf-8",
            )
            out = str(Path(tmp) / "weekly.csv")
            state = run_trends_pipeline(str(src), out)
            self.assertIn("2014-08-03", state["weekly"])
            self.assertTrue(Path(out).exists())

    def test_pipeline_abort_empty(self):
        from trend_mmm.workflows.graph import run_trends_pipeline

        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "docs.csv"
            src.write_text(
                "source_url,published_at,collected_at,category,score\n",
                encoding="utf-8",
            )
            with self.assertRaises(ValueError):
                run_trends_pipeline(str(src), str(Path(tmp) / "weekly.csv"))


if __name__ == "__main__":
    unittest.main()
