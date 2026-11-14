"""Optional dense retrieval: an Embedder interface plus exact cosine search.

At this corpus size (tens to hundreds of chunks) exact search over a numpy
matrix is fast enough; an ANN index (HNSW, e.g. Qdrant) matters only at much
larger scale. Dense retrieval is off unless CG_DENSE=1, because the embedding
model must be downloaded once (fastembed pulls it from Hugging Face).
"""
from typing import Protocol

import numpy as np


class Embedder(Protocol):
    model_name: str

    def embed_documents(self, texts: list[str]) -> np.ndarray: ...

    def embed_query(self, text: str) -> np.ndarray: ...


class FastEmbedEmbedder:
    def __init__(self, model_name: str):
        from fastembed import TextEmbedding   # imported lazily: optional dependency

        self.model_name = model_name
        self._model = TextEmbedding(model_name=model_name)

    def embed_documents(self, texts):
        return np.array(list(self._model.passage_embed(texts)), dtype=np.float32)

    def embed_query(self, text):
        return np.array(next(iter(self._model.query_embed([text]))), dtype=np.float32)


def _normalize(m: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(m, axis=-1, keepdims=True)
    return m / np.where(norms == 0, 1, norms)


class DenseIndex:
    def __init__(self, embedder: Embedder, texts: list[str]):
        self.embedder = embedder
        self.matrix = _normalize(embedder.embed_documents(texts)) if texts else np.zeros((0, 1))

    def search(self, query: str, k: int, allowed: set[int] | None = None) -> list[tuple[int, float]]:
        if not len(self.matrix):
            return []
        sims = self.matrix @ _normalize(self.embedder.embed_query(query))
        order = np.argsort(-sims)
        out = [(int(i), float(sims[i])) for i in order if allowed is None or int(i) in allowed]
        return out[:k]
