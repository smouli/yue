#!/bin/bash

# Quick Fix Deployment - Patches missing modules and redeploys
# This should be much faster than full rebuild due to Docker layer caching

set -e

# Configuration
PROJECT_ID="music-generation-prototype"
REGION="us-central1"
REPOSITORY="yue-models"
IMAGE_NAME="yue-flask-server"
ENDPOINT_NAME="yue-runtime-endpoint"

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Build timestamp
BUILD_TIME=$(date '+%Y%m%d-%H%M%S')
IMAGE_TAG="fixed-modules-${BUILD_TIME}"

echo -e "${GREEN}🔧 YUE QUICK FIX DEPLOYMENT 🔧${NC}"
echo -e "${GREEN}==============================${NC}"
echo -e "${BLUE}📅 Started: $(date '+%Y-%m-%d %H:%M:%S')${NC}"
echo -e "${BLUE}🔧 Fix: Adding missing YuE modules${NC}"
echo -e "${BLUE}⚡ Speed: Fast (Docker layer caching)${NC}"
echo -e "${GREEN}==============================${NC}"

# Build image (should be fast due to caching)
FULL_IMAGE_NAME="${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPOSITORY}/${IMAGE_NAME}:${IMAGE_TAG}"

echo -e "\n${BLUE}🏗️  Building patched image (fast due to caching)...${NC}"
docker build --platform linux/amd64 -t ${FULL_IMAGE_NAME} .

echo -e "\n${BLUE}☁️  Pushing to Artifact Registry...${NC}"
docker push ${FULL_IMAGE_NAME}

echo -e "\n${BLUE}🎯 Uploading to Vertex AI...${NC}"
gcloud ai models upload \
    --region=${REGION} \
    --display-name="yue-fixed-model" \
    --container-image-uri=${FULL_IMAGE_NAME} \
    --container-health-route=/health \
    --container-predict-route=/predict \
    --container-ports=8080 \
    --version-aliases=fixed-latest \
    --quiet

# Get model ID
MODEL_ID=$(gcloud ai models list --region=${REGION} --filter="displayName:yue-fixed-model" --format="value(name)" --limit=1)

echo -e "\n${BLUE}🚀 Deploying to endpoint...${NC}"
gcloud ai endpoints deploy-model ${ENDPOINT_NAME} \
    --region=${REGION} \
    --model=${MODEL_ID} \
    --display-name="yue-fixed-deployment" \
    --machine-type=n1-standard-4 \
    --accelerator=type=nvidia-tesla-t4,count=1 \
    --min-replica-count=1 \
    --max-replica-count=3 \
    --quiet

echo -e "\n${GREEN}==============================${NC}"
echo -e "${GREEN}✅ QUICK FIX COMPLETED! ✅${NC}"
echo -e "${GREEN}==============================${NC}"
echo -e "${BLUE}🏷️  Image: ${IMAGE_TAG}${NC}"
echo -e "${BLUE}🔧 Fix: Missing modules added${NC}"
echo -e "${BLUE}⚡ Build: Fast (cached layers)${NC}"
echo -e "${BLUE}🎯 Endpoint: ${ENDPOINT_NAME}${NC}"
echo -e "${GREEN}==============================${NC}"

echo -e "\n${YELLOW}🧪 Test the fix:${NC}"
echo -e "${YELLOW}Wait 2-3 minutes for deployment, then test:${NC}"

PREDICTION_URL="https://us-central1-aiplatform.googleapis.com/v1/projects/music-generation-prototype/locations/us-central1/endpoints/4158120979295371264:predict"

echo -e "curl -X POST '${PREDICTION_URL}' \\"
echo -e "  -H 'Authorization: Bearer \$(gcloud auth print-access-token)' \\"
echo -e "  -H 'Content-Type: application/json' \\"
echo -e "  -d '{\"instances\": [{\"user_id\": \"test_fix\", \"song_name\": \"Fixed Test\", \"lyrics\": \"Testing the fix\", \"genre\": \"pop\"}]}'"

echo -e "\n${GREEN}🎉 Your YuE server should now work without module errors!${NC}" 