#!/bin/bash

# Deploy secure YuE API to Cloud Run
set -e

PROJECT_ID="music-generation-prototype"
REGION="us-central1"
SERVICE_NAME="yue-music-secure-api"
API_SECRET="yue-secure-key-2025-$(date +%s)"

echo "🚀 Deploying YuE Secure API to Cloud Run..."
echo "📦 Service name: ${SERVICE_NAME}"
echo "🌍 Region: ${REGION}"
echo "📊 Project: ${PROJECT_ID}"
echo "🔐 API Secret: ${API_SECRET}"

# Build and deploy to Cloud Run
echo "🏗️ Building and deploying..."

# Rename files for Cloud Run auto-detection
cp secure_api_server.py main.py
cp secure_api_requirements.txt requirements.txt

gcloud run deploy ${SERVICE_NAME} \
  --source=. \
  --platform=managed \
  --region=${REGION} \
  --allow-unauthenticated \
  --port=8080 \
  --memory=512Mi \
  --cpu=1 \
  --timeout=300s \
  --max-instances=10 \
  --min-instances=0 \
  --concurrency=80 \
  --set-env-vars="API_SECRET=${API_SECRET}"

if [ $? -eq 0 ]; then
    echo "✅ Cloud Run service deployed successfully!"
    echo ""
    
    # Get the service URL
    SERVICE_URL=$(gcloud run services describe ${SERVICE_NAME} --region=${REGION} --format="value(status.url)")
    echo "🔗 Service URL: ${SERVICE_URL}"
    echo ""
    
    echo "📱 Update your iOS app with:"
    echo "  private let cloudFunctionURL = \"${SERVICE_URL}/generate\""
    echo "  private let apiSecret = \"${API_SECRET}\""
    echo ""
    
    echo "🧪 Test endpoints:"
    echo "  Health: curl ${SERVICE_URL}/health"
    echo "  API Info: curl ${SERVICE_URL}/"
    echo ""
    
    echo "🔧 Secure request example:"
    echo "TIMESTAMP=\$(date +%s)"
    echo "SIGNATURE=\$(echo -n '{\"genre\":\"pop\",\"lyrics\":\"test\",\"song_name\":\"test\",\"user_id\":\"test\"}'\$TIMESTAMP | openssl dgst -sha256 -hmac \"${API_SECRET}\" -binary | xxd -p -c 256)"
    echo ""
    echo "curl -X POST ${SERVICE_URL}/generate \\"
    echo "  -H 'Content-Type: application/json' \\"
    echo "  -H 'X-API-Signature: \$SIGNATURE' \\"
    echo "  -H 'X-Timestamp: \$TIMESTAMP' \\"
    echo "  -d '{\"user_id\":\"test\",\"song_name\":\"test\",\"genre\":\"pop\",\"lyrics\":\"test\"}'"
    
else
    echo "❌ Cloud Run deployment failed"
    exit 1
fi 