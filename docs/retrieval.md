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

## 다음

- 수집 자동화(크롤러)는 연기. 현 파이프라인은 수동 CSV + Google Trends fetch 커버.
- RAG → 외부변수 자동 주입은 트렌드 스키마 확정 후 연결.
