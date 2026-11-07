export const navigation = [
  { href: "/", label: "분석 개요", english: "Overview", description: "프로젝트의 목적과 분석 흐름을 살펴보는 공간입니다. 주요 지표와 모델 성능은 데이터 연동 단계에서 제공할 예정입니다." },
  { href: "/eda", label: "탐색적 분석", english: "EDA", description: "매출과 광고비의 흐름, 채널별 특성을 살펴보는 공간입니다. 원본 데이터 기반의 표와 그래프는 후속 단계에서 연결합니다." },
  { href: "/scenarios", label: "시나리오 비교", english: "Scenarios", description: "기준 예산을 유지하는 S0와 채널 간 예산을 이동하는 S1~S4를 비교하는 공간입니다. 결과는 출처와 분석 조건을 함께 표시할 예정입니다." },
  { href: "/optimization", label: "예산 최적화", english: "Optimization", description: "기존 배분과 최적 예산 배분 결과를 비교하는 공간입니다. 예상 증분과 불확실성은 검증된 자료를 연결한 뒤 제공합니다." },
  { href: "/simulator", label: "예산 시뮬레이터", english: "Simulator", description: "모델 결과 확보 후 활성화 예정" },
  { href: "/methodology", label: "분석 방법론", english: "Methodology", description: "Bayesian MMM의 구조, 데이터 출처, 분석 가정과 한계를 설명하는 공간입니다. 상세 내용은 기존 프로젝트 문서를 바탕으로 정리할 예정입니다." },
] as const;

export type PagePath = (typeof navigation)[number]["href"];

export function getPage(path: string) {
  const normalized = path === "/" ? path : path.replace(/\/$/, "");
  return navigation.find((page) => page.href === normalized);
}
