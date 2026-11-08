"use client";

import { useState } from "react";
import { Bar, BarChart, CartesianGrid, Legend, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import type { Channel, Distribution } from "@/lib/dashboard-data";

const axis = { fontSize: 11, fill: "#64748b" };
const keys = ["min", "q25", "median", "q75", "max"] as const;
const labels = ["최솟값", "Q1", "중앙값", "Q3", "최댓값"];

export function SpendChart({ channels }: { channels: Channel[] }) {
  const data = channels.map(c => ({ name: c.id.replace("mdsp_", "").toUpperCase(), spend: c.spend.total / 1e6 }));
  return <div className="h-72 min-w-0" role="img" aria-label="5개 채널의 전체 기간 누적 광고비. 단위 백만 USD. 아래 표에 동일 수치 제공.">
    <ResponsiveContainer width="100%" height="100%" initialDimension={{ width: 600, height: 288 }}>
      <BarChart data={data} margin={{ top: 10, right: 12, bottom: 26, left: 0 }} accessibilityLayer>
        <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#e2e8f0" />
        <XAxis dataKey="name" tick={axis} label={{ value: "광고 채널", position: "bottom", offset: 6, fontSize: 11, fill: "#475569" }} />
        <YAxis tick={axis} width={46} label={{ value: "백만 USD", angle: -90, position: "insideLeft", fontSize: 10, fill: "#475569" }} />
        <Tooltip formatter={v => [`${Number(v).toLocaleString("ko-KR", { maximumFractionDigits: 2 })} 백만 USD`, "누적 광고비"]} />
        <Bar dataKey="spend" fill="#0f766e" radius={[5, 5, 0, 0]} maxBarSize={54} isAnimationActive={false} />
      </BarChart>
    </ResponsiveContainer>
  </div>;
}

export function CorrelationChart({ channels }: { channels: Channel[] }) {
  const data = channels.map(c => ({ name: c.id.replace("mdsp_", "").toUpperCase(), Pearson: c.pearson, Spearman: c.spearman }));
  return <div className="h-80 min-w-0" role="img" aria-label="매출과 채널 광고비의 Pearson 선형 상관 및 Spearman 순위 상관 비교. 범위 -1부터 1. 아래 표 제공.">
    <ResponsiveContainer width="100%" height="100%" initialDimension={{ width: 600, height: 320 }}>
      <BarChart data={data} margin={{ top: 5, right: 10, bottom: 20, left: 0 }} accessibilityLayer>
        <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#e2e8f0" />
        <XAxis dataKey="name" tick={axis} />
        <YAxis domain={[-1, 1]} tick={axis} width={46} label={{ value: "상관계수", angle: -90, position: "insideLeft", fontSize: 10, fill: "#475569" }} />
        <ReferenceLine y={0} stroke="#94a3b8" /><Tooltip formatter={v => Number(v).toFixed(3)} />
        <Legend wrapperStyle={{ fontSize: 12, paddingTop: 12 }} />
        <Bar dataKey="Pearson" name="Pearson · 선형" fill="#0f766e" maxBarSize={26} radius={[3, 3, 0, 0]} isAnimationActive={false} />
        <Bar dataKey="Spearman" name="Spearman · 순위" fill="#4f46e5" maxBarSize={26} radius={[3, 3, 0, 0]} isAnimationActive={false} />
      </BarChart>
    </ResponsiveContainer>
  </div>;
}

export function DistributionChart({ stats, label }: { stats: Distribution; label: string }) {
  const data = keys.map((key, i) => ({ name: labels[i], value: stats[key] / 1e6 }));
  return <div className="h-64 min-w-0" role="img" aria-label={`${label} 5수치 분포 요약. 최솟값, Q1, 중앙값, Q3, 최댓값. 단위 백만 USD. 빈도 그래프가 아니며 아래 표 제공.`}>
    <ResponsiveContainer width="100%" height="100%" initialDimension={{ width: 600, height: 256 }}>
      <BarChart data={data} margin={{ top: 6, right: 10, bottom: 25, left: 0 }} accessibilityLayer>
        <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#e2e8f0" />
        <XAxis dataKey="name" tick={axis} interval={0} label={{ value: "분포 요약 통계", position: "bottom", fontSize: 11, offset: 6, fill: "#475569" }} />
        <YAxis tick={axis} width={46} label={{ value: "백만 USD", angle: -90, position: "insideLeft", fontSize: 10, fill: "#475569" }} />
        <Tooltip formatter={v => [`${Number(v).toLocaleString("ko-KR", { maximumFractionDigits: 3 })} 백만 USD`, label]} />
        <Bar dataKey="value" fill="#475569" maxBarSize={46} radius={[4, 4, 0, 0]} isAnimationActive={false} />
      </BarChart>
    </ResponsiveContainer>
  </div>;
}

export function ChannelDistribution({ channels }: { channels: Channel[] }) {
  const [id, setId] = useState(channels[0].id);
  const selected = channels.find(c => c.id === id)!;
  return <>
    <label htmlFor="distribution-channel" className="text-xs font-medium text-slate-700">광고 채널 선택</label>
    <select id="distribution-channel" value={id} onChange={e => setId(e.target.value)} className="mb-4 ml-3 max-w-full rounded-lg border border-slate-300 bg-white p-2 text-sm">
      {channels.map(c => <option key={c.id} value={c.id}>{c.label}</option>)}
    </select>
    <DistributionChart stats={selected.spend} label={selected.label} />
  </>;
}
