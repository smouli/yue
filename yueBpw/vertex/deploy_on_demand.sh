#!/bin/bash

# YuE Vertex AI - On-Demand Model Loading Deployment
# Server starts immediately, models download on first request

set -e
set -x

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
IMAGE_TAG="on-demand-${BUILD_TIME}"

echo -e "${GREEN}=========================================${NC}"
echo -e "${GREEN}🚀 YUE ON-DEMAND DEPLOYMENT 🚀${NC}"
echo -e "${GREEN}=========================================${NC}"
echo -e "${BLUE}📅 Started: $(date '+%Y-%m-%d %H:%M:%S')${NC}"
echo -e "${BLUE}🔄 Models download: On first request${NC}"
echo -e "${BLUE}⚡ Startup: Immediate (< 30 seconds)${NC}"
echo -e "${GREEN}=========================================${NC}"

# Build image
FULL_IMAGE_NAME="${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPOSITORY}/${IMAGE_NAME}:${IMAGE_TAG}"
LATEST_IMAGE_NAME="${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPOSITORY}/${IMAGE_NAME}:latest"

echo -e "\n${BLUE}🏗️  Building Docker image...${NC}"
docker build --platform linux/amd64 -t ${FULL_IMAGE_NAME} -t ${LATEST_IMAGE_NAME} .

echo -e "\n${BLUE}☁️  Pushing to Artifact Registry...${NC}"
docker push ${FULL_IMAGE_NAME}
docker push ${LATEST_IMAGE_NAME}

echo -e "\n${BLUE}🎯 Uploading to Vertex AI...${NC}"
gcloud ai models upload \
    --region=${REGION} \
    --display-name="yue-on-demand-model" \
    --container-image-uri=${FULL_IMAGE_NAME} \
    --container-health-route=/health \
    --container-predict-route=/predict \
    --container-ports=8080 \
    --version-aliases=on-demand-latest \
    --quiet

# Get model ID
MODEL_ID=$(gcloud ai models list --region=${REGION} --filter="displayName:yue-on-demand-model" --format="value(name)" --limit=1)

echo -e "\n${BLUE}🚀 Deploying to endpoint...${NC}"
gcloud ai endpoints deploy-model ${ENDPOINT_NAME} \
    --region=${REGION} \
    --model=${MODEL_ID} \
    --display-name="yue-on-demand-deployment" \
    --machine-type=n1-standard-4 \
    --accelerator=type=nvidia-tesla-t4,count=1 \
    --min-replica-count=1 \
    --max-replica-count=3 \
    --quiet

echo -e "\n${GREEN}=========================================${NC}"
echo -e "${GREEN}✅ ON-DEMAND DEPLOYMENT COMPLETED! ✅${NC}"
echo -e "${GREEN}=========================================${NC}"
echo -e "${BLUE}🏷️  Image: ${IMAGE_TAG}${NC}"
echo -e "${BLUE}⚡ Startup: Immediate${NC}"
echo -e "${BLUE}📥 Models: Download on first request${NC}"
echo -e "${BLUE}🎯 Endpoint: ${ENDPOINT_NAME}${NC}"
echo -e "${GREEN}=========================================${NC}"

echo -e "\n${YELLOW}📝 Usage Instructions:${NC}"
echo -e "${YELLOW}1. Server starts immediately (health check passes)${NC}"
echo -e "${YELLOW}2. First request triggers 5-10 minute model download${NC}"
echo -e "${YELLOW}3. Subsequent requests are processed immediately${NC}"
echo -e "${YELLOW}4. Use POST /download-models to preload models${NC}"
echo -e "${YELLOW}5. Use GET /models/status to check loading status${NC}"

echo -e "\n${GREEN}🎉 Ready to receive requests!${NC}" 