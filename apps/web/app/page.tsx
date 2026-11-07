import Link from "next/link";
import { AnalysisHeading, DataTable, Metric, Panel, SourceLabel } from "@/components/analysis-ui";
import { dashboard as d, number, percent, periodLabel } from "@/lib/dashboard-data";

export default function OverviewPage() {
  const available = [
    ["원본 CSV", d.availability.raw_csv], ["Bayesian trace", d.availability.trace],
    ["모델 요약 JSON", d.availability.model_summary], ["트렌드 CSV", d.availability.trend_csv],
    ["시나리오 JSON", d.availability.scenario_results], ["최적화 JSON", d.availability.optimum_results],
  ] as const;
  return <div className="mx-auto max-w-6xl space-y-7">
    <AnalysisHeading english="Overview" title="분석 개요">과거 미국 리테일 데이터를 바탕으로 마케팅 예산 분석의 근거와 한계를 살펴봅니다. CSV 집계값과 문서에 기록된 모델 성능을 구분해 제공합니다.</AnalysisHeading>
    <SourceLabel>원본 CSV 직접 집계 · 주간 형식 검증 통과</SourceLabel>
    <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
      <Metric label="분석 데이터" value={`${d.summary.weeks}주`} note={periodLabel} />
      <Metric label="광고 채널" value={`${d.summary.channel_count}개`} note="DM · SO · VIDTR · VIDDIG · SEM" />
      <Metric label="시간순 검증 분할" value={`${d.summary.train_weeks} / ${d.summary.test_weeks}주`} note="Train / Test · 마지막 26주를 평가 구간으로 사용" />
      <Metric label="전체 기간 누적 광고비" value={`${number(d.summary.spend_total / 1e6, 2)} 백만 USD`} note="핵심 5채널 합계 · 미래 분기 예산과 구분" />
    </div>
    <Panel title="모델 성능 비교" note="평가 구간: 마지막 26주 · 동일한 시간순 검증 분할 · 이번 웹 작업에서 재학습하지 않았습니다.">
      <SourceLabel>문서 기록 · 확정런 2026-10-12 · 현재 trace 미확보</SourceLabel>
      <div className="mt-5 grid gap-4 md:grid-cols-2">{d.model_performance.models.map(model => <article key={model.id} className="rounded-xl border border-slate-200 p-5">
        <h3 className="font-semibold text-slate-900">{model.label}</h3>
        <p className="mt-2 text-[11px] leading-5 text-slate-500">문서 기록 · 확정런 2026-10-12 · 현재 trace 미확보</p>
        <dl className="mt-5 grid grid-cols-3 gap-2">
          {[['Test MAPE', percent(model.test_mape)], ['방향정확도', percent(model.direction_accuracy)], ['Max R-hat', model.max_rhat.toFixed(3)]].map(([label, value]) => <div key={label}><dt className="text-[11px] text-slate-500">{label}</dt><dd className="mt-2 text-lg font-bold tabular-nums text-teal-900">{value}</dd></div>)}
        </dl>
      </article>)}</div>
      <p className="mt-5 text-sm leading-7 text-slate-600">트렌드 결합 모델은 MAPE가 낮지만 방향정확도는 개선되지 않았습니다. R-hat은 표본 수렴 진단이며 예측 정확도와 다릅니다. 트렌드 모델에는 문서상 divergence 3건이 기록되어 있습니다.</p>
      <p className="mt-2 text-xs text-slate-500">출처: docs/bayes-run.md · 최종 확정런 절 · 현재 산출물로 재검증되지 않은 수치</p>
    </Panel>
    <div className="grid gap-7 xl:grid-cols-2">
      <Panel title="주간 매출 요약" note={`CSV 직접 계산 · ${periodLabel} · USD, 소수 둘째 자리 반올림`}>
        <DataTable caption="전체 209주 매출의 기술통계" headings={["통계", "USD"]} rows={[["평균", number(d.sales.mean, 2)], ["중앙값", number(d.sales.median, 2)], ["최솟값", number(d.sales.min, 2)], ["최댓값", number(d.sales.max, 2)]]} />
        <Link href="/eda/" className="mt-5 inline-flex min-h-11 items-center text-sm font-semibold text-teal-800 underline underline-offset-4">채널별 집계와 분포 살펴보기 →</Link>
      </Panel>
      <Panel title="데이터·모델 파일 확보 상태" note="집계 JSON 생성 시 로컬 파일 존재 여부를 확인한 결과입니다. 존재 여부와 모델 검증 완료는 다릅니다.">
        <ul className="divide-y divide-slate-100">{available.map(([label, exists]) => <li key={label} className="flex items-center justify-between gap-3 py-3 text-sm"><span className="text-slate-700">{label}</span><span className={`rounded-md px-2 py-1 text-xs font-medium ${exists ? 'bg-teal-50 text-teal-800' : 'bg-slate-100 text-slate-600'}`}>{exists ? '확보 · 형식 검증 완료' : '미확보'}</span></li>)}</ul>
      </Panel>
    </div>
    <Panel title="출처와 공개 범위" note="집계 데이터만 웹 빌드에 사용합니다. 원본 CSV와 날짜별 관측값은 포함하지 않습니다.">
      <dl className="grid gap-4 text-xs leading-6 text-slate-600 sm:grid-cols-2">
        <div><dt className="font-semibold text-slate-800">CSV 출처</dt><dd>{d.source} · USD · {periodLabel}</dd></div>
        <div><dt className="font-semibold text-slate-800">집계 생성 시각 (UTC)</dt><dd>{d.generated_at}</dd></div>
        <div className="sm:col-span-2"><dt className="font-semibold text-slate-800">원본 SHA-256</dt><dd className="break-all font-mono">{d.source_sha256}</dd></div>
      </dl>
      <p className="mt-4 text-xs leading-6 text-slate-500">docs/eda.md의 {d.document_comparison.checks.length}개 항목과 대조: {d.document_comparison.mismatch_count}건 차이 (SEM Q1 서술). 상세 차이는 EDA에 표시했습니다. 미국 리테일 2014~2018년 회고 분석이며 현재 한국 시장의 예측·집행 권고가 아닙니다. 원본의 최초 출처·라이선스와 공개 권한은 별도 확인이 필요합니다.</p>
    </Panel>
  </div>;
}
