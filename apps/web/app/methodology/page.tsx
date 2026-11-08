import type { Metadata } from "next";
import Link from "next/link";
import { AnalysisHeading, DataTable, Metric, Panel, SourceLabel } from "@/components/analysis-ui";
import { dashboard as d, number, percent, periodLabel } from "@/lib/dashboard-data";
import { results } from "@/lib/mmm-results";
import audit from "@/data/release-audit.json";

export const metadata: Metadata = { title: "분석 방법론" };
export default function MethodologyPage() {
  const sources = ["data-contract.md", "eda.md", "priors.md", "bayes-run.md", "trends.md", "trend-compare.md", "scenario.md", "scenario-results.md", "optimization.md"];
  return <div className="mx-auto max-w-6xl space-y-7">
    <AnalysisHeading english="Methodology" title="분석 방법론">과거 미국 리테일 데이터로 광고비와 매출의 관계를 분석하고, 동일 예산 아래 재배분 방향과 불확실성을 비교합니다. 실제 집행 성과를 검증한 실험은 아닙니다.</AnalysisHeading>
    <SourceLabel>모델 결과: document_recorded · 2026-10-12 확정런 · 현재 trace 미확보</SourceLabel>
    <div className="grid gap-4 sm:grid-cols-3">
      <Metric label="분석 대상" value={`${d.summary.weeks}주`} note={`${periodLabel} · 미국 리테일 · 주간 USD`} />
      <Metric label="시간순 분할" value={`${d.summary.train_weeks} / ${d.summary.test_weeks}주`} note="Train / Test · 마지막 26주로 평가 · 무작위 분할 아님" />
      <Metric label="예산 배분 비교 기간" value="13주 합계" note="시나리오·최적화 매출은 억 USD · 광고예산 입력은 USD" />
    </div>
    <Panel title="목적과 데이터 구조" note="출처: docs/data-contract.md · docs/eda.md · dashboard-aggregates.json (csv_computed)">
      <p className="mb-5 text-sm leading-7 text-slate-600">관측자료의 상관관계는 인과효과를 뜻하지 않습니다. 2014~2018년 회고 분석을 현재 한국 시장의 예측이나 집행 권고로 직접 적용할 수 없습니다. 핵심 광고 채널 5개를 사용하며 웹에는 요약 집계와 문서 기록값을 제공합니다.</p>
      <DataTable caption="주간 입력 데이터의 역할 · 원본 행은 공개하지 않음" headings={["역할", "필드", "내용"]} rows={[
        ["시간·타깃", "wk_strt_dt / sales", "주 시작일 / 주간 총매출 (USD)"],
        ["광고비", "mdsp_dm / so / vidtr / viddig / sem", "DM · 소셜 · 전통 영상 · 디지털 영상 · 검색 광고비 (USD)"],
        ["통제", "me_gas_dpg / me_ics_all / st_ct", "경제·매장 환경 변수"],
        ["휴일·계절", "hldy_* / seas_prd_*", "휴일 묶음과 계절 더미 · 첫 계절 더미 제외"],
        ["trend 결합", "trend_demand", "검색 관심도의 합성지수 · 매출과 별개인 보조변수"],
      ]} />
    </Panel>
    <Panel title="Bayesian MMM은 어떻게 계산하나요?" note="출처: docs/priors.md 및 기존 src/trend_mmm/mmm/bayesian.py · 이 웹사이트에서 학습하지 않습니다.">
      <p className="rounded-xl bg-slate-50 p-4 text-sm leading-7 text-slate-800">주간 매출 = 절편 + 채널별 기여의 합 + 통제·휴일·계절·trend 항 + 오차</p>
      <ol className="mt-5 grid gap-4 sm:grid-cols-2">
        <li className="rounded-xl border border-slate-200 p-4"><h3 className="font-semibold text-slate-900">1. Adstock · 광고 효과의 이월</h3><p className="mt-2 text-sm leading-7 text-slate-600">이번 주 광고의 영향이 다음 주에도 일부 남는 구조입니다. 현재 지출에 이전 주 이월값 × decay를 더합니다. decay는 채널별로 추정하며 단순 시차 상관과 구분합니다.</p></li>
        <li className="rounded-xl border border-slate-200 p-4"><h3 className="font-semibold text-slate-900">2. Hill Saturation · 포화</h3><p className="mt-2 text-sm leading-7 text-slate-600">이월 지출을 0~1의 반응으로 바꾸어 추가 지출의 효과가 제한되는 구조를 표현합니다. ec50은 train 구간에서 정한 절반 반응 수준으로 고정하며 alpha는 곡선 모양입니다. alpha가 1보다 크면 S자여서 모든 구간이 오목하지 않습니다.</p></li>
        <li className="rounded-xl border border-slate-200 p-4"><h3 className="font-semibold text-slate-900">3. Bayesian posterior · 가능한 추정의 분포</h3><p className="mt-2 text-sm leading-7 text-slate-600">사전분포와 관측자료를 결합해 하나의 정답 대신 계수의 사후분포를 구합니다. 광고 계수 beta는 0 이상으로 제약합니다. 80% 신용구간은 모델·가정 아래의 사후 불확실성이며, 실제 매출의 보장 범위가 아닙니다.</p></li>
        <li className="rounded-xl border border-slate-200 p-4"><h3 className="font-semibold text-slate-900">4. trend 결합 · 수요 신호 보완</h3><p className="mt-2 text-sm leading-7 text-slate-600">sale·deals·coupons·gift 검색 관심도에서 합성한 지수를 train 통계로 표준화해 보조항으로 넣습니다. 미래 trend는 알 수 없어 시나리오에서는 최근 13주 평균으로 고정합니다. gift와 연말 휴일의 겹침 가능성 때문에 독립적인 인과 기여로 해석하지 않습니다.</p></li>
      </ol>
    </Panel>
    <Panel title="trend 모델 채택 근거와 예측 한계" note="출처: docs/bayes-run.md · docs/trend-compare.md · 2026-10-12 확정런 기록 (document_recorded)">
      <DataTable caption="동일 test 26주 모델 비교 · 낮은 MAPE가 유리" headings={["모델", "Test MAPE", "방향정확도", "Max R-hat"]} rows={d.model_performance.models.map(model => [model.label, percent(model.test_mape), percent(model.direction_accuracy), model.max_rhat.toFixed(3)])} />
      <p className="mt-4 text-sm leading-7 text-slate-600">MAPE는 매출 수준의 평균 절대 백분율 오차입니다. 기본 33.6%에서 trend 30.6%로 낮아져 trend 결합을 채택했습니다. 방향정확도는 전주 대비 등락 방향을 맞힌 비율이며 40%에서 36%로 낮아졌습니다. 주간 상승·하락 예측용으로 사용하지 않습니다.</p>
      <p className="mt-3 text-sm leading-7 text-slate-600">확정런은 4체인, 총 4000 draws입니다. R-hat은 표본 수렴 진단이지 정확도나 인과성의 증명이 아닙니다. trend 모델 divergence 3건도 문서에 기록되어 있습니다. 현재 trace·완전한 summary·trend 입력이 없어 이 웹 작업에서 모델 수치를 재현 검증하지 못했습니다.</p>
    </Panel>
    <Panel title="S0~S4 시나리오 설계" note="출처: docs/scenario.md · docs/scenario-results.md · 확정런 2026-10-12">
      <DataTable caption="총예산을 고정한 비중 이동 · 이동폭은 %p" headings={["시나리오", "설계", "목적"]} rows={[
        ["S0", "최근 13주 기존 비중 유지", "재배분 비교의 기준"],
        ["S1", "DM → VIDTR · 5/10/15%p", "전통 영상으로 이동하는 방향 비교"],
        ["S2", "DM → SEM · 5/10/15%p", "검색 광고 증액의 추가 효과 비교"],
        ["S3", "DM → VIDDIG · 5/10/15%p", "디지털 영상 확대와 외삽 위험 비교"],
        ["S4", "DM → SO · 5/10/15%p", "소셜로 이동하는 대안 비교"],
      ]} />
      <p className="mt-4 text-sm leading-7 text-slate-600">주는 채널의 감소분과 받는 채널의 증가분을 같게 두어 총액을 유지합니다. 13주 균등 집행, 이월 0에서 시작, 보조변수·trend 수준은 최근 13주 평균 고정이라는 가정입니다. 매출은 13주 합계, 억 USD로 표시합니다.</p>
      <p className="mt-3 text-sm leading-7 text-amber-950">S3_10·S3_15는 VIDDIG 관측 범위를 넘는 외삽입니다. 시나리오의 80% 구간이 S0와 겹치므로 점추정 순서가 확정 성과 순위는 아닙니다.</p>
      <Link href="/scenarios/" className="mt-3 inline-flex min-h-11 items-center text-sm font-semibold text-teal-800 underline">시나리오별 평균과 구간 보기 →</Link>
    </Panel>
    <Panel title="예산 최적화와 운영 경계" note="출처: docs/optimization.md · 2026-10-12 draws 기대최적 기록 · document_recorded">
      <p className="text-sm leading-7 text-slate-600">기대최적(pooled)은 사후 draw 전체의 평균 매출을 기준으로 선택한 하나의 배분입니다. draw마다 따로 구한 최적 비중 분포는 민감도 자료이며 동일한 권고안이 아닙니다. 평균 기준의 탐욕 탐색은 국소 최적일 수 있어 전역 최적을 보장하지 않습니다.</p>
      <p className="mt-3 text-sm leading-7 text-slate-600">기본 권고안은 trend + 운영 경계입니다. DM 최소 5%로 최소 집행을 유지하고 VIDDIG 최대 8.3%로 기준 예산에서 관측 최대 지출을 넘는 외삽을 방지합니다. 나머지 채널은 0~60%입니다. 총예산이 달라지면 같은 비중 경계만으로 관측 지출 범위 준수를 보장할 수 없습니다.</p>
      <p className="mt-3 text-sm leading-7 text-slate-600">S0 대비 paired 증분은 같은 draw의 두 배분 매출을 빼서 구합니다. 매출 구간의 양 끝을 빼서 증분 구간을 만들지 않으며 P(증분&gt;0)도 모델 조건부 확률입니다. 최적 비중은 추정치로 실제 집행의 매출 증가를 보장하지 않습니다.</p>
      <p className="mt-3 text-sm leading-7 text-slate-600">운영 경계안의 문서 비중 합계는 99.9%입니다. 정확한 내부 비중이 없어 원문을 보존합니다. Simulator는 이를 그대로 불러와 사용자의 보정을 요구하며 매출·ROAS·80% 구간을 새로 계산하지 않습니다.</p>
      <Link href="/optimization/" className="mt-3 inline-flex min-h-11 items-center text-sm font-semibold text-teal-800 underline">배분·paired 증분과 불확실성 보기 →</Link>
    </Panel>
    <Panel title="출처 구분과 확인된 차이" note="CSV 재집계와 문서 기록값을 구분합니다. 현재 웹에서 모델 재학습·추정은 수행하지 않습니다.">
      <DataTable caption="웹 데이터의 출처·검증 범위" headings={["데이터", "출처 표식", "검증 범위"]} rows={[
        ["원본 주간 CSV 입력값", "과거 관측 기록으로 사용하는 입력", "원본 행은 비공개 · 실제 수집·가공 경위는 별도 미확인"],
        ["Overview·EDA 집계", "csv_computed", "원본 해시·기술통계·상관계수 재계산"],
        ["모델 성능·시나리오·최적화", "document_recorded", "2026-10-12 확정런 문서 대조 · trace 미검증"],
        ["Simulator 사용자 배분", "사용자 입력의 산술 계산", "합계·센트 금액·운영 제약 · 모델 예측 아님"],
      ]} />
      <p className="mt-4 text-sm leading-7 text-slate-600">SEM Q1은 CSV {number(Number(audit.sem_q1.csv_usd), 2)} USD와 문서 365,000 USD 사이에 {number(Number(audit.sem_q1.difference_usd), 2)} USD 차이가 있습니다. 통상 사분위수 계산법과 train/test 분할을 점검해도 문서값을 재현하지 못했습니다. 원인은 미확인으로 남기고 CSV 값과 기존 문서를 각각 유지합니다.</p>
      <p className="mt-3 text-sm leading-7 text-slate-600">최근 13주 실제 CSV 합계는 {number(Number(audit.recent_13_weeks_total_usd), 2)} USD(csv_computed), 문서 총액은 약 {results.budget_million_usd.toFixed(2)}M USD(document_recorded)입니다. 16,200,000 USD와 실제 합계의 차이는 {number(Math.abs(Number(audit.actual_minus_document_usd)), 2)} USD입니다. 기존 모델 기록과 Simulator 기본값은 문서 기준으로 유지하며, 이를 실제 집계의 정확값이라고 표시하지 않습니다.</p>
    </Panel>
    <Panel title="공개 출처·라이선스 및 남은 확인" note="권리 재점검: 2026-11-09 · 원본 CSV와 행별 시계열은 정적 사이트에 포함하지 않습니다.">
      <p className="text-sm leading-7 text-slate-600">공개 저장소 <a href="https://github.com/sibylhe/mmm_stan/blob/main/data.csv" className="font-semibold text-teal-800 underline">sibylhe/mmm_stan의 data.csv</a>가 로컬 원본과 SHA-256 기준 바이트 단위로 일치합니다. 해당 저장소에는 <a href="https://github.com/sibylhe/mmm_stan/blob/main/LICENSE" className="font-semibold text-teal-800 underline">MIT 라이선스</a>가 있으며 저작권자는 Sibyl He(2021)로 표시되어 있습니다.</p>
      <p className="mt-3 rounded-lg border border-amber-200 bg-amber-50 p-4 text-sm leading-7 text-amber-950">데이터 자체의 별도 이용·재배포 허락과 최초 수집 출처는 미확인입니다. 저장소의 MIT 표시만으로 데이터 공개 권한을 확정하지 않습니다. 집계와 모델 결과의 공개 범위 및 필요한 저작권 고지를 공개 전 확인해야 합니다.</p>
      <p className="mt-3 text-sm leading-7 text-slate-600">원본 README는 209주 매출·매체 노출·지출 기록을 설명하지만, 데이터의 실제 생성자·최초 수집 기관·제3자 권리나 별도 허락은 명시하지 않습니다. 업로더와 LICENSE의 저작권 표시만으로 데이터 권리자를 단정하지 않습니다. 분석 기간은 2014~2018년이며 현재 시장 실적이 아닙니다.</p>
      <p className="mt-3 text-sm leading-7 text-slate-600">MIT 원문은 소프트웨어와 관련 문서에 대한 허락 및 저작권·허락 고지 유지 조건을 담고 있습니다. <a href="/third-party/mmm-stan-LICENSE.txt" className="font-semibold text-teal-800 underline">저작권·허락·면책 문구를 포함한 MIT 원문 고지</a>를 그대로 보존했습니다. 이는 데이터 또는 파생 통계의 게시 허락을 새로 부여하거나 본 프로젝트 전체에 MIT를 적용한다는 뜻이 아닙니다.</p>
      <p className="mt-3 text-sm leading-7 text-slate-600">자체 작성한 분석 코드·화면의 권리와 입력 데이터의 권리는 구분해야 합니다. CSV 집계값과 문서에 기록된 모델 추정 결과는 직접 만든 결과라도 원본 데이터에 기반하므로 공개 가능 여부를 별도로 확인해야 합니다. 집계·시나리오·최적화 수치는 HTML·JS·RSC에 포함되어 읽힐 수 있으며 원본 CSV를 제외해도 이 공개가 차단되지는 않습니다.</p>
      <p className="mt-3 text-sm leading-7 text-slate-600">본 프로젝트의 모델은 위 저장소의 구현을 그대로 설명하는 것이 아니라 기존 Python 코드의 가산형 Bayesian MMM입니다. 시각화된 추정치는 관측자료와 모델 가정에 따른 결과이며 실제 집행 성과와 구분해야 합니다.</p>
    </Panel>
    <Panel title="분석 근거 문서" note="모델 수치는 각 문서의 2026-10-12 확정런 절을 사용하며 이전 실행 이력과 혼용하지 않습니다.">
      <ul className="grid gap-3 text-sm sm:grid-cols-2">{sources.map(source => <li key={source}><a className="inline-flex min-h-11 items-center break-all font-medium text-teal-800 underline" href={`https://github.com/LEE-ok/trend-aware-mmm/blob/feature/nextjs-dashboard/docs/${source}`}>{`docs/${source}`}</a></li>)}</ul>
    </Panel>
  </div>;
}
