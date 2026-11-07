import type { Metadata } from "next";
import { DashboardNavigation } from "@/components/navigation";
import "./globals.css";

export const metadata: Metadata = {
  title: { default: "분석 개요 | Trend-aware MMM", template: "%s | Trend-aware MMM" },
  description: "마케팅 예산 분석과 Bayesian MMM의 가정 및 결과를 살펴보는 한국어 대시보드",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="ko">
      <body className="min-h-screen bg-slate-50 font-sans text-slate-900 antialiased">
        <a href="#main-content" className="fixed left-4 top-4 z-50 -translate-y-24 rounded-lg bg-teal-900 px-5 py-3 text-sm font-semibold text-white focus:translate-y-0">본문 바로가기</a>
        <DashboardNavigation />
        <main id="main-content" tabIndex={-1} className="min-h-[calc(100svh-5rem)] px-5 py-10 sm:px-8 sm:py-12 lg:ml-72 lg:px-12">{children}</main>
      </body>
    </html>
  );
}
