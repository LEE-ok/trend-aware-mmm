import type { Metadata } from "next";
import { AnalysisHeading, DataTable, Metric, Panel, SourceLabel } from "@/components/analysis-ui";
import { ChannelDistribution, CorrelationChart, DistributionChart, SpendChart } from "@/components/aggregate-charts";
import { dashboard as d, number, percent, periodLabel } from "@/lib/dashboard-data";

export const metadata: Metadata = { title: "탐색적 분석" };
export default function EdaPage() {
  return <div className="mx-auto max-w-6xl space-y-7">
    <AnalysisHeading english="EDA" title="탐색적 분석">매출과 광고비의 규모·분포·동시 상관관계를 전체 기간 집계로 살펴봅니다. 개별 주간 관측값이나 날짜별 매출은 공개하지 않습니다.</AnalysisHeading>
    <SourceLabel>csv_computed · CSV 직접 계산 · {periodLabel} · {d.summary.weeks}주 · USD</SourceLabel>
    <div className="grid gap-4 sm:grid-cols-3">
      <Metric label="주간 매출 평균" value={`${number(d.sales.mean / 1e6, 2)} 백만 USD`} note="전체 209주 평균 · 소수 둘째 자리 반올림" />
      <Metric label="주간 매출 중앙값" value={`${number(d.sales.median / 1e6, 2)} 백만 USD`} note="Q2 · 전체 관측값의 가운데 값" />
      <Metric label="누적 광고비" value={`${number(d.summary.spend_total / 1e6, 2)} 백만 USD`} note="5채널 합계 · 전체 기간 기준" />
    </div>
    <Panel title="채널별 누적 광고비와 비중" note={`${periodLabel} · 209주 합계 · 차트 세로축: 백만 USD · 가로축: 광고 채널`}>
      <SpendChart channels={d.channels} />
      <DataTable caption="광고비 집계 · 금액 USD, 소수 둘째 자리 / 비중 소수 첫째 자리 반올림" headings={["채널", "누적 광고비 (USD)", "비중", "주간 평균 (USD)", "0 집행 주"]} rows={d.channels.map(c => [c.label, number(c.spend.total, 2), percent(c.share), number(c.spend.mean, 2), `${c.zero_weeks}주`])} />
      <p className="mt-3 text-xs leading-6 text-slate-500">비중의 분모는 전체 209주 핵심 5채널 광고비 합계입니다. 시나리오의 최근 13주 기준 비중과 다릅니다.</p>
    </Panel>
    <Panel title="매출과 광고비의 상관관계" note={`${periodLabel} · 동시점 209주 · 세로축: 상관계수 (-1~1) · 가로축: 광고 채널`}>
      <CorrelationChart channels={d.channels} />
      <p className="mb-5 text-sm leading-7 text-slate-600"><strong>Pearson</strong>은 원래 값의 선형 관계, <strong>Spearman</strong>은 순위의 단조 관계를 측정합니다. Spearman 계산 시 동률에는 평균 순위를 부여했습니다. 두 지표는 서로 다른 측정값입니다.</p>
      <DataTable caption="매출 대비 상관계수 · CSV 직접 계산, 소수 셋째 자리 반올림" headings={["채널", "Pearson r · 선형", "Spearman ρ · 순위"]} rows={d.channels.map(c => [c.label, c.pearson.toFixed(3), c.spearman.toFixed(3)])} />
      <p className="mt-5 rounded-lg border border-amber-200 bg-amber-50 p-4 text-sm leading-7 text-amber-950">상관관계는 인과효과가 아닙니다. 휴일·계절성·프로모션 등 교란 요인이 포함될 수 있으며, 이 차트만으로 채널의 효과나 예산 이동을 결정할 수 없습니다.</p>
    </Panel>
    <div className="grid gap-7 xl:grid-cols-2">
      <Panel title="주간 매출 분포 요약" note={`${periodLabel} · 세로축: 백만 USD · 가로축: 5수치 요약 통계 (빈도 아님)`}>
        <DistributionChart stats={d.sales} label="주간 매출" />
        <DataTable caption="주간 매출 분포 · USD, 소수 둘째 자리 반올림" headings={["최솟값", "Q1 (25%)", "중앙값", "Q3 (75%)", "최댓값"]} rows={[[d.sales.min, d.sales.q25, d.sales.median, d.sales.q75, d.sales.max].map(v => number(v, 2))]} />
      </Panel>
      <Panel title="채널별 주간 지출 분포" note={`${periodLabel} · 세로축: 백만 USD · 가로축: 5수치 요약 통계 (빈도 아님)`}>
        <ChannelDistribution channels={d.channels} />
        <p className="mt-4 text-xs leading-6 text-slate-500">채널마다 세로축 범위가 다릅니다. 절대 규모는 아래 전체 채널 표에서 비교할 수 있습니다.</p>
      </Panel>
    </div>
    <Panel title="채널별 분포 수치표" note="CSV 직접 계산 · USD, 소수 둘째 자리 반올림 · 사분위수는 선형 보간 방식 (n−1 위치 기준)">
      <DataTable caption={`전체 채널 주간 광고비 5수치 요약 · ${periodLabel}`} headings={["채널", "최솟값", "Q1 (25%)", "중앙값", "Q3 (75%)", "최댓값"]} rows={d.channels.map(c => [c.label, ...[c.spend.min, c.spend.q25, c.spend.median, c.spend.q75, c.spend.max].map(v => number(v, 2))])} />
      <p className="mt-4 text-xs leading-6 text-slate-500">Q1~Q3는 관측값 중앙 50%의 범위입니다. Bayesian credible interval이 아닙니다. 요약 분포는 개별 값의 빈도나 이상치 발생 주차를 보여주지 않습니다.</p>
    </Panel>
    <section className="rounded-xl border border-dashed border-slate-300 bg-slate-100 p-6" aria-labelledby="weekly-series-title">
      <h2 id="weekly-series-title" className="font-semibold text-slate-700">주간 매출·광고비 시계열 · 비활성화</h2>
      <p className="mt-2 text-sm leading-7 text-slate-600">원본 주간 데이터 공개 승인 전까지 제공하지 않습니다. 집계 JSON에는 원본 209행, 개별 날짜-매출 쌍, 주간 시계열이 포함되어 있지 않습니다.</p>
    </section>
    <Panel title="기존 EDA 문서와의 대조" note={`docs/eda.md · ${d.document_comparison.checks.length}개 항목 중 ${d.document_comparison.checks.length - d.document_comparison.mismatch_count}개 일치, ${d.document_comparison.mismatch_count}개 차이`}>
      <p className="text-sm leading-7 text-slate-600">표의 정수 금액·상관계수는 반올림 범위 내 일치합니다. 서술형 SEM Q1은 문서의 약 365,000 USD와 원본 계산값 355,954.51 USD 사이에 9,045.49 USD 차이가 있어 단순 반올림으로 설명되지 않습니다. 전사 또는 과거 집계 기준 차이인지 확인할 수 없어 기존 문서는 유지하고 현재 CSV 계산값을 표시합니다.</p>
      <p className="mt-3 text-xs text-slate-500">금액 표 ±0.5 USD, 상관계수 ±0.0005, 소수 첫째 자리 만 단위의 근삿값 ±500 USD로 대조했습니다.</p>
    </Panel>
  </div>;
}
