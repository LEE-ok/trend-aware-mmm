# 트렌드 데이터 — Google Trends 실측

## 출처·재현

- 명령: `python -m trend_mmm trends-fetch --out data/raw/trends_google.csv`
- 키워드: sale, deals, coupons, gift (미국, 2014-08-03~2018-07-29, 주간).
- `christmas`는 제외. 연말 스파이크는 휴일 묶음(`hol_year_end`)이 이미 커버.
- 값은 요청 구간 최대값 대비 0~100 상대지수. Google이 요청마다 리샘플링하므로
  재수집 시 소수점 변동 가능. 형태(계절성·스파이크)는 안정.
- 209주, 결측 없음, `data_GIT.csv` 주와 일자 일치 확인.

## 합성

- 채널 합성지수 `trend_demand` = 키워드별 z-score 평균.
- sales와 단순 상관: gift 0.746, coupons 0.564, deals 0.427, sale -0.131, 합성 0.665.
- gift가 높은 것은 크리스마스 겹침 의심. 휴일·계절 통제 후 추가 설명력이
  남는지 모델 비교(베이스 vs 결합, 동일 test 26주)로 판정. 상관만으로 채택 금지.

## 모델 투입

- `bayes --trend <csv>`: 합성지수를 train 통계로 표준화해 보조 1열 추가.
  prior는 다른 보조와 동일 Normal(0, AUX_SD).
- 예측(forecast) 시점 실제 트렌드값은 모름. 시나리오는 mean(최근 13주 평균)/
  low(train p10)/high(train p90) 3수준으로 평가. `scenarios --trend --trend-level`.
