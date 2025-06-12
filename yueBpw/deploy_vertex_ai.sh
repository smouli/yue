#!/bin/bash

# Configuration
PROJECT_ID="music-generation-prototype"
REGION="us-central1"
BUCKET_NAME="yue-model-weights-20250607"
MODEL_NAME="yue-model"
ENDPOINT_NAME="yue-endpoint"

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}=== YuE Model Vertex AI Deployment Script ===${NC}"

# Step 1: Create GCS bucket and upload model weights
echo -e "${YELLOW}Step 1: Setting up Google Cloud Storage${NC}"

# Create bucket if it doesn't exist
gsutil mb -p $PROJECT_ID -c STANDARD -l $REGION gs://$BUCKET_NAME/ 2>/dev/null || echo "Bucket already exists"

# Check if model weights are already in GCS, upload if not
echo "Checking for model weights in GCS..."
if gsutil ls "gs://$BUCKET_NAME/model-weights/blobs/" >/dev/null 2>&1; then
    echo "✅ Model weights already exist in GCS"
else
    echo "Uploading model weights to GCS..."
    # Upload the HuggingFace cache structure (blobs and snapshots)
    HF_CACHE_DIR="/home/team_samarastudios_com/.cache/huggingface/hub/models--m-a-p--YuE-s1-7B-anneal-en-cot"
    gsutil -m cp -r "$HF_CACHE_DIR/blobs" "gs://$BUCKET_NAME/model-weights/"
    gsutil -m cp -r "$HF_CACHE_DIR/snapshots" "gs://$BUCKET_NAME/model-weights/"
fi

# Step 2: Build and push Docker image to Artifact Registry
echo -e "${YELLOW}Step 2: Building and pushing Docker image${NC}"

# Enable required APIs (skip if permission denied)
echo "Enabling required APIs (may fail if service account lacks permissions)..."
gcloud services enable artifactregistry.googleapis.com 2>/dev/null || echo "⚠️  Could not enable Artifact Registry API - may already be enabled or need admin permissions"
gcloud services enable aiplatform.googleapis.com 2>/dev/null || echo "⚠️  Could not enable Vertex AI API - may already be enabled or need admin permissions"

# Create Artifact Registry repository
gcloud artifacts repositories create yue-models \
    --repository-format=docker \
    --location=$REGION \
    --project=$PROJECT_ID

# Configure Docker auth
gcloud auth configure-docker $REGION-docker.pkg.dev

# Check and set permissions for Cloud Build service account
echo "Checking Cloud Build service account permissions..."
PROJECT_NUMBER=$(gcloud projects describe $PROJECT_ID --format="value(projectNumber)")
BUILD_SA="${PROJECT_NUMBER}@cloudbuild.gserviceaccount.com"
echo "Cloud Build service account: $BUILD_SA"

# Ensure Cloud Build SA has Artifact Registry writer permissions
if ! gcloud projects get-iam-policy $PROJECT_ID --format="table(bindings.members)" --filter="bindings.role:roles/artifactregistry.writer" | grep -q "$BUILD_SA"; then
    echo "🔧 Granting Artifact Registry writer permission to Cloud Build service account..."
    gcloud projects add-iam-policy-binding $PROJECT_ID \
        --member="serviceAccount:$BUILD_SA" \
        --role="roles/artifactregistry.writer"
else
    echo "✅ Cloud Build service account already has Artifact Registry permissions"
fi

# Build image using Cloud Build (to avoid local disk space issues)
IMAGE_URI="$REGION-docker.pkg.dev/$PROJECT_ID/yue-models/yue-server:latest"
echo "Starting Cloud Build with real-time logs..."
echo "Archive size may be large - this could take several minutes..."

gcloud builds submit \
    --config=cloudbuild-vertex.yaml \
    --project=$PROJECT_ID \
    --verbosity=info

echo -e "${GREEN}Image pushed to: $IMAGE_URI${NC}"

# Step 3: Deploy to Vertex AI
echo -e "${YELLOW}Step 3: Deploying to Vertex AI${NC}"

# Upload model
gcloud ai models upload \
    --region=$REGION \
    --display-name=$MODEL_NAME \
    --container-image-uri=$IMAGE_URI \
    --container-ports=8000 \
    --container-health-route=/health \
    --container-predict-route=/predict \
    --project=$PROJECT_ID

# Create endpoint
gcloud ai endpoints create \
    --region=$REGION \
    --display-name=$ENDPOINT_NAME \
    --project=$PROJECT_ID

echo -e "${GREEN}Deployment initiated! Check Vertex AI console for status.${NC}"
echo -e "${YELLOW}Don't forget to:${NC}"
echo "1. Set up proper IAM roles for the service account"
echo "2. Configure environment variables in the model"
echo "3. Test the endpoint before production use" 