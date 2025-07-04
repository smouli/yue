#!/bin/bash

# Fix HMAC Key Permissions - Grant Storage Admin role to existing HMAC key
# This script helps grant write permissions to your existing HMAC key

set -e

# Configuration
PROJECT_ID="music-generation-prototype"
HMAC_ACCESS_KEY="GOOG1EMCKDIMXMS35ISQUXZGCJNOSVJCDM4K6SXUMGWP3IXCXYXOMWFFSCJRB"

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${GREEN}🔧 FIX HMAC KEY PERMISSIONS 🔧${NC}"
echo -e "${GREEN}================================${NC}"
echo -e "${BLUE}📅 Started: $(date '+%Y-%m-%d %H:%M:%S')${NC}"
echo -e "${BLUE}🔑 HMAC Key: ${HMAC_ACCESS_KEY:0:20}...${NC}"
echo -e "${BLUE}🎯 Goal: Grant Storage Admin role${NC}"
echo -e "${GREEN}================================${NC}"

# Step 1: Find the service account that owns this HMAC key
echo -e "\n${BLUE}🔍 Step 1: Finding service account for HMAC key...${NC}"

# List all HMAC keys and find the one that matches
HMAC_LIST=$(gcloud storage hmac list --format="value(metadata.accessId,metadata.serviceAccountEmail)" 2>/dev/null)

SERVICE_ACCOUNT=""
while IFS=$'\t' read -r access_id service_account_email; do
    if [[ "$access_id" == "$HMAC_ACCESS_KEY" ]]; then
        SERVICE_ACCOUNT="$service_account_email"
        break
    fi
done <<< "$HMAC_LIST"

if [[ -z "$SERVICE_ACCOUNT" ]]; then
    echo -e "${RED}❌ Could not find service account for HMAC key${NC}"
    echo -e "${YELLOW}💡 This could mean:${NC}"
    echo -e "${YELLOW}  • HMAC key is from a different project${NC}"
    echo -e "${YELLOW}  • HMAC key has been deleted${NC}"
    echo -e "${YELLOW}  • You don't have permissions to list HMAC keys${NC}"
    echo -e "${YELLOW}🔧 Manual fix:${NC}"
    echo -e "${YELLOW}  1. Run: gcloud storage hmac list${NC}"
    echo -e "${YELLOW}  2. Find your HMAC key in the list${NC}"
    echo -e "${YELLOW}  3. Note the service account email${NC}"
    echo -e "${YELLOW}  4. Grant Storage Admin role to that service account${NC}"
    exit 1
fi

echo -e "${GREEN}✅ Found service account: ${SERVICE_ACCOUNT}${NC}"

# Step 2: Check current permissions
echo -e "\n${BLUE}🔍 Step 2: Checking current permissions...${NC}"

# Get current IAM policy for this service account
CURRENT_ROLES=$(gcloud projects get-iam-policy ${PROJECT_ID} \
    --flatten="bindings[].members" \
    --format="value(bindings.role)" \
    --filter="bindings.members:serviceAccount:${SERVICE_ACCOUNT}" 2>/dev/null)

echo -e "${BLUE}📋 Current roles for ${SERVICE_ACCOUNT}:${NC}"
if [[ -z "$CURRENT_ROLES" ]]; then
    echo -e "${YELLOW}  • No roles found (this is likely the issue)${NC}"
else
    while IFS= read -r role; do
        echo -e "${BLUE}  • ${role}${NC}"
    done <<< "$CURRENT_ROLES"
fi

# Check if Storage Admin role is already granted
if echo "$CURRENT_ROLES" | grep -q "roles/storage.admin"; then
    echo -e "${GREEN}✅ Storage Admin role already granted!${NC}"
    echo -e "${YELLOW}💡 Your HMAC key should have write permissions${NC}"
    echo -e "${YELLOW}🧪 Test with: python3 test_hmac_key.py${NC}"
    exit 0
fi

# Step 3: Grant Storage Admin role
echo -e "\n${BLUE}🔧 Step 3: Granting Storage Admin role...${NC}"

gcloud projects add-iam-policy-binding ${PROJECT_ID} \
    --member="serviceAccount:${SERVICE_ACCOUNT}" \
    --role="roles/storage.admin" \
    --quiet

echo -e "${GREEN}✅ Storage Admin role granted!${NC}"

# Step 4: Verify the change
echo -e "\n${BLUE}🔍 Step 4: Verifying permissions...${NC}"

# Wait a moment for IAM changes to propagate
echo -e "${YELLOW}⏳ Waiting 10 seconds for IAM changes to propagate...${NC}"
sleep 10

# Check updated permissions
UPDATED_ROLES=$(gcloud projects get-iam-policy ${PROJECT_ID} \
    --flatten="bindings[].members" \
    --format="value(bindings.role)" \
    --filter="bindings.members:serviceAccount:${SERVICE_ACCOUNT}" 2>/dev/null)

echo -e "${BLUE}📋 Updated roles for ${SERVICE_ACCOUNT}:${NC}"
while IFS= read -r role; do
    echo -e "${BLUE}  • ${role}${NC}"
done <<< "$UPDATED_ROLES"

if echo "$UPDATED_ROLES" | grep -q "roles/storage.admin"; then
    echo -e "${GREEN}✅ Storage Admin role confirmed!${NC}"
else
    echo -e "${RED}❌ Storage Admin role not found (IAM propagation delay?)${NC}"
    echo -e "${YELLOW}💡 Wait 1-2 minutes and test again${NC}"
fi

# Final instructions
echo -e "\n${GREEN}================================${NC}"
echo -e "${GREEN}🎉 HMAC KEY PERMISSIONS FIXED! 🎉${NC}"
echo -e "${GREEN}================================${NC}"
echo -e "${BLUE}🔑 Service Account: ${SERVICE_ACCOUNT}${NC}"
echo -e "${BLUE}🛡️  Role Added: Storage Admin${NC}"
echo -e "${BLUE}⏱️  Propagation: 1-2 minutes${NC}"
echo -e "${GREEN}================================${NC}"

echo -e "\n${YELLOW}🧪 Next Steps:${NC}"
echo -e "${YELLOW}1. Test HMAC key: python3 test_hmac_key.py${NC}"
echo -e "${YELLOW}2. If test passes: ./quick_gcs_fix_deploy.sh${NC}"
echo -e "${YELLOW}3. If test fails: Wait 2 minutes and retry${NC}"

echo -e "\n${GREEN}🎯 Your HMAC key should now have write permissions!${NC}" 