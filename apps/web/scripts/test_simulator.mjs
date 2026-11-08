/** Node 24 built-in test runner; executes the same pure TypeScript arithmetic as the UI. */
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";
import { allocateCents, createSimulatorConfig, evaluateAllocation, initialInputs, parseBudget, parseShare, presetInputs, shareText, usd } from "../lib/simulator.ts";

const web = new URL("../", import.meta.url);
const recorded = JSON.parse(readFileSync(new URL("data/mmm-results.json", web), "utf8"));
const config = createSimulatorConfig(recorded);
const initial = initialInputs(config);
const evaluate = (shares = initial.shares, budget = initial.budget) => evaluateAllocation(config, budget, shares);
const sum = values => values.reduce((a, b) => a + b, 0n);

test("S0 uses the verified M2 contract, recent 13 weeks and the recorded budget", () => {
  assert.equal(config.budget, "16200000.00");
  assert.equal(config.weeks, 13);
  assert.deepEqual(config.channels.map(c => c.id), recorded.channels);
  assert.deepEqual(initial.shares.map(Number), recorded.s0_shares_pct);
  const result = evaluate();
  assert.equal(result.ready, true);
  assert.equal(result.sumUnits, 10000);
  assert.deepEqual(result.amounts, [418284000n, 214002000n, 155682000n, 17496000n, 814536000n]);
  assert.deepEqual(result.baseline, result.amounts);
  assert.equal(result.budgetDifference, 0n);
});

test("100%, under and over allocations are distinct; inputs never normalize", () => {
  const under = evaluate(["20", "20", "20", "8", "20"]);
  assert.equal(under.sumUnits, 8800);
  assert.equal(under.allocated, 1425600000n);
  assert.equal(under.budgetDifference, -194400000n);
  assert.equal(under.ready, false);
  const over = evaluate(["25", "25", "25", "8", "25"]);
  assert.equal(over.sumUnits, 10800);
  assert.equal(over.allocated, 1749600000n);
  assert.equal(over.budgetDifference, 129600000n);
  assert.equal(over.ready, false);
  assert.equal(evaluate(["10", "10", "25", "5", "50"]).ready, true);
});

test("strict shares reject empty, negative, out of range and non-finite numbers", () => {
  for (const text of ["", " ", "-1", "100.01", "NaN", "Infinity", "1e2", "abc", "1,0", "0.001", "1..2", "-0", "9".repeat(40)]) {
    assert.equal(parseShare(text).units, null, text);
    const result = evaluate([text, ...initial.shares.slice(1)]);
    assert.equal(result.sumUnits, null, text);
    assert.equal(result.amounts, null, text);
    assert.equal(result.ready, false, text);
  }
  assert.equal(parseShare("0").units, 0);
  assert.equal(parseShare("100").units, 10000);
  assert.equal(parseShare(".5").units, 50);
  assert.equal(parseShare("5.").units, 500);
});

test("budget rejects invalid and non-positive values without breaking share validation", () => {
  for (const text of ["", "-1", "0", "0.00", "NaN", "Infinity", "abc", "1e6", "16,200,000", "0.001", "1000000000000", "9".repeat(40)]) {
    assert.equal(parseBudget(text).cents, null, text);
    const result = evaluate(initial.shares, text);
    assert.equal(result.amounts, null, text);
    assert.equal(result.sumUnits, 10000, text);
    assert.equal(result.constraints.every(c => c.valid), true, text);
    assert.equal(result.ready, false, text);
  }
  assert.equal(parseBudget(".01").cents, 1n);
  assert.equal(parseBudget("999999999999.99").cents, 99999999999999n);
});

test("decimal shares use exact 0.01% integers without accumulated float error", () => {
  const values = ["5.10", "4.10", "31.10", "8.20", "51.50"];
  const result = evaluate(values, "100.01");
  assert.equal(result.sumUnits, 10000);
  assert.equal(result.allocated, 10001n);
  assert.equal(result.ready, true);
  assert.equal(shareText(result.sumUnits), "100.00");
  assert.deepEqual(values, ["5.10", "4.10", "31.10", "8.20", "51.50"]);
});

test("bounded preset preserves document values, 99.9% and 0.1 percentage point shortfall", () => {
  const values = presetInputs(config, "bounded");
  assert.deepEqual(values.map(Number), recorded.optimization_plans.find(p => p.id === "trend_bounded").shares_pct);
  const result = evaluate(values);
  assert.equal(result.sumUnits, 9990);
  assert.equal(result.sumUnits - 10000, -10);
  assert.equal(result.allocated, 1618380000n);
  assert.equal(result.budgetDifference, -1620000n);
  assert.equal(result.constraints.every(c => c.valid), true);
  assert.equal(result.ready, false);
  values[4] = "51.5"; // Only the user's explicit edit repairs the shortfall.
  assert.equal(evaluate(values).ready, true);
  assert.equal(config.channels[4].bounded, "51.4");
});

test("preset/reset return independent copies and reset restores both budget and S0", () => {
  const draft = initialInputs(config);
  draft.budget = "123.45";
  draft.shares[0] = "100";
  const reset = initialInputs(config);
  assert.deepEqual(reset, initial);
  assert.notEqual(reset.shares, initial.shares);
  assert.deepEqual(presetInputs(config, "s0"), initial.shares);
});

test("DM minimum and VIDDIG maximum are checked independently of the sum", () => {
  const dm = evaluate(["4.99", "10", "30", "5", "50.01"]);
  assert.equal(dm.sumUnits, 10000);
  assert.equal(dm.constraints[0].valid, false);
  assert.match(dm.constraints[0].message, /DM 최소 5.00%/);
  const video = evaluate(["5", "10", "30", "8.31", "46.69"]);
  assert.equal(video.sumUnits, 10000);
  assert.equal(video.constraints[3].valid, false);
  assert.match(video.constraints[3].message, /VIDDIG 최대 8.30%/);
  assert.equal(evaluate(["5", "10", "30", "8.3", "46.7"]).ready, true);
});

test("all M2 upper bounds apply even though input range permits 100%", () => {
  for (const i of [0, 1, 2, 4]) {
    const values = [...initial.shares];
    values[i] = "60.01";
    const result = evaluate(values);
    assert.equal(result.shares[i].error, null);
    assert.equal(result.constraints[i].valid, false);
    assert.match(result.constraints[i].message, /최대 60.00%/);
  }
});

test("constraints are supplied as configuration, not fixed in the UI arithmetic", () => {
  const changed = { ...config, channels: config.channels.map(c => ({ ...c, minUnits: 0, maxUnits: 10000 })) };
  assert.equal(evaluateAllocation(changed, "100", ["100", "0", "0", "0", "0"]).ready, true);
});

test("cent rounding preserves total and is deterministic for equal remainders", () => {
  assert.deepEqual(allocateCents(1n, [2000, 2000, 2000, 2000, 2000]), [1n, 0n, 0n, 0n, 0n]);
  assert.deepEqual(allocateCents(3n, [2000, 2000, 2000, 2000, 2000]), [1n, 1n, 1n, 0n, 0n]);
  for (const budget of [1n, 3n, 101n, 12345n, 1620000000n, 99999999999999n]) {
    for (let i = 0; i <= 100; i++) {
      const shares = [i, i * 2, i * 3, i * 4, 10000 - i * 10];
      const amounts = allocateCents(budget, shares);
      assert.equal(sum(amounts), budget);
      amounts.forEach((amount, index) => {
        const residual = amount * 10000n - budget * BigInt(shares[index]);
        assert.ok(residual > -10000n && residual < 10000n);
      });
    }
  }
});

test("cent rounding for partial allocation targets the actual sum, never the full budget", () => {
  for (const shares of [[1000, 1000, 1000, 1000, 1000], [510, 410, 3110, 820, 5140], [2500, 2500, 2500, 800, 2500]]) {
    const budget = 12345n;
    const expected = (budget * BigInt(shares.reduce((a, b) => a + b, 0)) + 5000n) / 10000n;
    assert.equal(sum(allocateCents(budget, shares)), expected);
  }
});

test("USD formatting retains cents and signs exactly, including large budgets", () => {
  assert.equal(usd(1n), "0.01 USD");
  assert.equal(usd(-1620000n), "-16,200.00 USD");
  assert.equal(usd(99999999999999n), "999,999,999,999.99 USD");
});

test("client configuration and calculations contain no model outcomes", () => {
  const serialized = JSON.stringify(config);
  for (const key of ["mean", "paired_increment", "probability_positive", "interval", "change_pct"]) {
    assert.equal(serialized.includes(`\"${key}\"`), false, key);
    assert.equal(key in evaluate(), false, key);
  }
  assert.equal(serialized.includes("20.8"), false);
});

test("static simulator disables all model functions and does not serialize M2 outcomes", () => {
  const html = readFileSync(new URL("out/simulator/index.html", web), "utf8");
  for (const name of ["예상 매출 계산", "ROAS 계산", "80% 신용구간 계산"]) {
    assert.match(html, new RegExp(`<button[^>]*disabled[^>]*>${name}</button>`));
  }
  assert.equal(html.includes("+20.8%"), false);
  assert.equal(html.includes("paired_increment"), false);
  assert.equal(html.includes("probability_positive"), false);
  for (const phrase of ["document_recorded", "99.9%", "0.1%p", "모델 결과가 아닙니다", "제약 검증", "Reset", "13주"]) assert.ok(html.includes(phrase), phrase);
});
