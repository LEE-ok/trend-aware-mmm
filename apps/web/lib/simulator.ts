/** Budget arithmetic only. No model, revenue, ROAS or posterior evaluation. */
export const CHANNEL_IDS = ["DM", "SO", "VIDTR", "VIDDIG", "SEM"] as const;
export type Preset = "s0" | "bounded";
export type SimulatorChannel = {
  id: string;
  s0: string;
  bounded: string;
  minUnits: number;
  maxUnits: number;
};
export type SimulatorConfig = {
  budget: string;
  weeks: number;
  channels: SimulatorChannel[];
};
type RecordedAllocation = {
  budget_million_usd: number;
  weeks: number;
  channels: string[];
  s0_shares_pct: number[];
  optimization_plans: { id: string; shares_pct: number[]; bounds_pct: number[][] }[];
};

const ZERO = BigInt(0);
const ONE = BigInt(1);
const HUNDRED = BigInt(100);
const DENOMINATOR = BigInt(10000);
const decimal = /^(?:\d+(?:\.\d{0,2})?|\.\d{1,2})$/;

/** Strict decimal input; never treats blank, exponent notation or NaN as zero. */
function hundredths(text: string): bigint | null {
  if (text.length > 32 || !decimal.test(text)) return null;
  const [whole, fraction = ""] = text.split(".");
  return BigInt(whole || "0") * HUNDRED + BigInt(fraction.padEnd(2, "0"));
}

export function parseShare(text: string): { units: number | null; error: string | null } {
  const value = hundredths(text);
  if (value === null) return { units: null, error: "0~100%의 숫자를 소수 둘째 자리까지 입력하세요. 빈 값·지수 표기는 사용할 수 없습니다." };
  if (value > DENOMINATOR) return { units: null, error: "입력 범위는 0~100%입니다." };
  return { units: Number(value), error: null };
}

export function parseBudget(text: string): { cents: bigint | null; error: string | null } {
  const value = hundredths(text);
  if (value === null || value <= ZERO) return { cents: null, error: "총 광고예산은 0보다 큰 USD 숫자를 소수 둘째 자리까지 입력하세요." };
  if (value > BigInt("99999999999999")) return { cents: null, error: "총 광고예산은 999,999,999,999.99 USD 이하여야 합니다." };
  return { cents: value, error: null };
}

export function createSimulatorConfig(recorded: RecordedAllocation): SimulatorConfig {
  const bounded = recorded.optimization_plans.find(plan => plan.id === "trend_bounded");
  if (!bounded || recorded.channels.join() !== CHANNEL_IDS.join() || recorded.s0_shares_pct.length !== 5 || bounded.shares_pct.length !== 5 || bounded.bounds_pct.length !== 5) {
    throw new Error("Simulator allocation contract is invalid");
  }
  const toUnits = (value: number) => {
    const parsed = parseShare(String(value));
    if (parsed.units === null) throw new Error("Recorded share is invalid");
    return parsed.units;
  };
  const budget = (recorded.budget_million_usd * 1e6).toFixed(2);
  if (parseBudget(budget).cents === null) throw new Error("Recorded budget is invalid");
  return {
    budget,
    weeks: recorded.weeks,
    channels: recorded.channels.map((id, i) => {
      const bounds = bounded.bounds_pct[i];
      if (bounds.length !== 2 || bounds[0] > bounds[1]) throw new Error("Recorded bounds are invalid");
      toUnits(recorded.s0_shares_pct[i]);
      toUnits(bounded.shares_pct[i]);
      return { id, s0: String(recorded.s0_shares_pct[i]), bounded: String(bounded.shares_pct[i]), minUnits: toUnits(bounds[0]), maxUnits: toUnits(bounds[1]) };
    }),
  };
}

export function presetInputs(config: SimulatorConfig, preset: Preset) {
  return config.channels.map(channel => preset === "s0" ? channel.s0 : channel.bounded);
}

export function initialInputs(config: SimulatorConfig) {
  return { budget: config.budget, shares: presetInputs(config, "s0") };
}

export const shareText = (units: number) => (units / 100).toFixed(2);
export const signedShareText = (units: number) => `${units > 0 ? "+" : ""}${shareText(units)}`;

/** Format integer cents without conversion to floating point. */
export function usd(cents: bigint): string {
  const magnitude = cents < ZERO ? -cents : cents;
  const whole = (magnitude / HUNDRED).toString().replace(/\B(?=(\d{3})+(?!\d))/g, ",");
  return `${cents < ZERO ? "-" : ""}${whole}.${(magnitude % HUNDRED).toString().padStart(2, "0")} USD`;
}
export const signedUsd = (cents: bigint) => `${cents > ZERO ? "+" : ""}${usd(cents)}`;

/**
 * Largest remainder to cents. The target is budget * actual share sum, NOT
 * budget * a normalized allocation. A 99.9% draft remains 99.9% funded.
 * Ties use document channel order. Share values never change.
 */
export function allocateCents(budget: bigint, shares: number[]): bigint[] {
  if (budget <= ZERO || shares.length !== 5 || shares.some(value => !Number.isInteger(value) || value < 0 || value > 10000)) {
    throw new Error("Invalid arithmetic allocation input");
  }
  const products = shares.map(value => budget * BigInt(value));
  const allocated = products.map(value => value / DENOMINATOR);
  const totalProduct = products.reduce((sum, value) => sum + value, ZERO);
  const target = (totalProduct + DENOMINATOR / BigInt(2)) / DENOMINATOR;
  const remainder = Number(target - allocated.reduce((sum, value) => sum + value, ZERO));
  const order = products.map((value, i) => ({ i, remainder: value % DENOMINATOR }))
    .sort((a, b) => a.remainder === b.remainder ? a.i - b.i : a.remainder > b.remainder ? -1 : 1);
  for (let i = 0; i < remainder; i++) allocated[order[i].i] += ONE;
  return allocated;
}

export function evaluateAllocation(config: SimulatorConfig, budgetInput: string, shareInputs: string[]) {
  const budget = parseBudget(budgetInput);
  const shares = config.channels.map((_, i) => parseShare(shareInputs[i] ?? ""));
  const validShares = shares.every(share => share.units !== null);
  const units = shares.map(share => share.units ?? 0);
  const sumUnits = validShares ? units.reduce((sum, value) => sum + value, 0) : null;
  const constraints = config.channels.map((channel, i) => {
    if (shares[i].units === null) return { valid: false, message: "입력값 확인 필요" };
    const value = units[i];
    if (value < channel.minUnits) return { valid: false, message: `${channel.id} 최소 ${shareText(channel.minUnits)}% 위반` };
    if (value > channel.maxUnits) return { valid: false, message: `${channel.id} 최대 ${shareText(channel.maxUnits)}% 위반` };
    return { valid: true, message: "충족" };
  });
  const inputValid = budget.cents !== null && validShares;
  const amounts = inputValid ? allocateCents(budget.cents!, units) : null;
  const baseline = budget.cents !== null ? allocateCents(budget.cents, config.channels.map(channel => parseShare(channel.s0).units!)) : null;
  const allocated = amounts ? amounts.reduce((sum, value) => sum + value, ZERO) : null;
  return {
    budget, shares, units, sumUnits, constraints, amounts, baseline, allocated,
    budgetDifference: allocated !== null && budget.cents !== null ? allocated - budget.cents : null,
    ready: inputValid && sumUnits === 10000 && constraints.every(result => result.valid),
  };
}
