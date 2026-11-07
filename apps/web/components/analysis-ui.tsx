import type { ReactNode } from "react";

export function AnalysisHeading({ english, title, children }: { english: string; title: string; children: ReactNode }) {
  return <header className="mb-8 border-b border-slate-200 pb-7">
    <p lang="en" className="text-xs font-semibold uppercase tracking-[0.18em] text-teal-800">{english}</p>
    <h1 className="mt-3 text-3xl font-bold tracking-tight text-slate-950 sm:text-4xl">{title}</h1>
    <p className="mt-4 max-w-3xl text-sm leading-7 text-slate-600">{children}</p>
  </header>;
}

export function Panel({ title, note, children }: { title: string; note?: string; children: ReactNode }) {
  return <section className="min-w-0 rounded-2xl border border-slate-200 bg-white p-5 sm:p-7">
    <h2 className="text-lg font-bold text-slate-900">{title}</h2>
    {note ? <p className="mt-2 text-xs leading-6 text-slate-500">{note}</p> : null}
    <div className="mt-5">{children}</div>
  </section>;
}

export function Metric({ label, value, note }: { label: string; value: string; note: string }) {
  return <div className="min-w-0 rounded-xl border border-slate-200 bg-white p-5">
    <p className="text-xs font-medium text-slate-500">{label}</p>
    <p className="mt-3 break-words text-2xl font-bold tracking-tight text-slate-950">{value}</p>
    <p className="mt-2 text-xs leading-5 text-slate-500">{note}</p>
  </div>;
}

export function SourceLabel({ children }: { children: ReactNode }) {
  return <span className="inline-block rounded-md bg-teal-50 px-2.5 py-1 text-xs font-medium leading-5 text-teal-800">{children}</span>;
}

export function DataTable({ caption, headings, rows }: { caption: string; headings: string[]; rows: ReactNode[][] }) {
  return <div className="max-w-full overflow-x-auto rounded-lg border border-slate-200" role="region" aria-label={caption} tabIndex={0}>
    <table className="w-full min-w-[520px] text-left text-xs leading-6">
      <caption className="px-4 py-3 text-left text-xs text-slate-500">{caption}</caption>
      <thead className="border-y border-slate-200 bg-slate-50 text-slate-600"><tr>{headings.map(h => <th scope="col" className="whitespace-nowrap px-4 py-3 font-semibold" key={h}>{h}</th>)}</tr></thead>
      <tbody className="divide-y divide-slate-100">{rows.map((row, index) => <tr key={index}>{row.map((cell, i) => i === 0 ? <th scope="row" className="whitespace-nowrap px-4 py-3 font-medium text-slate-800" key={i}>{cell}</th> : <td className="whitespace-nowrap px-4 py-3 tabular-nums text-slate-600" key={i}>{cell}</td>)}</tr>)}</tbody>
    </table>
  </div>;
}
