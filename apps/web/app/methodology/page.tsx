import type { Metadata } from "next";
import { PageIntro } from "@/components/page-intro";

export const metadata: Metadata = { title: "분석 방법론" };
export default function MethodologyPage() { return <PageIntro path="/methodology" />; }
