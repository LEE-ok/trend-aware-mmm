"use client";

import { useState } from "react";
import { DataTable, Panel } from "@/components/analysis-ui";
import { Extrapolation, ModelSelect } from "@/components/mmm-shared";
import { fixed, interval, results, signed, type Scenario } from "@/lib/mmm-results";

function IntervalChart({ rows }: { rows: Scenario[] }) {
  const min = 0;
  const max = 22;
  const x = (value: number) => 105 + (value - min) / (max - min) * 565;
  return <div className="max-w-full overflow-x-auto" role="region" aria-label="시나리오 구간 차트 · 작은 화면에서 가로 스크롤" tabIndex={0}><svg viewBox="0 0 720 540" className="w-full min-w-[640px]" role="img" aria-label="시나리오별 평균 매출과 80% 신용구간. 단위 억 USD. 아래 대체 표 제공.">
    <title>시나리오별 예상 매출 평균(점)과 80% 신용구간(선), 억 USD. 아래 대체 표 제공.</title>
    {[0, 5, 10, 15, 20].map(tick => <g key={tick}><line x1={x(tick)} x2={x(tick)} y1="20" y2="495" stroke="#e2e8f0" /><text x={x(tick)} y="518" textAnchor="middle" fontSize="13" fill="#475569">{tick}</text></g>)}
    {rows.map((row, index) => { const y = 38 + index * 36; const color = row.extrapolation ? "#b45309" : "#0f766e"; return <g key={row.id}>
      <text x="10" y={y + 4} fontSize="13" fill={color}>{row.id}{row.extrapolation ? " ⚠" : ""}</text>
      <line x1={x(row.interval[0])} x2={x(row.interval[1])} y1={y} y2={y} stroke={color} strokeWidth="3" />
      {row.interval.map((v, i) => <line key={i} x1={x(v)} x2={x(v)} y1={y - 6} y2={y + 6} stroke={color} strokeWidth="2" />)}
      <circle cx={x(row.mean)} cy={y} r="5" fill={color}><title>{`${row.id}: ${fixed(row.mean)} 억 USD, 80% ${interval(row.interval)}`}</title></circle>
    </g>; })}
    <text x="390" y="538" textAnchor="middle" fontSize="13" fill="#475569">13주 매출 합계 (억 USD)</text>
  </svg></div>;
}

export function ScenarioResults() {
  const [id, setId] = useState(results.default_scenario_model);
  const model = results.scenario_models.find(model => model.id === id)!;
  return <>
    <ModelSelect id="scenario-model" label="시나리오 모델 선택" value={id} onChange={setId} options={results.scenario_models} />
    <div className="space-y-6" aria-live="polite">
      <div className="rounded-xl border border-amber-200 bg-amber-50 p-4 text-sm leading-7 text-amber-950" role="note">⚠ S3_10·S3_15는 VIDDIG 광고비가 과거 관측 범위를 넘는 외삽 시나리오입니다. 추정 신뢰도가 낮아 예산 권고에 주의가 필요합니다.</div>
      <Panel title={`${model.label} · S0~S4 비교`} note="점은 평균, 선은 80% 신용구간입니다. 황색과 ⚠는 외삽을 뜻합니다. 공통 축을 사용하며 문서 순서로 표시합니다.">
        <IntervalChart rows={model.scenarios} />
        <p className="mt-4 text-sm leading-7 text-slate-600">모든 시나리오의 구간이 S0 구간과 겹칩니다. 점추정 순서는 확정적인 성과 순위가 아닙니다. VIDTR 이동이 유리한 방향이라는 정도로 해석하며, 실제 성과를 보장하지 않습니다.</p>
      </Panel>
      <Panel title="시나리오 상세 · 차트 대체 표" note="S1: DM→VIDTR · S2: DM→SEM · S3: DM→VIDDIG · S4: DM→SO. 이동폭은 총예산 비중의 %p입니다. S0 대비 변화율은 문서 기록값이며 반올림된 매출로 재계산하지 않습니다.">
        <DataTable caption={`${model.label} · 13주 합계 · 억 USD · 80% 신용구간`} headings={["시나리오", "예산 이동", "이동폭 (%p)", "평균 (억 USD)", "80% 구간 (억 USD)", "S0 대비 (%)", "외삽 여부"]} rows={model.scenarios.map(row => [row.id, row.id === "S0" ? "기존 배분 유지" : `${row.from_channel} → ${row.to_channel}`, row.shift_pp, fixed(row.mean), interval(row.interval), row.change_pct === null ? "— (기준)" : `${signed(row.change_pct)}%`, <Extrapolation key={row.id} active={row.extrapolation} />])} />
      </Panel>
    </div>
  </>;
}
