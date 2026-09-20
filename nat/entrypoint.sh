#!/bin/bash
set -e

echo "=== Fleet Help Chat Agent ==="
echo "Ingesting documentation into Milvus..."
if python ingest.py; then
    echo "Milvus collections are ready."
else
    echo "WARNING: Initial ingestion failed; starting NAT with the existing Milvus collections."
    echo "WARNING: Check the embedding endpoint and run documentation reindexing after it recovers."
fi

echo "Starting NeMo Agent Toolkit server..."
python prepare_config.py
exec nat serve --config_file=/tmp/fleet-nat-config.yml --host 0.0.0.0 --port 8000
