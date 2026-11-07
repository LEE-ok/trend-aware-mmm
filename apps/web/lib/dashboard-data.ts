import aggregates from "@/data/dashboard-aggregates.json";

export const dashboard = aggregates;
export type Distribution = typeof aggregates.sales;
export type Channel = (typeof aggregates.channels)[number];
export const periodLabel = `${aggregates.period.start} ~ ${aggregates.period.end}`;
export const number = (value: number, digits = 0) => new Intl.NumberFormat("ko-KR", { maximumFractionDigits: digits }).format(value);
export const percent = (value: number) => `${number(value * 100, 1)}%`;
