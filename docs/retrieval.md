# Retrieval + Workflows (6~7주차)

## Vector DB

- `retrieval/store.py`: Chroma 영속 스토어. 기본 임베딩은 로컬
  sentence-transformers(all-MiniLM-L6-v2). API 키 불필요.
- 문서 스키마: source_url, published_at, collected_at, category, score + text(선택).
- 누설 차단: `search(..., available_before)`는 collected_ymd 이하만 반환.
  과거 시점 평가는 반드시 cutoff 지정.
- 저장 경로 기본 `artifacts/chroma`(Git 제외). OneDrive 잠금 발생 시
  로컬 temp 경로를 `--store`로 지정.

```
python -m trend_mmm retrieve-index data/sample/trends.csv --store <dir>
python -m trend_mmm retrieve-search 'shopping sale' --store <dir> --available-before 2014-08-06
```

## LangGraph 워크플로우

- `workflows/graph.py`: collect → clean → aggregate → save. 결정적 노드(LLM 없음).
  빈 입력은 abort. 실패 처리는 그래프가 담당.
- kind 2종: `docs-csv`(수동 수집), `google-fetch`(주간 검색지수 문서화).

```
python -m trend_mmm workflow-trends data/sample/trends.csv --out artifacts/trend_weekly.csv
```

## 파이프라인 → 외부변수 주입 (2026-10-12)

LangGraph 파이프라인 출력을 모델의 트렌드 변수로 바로 넣을 수 있다.

```
python -m trend_mmm workflow-trends x --kind google-fetch --out artifacts/trend_weekly.csv
python -m trend_mmm bayes data/raw/data_GIT.csv --trend artifacts/trend_weekly.csv ...
```

- 연결 지점은 `trends/google.py: trend_zscores`. CSV 헤더에 `mean_score`가 있으면 파이프라인 출력으로 보고
  그 열을 쓰고, 없으면 기존처럼 키워드 4열의 z-score 평균을 쓴다. 이후 처리(train 통계로 표준화, 보조 1열 추가)는 동일.
  `scenarios`, `optimize-draws`의 `--trend`에도 같은 파일을 쓴다.
- 누설 방지: 표준화의 평균·표준편차는 train 구간에서만 계산한다. 문서 검색 쪽 누설 차단(`available_before`)과 별개.
- google-fetch 경로는 이번에 처음 끝까지 돌았다. 문서 날짜를 문자열로 넘겨 aggregate 단계에서 죽는 버그가 있어 수정
  (`workflows/graph.py`), 테스트 추가(`tests/test_retrieval_workflow.py`).

확인한 것(실제 Google Trends fetch):

- 209주 전부 생성, `data_GIT.csv` 주와 정렬(train 183 / test 26).
- 파이프라인 변수와 기존 합성지수의 train 상관 0.952. 매출과의 train 상관은 0.591(기존 합성지수 0.683).
  파이프라인 변수는 키워드 원지수의 단순 평균이라 z-score 평균인 기존 지수와 조금 다르다.
- `bayes --trend <파이프라인 CSV>`가 `trend_demand` 보조열로 받아 샘플링까지 통과(draws 40의 배선 확인용 실행).

하지 않은 것:

- 이 변수로 확정런을 돌리지 않았다. 보고 수치는 전부 기존 합성지수(`trends_google.csv`) 기준이다.
- 수동 수집 문서(docs-csv)는 샘플 몇 주뿐이라 209주를 덮지 못해 변수로 쓸 수 없다. 주가 비면 KeyError로 멈춘다.
- 검색(RAG) 결과 자체를 점수화해 변수로 만드는 단계는 없다. 문서 라벨·점수 정의(승아 확인 사항)가 정해져야 한다.
  현재 검색은 챗봇의 `search_trend_docs` 툴로만 쓰인다(`docs/chatbot.md`).

## 다음

- 수집 자동화(크롤러)는 연기. 현 파이프라인은 수동 CSV + Google Trends fetch 커버.
- 문서 기반 변수는 라벨·점수 정의 확정과 209주 분량 문서 확보가 선행 조건.
