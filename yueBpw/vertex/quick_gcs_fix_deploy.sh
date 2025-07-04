#!/bin/bash

# Quick GCS Fix Deployment - Uses HMAC keys with proper write permissions
# This should fix the "Failed to upload one or more files to GCS" error

set -e

# Configuration
PROJECT_ID="music-generation-prototype"
REGION="us-central1"
REPOSITORY="yue-models"
IMAGE_NAME="yue-flask-server"
ENDPOINT_ID="4158120979295371264"

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Build timestamp
BUILD_TIME=$(date '+%Y%m%d-%H%M%S')
IMAGE_TAG="gcs-fixed-${BUILD_TIME}"

echo -e "${GREEN}🔧 YUE GCS FIX DEPLOYMENT 🔧${NC}"
echo -e "${GREEN}==============================${NC}"
echo -e "${BLUE}📅 Started: $(date '+%Y-%m-%d %H:%M:%S')${NC}"
echo -e "${BLUE}🔧 Fix: HMAC keys with write permissions${NC}"
echo -e "${BLUE}⚡ Speed: Fast (Docker layer caching)${NC}"
echo -e "${GREEN}==============================${NC}"

# Build image (should be fast due to caching)
FULL_IMAGE_NAME="${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPOSITORY}/${IMAGE_NAME}:${IMAGE_TAG}"

echo -e "\n${BLUE}🏗️  Building GCS-fixed image (fast due to caching)...${NC}"
docker build --platform linux/amd64 -t ${FULL_IMAGE_NAME} .

echo -e "\n${BLUE}☁️  Pushing to Artifact Registry...${NC}"
docker push ${FULL_IMAGE_NAME}

echo -e "\n${BLUE}🎯 Uploading to Vertex AI...${NC}"
gcloud ai models upload \
    --region=${REGION} \
    --display-name="yue-gcs-fixed-model" \
    --container-image-uri=${FULL_IMAGE_NAME} \
    --container-health-route=/health \
    --container-predict-route=/predict \
    --container-ports=8080 \
    --version-aliases=gcs-fixed-latest \
    --quiet

# Get model ID
MODEL_ID=$(gcloud ai models list --region=${REGION} --filter="displayName:yue-gcs-fixed-model" --format="value(name)" --limit=1)

echo -e "\n${BLUE}🚀 Deploying to endpoint...${NC}"
gcloud ai endpoints deploy-model ${ENDPOINT_ID} \
    --region=${REGION} \
    --model=${MODEL_ID} \
    --display-name="yue-gcs-fixed-deployment" \
    --machine-type=n1-standard-4 \
    --accelerator=type=nvidia-tesla-t4,count=1 \
    --min-replica-count=1 \
    --max-replica-count=3 \
    --quiet

echo -e "\n${GREEN}==============================${NC}"
echo -e "${GREEN}✅ GCS FIX COMPLETED! ✅${NC}"
echo -e "${GREEN}==============================${NC}"
echo -e "${BLUE}🏷️  Image: ${IMAGE_TAG}${NC}"
echo -e "${BLUE}🔧 Fix: HMAC key S3-compatible auth${NC}"
echo -e "${BLUE}⚡ Build: Fast (cached layers)${NC}"
echo -e "${BLUE}🎯 Endpoint: ${ENDPOINT_ID}${NC}"
echo -e "${GREEN}==============================${NC}"

echo -e "\n${YELLOW}🧪 Test the GCS fix:${NC}"
echo -e "${YELLOW}Wait 2-3 minutes for deployment, then test:${NC}"

PREDICTION_URL="https://us-central1-aiplatform.googleapis.com/v1/projects/music-generation-prototype/locations/us-central1/endpoints/4158120979295371264:predict"

echo -e "curl -X POST '${PREDICTION_URL}' \\"
echo -e "  -H 'Authorization: Bearer \$(gcloud auth print-access-token)' \\"
echo -e "  -H 'Content-Type: application/json' \\"
echo -e "  -d '{\"instances\": [{\"user_id\": \"test_gcs_fix\", \"song_name\": \"GCS Fixed Test\", \"lyrics\": \"Testing GCS uploads\", \"genre\": \"pop\"}]}'"

echo -e "\n${GREEN}🎉 Your YuE server should now upload files to GCS successfully!${NC}"
echo -e "\n${YELLOW}💡 What was fixed:${NC}"
echo -e "${YELLOW}  • Reverted to HMAC keys with S3-compatible API${NC}"
echo -e "${YELLOW}  • Uses boto3 with S3v2 signature for GCS compatibility${NC}"
echo -e "${YELLOW}  • Requires HMAC key to have 'Storage Admin' role${NC}"
echo -e "${YELLOW}  • See hmac_key_setup_guide.md for HMAC key setup${NC}" 