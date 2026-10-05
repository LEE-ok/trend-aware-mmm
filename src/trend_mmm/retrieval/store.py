"""Chroma-backed trend document store with pluggable embeddings.

Leakage rule (docs/architecture.md): searches take ``available_before``
and only return documents collected on or before that date.

Production embeddings default to sentence-transformers all-MiniLM-L6-v2
(local, no API key). Tests inject ``fake_embed``. chromadb /
sentence-transformers are imported lazily so the package imports
without them; callers get a clear error telling what to install.
"""
import hashlib

EMBED_MODEL = "all-MiniLM-L6-v2"


def fake_embed(texts: list[str], dim: int = 16) -> list[list[float]]:
    """Deterministic test embeddings. Not for production use."""
    vectors = []
    for text in texts:
        digest = hashlib.sha256(text.encode("utf-8")).digest()
        vectors.append([(digest[i % len(digest)] / 255.0) for i in range(dim)])
    return vectors


def default_embed(texts: list[str]) -> list[list[float]]:
    """Local sentence-transformer embeddings. Downloads model on first use."""
    try:
        from sentence_transformers import SentenceTransformer
    except ImportError as exc:
        raise ImportError("Install sentence-transformers for default embeddings.") from exc
    global _MODEL
    if _MODEL is None:
        _MODEL = SentenceTransformer(EMBED_MODEL)
    return _MODEL.encode(list(texts), normalize_embeddings=True).tolist()


_MODEL = None


def doc_text(doc: dict) -> str:
    """Index text: category plus human text (falls back to URL)."""
    body = (doc.get("text") or "").strip() or doc.get("source_url", "")
    return f"{doc.get('category', '')}: {body}"


def _ymd(value) -> int:
    """YYYY-MM-DD (or date) -> int YYYYMMDD for range filtering."""
    text = value.isoformat() if hasattr(value, "isoformat") else str(value)
    return int(text[:10].replace("-", ""))


def _metadata(doc: dict) -> dict:
    collected = str(doc.get("collected_at", ""))
    if hasattr(doc.get("collected_at"), "isoformat"):
        collected = doc["collected_at"].isoformat()
    published = str(doc.get("published_at", ""))
    if hasattr(doc.get("published_at"), "isoformat"):
        published = doc["published_at"].isoformat()
    return {
        "source_url": str(doc.get("source_url", "")),
        "published_at": published,
        "collected_at": collected,
        "collected_ymd": _ymd(collected),
        "category": str(doc.get("category", "")),
        "score": float(doc.get("score", 0.0)),
    }


class TrendStore:
    """Thin wrapper over a persistent Chroma collection."""

    def __init__(self, persist_dir=None, collection: str = "trends", embed_fn=None):
        try:
            import chromadb
        except ImportError as exc:
            raise ImportError("Install chromadb for the trend store.") from exc
        if persist_dir is None:
            self._client = chromadb.EphemeralClient()
        else:
            self._client = chromadb.PersistentClient(path=str(persist_dir))
        self._collection = self._client.get_or_create_collection(name=collection)
        self._embed = embed_fn or default_embed

    def add(self, docs: list[dict]) -> int:
        """Store docs. Each needs source_url, published_at, collected_at, category."""
        if not docs:
            return 0
        texts = [doc_text(d) for d in docs]
        vectors = self._embed(texts)
        self._collection.add(
            ids=[f"doc-{abs(hash((d.get('source_url'), d.get('published_at'))))}" for d in docs],
            documents=texts,
            embeddings=vectors,
            metadatas=[_metadata(d) for d in docs],
        )
        return len(docs)

    def search(
        self,
        query: str,
        available_before=None,
        category: str | None = None,
        n: int = 5,
    ) -> list[dict]:
        """Semantic search with a collection-date cutoff and optional category."""
        where: dict = {}
        if available_before is not None:
            cutoff = available_before
            cutoff = cutoff.isoformat() if hasattr(cutoff, "isoformat") else str(cutoff)
            where["collected_ymd"] = {"$lte": int(cutoff[:10].replace("-", ""))}
        if category is not None:
            where["category"] = {"$eq": category}
        result = self._collection.query(
            query_embeddings=self._embed([query]),
            n_results=n,
            where=where or None,
        )
        hits = []
        for i in range(len(result["ids"][0])):
            meta = result["metadatas"][0][i]
            hits.append(
                {
                    "source_url": meta["source_url"],
                    "published_at": meta["published_at"],
                    "collected_at": meta["collected_at"],
                    "category": meta["category"],
                    "score": meta["score"],
                    "distance": result["distances"][0][i],
                }
            )
        return hits

    def count(self) -> int:
        return self._collection.count()
