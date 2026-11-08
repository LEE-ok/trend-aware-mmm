import { SourceLabel } from "@/components/analysis-ui";
import { results } from "@/lib/mmm-results";

export function RecordedSource({ source }: { source: string }) {
  return <div className="mb-6 space-y-3 text-xs leading-6 text-slate-600">
    <SourceLabel>document_recorded · 확정런 {results.run_date} · 문서 수치 대조 통과</SourceLabel>
    <p>출처: <code>{source}</code>의 2026-10-12 확정런 절. 문서 기록값이며 trace는 미검증입니다. 모델 재학습·재계산 없이 표시합니다.</p>
    <p>13주 합계 · 금액 단위: 억 USD · 총 광고예산 1,620만 USD 고정. 균등 주배분, 이월 0에서 시작, 보조변수와 trend 수준은 최근 13주 평균 고정 가정입니다.</p>
  </div>;
}

export function Extrapolation({ active }: { active: boolean }) {
  return <span className={active ? "font-semibold text-amber-900" : "text-slate-600"}>{active ? "⚠ 외삽 · VIDDIG" : "외삽 없음"}</span>;
}

export function ModelSelect({ id, label, value, options, onChange }: { id: string; label: string; value: string; options: { id: string; label: string }[]; onChange: (value: string) => void }) {
  return <div className="mb-6 flex flex-col items-start gap-2">
    <label htmlFor={id} className="text-sm font-semibold text-slate-800">{label}</label>
    <select id={id} value={value} onChange={event => onChange(event.target.value)} className="w-full max-w-md rounded-lg border border-slate-300 bg-white p-3 text-sm text-slate-900">
      {options.map(option => <option key={option.id} value={option.id}>{option.label}</option>)}
    </select>
  </div>;
}
