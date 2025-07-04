from flask import Flask, request, jsonify
import json
import requests
import os
import time
import hashlib
import hmac
import logging
from google.auth import default
from google.auth.transport.requests import Request

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Configuration
PROJECT_ID = "music-generation-prototype"
REGION = "us-central1"
ENDPOINT_ID = "4158120979295371264"
API_SECRET = os.environ.get('API_SECRET', 'change-this-secret-key')
RATE_LIMIT_PER_MINUTE = 5

# Simple in-memory rate limiting
request_counts = {}

def verify_api_signature(request_data, timestamp, signature):
    """Verify HMAC signature from iOS app"""
    try:
        message = f"{json.dumps(request_data, sort_keys=True)}{timestamp}"
        expected_signature = hmac.new(
            API_SECRET.encode('utf-8'),
            message.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        
        # Check timestamp (prevent replay attacks)
        current_time = int(time.time())
        if abs(current_time - int(timestamp)) > 300:  # 5 minute window
            logger.warning(f"Request timestamp too old: {timestamp}")
            return False
            
        return hmac.compare_digest(expected_signature, signature)
    except Exception as e:
        logger.error(f"Signature verification error: {e}")
        return False

def check_rate_limit(user_id):
    """Rate limiting per user"""
    current_time = int(time.time())
    minute_key = f"{user_id}:{current_time // 60}"
    
    request_counts[minute_key] = request_counts.get(minute_key, 0) + 1
    
    # Clean old entries
    old_keys = [k for k in request_counts.keys() 
                if int(k.split(':')[1]) < (current_time // 60) - 5]
    for k in old_keys:
        del request_counts[k]
    
    return request_counts[minute_key] <= RATE_LIMIT_PER_MINUTE

@app.before_request
def handle_preflight():
    """Handle CORS preflight requests"""
    if request.method == 'OPTIONS':
        response = jsonify()
        response.headers.add('Access-Control-Allow-Origin', '*')
        response.headers.add('Access-Control-Allow-Headers', 'Content-Type, X-API-Signature, X-Timestamp')
        response.headers.add('Access-Control-Allow-Methods', 'POST')
        response.headers.add('Access-Control-Max-Age', '3600')
        return response

@app.after_request
def after_request(response):
    """Add CORS headers to all responses"""
    response.headers.add('Access-Control-Allow-Origin', '*')
    response.headers.add('Access-Control-Allow-Headers', 'Content-Type, X-API-Signature, X-Timestamp')
    response.headers.add('Access-Control-Allow-Methods', 'POST')
    return response

@app.route('/health', methods=['GET'])
def health():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'service': 'yue-music-secure-api',
        'timestamp': int(time.time())
    })

@app.route('/generate', methods=['POST'])
def generate_music():
    """Secure endpoint for music generation"""
    try:
        # 1. Get signature and timestamp from headers
        api_signature = request.headers.get('X-API-Signature')
        timestamp = request.headers.get('X-Timestamp')
        
        if not api_signature or not timestamp:
            logger.warning("Missing authentication headers")
            return jsonify({'error': 'Missing authentication headers'}), 401
        
        # 2. Parse and validate request
        try:
            request_data = request.get_json()
            if not request_data:
                return jsonify({'error': 'Invalid JSON'}), 400
        except Exception as e:
            logger.error(f"JSON parsing error: {e}")
            return jsonify({'error': 'Invalid JSON format'}), 400
        
        # 3. Verify signature
        if not verify_api_signature(request_data, timestamp, api_signature):
            logger.warning("Invalid API signature")
            return jsonify({'error': 'Invalid signature'}), 401
        
        # 4. Rate limiting
        user_id = request_data.get('user_id', 'unknown')
        if not check_rate_limit(user_id):
            logger.warning(f"Rate limit exceeded for user: {user_id}")
            return jsonify({'error': 'Rate limit exceeded. Please wait before trying again.'}), 429
        
        # 5. Input validation
        required_fields = ['user_id', 'song_name', 'genre', 'lyrics']
        missing_fields = [field for field in required_fields if field not in request_data]
        if missing_fields:
            logger.warning(f"Missing required fields: {missing_fields}")
            return jsonify({'error': f'Missing required fields: {missing_fields}'}), 400
        
        # 6. Input sanitization
        for field in required_fields:
            if not isinstance(request_data[field], str) or len(request_data[field]) > 1000:
                logger.warning(f"Invalid {field} format")
                return jsonify({'error': f'Invalid {field} format'}), 400
        
        logger.info(f"Secure request from user: {user_id} - song: {request_data.get('song_name')}")
        
        # 7. Get access token and call Vertex AI
        try:
            credentials, project = default()
            auth_req = Request()
            credentials.refresh(auth_req)
            access_token = credentials.token
        except Exception as e:
            logger.error(f"Authentication error: {e}")
            return jsonify({'error': 'Authentication failed'}), 500
        
        # 8. Call Vertex AI endpoint
        vertex_url = f"https://{REGION}-prediction-aiplatform.googleapis.com/v1/projects/{PROJECT_ID}/locations/{REGION}/endpoints/{ENDPOINT_ID}:predict"
        
        vertex_payload = {"instances": [request_data]}
        vertex_headers = {
            'Authorization': f'Bearer {access_token}',
            'Content-Type': 'application/json'
        }
        
        try:
            response = requests.post(
                vertex_url,
                json=vertex_payload,
                headers=vertex_headers,
                timeout=30
            )
            
            logger.info(f"Vertex AI response status: {response.status_code}")
            
            if response.status_code == 200:
                return jsonify(response.json())
            else:
                logger.error(f"Vertex AI error: {response.text}")
                return jsonify({'error': 'Music generation service temporarily unavailable'}), 503
                
        except requests.exceptions.Timeout:
            logger.error("Vertex AI request timeout")
            return jsonify({'error': 'Request timeout. Please try again.'}), 504
        except Exception as e:
            logger.error(f"Vertex AI request error: {e}")
            return jsonify({'error': 'Service temporarily unavailable'}), 503
            
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        return jsonify({'error': 'Internal server error'}), 500

@app.route('/', methods=['GET'])
def root():
    """Root endpoint with API information"""
    return jsonify({
        'service': 'YuE Music Generation Secure API',
        'version': '1.0',
        'endpoints': {
            'health': '/health',
            'generate': '/generate (POST with signature)'
        },
        'security': 'HMAC-SHA256 signature required'
    })

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port, debug=False) 