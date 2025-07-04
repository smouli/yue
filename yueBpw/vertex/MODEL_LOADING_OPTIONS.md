# YuE Model Loading Architecture Options

## 🎯 **Overview**

YuE supports two model loading strategies, each with different trade-offs:

1. **On-Demand Loading** (Recommended for flexibility)
2. **Startup Loading** (Recommended for production)

---

## 🚀 **Option 1: On-Demand Model Loading** 

### ✅ **Advantages**
- **⚡ Fast Startup**: Server starts in ~30 seconds
- **🔄 No Restart Required**: Can download/update models while running
- **💡 Development Friendly**: Easy to test different models
- **🧪 Debugging**: Manual trigger via `/download-models` endpoint

### ⚠️ **Trade-offs** 
- **⏳ First Request Delay**: 5-10 minutes for initial model download
- **🔀 Complex State**: Must handle concurrent requests during download
- **📊 Status Monitoring**: Need to check `/models/status` for readiness

### 🏗️ **Architecture**
```
Container Start → Server Ready (30s) → First Request → Download Models (5-10min) → Process Request
                                    ↓
                                Health Check ✅ (immediately)
```

### 🚀 **Deployment**
```bash
./deploy_on_demand.sh
```

### 📡 **API Endpoints**
- `GET /health` - Always healthy (server running)
- `GET /models/status` - Check model loading status
- `POST /download-models` - Manually trigger download
- `POST /predict` - Main inference (triggers download if needed)

### 💻 **Usage Example**
```bash
# 1. Deploy (fast startup)
./deploy_on_demand.sh

# 2. Server is immediately ready
curl https://ENDPOINT/health
# → {"status": "healthy", "models": {"status": "not_loaded"}}

# 3. Pre-load models (optional)
curl -X POST https://ENDPOINT/download-models
# → {"status": "success", "message": "Models downloaded..."}

# 4. Or let first request trigger download
curl -X POST https://ENDPOINT/predict -d '{"instances": [...]}'
# → First request: 5-10 min delay
# → Subsequent requests: Immediate
```

---

## 🎯 **Option 2: Startup Model Loading**

### ✅ **Advantages**
- **🎯 Predictable**: Models always ready when health check passes
- **⚡ Fast Inference**: No download delays during operation
- **🏭 Production Ready**: Consistent response times
- **🔒 Simple State**: Models loaded or not loaded

### ⚠️ **Trade-offs**
- **⏳ Slow Startup**: 5-10 minutes container initialization
- **🔄 Restart Required**: To update models
- **💾 Container Size**: Models stored in container

### 🏗️ **Architecture** 
```
Container Start → Download Models (5-10min) → Server Ready → Process Requests
                                            ↓
                                        Health Check ✅ (after download)
```

### 🚀 **Deployment**
```bash
./deploy_with_entrypoint.sh
```

### 📡 **API Endpoints**
- `GET /health` - Healthy only after models loaded
- `POST /predict` - Always ready (no download delay)

### 💻 **Usage Example**
```bash
# 1. Deploy (slow startup)
./deploy_with_entrypoint.sh

# 2. Wait for container to be ready (5-10 minutes)
curl https://ENDPOINT/health  
# → {"status": "healthy", "models": {"status": "ready"}}

# 3. All requests are immediate
curl -X POST https://ENDPOINT/predict -d '{"instances": [...]}'
# → Always fast response
```

---

## 📊 **Comparison Table**

| Feature | On-Demand Loading | Startup Loading |
|---------|------------------|-----------------|
| **Startup Time** | ~30 seconds | 5-10 minutes |
| **First Request** | 5-10 min delay | Immediate |
| **Health Check** | Always passes | Passes after download |
| **Model Updates** | No restart needed | Restart required |
| **Development** | Very flexible | Less flexible |
| **Production** | Good with pre-loading | Excellent |
| **State Complexity** | Higher | Lower |
| **Container Size** | Smaller | Larger |

---

## 🎯 **Recommendations**

### **For Development/Testing** 
```bash
./deploy_on_demand.sh
```
- Fast iteration cycles
- Easy model experimentation  
- Manual control via endpoints

### **For Production**
```bash
./deploy_with_entrypoint.sh  
```
- Predictable performance
- No user-facing delays
- Simple monitoring

### **Hybrid Approach**
Use on-demand in development, startup loading in production:

```bash
# Development
./deploy_on_demand.sh

# Pre-load for testing
curl -X POST https://ENDPOINT/download-models

# Production  
./deploy_with_entrypoint.sh
```

---

## 🔧 **Current Implementation**

The server has been updated to support **on-demand loading by default**:

- **Thread-safe model downloading** with proper locking
- **Concurrent request handling** during download
- **Status monitoring endpoints** for observability  
- **Manual download triggers** for pre-loading
- **Graceful error handling** for failed downloads

### **Key Files**
- `server.py` - Updated with on-demand loading logic
- `deploy_on_demand.sh` - On-demand deployment script
- `deploy_with_entrypoint.sh` - Startup loading deployment script
- `Dockerfile` - Now supports both approaches

### **Model Loading Flow**
```python
# In server.py
MODELS_LOADED = threading.Event()      # Thread-safe ready flag
MODEL_LOAD_LOCK = threading.Lock()     # Prevent concurrent downloads  
MODELS_DOWNLOADING = threading.Event() # Track download progress

def ensure_models_available():
    # Thread-safe model loading with proper state management
    pass
```

---

## 🎉 **Quick Start**

**Try on-demand loading now:**

```bash
cd yueBpw/vertex
./deploy_on_demand.sh
```

Server will be ready in ~30 seconds! 🚀 