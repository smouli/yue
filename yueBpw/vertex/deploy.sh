#!/bin/bash

# YuE Vertex AI - Clean Build and Deployment Script
# This script ensures all build artifacts are cleaned and PyTorch versions are consistent

set -e  # Exit on any error
set -x  # Print each command (verbose mode)

# Configuration
PROJECT_ID="music-generation-prototype"
REGION="us-central1"
REPOSITORY="yue-models"
IMAGE_NAME="yue-flask-server"
MODEL_NAME="yue-flask-model"
ENDPOINT_NAME="yue-flask-endpoint"

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
RED='\033[0;31m'
PURPLE='\033[0;35m'
NC='\033[0m' # No Color

echo -e "${GREEN}=========================================${NC}"
echo -e "${GREEN}🚀 YUE CLEAN BUILD & DEPLOYMENT 🚀${NC}"
echo -e "${GREEN}=========================================${NC}"
echo -e "${BLUE}📅 Started: $(date '+%Y-%m-%d %H:%M:%S')${NC}"
echo -e "${BLUE}🐋 Using PyTorch 2.6.0 + CUDA 12.4 + cuDNN 9${NC}"
echo -e "${GREEN}=========================================${NC}"

# Function to log errors
log_error() {
    echo -e "${RED}❌ ERROR: $1${NC}"
    exit 1
}

# Function to log success
log_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

# Function to log info
log_info() {
    echo -e "${BLUE}ℹ️  $1${NC}"
}

# Function to log warnings
log_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

# Build timestamp for image tagging
BUILD_TIME=$(date '+%Y%m%d-%H%M%S')
IMAGE_TAG="pytorch2.6.0-cuda12.4-${BUILD_TIME}"

log_info "🔧 Configuration:"
log_info "   Project: ${PROJECT_ID}"
log_info "   Region: ${REGION}"
log_info "   Repository: ${REPOSITORY}"
log_info "   Image: ${IMAGE_NAME}:${IMAGE_TAG}"

# === STEP 1: ENVIRONMENT VALIDATION ===
echo -e "\n${PURPLE}🔍 STEP 1: Environment Validation${NC}"

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
    log_error "Docker is not running. Please start Docker."
fi
log_success "Docker is running"

# Check if gcloud is authenticated
if ! gcloud auth list --filter=status:ACTIVE --format="value(account)" | grep -q .; then
    log_error "gcloud is not authenticated. Run 'gcloud auth login'"
fi
log_success "gcloud is authenticated"

# Check if Docker is configured for GCR
if ! gcloud auth configure-docker ${REGION}-docker.pkg.dev --quiet; then
    log_error "Failed to configure Docker for Artifact Registry"
fi
log_success "Docker configured for Artifact Registry"

# === STEP 2: BUILD ARTIFACT CLEANUP ===
echo -e "\n${PURPLE}🧹 STEP 2: Build Artifact Cleanup${NC}"

# Show current Docker usage
log_info "Current Docker usage:"
docker system df

# Clean up old images and build cache
log_info "Cleaning Docker build cache and dangling images..."
docker system prune -f --volumes
docker builder prune -f

# Remove old YuE images
log_info "Removing old YuE images..."
docker images | grep -E "(yue|pytorch)" | awk '{print $3}' | head -10 | xargs -r docker rmi -f || true

# Clean Python cache
log_info "Cleaning Python cache..."
find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
find . -name "*.pyc" -delete 2>/dev/null || true

log_success "Build artifacts cleaned"

# === STEP 3: REQUIREMENTS VALIDATION ===
echo -e "\n${PURPLE}📋 STEP 3: Requirements Validation${NC}"

# Validate our Flask server requirements
log_info "Validating Flask server requirements..."
if [[ -f "requirements.txt" ]]; then
    log_success "Flask server requirements.txt found"
    
    # Check for essential Flask dependencies
    if grep -q "Flask" requirements.txt && grep -q "gunicorn" requirements.txt; then
        log_success "Essential Flask dependencies found"
    else
        log_warning "Missing essential Flask dependencies"
    fi
    
    # Check for GCS dependencies
    if grep -q "google-cloud-storage" requirements.txt; then
        log_success "GCS dependencies found"
    else
        log_warning "GCS dependencies not found"
    fi
else
    log_error "Flask server requirements.txt not found!"
fi

# Validate YuE requirements
log_info "Validating YuE requirements..."
if [[ -f "YuE-exllamav2/requirements.txt" ]]; then
    log_success "YuE requirements.txt found"
    
    # Check if YuE requirements specify PyTorch 2.6.0
    if grep -q "torch==2\.6\.0" YuE-exllamav2/requirements.txt; then
        log_success "YuE specifies PyTorch 2.6.0 - matches base image!"
    else
        log_warning "YuE doesn't specify PyTorch 2.6.0"
    fi
    
    # Check for ExllamaV2 wheels for PyTorch 2.6.0
    if grep -q "exllamav2.*torch2\.6\.0" YuE-exllamav2/requirements.txt; then
        log_success "YuE includes ExllamaV2 wheels for PyTorch 2.6.0!"
    else
        log_warning "YuE doesn't include ExllamaV2 wheels for PyTorch 2.6.0"
    fi
    
    # Check for Flash Attention wheels for PyTorch 2.6.0  
    if grep -q "flash-attn.*torch2\.6" YuE-exllamav2/requirements.txt; then
        log_success "YuE includes Flash Attention wheels for PyTorch 2.6.0!"
    else
        log_warning "YuE doesn't include Flash Attention wheels for PyTorch 2.6.0"
    fi
    
    # Check for CUDA 12.4 compatibility
    if grep -q "cu124" YuE-exllamav2/requirements.txt; then
        log_success "YuE includes CUDA 12.4 compatibility!"
    else
        log_warning "YuE doesn't specify CUDA 12.4"
    fi
else
    log_error "YuE requirements.txt not found at YuE-exllamav2/requirements.txt!"
fi

log_success "Requirements validation passed"

# === STEP 4: DOCKER IMAGE BUILD ===
echo -e "\n${PURPLE}🏗️  STEP 4: Docker Image Build${NC}"

# Build image with proper tags
FULL_IMAGE_NAME="${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPOSITORY}/${IMAGE_NAME}:${IMAGE_TAG}"
LATEST_IMAGE_NAME="${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPOSITORY}/${IMAGE_NAME}:latest"

log_info "Building Docker image..."
log_info "Image: ${FULL_IMAGE_NAME}"

# Build with build logs
docker build \
    --platform linux/amd64 \
    --tag ${FULL_IMAGE_NAME} \
    --tag ${LATEST_IMAGE_NAME} \
    --build-arg BUILDKIT_INLINE_CACHE=1 \
    . 2>&1 | tee "build_${BUILD_TIME}.log"

if [ ${PIPESTATUS[0]} -ne 0 ]; then
    log_error "Docker build failed. Check build_${BUILD_TIME}.log for details."
fi

log_success "Docker image built successfully"

# === STEP 5: IMAGE VERIFICATION ===
echo -e "\n${PURPLE}🧪 STEP 5: Image Verification${NC}"

log_info "Verifying Docker image..."

# Test that the image starts correctly
docker run --rm ${FULL_IMAGE_NAME} python3 -c "
import sys
print(f'Python: {sys.version}')

import torch
print(f'PyTorch: {torch.__version__}')
assert torch.__version__.startswith('2.6.'), f'Expected PyTorch 2.6.x, got {torch.__version__}'

import torchaudio  
print(f'TorchAudio: {torchaudio.__version__}')

print('CUDA Available:', torch.cuda.is_available())
print('CUDA Version:', torch.version.cuda)

try:
    import exllamav2
    print('✅ ExllamaV2 imported successfully')
except Exception as e:
    print(f'❌ ExllamaV2 import failed: {e}')
    sys.exit(1)

print('✅ All validations passed!')
"

if [ $? -ne 0 ]; then
    log_error "Image verification failed"
fi

log_success "Image verification passed"

# === STEP 6: PUSH TO ARTIFACT REGISTRY ===
echo -e "\n${PURPLE}☁️  STEP 6: Push to Artifact Registry${NC}"

log_info "Pushing to Artifact Registry..."

# Push both tags
docker push ${FULL_IMAGE_NAME}
docker push ${LATEST_IMAGE_NAME}

if [ $? -ne 0 ]; then
    log_error "Failed to push image to Artifact Registry"
fi

log_success "Image pushed to Artifact Registry"

# === STEP 7: VERTEX AI DEPLOYMENT ===
echo -e "\n${PURPLE}🎯 STEP 7: Vertex AI Deployment${NC}"

log_info "Deploying to Vertex AI..."

# Upload model
log_info "Uploading model to Vertex AI Model Registry..."
gcloud ai models upload \
    --region=${REGION} \
    --display-name=${MODEL_NAME} \
    --container-image-uri=${FULL_IMAGE_NAME} \
    --container-health-route=/health \
    --container-predict-route=/generate \
    --container-ports=8080 \
    --version-aliases=pytorch-2-6-0 \
    --quiet

if [ $? -ne 0 ]; then
    log_error "Failed to upload model to Vertex AI"
fi

log_success "Model uploaded to Vertex AI"

# Create or update endpoint
log_info "Creating/updating Vertex AI endpoint..."
if gcloud ai endpoints describe ${ENDPOINT_NAME} --region=${REGION} --quiet > /dev/null 2>&1; then
    log_info "Endpoint exists, updating..."
    
    # Get the latest model version
    MODEL_ID=$(gcloud ai models list --region=${REGION} --filter="displayName:${MODEL_NAME}" --format="value(name)" --limit=1)
    
    # Deploy to existing endpoint
    gcloud ai endpoints deploy-model ${ENDPOINT_NAME} \
        --region=${REGION} \
        --model=${MODEL_ID} \
        --display-name=${MODEL_NAME}-deployment \
        --machine-type=n1-standard-4 \
        --min-replica-count=1 \
        --max-replica-count=3 \
        --quiet
else
    log_info "Creating new endpoint..."
    
    # Create new endpoint
    gcloud ai endpoints create \
        --region=${REGION} \
        --display-name=${ENDPOINT_NAME} \
        --quiet
    
    # Get the model ID and deploy
    MODEL_ID=$(gcloud ai models list --region=${REGION} --filter="displayName:${MODEL_NAME}" --format="value(name)" --limit=1)
    
    gcloud ai endpoints deploy-model ${ENDPOINT_NAME} \
        --region=${REGION} \
        --model=${MODEL_ID} \
        --display-name=${MODEL_NAME}-deployment \
        --machine-type=n1-standard-4 \
        --min-replica-count=1 \
        --max-replica-count=3 \
        --quiet
fi

if [ $? -ne 0 ]; then
    log_error "Failed to deploy to Vertex AI endpoint"
fi

log_success "Deployed to Vertex AI endpoint"

# === STEP 8: CLEANUP & SUMMARY ===
echo -e "\n${PURPLE}🧹 STEP 8: Cleanup & Summary${NC}"

# Clean up local Docker images to save space
log_info "Cleaning up local Docker images..."
docker rmi ${FULL_IMAGE_NAME} ${LATEST_IMAGE_NAME} || true

# Show final status
echo -e "\n${GREEN}=========================================${NC}"
echo -e "${GREEN}🎉 DEPLOYMENT COMPLETED SUCCESSFULLY! 🎉${NC}"
echo -e "${GREEN}=========================================${NC}"
echo -e "${BLUE}📅 Completed: $(date '+%Y-%m-%d %H:%M:%S')${NC}"
echo -e "${BLUE}🏷️  Image Tag: ${IMAGE_TAG}${NC}"
echo -e "${BLUE}🌐 Endpoint: ${ENDPOINT_NAME}${NC}"
echo -e "${BLUE}📊 Model: ${MODEL_NAME}${NC}"
echo -e "${BLUE}🔧 PyTorch: 2.6.0 + CUDA 12.4${NC}"
echo -e "${GREEN}=========================================${NC}"

# Show endpoint information
log_info "Getting endpoint information..."
gcloud ai endpoints describe ${ENDPOINT_NAME} --region=${REGION} --format="yaml(displayName,deployedModels,createTime)"

echo -e "\n${GREEN}✅ Deployment ready! Your YuE model is now serving on Vertex AI.${NC}" 