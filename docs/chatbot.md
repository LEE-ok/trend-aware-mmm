# 챗봇 (11~12주차)

`python -m trend_mmm chat [data/raw/data_GIT.csv] [--artifacts artifacts] [--store artifacts/chroma] [-q "질문"]`
대시보드에서는 Chat 탭. `.env`에 `ANTHROPIC_API_KEY` 필요(변수명은 `.env.example`).

## 구조

`workflows/chat.py`. LangGraph 그래프 `model → tools → model → … → END`.

- model 노드: Claude Haiku 5.5(`claude-haiku-5-5`)를 Anthropic SDK로 호출. 툴 정의와 대화 전체를 보낸다.
- tools 노드: 모델이 요청한 툴을 실행하고 결과를 한 메시지로 돌려준다. 모델이 더 요청하지 않으면 종료.
- 무거운 연산 없음. 새 샘플링을 하지 않고 CLI가 이미 만든 산출물과 기존 모듈만 쓴다.

## 툴

| 툴 | 읽는 것 | 용도 |
|---|---|---|
| `get_model_summary` | `bayes_summary.json` | 정확도, R-hat, 채널별 posterior |
| `get_scenarios` | `scenario_results.json`, `scenario_trend_mean.json` | S0~S4 비교 |
| `get_optimum` | `optimum_draws*.json` | 기대최적 배분, 구간, paired 증분 |
| `evaluate_allocation` | `bayes_trace.nc` + `simulation/evaluate.py` | 사용자가 제안한 배분 what-if (기본 모델) |
| `search_trend_docs` | Chroma 스토어(`retrieval/store.py`) | 트렌드 문서 검색, `available_before`로 누설 차단 |

## 설계 원칙

- 숫자는 툴 결과에서만. 모델이 계산하거나 추정하지 않게 시스템 프롬프트에 명시.
- 모델이 틀리기 쉬운 판단은 코드가 한다. 첫 시험에서 Haiku가 겹치는 두 구간을 "겹치지 않는다"고 답해서,
  구간 겹침 여부(`sales_intervals_overlap`)와 S0 대비 paired 증분을 툴이 계산해 넘기도록 바꿨다.
- 툴 오류는 예외로 죽지 않고 `is_error` 결과로 모델에 돌아간다(파일 없음, 비중 합 ≠ 1 등).

## 확인한 것 (2026-10-12, 실제 API 호출)

- "예산을 어떻게 바꾸는 게 좋아?" → `get_optimum(trend_bounded)` + `get_model_summary` 호출,
  +3.15억 USD [1.43, 4.86], P 0.993, 구간 겹침과 test MAPE 한계를 함께 답함.
- 사용자 배분 what-if → `evaluate_allocation` 호출, S0 대비 paired 증분으로 답함.
- 문서 검색 → `search_trend_docs` 호출, 거리값이 커 관련성이 낮다고 답함(스토어에 샘플 문서뿐).
- 자동 테스트(`tests/test_chat.py`)는 API 없이 가짜 클라이언트로 그래프 루프와 툴 오류 처리를 검증.

## 한계

- 답변 품질 평가는 수동 확인 3건뿐. 정량 평가 세트 없음.
- what-if는 기본 모델 trace 기준. 채택 모델(trend) 수치는 `get_scenarios`/`get_optimum`의 trend 변형으로만 제공.
- 가끔 용어를 틀린다(예: 13주 합을 "연간"이라 표기). 수치 자체는 툴 값 그대로였다.
- 스트리밍 없음. 한 질문에 수 초~십여 초.
