import type { Metadata } from "next";
import { PageIntro } from "@/components/page-intro";

export const metadata: Metadata = { title: "예산 최적화" };
export default function OptimizationPage() { return <PageIntro path="/optimization" />; }
