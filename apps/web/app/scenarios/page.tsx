import type { Metadata } from "next";
import { AnalysisHeading } from "@/components/analysis-ui";
import { RecordedSource } from "@/components/mmm-shared";
import { ScenarioResults } from "@/components/scenario-results";

export const metadata: Metadata = { title: "시나리오 비교" };
export default function ScenariosPage() { return <>
  <AnalysisHeading english="Scenarios" title="시나리오 비교">동일한 총 광고예산 아래 DM 예산을 다른 채널로 이동했을 때의 매출과 불확실성을 비교합니다.</AnalysisHeading>
  <RecordedSource source="docs/scenario-results.md" />
  <ScenarioResults />
</>; }
