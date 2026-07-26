"""
rag/build_index.py

Chunks the real downloaded docs and builds a local FAISS index using
sentence-transformers (all-MiniLM-L6-v2 — small, fast, free, runs on CPU,
no API calls / no cost).

Run once after rag/ingest.py: python rag/build_index.py
"""

import os
import glob
import pickle
import numpy as np
import faiss
from sentence_transformers import SentenceTransformer

DOCS_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "docs")
INDEX_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "index")
MODEL_NAME = "all-MiniLM-L6-v2"
CHUNK_SIZE = 800      # characters
CHUNK_OVERLAP = 150


def chunk_text(text: str, source: str) -> list[dict]:
    chunks = []
    start = 0
    while start < len(text):
        end = start + CHUNK_SIZE
        chunk = text[start:end]
        if chunk.strip():
            chunks.append({"text": chunk, "source": source})
        start += CHUNK_SIZE - CHUNK_OVERLAP
    return chunks


def build():
    print(f"Loading embedding model ({MODEL_NAME})...")
    model = SentenceTransformer(MODEL_NAME)

    all_chunks = []
    for filepath in glob.glob(os.path.join(DOCS_DIR, "**", "*.md"), recursive=True):
        rel_source = os.path.relpath(filepath, DOCS_DIR)
        with open(filepath, "r", encoding="utf-8") as f:
            text = f.read()
        all_chunks.extend(chunk_text(text, rel_source))

    print(f"Built {len(all_chunks)} chunks from {len(glob.glob(os.path.join(DOCS_DIR, '**', '*.md'), recursive=True))} docs")

    print("Embedding chunks (local, free, no API calls)...")
    texts = [c["text"] for c in all_chunks]
    embeddings = model.encode(texts, show_progress_bar=True, convert_to_numpy=True)

    dim = embeddings.shape[1]
    index = faiss.IndexFlatL2(dim)
    index.add(embeddings.astype(np.float32))

    os.makedirs(INDEX_DIR, exist_ok=True)
    faiss.write_index(index, os.path.join(INDEX_DIR, "docs.faiss"))
    with open(os.path.join(INDEX_DIR, "chunks.pkl"), "wb") as f:
        pickle.dump(all_chunks, f)

    print(f"\nIndex built: {len(all_chunks)} vectors, dim={dim}")
    print(f"Saved to {INDEX_DIR}/docs.faiss + chunks.pkl")


if __name__ == "__main__":
    build()