# 구성 및 구현 경계
2인 프로젝트의 초기 구조로 단일 Python 패키지를 사용합니다.

## 데이터 흐름
마케팅 CSV → data → mmm 학습·검증 → 모델 아티팩트 → simulation / optimization → dashboard

트렌드 출처 → trends 수집·정제 → retrieval 문서 저장·검색
→ trends 주별 변수 생성 → 정량 데이터와 결합 → mmm 검증

workflows는 수집·정제·변수 생성의 실행 순서와 실패 처리를 관리합니다.
Vector DB는 문서 검색용이며 정량 시계열의 원본 저장소가 아닙니다.

## 구현 원칙
- UI는 계산 로직을 직접 구현하지 않고 패키지를 호출합니다.
- 시뮬레이션 요청마다 모델을 재학습하지 않습니다.
- 모델 버전, 데이터 기준일, 시나리오 가정을 결과에 포함합니다.
- 과거 시계열이 없는 최신 뉴스는 설명 또는 시나리오에만 활용합니다.
- 기본 MMM과 트렌드 MMM을 동일 시간순 검증 구간에서 비교합니다.
- 실제 사후표본을 확보하기 전에는 신뢰구간이나 투자 추천 범위를 만들어 표시하지 않습니다.
- 설정 파일은 후속 구현 명세이며 아직 실행 코드와 연결되지 않았습니다.

## 후속 인터페이스 초안
- mmm: fit(weekly_data, config), predict(posterior, scenario)
- trends: collect(source, time_range), aggregate_weekly(documents)
- retrieval: search(query, available_before, filters)
- optimization: optimize(posterior, budget, bounds, scenario)
- simulation: simulate(posterior, allocation, scenario)

구체 자료형은 첫 모델 구현 단계에서 확정합니다.

