#!/bin/bash

# YuE Vertex AI Container Entrypoint
# Downloads models from Hugging Face at startup, then starts the server

set -e  # Exit on any error

echo "=========================================="
echo "🚀 YUE VERTEX AI CONTAINER STARTUP"
echo "=========================================="
echo "📅 Started at: $(date)"
echo "🐋 Container initialization beginning..."

# Set environment variables
export PYTHONUNBUFFERED=1
export PYTHONDONTWRITEBYTECODE=1

# Function to log with timestamps
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1"
}

log "🔧 Setting up environment..."

# Check if we're in the right directory
if [ ! -d "/app/YuE-exllamav2" ]; then
    log "❌ YuE directory not found at /app/YuE-exllamav2"
    exit 1
fi

log "✅ YuE directory found"

# Check if models already exist (for container restarts)
MODEL_DIR="/app/YuE-exllamav2/src/yue/models"
STAGE1_MODEL="$MODEL_DIR/YuE-s1-7B-anneal-en-cot"
STAGE2_MODEL="$MODEL_DIR/YuE-s2-1B-general"

if [ -d "$STAGE1_MODEL" ] && [ -d "$STAGE2_MODEL" ]; then
    log "✅ Models already exist - skipping download"
    log "   Stage 1: $STAGE1_MODEL"
    log "   Stage 2: $STAGE2_MODEL"
else
    log "📥 Models not found - downloading from Hugging Face..."
    log "   This may take 5-10 minutes depending on network speed"
    
    # Copy the download script to a temporary location and run it
    cd /app
    
    # Use the existing download script from the scripts directory
    if [ -f "/app/yueBpw/scripts/download_models_hf.py" ]; then
        log "🔧 Using existing download script from yueBpw/scripts/"
        python3 /app/yueBpw/scripts/download_models_hf.py
    elif [ -f "/app/download_models_hf.py" ]; then
        log "🔧 Using download script from app root"
        python3 /app/download_models_hf.py
    else
        log "❌ Model download script not found!"
        log "   Expected: /app/yueBpw/scripts/download_models_hf.py or /app/download_models_hf.py"
        exit 1
    fi
    
    if [ $? -eq 0 ]; then
        log "✅ Model download completed successfully!"
    else
        log "❌ Model download failed!"
        exit 1
    fi
fi

# Verify models are properly set up
log "🔍 Verifying model setup..."

if [ ! -d "$STAGE1_MODEL" ]; then
    log "❌ Stage 1 model directory not found: $STAGE1_MODEL"
    exit 1
fi

if [ ! -d "$STAGE2_MODEL" ]; then
    log "❌ Stage 2 model directory not found: $STAGE2_MODEL"
    exit 1
fi

# Count files in each model directory
STAGE1_FILES=$(find "$STAGE1_MODEL" -type f | wc -l)
STAGE2_FILES=$(find "$STAGE2_MODEL" -type f | wc -l)

log "✅ Model verification successful:"
log "   Stage 1: $STAGE1_FILES files in $STAGE1_MODEL"
log "   Stage 2: $STAGE2_FILES files in $STAGE2_MODEL"

# Check GPU availability
log "🔧 Checking GPU availability..."
python3 -c "
import torch
print(f'PyTorch: {torch.__version__}')
print(f'CUDA available: {torch.cuda.is_available()}')
if torch.cuda.is_available():
    print(f'GPU device: {torch.cuda.get_device_name(0)}')
    print(f'GPU memory: {torch.cuda.get_device_properties(0).total_memory / 1024**3:.1f} GB')
else:
    print('No GPU detected')
"

# Test model imports
log "🧪 Testing YuE imports..."
cd /app
python3 -c "
import sys
sys.path.insert(0, '/app/YuE-exllamav2/src')
try:
    import yue
    print('✅ YuE imports successful')
except Exception as e:
    print(f'⚠️ YuE import issue: {e}')
    print('Will attempt to load during inference')
"

log "🎯 Container initialization completed successfully!"
log "🚀 Starting production server with Gunicorn..."
echo "=========================================="

# Start the production server with Gunicorn
cd /app
exec gunicorn --bind 0.0.0.0:8080 \
              --workers 1 \
              --threads 8 \
              --timeout 0 \
              --keep-alive 2 \
              --max-requests 1000 \
              --max-requests-jitter 100 \
              --access-logfile - \
              --error-logfile - \
              server:app 