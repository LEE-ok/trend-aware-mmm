# 대시보드 (Streamlit MVP)

`docs/architecture.md` 원칙대로 계산 로직 없이 패키지 호출만 합니다.

## 실행

저장소 루트에서:

```
streamlit run apps/dashboard/app.py
```

## 탭

- EDA: 주간 CSV 요약(규모, 0 집행 주, sales 상관).
- S0-S4 scenarios: `artifacts/scenario_results.json` 비교표. 없으면 생성 안내.
- What-if: 채널 비중 슬라이더 + 총예산 입력 → 예상 매출.
  `artifacts/bayes_trace.nc`가 있으면 100 draws 구간 포함,
  없으면 posterior-mean 근사(구간 없음) + 외삽 경고.

필요 아티팩트 생성:

```
python -m trend_mmm scenarios data/raw/data_GIT.csv --trace <bayes_trace.nc> --weeks 13
```
