#!/bin/bash

# Quick rebuild for lazy loading model downloads
# Keeps existing deployment - just updates the container image

set -e
set -x

PROJECT_ID="music-generation-prototype"
REGION="us-central1"
REPOSITORY="yue-models"
IMAGE_NAME="yue-flask-server"
MODEL_ID="7146952024381194240"

# New build timestamp for lazy loading version
BUILD_TIME=$(date '+%Y%m%d-%H%M%S')
IMAGE_TAG="lazy-loading-${BUILD_TIME}"

echo "🔄 Rebuilding YuE container with lazy loading model downloads..."
echo "📦 New image tag: ${IMAGE_TAG}"

# Build new image
FULL_IMAGE_NAME="${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPOSITORY}/${IMAGE_NAME}:${IMAGE_TAG}"
LATEST_IMAGE_NAME="${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPOSITORY}/${IMAGE_NAME}:latest"

echo "🏗️ Building container with lazy loading..."
docker build \
    --platform linux/amd64 \
    --tag ${FULL_IMAGE_NAME} \
    --tag ${LATEST_IMAGE_NAME} \
    .

if [ $? -ne 0 ]; then
    echo "❌ Docker build failed"
    exit 1
fi

echo "✅ Container built successfully"

# Push images
echo "📤 Pushing to Artifact Registry..."
docker push ${FULL_IMAGE_NAME}
docker push ${LATEST_IMAGE_NAME}

if [ $? -ne 0 ]; then
    echo "❌ Push failed"
    exit 1
fi

echo "✅ Images pushed successfully"

# Upload new model version
echo "📦 Uploading new model version to Vertex AI..."
gcloud ai models upload \
    --region=${REGION} \
    --display-name=yue-flask-model \
    --container-image-uri=${FULL_IMAGE_NAME} \
    --container-health-route=/health \
    --container-predict-route=/predict \
    --container-ports=8080 \
    --version-aliases=lazy-loading \
    --quiet

if [ $? -ne 0 ]; then
    echo "❌ Model upload failed"
    exit 1
fi

echo "✅ New model version uploaded"

# Get new model ID
NEW_MODEL_ID=$(gcloud ai models list --region=${REGION} --filter="displayName:yue-flask-model" --format="value(name)" --limit=1)

echo "🔄 Updating endpoint with new model version..."
echo "📊 New model ID: ${NEW_MODEL_ID}"

# Update the endpoint deployment
gcloud ai endpoints deploy-model yue-flask-endpoint \
    --region=${REGION} \
    --model=${NEW_MODEL_ID} \
    --display-name=yue-flask-model-lazy-loading \
    --machine-type=g2-standard-4 \
    --accelerator=count=1,type=nvidia-l4 \
    --min-replica-count=1 \
    --max-replica-count=3 \
    --traffic-split=0=100 \
    --quiet

if [ $? -ne 0 ]; then
    echo "❌ Endpoint deployment failed"
    exit 1
fi

echo "🎉 Deployment updated successfully!"
echo "🔧 New features:"
echo "  • Lazy model loading on first request"
echo "  • Faster container startup"  
echo "  • Health checks pass immediately"
echo "  • Models download automatically when needed"
echo "  • Proper symlink structure (matches entrypoint.py)"
echo "  • Thread-safe concurrent request handling"
echo ""
echo "🧪 Test the health check:"
echo "curl -X GET https://ENDPOINT_URL/health"
echo ""
echo "📊 Model status will show 'not_loaded' until first prediction request" 