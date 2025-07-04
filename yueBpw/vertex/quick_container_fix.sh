#!/bin/bash

# Quick Container Fix - Patches running Vertex AI container
echo "🚀 Quick Container Fix for YuE Missing Modules"
echo "=============================================="

# Get the running pod
echo "🔍 Finding running container..."
kubectl get pods --field-selector=status.phase=Running

echo ""
echo "📋 Instructions for quick fix:"
echo "1. Find your pod name from above (usually starts with 'deployed-model-')"
echo "2. Run: kubectl exec -it <POD-NAME> -- /bin/bash"
echo "3. Inside container, run the fix commands below:"

echo ""
echo "🔧 Commands to run inside container:"
cat << 'EOF'

# Once inside the container:
cd /app/YuE-exllamav2/src

# Check what's missing
echo "🔍 Current structure:"
find . -name "*soundstream*" -o -name "models" -type d

# Download and fix missing files
cd /tmp
apt-get update && apt-get install -y git
git clone --depth 1 https://github.com/m-a-p/YuE-exllamav2 yue_fix

# Copy missing models
mkdir -p /app/YuE-exllamav2/src/models
cp -r yue_fix/src/models/* /app/YuE-exllamav2/src/models/ 2>/dev/null || true

# Verify fix
cd /app/YuE-exllamav2/src
find . -name "*soundstream*"

# Test if module can be imported
cd /app/YuE-exllamav2/src
python3 -c "from models.soundstream_hubert_new import SoundStream; print('✅ Module imported successfully!')"

# Cleanup
rm -rf /tmp/yue_fix

echo "🎉 Fix completed! Try your request again."

EOF

echo ""
echo "🎯 Alternative: Use our fix script:"
echo "1. Copy fix script to container:"
echo "   kubectl cp fix_missing_modules.sh <POD-NAME>:/tmp/"
echo "2. Run fix script in container:"
echo "   kubectl exec -it <POD-NAME> -- /bin/bash -c 'cd /tmp && bash fix_missing_modules.sh'" 