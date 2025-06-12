# YuE Model Enhanced API - Curl Examples with Downloads

## 🎵 **NEW: Full Song Generation with Download URLs**

### **Option 1: Full Song Generation (Lyrics + Audio + Download)**

```bash
curl -X POST \
  "https://us-central1-aiplatform.googleapis.com/v1/projects/music-generation-prototype/locations/us-central1/endpoints/3577596432015687680:predict" \
  -H "Authorization: Bearer $(gcloud auth print-access-token)" \
  -H "Content-Type: application/json" \
  -d '{
    "instances": [
      {
        "data": {
          "prompt": "Write a complete pop song about chasing dreams and never giving up",
          "generate_audio": true
        }
      }
    ]
  }'
```

**Response will include download instructions:**
```json
{
  "predictions": [
    {
      "request_id": "abc-123-def",
      "lyrics": "Generated song lyrics...",
      "genre": "pop, upbeat, inspirational",
      "status": "queued",
      "download_instructions": {
        "status_url": "/result/abc-123-def",
        "download_url": "/download/abc-123-def",
        "note": "Check status_url periodically. Use download_url when status becomes 'complete'"
      }
    }
  ]
}
```

### **Option 2: Lyrics Only (Default)**

```bash
curl -X POST \
  "https://us-central1-aiplatform.googleapis.com/v1/projects/music-generation-prototype/locations/us-central1/endpoints/3577596432015687680:predict" \
  -H "Authorization: Bearer $(gcloud auth print-access-token)" \
  -H "Content-Type: application/json" \
  -d '{
    "instances": [
      {
        "data": {
          "prompt": "Write a complete pop song about chasing dreams and never giving up"
        }
      }
    ]
  }'
```

## 🔄 **Download Workflow**

### **Step 1: Request Full Song Generation**
```bash
curl -X POST \
  "https://us-central1-aiplatform.googleapis.com/v1/projects/music-generation-prototype/locations/us-central1/endpoints/3577596432015687680:predict" \
  -H "Authorization: Bearer $(gcloud auth print-access-token)" \
  -H "Content-Type: application/json" \
  -d '{
    "instances": [
      {
        "data": {
          "prompt": "Create a romantic ballad about eternal love under starlit skies",
          "generate_audio": true,
          "run_n_segments": 2
        }
      }
    ]
  }' | jq -r '.predictions[0].request_id'
```

### **Step 2: Check Status**
```bash
# Replace REQUEST_ID with the ID from step 1
REQUEST_ID="abc-123-def"

curl -X GET \
  "https://us-central1-aiplatform.googleapis.com/v1/projects/music-generation-prototype/locations/us-central1/endpoints/3577596432015687680/result/${REQUEST_ID}" \
  -H "Authorization: Bearer $(gcloud auth print-access-token)"
```

### **Step 3: Download When Ready**
```bash
# When status shows "complete", download the audio file
curl -X GET \
  "https://us-central1-aiplatform.googleapis.com/v1/projects/music-generation-prototype/locations/us-central1/endpoints/3577596432015687680/download/${REQUEST_ID}" \
  -H "Authorization: Bearer $(gcloud auth print-access-token)" \
  -o "my_song.wav"
```

## 🎛️ **Advanced Parameters**

You can customize the generation by adding these parameters:

```bash
curl -X POST \
  "https://us-central1-aiplatform.googleapis.com/v1/projects/music-generation-prototype/locations/us-central1/endpoints/3577596432015687680:predict" \
  -H "Authorization: Bearer $(gcloud auth print-access-token)" \
  -H "Content-Type: application/json" \
  -d '{
    "instances": [
      {
        "data": {
          "prompt": "Write an epic rock anthem about overcoming obstacles",
          "generate_audio": true,
          "run_n_segments": 3,
          "stage2_batch_size": 16,
          "max_new_tokens": 4000,
          "repetition_penalty": 1.05
        }
      }
    ]
  }'
```

## 🚨 **Important Notes**

1. **Audio Generation Takes Time**: Full songs typically take 2-5 minutes to generate
2. **Check Status Regularly**: Poll the status_url every 30 seconds until status is "complete"
3. **Download Links Expire**: Download your audio files promptly after generation
4. **Queue Position**: Response includes estimated wait time if there's a queue

## 📋 **Response Status Values**

- `"queued"`: Request is waiting in the generation queue
- `"processing"`: Audio generation has started
- `"generating_lyrics"`: Creating lyrics and musical characteristics
- `"generating_audio"`: Creating the audio track
- `"complete"`: Ready for download
- `"error"`: Generation failed (check error message)

## 🔧 **Troubleshooting**

- **"lyrics-only generation" note**: You forgot to set `"generate_audio": true`
- **Long wait times**: Server processes requests sequentially
- **404 on download**: Audio generation may have failed, check status first
- **401 errors**: Get a fresh access token with `gcloud auth print-access-token` 