#!/bin/bash

# YuE Vertex AI - Entrypoint-based Model Download Deployment
# Downloads models from Hugging Face during container startup

set -e
set -x

PROJECT_ID="music-generation-prototype"
REGION="us-central1"
REPOSITORY="yue-models"
IMAGE_NAME="yue-flask-server"

# Build timestamp for entrypoint version
BUILD_TIME=$(date '+%Y%m%d-%H%M%S')
IMAGE_TAG="entrypoint-hf-${BUILD_TIME}"

echo "🔄 Building YuE container with entrypoint-based HF model downloads..."
echo "📦 New image tag: ${IMAGE_TAG}"

# Build new image
FULL_IMAGE_NAME="${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPOSITORY}/${IMAGE_NAME}:${IMAGE_TAG}"
LATEST_IMAGE_NAME="${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPOSITORY}/${IMAGE_NAME}:latest"

echo "🏗️ Building container with entrypoint model download..."
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
    --version-aliases=entrypoint-hf \
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
gcloud ai endpoints deploy-model yue-runtime-endpoint \
    --region=${REGION} \
    --model=${NEW_MODEL_ID} \
    --display-name=yue-flask-model-entrypoint-hf \
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
echo ""
echo "🔧 New architecture:"
echo "  • Models downloaded from Hugging Face at container startup"
echo "  • entrypoint.sh handles all model setup before server starts"
echo "  • Health checks show actual model readiness"
echo "  • No lazy loading - models ready immediately after startup"
echo "  • Production Gunicorn server"
echo "  • Predictable startup time (5-10 minutes for model download)"
echo ""
echo "📥 Model sources:"
echo "  • Stage 1: m-a-p/YuE-s1-7B-anneal-en-cot (Hugging Face)"
echo "  • Stage 2: m-a-p/YuE-s2-1B-general (Hugging Face)"
echo ""
echo "🧪 Test the deployment:"
echo "curl -X GET https://ENDPOINT_URL/health"
echo ""
echo "📊 Health check will show model status and file counts" 