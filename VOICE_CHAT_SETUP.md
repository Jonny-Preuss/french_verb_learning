# Voice Chat Setup

## Overview
The Voice Chat tab uses OpenAI's API for conversational French practice with minimal latency.

## Required API

You need an **OpenAI API key** to use this feature.

### Getting Your API Key

1. Go to [OpenAI Platform](https://platform.openai.com/)
2. Sign up or log in to your account
3. Navigate to [API Keys](https://platform.openai.com/api-keys)
4. Click "Create new secret key"
5. Copy the key (you won't be able to see it again!)

### Setting Up the API Key

**Option 1: Environment Variable (Recommended)**
```bash
export OPENAI_API_KEY="your-api-key-here"
```

Or add it to your `.env` file:
```
OPENAI_API_KEY=your-api-key-here
```

**Option 2: Enter in the App**
You can also enter the API key directly in the Configuration section of the Voice Chat tab.

## How It Works

1. **Recording**: Click the microphone button to record your French speech
2. **Whisper API**: Transcribes your speech to text (with French language detection)
3. **GPT-4**: Generates intelligent, contextual responses in French
4. **Text-to-Speech (TTS)**: Converts the response to natural-sounding French speech
5. **Playback**: Automatically plays the AI's response

## Features

- ✅ Browser-based audio recording (no local audio device configuration needed)
- ✅ Natural French conversation
- ✅ 6 different voice options (alloy, echo, fable, onyx, nova, shimmer)
- ✅ Conversation history with full context
- ✅ Customizable system prompt for different teaching styles

## Dependencies

The Voice Chat feature uses:
- `openai>=1.77.0` - OpenAI API client
- `audio-recorder-streamlit>=0.0.8` - Browser-based audio recording
- `streamlit>=1.44.1` - Web framework

These are automatically installed via `uv sync`.

## Cost Information

OpenAI charges per use (pay-as-you-go):
- **Whisper (transcription)**: ~$0.006 per minute of audio
- **GPT-4 (text generation)**: ~$0.03 per 1K input tokens, ~$0.06 per 1K output tokens
- **TTS (text-to-speech)**: ~$0.015 per 1K characters

A typical 5-minute conversation might cost approximately $0.15-0.30.

Check your [OpenAI usage dashboard](https://platform.openai.com/account/usage/overview) to monitor costs.

## Troubleshooting

**"streamlit-audiorec package not found" error:**
- This is fixed! We now use `audio-recorder-streamlit` which is more reliable
- Run `uv sync` to install all dependencies

**No audio recording?**
- Make sure your browser has microphone permissions
- Check your browser's address bar for a microphone icon
- Try a different browser if recording doesn't work

**API Error / "Invalid API Key"?**
- Check that your API key is valid at https://platform.openai.com/api-keys
- Ensure you have credits in your OpenAI account
- Check [OpenAI Status](https://status.openai.com/)

**Poor quality responses?**
- Speak clearly and in French
- Check your system prompt settings
- Try adjusting the voice option

## Tips for Better Learning

1. **Speak naturally** - The AI responds better to natural conversation
2. **Use the system prompt** - Customize it to match your learning style
3. **Ask for corrections** - Say "Corrige-moi" (correct me) for grammar help
4. **Request explanations** - Ask "Pourquoi?" (Why?) to learn grammar rules
5. **Keep conversations short** - 2-3 exchanges work better than long monologues
