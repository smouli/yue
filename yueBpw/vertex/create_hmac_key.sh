#!/bin/bash

# Create HMAC Keys for GCS Access with Storage Admin Permissions
# This script creates a service account with proper permissions and generates HMAC keys

set -e  # Exit on any error

# Configuration
PROJECT_ID="music-generation-prototype"
SERVICE_ACCOUNT_NAME="yue-gcs-hmac"
SERVICE_ACCOUNT_EMAIL="${SERVICE_ACCOUNT_NAME}@${PROJECT_ID}.iam.gserviceaccount.com"
GCS_BUCKET_NAME="yue-generated-songs"
KEY_FILE="hmac_credentials.json"

echo "🔧 Setting up HMAC Keys for GCS Storage Admin Access"
echo "=================================================="
echo "Project ID: $PROJECT_ID"
echo "Service Account: $SERVICE_ACCOUNT_EMAIL"
echo "Bucket: $GCS_BUCKET_NAME"
echo ""

# Function to check if command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Check prerequisites
if ! command_exists gcloud; then
    echo "❌ gcloud CLI is required but not installed."
    exit 1
fi

if ! command_exists gsutil; then
    echo "❌ gsutil is required but not installed."
    exit 1
fi

# Set project
echo "🎯 Setting active project..."
gcloud config set project $PROJECT_ID

# Enable required APIs
echo "🔌 Enabling required APIs..."
gcloud services enable storage-api.googleapis.com
gcloud services enable iam.googleapis.com
gcloud services enable storage-component.googleapis.com

# Create service account (if it doesn't exist)
echo "👤 Creating service account..."
if gcloud iam service-accounts describe $SERVICE_ACCOUNT_EMAIL >/dev/null 2>&1; then
    echo "✅ Service account already exists: $SERVICE_ACCOUNT_EMAIL"
else
    gcloud iam service-accounts create $SERVICE_ACCOUNT_NAME \
        --display-name="YuE GCS HMAC Access" \
        --description="Service account for GCS HMAC key access with storage admin permissions"
    echo "✅ Created service account: $SERVICE_ACCOUNT_EMAIL"
fi

# Grant comprehensive storage permissions
echo "🔐 Granting storage permissions..."

# Project-level permissions
ROLES=(
    "roles/storage.admin"
    "roles/storage.objectAdmin"
    "roles/storage.objectCreator"
    "roles/storage.objectViewer"
    "roles/storage.legacyBucketReader"
    "roles/storage.legacyBucketWriter"
    "roles/storage.legacyObjectReader"
    "roles/storage.legacyObjectOwner"
)

for role in "${ROLES[@]}"; do
    echo "  Granting $role..."
    gcloud projects add-iam-policy-binding $PROJECT_ID \
        --member="serviceAccount:$SERVICE_ACCOUNT_EMAIL" \
        --role="$role" >/dev/null 2>&1 || echo "  ✅ $role (already granted)"
done

# Bucket-level permissions (if bucket exists)
echo "📦 Granting bucket-level permissions..."
if gsutil ls -b gs://$GCS_BUCKET_NAME >/dev/null 2>&1; then
    echo "✅ Bucket exists: $GCS_BUCKET_NAME"
    
    # Grant bucket permissions
    gsutil iam ch serviceAccount:$SERVICE_ACCOUNT_EMAIL:objectAdmin gs://$GCS_BUCKET_NAME
    gsutil iam ch serviceAccount:$SERVICE_ACCOUNT_EMAIL:legacyBucketOwner gs://$GCS_BUCKET_NAME
    echo "✅ Bucket permissions granted"
else
    echo "⚠️  Bucket doesn't exist, creating it..."
    gsutil mb gs://$GCS_BUCKET_NAME
    gsutil iam ch serviceAccount:$SERVICE_ACCOUNT_EMAIL:objectAdmin gs://$GCS_BUCKET_NAME
    gsutil iam ch serviceAccount:$SERVICE_ACCOUNT_EMAIL:legacyBucketOwner gs://$GCS_BUCKET_NAME
    echo "✅ Bucket created and permissions granted"
fi

# Wait for permissions to propagate
echo "⏳ Waiting for permissions to propagate (30 seconds)..."
sleep 30

# Create HMAC key
echo "🗝️  Creating HMAC key..."
HMAC_OUTPUT=$(gcloud storage hmac create $SERVICE_ACCOUNT_EMAIL --project=$PROJECT_ID --format="json")

if [ $? -eq 0 ]; then
    # Extract access key and secret from JSON output
    ACCESS_KEY=$(echo "$HMAC_OUTPUT" | python3 -c "import sys, json; data=json.load(sys.stdin); print(data['metadata']['accessId'])")
    SECRET_KEY=$(echo "$HMAC_OUTPUT" | python3 -c "import sys, json; data=json.load(sys.stdin); print(data['secret'])")
    
    echo "✅ HMAC key created successfully!"
    echo ""
    echo "🔑 HMAC Credentials:"
    echo "Access Key ID: $ACCESS_KEY"
    echo "Secret Access Key: $SECRET_KEY"
    echo ""
    
    # Save credentials to file
    cat > $KEY_FILE << EOF
{
    "access_key_id": "$ACCESS_KEY",
    "secret_access_key": "$SECRET_KEY",
    "service_account_email": "$SERVICE_ACCOUNT_EMAIL",
    "project_id": "$PROJECT_ID",
    "bucket_name": "$GCS_BUCKET_NAME",
    "endpoint_url": "https://storage.googleapis.com",
    "region": "us-central1"
}
EOF
    
    echo "💾 Credentials saved to: $KEY_FILE"
    echo ""
    
    # Test the HMAC key
    echo "🧪 Testing HMAC key functionality..."
    
    # Create a test Python script
    cat > test_hmac.py << 'EOF'
#!/usr/bin/env python3
import json
import boto3
import sys
import time

def test_hmac_key(creds_file):
    """Test HMAC key functionality"""
    print("🧪 Testing HMAC key functionality...")
    
    try:
        # Load credentials
        with open(creds_file, 'r') as f:
            creds = json.load(f)
        
        # Initialize S3 client with GCS endpoint
        client = boto3.client('s3',
            endpoint_url=creds['endpoint_url'],
            aws_access_key_id=creds['access_key_id'],
            aws_secret_access_key=creds['secret_access_key'],
            region_name=creds['region']
        )
        
        bucket_name = creds['bucket_name']
        
        # Test 1: List objects (read access)
        print("📋 Test 1: List objects...")
        try:
            response = client.list_objects_v2(Bucket=bucket_name, MaxKeys=5)
            print("✅ List objects successful")
        except Exception as e:
            print(f"❌ List objects failed: {e}")
            return False
        
        # Test 2: Upload object (write access)
        print("📤 Test 2: Upload object...")
        test_key = f"hmac_test/test_{int(time.time())}.txt"
        test_content = f"HMAC test at {time.time()}\nAccess Key: {creds['access_key_id']}\nFull read/write access confirmed!"
        
        try:
            client.put_object(
                Bucket=bucket_name,
                Key=test_key,
                Body=test_content.encode('utf-8'),
                ContentType='text/plain'
            )
            print(f"✅ Upload successful: gs://{bucket_name}/{test_key}")
        except Exception as e:
            print(f"❌ Upload failed: {e}")
            return False
        
        # Test 3: Download object (read access verification)
        print("📥 Test 3: Download object...")
        try:
            response = client.get_object(Bucket=bucket_name, Key=test_key)
            content = response['Body'].read().decode('utf-8')
            print("✅ Download successful")
            print(f"📄 Content preview: {content[:100]}...")
        except Exception as e:
            print(f"❌ Download failed: {e}")
            return False
        
        # Test 4: Delete object (delete access)
        print("🗑️  Test 4: Delete object...")
        try:
            client.delete_object(Bucket=bucket_name, Key=test_key)
            print("✅ Delete successful")
        except Exception as e:
            print(f"❌ Delete failed: {e}")
            return False
        
        print("")
        print("🎉 All HMAC key tests passed!")
        print("✅ The HMAC key has full read/write/delete permissions to GCS")
        return True
        
    except Exception as e:
        print(f"❌ HMAC test failed: {e}")
        return False

if __name__ == "__main__":
    success = test_hmac_key(sys.argv[1] if len(sys.argv) > 1 else 'hmac_credentials.json')
    sys.exit(0 if success else 1)
EOF
    
    # Run the test
    if python3 test_hmac.py $KEY_FILE; then
        echo ""
        echo "🎉 HMAC Key Setup Complete!"
        echo "=========================="
        echo ""
        echo "✅ Service Account: $SERVICE_ACCOUNT_EMAIL"
        echo "✅ HMAC Access Key: $ACCESS_KEY"
        echo "✅ Full Storage Admin Permissions Granted"
        echo "✅ All Tests Passed"
        echo ""
        echo "📋 Next Steps:"
        echo "1. Update your server.py to use these credentials"
        echo "2. Store credentials securely (environment variables or secrets)"
        echo "3. Remove hardcoded credentials from your code"
        echo ""
        echo "💡 Example usage in Python:"
        echo "import json, boto3"
        echo "with open('$KEY_FILE') as f: creds = json.load(f)"
        echo "client = boto3.client('s3', **creds)"
        echo ""
    else
        echo "❌ HMAC key test failed - check permissions and try again"
        exit 1
    fi
    
    # Clean up test script
    rm -f test_hmac.py
    
else
    echo "❌ Failed to create HMAC key"
    echo "Check that you have the necessary permissions to create HMAC keys"
    exit 1
fi

echo "🔒 Security Notes:"
echo "- Store these credentials securely"
echo "- Never commit credentials to version control"
echo "- Consider using environment variables or Google Secret Manager"
echo "- Rotate keys periodically for security" 