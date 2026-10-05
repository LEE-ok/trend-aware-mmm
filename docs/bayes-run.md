# Bayesian MMM 1차 실행 — 2026-09-28

`python -m trend_mmm bayes data/raw/data_GIT.csv --test-weeks 26 --draws 500 --tune 1000 --chains 2`.
설정: priors v1.0(`docs/priors.md`), ec50은 train 중앙값 고정, 통제 3종 + 휴일묶음 2종 + `seas_prd_*`(첫 더미 제외).

## 성능 (베이스라인 대비)

| 구분 | MAPE | RMSE | 방향정확도 |
|---|---|---|---|
| 베이스라인 train(183주) | 0.296 | 38,789,490 | 0.544 |
| 베이스라인 test(26주) | 0.370 | 37,962,802 | 0.400 |
| Bayes train(183주) | 0.285 | 38,455,397 | 0.560 |
| Bayes test(26주) | **0.355** | **33,771,621** | 0.400 |

MAPE·RMSE 개선, 방향정확도는 동일. 예측용 확정치가 아니라 기준선+사전분포 검증용 1차 결과.

## Posterior 평균

| 채널 | beta 평균 (sd) | decay 평균 (sd) | alpha 평균 (sd) |
|---|---|---|---|
| mdsp_dm | 15,910,846 (12,859,716) | 0.49 (0.12) | 0.95 (0.34) |
| mdsp_so | 15,021,875 (12,262,497) | 0.19 (0.11) | 0.92 (0.35) |
| mdsp_vidtr | 93,640,548 (23,706,713) | 0.38 (0.06) | 1.26 (0.19) |
| mdsp_viddig | 24,788,002 (15,983,674) | 0.19 (0.11) | 1.01 (0.31) |
| mdsp_sem | 134,430,709 (29,331,833) | 0.22 (0.11) | 1.34 (0.13) |

- intercept 평균 -2,685,997 (sd 15,343,312). 0 근처, 포화특징+절편 트레이드오프 범위.
- sigma 평균 39,952,642.
- max R-hat 1.006. 수렴 양호.
- 전 채널 beta 양수. 베이스라인의 `mdsp_so` 음수 문제 해소됨.
- 강도 순서 sem≈vidtr > viddig≈so≈dm. priors 기대(vidtr≈sem > viddig≈so > dm)와 일치.
- dm/so/viddig의 beta sd가 평균과 비슷할 정도로 큼 → 해당 채널 기여도 불확실성 큼. S1~S4 해석 시 credible interval 필수.

## 4체인 확정런 — 2026-10-05

동일 설정 4체인(500 draws, tune 1000). trace `bayes_trace.nc` 확보.

- test: MAPE **0.336**, RMSE 33,461,832, 방향정확도 0.400. 2체인(0.355) 대비 개선.
- max R-hat **1.013**. 1.01 기준 살짝 초과. posterior 평균은 2체인과 사실상 동일(beta·decay·alpha 소수점 둘째자리 일치)이라 결론은 안정. 최종 보고 전 tune 연장 검토.
- Posterior 평균(2체인과 동일): sem beta 1.35억/decay 0.22, vidtr 9,377만/0.38, viddig 2,482만/0.19, so 1,530만/0.19, dm 1,609만/0.49.
- S0~S4는 4체인 trace로 재산출. S0 12.98억, S1_15 +24.2%, S3_10/15 외삽 플래그 유지. 순위·해석 변동 없음.

## 한계·다음

- 2체인 실행. R-hat 양호하나 최종 보고 전 4체인 권장.
- ec50 고정, alpha/decay posterior sd 큼 → 2차에서 ec50 추정 전환 검토.
- 다음: S0~S4 시나리오별 예상 sales·기여도·ROAS 산출(`docs/scenario.md` 9절).
- trace(`bayes_trace.nc`)는 OneDrive 잠금 회피를 위해 로컬 temp에 보관. 재현은 위 커맨드로 가능.
