"""Quantitative check of chatbot answers against the artifacts the tools read.

Each case in configs/chat_eval.json has a question plus what a correct answer needs:
tools that must be called, numbers (looked up in artifacts/*.json at run time, never
hard-coded) with a tolerance, keywords, and forbidden terms (e.g. calling a 13-week
total "annual"). score_answer() is pure; run_eval() calls the real chat agent, so it
is meant to be run locally with an API key.
"""
import json
import re
from pathlib import Path

# Applied to every case: horizon and currency mistakes seen in manual checks.
FORBIDDEN = ("연간", "annual", "yearly", "per year", "억 원", "억원", "만원", "KRW")
DEFAULT_REL_TOL = 0.02  # answers round to ~3 significant figures

UNITS = {
    "%p": "pct", "%": "pct",
    "십억": 1e9, "천만": 1e7, "백만": 1e6, "억": 1e8, "만": 1e4, "천": 1e3,
    "billion": 1e9, "million": 1e6, "thousand": 1e3, "bn": 1e9, "b": 1e9, "m": 1e6, "k": 1e3,
}
MONEY_SCALES = (1.0, 1e3, 1e4, 1e6, 1e8, 1e9)
_NUM = re.compile(
    r"(\d[\d,]*(?:\.\d+)?)\s*(%p|%|십억|천만|백만|억|만|천|billion|million|thousand|bn|b|m|k)?(?![a-z])",
    re.IGNORECASE,
)


def extract_numbers(text: str) -> list[tuple[float, object]]:
    """[(value, unit)] where unit is a multiplier, 'pct', or None for a bare number.

    Signs are dropped (ranges like 1.43-4.86 would otherwise read as negative);
    expected values are compared by magnitude.
    """
    out = []
    for num, unit in _NUM.findall(text):
        try:
            value = float(num.replace(",", ""))
        except ValueError:
            continue
        out.append((value, UNITS[unit.lower()] if unit else None))
    return out


def _close(a: float, b: float, rel_tol: float, abs_tol: float) -> bool:
    return abs(a - b) <= max(rel_tol * abs(b), abs_tol)


def number_found(text: str, expected: float, kind: str, rel_tol: float = DEFAULT_REL_TOL, abs_tol: float = 0.0) -> bool:
    """Whether the answer states `expected`.

    kind: 'money' (any scale; a bare number may carry the unit of a nearby one, e.g. "3.15억 [1.43, 4.86]"),
    'percent' (needs %), 'fraction' (0.993 or 99.3%), 'plain' (bare number, e.g. R-hat).
    """
    target = abs(expected)
    for value, unit in extract_numbers(text):
        if kind == "money":
            scales = MONEY_SCALES if unit is None else (() if unit == "pct" else (unit,))
            if any(_close(value * s, target, rel_tol, abs_tol) for s in scales):
                return True
        elif kind == "percent":
            if unit == "pct" and _close(value, target, rel_tol, abs_tol):
                return True
        elif kind == "fraction":
            if unit is None and _close(value, target, rel_tol, abs_tol):
                return True
            if unit == "pct" and _close(value, 100 * target, rel_tol, 100 * abs_tol):
                return True
        elif kind == "plain":
            if unit is None and _close(value, target, rel_tol, abs_tol):
                return True
        else:
            raise ValueError(f"Unknown number kind: {kind}")
    return False


def lookup(data, path: str):
    """Dotted path into nested dicts/lists: 'uplift_vs_s0.interval.0'."""
    for key in path.split("."):
        data = data[int(key)] if isinstance(data, list) else data[key]
    return data


def expected_value(check: dict, artifacts: Path) -> float:
    """Value of one number check, read from the artifact it names.

    pct_change_from: another path in the same file -> 100 * (value / ref - 1), e.g. +20.8% vs S0.
    scale: multiplier, e.g. 100 to state a share (0.514) as a percent (51.4).
    """
    data = json.loads((artifacts / check["source"]).read_text(encoding="utf-8"))
    value = float(lookup(data, check["path"]))
    if "pct_change_from" in check:
        value = 100 * (value / float(lookup(data, check["pct_change_from"])) - 1)
    return value * check.get("scale", 1.0)


def _tool_called(spec: dict, calls: list) -> bool:
    for call in calls:
        if call["name"] != spec["name"]:
            continue
        given = call.get("input") or {}
        if all(key in given for key in spec.get("input_has", [])) and all(
            _matches(given.get(k), v) for k, v in spec.get("input", {}).items()
        ):
            return True
    return False


def _matches(given, want) -> bool:
    if isinstance(want, dict):
        return isinstance(given, dict) and all(_matches(given.get(k), v) for k, v in want.items())
    if isinstance(want, (int, float)) and isinstance(given, (int, float)):
        return abs(given - want) <= 1e-3
    return given == want


def score_answer(case: dict, answer: str, tool_calls: list, artifacts: Path) -> dict:
    """Score one answer. pass = right tools, every number found, keywords present, nothing forbidden."""
    artifacts = Path(artifacts)
    missing = [c["source"] for c in case.get("numbers", []) if not (artifacts / c["source"]).exists()]
    if missing:
        return {"id": case["id"], "status": "skipped", "reason": f"missing artifacts: {sorted(set(missing))}"}
    lowered = answer.lower()
    tools = [{"name": t["name"], "ok": _tool_called(t, tool_calls)} for t in case.get("tools", [])]
    numbers = []
    for check in case.get("numbers", []):
        expected = expected_value(check, artifacts)
        ok = number_found(
            answer, expected, check.get("kind", "money"),
            check.get("rel_tol", DEFAULT_REL_TOL), check.get("abs_tol", 0.0),
        )
        numbers.append({"label": check.get("label", check["path"]), "expected": expected, "found": ok})
    keywords_missing = [k for k in case.get("keywords_all", []) if k.lower() not in lowered]
    any_groups = case.get("keywords_any", [])
    any_groups = [any_groups] if any_groups and isinstance(any_groups[0], str) else any_groups
    keywords_missing += ["|".join(g) for g in any_groups if not any(k.lower() in lowered for k in g)]
    forbidden = [w for w in (*FORBIDDEN, *case.get("forbidden", [])) if w.lower() in lowered]
    passed = (
        all(t["ok"] for t in tools) and all(n["found"] for n in numbers)
        and not keywords_missing and not forbidden
    )
    return {
        "id": case["id"],
        "status": "pass" if passed else "fail",
        "tools": tools,
        "numbers": numbers,
        "keywords_missing": keywords_missing,
        "forbidden_hits": forbidden,
    }


def summarize(results: list) -> dict:
    scored = [r for r in results if r["status"] != "skipped"]
    nums = [n for r in scored for n in r["numbers"]]
    tools = [t for r in scored for t in r["tools"]]
    return {
        "cases": len(results),
        "scored": len(scored),
        "passed": sum(r["status"] == "pass" for r in scored),
        "skipped": len(results) - len(scored),
        "number_hit_rate": sum(n["found"] for n in nums) / len(nums) if nums else None,
        "tool_hit_rate": sum(t["ok"] for t in tools) / len(tools) if tools else None,
        "forbidden_answers": sum(bool(r["forbidden_hits"]) for r in scored),
    }


def load_cases(path: str | Path) -> list:
    return json.loads(Path(path).read_text(encoding="utf-8"))["cases"]


def run_eval(cases: list, artifacts: str | Path, ask_fn) -> dict:
    """Ask every question fresh (no history) and score it. ask_fn(question) -> {answer, tool_calls}."""
    results = []
    for case in cases:
        try:
            turn = ask_fn(case["question"])
        except Exception as exc:  # one failed call should not lose the other results
            results.append({"id": case["id"], "status": "fail", "error": f"{type(exc).__name__}: {exc}",
                            "tools": [], "numbers": [], "keywords_missing": [], "forbidden_hits": []})
            continue
        result = score_answer(case, turn["answer"], turn["tool_calls"], Path(artifacts))
        result["question"] = case["question"]
        result["answer"] = turn["answer"]
        results.append(result)
    return {"summary": summarize(results), "results": results}
