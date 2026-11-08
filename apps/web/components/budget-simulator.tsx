"use client";

import { useState } from "react";
import { Bar, BarChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { DataTable, Metric, Panel } from "@/components/analysis-ui";
import { evaluateAllocation, initialInputs, parseShare, presetInputs, shareText, signedShareText, signedUsd, usd, type Preset, type SimulatorConfig } from "@/lib/simulator";

const inputClass = "mt-2 w-full min-w-0 rounded-lg border border-slate-300 bg-white p-3 text-sm text-slate-900 aria-invalid:border-red-600";
const buttonClass = "min-h-11 rounded-lg border border-slate-300 bg-white px-4 py-2 text-sm font-semibold text-slate-800 hover:bg-slate-50";

export function BudgetSimulator({ config }: { config: SimulatorConfig }) {
  const [inputs, setInputs] = useState(() => initialInputs(config));
  const [preset, setPreset] = useState<Preset | "custom">("s0");
  const [notice, setNotice] = useState("S0 기존 배분으로 시작합니다.");
  const result = evaluateAllocation(config, inputs.budget, inputs.shares);
  const loadPreset = (next: Preset) => {
    setInputs(previous => ({ ...previous, shares: presetInputs(config, next) }));
    setPreset(next);
    setNotice(next === "s0" ? "S0 기존 비중을 불러왔습니다. 총예산은 유지됩니다." : "trend + 운영 경계의 문서 반올림 비중을 불러왔습니다. 합계는 99.9%이며 총예산은 유지됩니다.");
  };
  const reset = () => {
    setInputs(initialInputs(config));
    setPreset("s0");
    setNotice("초기 S0 비중과 기본 총예산으로 초기화했습니다.");
  };
  const chart = config.channels.map((channel, i) => ({ channel: channel.id, s0: Number(channel.s0), draft: result.shares[i].units === null ? null : result.units[i] / 100 }));

  return <div className="space-y-6">
    <Panel title="배분안 입력" note="분석 기간은 13주로 고정됩니다. 총예산과 비중을 바꿔도 모델 예측은 실행되지 않습니다.">
      <div className="grid gap-5 sm:grid-cols-2">
        <div>
          <label htmlFor="simulator-budget" className="text-sm font-semibold text-slate-800">총 광고예산 (USD)</label>
          <input id="simulator-budget" type="text" inputMode="decimal" autoComplete="off" maxLength={32} value={inputs.budget} onChange={event => setInputs(previous => ({ ...previous, budget: event.target.value }))} aria-invalid={!!result.budget.error} aria-describedby="budget-help budget-error" className={inputClass} />
          <p id="budget-help" className="mt-2 text-xs leading-6 text-slate-500">쉼표 없이 입력 · 소수 둘째 자리까지 · 기본값 16,200,000 USD는 문서 근사값입니다.</p>
          <p id="budget-error" className="mt-1 text-xs leading-6 text-red-800">{result.budget.error}</p>
        </div>
        <div className="rounded-xl bg-slate-50 p-4 text-sm leading-7 text-slate-600">
          <p className="font-semibold text-slate-900">기간: {config.weeks}주 · 단순 예산 산술 계산</p>
          <p>S0 비교 금액은 사용자가 입력한 동일 총예산에 기존 비중을 적용합니다. 과거 실제 집행액과의 차이를 뜻하지 않습니다.</p>
        </div>
      </div>
      <div className="mt-6 border-t border-slate-200 pt-5">
        <p id="preset-help" className="mb-3 text-xs leading-6 text-slate-600">프리셋은 편집 중인 채널 비중을 교체합니다. 총예산은 유지되며, Reset은 총예산도 기본값으로 복원합니다.</p>
        <div className="flex flex-wrap gap-2" role="group" aria-label="배분 프리셋" aria-describedby="preset-help">
          <button type="button" className={buttonClass} onClick={() => loadPreset("s0")}>S0 기존 배분 불러오기</button>
          <button type="button" className={buttonClass} onClick={() => loadPreset("bounded")}>trend + 운영 경계 불러오기</button>
          <button type="button" className={buttonClass} onClick={reset}>Reset · 초기 S0 복원</button>
        </div>
        <p className="mt-3 text-xs leading-6 text-slate-600" role="status">{notice}</p>
        <p className="mt-2 text-xs leading-6 text-amber-900">운영 경계 프리셋은 문서 반올림값으로 합계 99.9%입니다. 정확한 내부 배분값이 없어 자동 정규화나 특정 채널의 0.1%p 추가를 하지 않습니다. 사용자가 직접 보정해야 합니다.</p>
        <p className="mt-2 text-xs text-slate-500">현재 배분: {preset === "custom" ? "사용자 편집안" : preset === "bounded" ? "trend + 운영 경계 · 문서 반올림값" : "S0 기존 배분"}</p>
      </div>
      <p id="share-help" className="mb-4 mt-6 text-xs leading-6 text-slate-600">각 비중은 0~100%, 소수 둘째 자리까지 입력할 수 있습니다. 운영 제약은 입력 범위와 별도로 검사합니다.</p>
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-5">
        {config.channels.map((channel, i) => <div key={channel.id} className="min-w-0 rounded-xl border border-slate-200 p-4">
          <label htmlFor={`share-${channel.id}`} className="text-sm font-semibold text-slate-800">{channel.id} 비중 (%)</label>
          <input id={`share-${channel.id}`} type="text" inputMode="decimal" autoComplete="off" maxLength={32} className={inputClass} value={inputs.shares[i]} onChange={event => {
            setInputs(previous => ({ ...previous, shares: previous.shares.map((value, index) => i === index ? event.target.value : value) }));
            setPreset("custom");
          }} aria-invalid={!!result.shares[i].error} aria-describedby={`share-help share-error-${channel.id} constraint-${channel.id}`} />
          <p id={`share-error-${channel.id}`} className="mt-2 text-xs leading-6 text-red-800">{result.shares[i].error}</p>
          <p id={`constraint-${channel.id}`} className={`mt-2 text-xs leading-6 ${result.constraints[i].valid ? "text-teal-800" : "font-semibold text-amber-900"}`}>{result.constraints[i].valid ? `운영 범위 ${shareText(channel.minUnits)}~${shareText(channel.maxUnits)}% · 충족` : result.constraints[i].message}</p>
        </div>)}
      </div>
    </Panel>

    <div className="grid gap-4 sm:grid-cols-3" aria-live="polite" aria-atomic="true">
      <Metric label="비중 합계" value={result.sumUnits === null ? "입력 확인 필요" : `${shareText(result.sumUnits)}%`} note={result.sumUnits === null ? "유효하지 않은 비중을 수정하세요." : `100%와의 차이 ${signedShareText(result.sumUnits - 10000)}%p`} />
      <Metric label="채널 배분 금액 합계" value={result.allocated === null ? "계산 보류" : usd(result.allocated)} note="입력 비중을 그대로 적용 · 자동 정규화 없음" />
      <Metric label="총예산 대비 배분 차액" value={result.budgetDifference === null ? "계산 보류" : signedUsd(result.budgetDifference)} note="음수는 미배분, 양수는 초과 배분 · 0이면 금액 일치" />
    </div>
    <div role="status" className={`rounded-xl border p-4 text-sm leading-7 ${result.ready ? "border-teal-200 bg-teal-50 text-teal-900" : "border-amber-200 bg-amber-50 text-amber-950"}`}>
      <p className="font-semibold">{result.ready ? "예산 입력·비중 합계·운영 제약 충족" : "배분안 수정 필요"}</p>
      {result.sumUnits !== null && result.sumUnits !== 10000 ? <p>{shareText(Math.abs(result.sumUnits - 10000))}%p {result.sumUnits < 10000 ? "부족합니다. 채널 비중을 늘려" : "초과했습니다. 채널 비중을 줄여"} 합계를 100%로 맞추세요.</p> : null}
      {result.budget.error || result.sumUnits === null ? <p>입력란에 표시된 오류를 수정하세요. 잘못된 입력을 0으로 대체하지 않습니다.</p> : null}
      <p>{result.ready ? "이는 산술 계산과 운영 범위 검사만 통과했다는 뜻입니다. 모델 성과와 외삽 여부를 검증한 결과가 아닙니다." : "채널별 제약 위반과 입력 오류를 확인하세요. 합계가 100%가 아니면 금액은 임시 배분안입니다."}</p>
    </div>

    <Panel title="S0와 사용자 비중 비교" note="단위 % · 회색은 기존 S0, 청록색은 사용자 입력입니다. 비중 입력이 잘못되면 차트를 보류하고 0으로 표시하지 않습니다.">
      {result.sumUnits === null ? <p className="text-sm text-slate-600">유효한 채널 비중을 입력하면 비교 차트를 표시합니다.</p> : <div className="h-80 min-w-0" role="img" aria-label="채널별 기존 S0와 사용자 입력 비중 비교. 아래 대체 표에 동일 수치 제공.">
        <ResponsiveContainer width="100%" height="100%" initialDimension={{ width: 600, height: 320 }}>
          <BarChart data={chart} margin={{ top: 10, right: 10, bottom: 15, left: 0 }} accessibilityLayer>
            <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#e2e8f0" />
            <XAxis dataKey="channel" tick={{ fontSize: 11 }} /><YAxis domain={[0, 100]} width={44} tick={{ fontSize: 11 }} unit="%" />
            <Tooltip formatter={value => `${Number(value).toFixed(2)}%`} /><Legend wrapperStyle={{ fontSize: 12 }} />
            <Bar dataKey="s0" name="기존 S0" fill="#64748b" maxBarSize={32} isAnimationActive={false} />
            <Bar dataKey="draft" name="사용자 입력" fill="#0f766e" maxBarSize={32} isAnimationActive={false} />
          </BarChart>
        </ResponsiveContainer>
      </div>}
      <DataTable caption="비중 차트 대체 표 · 동일 총예산 기준 USD · 변화폭 %p" headings={["채널", "S0 (%)", "사용자 (%)", "변화 (%p)", "S0 금액 (USD)", "배분 금액 (USD)", "증감 (USD)", "운영 범위 (%)", "제약 검증"]} rows={config.channels.map((channel, i) => [channel.id, Number(channel.s0).toFixed(2), result.shares[i].units === null ? "입력 오류" : shareText(result.units[i]), result.shares[i].units === null ? "—" : signedShareText(result.units[i] - parseShare(channel.s0).units!), result.baseline ? usd(result.baseline[i]) : "계산 보류", result.amounts ? usd(result.amounts[i]) : "계산 보류", result.amounts && result.baseline ? signedUsd(result.amounts[i] - result.baseline[i]) : "계산 보류", `${shareText(channel.minUnits)}~${shareText(channel.maxUnits)}`, result.constraints[i].message])} />
      <p className="mt-4 text-xs leading-6 text-slate-500">센트 단위 표시 금액은 소수 센트 잔여분이 큰 채널부터 1센트씩 배정해 합계를 맞춥니다. 동률이면 DM·SO·VIDTR·VIDDIG·SEM 순서입니다. 비중은 바꾸지 않습니다. 합계 100%에서는 총예산과 정확히 일치하고, 미달·초과 시 실제 입력 합계에 해당하는 금액까지만 계산합니다.</p>
    </Panel>

    <Panel title="모델 예측 기능 · 사용 불가" note="Bayesian trace, 완전한 모델 summary 및 trend 입력 파일이 미확보되어 예측 기능은 비활성화되어 있습니다.">
      <div className="flex flex-wrap gap-3" role="group" aria-label="비활성 모델 예측 기능" aria-describedby="prediction-unavailable">
        {["예상 매출 계산", "ROAS 계산", "80% 신용구간 계산"].map(label => <button type="button" key={label} disabled className="min-h-11 cursor-not-allowed rounded-lg border border-slate-200 bg-slate-100 px-4 py-3 text-sm text-slate-500">{label}</button>)}
      </div>
      <p id="prediction-unavailable" className="mt-4 text-sm leading-7 text-slate-600">이 도구는 예산 배분 설계 및 제약 검증만 수행합니다. 매출·ROAS·posterior 신용구간을 새로 계산하지 않습니다. M2의 문서 기록 성과는 사용자 배분에 연결하지 않으며, 입력안의 실제 매출 증가나 외삽 안전성을 보장하지 않습니다.</p>
    </Panel>
  </div>;
}
