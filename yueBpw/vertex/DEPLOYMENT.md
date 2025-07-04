# Vertex AI Deployment with Runtime Model Download

This deployment setup downloads YuE model weights at runtime from GCS, avoiding the need to bake large model files into the Docker image.

## Files Overview

- `entrypoint.py` - Downloads models from `AIP_STORAGE_URI` and starts the server
- `Dockerfile` - Lightweight Python 3.10 container without model weights
- `server.py` - Flask server (existing, Vertex AI compliant)
- `requirements.txt` - Python dependencies

## Prerequisites

1. **Upload model weights to GCS:**
   ```bash
   # Upload your YuE models to GCS
   gsutil -m cp -r ./YuE-s1-7B-anneal-en-cot gs://your-bucket/models/
   gsutil -m cp -r ./YuE-s2-1B-general gs://your-bucket/models/
   ```

2. **Verify GCS structure:**
   ```
   gs://your-bucket/models/
   ├── YuE-s1-7B-anneal-en-cot/
   │   ├── config.json
   │   ├── model files...
   └── YuE-s2-1B-general/
       ├── config.json
       ├── model files...
   ```

## Deployment Steps

### 1. Build and Push Container

```bash
# Set your project variables
PROJECT_ID="your-project-id"
REGION="us-central1"
REPOSITORY="yue-models"
IMAGE_NAME="yue-runtime-server"

# Create Artifact Registry repository
gcloud artifacts repositories create $REPOSITORY \
    --repository-format=docker \
    --location=$REGION \
    --project=$PROJECT_ID

# Configure Docker auth
gcloud auth configure-docker $REGION-docker.pkg.dev

# Build using the Dockerfile
docker build -t $REGION-docker.pkg.dev/$PROJECT_ID/$REPOSITORY/$IMAGE_NAME:latest .

# Push to registry
docker push $REGION-docker.pkg.dev/$PROJECT_ID/$REPOSITORY/$IMAGE_NAME:latest
```

### 2. Upload Model to Vertex AI

```bash
# Upload model with storage URI
gcloud ai models upload \
    --region=$REGION \
    --display-name="yue-runtime-model" \
    --container-image-uri=$REGION-docker.pkg.dev/$PROJECT_ID/$REPOSITORY/$IMAGE_NAME:latest \
    --container-ports=8080 \
    --container-health-route=/health \
    --container-predict-route=/predict \
    --artifact-uri=gs://your-bucket/models \
    --project=$PROJECT_ID
```

### 3. Deploy to Endpoint

```bash
# Create endpoint
gcloud ai endpoints create \
    --display-name="yue-runtime-endpoint" \
    --region=$REGION \
    --project=$PROJECT_ID

# Get endpoint ID
ENDPOINT_ID=$(gcloud ai endpoints list \
    --region=$REGION \
    --project=$PROJECT_ID \
    --filter="displayName:yue-runtime-endpoint" \
    --format="value(name)")

# Get model ID
MODEL_ID=$(gcloud ai models list \
    --region=$REGION \
    --project=$PROJECT_ID \
    --filter="displayName:yue-runtime-model" \
    --format="value(name)" \
    --sort-by="~createTime" | head -1)

# Deploy model to endpoint
gcloud ai endpoints deploy-model $ENDPOINT_ID \
    --region=$REGION \
    --model=$MODEL_ID \
    --display-name="yue-runtime-deployment" \
    --machine-type="a2-highgpu-1g" \
    --min-replica-count=1 \
    --max-replica-count=3 \
    --traffic-split=0=100 \
    --project=$PROJECT_ID
```

## How It Works

1. **Container Startup:** Vertex AI starts the container and sets `AIP_STORAGE_URI` to your model artifact URI
2. **Model Download:** `entrypoint.py` downloads models from GCS to `/workspace/model/`
3. **Symlink Setup:** Creates symlinks from `/app/YuE-exllamav2/src/yue/models/` to downloaded models
4. **Server Start:** Launches `server.py` which finds models in expected locations

## Environment Variables

The container automatically receives these from Vertex AI:
- `AIP_STORAGE_URI` - Points to your GCS model location
- `AIP_HTTP_PORT` - Port to bind server (default: 8080)

## Testing

```bash
# Test prediction
gcloud ai endpoints predict $ENDPOINT_ID \
    --region=$REGION \
    --json-request='{
        "instances": [{
            "user_id": "test_user",
            "song_name": "Test Song",
            "lyrics": "Test lyrics here",
            "genre": "pop"
        }]
    }'

# Check status
gcloud ai endpoints predict $ENDPOINT_ID \
    --region=$REGION \
    --json-request='{
        "instances": [{
            "status_request_id": "your-request-id"
        }]
    }'
```

## Monitoring

Check logs for model download and startup:
```bash
gcloud logging read 'resource.type="aiplatform.googleapis.com/Endpoint"' \
    --limit=50 \
    --format="table(timestamp,textPayload)"
```

## Benefits

- ✅ **Smaller Images:** No 16GB+ model weights in container
- ✅ **Faster Builds:** Docker build completes in minutes, not hours
- ✅ **Flexible Models:** Update models without rebuilding container
- ✅ **Better Caching:** Container layers cache effectively
- ✅ **Storage Efficiency:** Models stored once in GCS, not in every image

## Troubleshooting

- **Model download fails:** Check `AIP_STORAGE_URI` and GCS permissions
- **Symlinks fail:** Verify model directory structure in GCS
- **Server won't start:** Check that all expected models are present
- **Health check fails:** Ensure models are fully downloaded before server starts 