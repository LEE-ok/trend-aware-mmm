import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from trend_mmm.data.validation import SPEND_COLUMNS
from trend_mmm.workflows.chat import TOOLS, ChatContext, ask, run_tool

try:
    import langgraph  # noqa: F401
    HAS_LANGGRAPH = True
except ImportError:
    HAS_LANGGRAPH = False

SCENARIOS = {
    name: {"shares": {}, "sales_mean": mean, "sales_lo": mean - 1, "sales_hi": mean + 1,
           "marginal_roas": {}, "extrapolation_flags": flags}
    for name, mean, flags in (("S0", 100.0, []), ("S3_10", 110.0, [{"channel": "mdsp_viddig"}]))
}


class FakeClient:
    """Asks for one tool, then answers with whatever the tool returned."""

    def __init__(self, tool_name, tool_input):
        self.requests = []
        self.messages = self
        self._call = SimpleNamespace(type="tool_use", id="t1", name=tool_name, input=tool_input)

    def create(self, **kwargs):
        self.requests.append(kwargs)
        if len(self.requests) == 1:
            return SimpleNamespace(content=[self._call], stop_reason="tool_use")
        result = kwargs["messages"][-1]["content"][0]
        text = SimpleNamespace(type="text", text=f"error={result['is_error']} {result['content']}")
        return SimpleNamespace(content=[text], stop_reason="end_turn")


class ChatToolTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        (Path(self.tmp.name) / "scenario_results.json").write_text(json.dumps(SCENARIOS), encoding="utf-8")
        self.ctx = ChatContext(artifacts=self.tmp.name, store=str(Path(self.tmp.name) / "missing"))

    def tearDown(self):
        self.tmp.cleanup()

    def test_every_tool_has_a_handler(self):
        for tool in TOOLS:
            self.assertTrue(callable(getattr(self.ctx, tool["name"])))

    def test_scenarios_tool_reports_change_and_flags(self):
        content, is_error = run_tool(self.ctx, "get_scenarios", {"model": "base"})
        self.assertFalse(is_error)
        data = json.loads(content)
        self.assertEqual(data["S3_10"]["vs_s0_pct"], 10.0)
        self.assertEqual(data["S3_10"]["extrapolated_channels"], ["mdsp_viddig"])

    def test_tool_errors_are_returned_not_raised(self):
        for name, tool_input in (
            ("get_model_summary", {}),
            ("search_trend_docs", {"query": "sale"}),
            ("evaluate_allocation", {"shares": {ch: 0.5 for ch in SPEND_COLUMNS}}),
            ("no_such_tool", {}),
        ):
            content, is_error = run_tool(self.ctx, name, tool_input)
            self.assertTrue(is_error, name)
            self.assertTrue(content)

    @unittest.skipUnless(HAS_LANGGRAPH, "langgraph not installed")
    def test_graph_runs_tool_and_feeds_result_back(self):
        client = FakeClient("get_scenarios", {"model": "base"})
        turn = ask("S3_10 어때?", self.ctx, client=client)
        self.assertEqual(len(client.requests), 2)
        self.assertEqual([c["name"] for c in turn["tool_calls"]], ["get_scenarios"])
        self.assertIn("error=False", turn["answer"])
        self.assertIn("mdsp_viddig", turn["answer"])
        self.assertEqual([m["role"] for m in turn["messages"]], ["user", "assistant", "user", "assistant"])


if __name__ == "__main__":
    unittest.main()
