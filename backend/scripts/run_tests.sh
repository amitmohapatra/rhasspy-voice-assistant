#!/bin/bash
# Test runner script for Rhasspy Voice Assistant backend

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}  Rhasspy Voice Assistant Test Runner  ${NC}"
echo -e "${GREEN}========================================${NC}"

# Navigate to backend directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$(dirname "$SCRIPT_DIR")"
cd "$BACKEND_DIR"

# Function to check if service is running
check_service() {
    local host=$1
    local port=$2
    local service_name=$3

    if nc -z "$host" "$port" 2>/dev/null; then
        echo -e "${GREEN}$service_name is running on $host:$port${NC}"
        return 0
    else
        echo -e "${YELLOW}$service_name is not running on $host:$port${NC}"
        return 1
    fi
}

# Parse command line arguments
TEST_TYPE="${1:-all}"
VERBOSE="${2:-}"

echo ""
echo -e "${YELLOW}Test Type: $TEST_TYPE${NC}"
echo ""

case "$TEST_TYPE" in
    unit)
        echo -e "${GREEN}Running Unit Tests...${NC}"
        python -m pytest tests/unit -v --tb=short -m "unit" $VERBOSE
        ;;

    integration)
        echo -e "${GREEN}Running Integration Tests...${NC}"
        echo "Checking required services..."

        # Check if test services are running
        check_service localhost 5433 "PostgreSQL (test)"
        check_service localhost 6380 "Redis (test)"
        check_service localhost 4566 "LocalStack"
        check_service localhost 10000 "Azurite"
        check_service localhost 6334 "Qdrant"

        python -m pytest tests/integration -v --tb=short -m "integration" $VERBOSE
        ;;

    e2e)
        echo -e "${GREEN}Running E2E Tests...${NC}"
        echo "Checking if API server is running..."

        if check_service localhost 8000 "API Server"; then
            python -m pytest tests/e2e -v --tb=short -m "e2e" $VERBOSE
        else
            echo -e "${RED}API server is not running. Start it with: uvicorn src.main:app${NC}"
            exit 1
        fi
        ;;

    cloud)
        echo -e "${GREEN}Running Cloud Provider Tests...${NC}"
        echo "Checking cloud emulators..."

        check_service localhost 4566 "LocalStack (AWS)"
        check_service localhost 10000 "Azurite (Azure)"
        check_service localhost 4443 "GCP Storage Emulator"

        python -m pytest tests/integration/test_cloud_providers.py -v --tb=short $VERBOSE
        ;;

    vectordb)
        echo -e "${GREEN}Running Vector Database Tests...${NC}"
        echo "Checking vector databases..."

        check_service localhost 5433 "PostgreSQL (pgvector)"
        check_service localhost 6334 "Qdrant"
        check_service localhost 8081 "Weaviate"
        check_service localhost 8002 "ChromaDB"

        python -m pytest tests/integration/test_vector_databases.py -v --tb=short $VERBOSE
        ;;

    encryption)
        echo -e "${GREEN}Running Encryption Tests...${NC}"
        python -m pytest tests/unit/test_encryption.py -v --tb=short $VERBOSE
        ;;

    licensing)
        echo -e "${GREEN}Running Licensing Tests...${NC}"
        if check_service localhost 8000 "API Server"; then
            python -m pytest tests/e2e/test_licensing.py -v --tb=short $VERBOSE
        else
            echo -e "${RED}API server is not running${NC}"
            exit 1
        fi
        ;;

    onboarding)
        echo -e "${GREEN}Running Company Onboarding Tests...${NC}"
        if check_service localhost 8000 "API Server"; then
            python -m pytest tests/e2e/test_company_onboarding.py -v --tb=short $VERBOSE
        else
            echo -e "${RED}API server is not running${NC}"
            exit 1
        fi
        ;;

    all)
        echo -e "${GREEN}Running All Tests...${NC}"

        echo ""
        echo -e "${YELLOW}=== Unit Tests ===${NC}"
        python -m pytest tests/unit -v --tb=short -m "unit" $VERBOSE || true

        echo ""
        echo -e "${YELLOW}=== Integration Tests ===${NC}"
        python -m pytest tests/integration -v --tb=short -m "integration" $VERBOSE || true

        echo ""
        echo -e "${YELLOW}=== E2E Tests ===${NC}"
        if check_service localhost 8000 "API Server"; then
            python -m pytest tests/e2e -v --tb=short -m "e2e" $VERBOSE || true
        else
            echo -e "${YELLOW}Skipping E2E tests - API server not running${NC}"
        fi
        ;;

    coverage)
        echo -e "${GREEN}Running Tests with Coverage...${NC}"
        python -m pytest tests/ -v --cov=src --cov-report=html --cov-report=term-missing $VERBOSE
        echo ""
        echo -e "${GREEN}Coverage report generated in htmlcov/${NC}"
        ;;

    *)
        echo -e "${RED}Unknown test type: $TEST_TYPE${NC}"
        echo ""
        echo "Usage: $0 [test_type] [verbose]"
        echo ""
        echo "Test types:"
        echo "  unit        - Run unit tests only"
        echo "  integration - Run integration tests (requires test services)"
        echo "  e2e         - Run E2E tests (requires API server)"
        echo "  cloud       - Run cloud provider tests (requires emulators)"
        echo "  vectordb    - Run vector database tests"
        echo "  encryption  - Run encryption service tests"
        echo "  licensing   - Run licensing tests"
        echo "  onboarding  - Run company onboarding tests"
        echo "  all         - Run all tests"
        echo "  coverage    - Run tests with coverage report"
        echo ""
        echo "Options:"
        echo "  -vv         - Extra verbose output"
        echo ""
        exit 1
        ;;
esac

echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}  Tests Completed!                     ${NC}"
echo -e "${GREEN}========================================${NC}"
