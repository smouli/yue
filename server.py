import os
import subprocess
import tempfile
from flask import Flask, request, jsonify, send_file, Response
import werkzeug
import uuid
import glob
import threading
import time
import json

# Print current working directory for debugging
print(f"Current working directory: {os.getcwd()}")

# Define base directory as the script's location
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
print(f"Base directory: {BASE_DIR}")

app = Flask(__name__)

# Configure upload settings
UPLOAD_FOLDER = os.path.join(BASE_DIR, 'uploads')
OUTPUT_FOLDER = os.path.join(BASE_DIR, 'output')
PROMPT_FOLDER = os.path.join(BASE_DIR, 'prompt_egs')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(OUTPUT_FOLDER, exist_ok=True)

# Make the prompt directories if they don't exist
os.makedirs(PROMPT_FOLDER, exist_ok=True)

# Default genre and lyrics text content
DEFAULT_GENRE = "pop upbeat"
DEFAULT_LYRICS = """[verse]
This is a sample verse
With some sample lyrics
For demonstration only

[chorus]
This is a sample chorus
That repeats in the song
"""

# Track active generation tasks
active_tasks = {}

@app.route('/', methods=['GET'])
def documentation():
    """Provide API documentation"""
    return jsonify({
        "api_version": "1.0",
        "endpoints": {
            "/generate": {
                "method": "POST",
                "description": "Generate music from an audio file using YuE model",
                "parameters": {
                    "file": "Required. WAV or MP3 audio file to use as prompt",
                    "genre": f"Optional. Genre description. Default: '{DEFAULT_GENRE}'",
                    "lyrics": "Optional. Lyrics in proper format with [verse], [chorus] sections"
                },
                "returns": "Generated MP3 audio file or error JSON"
            },
            "/status/{request_id}": {
                "method": "GET", 
                "description": "Check the status of a generation task",
                "returns": "JSON with status information"
            }
        },
        "example_curl": "curl -X POST -F 'file=@your_sample.mp3' -F 'genre=pop upbeat' -F 'lyrics=[verse]\\nYour lyrics here\\n\\n[chorus]\\nYour chorus here' http://localhost:5000/generate"
    })

def find_output_file(output_dir):
    """Find the generated output file in the output directory structure"""
    # First check the main output dir
    for file in os.listdir(output_dir):
        if file.endswith('.mp3'):
            return os.path.join(output_dir, file)
    
    # Check in the vocoder/mix directory
    vocoder_mix_dir = os.path.join(output_dir, 'vocoder', 'mix')
    if os.path.exists(vocoder_mix_dir):
        for file in os.listdir(vocoder_mix_dir):
            if file.endswith('.mp3'):
                return os.path.join(vocoder_mix_dir, file)
    
    # Fall back to any MP3 file in any subdirectory
    for mp3_file in glob.glob(f"{output_dir}/**/*.mp3", recursive=True):
        return mp3_file
    
    return None

def run_generation_task(request_id, cmd, output_dir, input_file_path):
    """Run the generation task in a separate thread and track its progress"""
    try:
        active_tasks[request_id] = {
            'status': 'running',
            'start_time': time.time(),
            'command': ' '.join(cmd),
            'output': ''
        }
        
        # Run the command with real-time output capture
        process = subprocess.Popen(
            cmd, 
            stdout=subprocess.PIPE, 
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            universal_newlines=True
        )
        
        output = []
        for line in process.stdout:
            output.append(line)
            active_tasks[request_id]['output'] = ''.join(output)
        
        process.wait()
        return_code = process.returncode
        
        if return_code == 0:
            output_file_path = find_output_file(output_dir)
            if output_file_path:
                active_tasks[request_id] = {
                    'status': 'completed',
                    'end_time': time.time(),
                    'output_file': output_file_path,
                    'return_code': return_code,
                    'output': ''.join(output)
                }
            else:
                active_tasks[request_id] = {
                    'status': 'failed',
                    'end_time': time.time(),
                    'error': 'No output file generated',
                    'return_code': return_code,
                    'output': ''.join(output)
                }
        else:
            active_tasks[request_id] = {
                'status': 'failed',
                'end_time': time.time(),
                'error': f'Command failed with return code {return_code}',
                'return_code': return_code,
                'output': ''.join(output)
            }
    except Exception as e:
        active_tasks[request_id] = {
            'status': 'failed',
            'end_time': time.time(),
            'error': str(e),
            'output': ''.join(output) if 'output' in locals() else ''
        }
    finally:
        # Clean up uploaded file
        if os.path.exists(input_file_path):
            try:
                os.remove(input_file_path)
            except:
                pass

@app.route('/status/<request_id>', methods=['GET'])
def get_status(request_id):
    """Get the status of a generation task"""
    if request_id in active_tasks:
        task_info = active_tasks[request_id].copy()
        
        # If task is complete and has an output file, provide a download URL
        if task_info['status'] == 'completed' and 'output_file' in task_info:
            task_info['download_url'] = f"/download/{request_id}"
        
        # Don't return full command output unless specifically requested
        if 'full_output' not in request.args and 'output' in task_info:
            # Truncate output if it's too long
            if len(task_info['output']) > 1000:
                task_info['output'] = task_info['output'][:1000] + "...[truncated]"
        
        return jsonify(task_info)
    else:
        return jsonify({'error': 'Task not found'}), 404

@app.route('/download/<request_id>', methods=['GET'])
def download_result(request_id):
    """Download the generated file for a completed task"""
    if request_id in active_tasks and active_tasks[request_id]['status'] == 'completed':
        output_file_path = active_tasks[request_id]['output_file']
        if os.path.exists(output_file_path):
            return send_file(
                output_file_path,
                mimetype="audio/mpeg",
                as_attachment=True,
                download_name=f"generated_music_{request_id}.mp3"
            )
        else:
            return jsonify({'error': 'Output file not found'}), 404
    else:
        return jsonify({'error': 'No completed task found with this ID'}), 404

@app.route('/generate', methods=['POST'])
def generate_music():
    # Check if the post request has the file part
    if 'file' not in request.files:
        return jsonify({'error': 'No file part in the request'}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400
    
    # Get parameters from request
    genre = request.form.get('genre', DEFAULT_GENRE)
    lyrics = request.form.get('lyrics', DEFAULT_LYRICS)
    
    # Generate a unique ID for this request
    request_id = str(uuid.uuid4())
    
    # Save the uploaded file
    filename = werkzeug.utils.secure_filename(file.filename)
    file_extension = os.path.splitext(filename)[1].lower()
    
    if file_extension not in ['.wav', '.mp3']:
        return jsonify({'error': 'Only WAV or MP3 files are allowed'}), 400
    
    input_file_path = os.path.join(UPLOAD_FOLDER, f"{request_id}{file_extension}")
    file.save(input_file_path)
    
    # Create genre.txt and lyrics.txt files
    genre_path = os.path.join(PROMPT_FOLDER, 'genre.txt')
    lyrics_path = os.path.join(PROMPT_FOLDER, 'lyrics.txt')
    
    with open(genre_path, 'w') as f:
        f.write(genre)
    
    with open(lyrics_path, 'w') as f:
        f.write(lyrics)
    
    # Save the uploaded file as both vocal and instrumental tracks
    # (since the API seems to need both for dual tracks mode)
    vocal_track_path = os.path.join(PROMPT_FOLDER, f'pop.00001.Vocals{file_extension}')
    instrumental_track_path = os.path.join(PROMPT_FOLDER, f'pop.00001.Instrumental{file_extension}')
    
    # Copy the uploaded file to both paths
    import shutil
    shutil.copy(input_file_path, vocal_track_path)
    shutil.copy(input_file_path, instrumental_track_path)
    
    # Set the output directory for this request
    output_dir = os.path.join(OUTPUT_FOLDER, request_id)
    os.makedirs(output_dir, exist_ok=True)
    
    # Build the command
    cmd = [
        'python', 'infer.py',
        '--cuda_idx', '0',
        '--stage1_model', 'm-a-p/YuE-s1-7B-anneal-en-icl',
        '--stage2_model', 'm-a-p/YuE-s2-1B-general',
        '--genre_txt', genre_path,
        '--lyrics_txt', lyrics_path,
        '--run_n_segments', '2',
        '--stage2_batch_size', '4',
        '--output_dir', output_dir,
        '--max_new_tokens', '3000',
        '--repetition_penalty', '1.1',
        '--use_dual_tracks_prompt',
        '--vocal_track_prompt_path', vocal_track_path,
        '--instrumental_track_prompt_path', instrumental_track_path,
        '--prompt_start_time', '0',
        '--prompt_end_time', '30'
    ]
    
    # Run the generation task in a separate thread
    thread = threading.Thread(
        target=run_generation_task,
        args=(request_id, cmd, output_dir, input_file_path)
    )
    thread.daemon = True
    thread.start()
    
    # Return a response with the request ID for status checking
    return jsonify({
        'request_id': request_id,
        'status': 'started',
        'status_url': f"/status/{request_id}"
    })

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True) 