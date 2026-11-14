"""Okapi BM25 over a small in-memory corpus.

score(q, d) = sum over query terms t of
    idf(t) * tf(t, d) * (k1 + 1) / (tf(t, d) + k1 * (1 - b + b * |d| / avgdl))
idf(t) = ln(1 + (N - df(t) + 0.5) / (df(t) + 0.5))
"""
import math
from collections import Counter

from backend.app.retrieval.text import tokenize


class BM25Index:
    def __init__(self, texts: list[str], k1: float = 1.5, b: float = 0.75):
        self.k1, self.b = k1, b
        self.docs = [Counter(tokenize(t)) for t in texts]
        self.lengths = [sum(d.values()) for d in self.docs]
        self.avgdl = (sum(self.lengths) / len(self.lengths)) if self.docs else 0.0
        df = Counter(term for d in self.docs for term in d)
        n = len(self.docs)
        self.idf = {t: math.log(1 + (n - f + 0.5) / (f + 0.5)) for t, f in df.items()}

    def scores(self, query: str) -> list[float]:
        terms = tokenize(query)
        out = []
        for doc, length in zip(self.docs, self.lengths):
            s = 0.0
            for t in terms:
                tf = doc.get(t)
                if not tf:
                    continue
                norm = self.k1 * (1 - self.b + self.b * length / self.avgdl)
                s += self.idf[t] * tf * (self.k1 + 1) / (tf + norm)
            out.append(s)
        return out

    def search(self, query: str, k: int, allowed: set[int] | None = None) -> list[tuple[int, float]]:
        ranked = [(i, s) for i, s in enumerate(self.scores(query)) if s > 0 and (allowed is None or i in allowed)]
        ranked.sort(key=lambda x: x[1], reverse=True)
        return ranked[:k]
