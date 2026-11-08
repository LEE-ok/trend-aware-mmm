"use client";

import { useState } from "react";
import { Bar, BarChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { DataTable, Metric, Panel } from "@/components/analysis-ui";
import { Extrapolation, ModelSelect } from "@/components/mmm-shared";
import { fixed, interval, results, signed } from "@/lib/mmm-results";

export function OptimizationResults() {
  const [id, setId] = useState(results.default_optimization);
  const plan = results.optimization_plans.find(plan => plan.id === id)!;
  const shares = results.channels.map((channel, i) => ({ channel, baseline: results.s0_shares_pct[i], optimized: plan.shares_pct[i] }));
  return <>
    <ModelSelect id="optimization-model" label="최적화안 선택" value={id} onChange={setId} options={results.optimization_plans} />
    <div className="space-y-6" aria-live="polite">
      <p className="text-sm font-semibold text-slate-800">{plan.label} · <Extrapolation active={plan.extrapolation} /></p>
      {plan.extrapolation ? <div role="note" className="rounded-xl border border-amber-200 bg-amber-50 p-4 text-sm leading-7 text-amber-950">⚠ trend 결합안의 VIDDIG는 주간 관측 최대 지출을 초과합니다. 외삽을 방지한 trend + 운영 경계안을 최종 권고안으로 사용합니다.</div> : null}
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <Metric label="예상 매출 · 13주 합계" value={`${fixed(plan.mean)} 억 USD`} note={`80% 신용구간 ${interval(plan.interval)} 억 USD`} />
        <Metric label="S0 대비 paired 증분" value={`${signed(plan.paired_increment, 2)} 억 USD`} note={`80% 신용구간 ${interval(plan.paired_interval)} 억 USD`} />
        <Metric label="S0 대비 변화율" value={`${signed(plan.change_pct)}%`} note="문서 기록값 · 동일 모델의 S0 기준" />
        <Metric label="P(증분 > 0)" value={`${fixed(plan.probability_positive * 100, 2)}%`} note="모델 사후분포의 확률 · 실제 성과 보장 아님" />
      </div>
      <Panel title="기존 S0와 기대최적 배분 비교" note="채널 비중 (%) · S0는 최근 13주 집행 비중입니다. M1의 전체 209주 비중과 기준이 다릅니다.">
        <div className="h-80 min-w-0" role="img" aria-label="채널별 S0와 최적 배분 비중 비교. 아래 대체 표에 동일 수치와 변화폭 제공.">
          <ResponsiveContainer width="100%" height="100%" initialDimension={{ width: 600, height: 320 }}>
            <BarChart data={shares} margin={{ top: 10, right: 10, bottom: 15, left: 0 }} accessibilityLayer>
              <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#e2e8f0" />
              <XAxis dataKey="channel" tick={{ fontSize: 11 }} /><YAxis domain={[0, 60]} width={40} tick={{ fontSize: 11 }} unit="%" />
              <Tooltip formatter={value => `${fixed(Number(value), 2)}%`} /><Legend wrapperStyle={{ fontSize: 12 }} />
              <Bar dataKey="baseline" name="기존 S0" fill="#64748b" maxBarSize={32} isAnimationActive={false} />
              <Bar dataKey="optimized" name="기대최적 배분" fill="#0f766e" maxBarSize={32} isAnimationActive={false} />
            </BarChart>
          </ResponsiveContainer>
        </div>
        <DataTable caption="배분 차트 대체 표 · S0 출처: docs/scenario.md · 변화폭은 표시된 문서 비중의 차이" headings={["채널", "S0 (%)", "기대최적 (%)", "변화 (%p)", "선택안 제약 (%)"]} rows={shares.map((row, i) => [row.channel, fixed(row.baseline), fixed(row.optimized, 1), signed(row.optimized - row.baseline, 2), `${plan.bounds_pct[i][0]} ~ ${plan.bounds_pct[i][1]}`])} />
        <p className="mt-3 text-xs leading-6 text-slate-500">문서의 반올림 비중을 유지합니다. 운영 경계안 합계는 99.9%이며, 합계를 맞추기 위한 비중 보정은 하지 않았습니다.</p>
      </Panel>
      <Panel title="매출·증분과 불확실성" note="모든 구간은 80% 신용구간입니다. 매출 구간의 양 끝을 빼서 증분 구간을 만들지 않습니다.">
        <DataTable caption={`${plan.label} · 13주 합계 · 억 USD`} headings={["지표", "평균 (억 USD)", "80% 구간 (억 USD)"]} rows={[["기존 S0 매출", fixed(plan.s0_mean), interval(plan.s0_interval)], ["기대최적 매출", fixed(plan.mean), interval(plan.interval)], ["S0 대비 paired 증분", signed(plan.paired_increment, 2), interval(plan.paired_interval)]]} />
        <p className="mt-4 text-sm leading-7 text-slate-600">paired 증분은 동일한 posterior draw에서 최적안과 S0를 뺀 값입니다. 총매출 구간이 겹쳐도 paired 증분 구간과 P(증분&gt;0)은 별도로 해석합니다. 80% 신용구간은 모델과 가정 아래의 사후 불확실성을 나타냅니다.</p>
      </Panel>
      <Panel title="운영 경계와 권고안 해석">
        <div className="space-y-3 text-sm leading-7 text-slate-600">
          <p>최종 권고안은 trend + 운영 경계입니다. DM 최소 5%는 최소 집행을 유지하며, VIDDIG 최대 8.3%는 과거 관측 최대 주간 지출을 넘는 외삽을 방지합니다. 나머지 채널은 0~60% 범위입니다.</p>
          <p>기대최적은 평균 매출을 기준으로 선택한 하나의 배분입니다. 최적 비중 자체도 불확실하며, draw별 최적 비중의 분포와 구분해야 합니다. 운영 경계안의 채널별 비중 구간은 문서에 없어 표시하지 않습니다.</p>
          <p>탐욕 탐색 결과는 국소 최적일 수 있고 전역 최적을 보장하지 않습니다. 확정런의 추가 국소최적 점검·하방 위험 최적화 결과는 문서에 미기입 상태입니다.</p>
          <p className="font-semibold text-slate-900">최적 비중은 모델 추정치이며 실제 매출 증가를 보장하지 않습니다. SEM·VIDTR 중심, DM·SO 축소 방향을 참고하여 운영 검토와 실험으로 확인해야 합니다.</p>
        </div>
      </Panel>
    </div>
  </>;
}
