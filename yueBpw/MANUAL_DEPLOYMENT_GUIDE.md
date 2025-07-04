# Manual Vertex AI Deployment Guide

This guide is for manual deployment when you don't have sufficient permissions for the automated script.

## Prerequisites

**Person with Admin Access Needs:**
- Project Owner or Editor role on `music-generation-prototype`
- Vertex AI Admin role
- Artifact Registry Admin role

## Configuration

Your model weights are already uploaded to: `gs://yue-model-weights-20250607/model-weights/`

## Step 1: Enable APIs (Admin Required)

```bash
gcloud config set project music-generation-prototype

# Enable required APIs
gcloud services enable artifactregistry.googleapis.com
gcloud services enable aiplatform.googleapis.com
gcloud services enable containerregistry.googleapis.com
```

## Step 2: Create Artifact Registry Repository (Admin Required)

```bash
gcloud artifacts repositories create yue-models \
    --repository-format=docker \
    --location=us-central1 \
    --project=music-generation-prototype
```

## Step 3: Build and Push Docker Image

### Option A: From your current machine (if Docker works)
```bash
cd /home/team_samarastudios_com/yueBpw

# Configure Docker auth
gcloud auth configure-docker us-central1-docker.pkg.dev

# Build image
IMAGE_URI="us-central1-docker.pkg.dev/music-generation-prototype/yue-models/yue-server:latest"
docker build -t $IMAGE_URI -f Dockerfile.vertex .

# Push image
docker push $IMAGE_URI
```

### Option B: Using Cloud Build (Recommended)
```bash
cd /home/team_samarastudios_com/yueBpw

# Submit build job to Cloud Build
gcloud builds submit --tag us-central1-docker.pkg.dev/music-generation-prototype/yue-models/yue-server:latest --dockerfile=Dockerfile.vertex .
```

## Step 4: Deploy to Vertex AI

### Upload Model
```bash
gcloud ai models upload \
    --region=us-central1 \
    --display-name="yue-model" \
    --container-image-uri="us-central1-docker.pkg.dev/music-generation-prototype/yue-models/yue-server:latest" \
    --container-ports=8000 \
    --container-health-route=/health \
    --container-predict-route=/predict \
    --container-env-vars="MODEL_BUCKET_NAME=yue-model-weights-20250607,GOOGLE_CLOUD_PROJECT=music-generation-prototype" \
    --project=music-generation-prototype

# Note the MODEL_ID from the output
```

### Create Endpoint
```bash
gcloud ai endpoints create \
    --region=us-central1 \
    --display-name="yue-endpoint" \
    --project=music-generation-prototype

# Note the ENDPOINT_ID from the output
```

### Deploy Model to Endpoint
```bash
# Replace MODEL_ID and ENDPOINT_ID with values from above
MODEL_ID="your-model-id-here"
ENDPOINT_ID="your-endpoint-id-here"

gcloud ai endpoints deploy-model $ENDPOINT_ID \
    --region=us-central1 \
    --model=$MODEL_ID \
    --display-name="yue-deployment" \
    --machine-type=n1-standard-4 \
    --accelerator-type=NVIDIA_TESLA_T4 \
    --accelerator-count=1 \
    --min-replica-count=1 \
    --max-replica-count=3 \
    --project=music-generation-prototype
```

## Step 5: Test Deployment

```bash
# Test prediction (replace ENDPOINT_ID)
curl -X POST \
    -H "Authorization: Bearer $(gcloud auth print-access-token)" \
    -H "Content-Type: application/json" \
    -d '{"instances": [{"text": "Generate a happy upbeat song"}]}' \
    "https://us-central1-aiplatform.googleapis.com/v1/projects/music-generation-prototype/locations/us-central1/endpoints/$ENDPOINT_ID:predict"
```

## Alternative: Use Cloud Build for Everything

If you can't run Docker locally, use Cloud Build for the entire process:

### Create `cloudbuild.yaml`
```yaml
steps:
  # Build and push image
  - name: 'gcr.io/cloud-builders/docker'
    args: [
      'build',
      '-f', 'Dockerfile.vertex',
      '-t', 'us-central1-docker.pkg.dev/music-generation-prototype/yue-models/yue-server:latest',
      '.'
    ]
  
  # Push to Artifact Registry
  - name: 'gcr.io/cloud-builders/docker'
    args: [
      'push',
      'us-central1-docker.pkg.dev/music-generation-prototype/yue-models/yue-server:latest'
    ]

options:
  logging: CLOUD_LOGGING_ONLY
  machineType: 'E2_HIGHCPU_8'
```

### Run Cloud Build
```bash
gcloud builds submit --config cloudbuild.yaml .
```

## Current Status

✅ **Completed:**
- Model weights uploaded to GCS: `gs://yue-model-weights-20250607/model-weights/`
- Total size: ~24GB (includes snapshots with resolved files)
- Deployment scripts created and tested

⏳ **Needs Admin:**
- Enable APIs (Artifact Registry, Vertex AI)
- Create Artifact Registry repository
- Build and push Docker image
- Deploy to Vertex AI

## Next Steps for Admin

1. Run the API enablement commands
2. Create the Artifact Registry repository  
3. Choose Option A (Docker) or Option B (Cloud Build) for image creation
4. Deploy the model using the gcloud commands above
5. Test the endpoint

## Cost Estimate

- **Storage**: ~$0.60/month for 24GB in GCS
- **Compute**: ~$0.50-2.00/hour depending on usage (T4 GPU)
- **Artifact Registry**: ~$0.20/month for Docker images

The deployment will auto-scale from 1-3 replicas based on traffic. 