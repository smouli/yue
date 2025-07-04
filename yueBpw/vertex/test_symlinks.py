#!/usr/bin/env python3
"""
Test script to verify YuE model symlink structure
Run this inside the container to verify models are properly linked
"""

import os
import sys
from pathlib import Path

def test_symlink_structure():
    """Test that symlinks are properly set up like entrypoint.py expects"""
    print("🔍 Testing YuE model symlink structure...")
    print("=" * 50)
    
    # Paths that server.py expects
    base_dir = Path("/app")
    yue_dir = base_dir / "YuE-exllamav2"
    src_dir = yue_dir / "src" / "yue"
    model_base_dir = src_dir / "models"
    
    stage1_model = model_base_dir / "YuE-s1-7B-anneal-en-cot"
    stage2_model = model_base_dir / "YuE-s2-1B-general"
    
    # Workspace paths where models should be downloaded
    workspace_dir = Path("/workspace/model")
    stage1_download = workspace_dir / "YuE-s1-7B-anneal-en-cot"
    stage2_download = workspace_dir / "YuE-s2-1B-general"
    
    print("📁 Directory Structure:")
    print(f"   Model Base: {model_base_dir}")
    print(f"   Workspace:  {workspace_dir}")
    print()
    
    # Test each model
    models_to_test = [
        ("Stage 1", stage1_model, stage1_download),
        ("Stage 2", stage2_model, stage2_download)
    ]
    
    all_tests_passed = True
    
    for model_name, symlink_path, download_path in models_to_test:
        print(f"🎯 Testing {model_name} Model:")
        print(f"   Symlink: {symlink_path}")
        print(f"   Target:  {download_path}")
        
        # Test 1: Check if symlink exists
        if symlink_path.exists():
            print(f"   ✅ Symlink exists")
        else:
            print(f"   ❌ Symlink missing")
            all_tests_passed = False
            continue
        
        # Test 2: Check if it's actually a symlink
        if symlink_path.is_symlink():
            print(f"   ✅ Is a symlink")
            actual_target = symlink_path.resolve()
            print(f"   🔗 Points to: {actual_target}")
        else:
            print(f"   ⚠️  Not a symlink (might be direct directory)")
        
        # Test 3: Check if target exists
        if download_path.exists():
            print(f"   ✅ Target exists")
        else:
            print(f"   ❌ Target missing")
            all_tests_passed = False
            continue
        
        # Test 4: Count files accessible through symlink
        try:
            file_count = len([f for f in symlink_path.rglob("*") if f.is_file()])
            print(f"   ✅ Accessible files: {file_count}")
        except Exception as e:
            print(f"   ❌ Cannot access files: {e}")
            all_tests_passed = False
        
        print()
    
    print("=" * 50)
    if all_tests_passed:
        print("🎉 All symlink tests PASSED! YuE should work correctly.")
        return True
    else:
        print("❌ Some symlink tests FAILED. YuE may not work correctly.")
        return False

def test_import_compatibility():
    """Test that the paths work with server.py imports"""
    print("🐍 Testing Python import compatibility...")
    
    try:
        # Try to import the model validation function
        sys.path.insert(0, '/app')
        from server import validate_models, MODEL_BASE_DIR, STAGE1_MODEL, STAGE2_MODEL
        
        print(f"✅ Server imports successful")
        print(f"   MODEL_BASE_DIR: {MODEL_BASE_DIR}")
        print(f"   STAGE1_MODEL: {STAGE1_MODEL}")
        print(f"   STAGE2_MODEL: {STAGE2_MODEL}")
        
        # Test the validation function
        print("🧪 Running server.py validate_models()...")
        result = validate_models()
        
        if result:
            print("✅ Server validation PASSED!")
            return True
        else:
            print("❌ Server validation FAILED!")
            return False
            
    except Exception as e:
        print(f"❌ Import test failed: {e}")
        return False

if __name__ == "__main__":
    print("🚀 YuE Model Symlink Test")
    print("=" * 60)
    
    symlink_ok = test_symlink_structure()
    print()
    import_ok = test_import_compatibility()
    
    print()
    print("=" * 60)
    if symlink_ok and import_ok:
        print("🎉 ALL TESTS PASSED! YuE is ready for inference.")
        sys.exit(0)
    else:
        print("❌ TESTS FAILED! Check symlink structure and model downloads.")
        sys.exit(1) 