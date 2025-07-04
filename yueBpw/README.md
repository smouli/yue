# YuE Server

This server provides a REST API for generating lyrics and songs using YuE and AI language models.

## New Feature: Interoperable LyricsGenerator Support

The system now supports multiple AI providers for lyrics generation:

- **Claude** (Anthropic) - Default provider with automatic model selection
- **Gemini** (Google)

### Configuration

To configure the API keys and provider, create a `config.json` file in the root directory:

```json
{
  "google_api_key": "your_google_api_key_here",
  "anthropic_api_key": "your_anthropic_api_key_here", 
  "lyrics_provider": "anthropic"
}
```

You can also set these values as environment variables:
- `GOOGLE_API_KEY`
- `ANTHROPIC_API_KEY`
- `LYRICS_PROVIDER`

### Claude Model Selection

The system now includes automatic model selection for Anthropic's Claude. It will try the following models in order:

1. claude-3-7-sonnet-20250219
2. claude-3-5-sonnet-20240620
3. claude-3-5-sonnet
4. claude-3-sonnet
5. claude-3-haiku
6. claude-instant

This ensures that the system will work even as Anthropic updates their model lineup.

### Prompt Files

The system uses two prompt files for lyrics generation:

- `lyrics_prompt.txt` - Contains the system prompt for lyrics generation
- `genre_prompt.txt` - Contains the system prompt for genre extraction

These files are read and written by the LyricsGenerator classes. You can customize them using the API endpoints:

```bash
# Get the current lyrics prompt
curl -X GET http://localhost:5000/system_prompt

# Update the lyrics prompt
curl -X PUT http://localhost:5000/system_prompt \
  -H "Content-Type: application/json" \
  -d '{"prompt": "Your custom lyrics prompt here"}'

# Get the current genre prompt
curl -X GET http://localhost:5000/genre_prompt

# Update the genre prompt
curl -X PUT http://localhost:5000/genre_prompt \
  -H "Content-Type: application/json" \
  -d '{"prompt": "Your custom genre prompt here"}'
```

### Switching Providers at Runtime

You can switch between providers at runtime using the `/provider` endpoint:

```bash
# Get current provider
curl -X GET http://localhost:5000/provider

# Switch to Anthropic
curl -X POST http://localhost:5000/provider \
  -H "Content-Type: application/json" \
  -d '{"provider": "anthropic"}'

# Switch to Gemini
curl -X POST http://localhost:5000/provider \
  -H "Content-Type: application/json" \
  -d '{"provider": "gemini"}'
```

### API Endpoints

All endpoints now include information about the provider used for lyrics generation in their responses:

- `/generate_track` - Generate a complete track from a prompt
- `/generate_lyrics` - Generate only lyrics from a prompt
- `/generate_lyrics_with_genres` - Generate lyrics incorporating specific genres
- `/provider` - Get or set the active lyrics provider
- `/system_prompt` - Get or update the lyrics generation prompt
- `/genre_prompt` - Get or update the genre extraction prompt

## Installation

1. Clone this repository
2. Install the required dependencies:
   ```bash
   pip install flask google-generativeai anthropic
   ```
3. Create a `config.json` file with your API keys
4. Run the server:
   ```bash
   python server.py
   ```

The server will be available at `http://localhost:5000`. 