"""LangGraph trends pipeline: collect -> clean -> aggregate -> save.

Deterministic nodes (no LLM): the graph owns execution order and failure
handling per docs/architecture.md. langgraph is imported lazily; tests
skip when it is missing.
"""
import csv
from pathlib import Path


def _node_collect(state: dict) -> dict:
    source = state["source"]
    if state.get("kind", "docs-csv") == "google-fetch":
        from trend_mmm.trends.google import fetch

        frame = fetch()
        docs = [
            {
                "source_url": f"google-trends:{col}",
                "published_at": day.date().isoformat(),
                "collected_at": day.date().isoformat(),
                "category": "search-interest",
                "score": float(value) / 100.0,
                "text": f"{col} search interest {float(value):.0f}",
            }
            for col in frame.columns
            for day, value in zip(frame.index, frame[col])
        ]
    else:
        from trend_mmm.trends.collect import collect_csv

        docs = collect_csv(source)
        for doc in docs:
            doc.setdefault("text", "")
    return {**state, "docs": docs}


def _node_clean(state: dict) -> dict:
    from trend_mmm.trends.collect import clean_docs

    return {**state, "docs": clean_docs(state["docs"])}


def _node_aggregate(state: dict) -> dict:
    from trend_mmm.trends.collect import aggregate_weekly

    return {**state, "weekly": aggregate_weekly(state["docs"])}


def _node_save(state: dict) -> dict:
    out = Path(state["out"])
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(["wk_strt_dt", "n_docs", "mean_score"])
        for week in sorted(state["weekly"]):
            cell = state["weekly"][week]
            writer.writerow([week, cell["n_docs"], round(cell["mean_score"], 4)])
    return {**state, "saved": str(out)}


def build_graph():
    """collect -> clean -> aggregate -> save, aborting on empty intake."""
    try:
        from langgraph.graph import END, StateGraph
    except ImportError as exc:
        raise ImportError("Install langgraph for workflows.") from exc

    graph = StateGraph(dict)
    graph.add_node("collect", _node_collect)
    graph.add_node("clean", _node_clean)
    graph.add_node("aggregate", _node_aggregate)
    graph.add_node("save", _node_save)
    graph.set_entry_point("collect")

    def has_docs(state: dict) -> str:
        return "clean" if state.get("docs") else "abort"

    graph.add_conditional_edges("collect", has_docs, {"clean": "clean", "abort": END})
    graph.add_edge("clean", "aggregate")
    graph.add_edge("aggregate", "save")
    graph.add_edge("save", END)
    return graph.compile()


def run_trends_pipeline(source: str, out: str, kind: str = "docs-csv") -> dict:
    """Execute the pipeline. Returns the final state (weekly, saved)."""
    app = build_graph()
    return app.invoke({"source": source, "out": out, "kind": kind})
