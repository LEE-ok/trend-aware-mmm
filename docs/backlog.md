# 개발 백로그
- [x] Python 패키지와 폴더 구조
- [x] CSV 계약 및 기본 검증
- [x] 예시 CSV와 검증 테스트
- [x] 2주: 업종·채널·성과 지표 확정 / 승아 → 계약 v0.2: 미국 리테일 회고 시뮬레이션, 5채널 코어(dm/so/vidtr/viddig/sem), sales 타깃, USD
- [x] 2주: 실제 데이터 탐색, 합성 시나리오 명세 / 승아 → data_GIT.csv 209주(2014-08-03~2018-07-29) 채택, 보조 20만행은 RAG/UI용으로 격리
- [ ] 2주: 전처리·합성 생성 / 종석 → 전처리 파이프라인 완료(`data/preprocess.py`). 합성은 실측 채택으로 대체
- [x] 3주: 수집기 MVP(파일 기반 collect→clean→aggregate_weekly) / 종석. 자동 크롤러는 6~7주로 연기. 출처·라벨 정의는 승아 확인 필요
- [x] 4주: 기본 MMM·시간순 검증 / 종석 → 베이스라인(adstock+saturation+OLS, test MAPE 0.370) 완료. `docs/eda.md` 참고
- [ ] 4~5주: 사전분포 근거 확정 / 승아 → 초안(`docs/priors.md`) 작성됨, 도메인 검토 필요
- [x] 6~7주: Vector DB·LangGraph / 종석 → Chroma 스토어 + LangGraph 수집 파이프라인 완료(`docs/retrieval.md`). 크롤러 자동화는 연기
- [x] 8주: 트렌드 모델 비교 및 채택 여부 결정 / 공동 → 채택. test MAPE 0.336→0.305, 순위 강건. `docs/trend-compare.md`
- [x] 9~10주: 예산 제약, 최적화, what-if / 공동 → S0~S4 산출 + 경계 최적화 완료(`docs/optimization.md`, `optimization/allocate.py`). draws 전체 분포 최적은 다음
- [x] 11~13주: UI 및 설명 / 공동 → Streamlit MVP(`apps/dashboard/app.py`: EDA, S0-S4, what-if). 챗봇은 보류
- [ ] 14~15주: 통합 평가, 보고서, 데모 / 공동

## 완료 기준
요구사항 연결, 입력·출력 명시, 의미 있는 검증, README 갱신, 동료 검토.
핵심 시뮬레이터가 완성되기 전에는 Neo4j와 챗봇 고도화를 시작하지 않습니다.

