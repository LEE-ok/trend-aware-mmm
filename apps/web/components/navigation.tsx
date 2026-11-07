"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useRef, useState } from "react";
import { getPage, navigation } from "@/lib/navigation";

function NavigationLinks({ onNavigate }: { onNavigate?: () => void }) {
  const pathname = usePathname();
  const current = getPage(pathname);

  return navigation.map((page) => {
    const active = current?.href === page.href;
    return (
      <Link
        key={page.href}
        href={page.href}
        aria-current={active ? "page" : undefined}
        onClick={onNavigate}
        className={`group flex min-h-14 items-center justify-between rounded-lg border px-4 py-3 text-sm ${active ? "border-teal-200 bg-teal-50 font-semibold text-teal-900" : "border-transparent text-slate-600 hover:bg-slate-100 hover:text-slate-950"}`}
      >
        <span>{page.label}</span>
        <span className={`text-[11px] ${active ? "text-teal-700" : "text-slate-500"}`} lang="en">{page.english}</span>
      </Link>
    );
  });
}

function Brand() {
  return (
    <Link href="/" aria-label="Trend-aware MMM 분석 개요" className="inline-flex items-center gap-3 rounded-md">
      <span aria-hidden="true" className="grid size-10 place-items-center rounded-xl bg-teal-900 text-sm font-bold tracking-tight text-white">tm.</span>
      <span>
        <span className="block text-sm font-bold tracking-tight text-slate-950" lang="en">Trend-aware MMM</span>
        <span className="mt-0.5 block text-[11px] text-slate-500">마케팅 예산 분석</span>
      </span>
    </Link>
  );
}

export function DashboardNavigation() {
  const pathname = usePathname();
  const current = getPage(pathname);
  const [open, setOpen] = useState(false);
  const toggleRef = useRef<HTMLButtonElement>(null);

  return (
    <>
      <aside className="fixed inset-y-0 left-0 z-30 hidden w-72 flex-col border-r border-slate-200 bg-white px-5 py-8 lg:flex">
        <div className="px-3"><Brand /></div>
        <p className="mb-3 mt-12 px-4 text-[10px] font-semibold uppercase tracking-[0.18em] text-slate-500" lang="en">Workspace</p>
        <nav aria-label="주 메뉴" className="space-y-1"><NavigationLinks /></nav>
        <div className="mt-auto border-t border-slate-200 px-4 pt-6">
          <p className="text-xs font-medium text-slate-700">분석의 근거를 함께 봅니다.</p>
          <p className="mt-2 text-xs leading-5 text-slate-500">데이터와 모델의 가정, 결과의 한계를<br />명확하게 전달하는 대시보드</p>
        </div>
      </aside>

      <header className="border-b border-slate-200 bg-white lg:ml-72">
        <div className="flex min-h-20 items-center justify-between gap-4 px-5 sm:px-8 lg:px-12">
          <div className="lg:hidden"><Brand /></div>
          <div className="hidden items-center gap-3 text-sm lg:flex">
            <span className="text-slate-500">분석 워크스페이스</span>
            <span aria-hidden="true" className="text-slate-300">/</span>
            <span className="font-medium text-slate-800">{current?.label ?? "페이지 안내"}</span>
          </div>
          <span className="hidden rounded-full border border-slate-200 px-3 py-1.5 text-xs text-slate-600 sm:inline-flex">Bayesian MMM</span>
          <button
            ref={toggleRef}
            type="button"
            aria-expanded={open}
            aria-controls="mobile-navigation"
            aria-label={open ? "메뉴 닫기" : "메뉴 열기"}
            onClick={() => setOpen(!open)}
            className="inline-flex min-h-11 min-w-11 items-center justify-center rounded-lg border border-slate-300 text-slate-700 hover:bg-slate-100 lg:hidden"
          >
            <svg aria-hidden="true" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round">
              {open ? <path d="m6 6 12 12M6 18 18 6" /> : <path d="M4 6h16M4 12h16M4 18h16" />}
            </svg>
          </button>
        </div>
        <nav
          id="mobile-navigation"
          aria-label="모바일 주 메뉴"
          hidden={!open}
          onKeyDown={(event) => {
            if (event.key === "Escape") {
              setOpen(false);
              toggleRef.current?.focus();
            }
          }}
          className="border-t border-slate-200 p-4 lg:hidden"
        >
          <NavigationLinks onNavigate={() => setOpen(false)} />
        </nav>
      </header>
    </>
  );
}
