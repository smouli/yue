#!/bin/bash

# Test Model Download Workflow
# This script demonstrates how to manually download models using curl

set -e

# Configuration
PROJECT_ID="music-generation-prototype"
REGION="us-central1"
ENDPOINT_NAME="yue-flask-endpoint"

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${GREEN}=========================================${NC}"
echo -e "${GREEN}🧪 YUE MODEL DOWNLOAD TEST 🧪${NC}"
echo -e "${GREEN}=========================================${NC}"

# Get the endpoint URL
echo -e "${BLUE}🔍 Getting endpoint URL...${NC}"
ENDPOINT_URL=$(gcloud ai endpoints describe ${ENDPOINT_NAME} \
  --region=${REGION} \
  --format="value(deployedModels[0].serviceAccount)")

if [ -z "$ENDPOINT_URL" ]; then
    echo -e "${RED}❌ Could not find endpoint URL${NC}"
    echo -e "${YELLOW}💡 Make sure the endpoint is deployed:${NC}"
    echo -e "${YELLOW}   gcloud ai endpoints list --region=${REGION}${NC}"
    exit 1
fi

# Get the actual endpoint URL for predictions
ENDPOINT_URL=$(gcloud ai endpoints describe ${ENDPOINT_NAME} \
  --region=${REGION} \
  --format="value(name)")

# Convert to prediction URL
PREDICTION_URL="https://${REGION}-aiplatform.googleapis.com/v1/${ENDPOINT_URL}:predict"
BASE_URL="https://${REGION}-aiplatform.googleapis.com/v1/${ENDPOINT_URL}"

echo -e "${GREEN}✅ Endpoint URL: ${ENDPOINT_URL}${NC}"
echo -e "${GREEN}✅ Prediction URL: ${PREDICTION_URL}${NC}"

# Get access token
echo -e "${BLUE}🔑 Getting access token...${NC}"
ACCESS_TOKEN=$(gcloud auth print-access-token)

if [ -z "$ACCESS_TOKEN" ]; then
    echo -e "${RED}❌ Could not get access token${NC}"
    echo -e "${YELLOW}💡 Make sure you're logged in: gcloud auth login${NC}"
    exit 1
fi

echo -e "${GREEN}✅ Access token obtained${NC}"

# Function to make health check
check_health() {
    echo -e "${BLUE}🏥 Checking health...${NC}"
    
    # For Vertex AI, we need to use the predict endpoint format
    curl -s -X POST "${PREDICTION_URL}" \
        -H "Authorization: Bearer ${ACCESS_TOKEN}" \
        -H "Content-Type: application/json" \
        -d '{
            "instances": [
                {
                    "health_check": true
                }
            ]
        }' | jq '.'
}

# Function to check model status
check_models_status() {
    echo -e "${BLUE}📊 Checking model status...${NC}"
    
    curl -s -X POST "${PREDICTION_URL}" \
        -H "Authorization: Bearer ${ACCESS_TOKEN}" \
        -H "Content-Type: application/json" \
        -d '{
            "instances": [
                {
                    "models_status": true
                }
            ]
        }' | jq '.'
}

# Function to trigger model download
trigger_download() {
    echo -e "${BLUE}📥 Triggering model download...${NC}"
    
    curl -s -X POST "${PREDICTION_URL}" \
        -H "Authorization: Bearer ${ACCESS_TOKEN}" \
        -H "Content-Type: application/json" \
        -d '{
            "instances": [
                {
                    "download_models": true
                }
            ]
        }' | jq '.'
}

# Step 1: Initial health check
echo -e "\n${YELLOW}📋 Step 1: Initial Health Check${NC}"
check_health

# Step 2: Check initial model status
echo -e "\n${YELLOW}📋 Step 2: Check Model Status (Before Download)${NC}"
check_models_status

# Step 3: Trigger model download
echo -e "\n${YELLOW}📋 Step 3: Trigger Model Download${NC}"
trigger_download

# Step 4: Monitor download progress
echo -e "\n${YELLOW}📋 Step 4: Monitor Download Progress${NC}"
echo -e "${BLUE}⏳ Waiting for download to complete (this may take 5-10 minutes)...${NC}"

# Poll status every 30 seconds
for i in {1..20}; do
    sleep 30
    echo -e "${BLUE}🔄 Check #${i} (${i}0 seconds elapsed)${NC}"
    
    RESPONSE=$(curl -s -X POST "${PREDICTION_URL}" \
        -H "Authorization: Bearer ${ACCESS_TOKEN}" \
        -H "Content-Type: application/json" \
        -d '{
            "instances": [
                {
                    "models_status": true
                }
            ]
        }')
    
    echo "$RESPONSE" | jq '.'
    
    # Check if models are loaded
    if echo "$RESPONSE" | jq -r '.predictions[0].models_loaded' | grep -q "true"; then
        echo -e "${GREEN}✅ Models loaded successfully!${NC}"
        break
    fi
    
    if [ $i -eq 20 ]; then
        echo -e "${RED}⏰ Timeout after 10 minutes${NC}"
        echo -e "${YELLOW}💡 Download may still be in progress - check logs${NC}"
    fi
done

# Step 5: Final verification
echo -e "\n${YELLOW}📋 Step 5: Final Verification${NC}"
check_models_status

echo -e "\n${GREEN}=========================================${NC}"
echo -e "${GREEN}🎉 MODEL DOWNLOAD TEST COMPLETED! 🎉${NC}"
echo -e "${GREEN}=========================================${NC}"

echo -e "\n${YELLOW}📝 Manual Commands:${NC}"
echo -e "${YELLOW}Health Check:${NC}"
echo -e "curl -X POST '${PREDICTION_URL}' \\"
echo -e "  -H 'Authorization: Bearer \$(gcloud auth print-access-token)' \\"
echo -e "  -H 'Content-Type: application/json' \\"
echo -e "  -d '{\"instances\": [{\"health_check\": true}]}'"

echo -e "\n${YELLOW}Model Status:${NC}"
echo -e "curl -X POST '${PREDICTION_URL}' \\"
echo -e "  -H 'Authorization: Bearer \$(gcloud auth print-access-token)' \\"
echo -e "  -H 'Content-Type: application/json' \\"
echo -e "  -d '{\"instances\": [{\"models_status\": true}]}'"

echo -e "\n${YELLOW}Download Models:${NC}"
echo -e "curl -X POST '${PREDICTION_URL}' \\"
echo -e "  -H 'Authorization: Bearer \$(gcloud auth print-access-token)' \\"
echo -e "  -H 'Content-Type: application/json' \\"
echo -e "  -d '{\"instances\": [{\"download_models\": true}]}'" 