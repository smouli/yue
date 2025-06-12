#!/bin/bash
# Run these commands from your LOCAL MACHINE or CLOUD SHELL
# where you have proper gcloud permissions

PROJECT_ID="music-generation-prototype"
REGION="us-central1"
BUCKET_NAME="yue-model-weights-20250607"

echo "🚀 External Deployment Commands for YuE Model"
echo "Run these from your local machine or Cloud Shell (NOT from the VM)"
echo ""

# Step 1: Enable APIs
echo "Step 1: Enabling APIs..."
gcloud config set project $PROJECT_ID
gcloud services enable artifactregistry.googleapis.com aiplatform.googleapis.com cloudbuild.googleapis.com

# Step 2: Create Artifact Registry repository
echo "Step 2: Creating Artifact Registry repository..."
gcloud artifacts repositories create yue-models \
    --repository-format=docker \
    --location=$REGION \
    --project=$PROJECT_ID

# Step 3: Copy deployment files from VM (if running locally)
echo "Step 3: Copy files from VM to local machine..."
echo "Run this command to copy files from VM:"
echo "gcloud compute scp --recurse team_samarastudios_com@instance-20250402-200504:~/yueBpw/ ./yueBpw-local/ --zone=us-central1-a"
echo ""
echo "Then cd into yueBpw-local and run the remaining commands:"

# Step 4: Submit Cloud Build (run this after copying files)
echo "Step 4: Build and push Docker image..."
echo "cd yueBpw-local"
echo "gcloud builds submit --config cloudbuild.yaml . --timeout=1800"

# Step 5: Deploy to Vertex AI
echo "Step 5: Deploy to Vertex AI..."
echo "gcloud ai models upload \\"
echo "    --region=$REGION \\"
echo "    --display-name=\"yue-model\" \\"
echo "    --container-image-uri=\"$REGION-docker.pkg.dev/$PROJECT_ID/yue-models/yue-server:latest\" \\"
echo "    --container-ports=8000 \\"
echo "    --container-health-route=/health \\"
echo "    --container-predict-route=/predict \\"
echo "    --container-env-vars=\"MODEL_BUCKET_NAME=$BUCKET_NAME,GOOGLE_CLOUD_PROJECT=$PROJECT_ID\" \\"
echo "    --project=$PROJECT_ID"

echo ""
echo "Step 6: Create endpoint..."
echo "gcloud ai endpoints create \\"
echo "    --region=$REGION \\"
echo "    --display-name=\"yue-endpoint\" \\"
echo "    --project=$PROJECT_ID"

echo ""
echo "Step 7: Deploy model to endpoint (replace MODEL_ID and ENDPOINT_ID)..."
echo "gcloud ai endpoints deploy-model \$ENDPOINT_ID \\"
echo "    --region=$REGION \\"
echo "    --model=\$MODEL_ID \\"
echo "    --display-name=\"yue-deployment\" \\"
echo "    --machine-type=n1-standard-4 \\"
echo "    --accelerator-type=NVIDIA_TESLA_T4 \\"
echo "    --accelerator-count=1 \\"
echo "    --min-replica-count=1 \\"
echo "    --max-replica-count=3 \\"
echo "    --project=$PROJECT_ID"

echo ""
echo "🎉 Deployment complete!" 