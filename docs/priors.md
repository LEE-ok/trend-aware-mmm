# 사전분포 근거 v1.0

상태: **확정(2026-10-12).** 아래 "Prior 수치표 v1.0"을 확정값으로 사용한다.
코드(`src/trend_mmm/mmm/bayesian.py`의 `CHANNEL_PRIORS` 등)와 수치가 일치하며, 지금까지의 모든 실행이 이 값을 썼다.
위쪽 절(사전 기대, EDA 2차 메모)은 수치표에 이르기까지의 근거 기록이다. 그 안의 "확정 전" 표현은 작성 당시 기준.
베이스라인(`docs/eda.md`)에서 `mdsp_so` 음수 계수가 나온 것이 제약 필요성의 근거.

## 읽는 법 (모델 구조 요약)

주간 매출 = 절편 + Σ 채널 beta × Hill(adstock(지출)) + 보조변수 × gamma + 오차.

- **adstock(이월)**: `carry_t = spend_t + decay × carry_{t-1}`. 이번 주 광고 효과가 다음 주에 decay 비율만큼 남는다.
  decay prior가 채널별 Uniform 구간인 이유는 매체 특성(TV는 길게, 검색은 짧게)을 범위로만 제한하고 값은 데이터가 정하게 하려는 것.
- **Hill 포화**: `x^alpha / (x^alpha + ec50^alpha)`, 0~1. 지출이 늘수록 효과 증가폭이 줄어드는 수확체감을 표현.
  ec50은 효과가 절반에 이르는 지출 수준(train 중앙값 고정), alpha는 곡선 모양(1 이하 오목, 1 초과 S자).
- **beta ~ HalfNormal**: 채널 최대 기여(포화 시 주간 매출 증분). 0 이상으로 제약해 "광고가 매출을 줄인다"는 추정을 막는다.
  σ는 강도 기대에 따라 차등(vidtr·sem 1.5e8, 나머지 5e7).
- 사전분포는 값을 고정하는 것이 아니라 허용 범위를 정하는 것. posterior가 prior 경계에 붙으면 범위 재검토 신호.

## 채널별 사전 기대 (부호·상대 강도)

| 채널 | 기대 부호 | 상대 강도 근거 |
|---|---|---|
| mdsp_dm | + | 도달은 넓으나 반응률 낮음. EDA 상관 0.149로 최약. 약한 양의 효과 |
| mdsp_so | + | 타깃 정교, EDA 상관 0.335. 중간 양의 효과 |
| mdsp_vidtr | + | TV 도달·브랜드 효과 큼. EDA 상관 0.657로 최강. 강한 양의 효과 |
| mdsp_viddig | + | 온라인 영상, 측정 가능. EDA 상관 0.458. 중간 양의 효과 |
| mdsp_sem | + | 검색 의도 강함. EDA 상관 0.586. 강한 양의 효과 |

모든 채널 계수는 0 이상으로 제약(광고비가 매출을 줄인다는 추정은 허용하지 않음).
상대 강도는 EDA 상관 + 도메인 상식의 결합이며, 최종 수치는 PyMC 구현 시 확정.

## 이월(Adstock) 기대

- vidtr: 길게(감쇠 큼). TV 브랜드 잔존.
- dm: 중간.
- so/viddig: 중간~짧음. 디지털 피로 빠름.
- sem: 짧게(감쇠 작음). 검색은 즉시 반응.

베이스라인 그리드 선택값 decay=0.5를 중심 출발점으로 사용.

## 포화(Saturation) 기대

- 전 채널 수확체감 가정. Hill alpha < 1 출발.
- sem은 포화점이 높게(수요上限까지 탄력), dm은 포화점이 낮게(낭비 구간 빠름).

## 결정 사항 (v1.0에서 정리됨)

1. 강도 순서(vidtr≈sem > viddig≈so > dm) → beta σ 차등으로 반영.
2. 외부변수(`me_gas_dpg, me_ics_all, st_ct`) → 표준화 통제변수로 투입. 시나리오에서는 최근 13주 평균 고정.
3. 휴일(`hldy_*`) → 연말/기타 2묶음의 별도 항.


---

## EDA 2차 반영 메모 — 2026-09-28

기존 사전분포 초안은 유지하고, 추가 EDA 결과를 참고용으로 아래에 기록한다.
본 내용은 prior 확정값이 아니라 Bayesian MMM 구현 전 검토용 근거이다.

### Adstock 관련 추가 근거

lag 0~8주 탐색 결과:

- `mdsp_dm`: 당주보다 1~2주 lag에서 sales와의 관계가 상대적으로 높게 나타남.
- `mdsp_so`: 당주 관계가 가장 높게 나타남.
- `mdsp_vidtr`: 당주 관계가 가장 높게 나타남.
- `mdsp_viddig`: 당주 관계가 가장 높게 나타남.
- `mdsp_sem`: Pearson 기준 2주 lag에서 가장 높은 값이 나타남.

단, 위 결과는 단순 시차 상관 탐색 결과이며 adstock decay 확정값으로 사용하지 않는다.
최종 decay 범위는 Bayesian MMM posterior 및 모델 적합도를 확인한 뒤 조정한다.

### Saturation 관련 추가 근거

- 일부 채널에서 고지출 구간의 매출 증가폭이 둔화되는 형태가 관찰됨.
- 다만 log 변환이 선형 모형보다 일관되게 높은 설명력을 보이지 않음.
- 따라서 현재 EDA만으로 채널별 포화 강도나 포화점을 확정하지 않음.
- 전 채널에 수확체감 구조는 적용하되, Hill saturation 파라미터는 넓은 prior에서 시작하는 방향을 검토한다.

### 외부변수 및 휴일 관련 추가 근거

- `st_ct`, `me_gas_dpg`, `me_ics_all` 등 주요 외부변수는 sales와의 단순 상관이 크지 않음.
- 단순 상관이 낮더라도 교란변수로 작용할 수 있으므로 제외를 확정하지 않음.
- 일부 `hldy_*` 변수는 비교적 높은 상관이 확인되었으나 발생 주차가 적고 계절성과 겹칠 가능성이 있음.
- 외부변수 및 휴일 변수는 최종 모델 설계 단계에서 통제변수 포함 여부를 재검토한다.

### 해석 주의

- 상관계수 및 lag 탐색 결과는 인과효과를 의미하지 않음.
- 현재 결과는 prior 범위를 좁히기 위한 탐색 근거로만 사용함.
- 기존 `priors.md`의 가정은 Bayesian MMM 구현 및 posterior 검증 전까지 확정값으로 간주하지 않음.


---

## Prior 수치표 v1.0 — 2026-09-28 적용, 2026-10-12 확정

아래는 코드 구현용 확정값. EDA 상관 + 매체 상식 + 업계 표준(Hill + 비음수 계수) 반영.

| 채널 | beta prior | decay prior | alpha prior | ec50 |
|---|---|---|---|---|
| mdsp_dm | HalfNormal(σ=5e7) | Uniform(0.3, 0.7) | Uniform(0.3, 1.5) | train 중앙값 고정 |
| mdsp_so | HalfNormal(σ=5e7) | Uniform(0.0, 0.4) | Uniform(0.3, 1.5) | train 중앙값 고정 |
| mdsp_vidtr | HalfNormal(σ=1.5e8) | Uniform(0.3, 0.7) | Uniform(0.3, 1.5) | train 중앙값 고정 |
| mdsp_viddig | HalfNormal(σ=5e7) | Uniform(0.0, 0.4) | Uniform(0.3, 1.5) | train 중앙값 고정 |
| mdsp_sem | HalfNormal(σ=1.5e8) | Uniform(0.0, 0.5) | Uniform(0.3, 1.5) | train 중앙값 고정 |

- intercept: Normal(μ=train sales 평균, σ=3e7).
- sigma_obs: HalfNormal(σ=4e7) (sales 표준편차 규모).
- 통제·휴일·계절 계수: Normal(0, 1e7) (표준화 투입이므로 보수적).
- ec50은 1차 실행에서 추정하지 않고 train 중앙값 고정. 2차에서 추정 전환 검토.
- beta σ 차등 근거: EDA 상관 강도(vidtr 0.657, sem 0.586 > viddig 0.458, so 0.335 > dm 0.149).
