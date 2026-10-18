"""Validate provider vectors before associating them with documents or writing indexes."""

import math


def validate_embeddings(payload, expected_count, expected_dimension=None):
    rows = payload.get("data") if isinstance(payload, dict) else None
    if not isinstance(rows, list) or len(rows) != expected_count:
        raise ValueError("Embedding response count does not match the input batch")
    if any(not isinstance(row, dict) or type(row.get("index")) is not int for row in rows):
        raise ValueError("Embedding response has invalid indexes")
    rows = sorted(rows, key=lambda row: row["index"])
    if [row["index"] for row in rows] != list(range(expected_count)):
        raise ValueError("Embedding response indexes must cover each input exactly once")
    vectors = []
    for row in rows:
        vector = row.get("embedding")
        if not isinstance(vector, list) or not vector:
            raise ValueError("Embedding vectors must be nonempty arrays")
        if expected_dimension is None:
            expected_dimension = len(vector)
        if len(vector) != expected_dimension:
            raise ValueError("Embedding vector dimension does not match the configured or observed dimension")
        if any(type(value) not in (int, float) or not math.isfinite(value) for value in vector):
            raise ValueError("Embedding vectors must contain finite numbers")
        vectors.append(vector)
    return vectors
