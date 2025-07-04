#!/bin/bash

# Vertex AI Deployment Script with Full Visibility
set -e  # Exit on any error
set -x  # Print each command before executing (verbose mode)

# Configuration - Update these for your project
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

# Simple logging (avoiding tee to prevent disk space issues)
echo "Deployment started at $(date)" > deployment.log

echo -e "${GREEN}=== Vertex AI Flask Deployment (Full Visibility Mode) ===${NC}"
echo -e "${BLUE}Timestamp: $(date)${NC}"
echo -e "${BLUE}Project: ${PROJECT_ID}${NC}"
echo -e "${BLUE}Region: ${REGION}${NC}"
echo -e "${PURPLE}Logging to: deployment.log${NC}"
echo ""

# Function to execute commands with full visibility
execute_step() {
    local step_name="$1"
    local command="$2"
    
    echo -e "${YELLOW}===========================================${NC}"
    echo -e "${YELLOW}STEP: $step_name${NC}"
    echo -e "${YELLOW}COMMAND: $command${NC}"
    echo -e "${YELLOW}TIME: $(date)${NC}"
    echo -e "${YELLOW}===========================================${NC}"
    
    # Execute the command and capture exit code
    set +e  # Don't exit on error temporarily
    eval "$command"
    local exit_code=$?
    set -e  # Re-enable exit on error
    
    if [ $exit_code -eq 0 ]; then
        echo -e "${GREEN}✅ SUCCESS: $step_name${NC}"
        echo ""
    else
        echo -e "${RED}❌ FAILED: $step_name (Exit Code: $exit_code)${NC}"
        echo -e "${RED}Command that failed: $command${NC}"
        echo -e "${RED}Check deployment.log for full details${NC}"
        exit $exit_code
    fi
}

# Function for manual checks
check_prerequisites() {
    echo -e "${YELLOW}🔍 CHECKING PREREQUISITES${NC}"
    
    echo "Checking gcloud installation..."
    which gcloud || (echo -e "${RED}❌ gcloud not found${NC}" && exit 1)
    
    echo "Checking docker installation..."  
    which docker || (echo -e "${RED}❌ docker not found${NC}" && exit 1)
    
    echo "Checking required files..."
    ls -la Dockerfile requirements.txt server.py || (echo -e "${RED}❌ Missing required files${NC}" && exit 1)
    
    echo "Checking current gcloud configuration..."
    gcloud config list
    
    echo -e "${GREEN}✅ All prerequisites check passed${NC}"
    echo ""
}

# Run prerequisites check
check_prerequisites

# Set up image URI
IMAGE_URI="$REGION-docker.pkg.dev/$PROJECT_ID/$REPOSITORY/$IMAGE_NAME:latest"
echo -e "${BLUE}Target Image URI: ${IMAGE_URI}${NC}"
echo ""

# Step 1: Enable required APIs
execute_step "Enable Artifact Registry API" \
    "gcloud services enable artifactregistry.googleapis.com --project=$PROJECT_ID"

execute_step "Enable AI Platform API" \
    "gcloud services enable aiplatform.googleapis.com --project=$PROJECT_ID"

# Step 2: Create Artifact Registry repository
execute_step "Create Artifact Registry Repository" \
    "gcloud artifacts repositories create $REPOSITORY --repository-format=docker --location=$REGION --project=$PROJECT_ID || echo 'Repository already exists'"

execute_step "Configure Docker Authentication" \
    "gcloud auth configure-docker $REGION-docker.pkg.dev"

# Step 3: Build Docker image locally
execute_step "Build Docker Image Locally" \
    "docker build -t $IMAGE_URI . --no-cache"

# Step 4: Push to Artifact Registry  
execute_step "Push Image to Artifact Registry" \
    "docker push $IMAGE_URI"

# Step 5: Upload model to Vertex AI
execute_step "Upload Model to Vertex AI" \
    "gcloud ai models upload --region=$REGION --display-name=$MODEL_NAME --container-image-uri=$IMAGE_URI --container-ports=8080 --container-health-route=/health --container-predict-route=/predict --project=$PROJECT_ID"

# Step 6: Check/Create endpoint
echo -e "${YELLOW}===========================================${NC}"
echo -e "${YELLOW}STEP: Check/Create Endpoint${NC}"
echo -e "${YELLOW}TIME: $(date)${NC}"
echo -e "${YELLOW}===========================================${NC}"

ENDPOINT_ID=$(gcloud ai endpoints list --region=$REGION --project=$PROJECT_ID --filter="displayName:$ENDPOINT_NAME" --format="value(name)" | head -1)

if [ -z "$ENDPOINT_ID" ]; then
    echo -e "${BLUE}No existing endpoint found. Creating new endpoint...${NC}"
    execute_step "Create New Endpoint" \
        "gcloud ai endpoints create --display-name=$ENDPOINT_NAME --region=$REGION --project=$PROJECT_ID"
    
    ENDPOINT_ID=$(gcloud ai endpoints list --region=$REGION --project=$PROJECT_ID --filter="displayName:$ENDPOINT_NAME" --format="value(name)" | head -1)
    echo -e "${GREEN}✅ Created new endpoint: $ENDPOINT_ID${NC}"
else
    echo -e "${GREEN}✅ Using existing endpoint: $ENDPOINT_ID${NC}"
fi
echo ""

# Step 7: Get latest model and deploy
echo -e "${YELLOW}===========================================${NC}"
echo -e "${YELLOW}STEP: Get Latest Model ID${NC}"
echo -e "${YELLOW}TIME: $(date)${NC}"
echo -e "${YELLOW}===========================================${NC}"

MODEL_ID=$(gcloud ai models list --region=$REGION --project=$PROJECT_ID --filter="displayName:$MODEL_NAME" --format="value(name)" --sort-by="~createTime" | head -1)
echo -e "${BLUE}Latest Model ID: $MODEL_ID${NC}"
echo -e "${BLUE}Deploying to Endpoint: $ENDPOINT_ID${NC}"
echo ""

execute_step "Deploy Model to Endpoint (a2-highgpu-1g)" \
    "gcloud ai endpoints deploy-model $ENDPOINT_ID --region=$REGION --model=$MODEL_ID --display-name='$MODEL_NAME-deployment-$(date +%Y%m%d-%H%M%S)' --machine-type='a2-highgpu-1g' --min-replica-count=1 --max-replica-count=3 --traffic-split=0=100 --project=$PROJECT_ID"

echo -e "${GREEN}===========================================${NC}"
echo -e "${GREEN}🎉 DEPLOYMENT COMPLETED SUCCESSFULLY! 🎉${NC}"
echo -e "${GREEN}===========================================${NC}"
echo -e "${GREEN}Timestamp: $(date)${NC}"
echo -e "${BLUE}Endpoint ID: $ENDPOINT_ID${NC}"
echo -e "${BLUE}Model ID: $MODEL_ID${NC}"
echo -e "${BLUE}Image URI: $IMAGE_URI${NC}"
echo -e "${BLUE}Machine Type: a2-highgpu-1g (1 A100 GPU, 85GB RAM)${NC}"
echo -e "${PURPLE}Full deployment log saved to: deployment.log${NC}"
echo ""

echo -e "${YELLOW}🧪 TEST YOUR DEPLOYMENT:${NC}"
echo "gcloud ai endpoints predict $ENDPOINT_ID \\"
echo "  --region=$REGION \\"
echo "  --json-request='{\"instances\":[{\"text\":\"test\"}]}'"
echo ""

echo -e "${YELLOW}📊 MONITOR LOGS:${NC}"
echo "gcloud logging read 'resource.type=\"aiplatform.googleapis.com/Endpoint\"' --limit=50"
echo ""

echo -e "${YELLOW}🔍 VIEW DEPLOYMENT LOG:${NC}"
echo "tail -f deployment.log"
echo ""

echo -e "${YELLOW}📋 USEFUL COMMANDS:${NC}"
echo "# List endpoints:"
echo "gcloud ai endpoints list --region=$REGION --project=$PROJECT_ID"
echo ""
echo "# List models:"
echo "gcloud ai models list --region=$REGION --project=$PROJECT_ID"
echo ""
echo "# Check endpoint status:"
echo "gcloud ai endpoints describe $ENDPOINT_ID --region=$REGION --project=$PROJECT_ID" 