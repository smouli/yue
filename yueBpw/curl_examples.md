# YuE Model API - Curl Examples

## 🚀 **Basic Curl Request**

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

## 🎵 **Full Song Generation Examples**

### Example 1: Romantic Ballad
```bash
curl -X POST \
  "https://us-central1-aiplatform.googleapis.com/v1/projects/music-generation-prototype/locations/us-central1/endpoints/3577596432015687680:predict" \
  -H "Authorization: Bearer $(gcloud auth print-access-token)" \
  -H "Content-Type: application/json" \
  -d '{
    "instances": [
      {
        "data": {
          "prompt": "Create a romantic ballad with verses, chorus, and bridge about eternal love under starlit skies. Include emotional depth and poetic imagery."
        }
      }
    ]
  }'
```

### Example 2: Upbeat Pop Song
```bash
curl -X POST \
  "https://us-central1-aiplatform.googleapis.com/v1/projects/music-generation-prototype/locations/us-central1/endpoints/3577596432015687680:predict" \
  -H "Authorization: Bearer $(gcloud auth print-access-token)" \
  -H "Content-Type: application/json" \
  -d '{
    "instances": [
      {
        "data": {
          "prompt": "Write an energetic pop anthem about overcoming challenges, with catchy verses, powerful chorus, and an inspiring bridge. Make it motivational and uplifting."
        }
      }
    ]
  }'
```

### Example 3: Story-Driven Song
```bash
curl -X POST \
  "https://us-central1-aiplatform.googleapis.com/v1/projects/music-generation-prototype/locations/us-central1/endpoints/3577596432015687680:predict" \
  -H "Authorization: Bearer $(gcloud auth print-access-token)" \
  -H "Content-Type: application/json" \
  -d '{
    "instances": [
      {
        "data": {
          "prompt": "Create a complete folk song that tells the story of a small town, with multiple verses describing different characters and their lives, connected by a reflective chorus about community and belonging."
        }
      }
    ]
  }'
```

## 🔧 **For Postman**

**Method:** POST

**URL:** 
```
https://us-central1-aiplatform.googleapis.com/v1/projects/music-generation-prototype/locations/us-central1/endpoints/3577596432015687680:predict
```

**Headers:**
```
Authorization: Bearer YOUR_ACCESS_TOKEN
Content-Type: application/json
```

**Body (JSON):**
```json
{
  "instances": [
    {
      "data": {
        "prompt": "Write a complete song about [YOUR_THEME_HERE] with verses, chorus, and bridge"
      }
    }
  ]
}
```

## 🎯 **Getting Access Token**

**Option 1: Using gcloud (Dynamic)**
```bash
# Get token and use in curl
TOKEN=$(gcloud auth print-access-token)
curl -X POST \
  "https://us-central1-aiplatform.googleapis.com/v1/projects/music-generation-prototype/locations/us-central1/endpoints/3577596432015687680:predict" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"instances": [{"data": {"prompt": "Your song prompt here"}}]}'
```

**Option 2: Get token manually for Postman**
```bash
gcloud auth print-access-token
```
Copy the output and use it in Postman's Authorization header.

## 📋 **Expected Response Format**

```json
{
  "predictions": [
    {
      "lyrics": "[verse]\nYour generated song lyrics...\n[chorus]\n...",
      "genre": "pop, upbeat, inspirational",
      "genre_breakdown": {
        "genre": "pop",
        "instrument": "",
        "mood": "upbeat",
        "gender": "",
        "timbre": ""
      },
      "prompt": "Your original prompt",
      "status": "success",
      "timestamp": "2025-06-11T06:31:54.696353"
    }
  ],
  "deployedModelId": "4304793631417434112",
  "model": "projects/799748678255/locations/us-central1/models/7804072949698265088",
  "modelDisplayName": "yue-model-flask-fixed",
  "modelVersionId": "1"
}
```

## 💡 **Tips for Better Song Generation**

1. **Be Specific:** Include song structure (verse, chorus, bridge)
2. **Set the Mood:** Specify genre, tempo, emotion
3. **Add Context:** Describe the story or theme
4. **Request Completeness:** Ask for "complete song" or "full song with multiple verses"

## 🚨 **Troubleshooting**

- **401 Unauthorized:** Get a fresh access token with `gcloud auth print-access-token`
- **403 Forbidden:** Check your GCP permissions
- **500 Server Error:** Check Google Cloud Logs for model errors
- **Timeout:** Large requests may take 30-60 seconds 