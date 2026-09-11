# Trend-aware MMM

과거 마케팅 성과와 시장 트렌드를 활용한 다음 분기 예산 시뮬레이터.

## 현재 상태
초기 개발 골격입니다. CSV 검증 CLI와 테스트만 구현되었습니다.
MMM 학습, 트렌드 API 수집, Vector DB, LangGraph, 예산 최적화, UI는 아직 구현되지 않았습니다.

## 폴더 구조
```text
trend-aware-mmm/
├── apps/dashboard/       # 시뮬레이터 UI (예정)
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
python -m trend_mmm validate data/sample/marketing.csv
python -m unittest discover -s tests -v
```

기본 코드는 Python 표준 라이브러리만 사용합니다. 향후 PyMC, LangGraph 등의 버전은 실제 통합 시 검증 후 고정합니다.

## 협업
- 승아: 데이터 적합성, 용어·변수 정의, 사전분포 근거, 결과 해석, 사용성 평가
- 종석: 전처리, 모델, 수집·검색, 최적화, UI 구현
- 작은 작업마다 feature 브랜치와 PR을 만들고 요구사항·검증 결과를 기록합니다.
- 데이터·API 키·모델 파일은 커밋하지 않습니다. sample에는 공개 가능한 예시만 둡니다.
- 라이선스는 팀 합의 후 추가합니다.

## 다음 작업
1. 업종·성과 지표·채널 확정
2. 실제 데이터 확보와 누락 처리 정책 결정
3. 합성 데이터 생성 및 기본 MMM 구축
4. 시간순 검증 후 트렌드 처리 연결
5. 최적화·시뮬레이터·UI 연결

docs/architecture.md, docs/data-contract.md, docs/backlog.md를 참고하세요.

