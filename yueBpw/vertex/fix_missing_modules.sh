#!/bin/bash

# Quick fix for missing YuE modules
# This script can be run inside the container or used to patch files

set -e

echo "🔧 YuE Module Quick Fix"
echo "======================="

# Check if we're inside the container
if [ -d "/app/YuE-exllamav2" ]; then
    YUE_DIR="/app/YuE-exllamav2"
    echo "✅ Running inside container"
else
    YUE_DIR="./YuE-exllamav2"
    echo "✅ Running locally"
fi

echo "📁 YuE directory: $YUE_DIR"

# Check what's missing
echo "🔍 Checking missing modules..."
cd "$YUE_DIR/src"

# Look for soundstream files
echo "Looking for soundstream files..."
find . -name "*soundstream*" -type f

# Check models directory
echo "Looking for models directory..."
find . -name "models" -type d

# Check yue directory structure
echo "YuE src structure:"
ls -la yue/ || echo "No yue directory found"

# Check if we need to download missing files
if [ ! -f "models/soundstream_hubert_new.py" ] && [ ! -f "yue/models/soundstream_hubert_new.py" ]; then
    echo "❌ Missing soundstream_hubert_new.py"
    echo "🔧 Attempting to fix..."
    
    # Option 1: Download from GitHub
    echo "📥 Downloading missing files from GitHub..."
    
    # Create temp directory
    cd /tmp
    git clone --depth 1 https://github.com/m-a-p/YuE-exllamav2 yue_fix
    
    # Copy missing files
    if [ -f "yue_fix/src/models/soundstream_hubert_new.py" ]; then
        echo "✅ Found soundstream_hubert_new.py in GitHub repo"
        mkdir -p "$YUE_DIR/src/models"
        cp yue_fix/src/models/soundstream_hubert_new.py "$YUE_DIR/src/models/"
        echo "✅ Copied soundstream_hubert_new.py"
    fi
    
    # Copy entire models directory if it exists
    if [ -d "yue_fix/src/models" ]; then
        echo "✅ Found models directory in GitHub repo"
        cp -r yue_fix/src/models/* "$YUE_DIR/src/models/" 2>/dev/null || true
        echo "✅ Copied models directory"
    fi
    
    # Copy any other missing files
    if [ -d "yue_fix/src/yue/models" ]; then
        echo "✅ Found yue/models directory"
        mkdir -p "$YUE_DIR/src/yue/models"
        cp -r yue_fix/src/yue/models/* "$YUE_DIR/src/yue/models/" 2>/dev/null || true
        echo "✅ Copied yue/models directory"
    fi
    
    # Cleanup
    rm -rf yue_fix
    
    echo "🎉 Files copied! Verifying..."
    cd "$YUE_DIR/src"
    find . -name "*soundstream*" -type f
    
else
    echo "✅ soundstream_hubert_new.py already exists"
fi

echo "✅ Quick fix completed!"
echo "🔄 Restart the inference process to test" 