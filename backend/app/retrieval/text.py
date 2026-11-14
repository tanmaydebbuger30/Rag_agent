"""Tokenization shared by every lexical index.

CFR citations such as "164.312(a)(2)(iv)" are kept as single tokens (and also
emitted as their parts), because exact identifiers are where keyword search
beats embeddings.
"""
import re

CITATION_RE = re.compile(r"164\.\d{3}(?:\s*\([A-Za-z0-9]+\))*")
WORD_RE = re.compile(r"[a-z0-9]+")

STOPWORDS = frozenset("""
a an and are as at be been but by can could do does for from had has have how i if in into is it its
may must not of on or our should so such than that the their them then there these they this those
to under was we were what when where which while who will with would you your
""".split())


def normalize_citation(text: str) -> str:
    return re.sub(r"\s+", "", text)


def find_citations(text: str) -> list[str]:
    return [normalize_citation(m.group(0)) for m in CITATION_RE.finditer(text)]


def stem(word: str) -> str:
    for suffix, min_len in (("ing", 6), ("ed", 5), ("es", 5), ("s", 4)):
        if word.endswith(suffix) and len(word) >= min_len and not word.endswith("ss"):
            return word[: -len(suffix)]
    return word


def tokenize(text: str) -> list[str]:
    tokens = [c.lower() for c in find_citations(text)]
    for word in WORD_RE.findall(text.lower()):
        if word not in STOPWORDS:
            tokens.append(stem(word))
    return tokens
