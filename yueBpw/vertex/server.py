import os

import uuid
import threading
import queue
import time
import json
import subprocess
import sys
import logging
from enum import Enum
from flask import Flask, request, jsonify
import tempfile
import shutil
import gc
import requests

# ========================================
# ADD YUE MODULES TO PYTHON PATH
# ========================================
# Add the YuE source directory to Python path so we can import yue modules
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
YUE_SRC_DIR = os.path.join(BASE_DIR, "YuE-exllamav2", "src")
if YUE_SRC_DIR not in sys.path:
    sys.path.insert(0, YUE_SRC_DIR)
    print(f"Added to Python path: {YUE_SRC_DIR}")

# ========================================
# CRITICAL: Configure logging FIRST with unbuffered output
# ========================================
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)  # Only stdout - Cloud Logging captures this correctly
    ]
)

# Force unbuffered output for real-time logs
sys.stdout.reconfigure(line_buffering=True)
sys.stderr.reconfigure(line_buffering=True)

logger = logging.getLogger('vertex_yue_server')

# ========================================
# IMMEDIATE STARTUP DIAGNOSTICS
# ========================================
logger.info("=" * 80)
logger.info("🚀 VERTEX AI YUE SERVER - CONTAINER STARTUP INITIATED")
logger.info("=" * 80)
logger.info(f"📅 Startup timestamp: {time.time()}")
logger.info(f"📂 Current working directory: {os.getcwd()}")
logger.info(f"🐍 Python version: {sys.version}")
logger.info(f"🔧 Python path: {sys.path[:3]}...")  # First 3 entries
logger.info(f"🚀 Fast startup mode: {os.getenv('FAST_STARTUP_MODE', 'Not set')}")
logger.info("🎯 Container is starting up - this should appear in logs immediately")

app = Flask(__name__)

# ========================================
# MODEL LOADING STATE MANAGEMENT
# ========================================
# Thread-safe model loading state
MODELS_LOADED = threading.Event()
MODEL_LOAD_LOCK = threading.Lock()
MODEL_LOAD_ERROR = None
MODELS_DOWNLOADING = threading.Event()  # Track if download is in progress
MODELS_VALIDATED = False

# ========================================
# CUDA ENVIRONMENT SETUP
# ========================================
# Basic CUDA environment setup for Vertex AI
logger.info("🔧 Configuring CUDA environment...")

# Set CUDA device visibility
os.environ['CUDA_VISIBLE_DEVICES'] = '0'  # Use first GPU

logger.info("✅ CUDA environment configured")

# ========================================
# BASIC ML LIBRARY IMPORTS
# ========================================
logger.info("📦 Loading basic ML dependencies...")

try:
    import torch
    import numpy as np
    logger.info(f"✅ PyTorch loaded: {torch.__version__}")
    logger.info(f"✅ CUDA available: {torch.cuda.is_available()}")
    if torch.cuda.is_available():
        logger.info(f"✅ GPU device: {torch.cuda.get_device_name(0)}")
except Exception as e:
    logger.error(f"❌ Failed to load ML dependencies: {e}")
    # Don't exit - server can still work without GPU info

# Removed preloading - using subprocess approach instead

# ========================================
# ENHANCED SUBPROCESS EXECUTION WITH REAL-TIME LOGS
# ========================================
def run_inference_with_logging(command, cwd, request_id, stage_name):
    """Run inference subprocess with real-time log capture"""
    logger.info(f"🏃 Starting {stage_name} for request {request_id}")
    logger.info(f"📁 Working directory: {cwd}")
    logger.info(f"🔧 Command: {' '.join(command)}")
    
    # Check if working directory exists
    if not os.path.exists(cwd):
        logger.error(f"❌ Working directory does not exist: {cwd}")
        return 1
    
    # Check if the main script exists
    script_path = os.path.join(cwd, command[1]) if len(command) > 1 else None
    if script_path and not os.path.exists(script_path):
        logger.error(f"❌ Script not found: {script_path}")
        return 1
    
    try:
        # Start process with unbuffered output and proper PYTHONPATH
        env = os.environ.copy()
        env['PYTHONUNBUFFERED'] = '1'
        # Add YuE src directory to PYTHONPATH so yue.* imports work
        yue_src_dir = os.path.join(cwd, "src")  # Point to src so yue.* imports work
        if 'PYTHONPATH' in env:
            env['PYTHONPATH'] = f"{yue_src_dir}:{env['PYTHONPATH']}"
        else:
            env['PYTHONPATH'] = yue_src_dir
        
        logger.info(f"🔧 Environment PYTHONPATH: {env.get('PYTHONPATH', 'Not set')}")
        logger.info(f"🔧 YuE src directory: {yue_src_dir}")
        logger.info(f"🔧 YuE src directory exists: {os.path.exists(yue_src_dir)}")
        
        # Check if critical files exist
        models_dir = os.path.join(yue_src_dir, "yue", "models")
        soundstream_file = os.path.join(models_dir, "soundstream_hubert_new.py")
        logger.info(f"🔧 Models directory: {models_dir} (exists: {os.path.exists(models_dir)})")
        logger.info(f"🔧 SoundStream file: {soundstream_file} (exists: {os.path.exists(soundstream_file)})")
        
        if os.path.exists(models_dir):
            try:
                models_contents = os.listdir(models_dir)
                logger.info(f"🔧 Models directory contents: {models_contents}")
            except Exception as e:
                logger.error(f"❌ Error listing models directory: {e}")
        
        # Additional environment debugging
        logger.info(f"🔧 Working directory exists: {os.path.exists(cwd)}")
        logger.info(f"🔧 Python executable: {sys.executable}")
        if len(command) > 1:
            script_full_path = os.path.join(cwd, command[1])
            logger.info(f"🔧 Script to execute: {script_full_path} (exists: {os.path.exists(script_full_path)})")
        
        process = subprocess.Popen(
            command,
            cwd=cwd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            universal_newlines=True,
            bufsize=0,  # Unbuffered
            env=env
        )
        
        logger.info(f"🔧 Process started with PID: {process.pid}")
        
        # Stream output in real-time
        line_count = 0
        python_errors = []
        for line in iter(process.stdout.readline, ''):
            if line:
                line_count += 1
                # Log with stage prefix for easy identification
                logger.info(f"[{stage_name}] {line.rstrip()}")
                
                # Check for Python errors in the output
                line_lower = line.lower()
                if any(error_type in line_lower for error_type in ['error:', 'exception:', 'traceback', 'modulenotfounderror', 'importerror', 'attributeerror', 'runtimeerror']):
                    python_errors.append(line.rstrip())
                
                # Force flush for immediate visibility
                sys.stdout.flush()
                sys.stderr.flush()
        
        # Wait for completion
        return_code = process.wait()
        
        # If we found Python errors but got return code 0, force it to be an error
        if return_code == 0 and python_errors:
            logger.error(f"❌ Python errors detected in {stage_name} output despite return code 0:")
            for error_line in python_errors:
                logger.error(f"  ERROR: {error_line}")
            logger.error(f"❌ Forcing return code to 1 due to Python errors")
            return_code = 1
        
        logger.info(f"📊 {stage_name} process completed:")
        logger.info(f"  • Return code: {return_code}")
        logger.info(f"  • Lines of output: {line_count}")
        logger.info(f"  • Python errors detected: {len(python_errors)}")
        logger.info(f"  • PID: {process.pid}")
        
        if return_code == 0:
            logger.info(f"✅ {stage_name} completed successfully for request {request_id}")
        else:
            logger.error(f"❌ {stage_name} failed with return code {return_code} for request {request_id}")
            if python_errors:
                logger.error(f"❌ Python errors found:")
                for error_line in python_errors:
                    logger.error(f"  ERROR: {error_line}")
            
        return return_code
        
    except Exception as e:
        logger.error(f"❌ Exception during {stage_name} for request {request_id}: {e}")
        import traceback
        logger.error(f"❌ Exception traceback: {traceback.format_exc()}")
        return 1

# ========================================
# CONFIGURATION
# ========================================

class Status(Enum):
    QUEUED = "queued"
    PROCESSING = "processing"
    GENERATING_AUDIO = "generating_audio"
    UPLOADING = "uploading"
    COMPLETE = "complete"
    ERROR = "error"
    
    def __str__(self):
        return self.value
    
    def to_json(self):
        return self.value

# Base directory paths (BASE_DIR already defined above for path setup)
YUE_DIR = os.path.join(BASE_DIR, "YuE-exllamav2")
SRC_DIR = os.path.join(YUE_DIR, "src", "yue")
OUTPUT_BASE_DIR = os.path.join(YUE_DIR, "output")

# Model paths - should match where entrypoint.py creates symlinks
MODEL_BASE_DIR = os.path.join(SRC_DIR, "models")
STAGE1_MODEL = os.path.join(MODEL_BASE_DIR, "YuE-s1-7B-anneal-en-cot")
STAGE2_MODEL = os.path.join(MODEL_BASE_DIR, "YuE-s2-1B-general")

logger.info(f"🎯 Model paths configured:")
logger.info(f"  Stage 1: {STAGE1_MODEL}")
logger.info(f"  Stage 2: {STAGE2_MODEL}")

def validate_models():
    """Validate that required models are available"""
    logger.info("🔍 Validating model paths...")
    
    if not os.path.exists(STAGE1_MODEL):
        logger.error(f"❌ Stage 1 model not found at: {STAGE1_MODEL}")
        logger.error(f"📁 Contents of {MODEL_BASE_DIR}: {os.listdir(MODEL_BASE_DIR) if os.path.exists(MODEL_BASE_DIR) else 'Directory does not exist'}")
        return False
    
    if not os.path.exists(STAGE2_MODEL):
        logger.error(f"❌ Stage 2 model not found at: {STAGE2_MODEL}")
        logger.error(f"📁 Contents of {MODEL_BASE_DIR}: {os.listdir(MODEL_BASE_DIR) if os.path.exists(MODEL_BASE_DIR) else 'Directory does not exist'}")
        return False
    
    # Check if directories contain files
    stage1_files = len([f for f in os.listdir(STAGE1_MODEL) if os.path.isfile(os.path.join(STAGE1_MODEL, f))])
    stage2_files = len([f for f in os.listdir(STAGE2_MODEL) if os.path.isfile(os.path.join(STAGE2_MODEL, f))])
    
    logger.info(f"✅ Stage 1 model found: {stage1_files} files in {STAGE1_MODEL}")
    logger.info(f"✅ Stage 2 model found: {stage2_files} files in {STAGE2_MODEL}")
    
    if stage1_files == 0:
        logger.error(f"❌ Stage 1 model directory is empty: {STAGE1_MODEL}")
        return False
    
    if stage2_files == 0:
        logger.error(f"❌ Stage 2 model directory is empty: {STAGE2_MODEL}")
        return False
    
    logger.info("🎯 All models validated successfully!")
    global MODELS_VALIDATED
    MODELS_VALIDATED = True
    MODELS_LOADED.set()  # Mark as loaded
    return True

def download_models_from_huggingface():
    """Download YuE models from Hugging Face Hub while server is running"""
    logger.info("📥 Downloading models from Hugging Face Hub...")
    
    try:
        # Import huggingface_hub
        from huggingface_hub import snapshot_download
        
        # Create models directory
        os.makedirs(MODEL_BASE_DIR, exist_ok=True)
        
        # Models to download
        models_to_download = [
            {
                'name': 'Stage 1 Model (YuE-s1-7B-anneal-en-cot)',
                'repo_id': 'm-a-p/YuE-s1-7B-anneal-en-cot',
                'local_dir': STAGE1_MODEL
            },
            {
                'name': 'Stage 2 Model (YuE-s2-1B-general)', 
                'repo_id': 'm-a-p/YuE-s2-1B-general',
                'local_dir': STAGE2_MODEL
            }
        ]
        
        for model in models_to_download:
            logger.info(f"📥 Downloading {model['name']}...")
            logger.info(f"   From: {model['repo_id']}")
            logger.info(f"   To: {model['local_dir']}")
            
            start_time = time.time()
            
            try:
                snapshot_download(
                    repo_id=model['repo_id'],
                    local_dir=model['local_dir'],
                    local_files_only=False
                )
                
                download_time = time.time() - start_time
                logger.info(f"✅ {model['name']} downloaded in {download_time:.1f} seconds")
                
                # Verify download
                if os.path.exists(model['local_dir']):
                    file_count = len([f for f in os.listdir(model['local_dir']) if os.path.isfile(os.path.join(model['local_dir'], f))])
                    logger.info(f"   📊 {file_count} files in {model['local_dir']}")
                else:
                    logger.error(f"❌ Download completed but directory not found: {model['local_dir']}")
                    return False
                    
            except Exception as e:
                logger.error(f"❌ Failed to download {model['name']}: {e}")
                return False
        
        logger.info("✅ All models downloaded successfully from Hugging Face!")
        return True
        
    except ImportError:
        logger.error("❌ huggingface_hub not available - install with: pip install huggingface_hub")
        return False
    except Exception as e:
        logger.error(f"❌ Unexpected error during model download: {e}")
        return False

def ensure_models_available():
    """Ensure models are available - download if needed (thread-safe)"""
    global MODEL_LOAD_ERROR
    
    # If models are already loaded, return immediately
    if MODELS_LOADED.is_set():
        logger.info("✅ Models already loaded and ready")
        return True, None
    
    # If another thread is downloading, wait for it
    if MODELS_DOWNLOADING.is_set():
        logger.info("⏳ Models are being downloaded by another thread, waiting...")
        # Wait up to 15 minutes for download to complete
        if MODELS_LOADED.wait(timeout=900):
            logger.info("✅ Models downloaded by other thread - ready!")
            return True, None
        else:
            error_msg = "⏰ Timeout waiting for model download to complete"
            logger.error(error_msg)
            return False, error_msg
    
    # This thread will handle the download
    with MODEL_LOAD_LOCK:
        # Double-check in case another thread completed while we waited for lock
        if MODELS_LOADED.is_set():
            logger.info("✅ Models loaded by another thread while waiting for lock")
            return True, None
        
        # Set downloading flag
        MODELS_DOWNLOADING.set()
        MODEL_LOAD_ERROR = None
        
        try:
            logger.info("🚀 Starting model download (server remains responsive)...")
            logger.info("📥 This may take 5-10 minutes depending on network speed")
            
            start_time = time.time()
            
            # First try validation (maybe models exist from previous run)
            if validate_models():
                download_time = time.time() - start_time
                logger.info(f"✅ Models already available, validated in {download_time:.1f} seconds!")
                MODELS_LOADED.set()
                return True, None
            
            # Models missing, download them
            if download_models_from_huggingface():
                # Validate after download
                if validate_models():
                    download_time = time.time() - start_time
                    logger.info(f"✅ Models downloaded and validated successfully in {download_time:.1f} seconds!")
                    MODELS_LOADED.set()
                    return True, None
                else:
                    error_msg = "❌ Model validation failed after download"
                    logger.error(error_msg)
                    MODEL_LOAD_ERROR = error_msg
                    return False, error_msg
            else:
                error_msg = "❌ Failed to download models from Hugging Face"
                logger.error(error_msg)
                MODEL_LOAD_ERROR = error_msg
                return False, error_msg
                
        except Exception as e:
            error_msg = f"❌ Exception during model download: {str(e)}"
            logger.error(error_msg)
            import traceback
            logger.error(f"❌ Traceback: {traceback.format_exc()}")
            MODEL_LOAD_ERROR = error_msg
            return False, error_msg
        finally:
            # Always clear the downloading flag
            MODELS_DOWNLOADING.clear()

# Try to validate models at startup (fast path)
logger.info("🔍 Checking if models are already available...")
if validate_models():
    logger.info("✅ Models found and validated at startup!")
else:
    logger.info("📥 Models not found - will download on first request")
    logger.info("🚀 Server starting immediately (models download on-demand)")

# GCS Configuration
GCS_CLIENT = None
GCS_BUCKET_NAME = os.getenv('GCS_BUCKET_NAME', 'yue-generated-songs')

# Initialize GCS client using S3-compatible API (much simpler!)
def initialize_gcs_s3_client():
    """Initialize GCS using S3-compatible API with HMAC keys"""
    global GCS_CLIENT
    
    try:
        import boto3
        from botocore.config import Config
        from dotenv import load_dotenv
        
        # Load environment variables from .env file
        load_dotenv()
        
        # Get GCS credentials from environment variables
        gcs_access_key = os.getenv('GCS_ACCESS_KEY_ID')
        gcs_secret_key = os.getenv('GCS_SECRET_ACCESS_KEY')
        gcs_region = os.getenv('GCS_REGION', 'us-central1')
        
        if not gcs_access_key or not gcs_secret_key:
            raise ValueError("GCS credentials not found in environment variables. Please set GCS_ACCESS_KEY_ID and GCS_SECRET_ACCESS_KEY in .env file")
        
        # GCS S3-compatible endpoint and credentials (with S3v2 signature for compatibility)
        GCS_CLIENT = boto3.client('s3',
            endpoint_url='https://storage.googleapis.com',
            aws_access_key_id=gcs_access_key,
            aws_secret_access_key=gcs_secret_key,
            region_name=gcs_region,
            config=Config(signature_version='s3')  # Use S3v2 signature for GCS compatibility
        )
        
        # Test bucket access (read)
        response = GCS_CLIENT.list_objects_v2(Bucket=GCS_BUCKET_NAME, MaxKeys=1)
        logger.info(f"✅ GCS S3-compatible client initialized successfully!")
        logger.info(f"📊 Bucket: {GCS_BUCKET_NAME}")
        
        # Test write access
        try:
            GCS_CLIENT.put_object(
                Bucket=GCS_BUCKET_NAME,
                Key='test/write_test.txt',
                Body=b'write test with S3v2 signature'
            )
            logger.info(f"✅ GCS write access confirmed with S3v2 signature!")
            # Clean up test file
            GCS_CLIENT.delete_object(Bucket=GCS_BUCKET_NAME, Key='test/write_test.txt')
        except Exception as e:
            logger.warning(f"⚠️  GCS write access test failed: {e}")
            logger.warning(f"💡 HMAC key may need write permissions - see deployment guide")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ GCS S3-compatible client failed: {e}")
        GCS_CLIENT = None
        return False

gcs_success = initialize_gcs_s3_client()

# ========================================
# ENHANCED GCS AUTHENTICATION DEBUGGING
# ========================================
def debug_gcs_authentication():
    """Comprehensive GCS authentication debugging for HMAC keys"""
    logger.info("🔍 GCS Authentication Debug Report (HMAC Keys):")
    logger.info("=" * 50)
    
    # Environment variables
    logger.info("📋 Environment Variables:")
    env_vars = [
        'GOOGLE_CLOUD_PROJECT', 
        'GCP_PROJECT',
        'GCLOUD_PROJECT',
        'K_SERVICE',
        'GAE_SERVICE'
    ]
    
    for var in env_vars:
        value = os.getenv(var, 'Not set')
        logger.info(f"  • {var}: {value}")
    
    # Test GCS client status
    logger.info("☁️ GCS Client Status:")
    if GCS_CLIENT:
        logger.info("  ✅ GCS S3-compatible client initialized")
        logger.info(f"  📊 Client type: boto3.client (S3-compatible)")
        logger.info(f"  📊 Authentication: HMAC keys")
        logger.info(f"  📊 Endpoint: https://storage.googleapis.com")
        logger.info(f"  📊 Signature version: S3v2")
        
        # Test bucket access
        try:
            logger.info(f"  🪣 Testing bucket access: {GCS_BUCKET_NAME}")
            
            # Test read access
            response = GCS_CLIENT.list_objects_v2(Bucket=GCS_BUCKET_NAME, MaxKeys=1)
            object_count = response.get('KeyCount', 0)
            logger.info(f"  ✅ Bucket read access confirmed - {object_count} objects found")
            
            # Test write permissions by creating a test object
            try:
                test_key = f"auth_test/connection_test_{int(time.time())}.txt"
                test_content = f"HMAC connection test at {time.time()}"
                
                GCS_CLIENT.put_object(
                    Bucket=GCS_BUCKET_NAME,
                    Key=test_key,
                    Body=test_content.encode('utf-8')
                )
                logger.info("  ✅ Write permissions confirmed (test file uploaded)")
                
                # Clean up test file
                GCS_CLIENT.delete_object(Bucket=GCS_BUCKET_NAME, Key=test_key)
                logger.info("  🧹 Test file cleaned up")
                
            except Exception as e:
                logger.error(f"  ❌ Write permission test failed: {e}")
                logger.error("  This suggests HMAC key has read-only permissions")
                logger.error("  💡 See hmac_key_setup_guide.md for instructions")
                
        except Exception as e:
            logger.error(f"  ❌ Bucket access failed: {e}")
            logger.error("  Common causes:")
            logger.error("    - HMAC key lacks Storage permissions")
            logger.error("    - Bucket doesn't exist")
            logger.error("    - Network connectivity issues")
            logger.error("    - HMAC key is inactive or deleted")
            
    else:
        logger.error("  ❌ GCS client not initialized")
        logger.error("  Check boto3 installation and HMAC key configuration")
    
    logger.info("=" * 50)
    logger.info("🔧 Troubleshooting Tips:")
    logger.info("  1. Verify HMAC key has 'Storage Admin' role")
    logger.info("  2. Test HMAC key with test_hmac_key.py script")
    logger.info("  3. Ensure bucket exists and is in same project")
    logger.info("  4. Check network connectivity from container")
    logger.info("  5. See hmac_key_setup_guide.md for detailed instructions")
    logger.info("=" * 50)

# Run GCS debugging
debug_gcs_authentication()

# Request queue and results storage
request_queue = queue.Queue()
results = {}
processing_lock = threading.Lock()

def upload_to_gcs(local_file_path, gcs_path):
    """Upload a file to Google Cloud Storage using S3-compatible API"""
    if not GCS_CLIENT:
        logger.debug(f"📁 GCS not available - file saved locally: {local_file_path}")
        return False
    
    if not os.path.exists(local_file_path):
        logger.error(f"❌ Local file does not exist: {local_file_path}")
        return False
    
    try:
        # Get file size for logging
        file_size = os.path.getsize(local_file_path)
        logger.info(f"📤 Attempting upload {local_file_path} ({file_size:,} bytes) to gs://{GCS_BUCKET_NAME}/{gcs_path}")
        
        # Upload using S3-compatible API
        start_time = time.time()
        
        with open(local_file_path, 'rb') as f:
            GCS_CLIENT.put_object(
                Bucket=GCS_BUCKET_NAME,
                Key=gcs_path,
                Body=f.read()
            )
        
        upload_time = time.time() - start_time
        
        # Verify upload by checking if object exists
        try:
            response = GCS_CLIENT.head_object(Bucket=GCS_BUCKET_NAME, Key=gcs_path)
            uploaded_size = response.get('ContentLength', 0)
            
            logger.info(f"✅ Successfully uploaded to GCS: {gcs_path}")
            logger.info(f"📊 Upload stats: {file_size:,} bytes in {upload_time:.2f}s ({file_size/upload_time/1024/1024:.2f} MB/s)")
            logger.info(f"📊 GCS object size: {uploaded_size:,} bytes")
            return True
        except Exception as verify_error:
            logger.warning(f"⚠️ Upload completed but verification failed: {verify_error}")
            return True  # Still consider success if upload worked
        
    except Exception as e:
        logger.warning(f"⚠️ GCS upload failed (using local storage): {e}")
        # Don't treat as error - files are still saved locally
        logger.info(f"📁 File remains available locally: {local_file_path}")
        return False  # Return False but don't crash the process

def create_gcs_user_folder(user_id, request_id, song_name):
    """Create user folder path for GCS uploads using S3-compatible API"""
    
    gcs_folder = f"{user_id}_{request_id}_{song_name.replace(' ', '_').replace('/', '_')}"
    logger.info(f"📁 GCS folder path: gs://{GCS_BUCKET_NAME}/{gcs_folder}")
    
    if GCS_CLIENT:
        logger.info(f"✅ Ready to upload to GCS using S3-compatible API")
    else:
        logger.info(f"⚠️  GCS not available - using local storage")
    
    return gcs_folder

def process_yue_request(request_data, request_id):
    """Process a single YuE request"""
    start_time = time.time()
    logger.info(f"🚀 Starting processing for request {request_id}")
    logger.info(f"📝 Request data: user_id={request_data.get('user_id')}, song_name={request_data.get('song_name')}, genre={request_data.get('genre')}")
    
    # Create unique output directory for this request
    output_dir = os.path.join(OUTPUT_BASE_DIR, request_id)
    os.makedirs(output_dir, exist_ok=True)
    logger.info(f"📁 Created output directory: {output_dir}")
    
    # Extract required fields early for GCS folder creation
    user_id = request_data.get('user_id', 'test_user_12345')  # Fallback for testing
    song_name = request_data.get('song_name', 'untitled_song')
    
    # Create GCS folder immediately
    gcs_folder = create_gcs_user_folder(user_id, request_id, song_name)
    if gcs_folder:
        logger.info(f"📂 GCS folder ready: {gcs_folder}")
    
    # Add timing checkpoint
    prep_time = time.time() - start_time
    logger.info(f"⏱️  Preparation phase completed in {prep_time:.2f} seconds")
    
    try:
        # Extract additional fields (user_id and song_name already extracted above)
        lyrics = request_data.get('lyrics', '')
        genre = request_data.get('genre', 'pop')
        
        # Use the GCS folder that was already created (or fallback)
        if not gcs_folder:
            gcs_folder = f"{user_id}_{request_id}_{song_name.replace(' ', '_').replace('/', '_')}"
        logger.info(f"🗂️  Using GCS folder: {gcs_folder}")
        
        # Create temporary files for genre and lyrics
        genre_path = os.path.abspath(os.path.join(output_dir, "genre.txt"))
        lyrics_path = os.path.abspath(os.path.join(output_dir, "lyrics.txt"))
        
        # Write genre and lyrics to files
        with open(genre_path, 'w') as f:
            f.write(genre)
        
        # Ensure lyrics have proper section formatting
        if not lyrics or lyrics.lower().strip() in ['none', '']:
            formatted_lyrics = """[verse]
Your melody flows like a gentle stream
Through the silence of my heart
Every note you sing becomes my dream
A masterpiece of art

[chorus]
In this symphony of life we're writing
Each moment a brand new song
With every breath our souls uniting
Together we belong"""
        elif not any(marker in lyrics.lower() for marker in ['[verse]', '[chorus]', '[bridge]', '[intro]', '[outro]']):
            # Add basic structure if no section markers exist
            lines = [line.strip() for line in lyrics.split('\n') if line.strip()]
            if lines:
                total_lines = len(lines)
                if total_lines <= 4:
                    formatted_lyrics = f"[verse]\n" + '\n'.join(lines)
                elif total_lines <= 8:
                    mid_point = total_lines // 2
                    formatted_lyrics = f"[verse]\n" + '\n'.join(lines[:mid_point]) + "\n\n"
                    formatted_lyrics += f"[chorus]\n" + '\n'.join(lines[mid_point:])
                else:
                    quarter = total_lines // 4
                    formatted_lyrics = f"[verse]\n" + '\n'.join(lines[:quarter]) + "\n\n"
                    formatted_lyrics += f"[chorus]\n" + '\n'.join(lines[quarter:quarter*2]) + "\n\n"
                    formatted_lyrics += f"[verse]\n" + '\n'.join(lines[quarter*2:quarter*3]) + "\n\n"
                    formatted_lyrics += f"[chorus]\n" + '\n'.join(lines[quarter*3:])
            else:
                formatted_lyrics = """[verse]
Music flows through the air tonight
Creating magic in the sound"""
        else:
            formatted_lyrics = lyrics
        
        with open(lyrics_path, 'w') as f:
            f.write(formatted_lyrics)
        
        logger.info(f"Created genre file: {genre_path}")
        logger.info(f"Created lyrics file: {lyrics_path}")
        
        # Update status to generating audio
        results[request_id]['status'] = Status.GENERATING_AUDIO.value
        
        # Add timing checkpoint
        setup_time = time.time() - start_time
        logger.info(f"⏱️  Setup phase completed in {setup_time:.2f} seconds")
        
        # Build command for YuE inference
        base_args = [
            "--genre_txt", genre_path,
            "--lyrics_txt", lyrics_path,
            "--output_dir", output_dir,
            "--stage1_model", STAGE1_MODEL,
            "--stage2_model", STAGE2_MODEL,
            "--stage1_use_exl2",
            "--stage2_use_exl2"
        ]
        
        # Add optional parameters with defaults
        base_args.extend(["--stage2_batch_size", str(request_data.get('stage2_batch_size', 12))])
        base_args.extend(["--run_n_segments", str(request_data.get('run_n_segments', 1))])
        base_args.extend(["--max_new_tokens", str(request_data.get('max_new_tokens', 3000))])
        base_args.extend(["--repetition_penalty", str(request_data.get('repetition_penalty', 1.1))])
        base_args.extend(["--stage2_cache_size", str(request_data.get('stage2_cache_size', 32768))])
        
        # Add optional parameters if provided
        if 'cuda_idx' in request_data:
            base_args.extend(["--cuda_idx", str(request_data['cuda_idx'])])
        if 'stage1_cache_size' in request_data:
            base_args.extend(["--stage1_cache_size", str(request_data['stage1_cache_size'])])
        if 'stage1_cache_mode' in request_data:
            base_args.extend(["--stage1_cache_mode", request_data['stage1_cache_mode']])
        if 'stage2_cache_mode' in request_data:
            base_args.extend(["--stage2_cache_mode", request_data['stage2_cache_mode']])
        
        # Add boolean flags if set to True
        if request_data.get('stage1_no_guidance', False):
            base_args.append("--stage1_no_guidance")
        if request_data.get('keep_intermediate', False):
            base_args.append("--keep_intermediate")
        if request_data.get('disable_offload_model', False):
            base_args.append("--disable_offload_model")
        
        # Construct the final command - run script directly like original command
        # Original command was: python src/yue/infer.py ... from YuE-exllamav2 directory
        cmd = [sys.executable, "src/yue/infer.py"] + base_args
        
        logger.info(f"Running YuE inference command: {' '.join(cmd)}")
        
        # Run YuE inference using subprocess
        try:
            inference_start_time = time.time()
            logger.info(f"🎵 Starting YuE inference for request {request_id} (using subprocess)")
            logger.info(f"📂 Output directory: {output_dir}")
            logger.info(f"⏱️  About to start inference at {inference_start_time - start_time:.2f} seconds from request start")
            logger.info(f"🔧 Full command: {' '.join(cmd)}")
            logger.info(f"📁 Working directory: {YUE_DIR}")
            
            # Run from YuE-exllamav2 directory (like the original command)
            return_code = run_inference_with_logging(cmd, YUE_DIR, request_id, "YuE Inference")
            
            inference_end_time = time.time()
            inference_duration = inference_end_time - inference_start_time
            logger.info(f"📊 YuE inference subprocess completed with return code: {return_code}")
            logger.info(f"⏱️  Total inference took {inference_duration:.2f} seconds ({inference_duration/60:.1f} minutes)")
            
            if return_code != 0:
                logger.error(f"❌ YuE inference failed with return code {return_code}")
                # Let's still check if any files were generated despite the error
                logger.info(f"🔍 Checking if any files were generated despite the error...")
                if os.path.exists(output_dir):
                    files_after_error = os.listdir(output_dir)
                    logger.info(f"📂 Files in output dir after error: {files_after_error}")
                else:
                    logger.error(f"❌ Output directory {output_dir} doesn't exist after failed inference")
                raise Exception(f"YuE inference failed with return code {return_code}")
            
            logger.info(f"✅ YuE inference completed successfully for request {request_id}!")
            
        except Exception as e:
            error_msg = f"Error running YuE inference for request {request_id}: {str(e)}"
            logger.error(error_msg)
            import traceback
            logger.error(f"Full traceback: {traceback.format_exc()}")
            raise Exception(error_msg)
        
        # Update status to uploading (only after successful inference)
        results[request_id]['status'] = Status.UPLOADING.value
        
        # Upload files to GCS
        upload_success = True
        uploaded_files = {}
        
        # First, let's inspect what was actually generated
        logger.info(f"🔍 Inspecting output directory: {output_dir}")
        
        try:
            if os.path.exists(output_dir):
                all_files = []
                for root, dirs, files in os.walk(output_dir):
                    for filename in files:
                        full_path = os.path.join(root, filename)
                        rel_path = os.path.relpath(full_path, output_dir)
                        file_size = os.path.getsize(full_path)
                        all_files.append(f"  📄 {rel_path} ({file_size:,} bytes)")
                
                if all_files:
                    logger.info(f"📂 Output directory contains {len(all_files)} files:")
                    for file_info in all_files[:20]:  # Limit to first 20 files
                        logger.info(file_info)
                    if len(all_files) > 20:
                        logger.info(f"  ... and {len(all_files) - 20} more files")
                else:
                    logger.error(f"❌ Output directory {output_dir} is empty!")
            else:
                logger.error(f"❌ Output directory {output_dir} does not exist!")
        except Exception as e:
            logger.error(f"❌ Error inspecting output directory: {e}")
        
        # Upload lyrics.txt
        lyrics_gcs_path = f"{gcs_folder}/lyrics.txt"
        if upload_to_gcs(lyrics_path, lyrics_gcs_path):
            uploaded_files['lyrics.txt'] = f"gs://{GCS_BUCKET_NAME}/{lyrics_gcs_path}"
        else:
            upload_success = False
        
        # Upload genre.txt  
        genre_gcs_path = f"{gcs_folder}/genre.txt"
        if upload_to_gcs(genre_path, genre_gcs_path):
            uploaded_files['genre.txt'] = f"gs://{GCS_BUCKET_NAME}/{genre_gcs_path}"
        else:
            upload_success = False
        
        # Find and upload the generated WAV file
        logger.info(f"🔍 Searching for WAV files in {output_dir}...")
        wav_files_found = []
        for root, dirs, files in os.walk(output_dir):
            for filename in files:
                if filename.endswith('.wav'):
                    full_path = os.path.join(root, filename)
                    file_size = os.path.getsize(full_path)
                    wav_files_found.append((full_path, file_size))
                    logger.info(f"  🎵 Found WAV: {os.path.relpath(full_path, output_dir)} ({file_size:,} bytes)")
        
        if wav_files_found:
            # Use the largest WAV file (most likely the final output)
            wav_file_path, wav_size = max(wav_files_found, key=lambda x: x[1])
            logger.info(f"✅ Selected WAV file: {wav_file_path} ({wav_size:,} bytes)")
            
            wav_gcs_path = f"{gcs_folder}/{song_name.replace(' ', '_')}.wav"
            if upload_to_gcs(wav_file_path, wav_gcs_path):
                uploaded_files['song.wav'] = f"gs://{GCS_BUCKET_NAME}/{wav_gcs_path}"
                logger.info(f"✅ Successfully uploaded WAV file to GCS")
            else:
                upload_success = False
                logger.error(f"❌ Failed to upload WAV file to GCS")
        else:
            logger.error(f"❌ No WAV files found in output directory: {output_dir}")
            # Let's also check for other audio formats
            audio_files = []
            for root, dirs, files in os.walk(output_dir):
                for filename in files:
                    if any(filename.endswith(ext) for ext in ['.mp3', '.flac', '.ogg', '.m4a', '.aac']):
                        full_path = os.path.join(root, filename)
                        file_size = os.path.getsize(full_path)
                        audio_files.append(f"  🎵 {os.path.relpath(full_path, output_dir)} ({file_size:,} bytes)")
            
            if audio_files:
                logger.info(f"🔍 Found other audio files:")
                for audio_info in audio_files:
                    logger.info(audio_info)
            else:
                logger.error(f"❌ No audio files of any format found!")
            
            upload_success = False
        
        if GCS_CLIENT is not None and upload_success:
            # Create done.txt file
            done_path = os.path.abspath(os.path.join(output_dir, "done.txt"))
            with open(done_path, 'w') as f:
                f.write(f"done: {request_id}\n")
            # Upload done.txt
            done_gcs_path = f"{gcs_folder}/done.txt"
            if upload_to_gcs(done_path, done_gcs_path):
                uploaded_files['done.txt'] = f"gs://{GCS_BUCKET_NAME}/{done_gcs_path}"
            else:
                logger.error(f"Failed to upload done.txt for request {request_id}")
            # Update results with success
            results[request_id].update({
                'status': Status.COMPLETE.value,
                'gcs_folder': gcs_folder,
                'uploaded_files': uploaded_files,
                'completed_at': time.time()
            })
            logger.info(f"Successfully completed request {request_id} and uploaded to GCS (including done.txt)")
        elif GCS_CLIENT is None:
            # No GCS - just mark as complete locally
            logger.info("⚠️  GCS not configured, skipping upload. Files saved locally.")
            
            # Find the generated WAV file for local path
            local_wav_path = None
            for root, dirs, files in os.walk(output_dir):
                for filename in files:
                    if filename.endswith('.wav'):
                        local_wav_path = os.path.join(root, filename)
                        break
                if local_wav_path:
                    break
            
            results[request_id].update({
                'status': Status.COMPLETE.value,
                'local_output_dir': output_dir,
                'local_wav_file': local_wav_path,
                'completed_at': time.time()
            })
            logger.info(f"✅ Successfully completed request {request_id} - files saved locally in {output_dir}")
        else:
            raise Exception("Failed to upload one or more files to GCS")
        
    except Exception as e:
        logger.error(f"Error processing request {request_id}: {str(e)}")
        results[request_id].update({
            'status': Status.ERROR.value,
            'error': str(e),
            'completed_at': time.time()
        })

def queue_processor():
    """Worker thread that processes requests from the queue sequentially"""
    logger.info("Queue processor started")
    while True:
        if not request_queue.empty():
            request_id, request_data = request_queue.get()
            
            # Update status to processing
            results[request_id]['status'] = Status.PROCESSING.value
            results[request_id]['started_at'] = time.time()
            
            # Process this request
            with processing_lock:
                process_yue_request(request_data, request_id)
            
            request_queue.task_done()
        else:
            time.sleep(0.5)

# Models will be loaded by subprocess calls - no preloading needed

# Start the queue processor thread
threading.Thread(target=queue_processor, daemon=True).start()

@app.route('/health', methods=['GET'])
def health():
    """Simplified health check that works immediately without waiting for models"""
    logger.info("🏥 Health check requested")
    
    # Get fast startup mode status
    fast_startup = os.getenv('FAST_STARTUP_MODE', '0') == '1'
    
    # Basic container status
    health_data = {
        'status': 'healthy',
        'message': 'YuE server container is running',
        'fast_startup_mode': fast_startup,
        'container_startup_time': time.time(),
        'python_version': sys.version,
        'working_directory': os.getcwd(),
        'flask_app_running': True,
        'timestamp': time.time()
    }
    
    # Check GPU availability (non-blocking)
    try:
        if torch.cuda.is_available():
            health_data['gpu'] = {
                'available': True,
                'device_name': torch.cuda.get_device_name(0),
                'device_count': torch.cuda.device_count()
            }
        else:
            health_data['gpu'] = {'available': False}
    except Exception as e:
        health_data['gpu'] = {'error': str(e)}
    
    # Check model status (on-demand loading)
    try:
        global MODELS_VALIDATED, MODEL_LOAD_ERROR
        
        if MODELS_LOADED.is_set():
            model_status = "ready"
            model_message = "Models loaded and ready for inference"
        elif MODELS_DOWNLOADING.is_set():
            model_status = "downloading"
            model_message = "Models are currently being downloaded - check back in a few minutes"
        elif MODEL_LOAD_ERROR:
            model_status = "error"
            model_message = f"Model loading failed: {MODEL_LOAD_ERROR}"
        else:
            model_status = "not_loaded"
            model_message = "Models will be downloaded on first request"
        
        health_data['models'] = {
            'status': model_status,
            'message': model_message,
            'validated': MODELS_VALIDATED,
            'loaded': MODELS_LOADED.is_set(),
            'downloading': MODELS_DOWNLOADING.is_set(),
            'download_method': 'on_demand_huggingface',
            'source': 'huggingface_hub'
        }
        
        # Always try to get file counts for diagnostics
        stage1_dir = os.path.join(MODEL_BASE_DIR, "YuE-s1-7B-anneal-en-cot")
        stage2_dir = os.path.join(MODEL_BASE_DIR, "YuE-s2-1B-general")
        
        if os.path.exists(stage1_dir):
            stage1_files = len([f for f in os.listdir(stage1_dir) if os.path.isfile(os.path.join(stage1_dir, f))])
            health_data['models']['stage1_files'] = stage1_files
        else:
            health_data['models']['stage1_missing'] = stage1_dir
            
        if os.path.exists(stage2_dir):
            stage2_files = len([f for f in os.listdir(stage2_dir) if os.path.isfile(os.path.join(stage2_dir, f))])
            health_data['models']['stage2_files'] = stage2_files
        else:
            health_data['models']['stage2_missing'] = stage2_dir
            
    except Exception as e:
        health_data['models'] = {'error': str(e)}
    
    # Environment info
    health_data['environment'] = {
        'google_cloud_project': os.getenv('GOOGLE_CLOUD_PROJECT', 'Not set'),
        'gcs_bucket_name': os.getenv('GCS_BUCKET_NAME', 'Not set'),
        'pythonpath_set': 'PYTHONPATH' in os.environ,
        'port': os.getenv('PORT', '8000')
    }
    
    logger.info(f"🏥 Health check response: status={health_data['status']}, gpu_available={health_data.get('gpu', {}).get('available', 'unknown')}")
    return jsonify(health_data), 200

# Add a minimal readiness check
@app.route('/readiness', methods=['GET'])
def readiness():
    """Even simpler readiness check"""
    return jsonify({
        'ready': True,
        'timestamp': time.time(),
        'message': 'Container is ready to receive requests'
    }), 200

@app.route('/predict', methods=['POST'])
def predict():
    """Main prediction endpoint required by Vertex AI"""
    try:
        # Models will be loaded by subprocess - no waiting needed
        
        request_data = request.get_json()
        
        if not request_data:
            logger.warning("No JSON data provided in predict request")
            return jsonify({'error': 'No JSON data provided'}), 400
        
        # Handle both Vertex AI format and direct format
        if 'instances' in request_data:
            # Vertex AI format: {"instances": [{"data": {...}}]}
            if not request_data['instances']:
                return jsonify({'error': 'No instances provided'}), 400
            
            # Take the first instance
            instance = request_data['instances'][0]
            

            
            # Check if this is a status request
            if 'status_request_id' in instance:
                request_id = instance['status_request_id']
                logger.info(f"📊 Status check requested for {request_id}")
                
                if request_id not in results:
                    return jsonify({'predictions': [{'error': 'Request ID not found'}]}), 404
                
                result_data = results[request_id].copy()
                
                # Update queue position if still queued
                if result_data['status'] == Status.QUEUED.value:
                    position = 0
                    for i, (req_id, _) in enumerate(list(request_queue.queue)):
                        if req_id == request_id:
                            position = i
                            break
                    result_data['queue_position'] = position
                    result_data['estimated_wait_time'] = position * 120
                
                # Add timing information
                if 'queued_at' in result_data:
                    result_data['time_in_queue'] = time.time() - result_data['queued_at']
                
                if 'started_at' in result_data:
                    result_data['processing_time'] = time.time() - result_data['started_at']
                
                return jsonify({'predictions': [result_data]}), 200
            
            # Extract the actual request data
            if 'data' in instance:
                actual_request = instance['data']
            else:
                actual_request = instance
        else:
            # Direct format (backward compatibility)
            actual_request = request_data
        
        logger.info(f"Received predict request: {json.dumps(actual_request, indent=2)}")
        
        # Ensure models are available (download if needed)
        models_ready, error_msg = ensure_models_available()
        if not models_ready:
            if MODELS_DOWNLOADING.is_set():
                return jsonify({
                    'error': 'Models are currently being downloaded',
                    'status': 'downloading',
                    'message': 'Please wait 5-10 minutes for model download to complete, then retry.',
                    'retry_after': 300  # Suggest retry after 5 minutes
                }), 202  # Accepted but not ready
            else:
                return jsonify({
                    'error': 'Failed to load models',
                    'status': 'models_not_available',
                    'message': error_msg or 'Unknown model loading error'
                }), 503  # Service Unavailable
        
        logger.info("✅ Models loaded and ready! Proceeding with prediction request...")
        
        # Validate required fields
        required_fields = ['user_id', 'song_name', 'lyrics', 'genre']
        missing_fields = [field for field in required_fields if field not in actual_request]
        
        if missing_fields:
            error_msg = f'Missing required fields: {missing_fields}'
            logger.warning(error_msg)
            return jsonify({'error': error_msg}), 400
        
        # Generate request ID
        request_id = str(uuid.uuid4())
        
        # Initialize result entry with queued status
        queue_position = request_queue.qsize()
        estimated_wait_time = queue_position * 120  # 2 minutes per request estimate
        
        results[request_id] = {
            'status': Status.QUEUED.value,
            'queue_position': queue_position,
            'queued_at': time.time(),
            'estimated_wait_time': estimated_wait_time,
            'user_id': actual_request['user_id'],
            'song_name': actual_request['song_name']
        }
        
        # Add to processing queue
        request_queue.put((request_id, actual_request))
        
        logger.info(f"Added request {request_id} to queue at position {queue_position}")
        
        # Return immediate response indicating job was started successfully
        response = {
            'predictions': [{
                'request_id': request_id,
                'status': Status.QUEUED.value,
                'queue_position': queue_position,
                'estimated_wait_time_seconds': estimated_wait_time,
                'message': 'Audio generation job started successfully',
                'user_id': actual_request['user_id'],
                'song_name': actual_request['song_name']
            }]
        }
        
        logger.info(f"Returning success response for request {request_id}")
        return jsonify(response), 200
        
    except Exception as e:
        logger.error(f"Error in predict endpoint: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'error': f'Prediction failed: {str(e)}',
            'status': 'error'
        }), 500

@app.route('/status/<request_id>', methods=['GET'])
def get_status(request_id):
    """Get status of a specific request (optional endpoint for debugging)"""
    if request_id not in results:
        return jsonify({'error': 'Request ID not found'}), 404
    
    result_data = results[request_id].copy()
    
    # Update queue position if still queued
    if result_data['status'] == Status.QUEUED.value:
        position = 0
        for i, (req_id, _) in enumerate(list(request_queue.queue)):
            if req_id == request_id:
                position = i
                break
        result_data['queue_position'] = position
        result_data['estimated_wait_time'] = position * 120
    
    # Add timing information
    if 'queued_at' in result_data:
        result_data['time_in_queue'] = time.time() - result_data['queued_at']
    
    if 'started_at' in result_data:
        result_data['processing_time'] = time.time() - result_data['started_at']
    
    # Log status request for debugging
    logger.info(f"📊 Status requested for {request_id}: {result_data['status']}")
    
    return jsonify(result_data)

@app.route('/download-models', methods=['POST'])
def download_models_endpoint():
    """Manually trigger model download (useful for preloading or debugging)"""
    try:
        # Check if models are already loaded
        if MODELS_LOADED.is_set():
            return jsonify({
                'status': 'already_loaded',
                'message': 'Models are already loaded and ready',
                'models_loaded': True
            }), 200
        
        # Check if download is in progress
        if MODELS_DOWNLOADING.is_set():
            return jsonify({
                'status': 'downloading',
                'message': 'Models are already being downloaded by another request',
                'estimated_time_remaining': '5-10 minutes',
                'models_downloading': True
            }), 202  # Accepted
        
        # Trigger download (this will start immediately)
        logger.info("🔧 Manual model download triggered via /download-models endpoint")
        models_ready, error_msg = ensure_models_available()
        
        if models_ready:
            return jsonify({
                'status': 'success',
                'message': 'Models downloaded and loaded successfully',
                'models_loaded': True
            }), 200
        else:
            return jsonify({
                'status': 'error',
                'message': 'Failed to download models',
                'error': error_msg,
                'models_loaded': False
            }), 500
        
    except Exception as e:
        logger.error(f"❌ Error in download-models endpoint: {e}")
        return jsonify({
            'status': 'error',
            'message': 'Exception during model download',
            'error': str(e)
        }), 500

@app.route('/models/status', methods=['GET'])
def get_models_status():
    """Get detailed model loading status (useful for monitoring)"""
    try:
        status_info = {
            'models_loaded': MODELS_LOADED.is_set(),
            'models_downloading': MODELS_DOWNLOADING.is_set(),
            'models_validated': MODELS_VALIDATED,
            'model_load_error': MODEL_LOAD_ERROR,
            'timestamp': time.time()
        }
        
        # Add stage information if models are loaded
        if MODELS_LOADED.is_set():
            try:
                stage1_files = len([f for f in os.listdir(STAGE1_MODEL) if os.path.isfile(os.path.join(STAGE1_MODEL, f))]) if os.path.exists(STAGE1_MODEL) else 0
                stage2_files = len([f for f in os.listdir(STAGE2_MODEL) if os.path.isfile(os.path.join(STAGE2_MODEL, f))]) if os.path.exists(STAGE2_MODEL) else 0
                
                status_info['stage1_model'] = {
                    'path': STAGE1_MODEL,
                    'exists': os.path.exists(STAGE1_MODEL),
                    'file_count': stage1_files
                }
                status_info['stage2_model'] = {
                    'path': STAGE2_MODEL,
                    'exists': os.path.exists(STAGE2_MODEL),
                    'file_count': stage2_files
                }
            except Exception as e:
                status_info['model_info_error'] = str(e)
        
        logger.info(f"📊 Model status requested: loaded={status_info['models_loaded']}, downloading={status_info['models_downloading']}")
        return jsonify(status_info)
        
    except Exception as e:
        logger.error(f"❌ Error getting model status: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/debug/logs', methods=['GET'])
def get_debug_logs():
    """Debug endpoint - simplified since logs go to Cloud Logging"""
    try:
        debug_info = {
            'logging_info': {
                'method': 'Direct to Cloud Logging via stdout/stderr',
                'no_file_logging': 'All logs captured by Cloud Logging automatically',
                'log_level': 'INFO',
                'structured_json': True
            },
            'system_info': {
                'cwd': os.getcwd(),
                'pid': os.getpid(),
                'timestamp': time.time(),
                'queue_size': request_queue.qsize(),
                'active_results': len(results),
                'server_type': 'Flask (no Gunicorn)',
                'port': int(os.getenv('PORT', 8000))
            },
            'model_info': {
                'models_loaded': MODELS_LOADED.is_set(),
                'models_downloading': MODELS_DOWNLOADING.is_set(),
                'models_validated': MODELS_VALIDATED,
                'model_load_error': MODEL_LOAD_ERROR
            },
            'message': 'Check Cloud Logging console for all application logs'
        }
        
        logger.info("🔍 Debug info requested")
        return jsonify(debug_info)
        
    except Exception as e:
        logger.error(f"❌ Error getting debug info: {e}")
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    # Create necessary directories
    os.makedirs(OUTPUT_BASE_DIR, exist_ok=True)
    
    # Log startup information with high visibility
    logger.info("=" * 60)
    logger.info("🎵 VERTEX AI YUE SERVER INITIALIZATION 🎵")
    logger.info("=" * 60)
    logger.info(f"📁 Base directory: {BASE_DIR}")
    logger.info(f"📁 YuE directory: {YUE_DIR}")
    logger.info(f"📁 Source directory: {SRC_DIR}")
    logger.info(f"📁 Output directory: {OUTPUT_BASE_DIR}")
    
    # Environment information
    logger.info("🌍 Environment Information:")
    logger.info(f"  • GOOGLE_CLOUD_PROJECT: {os.getenv('GOOGLE_CLOUD_PROJECT', 'Not set')}")
    logger.info(f"  • GCS_BUCKET_NAME: {GCS_BUCKET_NAME}")
    logger.info(f"  • K_SERVICE: {os.getenv('K_SERVICE', 'Not set')}")
    logger.info(f"  • GAE_SERVICE: {os.getenv('GAE_SERVICE', 'Not set')}")
    
    # GCS status
    logger.info("☁️  GCS Configuration:")
    logger.info(f"  • GCS client initialized: {GCS_CLIENT is not None}")
    logger.info(f"  • GCS bucket: {GCS_BUCKET_NAME}")
    if GCS_CLIENT:
        logger.info(f"  • GCS client type: boto3 S3-compatible client")
        logger.info(f"  • GCS endpoint: https://storage.googleapis.com")
    
    logger.info(f"🚀 Starting Flask server on port 8000...")
    logger.info("=" * 60)
    
    # Flush logs before starting Flask
    logging.getLogger().handlers[0].flush()
    if len(logging.getLogger().handlers) > 1:
        logging.getLogger().handlers[1].flush()
    
    # Start the Flask server on port 8080 (Vertex AI requirement)
    port = int(os.getenv('PORT', 8080))
    logger.info(f"🚀 Starting Flask server on port {port}...")
    app.run(host='0.0.0.0', port=port, debug=False, threaded=True) 