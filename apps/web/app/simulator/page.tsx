import type { Metadata } from "next";
import { PageIntro } from "@/components/page-intro";

export const metadata: Metadata = { title: "예산 시뮬레이터" };
export default function SimulatorPage() { return <PageIntro path="/simulator" />; }
