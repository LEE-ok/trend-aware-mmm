import recorded from "@/data/mmm-results.json";

export const results = recorded;
export const fixed = (value: number, digits = 2) => value.toFixed(digits);
export const signed = (value: number, digits = 1) => `${value > 0 ? "+" : ""}${fixed(value, digits)}`;
export const interval = (values: number[]) => `[${values.map(v => fixed(v)).join(", ")}]`;
export type Scenario = (typeof recorded.scenario_models)[number]["scenarios"][number];
