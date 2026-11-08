import type { Metadata } from "next";
import { AnalysisHeading } from "@/components/analysis-ui";
import { RecordedSource } from "@/components/mmm-shared";
import { OptimizationResults } from "@/components/optimization-results";

export const metadata: Metadata = { title: "예산 최적화" };
export default function OptimizationPage() { return <>
  <AnalysisHeading english="Optimization" title="예산 최적화">기대 매출을 기준으로 한 배분과 기존 S0를 비교합니다. 외삽을 방지하는 운영 경계안을 기본 권고안으로 제시합니다.</AnalysisHeading>
  <RecordedSource source="docs/optimization.md" />
  <OptimizationResults />
</>; }
