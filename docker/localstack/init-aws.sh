#!/bin/bash
# =============================================================================
# LocalStack Initialization Script for Rhasspy Voice Assistant
# =============================================================================
# Creates AWS resources locally for development. In production, use real AWS.
# =============================================================================

set -e

echo "=============================================="
echo "Initializing LocalStack AWS resources..."
echo "=============================================="

# =============================================================================
# S3 Buckets
# =============================================================================
echo "Creating S3 buckets..."

# Main document storage bucket (RAG documents)
awslocal s3 mb s3://rhasspy-documents || true
awslocal s3api put-bucket-cors --bucket rhasspy-documents --cors-configuration '{
    "CORSRules": [{
        "AllowedHeaders": ["*"],
        "AllowedMethods": ["GET", "PUT", "POST", "DELETE"],
        "AllowedOrigins": ["http://localhost:3000", "http://localhost:8000"],
        "ExposeHeaders": ["ETag"]
    }]
}' || true

# Audio files bucket (TTS/STT)
awslocal s3 mb s3://rhasspy-audio || true

# Static assets bucket (avatars, 3D models)
awslocal s3 mb s3://rhasspy-assets || true

echo "S3 buckets created:"
awslocal s3 ls

# =============================================================================
# Secrets Manager
# =============================================================================
echo "Creating Secrets Manager secrets..."

awslocal secretsmanager create-secret \
    --name "rhasspy/api-keys" \
    --description "API keys for LLM providers" \
    --secret-string '{"openai":"","anthropic":"","google":""}' || true

echo "Secrets created:"
awslocal secretsmanager list-secrets --query 'SecretList[].Name'

# =============================================================================
# Summary
# =============================================================================
echo ""
echo "=============================================="
echo "LocalStack initialization complete!"
echo "=============================================="
echo ""
echo "To use S3 storage locally, set in .env:"
echo "  STORAGE_TYPE=s3"
echo "  S3_BUCKET=rhasspy-documents"
echo "  S3_ENDPOINT_URL=http://localstack:4566"
echo "  S3_USE_SSL=false"
echo "  AWS_ACCESS_KEY_ID=test"
echo "  AWS_SECRET_ACCESS_KEY=test"
echo "=============================================="
