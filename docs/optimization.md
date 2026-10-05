# 예산 최적화 — posterior-mean 탐욕 재배분

`python -m trend_mmm optimize data/raw/data_GIT.csv --summary artifacts/bayes_summary.json --total 16200000 --weeks 13 [--bounds '{...}']`

## 방법

후기평균 반응면 위 탐욕 한계재배분(`optimization/allocate.py`).
총액 고정, 매 스텝 최저 한계ROAS 채널 → 최고 채널로 0.1%p 이동.
한계효율 격차가 2% 이내면 수렴. Hill 포화라 오목성이 보장됨.
기본 경계: 채널별 [0%, 60%]. `--bounds` JSON으로 변경 가능.

## 결과 (총 16.20M, 13주)

- 최적 비중: dm 0.0% / so 4.1% / vidtr 30.8% / viddig 6.2% / sem 58.9%.
- 예상 매출 19.81억. S0(12.98억) 대비 +52.6%. S1_15(16.13억)보다 높음.
- 수렴 498회. 외삽 플래그 없음(전 채널 관측 범위 내).
- 수렴 시 한계ROAS ≈ 61로 균등화.

## 주의

- posterior-mean 점최적. 구간 없음. S0~S4 구간과 직접 비교 금지.
- dm 0%는 모델 결론이지 운영 권고가 아님. 실제 집행은 채널별 최소 집행률
  bound(예: dm ≥ 5%)를 `--bounds`로 강제 후 재계산할 것.
- +52%는 반응면 외삽이 아니라 범위 내 재배분 결과이나, posterior 불확실성
  (dm/so/viddig beta sd 큼)을 고려하면 낙관 편향 가능. trace draws 전체로
  최적 분포를 구하는 것이 다음 단계.
