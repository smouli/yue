# YuE Model Vertex AI Deployment Guide

This guide walks you through deploying your YuE text-to-music generation model to Google Cloud Vertex AI.

## Prerequisites

1. **Google Cloud Project** with billing enabled
2. **APIs enabled**:
   - Vertex AI API
   - Artifact Registry API
   - Cloud Storage API
3. **gcloud CLI** installed and configured
4. **Docker** installed
5. **Appropriate IAM roles**:
   - Vertex AI Admin
   - Artifact Registry Admin  
   - Storage Admin

## Step 1: Prepare Your Environment

```bash
# Set your project variables
export PROJECT_ID="your-project-id"
export REGION="us-central1"
export BUCKET_NAME="your-model-bucket"

# Configure gcloud
gcloud config set project $PROJECT_ID
gcloud config set compute/region $REGION
```

## Step 2: Store Model Weights in Cloud Storage

### Option A: Use the automated script
```bash
# Edit the configuration in deploy_vertex_ai.sh
nano deploy_vertex_ai.sh

# Update these variables:
PROJECT_ID="your-actual-project-id"
BUCKET_NAME="your-actual-bucket-name"

# Run the deployment script
chmod +x deploy_vertex_ai.sh
./deploy_vertex_ai.sh
```

### Option B: Manual upload
```bash
# Create GCS bucket
gsutil mb -p $PROJECT_ID -c STANDARD -l $REGION gs://$BUCKET_NAME/

# Upload model weights (only the actual files, not symlinks)
gsutil -m cp -r "YuE-exllamav2/src/yue/models/models--m-a-p--YuE-s1-7B-anneal-en-cot/blobs" "gs://$BUCKET_NAME/model-weights/"
gsutil -m cp -r "YuE-exllamav2/src/yue/models/models--m-a-p--YuE-s1-7B-anneal-en-cot/snapshots" "gs://$BUCKET_NAME/model-weights/"
```

## Step 3: Build and Push Docker Image

```bash
# Enable required APIs
gcloud services enable artifactregistry.googleapis.com
gcloud services enable aiplatform.googleapis.com

# Create Artifact Registry repository
gcloud artifacts repositories create yue-models \
    --repository-format=docker \
    --location=$REGION \
    --project=$PROJECT_ID

# Configure Docker authentication
gcloud auth configure-docker $REGION-docker.pkg.dev

# Build image
IMAGE_URI="$REGION-docker.pkg.dev/$PROJECT_ID/yue-models/yue-server:latest"
docker build -t $IMAGE_URI -f Dockerfile.vertex .

# Push image
docker push $IMAGE_URI
```

## Step 4: Deploy to Vertex AI

### Create the model
```bash
gcloud ai models upload \
    --region=$REGION \
    --display-name="yue-model" \
    --container-image-uri=$IMAGE_URI \
    --container-ports=8000 \
    --container-health-route=/health \
    --container-predict-route=/predict \
    --container-env-vars="MODEL_BUCKET_NAME=$BUCKET_NAME,GOOGLE_CLOUD_PROJECT=$PROJECT_ID" \
    --project=$PROJECT_ID
```

### Create an endpoint
```bash
gcloud ai endpoints create \
    --region=$REGION \
    --display-name="yue-endpoint" \
    --project=$PROJECT_ID
```

### Deploy model to endpoint
```bash
# Get the model ID and endpoint ID from the previous commands
MODEL_ID="your-model-id"
ENDPOINT_ID="your-endpoint-id"

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
```

## Step 5: Test Your Deployment

```bash
# Get prediction endpoint
ENDPOINT_URL=$(gcloud ai endpoints describe $ENDPOINT_ID \
    --region=$REGION \
    --format="value(deployedModels[0].dedicatedResources.machineSpec.machineType)")

# Test with curl
curl -X POST \
    -H "Authorization: Bearer $(gcloud auth print-access-token)" \
    -H "Content-Type: application/json" \
    -d '{"instances": [{"text": "Generate a happy upbeat song"}]}' \
    "https://$REGION-aiplatform.googleapis.com/v1/projects/$PROJECT_ID/locations/$REGION/endpoints/$ENDPOINT_ID:predict"
```

## Model Storage Strategy

### Why This Approach?

1. **Separation of Concerns**: Model weights stored in GCS, application code in container
2. **Faster Deployments**: Container builds are faster without 12GB model files
3. **Version Management**: Easy to update models without rebuilding containers
4. **Cost Efficiency**: GCS is cheaper for large file storage than container registries

### Storage Structure in GCS:
```
gs://your-bucket/model-weights/
├── blobs/
│   ├── 93c6f48ec95c0e36e681fb1c200754b9e39b9d7603ebdee88580429b526a86b2  # 4.9GB
│   ├── d9a7c7adf0142010ea7fb2d6d60b2698b86f36847d00d0afa4170c3a9fb66a9c  # 4.9GB
│   ├── c4c9f1d21524ad189e63230a62a62997c52205f9ce3099948c7fc3d27385d0dc  # 2.6GB
│   └── ... (other model files)
└── snapshots/
    └── 454c20e1748888800f8e4b3da45125f55482d967/
        └── (symlinks to blobs)
```

## Cost Optimization Tips

1. **Use Preemptible/Spot Instances**: Add `--machine-type=n1-standard-4-preemptible`
2. **Right-size Resources**: Start with smaller machines and scale up if needed
3. **Set Auto-scaling**: Configure min/max replicas based on traffic
4. **Monitor Usage**: Use Cloud Monitoring to track resource utilization

## Troubleshooting

### Common Issues:

1. **Model download fails**:
   - Check GCS bucket permissions
   - Verify MODEL_BUCKET_NAME environment variable

2. **GPU not available**:
   - Ensure accelerator type is supported in your region
   - Check Vertex AI GPU quotas

3. **Health check failures**:
   - Increase initialDelaySeconds in health probe
   - Check model loading time

4. **Out of memory**:
   - Increase memory limits in deployment
   - Consider using larger machine types

### Useful Commands:

```bash
# Check deployment status
gcloud ai endpoints describe $ENDPOINT_ID --region=$REGION

# View logs
gcloud logging read "resource.type=vertex_ai_endpoint" --limit=50

# Update deployment
gcloud ai endpoints undeploy-model $ENDPOINT_ID --deployed-model-id=$DEPLOYED_MODEL_ID --region=$REGION
# Then redeploy with new configuration
```

## Security Considerations

1. **IAM Roles**: Use least-privilege principles
2. **VPC**: Deploy in private VPC for additional security
3. **API Keys**: Store sensitive keys in Secret Manager
4. **Network**: Configure firewall rules appropriately

## Production Readiness Checklist

- [ ] Model weights successfully uploaded to GCS
- [ ] Docker image built and pushed to Artifact Registry  
- [ ] Model deployed to Vertex AI endpoint
- [ ] Health checks passing
- [ ] Monitoring and alerting configured
- [ ] Auto-scaling tested
- [ ] Load testing completed
- [ ] Backup and disaster recovery plan in place
- [ ] Security review completed
- [ ] Documentation updated 