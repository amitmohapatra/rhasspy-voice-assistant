#!/bin/bash
# =============================================================================
# fake-gcs-server Initialization Script for Rhasspy Voice Assistant
# =============================================================================
# Creates GCS buckets locally for development.
# In production, use real Google Cloud Storage.
# =============================================================================

set -e

echo "=============================================="
echo "Initializing fake-gcs-server GCP Storage..."
echo "=============================================="

GCS_ENDPOINT="http://localhost:4443"

# Wait for fake-gcs-server to be ready
echo "Waiting for fake-gcs-server to be ready..."
for i in $(seq 1 30); do
    if wget -q --spider "${GCS_ENDPOINT}/storage/v1/b" 2>/dev/null; then
        echo "fake-gcs-server is ready!"
        break
    fi
    echo "  Attempt $i/30..."
    sleep 1
done

echo "Creating GCS buckets..."

# Create rhasspy-documents bucket
curl -sf -X POST "${GCS_ENDPOINT}/storage/v1/b?project=test-project" \
    -H "Content-Type: application/json" \
    -d '{"name": "rhasspy-documents"}' \
    || echo "Bucket rhasspy-documents may already exist"

# Create rhasspy-audio bucket
curl -sf -X POST "${GCS_ENDPOINT}/storage/v1/b?project=test-project" \
    -H "Content-Type: application/json" \
    -d '{"name": "rhasspy-audio"}' \
    || echo "Bucket rhasspy-audio may already exist"

# Create rhasspy-assets bucket
curl -sf -X POST "${GCS_ENDPOINT}/storage/v1/b?project=test-project" \
    -H "Content-Type: application/json" \
    -d '{"name": "rhasspy-assets"}' \
    || echo "Bucket rhasspy-assets may already exist"

echo ""
echo "=============================================="
echo "fake-gcs-server initialization complete!"
echo "=============================================="
echo ""
echo "To use GCS storage locally, set in .env:"
echo "  STORAGE_TYPE=gcs"
echo "  GCP_STORAGE_BUCKET=rhasspy-documents"
echo "  GCP_PROJECT_ID=test-project"
echo "  GCP_STORAGE_ENDPOINT_URL=http://gcp-storage:4443"
echo "=============================================="
