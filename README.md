# Trend-aware MMM

과거 마케팅 성과와 시장 트렌드를 활용한 다음 분기 예산 시뮬레이터.

## 현재 상태 (2026-10-12)
데이터는 `data_GIT.csv` 주간 209주(train 183 / test 26), 5채널(dm/so/vidtr/viddig/sem), 계약 v0.2.

| 모델 | test MAPE | 방향정확도 | max R-hat |
|---|---|---|---|
| 베이스라인(OLS) | 0.370 | 0.400 | — |
| Bayes 기본(4체인) | 0.336 | 0.400 | 1.004 |
| Bayes + trend(4체인) | 0.306 | 0.360 | 1.003 |

확정런(4체인, tune 2000, draws 1000) 기준입니다. 방향정확도는 개선되지 않았습니다.
채택 모델(trend)의 기대최적 배분은 S0 대비 +3.15억(80% 구간 [1.43, 4.86], 경계 적용안)입니다.

구현됨:
- 전처리·검증, 베이스라인 MMM, PyMC Bayesian MMM(adstock + Hill 포화, `docs/bayes-run.md`)
- Google Trends 결합과 채택 판정(`docs/trend-compare.md`)
- S0~S4 예산 시나리오, marginal ROAS, 외삽 플래그(`docs/scenario-results.md`)
- 예산 최적화: 점최적 + draws 전체 최적 분포(`docs/optimization.md`)
- Chroma 검색, LangGraph 트렌드 파이프라인(`docs/retrieval.md`)
- 파이프라인 출력 → 트렌드 변수 주입(`docs/retrieval.md`)
- 챗봇: LangGraph + Claude Haiku 툴콜(`docs/chatbot.md`)
- Streamlit 대시보드(`apps/dashboard/app.py`): EDA, 최적 배분, 챗, 시나리오, what-if, 반응곡선

미구현: 문서 검색 결과 기반 변수, 크롤러 자동화, Neo4j.

## 폴더 구조
```text
trend-aware-mmm/
├── apps/dashboard/       # 시뮬레이터 UI (Streamlit)
├── src/trend_mmm/
│   ├── data/             # CSV 검증, 전처리, 합성 데이터
│   ├── mmm/              # 학습, 진단, posterior 예측
│   ├── trends/           # 수집, 정제, 주별 변수 생성
│   ├── retrieval/        # 임베딩 및 문서 검색
│   ├── workflows/        # LangGraph 작업 흐름
│   ├── optimization/     # 예산 제약과 최적화
│   └── simulation/       # 학습된 모델 기반 what-if
├── configs/              # 비밀값 없는 실행 설정
├── data/
│   ├── sample/           # 저장소에 포함하는 예시 데이터
│   ├── raw/              # 원본 데이터 (Git 제외)
│   └── processed/        # 전처리 데이터 (Git 제외)
├── artifacts/            # 모델과 실행 결과 (Git 제외)
├── notebooks/            # 탐색 분석
├── tests/                # 자동 검증
├── docs/                 # 요구사항, 데이터 계약, 개발 순서
└── .github/              # CI, Issue 및 PR 템플릿
```

## 시작하기
Python 3.12 기준입니다. 저장소 루트에서 실행하세요.

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -e .
$env:PYTHONPATH = "src"
python -m trend_mmm validate data/sample/marketing.csv
python -m trend_mmm eda data/raw/data_GIT.csv
python -m trend_mmm baseline data/raw/data_GIT.csv --test-weeks 26 --out artifacts
python -m trend_mmm trends data/sample/trends.csv
python -m trend_mmm bayes data/raw/data_GIT.csv --draws 1000 --tune 2000 --chains 4 --out artifacts
python -m trend_mmm scenarios data/raw/data_GIT.csv --trace artifacts/bayes_trace.nc
python -m trend_mmm optimize-draws data/raw/data_GIT.csv --trace artifacts/bayes_trace.nc
python -m trend_mmm chat -q "예산을 어떻게 바꾸는 게 좋아?"
streamlit run apps/dashboard/app.py
python -m unittest discover -s tests -v
```

트렌드 결합 모델은 `bayes`, `scenarios`, `optimize-draws`에 `--trend data/raw/trends_google.csv`를 붙입니다.
의존성은 `pyproject.toml`에 있습니다(PyMC, ArviZ, Streamlit, Chroma, LangGraph 등).
챗봇은 `.env`의 `ANTHROPIC_API_KEY`가 필요합니다(`.env.example` 참고).
OneDrive 폴더에서 trace 저장이 잠기면 `--out`을 로컬 temp 경로로 지정하세요.

## 협업
- 승아: 데이터 적합성, 용어·변수 정의, 사전분포 근거, 결과 해석, 사용성 평가
- 종석: 전처리, 모델, 수집·검색, 최적화, UI 구현
- 작은 작업마다 feature 브랜치와 PR을 만들고 요구사항·검증 결과를 기록합니다.
- 데이터·API 키·모델 파일은 커밋하지 않습니다. sample에는 공개 가능한 예시만 둡니다.
- 라이선스는 팀 합의 후 추가합니다.

## 다음 작업
1. ~~사전분포 확정~~ → 완료(수치표 v1.0, `docs/priors.md`)
2. ~~최종 확정런~~ → 완료(R-hat 1.004 / 1.003, `docs/bayes-run.md`)
3. ~~E2E 통합 테스트~~ → 완료(`tests/test_e2e.py`)
4. ~~챗봇, 파이프라인 → 외부변수 주입~~ → 완료(`docs/chatbot.md`, `docs/retrieval.md`)
5. UI 정리, 최종 보고서·데모

docs/architecture.md, docs/data-contract.md, docs/backlog.md를 참고하세요.

