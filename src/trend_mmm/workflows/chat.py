"""Chat agent over existing MMM results: LangGraph loop + Claude tool calls.

The model never computes numbers itself. Every figure comes from a tool that
reads an artifact the CLI already produced (summary, scenarios, optimum) or
calls an existing module (posterior what-if, trend document search).
Graph: model -> (tool_use?) -> tools -> model ... -> END.
anthropic / langgraph are imported lazily, like workflows/graph.py.
"""
import json
import os
from functools import lru_cache
from pathlib import Path
from types import SimpleNamespace

from trend_mmm.data.validation import SPEND_COLUMNS

MODEL = "claude-haiku-5-5"
MAX_TOKENS = 16000
OPTIMUM_FILES = {
    "base": "optimum_draws.json",
    "trend": "optimum_draws_trend.json",
    "trend_bounded": "optimum_draws_trend_bounded.json",
}

SYSTEM = """You answer questions about a Bayesian marketing mix model (MMM) for a US retailer: \
weekly sales explained by five media channels (mdsp_dm direct mail, mdsp_so social, mdsp_vidtr TV video, \
mdsp_viddig digital video, mdsp_sem search), each passed through adstock (carryover) and Hill saturation \
(diminishing returns), plus controls, holidays, season and an optional search-trend variable.

Your readers are a two-person student team and the people they present to. They need answers they can \
defend, so every number you give must come from a tool result in this conversation. If no tool provides \
a number, say it is not available rather than estimating it.

The model output is a posterior distribution, not a single truth, so report an interval whenever the \
tool gives one (they are 80% credible intervals), and when two options have overlapping intervals \
describe the direction without declaring a winner. The paired uplift from get_optimum is the right basis \
for comparing the optimum with the current plan S0, because it compares both plans draw by draw. \
Mention an extrapolation flag whenever a result has one: it means a channel's weekly spend is outside \
the range seen in the data, so the estimate is less trustworthy. Take whether two sales intervals overlap from \
the tool's sales_intervals_overlap field rather than judging it yourself.

All money is US dollars over a 13-week horizon: sales are on the order of 1.3 to 1.8 billion USD and the \
total media budget is about 16.2 million USD. Keep the currency as USD and do not convert it to won. \
Channel shares are fractions of that budget.

Answer in the language the user writes in, briefly and in plain prose. A short table is fine when \
comparing several scenarios or channels."""

TOOLS = [
    {
        "name": "get_model_summary",
        "description": (
            "Fit quality and posterior parameters of the base Bayesian MMM: train/test MAPE, RMSE, "
            "direction accuracy, max R-hat (convergence; below 1.01 is the project's bar), and the posterior "
            "mean and sd of beta (channel strength), decay (adstock carryover) and alpha (Hill shape) per "
            "channel. Use for questions about accuracy, convergence or which channel is strong or uncertain."
        ),
        "input_schema": {"type": "object", "properties": {}, "additionalProperties": False},
    },
    {
        "name": "get_scenarios",
        "description": (
            "Predefined budget scenarios with total budget fixed. S0 is the current split; S1-S4 move 5, 10 or "
            "15 points of budget from direct mail to TV video (S1), search (S2), digital video (S3) or social "
            "(S4), e.g. S1_10. Returns mean sales, 80% interval, change vs S0, marginal ROAS and extrapolation "
            "flags for each. model='trend' gives the adopted trend-aware model, 'base' the model without it."
        ),
        "input_schema": {
            "type": "object",
            "properties": {"model": {"type": "string", "enum": ["base", "trend"]}},
            "required": ["model"],
            "additionalProperties": False,
        },
    },
    {
        "name": "get_optimum",
        "description": (
            "Budget allocation that maximizes expected sales over all posterior draws, with its sales interval, "
            "the paired uplift over S0 (mean, 80% interval, probability the uplift is positive) and how much the "
            "optimal share of each channel varies across draws. variant: 'base' (model without trend), 'trend' "
            "(adopted model, may extrapolate), 'trend_bounded' (adopted model with direct mail >= 5% and "
            "digital video capped at its observed maximum; the one to recommend)."
        ),
        "input_schema": {
            "type": "object",
            "properties": {"variant": {"type": "string", "enum": list(OPTIMUM_FILES)}},
            "required": ["variant"],
            "additionalProperties": False,
        },
    },
    {
        "name": "evaluate_allocation",
        "description": (
            "What-if for a custom budget split on the base model: evaluates the split on every posterior draw "
            "and returns mean sales, 80% interval, per-channel ROAS, extrapolation flags and the paired uplift "
            "over the current split S0 (mean, 80% interval, probability it is positive). shares are "
            "fractions of the total budget for all five channels and must sum to 1. total_budget defaults to "
            "the last 13 weeks' actual spend. Use when the user proposes their own split."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "shares": {
                    "type": "object",
                    "properties": {ch: {"type": "number"} for ch in SPEND_COLUMNS},
                    "required": list(SPEND_COLUMNS),
                    "additionalProperties": False,
                },
                "total_budget": {"type": "number"},
            },
            "required": ["shares"],
            "additionalProperties": False,
        },
    },
    {
        "name": "search_trend_docs",
        "description": (
            "Semantic search over collected market-trend documents (news, search-interest notes). Returns "
            "source, category, collection date and distance (smaller is closer). Pass available_before "
            "(YYYY-MM-DD) when the question is about a past date, so later documents are not leaked."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "available_before": {"type": "string"},
            },
            "required": ["query"],
            "additionalProperties": False,
        },
    },
]


def load_env(path: str | Path = ".env") -> None:
    """Read KEY=VALUE lines into os.environ without overriding what is already set."""
    path = Path(path)
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        key, sep, value = line.strip().partition("=")
        if sep and key and not key.startswith("#"):
            os.environ.setdefault(key.strip(), value.strip().strip("'\""))


class ChatContext:
    """Where the tools read from. All paths are produced by the existing CLI."""

    def __init__(self, artifacts="artifacts", data="data/raw/data_GIT.csv", store="artifacts/chroma"):
        self.artifacts = Path(artifacts)
        self.data = str(data)
        self.store = str(store)

    def _json(self, name: str) -> dict:
        path = self.artifacts / name
        if not path.exists():
            raise FileNotFoundError(f"{name} not found in {self.artifacts}. Run the matching CLI command first.")
        return json.loads(path.read_text(encoding="utf-8"))

    def get_model_summary(self) -> dict:
        s = self._json("bayes_summary.json")
        params = {k: v for k, v in s["posterior"]["params"].items() if k != "gamma"}
        return {
            "settings": {k: s["settings"][k] for k in ("draws", "tune", "chains", "test_weeks")},
            "train_metrics": s["train_metrics"],
            "test_metrics": s["test_metrics"],
            "max_rhat": s["posterior"]["max_rhat"],
            "params": params,
            "assumptions": s["assumptions"],
        }

    def get_scenarios(self, model: str) -> dict:
        results = self._json({"base": "scenario_results.json", "trend": "scenario_trend_mean.json"}[model])
        base = results["S0"]["sales_mean"]
        return {
            name: {
                "shares": r["shares"],
                "sales_mean": r["sales_mean"],
                "sales_interval_80": [r["sales_lo"], r["sales_hi"]],
                "vs_s0_pct": round(100 * (r["sales_mean"] / base - 1), 1),
                "marginal_roas": r["marginal_roas"],
                "extrapolated_channels": [f["channel"] for f in r["extrapolation_flags"]],
            }
            for name, r in results.items()
        }

    def get_optimum(self, variant: str) -> dict:
        from trend_mmm.simulation.evaluate import BASE_SHARES

        opt = self._json(OPTIMUM_FILES[variant])
        opt["s0"]["shares"] = BASE_SHARES
        opt["sales_intervals_overlap"] = _overlap(opt["expected_optimum"]["sales_interval"], opt["s0"]["sales_interval"])
        return opt

    @lru_cache(maxsize=1)
    def _posterior(self):
        from trend_mmm.__main__ import _forecast_context

        args = SimpleNamespace(
            path=self.data, trace=str(self.artifacts / "bayes_trace.nc"),
            weeks=13, trend=None, trend_level="mean",
        )
        return _forecast_context(args)

    def evaluate_allocation(self, shares: dict, total_budget: float | None = None) -> dict:
        import numpy as np

        from trend_mmm.optimization.allocate import _params, channel_sales
        from trend_mmm.simulation.evaluate import BASE_SHARES, INTERVAL_HI, INTERVAL_LO, evaluate

        if min(shares.values()) < 0 or abs(sum(shares.values()) - 1.0) > 1e-3:
            raise ValueError(f"shares must be non-negative and sum to 1, got sum {sum(shares.values()):.4f}.")
        _, total, aux_mean, ranges, draws, ec50 = self._posterior()
        bundle = {"channels": list(SPEND_COLUMNS), "ec50": ec50}
        total = total_budget or total
        res = evaluate(draws, bundle, total, shares, 13, aux_mean, ranges)
        s0 = evaluate(draws, bundle, total, BASE_SHARES, 13, aux_mean, ranges)
        # Paired per draw, same as optimize-draws: intercept and aux cancel.
        params = _params(draws, bundle)
        uplift = (
            channel_sales(params, [shares[ch] for ch in SPEND_COLUMNS], total, 13)
            - channel_sales(params, [BASE_SHARES[ch] for ch in SPEND_COLUMNS], total, 13)
        ).sum(axis=1)
        interval = [res["sales_lo"], res["sales_hi"]]
        s0_interval = [s0["sales_lo"], s0["sales_hi"]]
        return {
            "total_spend": total,
            "sales_mean": res["sales_mean"],
            "sales_interval_80": interval,
            "roas": res["roas"],
            "extrapolation_flags": res["extrapolation_flags"],
            "s0": {"shares": BASE_SHARES, "sales_mean": s0["sales_mean"], "sales_interval_80": s0_interval},
            "sales_intervals_overlap": _overlap(interval, s0_interval),
            "uplift_vs_s0": {
                "mean": float(uplift.mean()),
                "interval_80": [float(np.percentile(uplift, INTERVAL_LO)), float(np.percentile(uplift, INTERVAL_HI))],
                "prob_positive": float((uplift > 0).mean()),
            },
            "n_draws": len(draws),
        }

    def search_trend_docs(self, query: str, available_before: str | None = None) -> list:
        from trend_mmm.retrieval.store import TrendStore

        if not Path(self.store).exists():
            raise FileNotFoundError(f"No document store at {self.store}. Run retrieve-index first.")
        return TrendStore(self.store).search(query, available_before, None, 5)


def _overlap(a: list, b: list) -> bool:
    return a[0] <= b[1] and b[0] <= a[1]


def run_tool(ctx: ChatContext, name: str, tool_input: dict) -> tuple[str, bool]:
    """Execute one tool call. Returns (content, is_error); errors go back to the model as text."""
    if name not in {t["name"] for t in TOOLS}:
        return f"Unknown tool: {name}", True
    try:
        return json.dumps(getattr(ctx, name)(**tool_input), ensure_ascii=False, default=str), False
    except Exception as exc:  # the model can read the message and retry or explain
        return f"{type(exc).__name__}: {exc}", True


def build_chat_graph(client, ctx: ChatContext):
    """model -> tools -> model loop, ending when the model stops asking for tools."""
    try:
        from langgraph.graph import END, StateGraph
    except ImportError as exc:
        raise ImportError("Install langgraph for workflows.") from exc

    def node_model(state: dict) -> dict:
        response = client.messages.create(
            model=MODEL, max_tokens=MAX_TOKENS, system=SYSTEM, tools=TOOLS,
            messages=state["messages"],
        )
        messages = [*state["messages"], {"role": "assistant", "content": response.content}]
        return {**state, "messages": messages, "stop_reason": response.stop_reason}

    def node_tools(state: dict) -> dict:
        results, calls = [], list(state.get("tool_calls", []))
        for block in state["messages"][-1]["content"]:
            if block.type != "tool_use":
                continue
            content, is_error = run_tool(ctx, block.name, block.input)
            calls.append({"name": block.name, "input": block.input, "is_error": is_error})
            results.append(
                {"type": "tool_result", "tool_use_id": block.id, "content": content, "is_error": is_error}
            )
        # All results of one assistant turn go back in a single user message.
        return {**state, "messages": [*state["messages"], {"role": "user", "content": results}], "tool_calls": calls}

    graph = StateGraph(dict)
    graph.add_node("model", node_model)
    graph.add_node("tools", node_tools)
    graph.set_entry_point("model")
    graph.add_conditional_edges(
        "model", lambda s: "tools" if s["stop_reason"] == "tool_use" else "end", {"tools": "tools", "end": END}
    )
    graph.add_edge("tools", "model")
    return graph.compile()


def ask(question: str, ctx: ChatContext, history: list | None = None, client=None) -> dict:
    """One user turn. Returns {answer, messages, tool_calls}; pass messages back as history."""
    if client is None:
        import anthropic

        load_env()
        client = anthropic.Anthropic()
    state = build_chat_graph(client, ctx).invoke(
        {"messages": [*(history or []), {"role": "user", "content": question}]}
    )
    last = state["messages"][-1]["content"]
    answer = "".join(b.text for b in last if b.type == "text")
    if state["stop_reason"] == "refusal":
        answer = answer or "The model declined to answer this request."
    elif state["stop_reason"] == "max_tokens":
        answer += "\n[answer cut off at the output limit]"
    return {"answer": answer, "messages": state["messages"], "tool_calls": state.get("tool_calls", [])}
