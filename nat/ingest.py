"""Ingest DGX documentation into Milvus for RAG retrieval.

Reads local markdown files from /app/docs/, splits them into sections,
embeds via NVIDIA API, and stores in Milvus.
Idempotent — skips if the collection already has data.
"""

import json
import os
import re
import time
import urllib.request

from pymilvus import (
    Collection,
    CollectionSchema,
    DataType,
    FieldSchema,
    connections,
    utility,
)
from pymilvus.exceptions import MilvusException

DOCS_DIR = "/app/docs"
COLLECTION_NAME = "fleet_docs"
JOB_LOG_COLLECTION_NAME = "fleet_job_logs"
MILVUS_URI = os.environ.get("MILVUS_URI", "http://milvus:19530")
EMBED_MODEL = os.environ.get("EMBED_MODEL", "nvidia/qwen/qwen3-embedding-0.6b")
EMBED_DIM = int(os.environ["EMBED_DIM"]) if os.environ.get("EMBED_DIM") else None
API_KEY = os.environ.get("EMBED_API_KEY") or os.environ.get("AI_HELPER_API_KEY", "")
API_BASE_URL = (
    os.environ.get("EMBED_BASE_URL")
    or os.environ.get("AI_HELPER_BASE_URL")
    or "https://inference-api.nvidia.com/v1"
)


def wait_for_milvus(uri, retries=30, delay=5):
    """Wait for Milvus to be ready."""
    host = uri.replace("http://", "").split(":")[0]
    port = uri.replace("http://", "").split(":")[-1]
    for i in range(retries):
        try:
            connections.connect("default", host=host, port=port)
            print(f"Connected to Milvus at {uri}")
            return True
        except MilvusException as e:
            print(f"Waiting for Milvus ({i + 1}/{retries}): {e}")
            time.sleep(delay)
    raise RuntimeError(f"Could not connect to Milvus at {uri}")


MAX_CHUNK_CHARS = 4000  # Keep chunks small for better retrieval quality
EMBED_BATCH_SIZE = 16


def _split_large_text(text, heading, max_chars=MAX_CHUNK_CHARS):
    """Split text that exceeds max_chars into smaller chunks at paragraph boundaries."""
    if len(text) <= max_chars:
        return [(heading, text)]

    chunks = []
    paragraphs = text.split("\n\n")
    current = ""
    part_num = 1

    for para in paragraphs:
        if current and len(current) + len(para) + 2 > max_chars:
            chunks.append((f"{heading} (part {part_num})", current.strip()))
            part_num += 1
            current = para
        else:
            current = current + "\n\n" + para if current else para

    if current.strip():
        label = f"{heading} (part {part_num})" if part_num > 1 else heading
        chunks.append((label, current.strip()))

    return chunks


def load_and_split_docs(docs_dir):
    """Load markdown files and split into sections by ## headings, then chunk large sections."""
    sections = []
    for filename in sorted(os.listdir(docs_dir)):
        if not filename.endswith(".md"):
            continue
        filepath = os.path.join(docs_dir, filename)

        with open(filepath, "r", encoding="utf-8") as f:
            text = f.read()
        source = (
            _doc_title(text) or filename.replace("-", " ").replace(".md", "").title()
        )
        reference = f"docs/{filename}"

        parts = re.split(r"(?=^## )", text, flags=re.MULTILINE)
        for part in parts:
            part = part.strip()
            if not part or len(part) < 50:
                continue
            lines = part.split("\n", 1)
            heading = (
                lines[0].lstrip("#").strip()
                if lines[0].startswith("#")
                else "Introduction"
            )

            for chunk_heading, chunk_text in _split_large_text(part, heading):
                sections.append(
                    {
                        "source": source,
                        "heading": chunk_heading,
                        "text": f"Source: {source}\nLocal document: {reference}\n\n{chunk_text}",
                    }
                )

    print(f"Loaded {len(sections)} chunks from {docs_dir}")
    return sections


def _doc_title(text):
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("#"):
            return line.lstrip("#").strip() or None
    return None


def _call_embeddings_api(texts, input_type="passage"):
    """Call NVIDIA embeddings API (OpenAI-compatible format)."""
    url = API_BASE_URL.rstrip("/") + "/embeddings"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {API_KEY}",
    }
    body = {
        "model": EMBED_MODEL,
        "input": texts,
        "encoding_format": "float",
        "input_type": input_type,
    }
    payload = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(url, data=payload, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            result = json.loads(resp.read())
    except urllib.error.HTTPError as e:
        error_body = e.read().decode("utf-8", errors="replace")
        print(f"Embeddings API error {e.code}: {error_body}")
        raise
    # Sort by index to preserve order
    data = sorted(result["data"], key=lambda x: x["index"])
    return [item["embedding"] for item in data]


def detect_embed_dim():
    """Embed a test string to auto-detect the embedding dimension."""
    print(f"Detecting embedding dimension for model: {EMBED_MODEL}")
    vectors = _call_embeddings_api(["test"])
    dim = len(vectors[0])
    print(f"Detected embedding dimension: {dim}")
    return dim


def embed_texts(texts):
    """Embed texts using the NVIDIA API in batches."""
    all_embeddings = []
    total = len(texts)
    for i in range(0, total, EMBED_BATCH_SIZE):
        batch = texts[i : i + EMBED_BATCH_SIZE]
        print(
            f"Embedding batch {i // EMBED_BATCH_SIZE + 1}/{(total + EMBED_BATCH_SIZE - 1) // EMBED_BATCH_SIZE}"
        )
        embeddings = _call_embeddings_api(batch)
        all_embeddings.extend(embeddings)
    return all_embeddings


def create_collection(embed_dim):
    """Create Milvus collection for doc sections."""
    fields = [
        FieldSchema(name="id", dtype=DataType.INT64, is_primary=True, auto_id=True),
        FieldSchema(name="source", dtype=DataType.VARCHAR, max_length=256),
        FieldSchema(name="heading", dtype=DataType.VARCHAR, max_length=512),
        FieldSchema(name="text", dtype=DataType.VARCHAR, max_length=16384),
        FieldSchema(name="vector", dtype=DataType.FLOAT_VECTOR, dim=embed_dim),
    ]
    schema = CollectionSchema(fields, description="DGX documentation sections")
    collection = Collection(COLLECTION_NAME, schema)
    collection.create_index(
        field_name="vector",
        index_params={
            "index_type": "IVF_FLAT",
            "metric_type": "L2",
            "params": {"nlist": 64},
        },
    )
    print(f"Created collection '{COLLECTION_NAME}' (dim={embed_dim})")
    return collection


def _collection_embed_dim(collection_name):
    """Read the vector dimension from an existing collection, if available."""
    if not utility.has_collection(collection_name):
        return None
    collection = Collection(collection_name)
    vector_field = next(
        (field for field in collection.schema.fields if field.name == "vector"), None
    )
    if not vector_field:
        return None
    return int(vector_field.params["dim"])


def ensure_job_log_collection(embed_dim):
    """Create the empty collection required by the NAT job-log retriever."""
    if utility.has_collection(JOB_LOG_COLLECTION_NAME):
        existing_dim = _collection_embed_dim(JOB_LOG_COLLECTION_NAME)
        if existing_dim == embed_dim:
            print(f"Collection '{JOB_LOG_COLLECTION_NAME}' is ready (dim={embed_dim})")
            collection = Collection(JOB_LOG_COLLECTION_NAME)
            collection.load()
            return collection
        print(
            f"Recreating '{JOB_LOG_COLLECTION_NAME}' because embedding dimension "
            f"changed from {existing_dim} to {embed_dim}"
        )
        utility.drop_collection(JOB_LOG_COLLECTION_NAME)

    fields = [
        FieldSchema(name="id", dtype=DataType.VARCHAR, max_length=128, is_primary=True),
        FieldSchema(name="source", dtype=DataType.VARCHAR, max_length=256),
        FieldSchema(name="heading", dtype=DataType.VARCHAR, max_length=512),
        FieldSchema(name="text", dtype=DataType.VARCHAR, max_length=16384),
        FieldSchema(name="job_id", dtype=DataType.VARCHAR, max_length=64),
        FieldSchema(name="status", dtype=DataType.VARCHAR, max_length=32),
        FieldSchema(name="finished_at", dtype=DataType.VARCHAR, max_length=64),
        FieldSchema(name="vector", dtype=DataType.FLOAT_VECTOR, dim=embed_dim),
    ]
    schema = CollectionSchema(
        fields, description="Redacted Fleet Manager completed operation logs"
    )
    collection = Collection(JOB_LOG_COLLECTION_NAME, schema)
    collection.create_index(
        field_name="vector",
        index_params={
            "index_type": "IVF_FLAT",
            "metric_type": "L2",
            "params": {"nlist": 64},
        },
    )
    collection.load()
    print(f"Created collection '{JOB_LOG_COLLECTION_NAME}' (dim={embed_dim})")
    return collection


def main():
    wait_for_milvus(MILVUS_URI)

    embed_dim = (
        EMBED_DIM
        or _collection_embed_dim(COLLECTION_NAME)
        or _collection_embed_dim(JOB_LOG_COLLECTION_NAME)
    )
    if not embed_dim:
        if not API_KEY:
            print("WARNING: embedding API is not configured, skipping ingestion")
            return
        embed_dim = detect_embed_dim()

    # The retriever validates its collection when NAT starts, even before the
    # first fleet job has completed.
    ensure_job_log_collection(embed_dim)

    if not os.path.exists(DOCS_DIR):
        print(
            f"WARNING: Docs directory {DOCS_DIR} not found, skipping documentation ingestion"
        )
        return

    if not API_KEY:
        print(
            "WARNING: embedding API is not configured, skipping documentation ingestion"
        )
        return

    # Check if collection already has data
    if utility.has_collection(COLLECTION_NAME):
        collection = Collection(COLLECTION_NAME)
        collection.load()
        count = collection.num_entities
        if count > 0:
            print(
                f"Collection '{COLLECTION_NAME}' already has {count} entities, skipping ingestion"
            )
            return
        else:
            utility.drop_collection(COLLECTION_NAME)

    sections = load_and_split_docs(DOCS_DIR)
    if not sections:
        print("No sections found, nothing to ingest")
        return

    print("Embedding sections...")
    texts = [s["text"] for s in sections]
    embeddings = embed_texts(texts)

    collection = create_collection(embed_dim)

    # Insert data
    data = [
        [s["source"] for s in sections],
        [s["heading"] for s in sections],
        [s["text"] for s in sections],
        embeddings,
    ]
    collection.insert(data)
    collection.flush()
    collection.load()

    print(
        f"Ingested {len(sections)} sections into Milvus collection '{COLLECTION_NAME}'"
    )


if __name__ == "__main__":
    main()
