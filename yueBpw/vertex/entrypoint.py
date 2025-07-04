#!/usr/bin/env python3
"""
Vertex AI Entrypoint for YuE Model Server
Downloads model weights from AIP_STORAGE_URI and starts the Flask server.
"""

import os
import sys
import subprocess
import logging
import time
import shutil
from pathlib import Path

# Configure logging for clear visibility
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger('vertex_entrypoint')

def run_command(cmd, description, check=True, capture_output=False):
    """Run a shell command with logging and error handling"""
    logger.info(f"🔧 {description}")
    logger.info(f"📋 Command: {' '.join(cmd) if isinstance(cmd, list) else cmd}")
    
    try:
        if capture_output:
            result = subprocess.run(cmd, shell=isinstance(cmd, str), check=check, 
                                  capture_output=True, text=True)
            if result.stdout:
                logger.info(f"📤 Output: {result.stdout.strip()}")
            return result
        else:
            result = subprocess.run(cmd, shell=isinstance(cmd, str), check=check)
            return result
    except subprocess.CalledProcessError as e:
        logger.error(f"❌ {description} failed with exit code {e.returncode}")
        if hasattr(e, 'stderr') and e.stderr:
            logger.error(f"❌ Error output: {e.stderr}")
        raise

def check_prerequisites():
    """Check that required tools are available"""
    logger.info("🔍 Checking prerequisites...")
    
    # Check if gsutil is available
    try:
        run_command(['gsutil', '--version'], "Check gsutil availability", capture_output=True)
        logger.info("✅ gsutil is available")
    except (subprocess.CalledProcessError, FileNotFoundError):
        logger.error("❌ gsutil not found - installing Google Cloud SDK...")
        raise RuntimeError("gsutil not available - ensure google-cloud-sdk is installed")
    
    # Check AIP_STORAGE_URI environment variable
    storage_uri = os.getenv('AIP_STORAGE_URI')
    if not storage_uri:
        logger.error("❌ AIP_STORAGE_URI environment variable not set")
        raise RuntimeError("AIP_STORAGE_URI must be set by Vertex AI")
    
    logger.info(f"✅ AIP_STORAGE_URI: {storage_uri}")
    return storage_uri

def setup_directories():
    """Create necessary directories"""
    logger.info("📁 Setting up directories...")
    
    # Create workspace directory for models
    workspace_dir = Path("/workspace")
    model_dir = workspace_dir / "model"
    model_dir.mkdir(parents=True, exist_ok=True)
    
    # Create YuE model directories that server.py expects
    yue_base_dir = Path("/app/YuE-exllamav2")
    yue_model_dir = yue_base_dir / "src" / "yue" / "models"
    yue_model_dir.mkdir(parents=True, exist_ok=True)
    
    logger.info(f"✅ Created directories:")
    logger.info(f"   📂 Workspace: {workspace_dir}")
    logger.info(f"   📂 Model storage: {model_dir}")
    logger.info(f"   📂 YuE models: {yue_model_dir}")
    
    return model_dir, yue_model_dir

def download_models(storage_uri, model_dir):
    """Download model weights from GCS using gsutil"""
    logger.info("📥 Downloading model weights from GCS...")
    logger.info(f"🔗 Source: {storage_uri}")
    logger.info(f"📁 Destination: {model_dir}")
    
    start_time = time.time()
    
    # Use gsutil with recursive copy and parallel downloads for better performance
    cmd = [
        'gsutil', '-m', 'cp', '-r',
        f"{storage_uri.rstrip('/')}/*",  # Download all contents
        str(model_dir)
    ]
    
    try:
        run_command(cmd, "Download models from GCS")
        download_time = time.time() - start_time
        logger.info(f"✅ Model download completed in {download_time:.2f} seconds")
        
        # List downloaded contents for verification
        logger.info("📋 Downloaded model contents:")
        for item in model_dir.rglob("*"):
            if item.is_file():
                size_mb = item.stat().st_size / (1024 * 1024)
                logger.info(f"   📄 {item.relative_to(model_dir)} ({size_mb:.1f} MB)")
        
        return True
        
    except subprocess.CalledProcessError as e:
        logger.error(f"❌ Failed to download models: {e}")
        logger.error("💡 Troubleshooting tips:")
        logger.error("   • Verify AIP_STORAGE_URI points to correct GCS location")
        logger.error("   • Check that service account has Storage Object Viewer permissions")
        logger.error("   • Ensure models were uploaded to the specified GCS path")
        raise

def setup_model_symlinks(model_dir, yue_model_dir):
    """Create symlinks from YuE expected paths to downloaded models"""
    logger.info("🔗 Setting up model symlinks...")
    
    # Expected model names based on server.py
    expected_models = [
        "YuE-s1-7B-anneal-en-cot",
        "YuE-s2-1B-general"
    ]
    
    symlinks_created = 0
    
    for model_name in expected_models:
        # Source: downloaded model directory
        source_path = model_dir / model_name
        # Target: where server.py expects to find it
        target_path = yue_model_dir / model_name
        
        if source_path.exists():
            # Remove existing target if it exists
            if target_path.exists() or target_path.is_symlink():
                if target_path.is_symlink():
                    target_path.unlink()
                else:
                    shutil.rmtree(target_path)
            
            # Create symlink
            target_path.symlink_to(source_path)
            logger.info(f"✅ Created symlink: {target_path} -> {source_path}")
            symlinks_created += 1
            
            # Verify symlink works by checking if files exist
            try:
                file_count = len(list(target_path.iterdir()))
                logger.info(f"   📊 Model contains {file_count} files/directories")
            except Exception as e:
                logger.warning(f"   ⚠️ Could not list symlink contents: {e}")
        else:
            logger.warning(f"⚠️ Model not found in download: {source_path}")
    
    if symlinks_created == 0:
        logger.error("❌ No model symlinks created - check download structure")
        logger.error("💡 Expected model directory structure:")
        for model_name in expected_models:
            logger.error(f"   📁 {model_dir}/{model_name}/")
        raise RuntimeError("No models found in expected locations")
    
    logger.info(f"✅ Successfully created {symlinks_created} model symlinks")

def verify_model_setup():
    """Verify that models are accessible from server.py perspective"""
    logger.info("✅ Verifying model setup...")
    
    # Import the paths from server.py logic
    base_dir = Path("/app")
    yue_dir = base_dir / "YuE-exllamav2"
    src_dir = yue_dir / "src" / "yue"
    model_base_dir = src_dir / "models"
    
    stage1_model = model_base_dir / "YuE-s1-7B-anneal-en-cot"
    stage2_model = model_base_dir / "YuE-s2-1B-general"
    
    models_ok = True
    
    for model_name, model_path in [("Stage 1", stage1_model), ("Stage 2", stage2_model)]:
        if model_path.exists():
            try:
                file_count = len([f for f in model_path.rglob("*") if f.is_file()])
                logger.info(f"✅ {model_name} model: {model_path} ({file_count} files)")
            except Exception as e:
                logger.warning(f"⚠️ {model_name} model path exists but cannot count files: {e}")
        else:
            logger.error(f"❌ {model_name} model not found: {model_path}")
            models_ok = False
    
    if not models_ok:
        raise RuntimeError("Model verification failed - server.py will not be able to load models")
    
    logger.info("🎯 All models verified and ready for server.py")

def start_server():
    """Start the Flask server"""
    logger.info("🚀 Starting Flask server...")
    logger.info("=" * 60)
    
    # Change to app directory and start server
    os.chdir("/app")
    
    # Set environment variables for server
    os.environ['PYTHONUNBUFFERED'] = '1'
    os.environ['FLASK_ENV'] = 'production'
    
    # Start server.py
    try:
        logger.info("🎵 Executing server.py...")
        subprocess.run([sys.executable, "server.py"], check=True)
    except KeyboardInterrupt:
        logger.info("🛑 Server stopped by user")
    except subprocess.CalledProcessError as e:
        logger.error(f"❌ Server failed with exit code {e.returncode}")
        raise

def main():
    """Main entrypoint function"""
    logger.info("=" * 80)
    logger.info("🚀 VERTEX AI YUE MODEL ENTRYPOINT STARTING")
    logger.info("=" * 80)
    logger.info(f"⏰ Started at: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    
    try:
        # Step 1: Check prerequisites
        storage_uri = check_prerequisites()
        
        # Step 2: Setup directories
        model_dir, yue_model_dir = setup_directories()
        
        # Step 3: Download models
        download_models(storage_uri, model_dir)
        
        # Step 4: Create symlinks
        setup_model_symlinks(model_dir, yue_model_dir)
        
        # Step 5: Verify setup
        verify_model_setup()
        
        # Step 6: Start server
        logger.info("✅ Initialization complete - starting server")
        start_server()
        
    except Exception as e:
        logger.error("=" * 80)
        logger.error("❌ ENTRYPOINT FAILED")
        logger.error("=" * 80)
        logger.error(f"Error: {e}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        sys.exit(1)

if __name__ == "__main__":
    main() 