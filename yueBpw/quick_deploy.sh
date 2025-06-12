#!/bin/bash
set -e

PROJECT_ID="music-generation-prototype"
REGION="us-central1"
BUCKET_NAME="yue-model-weights-20250607"

echo "🚀 Starting YuE Model Deployment..."

# Step 1: Enable APIs
echo "Step 1: Enabling APIs..."
gcloud services enable artifactregistry.googleapis.com aiplatform.googleapis.com cloudbuild.googleapis.com

# Step 2: Create Artifact Registry
echo "Step 2: Creating Artifact Registry repository..."
gcloud artifacts repositories create yue-models \
    --repository-format=docker \
    --location=$REGION \
    --project=$PROJECT_ID

# Step 3: Build and push image
echo "Step 3: Building and pushing Docker image..."
gcloud builds submit --config cloudbuild.yaml .

# Step 4: Upload model
echo "Step 4: Uploading model to Vertex AI..."
MODEL_OUTPUT=$(gcloud ai models upload \
    --region=$REGION \
    --display-name="yue-model" \
    --container-image-uri="$REGION-docker.pkg.dev/$PROJECT_ID/yue-models/yue-server:latest" \
    --container-ports=8000 \
    --container-health-route=/health \
    --container-predict-route=/predict \
    --container-env-vars="MODEL_BUCKET_NAME=$BUCKET_NAME,GOOGLE_CLOUD_PROJECT=$PROJECT_ID" \
    --project=$PROJECT_ID \
    --format="value(name)")

MODEL_ID=$(echo $MODEL_OUTPUT | sed 's/.*models\///')
echo "Model ID: $MODEL_ID"

# Step 5: Create endpoint
echo "Step 5: Creating endpoint..."
ENDPOINT_OUTPUT=$(gcloud ai endpoints create \
    --region=$REGION \
    --display-name="yue-endpoint" \
    --project=$PROJECT_ID \
    --format="value(name)")

ENDPOINT_ID=$(echo $ENDPOINT_OUTPUT | sed 's/.*endpoints\///')
echo "Endpoint ID: $ENDPOINT_ID"

# Step 6: Deploy model to endpoint
echo "Step 6: Deploying model to endpoint..."
gcloud ai endpoints deploy-model $ENDPOINT_ID \
    --region=$REGION \
    --model=$MODEL_ID \
    --display-name="yue-deployment" \
    --machine-type=n1-standard-4 \
    --accelerator-type=NVIDIA_TESLA_T4 \
    --accelerator-count=1 \
    --min-replica-count=1 \
    --max-replica-count=3 \
    --project=$PROJECT_ID

echo "🎉 Deployment complete!"
echo "Model ID: $MODEL_ID"
echo "Endpoint ID: $ENDPOINT_ID"
echo "Test your deployment with:"
echo "curl -X POST -H \"Authorization: Bearer \$(gcloud auth print-access-token)\" -H \"Content-Type: application/json\" -d '{\"instances\": [{\"text\": \"Generate a happy song\"}]}' \"https://$REGION-aiplatform.googleapis.com/v1/projects/$PROJECT_ID/locations/$REGION/endpoints/$ENDPOINT_ID:predict\"" 