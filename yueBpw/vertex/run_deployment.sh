#!/bin/bash

# Master YuE Vertex AI Deployment Script
# This script runs the complete deployment sequence in the correct order

set -e

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${GREEN}=== YuE Vertex AI Master Deployment Script ===${NC}"
echo -e "${BLUE}This script will run the complete deployment sequence${NC}"
echo ""

# Function to check if command succeeded
check_status() {
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✅ $1 completed successfully${NC}"
    else
        echo -e "${RED}❌ $1 failed${NC}"
        exit 1
    fi
}

# Prompt user for confirmation
echo -e "${YELLOW}This will:${NC}"
echo "1. 🔧 Fix any permission issues"
echo "2. 🚀 Deploy the YuE model to Vertex AI"
echo "3. ✅ Validate the deployment"
echo "4. 🧪 Run basic tests"
echo ""
read -p "Continue? (y/N): " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Deployment cancelled."
    exit 0
fi

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo -e "\n${YELLOW}=== Step 1: Fix Permissions ===${NC}"
if [ -f "./fix_permissions.sh" ]; then
    chmod +x ./fix_permissions.sh
    ./fix_permissions.sh
    check_status "Permission fixes"
else
    echo -e "${YELLOW}⚠️ fix_permissions.sh not found, skipping${NC}"
fi

echo -e "\n${YELLOW}=== Step 2: Deploy to Vertex AI ===${NC}"
chmod +x ./deploy.sh
./deploy.sh
check_status "Vertex AI deployment"

echo -e "\n${YELLOW}=== Step 3: Validate Deployment ===${NC}"
# Wait a moment for deployment to settle
echo "Waiting 30 seconds for deployment to settle..."
sleep 30

chmod +x ./validate_deployment.sh
./validate_deployment.sh
check_status "Deployment validation"

echo -e "\n${YELLOW}=== Step 4: Run Basic Tests ===${NC}"
if [ -f "./test_endpoint.py" ]; then
    echo "Running Python endpoint test..."
    python3 ./test_endpoint.py
    check_status "Python endpoint test"
else
    echo -e "${YELLOW}⚠️ test_endpoint.py not found, skipping Python test${NC}"
fi

# Test with curl if available
if [ -f "./test_curl.sh" ]; then
    echo "Running curl test..."
    chmod +x ./test_curl.sh
    ./test_curl.sh
    check_status "Curl test"
else
    echo -e "${YELLOW}⚠️ test_curl.sh not found, skipping curl test${NC}"
fi

echo -e "\n${GREEN}🎉 Complete deployment sequence finished successfully!${NC}"
echo -e "${BLUE}Your YuE model is now deployed and validated on Vertex AI${NC}"

echo -e "\n${YELLOW}=== Summary ===${NC}"
echo "✅ Permissions configured"
echo "✅ Model deployed to endpoint: yue-vertex-endpoint"
echo "✅ Deployment validated"
echo "✅ Basic tests completed"

echo -e "\n${YELLOW}=== Next Steps ===${NC}"
echo "1. 📊 Monitor your deployment: https://console.cloud.google.com/vertex-ai"
echo "2. 📋 Check logs: https://console.cloud.google.com/logs"
echo "3. 🎵 Start generating music!"

echo -e "\n${YELLOW}=== Useful Commands ===${NC}"
echo "# View logs:"
echo "./view_logs.sh"
echo ""
echo "# Monitor performance:"
echo "./test_and_monitor.sh"
echo ""
echo "# Test cold start optimization:"
echo "./test_optimized_cold_start.sh" 