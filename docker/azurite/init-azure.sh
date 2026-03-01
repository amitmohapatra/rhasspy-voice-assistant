#!/bin/bash
# =============================================================================
# Azurite Initialization Script for Rhasspy Voice Assistant
# =============================================================================
# Creates Azure Blob Storage containers locally for development.
# In production, use real Azure Blob Storage.
# =============================================================================

set -e

echo "=============================================="
echo "Initializing Azurite Azure Storage resources..."
echo "=============================================="

# Wait for Azurite to be ready
echo "Waiting for Azurite to be ready..."
for i in $(seq 1 30); do
    if nc -z localhost 10000 2>/dev/null; then
        echo "Azurite is ready!"
        break
    fi
    echo "  Attempt $i/30..."
    sleep 1
done

# Azurite well-known connection string
CONN_STR="DefaultEndpointsProtocol=http;AccountName=devstoreaccount1;AccountKey=Eby8vdM02xNOcqFlqUwJPLlmEtlCDXJ1OUzFT50uSRZ6IFsuFq2UVErCz4I6tq/K1SZFPTOtr/KBHBeksoGMGw==;BlobEndpoint=http://localhost:10000/devstoreaccount1"

# Create containers using the Azure CLI or curl
# Using curl directly against the Azurite REST API
ACCOUNT="devstoreaccount1"
BLOB_ENDPOINT="http://localhost:10000"

echo "Creating blob containers..."

# Create rhasspy-documents container
curl -sf -X PUT "${BLOB_ENDPOINT}/${ACCOUNT}/rhasspy-documents?restype=container" \
    -H "x-ms-version: 2020-10-02" \
    -H "x-ms-date: $(date -u '+%a, %d %b %Y %H:%M:%S GMT')" \
    || echo "Container rhasspy-documents may already exist"

# Create rhasspy-audio container
curl -sf -X PUT "${BLOB_ENDPOINT}/${ACCOUNT}/rhasspy-audio?restype=container" \
    -H "x-ms-version: 2020-10-02" \
    -H "x-ms-date: $(date -u '+%a, %d %b %Y %H:%M:%S GMT')" \
    || echo "Container rhasspy-audio may already exist"

# Create rhasspy-assets container
curl -sf -X PUT "${BLOB_ENDPOINT}/${ACCOUNT}/rhasspy-assets?restype=container" \
    -H "x-ms-version: 2020-10-02" \
    -H "x-ms-date: $(date -u '+%a, %d %b %Y %H:%M:%S GMT')" \
    || echo "Container rhasspy-assets may already exist"

echo ""
echo "=============================================="
echo "Azurite initialization complete!"
echo "=============================================="
echo ""
echo "To use Azure Blob storage locally, set in .env:"
echo "  STORAGE_TYPE=azure_blob"
echo "  AZURE_STORAGE_CONTAINER=rhasspy-documents"
echo '  AZURE_STORAGE_CONNECTION_STRING="DefaultEndpointsProtocol=http;AccountName=devstoreaccount1;AccountKey=Eby8vdM02xNOcqFlqUwJPLlmEtlCDXJ1OUzFT50uSRZ6IFsuFq2UVErCz4I6tq/K1SZFPTOtr/KBHBeksoGMGw==;BlobEndpoint=http://azurite:10000/devstoreaccount1"'
echo "=============================================="
