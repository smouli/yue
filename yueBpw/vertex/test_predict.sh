#!/bin/bash

# Simple Test Script for YuE Predict Endpoint

set -e

# Configuration
REGION="us-central1"
ENDPOINT_NAME="yue-runtime-endpoint"

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${GREEN}🎵 YUE PREDICT ENDPOINT TEST 🎵${NC}"

# Get endpoint URL
echo -e "${BLUE}Getting endpoint URL...${NC}"
ENDPOINT_URL=$(gcloud ai endpoints describe ${ENDPOINT_NAME} \
  --region=${REGION} \
  --format="value(name)")

if [ -z "$ENDPOINT_URL" ]; then
    echo "❌ Could not find endpoint. Make sure it's deployed."
    exit 1
fi

PREDICTION_URL="https://${REGION}-aiplatform.googleapis.com/v1/${ENDPOINT_URL}:predict"
echo -e "${GREEN}✅ Endpoint URL: ${PREDICTION_URL}${NC}"

# Test prediction (this will trigger model download if needed)
echo -e "${BLUE}🚀 Testing music generation...${NC}"
echo -e "${YELLOW}Note: First request may take 5-10 minutes for model download${NC}"

RESPONSE=$(curl -s -X POST "${PREDICTION_URL}" \
  -H "Authorization: Bearer $(gcloud auth print-access-token)" \
  -H "Content-Type: application/json" \
  -d '{
    "instances": [
      {
        "user_id": "test_user_123",
        "song_name": "My Test Song", 
        "lyrics": "This is a test song\nWith simple lyrics\nFor testing purposes",
        "genre": "pop"
      }
    ]
  }')

echo -e "${GREEN}📋 Response:${NC}"
echo "$RESPONSE" | jq '.'

# Extract request ID if available
REQUEST_ID=$(echo "$RESPONSE" | jq -r '.predictions[0].request_id // empty')

if [ -n "$REQUEST_ID" ]; then
    echo -e "${BLUE}📊 Request ID: ${REQUEST_ID}${NC}"
    echo -e "${YELLOW}You can check status with:${NC}"
    echo -e "curl -X POST '${PREDICTION_URL}' \\"
    echo -e "  -H 'Authorization: Bearer \$(gcloud auth print-access-token)' \\"
    echo -e "  -H 'Content-Type: application/json' \\"
    echo -e "  -d '{\"instances\": [{\"status_request_id\": \"${REQUEST_ID}\"}]}'"
fi

echo -e "${GREEN}🎉 Test completed!${NC}" 