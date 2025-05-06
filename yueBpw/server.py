import os
import uuid
import threading
import queue
import time
import json
import subprocess
from enum import Enum
from flask import Flask, request, jsonify, send_file
from lyrics_generators import create_lyrics_generator, LyricsGenerator

class Status(Enum):
    QUEUED = "queued"
    PROCESSING = "processing"
    GENERATING_LYRICS = "generating_lyrics"
    GENERATING_AUDIO = "generating_audio"
    COMPLETE = "complete"
    ERROR = "error"
    
    def __str__(self):
        return self.value
    
    def to_json(self):
        return self.value

app = Flask(__name__)

# Base directory paths
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
YUE_DIR = os.path.join(BASE_DIR, "YuE-exllamav2")
SRC_DIR = os.path.join(YUE_DIR, "src", "yue")
OUTPUT_BASE_DIR = os.path.join(YUE_DIR, "output")
RESULTS_FILE = os.path.join(BASE_DIR, "results.json")
LYRICS_PROMPT_FILE = os.path.join(BASE_DIR, "lyrics_prompt.txt")
GENRE_PROMPT_FILE = os.path.join(BASE_DIR, "genre_prompt.txt")

# Default system prompt for lyrics generation
DEFAULT_LYRICS_PROMPT = """You are a professional songwriter. Generate song lyrics based on the given prompt.
The lyrics MUST follow this exact structure and format:
- [verse]
- [chorus]
- [verse]
- [chorus]
- [bridge]
- [outro]

Each section should be separated by exactly two newlines (\n\n).
Within each section, lines should be separated by a single newline (\n).
Each section should be marked with its type in square brackets (e.g., [verse], [chorus], etc.).

Example format:
[verse]
Line 1
Line 2
Line 3
Line 4

[chorus]
Line 1
Line 2
Line 3
Line 4

[verse]
...and so on.

The lyrics should be creative, meaningful, and suitable for singing. Do not include any explanations or additional text - just the lyrics in the specified format."""

# Default system prompt for genre extraction - starts blank
DEFAULT_GENRE_PROMPT = "POP"

# Model paths
STAGE1_MODEL = os.path.join(SRC_DIR, "models", "YuE-s1-7B-anneal-en-cot-exl2-8.0bpw")
STAGE2_MODEL = os.path.join(SRC_DIR, "models", "YuE-s2-1B-general-exl2-8.0bpw")

# Load persisted results if they exist
def load_results():
    if os.path.exists(RESULTS_FILE):
        try:
            with open(RESULTS_FILE, 'r') as f:
                loaded_results = json.load(f)
                print(f"Loaded {len(loaded_results)} previous results from {RESULTS_FILE}")
                return loaded_results
        except Exception as e:
            print(f"Error loading results from {RESULTS_FILE}: {e}")
    return {}

# Save results to persistent storage
def save_results():
    try:
        with open(RESULTS_FILE, 'w') as f:
            json.dump(results, f, indent=2)
            print(f"Saved {len(results)} results to {RESULTS_FILE}")
    except Exception as e:
        print(f"Error saving results to {RESULTS_FILE}: {e}")

# Configure API clients
config_path = os.path.join(BASE_DIR, 'config.json')
print(f"\nLooking for config file at: {config_path}")
print(f"Config file exists: {os.path.exists(config_path)}")

# Default provider is Anthropic
lyrics_provider = "anthropic"
google_api_key = None
anthropic_api_key = None

if os.path.exists(config_path):
    print("Found config.json, attempting to read...")
    with open(config_path) as f:
        config = json.load(f)
        google_api_key = config.get('google_api_key')
        anthropic_api_key = config.get('anthropic_api_key')
        lyrics_provider = config.get('lyrics_provider', 'anthropic').lower()
        print(f"Google API key found in config: {'Yes' if google_api_key else 'No'}")
        print(f"Anthropic API key found in config: {'Yes' if anthropic_api_key else 'No'}")
        print(f"Using lyrics provider: {lyrics_provider}")
else:
    print("Config file not found, checking environment variables...")
    google_api_key = os.getenv('GOOGLE_API_KEY')
    anthropic_api_key = os.getenv('ANTHROPIC_API_KEY')
    lyrics_provider = os.getenv('LYRICS_PROVIDER', 'anthropic').lower()
    print(f"Google API key found in environment: {'Yes' if google_api_key else 'No'}")
    print(f"Anthropic API key found in environment: {'Yes' if anthropic_api_key else 'No'}")
    print(f"Using lyrics provider: {lyrics_provider}")

# Initialize the appropriate lyrics generator
if lyrics_provider == 'gemini':
    if not google_api_key:
        raise ValueError("Gemini provider selected but Google API key not found. Please set it in config.json or as GOOGLE_API_KEY environment variable.")
    api_key = google_api_key
elif lyrics_provider == 'anthropic':
    if not anthropic_api_key:
        raise ValueError("Anthropic provider selected but Anthropic API key not found. Please set it in config.json or as ANTHROPIC_API_KEY environment variable.")
    api_key = anthropic_api_key
else:
    raise ValueError(f"Unsupported lyrics provider: {lyrics_provider}. Supported: 'gemini', 'anthropic'")

print(f"Initializing {lyrics_provider} lyrics generator...")
lyrics_generator = create_lyrics_generator(lyrics_provider, api_key)
print(f"Lyrics generator initialized using {lyrics_provider}")

# Load top 200 tags
with open(os.path.join(YUE_DIR, 'top_200_tags.json')) as f:
    TOP_200_TAGS = json.load(f)
    VALID_GENRES = set(g.lower() for g in TOP_200_TAGS['genre'])

# Request queue and results storage
request_queue = queue.Queue()
results = load_results()  # Load previous results
processing_lock = threading.Lock() 

def find_closest_genre(genre):
    """Find the closest matching genre from the top 200 tags"""
    genre = genre.lower()
    
    # Direct match
    if genre in VALID_GENRES:
        return genre
    
    # Remove special characters and try again
    cleaned_genre = ''.join(c for c in genre if c.isalnum() or c.isspace())
    if cleaned_genre in VALID_GENRES:
        return cleaned_genre
    
    # Try common variations
    variations = {
        'hiphop': 'hip-hop',
        'hip hop': 'hip-hop',
        'rb': 'r&b',
        'randb': 'r&b',
        'rhythm and blues': 'r&b',
        'electronica': 'electronic',
        'classical music': 'classical',
        'pop music': 'pop',
        'rock music': 'rock'
    }
    if genre in variations and variations[genre] in VALID_GENRES:
        return variations[genre]
    
    # Find partial matches
    partial_matches = [valid_genre for valid_genre in VALID_GENRES 
                      if genre in valid_genre or valid_genre in genre]
    if partial_matches:
        return partial_matches[0]
    
    # Default to 'pop' if no match found
    return 'pop'

def generate_lyrics_with_gemini(prompt):
    """Generate song lyrics using the configured lyrics generator based on the prompt"""
    # Get the current lyrics prompt from file or use default
    lyrics_prompt = lyrics_generator.read_lyrics_prompt(LYRICS_PROMPT_FILE, DEFAULT_LYRICS_PROMPT)
    
    print("Starting lyrics generation...")
    try:
        lyrics = lyrics_generator.generate_lyrics(prompt, lyrics_prompt)
        print("Lyrics generated successfully")
        return lyrics
    except Exception as e:
        print(f"Detailed error in lyrics generation: {str(e)}")
        raise

def extract_genre_from_prompt(prompt):
    """Extract or generate a suitable genre from the prompt using the configured generator"""
    # Get the current genre prompt from file
    genre_prompt = lyrics_generator.read_genre_prompt(GENRE_PROMPT_FILE)
    
    print("Starting genre extraction...")
    try:
        suggested_genre = lyrics_generator.extract_genre(prompt, genre_prompt)
        print("Genre extracted successfully")
        matched_genre = find_closest_genre(suggested_genre)
        return matched_genre
    except Exception as e:
        print(f"Detailed error in genre extraction: {str(e)}")
        raise

def process_yue_request(request_data, request_id):
    """Process a single YuE request"""
    # Create unique output directory for this request
    output_dir = os.path.join(OUTPUT_BASE_DIR, request_id)
    os.makedirs(output_dir, exist_ok=True)
    
    try:
        # Update status to generating lyrics if they're not provided
        if 'lyrics' not in request_data:
            results[request_id]['status'] = Status.GENERATING_LYRICS.value
            save_results()
            
            # Generate lyrics if not provided
            lyrics = generate_lyrics_with_gemini(request_data.get('prompt', ''))
            request_data['lyrics'] = lyrics
        
        # Create temporary files for genre and lyrics
        genre_path = os.path.abspath(os.path.join(output_dir, "genre.txt"))
        lyrics_path = os.path.abspath(os.path.join(output_dir, "lyrics.txt"))
        
        with open(genre_path, 'w') as f:
            f.write(request_data.get('genre', ''))
        
        with open(lyrics_path, 'w') as f:
            f.write(request_data.get('lyrics', ''))
        
        # Update status to generating audio
        results[request_id]['status'] = Status.GENERATING_AUDIO.value
        save_results()
        
        # Build base command with common arguments
        base_args = [
            "--genre_txt", genre_path,
            "--lyrics_txt", lyrics_path,
            "--output_dir", output_dir,
            "--stage1_model", STAGE1_MODEL,
            "--stage2_model", STAGE2_MODEL,
            "--stage1_use_exl2",
            "--stage2_use_exl2"
        ]
        
        # Add optional parameters if provided
        if 'cuda_idx' in request_data:
            base_args.extend(["--cuda_idx", str(request_data['cuda_idx'])])
        if 'run_n_segments' in request_data:
            base_args.extend(["--run_n_segments", str(request_data['run_n_segments'])])
        if 'stage2_batch_size' in request_data:
            base_args.extend(["--stage2_batch_size", str(request_data['stage2_batch_size'])])
        if 'max_new_tokens' in request_data:
            base_args.extend(["--max_new_tokens", str(request_data['max_new_tokens'])])
        if 'repetition_penalty' in request_data:
            base_args.extend(["--repetition_penalty", str(request_data['repetition_penalty'])])
        if 'stage1_cache_size' in request_data:
            base_args.extend(["--stage1_cache_size", str(request_data['stage1_cache_size'])])
        if 'stage2_cache_size' in request_data:
            base_args.extend(["--stage2_cache_size", str(request_data['stage2_cache_size'])])
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
        
        # Construct the final command
        cmd = ["python", os.path.join(SRC_DIR, "infer.py")] + base_args
        
        print(f"Processing request {request_id}")
        print(f"Running command: {' '.join(cmd)}")
        subprocess.run(cmd, check=True, cwd=YUE_DIR)
        print(f"Completed request {request_id}")
        
        # Collect results
        result_files = {}
        print(f"Scanning output directory: {output_dir}")
        for root, dirs, files in os.walk(output_dir):
            for filename in files:
                if filename.endswith((".json", ".wav", ".mid", ".mp3")):
                    full_path = os.path.join(root, filename)
                    relative_path = os.path.relpath(full_path, OUTPUT_BASE_DIR)
                    result_files[filename] = relative_path
                    print(f"Found result file: {filename} at {relative_path}")
        
        if not result_files:
            raise Exception("No result files found in output directory")
        
        # Update results and save to file
        results[request_id].update({
            'status': Status.COMPLETE.value,
            'file_paths': result_files,
            'completed_at': time.time()
        })
        save_results()
        print(f"Stored results for request {request_id}: {result_files}")
        
    except Exception as e:
        print(f"Error processing request {request_id}: {str(e)}")
        results[request_id].update({
            'status': Status.ERROR.value,
            'error': str(e),
            'completed_at': time.time()
        })
        save_results() 

def queue_processor():
    """Worker thread that processes requests from the queue sequentially"""
    while True:
        if not request_queue.empty():
            request_id, request_data = request_queue.get()
            
            # Update status to processing
            results[request_id]['status'] = Status.PROCESSING.value
            results[request_id]['started_at'] = time.time()
            save_results()
            
            # Process this request
            with processing_lock:
                process_yue_request(request_data, request_id)
            
            request_queue.task_done()
        else:
            time.sleep(0.5)

# Start the queue processor thread
threading.Thread(target=queue_processor, daemon=True).start()

@app.route('/generate', methods=['POST'])
def generate():
    """Endpoint to submit a new generation request"""
    request_data = request.json
    request_id = str(uuid.uuid4())
    print(f"\n=== New generation request ===")
    print(f"Request ID: {request_id}")
    print(f"Received request data: {json.dumps(request_data, indent=2)}")
    
    # Validate required fields
    if 'genre' not in request_data or 'lyrics' not in request_data:
        print(f"Error: Missing required fields in request")
        return jsonify({
            'error': 'Missing required fields. Please provide genre and lyrics.'
        }), 400
    
    print(f"\nCreating YuE request with parameters:")
    # Create request data for the YuE system with default values
    yue_request = {
        'lyrics': request_data['lyrics'],
        'genre': request_data['genre'],
        'stage1_use_exl2': True,  # Enable exllamav2 for stage 1
        'stage2_use_exl2': True,   # Enable exllamav2 for stage 2
        'stage2_batch_size': 12,  # Set batch size
        'run_n_segments': 2,      # Number of segments to process
        'max_new_tokens': 3000,   # Maximum number of new tokens
        'repetition_penalty': 1.1,  # Control diversity and coherence
        'stage2_cache_size': 32768  # Cache size for stage 2
    }
    print(f"Default parameters set: {json.dumps(yue_request, indent=2)}")
    
    # Copy over any additional YuE parameters if provided
    for param in ['stage1_model', 'stage2_model', 'stage2_batch_size', 'max_new_tokens', 'repetition_penalty',
                 'stage1_cache_size', 'stage2_cache_size', 'stage1_cache_mode', 'stage2_cache_mode',
                 'stage1_no_guidance', 'keep_intermediate', 'disable_offload_model', 'cuda_idx']:
        if param in request_data:
            yue_request[param] = request_data[param]
            print(f"Overriding parameter {param}: {request_data[param]}")
    
    # Initialize result entry with queued status
    queue_position = request_queue.qsize()
    print(f"\nQueue status:")
    print(f"Current queue size: {queue_position}")
    print(f"Estimated wait time: ~{queue_position * 60} seconds")
    
    results[request_id] = {
        'status': Status.QUEUED.value,
        'queue_position': queue_position,
        'queued_at': time.time(),
        'estimated_wait_time': queue_position * 60  # Rough estimate: 60 seconds per request
    }
    save_results()  # Save after adding new request
    print(f"Request {request_id} added to results dictionary")
    print(f"Current active requests: {list(results.keys())}")
    
    # Add to processing queue
    request_queue.put((request_id, yue_request))
    print(f"\nRequest {request_id} added to processing queue")
    print(f"Final YuE request configuration: {json.dumps(yue_request, indent=2)}")
    print(f"=== End of request initialization ===\n")
    
    return jsonify({
        'request_id': request_id,
        'status': Status.QUEUED.value,
        'queue_position': queue_position,
        'estimated_wait_time': f"~{queue_position * 60} seconds"
    })

@app.route('/generate_track', methods=['POST'])
def generate_track():
    """Endpoint to generate a track from a prompt using the configured lyrics generator for lyrics and genre extraction"""
    request_data = request.json
    print(f"\n=== New track generation request ===")
    print(f"Received request data: {json.dumps(request_data, indent=2)}")
    
    # Validate required fields
    if 'prompt' not in request_data:
        print(f"Error: Missing required field 'prompt' in request")
        return jsonify({
            'error': 'Missing required field: prompt'
        }), 400
    
    try:
        print("\nStarting lyrics and genre generation...")
        # Generate lyrics and extract genre using configured provider
        lyrics = generate_lyrics_with_gemini(request_data['prompt'])
        genre = extract_genre_from_prompt(request_data['prompt'])
        print(f"Generated lyrics: {lyrics}")
        print(f"Extracted genre: {genre}")
        
        print("\nCreating YuE request with parameters:")
        # Create request data for the YuE system
        yue_request = {
            'lyrics': lyrics,
            'genre': genre,
            'stage1_use_exl2': True,  # Enable exllamav2 for stage 1
            'stage2_use_exl2': True,   # Enable exllamav2 for stage 2
            'stage2_batch_size': 12,  # Set batch size
            'run_n_segments': 2,      # Number of segments to process
            'max_new_tokens': 3000,   # Maximum number of new tokens
            'repetition_penalty': 1.1,  # Control diversity and coherence
            'stage2_cache_size': 32768  # Cache size for stage 2
        }
        print(f"Default parameters set: {json.dumps(yue_request, indent=2)}")
        
        # Copy over any additional YuE parameters if provided
        for param in ['stage1_model', 'stage2_model', 'stage2_batch_size', 'max_new_tokens', 'repetition_penalty',
                     'stage1_cache_size', 'stage2_cache_size', 'stage1_cache_mode', 'stage2_cache_mode',
                     'stage1_no_guidance', 'keep_intermediate', 'disable_offload_model', 'cuda_idx']:
            if param in request_data:
                yue_request[param] = request_data[param]
                print(f"Overriding parameter {param}: {request_data[param]}")
        
        # Generate a request ID
        request_id = str(uuid.uuid4())
        print(f"\nGenerated request ID: {request_id}")
        queue_position = request_queue.qsize()
        print(f"Current queue size: {queue_position}")
        
        # Initialize result entry
        results[request_id] = {
            'status': Status.QUEUED.value,
            'queue_position': queue_position,
            'queued_at': time.time(),
            'estimated_wait_time': queue_position * 60,  # Rough estimate: 60 seconds per request
            'generated_genre': genre,
            'generated_lyrics': lyrics,
            'lyrics_provider': lyrics_provider  # Include the provider used
        }
        save_results()  # Save after adding new request
        print(f"Request {request_id} added to results dictionary")
        print(f"Current active requests: {list(results.keys())}")
        
        # Add to processing queue
        request_queue.put((request_id, yue_request))
        print(f"\nRequest {request_id} added to processing queue")
        print(f"Final YuE request configuration: {json.dumps(yue_request, indent=2)}")
        print(f"=== End of track generation request initialization ===\n")
        
        return jsonify({
            'request_id': request_id,
            'status': Status.QUEUED.value,
            'queue_position': queue_position,
            'estimated_wait_time': f"~{queue_position * 60} seconds",
            'generated_genre': genre,
            'generated_lyrics': lyrics,
            'lyrics_provider': lyrics_provider  # Include the provider in the response
        })
        
    except Exception as e:
        error_message = f'Error processing request: {str(e)}'
        print(f"Error: {error_message}")
        return jsonify({
            'error': error_message
        }), 500

@app.route('/generate_lyrics', methods=['POST'])
def generate_lyrics():
    """Endpoint to generate only lyrics in the specified format using the configured lyrics generator"""
    request_data = request.json
    print(f"\n=== New lyrics generation request ===")
    print(f"Received request data: {json.dumps(request_data, indent=2)}")
    
    # Validate required fields
    if 'prompt' not in request_data:
        print(f"Error: Missing required field 'prompt' in request")
        return jsonify({
            'error': 'Missing required field: prompt'
        }), 400
    
    try:
        print("\nStarting lyrics generation...")
        lyrics = generate_lyrics_with_gemini(request_data['prompt'])
        print(f"Generated lyrics: {lyrics}")
        
        # Also generate a suggested genre for reference
        try:
            print("\nExtracting suggested genre...")
            suggested_genre = extract_genre_from_prompt(request_data['prompt'])
            print(f"Suggested genre: {suggested_genre}")
        except Exception as e:
            print(f"Warning: Could not extract genre: {e}")
            suggested_genre = None
        
        response = {
            'lyrics': lyrics,
            'suggested_genre': suggested_genre,
            'lyrics_provider': lyrics_provider,  # Include the provider used
            'format_explanation': {
                'structure': [
                    '[verse]',
                    '[chorus]',
                    '[verse]',
                    '[chorus]',
                    '[bridge]',
                    '[outro]'
                ],
                'notes': 'Each section is marked with square brackets and separated by two newlines. Lines within sections are separated by single newlines.'
            }
        }
        
        print("\nLyrics generation completed successfully")
        print(f"Response: {json.dumps(response, indent=2)}")
        print(f"=== End of lyrics generation request ===\n")
        return jsonify(response), 200
        
    except Exception as e:
        error_message = f'Error generating lyrics: {str(e)}'
        print(f"Error: {error_message}")
        return jsonify({
            'error': error_message
        }), 500

@app.route('/result/<request_id>', methods=['GET'])
def get_result(request_id):
    """Endpoint to check the status of a request or get results"""
    # print(f"Result check requested for ID: {request_id}")
    # print(f"Current results dictionary keys: {list(results.keys())}")
    
    if request_id not in results:
        print(f"Request ID {request_id} not found in results dictionary")
        return jsonify({'error': 'Request ID not found'}), 404
    
    result_data = results[request_id].copy()
    # print(f"Found result data: {result_data}")
    
    # Update queue position if still queued
    if result_data['status'] == Status.QUEUED.value:
        position = 0
        for i, (req_id, _) in enumerate(list(request_queue.queue)):
            if req_id == request_id:
                position = i
                break
        result_data['queue_position'] = position
        result_data['estimated_wait_time'] = f"~{position * 60} seconds"
    
    return jsonify(result_data)

@app.route('/download/<request_id>', methods=['GET'])
def download_song(request_id):
    """Download the generated song files"""
    print(f"\nDownload requested for request_id: {request_id}")
    print(f"Current results dictionary keys: {list(results.keys())}")
    
    if request_id not in results:
        print(f"Request ID {request_id} not found in results dictionary")
        return jsonify({'error': 'Request ID not found'}), 404
    
    result = results[request_id]
    print(f"Found result: {result}")
    
    if result['status'] != Status.COMPLETE.value:
        print(f"Request {request_id} status is {result['status']}, not complete")
        return jsonify({
            'error': 'Song generation not complete or failed',
            'status': result['status']
        }), 404
    
    # Get requested file type, default to wav since that's what's being generated
    file_type = request.args.get('type', 'wav')
    file_paths = result['file_paths']
    print(f"Looking for file type {file_type} in paths: {file_paths}")
    
    # If no specific type is requested and wav exists, prefer wav
    if file_type == 'wav' and any(f.endswith('.wav') for f in file_paths.keys()):
        for filename, relative_path in file_paths.items():
            if filename.endswith('.wav'):
                absolute_path = os.path.join(OUTPUT_BASE_DIR, relative_path)
                if os.path.exists(absolute_path):
                    print(f"Found WAV file: {absolute_path}")
                    return send_file(absolute_path, as_attachment=True)
    
    # Look for files of the requested type
    for filename, relative_path in file_paths.items():
        if filename.endswith(f'.{file_type}'):
            absolute_path = os.path.join(OUTPUT_BASE_DIR, relative_path)
            print(f"Checking file at: {absolute_path}")
            
            if os.path.exists(absolute_path):
                print(f"Found matching file: {absolute_path}")
                return send_file(absolute_path, as_attachment=True)
            else:
                print(f"Warning: File {absolute_path} not found on disk")
    
    # If we get here, no matching file was found
    available_types = set(os.path.splitext(f)[1][1:] for f in file_paths.keys())
    if available_types:
        return jsonify({
            'error': f'No {file_type} file found for this request. Available types: {list(available_types)}'
        }), 404
    else:
        return jsonify({'error': 'No output files found for this request'}), 404

@app.route('/repair/<request_id>', methods=['POST'])
def repair_request(request_id):
    """Endpoint to repair file paths for an existing request"""
    success, message = repair_request_paths(request_id)
    if success:
        return jsonify({'message': message, 'result': results[request_id]}), 200
    else:
        return jsonify({'error': message}), 404

def repair_request_paths(request_id):
    """Repair file paths for an existing request"""
    if request_id not in results:
        return False, "Request ID not found"
    
    result = results[request_id]
    output_dir = os.path.join(OUTPUT_BASE_DIR, request_id)
    
    if not os.path.exists(output_dir):
        return False, f"Output directory not found: {output_dir}"
    
    # Collect all result files
    result_files = {}
    print(f"Repairing paths for request {request_id}")
    print(f"Scanning output directory: {output_dir}")
    
    # Walk through all subdirectories
    for root, dirs, files in os.walk(output_dir):
        for filename in files:
            if filename.endswith((".json", ".wav", ".mid", ".mp3")):
                # Get path relative to OUTPUT_BASE_DIR
                full_path = os.path.join(root, filename)
                relative_path = os.path.relpath(full_path, OUTPUT_BASE_DIR)
                result_files[filename] = relative_path
                print(f"Found result file: {filename} at {relative_path}")
    
    if not result_files:
        return False, "No result files found in output directory"
    
    # Update the results dictionary
    result['file_paths'] = result_files
    result['output_dir'] = request_id
    save_results()
    
    return True, f"Successfully repaired paths for request {request_id}"

# Add repair function to check and fix paths on server start
def repair_all_requests():
    """Check and repair all requests on server start"""
    print("\nChecking and repairing existing requests...")
    repaired_count = 0
    failed_count = 0
    
    for request_id in list(results.keys()):
        result = results[request_id]
        if result['status'] == Status.COMPLETE.value and (not result.get('file_paths') or len(result['file_paths']) == 0):
            success, message = repair_request_paths(request_id)
            if success:
                repaired_count += 1
                print(f"Repaired request {request_id}")
            else:
                failed_count += 1
                print(f"Failed to repair request {request_id}: {message}")
    
    print(f"Repair complete: {repaired_count} repaired, {failed_count} failed")
    return repaired_count, failed_count

def infer_genres_from_prompt(prompt):
    """Infer multiple suitable genres from the prompt using the lyrics generator"""
    print("Inferring genres from prompt...")
    try:
        suggested_genres = lyrics_generator.infer_genres(prompt)
        
        # Validate and find closest matches for suggested genres
        validated_genres = []
        for genre in suggested_genres:
            if genre in VALID_GENRES:
                validated_genres.append(genre)
            else:
                closest_match = find_closest_genre(genre)
                if closest_match != 'pop':  # Avoid defaulting to pop
                    validated_genres.append(closest_match)
        
        # Ensure we have at least one genre
        if not validated_genres:
            validated_genres = ['pop']  # Default fallback
        
        print(f"Inferred genres: {validated_genres}")
        return validated_genres
    except Exception as e:
        print(f"Error in genre inference: {str(e)}")
        return ['pop']  # Default fallback on error

def generate_lyrics_with_genres(prompt, genres):
    """Generate lyrics that incorporate elements from specified genres"""
    print(f"Generating lyrics for genres: {genres}")
    try:
        lyrics = lyrics_generator.generate_lyrics_with_genres(prompt, genres)
        print("Genre-specific lyrics generated successfully")
        return lyrics
    except Exception as e:
        print(f"Error in genre-specific lyrics generation: {str(e)}")
        raise

@app.route('/generate_lyrics_with_genres', methods=['POST'])
def generate_lyrics_by_genres():
    """Endpoint to generate lyrics based on prompt and specified genres, then create the audio track"""
    request_data = request.json
    print(f"\n=== New lyrics with genres generation request ===")
    print(f"Received request data: {json.dumps(request_data, indent=2)}")
    
    # Validate required fields
    if 'prompt' not in request_data:
        print(f"Error: Missing required field 'prompt' in request")
        return jsonify({
            'error': 'Missing required field: prompt'
        }), 400
    
    # Initialize variables for genre handling
    validated_genres = []
    invalid_genres = []
    inferred_genres = False
    
    # Check if genres were provided
    if 'genres' in request_data and request_data['genres']:
        print("\nProcessing provided genres...")
        genres = request_data['genres']
        if not isinstance(genres, list):
            print(f"Error: Invalid genres format - expected list, got {type(genres)}")
            return jsonify({
                'error': 'Genres should be an array of strings'
            }), 400
        
        # Validate provided genres
        for genre in genres:
            if not isinstance(genre, str):
                print(f"Error: Invalid genre type: {genre} (should be a string)")
                return jsonify({
                    'error': f'Invalid genre type: {genre} (should be a string)'
                }), 400
            
            genre = genre.lower()
            print(f"Processing genre: {genre}")
            if genre in VALID_GENRES:
                validated_genres.append(genre)
                print(f"Genre '{genre}' is valid")
            else:
                # Try to find closest match
                closest_match = find_closest_genre(genre)
                if closest_match != 'pop':  # Avoid defaulting to pop
                    validated_genres.append(closest_match)
                    print(f"Found closest match for '{genre}': '{closest_match}'")
                else:
                    invalid_genres.append(genre)
                    print(f"Genre '{genre}' is invalid")
    
    # If no valid genres were provided or genres weren't provided at all, infer them
    if not validated_genres:
        print("\nNo valid genres provided, inferring from prompt...")
        validated_genres = infer_genres_from_prompt(request_data['prompt'])
        inferred_genres = True
        print(f"Inferred genres: {validated_genres}")
    
    try:
        print("\nStarting genre-specific lyrics generation...")
        lyrics = generate_lyrics_with_genres(request_data['prompt'], validated_genres)
        print(f"Generated lyrics: {lyrics}")
        
        # Create a request ID for tracking
        request_id = str(uuid.uuid4())
        print(f"\nGenerated request ID: {request_id}")
        
        # Prepare the request data for audio generation
        print("\nCreating YuE request with parameters:")
        yue_request = {
            'lyrics': lyrics,
            'genre': validated_genres[0],  # Use the first genre as primary
            'stage1_use_exl2': True,
            'stage2_use_exl2': True,
            'stage2_batch_size': 12,  # Set batch size
            'run_n_segments': 2,      # Number of segments to process
            'max_new_tokens': 3000,   # Maximum number of new tokens
            'repetition_penalty': 1.1,  # Control diversity and coherence
            'stage2_cache_size': 32768  # Cache size for stage 2
        }
        print(f"Default parameters set: {json.dumps(yue_request, indent=2)}")
        
        # Copy over any additional YuE parameters if provided
        for param in ['stage1_model', 'stage2_model', 'stage2_batch_size', 'max_new_tokens', 'repetition_penalty',
                     'stage1_cache_size', 'stage2_cache_size', 'stage1_cache_mode', 'stage2_cache_mode',
                     'stage1_no_guidance', 'keep_intermediate', 'disable_offload_model', 'cuda_idx']:
            if param in request_data:
                yue_request[param] = request_data[param]
                print(f"Overriding parameter {param}: {request_data[param]}")
        
        # Initialize result entry
        queue_position = request_queue.qsize()
        print(f"\nQueue status:")
        print(f"Current queue size: {queue_position}")
        results[request_id] = {
            'status': Status.QUEUED.value,
            'queue_position': queue_position,
            'queued_at': time.time(),
            'estimated_wait_time': queue_position * 60,
            'generated_lyrics': lyrics,
            'used_genres': validated_genres,
            'genres_were_inferred': inferred_genres,
            'lyrics_provider': lyrics_provider  # Include the provider used
        }
        save_results()
        print(f"Request {request_id} added to results dictionary")
        print(f"Current active requests: {list(results.keys())}")
        
        # Add to processing queue
        request_queue.put((request_id, yue_request))
        print(f"\nRequest {request_id} added to processing queue")
        print(f"Final YuE request configuration: {json.dumps(yue_request, indent=2)}")
        
        response = {
            'request_id': request_id,
            'status': Status.QUEUED.value,
            'queue_position': queue_position,
            'estimated_wait_time': f"~{queue_position * 60} seconds",
            'lyrics': lyrics,
            'used_genres': validated_genres,
            'lyrics_provider': lyrics_provider,
            'genres_were_inferred': inferred_genres,
            'download_instructions': {
                'check_status': f'/result/{request_id}',
                'download_when_ready': f'/download/{request_id}',
                'supported_formats': ['mp3', 'wav', 'mid']
            }
        }
        
        # Add information about genre handling
        if inferred_genres:
            response['genre_info'] = {
                'message': 'Genres were automatically inferred from the prompt',
                'inferred_genres': validated_genres
            }
        elif invalid_genres:
            response['warnings'] = {
                'invalid_genres': invalid_genres,
                'message': 'Some genres were not recognized and were omitted.'
            }
        
        print(f"\nResponse: {json.dumps(response, indent=2)}")
        print(f"=== End of lyrics with genres generation request ===\n")
        return jsonify(response), 200
        
    except Exception as e:
        error_message = f'Error processing request: {str(e)}'
        print(f"Error: {error_message}")
        return jsonify({
            'error': error_message,
            'status': Status.ERROR.value
        }), 500

@app.route('/system_prompt', methods=['GET'])
def get_system_prompt():
    """Endpoint to get the default system prompt for lyrics generation"""
    # Read from file each time using the lyrics generator helper
    current_prompt = lyrics_generator.read_lyrics_prompt(LYRICS_PROMPT_FILE, DEFAULT_LYRICS_PROMPT)
    
    return jsonify({
        'prompt': current_prompt,
        'provider': lyrics_provider
    })

@app.route('/system_prompt', methods=['PUT'])
def update_system_prompt():
    """Endpoint to update the default system prompt for lyrics generation"""
    if not request.is_json:
        return jsonify({'error': 'Content-Type must be application/json'}), 400
        
    data = request.json
    if 'prompt' not in data:
        return jsonify({'error': 'Missing required field: prompt'}), 400
        
    new_prompt = data['prompt']
    if not isinstance(new_prompt, str):
        return jsonify({'error': 'Prompt must be a string'}), 400
    
    # Save the prompt to a file using the lyrics generator helper
    success = lyrics_generator.write_lyrics_prompt(LYRICS_PROMPT_FILE, new_prompt)
    
    if not success:
        return jsonify({
            'message': 'Failed to save prompt to file'
        }), 500
    
    return jsonify({
        'message': 'System prompt updated successfully and saved to file',
        'prompt': new_prompt,
        'provider': lyrics_provider
    })

@app.route('/genre_prompt', methods=['GET'])
def get_genre_prompt():
    """Endpoint to get the default system prompt for genre extraction"""
    # Read from file each time using the lyrics generator helper
    current_prompt = lyrics_generator.read_genre_prompt(GENRE_PROMPT_FILE, DEFAULT_GENRE_PROMPT)
    
    return jsonify({
        'prompt': current_prompt,
        'provider': lyrics_provider
    })

@app.route('/genre_prompt', methods=['PUT'])
def update_genre_prompt():
    """Endpoint to update the default system prompt for genre extraction"""
    if not request.is_json:
        return jsonify({'error': 'Content-Type must be application/json'}), 400
        
    data = request.json
    if 'prompt' not in data:
        return jsonify({'error': 'Missing required field: prompt'}), 400
        
    new_prompt = data['prompt']
    if not isinstance(new_prompt, str):
        return jsonify({'error': 'Prompt must be a string'}), 400
    
    # Save the prompt to a file using the lyrics generator helper
    success = lyrics_generator.write_genre_prompt(GENRE_PROMPT_FILE, new_prompt)
    
    if not success:
        return jsonify({
            'message': 'Failed to save prompt to file'
        }), 500
    
    return jsonify({
        'message': 'Genre prompt updated successfully and saved to file',
        'prompt': new_prompt,
        'provider': lyrics_provider
    })

@app.route('/provider', methods=['GET'])
def get_provider():
    """Get the current lyrics provider"""
    return jsonify({
        'provider': lyrics_provider,
        'available_providers': ['gemini', 'anthropic']
    })

@app.route('/provider', methods=['POST'])
def set_provider():
    """Set the lyrics provider to use"""
    global lyrics_provider, lyrics_generator
    
    if not request.is_json:
        return jsonify({'error': 'Content-Type must be application/json'}), 400
    
    data = request.json
    if 'provider' not in data:
        return jsonify({'error': 'Missing required field: provider'}), 400
    
    new_provider = data['provider'].lower()
    if new_provider not in ['gemini', 'anthropic']:
        return jsonify({'error': 'Invalid provider. Supported providers: gemini, anthropic'}), 400
    
    # Verify we have the required API key
    if new_provider == 'gemini' and not google_api_key:
        return jsonify({
            'error': 'Cannot switch to Gemini: Google API key not configured',
            'current_provider': lyrics_provider
        }), 400
    
    if new_provider == 'anthropic' and not anthropic_api_key:
        return jsonify({
            'error': 'Cannot switch to Anthropic: Anthropic API key not configured',
            'current_provider': lyrics_provider
        }), 400
    
    # If requested provider is already active, just return success
    if new_provider == lyrics_provider:
        return jsonify({
            'message': f'Provider {new_provider} is already active',
            'provider': new_provider
        })
    
    try:
        # Get the appropriate API key
        api_key = google_api_key if new_provider == 'gemini' else anthropic_api_key
        
        # Initialize the new provider
        print(f"Switching lyrics provider from {lyrics_provider} to {new_provider}")
        new_generator = create_lyrics_generator(new_provider, api_key)
        
        # Update globals after successful initialization
        lyrics_provider = new_provider
        lyrics_generator = new_generator
        
        # Save the new provider to config file if it exists
        try:
            if os.path.exists(config_path):
                with open(config_path, 'r') as f:
                    config = json.load(f)
                
                config['lyrics_provider'] = new_provider
                
                with open(config_path, 'w') as f:
                    json.dump(config, f, indent=2)
                    print(f"Updated config file with new provider: {new_provider}")
        except Exception as e:
            print(f"Warning: Could not update config file: {e}")
        
        return jsonify({
            'message': f'Successfully switched provider to {new_provider}',
            'provider': new_provider
        })
    
    except Exception as e:
        error_message = f'Error switching provider: {str(e)}'
        print(f"Error: {error_message}")
        return jsonify({
            'error': error_message,
            'current_provider': lyrics_provider
        }), 500

if __name__ == '__main__':
    # Create necessary directories
    os.makedirs(OUTPUT_BASE_DIR, exist_ok=True)
    
    print(f"Starting server with:")
    print(f"Base directory: {BASE_DIR}")
    print(f"YuE directory: {YUE_DIR}")
    print(f"Source directory: {SRC_DIR}")
    print(f"Output directory: {OUTPUT_BASE_DIR}")
    print(f"Results file: {RESULTS_FILE}")
    print(f"Lyrics prompt file: {LYRICS_PROMPT_FILE}")
    print(f"Genre prompt file: {GENRE_PROMPT_FILE}")
    
    # Repair existing requests on startup
    repaired, failed = repair_all_requests()
    
    # Start the Flask app
    app.run(host='0.0.0.0', port=5000) 