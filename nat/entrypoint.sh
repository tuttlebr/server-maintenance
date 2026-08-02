#!/bin/bash
set -e

echo "=== DGX Help Chat Agent ==="
echo "Ingesting documentation into Milvus..."
python ingest.py

echo "Starting NeMo Agent Toolkit server..."
exec nat serve --config_file=config.yml --host 0.0.0.0 --port 8000
