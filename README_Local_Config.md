# Local Whisper STT Configuration

This integration has been modified to work with a local Whisper service instead of OpenAI's cloud API.

## Configuration

Add the following to your `configuration.yaml`:

```yaml
stt:
  - platform: openai_stt
    api_url: "http://sanjeev-debian-llm-vm:9000"  # Your local Whisper server URL
```

## Configuration Options

- `api_url` (optional): URL of your local Whisper service. Default: `http://sanjeev-debian-llm-vm:9000`

## Changes Made

1. Removed API key requirement (no authentication needed for local service)
2. Changed default API URL to local server
3. Updated API endpoint from `/audio/transcriptions` to `/asr`
4. Modified request format to match local Whisper API
5. Added PCM to WAV conversion function
6. Updated error handling for text responses instead of JSON
7. Changed timeout to 30 seconds for local processing
8. Updated manifest to reflect local polling instead of cloud polling

## Local Whisper Service

Your local Whisper service should accept POST requests to `/asr` with:
- Form data containing `audio_file` (WAV format)
- Query parameters: `encode=true`, `task=transcribe`, `output=txt`
- Returns plain text transcription

## Supported Audio Formats

- Formats: WAV, OGG
- Codecs: PCM, OPUS  
- Bit rates: 16-bit
- Sample rates: 16000 Hz
- Channels: Mono

The component automatically converts raw PCM audio data to WAV format before sending to your local service.
