"""Prepared exhaustive in-memory candidate retrieval for opt-in server use."""
from collections import Counter
from dataclasses import dataclass
from math import log, sqrt

import numpy as np

from candidates.story_lexical import grams


# CPython 3.12+ compensates built-in float sum; older runtimes may use
# ordinary addition. Detect the arithmetic used by the reference scorer.
_FLOAT_SUM_COMPENSATES = sum((1., 2.**-53, 2.**-53)) != 1.


class _InvertedLexical:
    """Same char-TFIDF weights as LexicalIndex, with contiguous postings."""

    def __init__(self, documents):
        df = Counter()
        for doc in documents:
            df.update(grams(doc.overview).keys())
        self.idf = {gram: log((1 + len(documents)) / (1 + count)) + 1
                    for gram, count in df.items()}
        self.slices = {}
        offset = 0
        for gram, count in df.items():
            self.slices[gram] = slice(offset, offset + count)
            offset += count
        self.rows = np.empty(offset, dtype=np.int32)
        self.weights = np.empty(offset, dtype=np.float64)
        cursors = {gram: span.start for gram, span in self.slices.items()}
        for row, doc in enumerate(documents):
            for gram, weight in self._normalized(doc.overview).items():
                position = cursors[gram]
                self.rows[position] = row
                self.weights[position] = weight
                cursors[gram] += 1
        self.count = len(documents)

    def _normalized(self, text):
        weights = {gram: (1 + log(count)) * self.idf[gram]
                   for gram, count in grams(text).items() if gram in self.idf}
        norm = sqrt(sum(value * value for value in weights.values())) or 1
        return {gram: value / norm for gram, value in weights.items()}

    def scores(self, query):
        scores = np.zeros(self.count, dtype=np.float64)
        # Query gram order matches LexicalIndex.scores, and each individual
        # posting contains each row at most once (no repeated fancy-index writes).
        residual = np.zeros_like(scores) if _FLOAT_SUM_COMPENSATES else None
        for gram, weight in self._normalized(query).items():
            span = self.slices[gram]
            rows = self.rows[span]
            product = weight * self.weights[span]
            if residual is None:
                scores[rows] += product
                continue
            # Neumaier compensation, as in CPython's built-in float sum.
            # Both operands are nonnegative, so magnitude is ordinary order.
            previous = scores[rows]
            updated = previous + product
            residual[rows] += (np.maximum(previous, product) - updated) + np.minimum(previous, product)
            scores[rows] = updated
        if residual is not None:
            scores += residual
        return scores


@dataclass(frozen=True)
class CandidateOrders:
    """Orders use document row indices; lexical ranks are -1 for zero/ineligible."""

    dense_top: tuple
    lexical_top: tuple
    dense_ranks: np.ndarray
    lexical_ranks: np.ndarray


class PreparedRetrievalIndex:
    """Exhaustive row-wise dense scores plus inverted character TF-IDF.

    Preparation does not encode text or touch data files. A contiguous float32
    input matrix can be reused rather than duplicated; caller must not mutate it.
    """

    def __init__(self, documents, vectors):
        documents = tuple(documents)
        keys = tuple(doc.key for doc in documents)
        if len(set(keys)) != len(keys):
            raise ValueError("retrieval keys must be unique")
        self.matrix = np.asarray(vectors, dtype=np.float32, order="C")
        if self.matrix.ndim != 2 or self.matrix.shape[0] != len(documents):
            raise ValueError("vector rows must match documents")
        self.key_rank = np.empty(len(keys), dtype=np.intp)
        for rank, row in enumerate(sorted(range(len(keys)), key=keys.__getitem__)):
            self.key_rank[row] = rank
        self.lexical = _InvertedLexical(documents)

    def orders(self, query, query_vector, *, eligible=None, top_k=40):
        if type(top_k) is not int or top_k < 0:
            raise ValueError("top_k must be a nonnegative integer")
        vector = np.asarray(query_vector, dtype=np.float32)
        if vector.shape != self.matrix.shape[1:]:
            raise ValueError("query dimension does not match the index")
        if eligible is None:
            rows = np.arange(len(self.matrix), dtype=np.intp)
        else:
            mask = np.asarray(eligible)
            if mask.dtype != np.bool_ or mask.shape != (len(self.matrix),):
                raise ValueError("eligibility must be a Boolean mask over the index")
            rows = np.flatnonzero(mask)

        # Keep the reference's scalar float32 dot product for all eligible
        # rows. A BLAS matvec can reduce in a different order and change
        # near-ties, including deep ranks used by lexical-only candidates.
        dense = np.fromiter((self.matrix[row] @ vector for row in rows),
                            dtype=np.float32, count=rows.size)
        lexical = self.lexical.scores(query)
        dense_rows = rows[np.lexsort((self.key_rank[rows], -dense))]
        positive = rows[lexical[rows] > 0]
        lexical_rows = positive[np.lexsort((self.key_rank[positive], -lexical[positive]))]
        # Preserve opposing-channel ranks beyond top K: RRF needs ranks for
        # candidates recalled by only the other channel.
        dense_ranks = np.full(len(self.matrix), -1, dtype=np.intp)
        lexical_ranks = np.full(len(self.matrix), -1, dtype=np.intp)
        dense_ranks[dense_rows] = np.arange(dense_rows.size)
        lexical_ranks[lexical_rows] = np.arange(lexical_rows.size)
        return CandidateOrders(tuple(map(int, dense_rows[:top_k])),
                               tuple(map(int, lexical_rows[:top_k])), dense_ranks, lexical_ranks)
