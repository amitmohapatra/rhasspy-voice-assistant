# Rhasspy AI Avatar Assistant

Enterprise-grade voice-enabled AI assistant with 3D avatar, real-time conversation, and streaming responses.

## Features

- 🎤 **Voice Interaction**: Real-time speech-to-text and text-to-speech
- 🤖 **OpenAI Assistant API**: Powered by GPT-4 with streaming responses
- 👤 **3D Avatar**: Animated avatar with lip sync and emotions
- 🔊 **Wake Word Detection**: Hands-free activation with "Hey Rhasspy"
- 💬 **Modern Chat UI**: WhatsApp/ChatGPT-style interface with markdown support
- 🌐 **Multi-language**: Support for multiple languages
- 📊 **Enterprise Logging**: Structured logging with request tracking
- 🔄 **SSE Streaming**: Real-time responses with Server-Sent Events

## Quick Start

### Prerequisites

- Python 3.9+
- OpenAI API key
- ffmpeg (automatically installed by start script)

### Automated Setup (Recommended)

The easiest way to get started is using the automated start scripts:

**Linux/macOS:**
```bash
git clone <repository-url>
cd avatar-project
cp backend/.env.example backend/.env
# Edit backend/.env and add your OPENAI_API_KEY
./start_servers.sh
```

**Windows:**
```batch
git clone <repository-url>
cd avatar-project
copy backend\.env.example backend\.env
REM Edit backend\.env and add your OPENAI_API_KEY
start_servers.bat
```

The start script will:
- ✅ Create and activate a Python virtual environment
- ✅ Install all dependencies automatically
- ✅ Start ffmpeg installation in background (non-blocking)
- ✅ Launch backend server (http://localhost:5000)
- ✅ Launch frontend server (http://localhost:8000)
- ✅ Open your browser automatically

### Manual Setup (Advanced)

If you prefer manual control:

1. **Clone the repository**
```bash
   git clone <repository-url>
   cd avatar-project
```

2. **Set up virtual environment**
```bash
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. **Install dependencies**
```bash
   pip install -r backend/requirements.txt
   ```

4. **Install ffmpeg** (if not already installed)
   - macOS: `brew install ffmpeg`
   - Ubuntu/Debian: `sudo apt-get install ffmpeg`
   - Windows: `choco install ffmpeg` or download from [ffmpeg.org](https://ffmpeg.org/download.html)

5. **Configure environment**
```bash
   cp backend/.env.example backend/.env
   # Edit backend/.env and add your OPENAI_API_KEY
   ```

6. **Run backend** (from project root)
```bash
   cd backend
python app.py
```

7. **Run frontend** (in a new terminal, from project root)
```bash
   cd frontend
   python -m http.server 8000
   ```

8. **Open browser**
   ```
   http://localhost:8000
```

## Configuration

### Environment Variables

Create a `.env` file in the `backend` directory:

```env
# Required
OPENAI_API_KEY=your_openai_api_key_here

# Optional
TTS_VOICE=nova                    # OpenAI TTS voice (alloy, echo, fable, onyx, nova, shimmer)
LOG_LEVEL=INFO                    # Logging level (DEBUG, INFO, WARNING, ERROR)
WAKEWORD_THRESHOLD=0.5            # Wake word detection threshold (0.0-1.0)
```

### Logging Levels

- **DEBUG**: Detailed logs for development (verbose)
- **INFO**: Standard operational logs (recommended for production)
- **WARNING**: Warning messages only
- **ERROR**: Error messages only

## Usage

### Starting a Conversation

1. **Click "Rhasspy" button** or say **"Hey Rhasspy"**
2. Wait for the greeting
3. Speak your message
4. Listen to the response
5. Continue the conversation naturally

### Text Chat

- Type your message in the chat input
- Press Enter or click Send
- Responses stream in real-time

### Voice Chat

- Click the microphone button to start listening
- Speak your message
- System automatically detects when you finish
- Response plays automatically

## Architecture

See [ARCHITECTURE.md](ARCHITECTURE.md) for detailed system architecture, data flows, and design patterns.

### Key Components

**Backend**:
- Flask REST API with SSE streaming
- OpenAI Assistant API integration
- Speech-to-Text (Whisper)
- Text-to-Speech (OpenAI TTS)
- Wake word detection (openWakeWord)

**Frontend**:
- Vanilla JavaScript (no framework dependencies)
- Three.js for 3D avatar
- Real-time Voice Activity Detection
- SSE client for streaming responses
- Modern chat UI with markdown support

## API Endpoints

### Chat Endpoints
- `POST /api/chats/greeting` - Initial greeting (SSE)
- `POST /api/chats` - Text chat (SSE)

### Audio Endpoints
- `POST /api/audio` - Audio chat pipeline (SSE)
- `POST /api/audio/wake-word` - Wake word detection

### Assistant Management
- `GET /api/assistants` - List assistants
- `POST /api/assistants` - Create assistant
- `GET /api/assistants/<id>` - Get assistant
- `PATCH /api/assistants/<id>` - Update assistant
- `DELETE /api/assistants/<id>` - Delete assistant
- ... (21 endpoints total, see code for full list)

## Development

### Project Structure

```
avatar-project/
├── backend/
│   ├── app.py                 # Main Flask application
│   ├── config.py              # Configuration management
│   ├── config/                # Configuration files
│   │   └── defaults.json      # Default settings
│   ├── routes/                # API route blueprints
│   │   ├── chat_routes.py     # Chat endpoints
│   │   ├── audio_routes.py    # Audio endpoints
│   │   └── assistant_routes.py # Assistant management
│   ├── services/              # Business logic
│   │   ├── assistant_service.py
│   │   ├── audio_service.py
│   │   └── emotion_service.py
│   └── utils/                 # Shared utilities
│       ├── logging_utils.py
│       ├── log_config.py      # Logging setup
│       ├── streaming_utils.py
│       └── text_filters.py
├── frontend/
│   ├── index.html             # Main HTML
│   ├── app.js                 # Application initialization
│   ├── audio.js               # Audio management (VAD, recording)
│   ├── avatar.js              # 3D avatar rendering
│   ├── chat.js                # Chat UI
│   ├── assistant-manager.js   # Session management
│   ├── settings.js            # Settings panel
│   ├── ui-controller.js       # Mode management
│   ├── message-processor.js   # Message processing
│   ├── manual-mode-controller.js  # Manual mode logic
│   ├── rhasspy-mode-controller.js # Rhasspy mode logic
│   ├── styles.css             # Styling
│   └── vendor/                # Third-party libraries
│       └── webrtc-vad.min.js  # Voice Activity Detection
├── venv/                      # Python virtual environment (auto-created)
├── start_servers.sh           # Linux/macOS startup script
├── start_servers.bat          # Windows startup script
├── backend.log                # Backend logs (auto-created)
├── frontend.log               # Frontend logs (auto-created)
├── ffmpeg_install.log         # ffmpeg installation log (auto-created)
└── README.md
```

### Code Style

- **Backend**: PEP 8, type hints, docstrings
- **Frontend**: ESLint-compatible, JSDoc comments
- **Logging**: Structured with emoji prefixes for easy filtering
- **Error Handling**: Try-catch blocks, unique error IDs
- **Modularity**: DRY principles, single responsibility

### Testing

1. **Open browser console** (F12)
2. **Watch logs** for state transitions and errors
3. **Use incognito mode** for cache-free testing
4. **Check Network tab** for SSE streams
5. **Test error scenarios** (disconnect, invalid input)

## Troubleshooting

### Backend Issues

**Problem**: `ModuleNotFoundError`
- **Solution**: Ensure virtual environment is activated:
  ```bash
  source venv/bin/activate  # Linux/macOS
  venv\Scripts\activate.bat  # Windows
  ```
  Then reinstall: `pip install -r backend/requirements.txt`

**Problem**: `OpenAI API Error`
- **Solution**: Check API key in `backend/.env` file

**Problem**: `Port 5000 already in use`
- **Solution**: The start script automatically clears ports. If running manually:
  ```bash
  # Linux/macOS
  lsof -ti tcp:5000 | xargs kill -9
  
  # Windows
  netstat -ano | findstr :5000
  taskkill /PID <PID> /F
  ```

**Problem**: `ffmpeg not found`
- **Solution**: The start script installs ffmpeg in background. Check `ffmpeg_install.log` for status. Or install manually:
  - macOS: `brew install ffmpeg`
  - Ubuntu/Debian: `sudo apt-get install ffmpeg`
  - Windows: `choco install ffmpeg`

### Frontend Issues

**Problem**: `Failed to fetch`
- **Solution**: Ensure backend is running on `localhost:5000`

**Problem**: Browser cache issues
- **Solution**: Hard refresh (Ctrl+Shift+R) or use incognito mode

**Problem**: Microphone not working
- **Solution**: Grant microphone permissions in browser

**Problem**: Wake word not detecting
- **Solution**: Adjust `WAKEWORD_THRESHOLD` in `.env`

### Audio Issues

**Problem**: No audio playback
- **Solution**: Check browser audio permissions and volume

**Problem**: Choppy audio
- **Solution**: Check network connection and backend logs

**Problem**: Voice not detected
- **Solution**: Speak louder or adjust microphone sensitivity

## Performance

- **Response Time**: < 2s for text responses
- **Audio Latency**: < 3s for full audio pipeline
- **Wake Word**: < 100ms detection time
- **Streaming**: Real-time text and audio chunks
- **Memory**: < 200MB backend, < 100MB frontend

## Security

- API keys in environment variables (never committed)
- Input validation on all endpoints
- CORS configuration for production
- No sensitive data in logs
- Rate limiting ready

## License

[Your License Here]

## Support

For issues, questions, or contributions:
- Open an issue on GitHub
- Check [ARCHITECTURE.md](ARCHITECTURE.md) for technical details
- Review console logs for debugging

## Acknowledgments

- OpenAI for GPT-4 and Whisper APIs
- Three.js for 3D rendering
- openWakeWord for wake word detection
- Flask for backend framework
