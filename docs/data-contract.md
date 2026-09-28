# 주 단위 데이터 계약 v0.2
회고적 시뮬레이션용. 원천: `data_GIT.csv` 계열(미국 리테일, 2014-08-03~2018-07-29, 주간).
2026년 한국 시장 실측이 아니므로 "방법론 검증 + 회고적 시뮬레이션" 범위로 사용합니다.
통화는 USD 기준(원천 기준)이며 KRW가 아닙니다.

## 필수 컬럼(5채널 코어)

| 컬럼 | 정의 |
|---|---|
| wk_strt_dt | 주의 시작일, YYYY-MM-DD, 동일 요일, 오름차순, 7일 간격 |
| sales | 해당 주 총매출, 유한한 0 이상 숫자. 종속변수(Target) |
| mdsp_dm | Direct Mail 주간 광고비 |
| mdsp_so | Social Media 주간 광고비 |
| mdsp_vidtr | Traditional Video(TV) 주간 광고비 |
| mdsp_viddig | Digital Video(온라인 동영상) 주간 광고비 |
| mdsp_sem | Search Engine Marketing 주간 광고비 |

모든 광고비는 동일 통화의 유한한 0 이상 숫자입니다.
미집행은 0, 누락은 빈값입니다. 빈값을 자동으로 0으로 바꾸지 않습니다.
검증기는 빈값·주차 누락을 오류로 보고합니다. 보간 정책은 추후 확정합니다.

## 허용 추가 컬럼(검증 통과, 모델 투입은 별도 결정)

- 다른 `mdsp_*`(inst, nsp, auddig, audtr, on 등 10채널 확장 시)
- `mdip_*`(노출수, 보조 설명변수)
- `me_gas_dpg, me_ics_all, st_ct`(외부/판매환경 통제)
- `mrkdn_*`(프로모션 통제)
- `hldy_*, seas_prd_*, seas_week_*`(캘린더/계절성, 사전 확정 가능)
- `va_pub_*`는 검증기는 허용하지만 의미 불명이므로 모델 투입에서 제외합니다.

## 샘플과 원본 구분

- `data/sample/marketing.csv`: 형식 확인용 합성 8주 데이터입니다.
  모델 학습, 성능 평가, 실제 예산 결정에는 사용할 수 없습니다.
- 실제 `data_GIT.csv` 209주 원본은 `data/raw/`에 두고 Git에 커밋하지 않습니다.
  출처·라이선스는 보고서 전에 표기합니다.

트렌드 문서는 source_url, published_at, collected_at, category를 보관하고
과거 시점 평가에서는 당시 이용 가능했던 정보만 사용합니다.
원천 시계열(2014~2018)과 최신 트렌드 API 연도가 불일치하므로,
트렌드 결합은 회고 구간 재현 또는 시나리오 오버레이로만 주장합니다.
