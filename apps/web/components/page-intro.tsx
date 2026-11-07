import { getPage, type PagePath } from "@/lib/navigation";

export function PageIntro({ path }: { path: PagePath }) {
  const page = getPage(path)!;

  return (
    <div className="mx-auto w-full max-w-6xl">
      <div className="border-b border-slate-200 pb-8">
        <p lang="en" className="text-xs font-semibold uppercase tracking-[0.18em] text-teal-800">{page.english}</p>
        <h1 className="mt-3 text-3xl font-bold tracking-tight text-slate-950 sm:text-4xl">{page.label}</h1>
      </div>
      <section aria-label={`${page.label} 안내`} className="mt-8 rounded-2xl border border-slate-200 bg-white px-6 py-12 sm:px-12 sm:py-16">
        <div aria-hidden="true" className="mb-7 inline-flex size-12 items-center justify-center rounded-xl border border-teal-100 bg-teal-50 text-teal-800">
          <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
            <rect x="4" y="3" width="16" height="18" rx="2" />
            <path d="M8 8h8M8 12h8M8 16h4" />
          </svg>
        </div>
        <p className="max-w-2xl text-base leading-8 text-slate-600 sm:text-lg">{page.description}</p>
      </section>
    </div>
  );
}
