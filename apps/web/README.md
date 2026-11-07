# Trend-aware MMM 웹 대시보드

M0: 한국어 공통 레이아웃과 안내 페이지. M1: Overview·EDA에 집계 JSON을 연결했습니다.
웹은 원본 CSV나 모델 파일을 직접 읽지 않습니다.
Node.js 24 LTS 및 npm을 기준으로 합니다. 기존 Python 프로젝트와 독립적으로 실행합니다.

```powershell
cd apps/web
npm.cmd install
npm.cmd run typecheck
npm.cmd run lint
npm.cmd run build
npm.cmd run dev
```

PowerShell 실행 정책이 npm.ps1을 차단하는 환경에서는 위와 같이 npm.cmd를 사용합니다.

경로: `/`, `/eda/`, `/scenarios/`, `/optimization/`, `/simulator/`, `/methodology/`.
Simulator는 모델 결과 확보 안내만 제공합니다.

`output: 'export'`로 빌드하며 정적 결과는 `out/`에 생성됩니다.
정적 파일 서버에서 `out/`을 제공하면 별도 Node.js/Python 서버가 필요하지 않습니다.
Vercel 배포 시 Root Directory는 `apps/web`입니다. 이번 단계에서는 배포하지 않습니다.

Windows의 Next.js 정적 export에서 RSC 파일 경로가 중첩되는 알려진 문제를
`scripts/normalize-static-export.mjs`가 빌드 후 보정합니다. 생성된 `out/` 안에만
올바른 파일명 별칭을 추가하며 Linux의 정상 출력에서는 변경하지 않습니다.

폰트는 한국어 시스템 글꼴을 사용하며 외부 폰트·API·DB·로그인을 요구하지 않습니다.

## M1 집계 데이터

Overview와 EDA는 `data/dashboard-aggregates.json`을 사용합니다. 서버나 외부 API 없이
빌드에 포함되며 원본 CSV를 배포하지 않습니다. 원본의 행별 데이터·날짜별 매출은
포함하지 않고 합계·비중·5수치 분포·상관계수만 내보냅니다. 최소·최대는 허용된
요약통계이며 관측 날짜와 연결하지 않습니다. 집계 공개가 원본 공개 승인을 뜻하지 않습니다.

저장소 루트에서 기존 Python 환경으로 실행합니다. 모델 학습은 하지 않습니다.

```powershell
.venv\Scripts\python.exe -B apps/web/scripts/export_dashboard_data.py
```

변환기는 `data/dashboard.schema.json`을 검증하고 출력 파일을 새로 생성하는 경우에만
저장합니다. 기존 출력이 있으면 중단합니다. 재계산을 검토할 때는 새 경로를 지정하세요.

```powershell
.venv\Scripts\python.exe -B apps/web/scripts/export_dashboard_data.py --output apps/web/.verification/recomputed.json
```

원본 집계는 `csv_computed`, 모델 성능은 `document_recorded`로 구분합니다.
모델 수치는 `docs/bayes-run.md`의 2026-10-12 확정런에서 읽으며 trace를 검증한 값이 아닙니다.
EDA 문서와 금액 ±0.5 USD, 상관계수 ±0.0005, 근사 만 단위 ±500 USD로 36건을 비교합니다.
35건은 일치하며 SEM Q1 서술 1건은 문서 약 365,000 USD와 CSV 355,954.51 USD로
차이가 있습니다. 단순 반올림으로 설명되지 않으며 원인은 미확인입니다. 원본 계산값을
유지하고 웹에 차이를 알립니다. 문서 불일치는 CSV 형식 검증 실패와 구분합니다.
지출 비중은 전체 209주 합계 기준이며 시나리오의 최근 13주 기준 비중과 다릅니다.
원본의 최초 출처·라이선스 확인은 별도 과제입니다. 이번 단계는 배포하지 않습니다.

빌드 후 저장소 루트에서 검증합니다. 기존 jsonschema·NumPy·SciPy를 사용합니다.

```powershell
.venv\Scripts\python.exe -B apps/web/scripts/test_dashboard_data.py
```

검사 범위: 엄격한 JSON 스키마, 원본 해시·기간·분할, 독립 집계·상관계수 대조,
문서 기록, 비밀값·행별 데이터 제외 정책, 정적 결과물의 원본 CSV·주간 관측값 미포함.
