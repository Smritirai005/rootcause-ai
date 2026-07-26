"""
rag/search.py

Queries the local FAISS index built by rag/build_index.py.
Same embedding model must be used for query-time encoding as index-time.
"""

import os
import pickle
import faiss
import numpy as np
from sentence_transformers import SentenceTransformer

INDEX_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "index")
MODEL_NAME = "all-MiniLM-L6-v2"

_model = None
_index = None
_chunks = None


def _load():
    global _model, _index, _chunks
    if _model is None:
        _model = SentenceTransformer(MODEL_NAME)
    if _index is None:
        _index = faiss.read_index(os.path.join(INDEX_DIR, "docs.faiss"))
        with open(os.path.join(INDEX_DIR, "chunks.pkl"), "rb") as f:
            _chunks = pickle.load(f)


def search_docs(query: str, top_k: int = 3) -> list[dict]:
    """
    MCP-exposed tool: semantic search over real FastAPI + Docker docs.

    Args:
        query: natural language query, e.g. "database connection refused"
        top_k: number of chunks to return
    """
    _load()
    query_vec = _model.encode([query], convert_to_numpy=True).astype(np.float32)
    distances, indices = _index.search(query_vec, top_k)

    results = []
    for dist, idx in zip(distances[0], indices[0]):
        if idx == -1:
            continue
        chunk = _chunks[idx]
        results.append({
            "source": chunk["source"],
            "text": chunk["text"].strip(),
            "relevance_score": round(float(1 / (1 + dist)), 3),
        })
    return results


if __name__ == "__main__":
    # smoke test — run after build_index.py has been run
    for q in ["database connection refused", "container out of memory"]:
        print(f"\nQuery: {q}")
        for r in search_docs(q, top_k=2):
            print(f"  [{r['source']}] score={r['relevance_score']}")
            print(f"  {r['text'][:150]}...")