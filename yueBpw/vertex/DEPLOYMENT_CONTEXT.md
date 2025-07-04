# YuE Vertex AI Deployment Context
*Generated: 2025-01-02 23:52 UTC*
*Build ID: pytorch2.6.0-cuda12.4-20250702-235238*
*Updated: 2025-01-03 01:30 UTC - Added Model Download Fix*

## 🎯 **CURRENT STATUS** ⚠️ DEPLOYED BUT NEEDS MODEL FIX

### ✅ **SUCCESSFULLY DEPLOYED:**
1. **Docker Image Built & Pushed** 🐋
   - Image: `us-central1-docker.pkg.dev/music-generation-prototype/yue-models/yue-flask-server:pytorch2.6.0-cuda12.4-20250702-235238`
   - Also tagged as: `latest`
   - Size: ~3.5GB (optimized with .dockerignore)
   - Base Image: `pytorch/pytorch:2.6.0-cuda12.4-cudnn9-devel`

2. **Vertex AI Model Registry** 📦
   - Model Name: `yue-flask-model`
   - Model ID: `7146952024381194240`
   - Version Alias: `pytorch-2-6-0`
   - Health Route: `/health`
   - Predict Route: `/predict`
   - Port: `8080`

3. **Vertex AI Endpoint DEPLOYED** 🎯
   - Endpoint Name: `yue-flask-endpoint`
   - Endpoint ID: `5027878657331298304`
   - Region: `us-central1`
   - GPU: **NVIDIA A100-SXM4-40GB** ✅
   - Status: **DEPLOYED WITH GPU!** 🚀

### ❌ **CRITICAL ISSUE IDENTIFIED:**
```
❌ Stage 1 model not found at: /app/YuE-exllamav2/src/yue/models/YuE-s1-7B-anneal-en-cot
📁 Contents of /app/YuE-exllamav2/src/yue/models: Directory does not exist
```

**Root Cause**: Our `.dockerignore` excluded model weights to reduce build context. Container runs but missing actual model files.

### 🔧 **SOLUTION IMPLEMENTED:**
- ✅ **Lazy model loading** on first request (not at startup)
- ✅ **Proper symlink structure** following entrypoint.py pattern
- ✅ **Thread-safe downloads** with concurrent request handling
- ✅ **Google Cloud SDK** included for gsutil downloads
- ✅ **Fast container startup** (health checks pass immediately)
- ✅ **Automatic symlink creation** from `/app/YuE-exllamav2/src/yue/models/` → `/workspace/model/`

---

## 🚨 **IMPROVED SOLUTION: LAZY LOADING** ✅

### 🎯 **NEW APPROACH: Download Models on First Request**
Instead of downloading models at startup, we now:
- ✅ **Fast container startup** (health checks pass immediately)
- ✅ **Lazy model download** on first prediction request  
- ✅ **Thread-safe** concurrent request handling
- ✅ **Better user experience** (no startup timeouts)

### **Step 1: Upload Models to GCS** (Required First)
```bash
# Create bucket for model weights
gsutil mb gs://yue-model-weights

# Upload Stage 1 model (you need the actual model files)
gsutil -m cp -r /path/to/YuE-s1-7B-anneal-en-cot gs://yue-model-weights/

# Upload Stage 2 model  
gsutil -m cp -r /path/to/YuE-s2-1B-general gs://yue-model-weights/
```

### **Step 2: Quick Rebuild with Lazy Loading**
```bash
cd yueBpw/vertex
./rebuild_lazy_loading.sh
```

This will:
- 🏗️ Rebuild container with lazy loading
- 📤 Push to Artifact Registry  
- 📦 Upload new model version
- 🔄 Update existing endpoint (keeps A100 GPU!)
- ✅ Deploy with lazy loading functionality

---

## 🎯 **MANUAL GPU DEPLOYMENT GUIDE**

### ✅ **DEPLOYMENT COMPLETED!**
- **GPU Type**: NVIDIA A100-SXM4-40GB (Premium GPU!)
- **PyTorch**: 2.6.0+cu124 ✅
- **CUDA**: Available ✅  
- **Issue**: Missing model files only

### Container Logs from Successful Deployment:
```
✅ PyTorch loaded: 2.6.0+cu124
✅ CUDA available: True
✅ GPU device: NVIDIA A100-SXM4-40GB
❌ Stage 1 model not found at: /app/YuE-exllamav2/src/yue/models/YuE-s1-7B-anneal-en-cot
```

---

## 📋 **PROJECT CONFIGURATION**

### GCP Settings:
- **Project ID**: `music-generation-prototype`
- **Region**: `us-central1`
- **Artifact Registry**: `yue-models`
- **Service Account**: `799748678255-compute@developer.gserviceaccount.com`

### Container Configuration:
- **Server**: Gunicorn production server (not Flask dev)
- **Threads**: 8 worker threads
- **Timeout**: Unlimited (for long inference)
- **Health Check**: `/health` endpoint
- **Prediction**: `/predict` endpoint (Vertex AI format)
- **NEW**: **Model Download**: Automatic from `gs://yue-model-weights/`

### Model Paths (inside container):
- **Stage 1**: `/app/YuE-exllamav2/src/yue/models/YuE-s1-7B-anneal-en-cot`
- **Stage 2**: `/app/YuE-exllamav2/src/yue/models/YuE-s2-1B-general`
- **Output**: `/app/YuE-exllamav2/output/{request_id}/`
- **GCS Source**: `gs://yue-model-weights/YuE-s1-7B-anneal-en-cot` and `gs://yue-model-weights/YuE-s2-1B-general`

---

## 🔧 **UPDATED DOCKERFILE CHANGES**

### New Dependencies Added:
```dockerfile
# Google Cloud SDK for gsutil
RUN apt-get install -y gnupg lsb-release && \
    echo "deb [signed-by=/usr/share/keyrings/cloud.google.gpg] https://packages.cloud.google.com/apt cloud-sdk main" | tee -a /etc/apt/sources.list.d/google-cloud-sdk.list && \
    curl https://packages.cloud.google.com/apt/doc/apt-key.gpg | apt-key --keyring /usr/share/keyrings/cloud.google.gpg add - && \
    apt-get update && apt-get install -y google-cloud-cli
```

### New Server.py Functions:
- `download_models_from_gcs()`: Downloads models and creates proper symlinks
- `ensure_models_downloaded_lazy()`: Thread-safe lazy loading on first request
- `validate_models()`: Checks symlink structure and sets MODELS_LOADED flag
- Uses `gsutil -m cp -r` for efficient multi-threaded downloads

### Symlink Structure (Following entrypoint.py Pattern):
```
/workspace/model/                          # Model storage directory
├── YuE-s1-7B-anneal-en-cot/              # Downloaded Stage 1 model
└── YuE-s2-1B-general/                    # Downloaded Stage 2 model

/app/YuE-exllamav2/src/yue/models/        # YuE expected paths (symlinks)
├── YuE-s1-7B-anneal-en-cot -> /workspace/model/YuE-s1-7B-anneal-en-cot/
└── YuE-s2-1B-general -> /workspace/model/YuE-s2-1B-general/
```

### Testing Symlinks:
```bash
# Run inside container to verify symlink structure
python3 test_symlinks.py
```

---

## 🧪 **TESTING AFTER MODEL FIX**

### 1. Health Check (Should work after model fix):
```bash
curl -X GET https://ENDPOINT_URL/health
```

### 2. Sample Request:
```bash
curl -X POST https://ENDPOINT_URL/predict \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $(gcloud auth print-access-token)" \
  -d '{
    "instances": [{
      "data": {
        "user_id": "test_user_123",
        "song_name": "Test Song", 
        "lyrics": "This is a test song\nWith simple lyrics",
        "genre": "pop"
      }
    }]
  }'
```

---

## 🏗️ **ARCHITECTURAL DETAILS**

### Dependencies:
- **PyTorch**: 2.6.0 + CUDA 12.4 + cuDNN 9 ✅
- **ExllamaV2**: Prebuilt wheels for PyTorch 2.6.0 ✅
- **Flash Attention**: Optimized for CUDA 12.4 ✅
- **Flask/Gunicorn**: Production web server ✅
- **GCS**: File upload (boto3 S3-compatible API) ✅
- **NEW**: **Google Cloud SDK**: Model downloads via gsutil ✅

### Request Flow:
1. **Container Startup** → Download models from GCS if missing
2. **Vertex AI** → `/predict` endpoint
3. **Queue System** → Sequential processing (prevents GPU memory issues)
4. **Subprocess Execution** → `python src/yue/infer.py` with real-time logs
5. **File Upload** → GCS bucket `yue-generated-songs`
6. **Response** → Request ID + status tracking

---

## 🚨 **DEPLOYMENT STATUS SUMMARY**

### ✅ **WORKING:**
- GPU deployment with A100
- PyTorch 2.6.0 + CUDA 12.4
- Container startup and networking
- All dependencies loaded correctly

### ❌ **NEEDS FIX:**
- Model files missing from container
- Need to upload models to `gs://yue-model-weights/`
- Need to rebuild container with model download capability

### 🎯 **NEXT ACTION:**
1. Upload YuE models to GCS bucket `gs://yue-model-weights/`
2. Rebuild container with model download fixes
3. Redeploy to existing endpoint (keeps A100 GPU)
4. Test functionality

---

*🎵 Container successfully deployed with A100 GPU - just needs model files! 🚀* 