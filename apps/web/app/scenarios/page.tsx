import type { Metadata } from "next";
import { PageIntro } from "@/components/page-intro";

export const metadata: Metadata = { title: "시나리오 비교" };
export default function ScenariosPage() { return <PageIntro path="/scenarios" />; }
