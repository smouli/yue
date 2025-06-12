#!/bin/bash

# Configuration
PROJECT_ID="music-generation-prototype"
REGION="us-central1"
BUCKET_NAME="yue-model-weights-20250607"
MODEL_NAME="yue-model"
ENDPOINT_NAME="yue-endpoint"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}=== YuE Model Vertex AI Deployment Script (DEBUG MODE) ===${NC}"

# Function to check command success and show errors
check_command() {
    if [ $? -ne 0 ]; then
        echo -e "${RED}❌ Command failed with exit code $?${NC}"
        return 1
    else
        echo -e "${GREEN}✅ Command succeeded${NC}"
        return 0
    fi
}

# Step 1: Create GCS bucket and upload model weights
echo -e "${YELLOW}Step 1: Setting up Google Cloud Storage${NC}"

# Create bucket if it doesn't exist - SHOW ALL ERRORS
echo "Creating/checking bucket..."
gsutil mb -p $PROJECT_ID -c STANDARD -l $REGION gs://$BUCKET_NAME/
if [ $? -ne 0 ]; then
    echo -e "${YELLOW}⚠️  Bucket creation failed - checking if it already exists...${NC}"
    gsutil ls gs://$BUCKET_NAME/ >/dev/null
    check_command
fi

# Check if model weights are already in GCS, upload if not
echo "Checking for model weights in GCS..."
if gsutil ls "gs://$BUCKET_NAME/model-weights/blobs/" >/dev/null 2>&1; then
    echo "✅ Model weights already exist in GCS"
else
    echo "Uploading model weights to GCS..."
    # Upload the HuggingFace cache structure (blobs and snapshots)
    HF_CACHE_DIR="/home/team_samarastudios_com/.cache/huggingface/hub/models--m-a-p--YuE-s1-7B-anneal-en-cot"
    gsutil -m cp -r "$HF_CACHE_DIR/blobs" "gs://$BUCKET_NAME/model-weights/"
    check_command
    gsutil -m cp -r "$HF_CACHE_DIR/snapshots" "gs://$BUCKET_NAME/model-weights/"
    check_command
fi

# Step 2: Build and push Docker image to Artifact Registry
echo -e "${YELLOW}Step 2: Building and pushing Docker image${NC}"

# Enable required APIs - SHOW ALL ERRORS
echo "Enabling required APIs..."
echo "Enabling Artifact Registry API..."
gcloud services enable artifactregistry.googleapis.com
if [ $? -ne 0 ]; then
    echo -e "${RED}❌ Failed to enable Artifact Registry API${NC}"
    echo "Error details above. Check if you have serviceusage.services.enable permission"
else
    echo -e "${GREEN}✅ Artifact Registry API enabled${NC}"
fi

echo "Enabling Vertex AI API..."
gcloud services enable aiplatform.googleapis.com
if [ $? -ne 0 ]; then
    echo -e "${RED}❌ Failed to enable Vertex AI API${NC}"
    echo "Error details above. Check if you have serviceusage.services.enable permission"
else
    echo -e "${GREEN}✅ Vertex AI API enabled${NC}"
fi

# Create Artifact Registry repository - SHOW ALL ERRORS
echo "Creating Artifact Registry repository..."
gcloud artifacts repositories create yue-models \
    --repository-format=docker \
    --location=$REGION \
    --project=$PROJECT_ID
if [ $? -ne 0 ]; then
    echo -e "${YELLOW}⚠️  Repository creation failed - checking if it already exists...${NC}"
    gcloud artifacts repositories describe yue-models --location=$REGION --project=$PROJECT_ID >/dev/null
    check_command
fi

# Configure Docker auth
echo "Configuring Docker authentication..."
gcloud auth configure-docker $REGION-docker.pkg.dev
check_command

# Check and set permissions for Cloud Build service account
echo "Checking Cloud Build service account permissions..."
PROJECT_NUMBER=$(gcloud projects describe $PROJECT_ID --format="value(projectNumber)")
if [ $? -ne 0 ]; then
    echo -e "${RED}❌ Failed to get project number${NC}"
    exit 1
fi

BUILD_SA="${PROJECT_NUMBER}@cloudbuild.gserviceaccount.com"
echo "Cloud Build service account: $BUILD_SA"

# Check current IAM policy - SHOW ALL ERRORS
echo "Getting current IAM policy..."
gcloud projects get-iam-policy $PROJECT_ID --format="table(bindings.members)" --filter="bindings.role:roles/artifactregistry.writer"
if [ $? -ne 0 ]; then
    echo -e "${RED}❌ Failed to get IAM policy. Check if you have resourcemanager.projects.getIamPolicy permission${NC}"
fi

# Ensure Cloud Build SA has Artifact Registry writer permissions
if ! gcloud projects get-iam-policy $PROJECT_ID --format="table(bindings.members)" --filter="bindings.role:roles/artifactregistry.writer" | grep -q "$BUILD_SA"; then
    echo "🔧 Granting Artifact Registry writer permission to Cloud Build service account..."
    gcloud projects add-iam-policy-binding $PROJECT_ID \
        --member="serviceAccount:$BUILD_SA" \
        --role="roles/artifactregistry.writer"
    if [ $? -ne 0 ]; then
        echo -e "${RED}❌ Failed to grant IAM permission. Check if you have resourcemanager.projects.setIamPolicy permission${NC}"
        exit 1
    else
        echo -e "${GREEN}✅ IAM permission granted${NC}"
    fi
else
    echo "✅ Cloud Build service account already has Artifact Registry permissions"
fi

# Build image using Cloud Build
IMAGE_URI="$REGION-docker.pkg.dev/$PROJECT_ID/yue-models/yue-server:latest"
echo "Starting Cloud Build with real-time logs..."
echo "Archive size may be large - this could take several minutes..."

gcloud builds submit \
    --config=cloudbuild-vertex.yaml \
    --project=$PROJECT_ID \
    --verbosity=info

if [ $? -ne 0 ]; then
    echo -e "${RED}❌ Cloud Build failed${NC}"
    echo "Check the build logs above for details"
    exit 1
else
    echo -e "${GREEN}✅ Cloud Build succeeded${NC}"
    echo -e "${GREEN}Image pushed to: $IMAGE_URI${NC}"
fi

# Step 3: Deploy to Vertex AI
echo -e "${YELLOW}Step 3: Deploying to Vertex AI${NC}"

# Upload model
echo "Uploading model to Vertex AI..."
gcloud ai models upload \
    --region=$REGION \
    --display-name=$MODEL_NAME \
    --container-image-uri=$IMAGE_URI \
    --container-ports=8000 \
    --container-health-route=/health \
    --container-predict-route=/predict \
    --project=$PROJECT_ID

if [ $? -ne 0 ]; then
    echo -e "${RED}❌ Model upload failed${NC}"
    echo "Check if you have aiplatform.models.create permission"
    exit 1
else
    echo -e "${GREEN}✅ Model uploaded successfully${NC}"
fi

# Create endpoint
echo "Creating Vertex AI endpoint..."
gcloud ai endpoints create \
    --region=$REGION \
    --display-name=$ENDPOINT_NAME \
    --project=$PROJECT_ID

if [ $? -ne 0 ]; then
    echo -e "${RED}❌ Endpoint creation failed${NC}"
    echo "Check if you have aiplatform.endpoints.create permission"
else
    echo -e "${GREEN}✅ Endpoint created successfully${NC}"
fi

echo -e "${GREEN}Deployment process completed!${NC}"
echo -e "${YELLOW}Don't forget to:${NC}"
echo "1. Set up proper IAM roles for the service account"
echo "2. Configure environment variables in the model"
echo "3. Test the endpoint before production use" 