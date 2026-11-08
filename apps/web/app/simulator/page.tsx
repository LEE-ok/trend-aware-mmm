import type { Metadata } from "next";
import { AnalysisHeading, SourceLabel } from "@/components/analysis-ui";
import { BudgetSimulator } from "@/components/budget-simulator";
import recorded from "@/data/mmm-results.json";
import { createSimulatorConfig } from "@/lib/simulator";

export const metadata: Metadata = { title: "예산 시뮬레이터" };
export default function SimulatorPage() {
  const config = createSimulatorConfig(recorded);
  return <>
    <AnalysisHeading english="Budget Simulator" title="예산 배분 설계 및 제약 검증">채널별 광고예산을 설계하고 기존 배분과 비교합니다. 총예산·비중을 이용한 산술 계산과 운영 범위 검사만 제공합니다.</AnalysisHeading>
    <div className="mb-6 space-y-3 text-xs leading-6 text-slate-600">
      <SourceLabel>프리셋: document_recorded · 2026-10-12 확정런 · trace 미검증</SourceLabel>
      <p>출처: <code>data/mmm-results.json</code> · S0 및 기본 예산 근거: <code>docs/scenario.md</code> · 운영 경계안: <code>docs/optimization.md</code>.</p>
      <p>기존 집계 JSON에는 정확한 최근 13주 예산 총액이 없어 문서의 약 16.20M USD를 사용합니다. 전체 209주 광고비 합계를 기본 예산으로 사용하지 않습니다. 사용자 계산값의 출처는 입력값이며 모델 결과가 아닙니다.</p>
    </div>
    <BudgetSimulator config={config} />
  </>;
}
