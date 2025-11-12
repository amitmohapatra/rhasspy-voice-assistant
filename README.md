# Rhasspy AI Avatar Assistant

Enterprise-grade voice-enabled AI assistant with 3D avatar, real-time conversation, and streaming responses.

## Features

- 🎤 **Voice Interaction**: Real-time speech-to-text and text-to-speech
- 🤖 **OpenAI Assistant API**: Powered by GPT-4, GPT-4o, o1, o3-mini with streaming responses
- 👤 **3D Avatar**: Animated avatar with lip sync and emotions
- 🔊 **Wake Word Detection**: Hands-free activation with "Hey Rhasspy"
- 💬 **Modern Chat UI**: WhatsApp/ChatGPT-style interface with markdown support
- 🌐 **Multi-language**: Support for multiple languages
- 📊 **Enterprise Logging**: Structured logging with request tracking
- 🔄 **SSE Streaming**: Real-time responses with Server-Sent Events
- 🧠 **Assistant Management**: Create, edit, and manage AI assistants with custom instructions
- 📚 **Knowledge Bases**: Upload files to vector stores for enhanced context
- 🔧 **Settings Panel**: Comprehensive UI for managing assistants, knowledge bases, and files

## Quick Start

### Prerequisites

- **Python 3.9+** (must be installed and on PATH)
- **pip** (must be installed)
- **OpenAI API key**
- **ffmpeg** (automatically installed by start script if missing)

### Automated Setup (Recommended)

The easiest way to get started is using the automated start scripts. The scripts assume Python and pip are already installed.

**Linux/macOS:**
```bash
git clone <repository-url>
cd avatar-project
cp backend/.env.example backend/.env
# Edit backend/.env and add your OPENAI_API_KEY
chmod +x START_SERVERS.sh
./START_SERVERS.sh
```

**Windows:**
```batch
git clone <repository-url>
cd avatar-project
copy backend\.env.example backend\.env
REM Edit backend\.env and add your OPENAI_API_KEY
START_SERVERS.bat
```

The start script will automatically:
- ✅ **Kill processes** on ports 5000 and 8000 if they're busy
- ✅ **Install ffmpeg** if not found (via Homebrew, apt-get, dnf, yum, pacman, Chocolatey, or winget)
- ✅ **Create and activate** a Python virtual environment
- ✅ **Install all dependencies** automatically
- ✅ **Launch backend server** (http://localhost:5000)
- ✅ **Launch frontend server** (http://localhost:8000)

After starting, access the application at: **http://localhost:8000**

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
   - Fedora: `sudo dnf install ffmpeg`
   - Windows: `choco install ffmpeg` or `winget install Gyan.FFmpeg`

5. **Configure environment**
```bash
cp backend/.env.example backend/.env
# Edit backend/.env and add your OPENAI_API_KEY
```

6. **Kill processes on ports** (if needed)
```bash
# Linux/macOS
lsof -ti tcp:5000 | xargs kill -9
lsof -ti tcp:8000 | xargs kill -9

# Windows (PowerShell)
Get-NetTCPConnection -LocalPort 5000 -State Listen | ForEach-Object { Stop-Process -Id $_.OwningProcess -Force }
Get-NetTCPConnection -LocalPort 8000 -State Listen | ForEach-Object { Stop-Process -Id $_.OwningProcess -Force }
```

7. **Run backend** (from project root)
```bash
cd backend
python app.py
```

8. **Run frontend** (in a new terminal, from project root)
```bash
cd frontend
python -m http.server 8000
```

9. **Open browser**
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

### Managing Assistants

Click the **Settings** button (☰) to access the settings panel:

- **Assistants Tab**: Create, edit, activate, and delete AI assistants
  - Configure model (GPT-4, GPT-4o, o1, o3-mini, etc.)
  - Set custom instructions
  - Enable/disable tools (File Search, Code Interpreter)
  - Attach knowledge bases (vector stores)
  - Configure reasoning effort for o1/o3 models

- **Knowledge Bases Tab**: Manage vector stores
  - Create new knowledge bases
  - Rename knowledge bases
  - Delete knowledge bases
  - View file counts

- **Files Tab**: Manage files in knowledge bases
  - Upload files (PDF, TXT, MD, CSV, JSONL, HTML)
  - View uploaded files
  - Remove files from knowledge bases

**Note**: OpenAI API allows only **1 knowledge base per assistant**. The UI enforces this limitation.

## Architecture

### Key Components

**Backend**:
- Flask REST API with SSE streaming
- OpenAI Assistant API integration
- Speech-to-Text (Whisper)
- Text-to-Speech (OpenAI TTS)
- Wake word detection (openWakeWord)
- Vector store and file management

**Frontend**:
- Vanilla JavaScript (no framework dependencies)
- Three.js for 3D avatar
- Real-time Voice Activity Detection
- SSE client for streaming responses
- Modern chat UI with markdown support
- Settings panel for assistant/knowledge base management

## API Endpoints

### Chat Endpoints
- `POST /api/chats/greeting` - Initial greeting (SSE)
- `POST /api/chats` - Text chat (SSE)

### Audio Endpoints
- `POST /api/audio` - Audio chat pipeline (SSE)
- `POST /api/audio/wake-word` - Wake word detection

### Assistant Management
- `GET /api/assistants` - List all assistants
- `POST /api/assistants` - Create new assistant
- `GET /api/assistants/<id>` - Get assistant details
- `PUT /api/assistants/<id>` - Update assistant
- `DELETE /api/assistants/<id>` - Delete assistant

### Vector Store Management
- `GET /api/vector-stores` - List all vector stores
- `POST /api/vector-stores` - Create new vector store
- `GET /api/vector-stores/<id>` - Get vector store details
- `PUT /api/vector-stores/<id>` - Update vector store name
- `DELETE /api/vector-stores/<id>` - Delete vector store
- `GET /api/vector-stores/<id>/files` - List files in vector store
- `POST /api/vector-stores/<id>/files` - Add file to vector store
- `DELETE /api/vector-stores/<id>/files/<file_id>` - Remove file from vector store

### File Management
- `GET /api/files` - List all files
- `POST /api/files` - Upload file
- `GET /api/files/<id>` - Get file details
- `DELETE /api/files/<id>` - Delete file

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
│   │   └── assistant_routes.py # Assistant & vector store management
│   ├── services/              # Business logic
│   │   ├── assistant_service.py # OpenAI Assistant API wrapper
│   │   ├── audio_service.py   # Audio processing (STT/TTS)
│   │   └── emotion_service.py # Emotion analysis
│   └── utils/                 # Shared utilities
│       ├── logging_utils.py   # Request/response logging
│       ├── log_config.py      # Logging setup
│       ├── streaming_utils.py # SSE streaming helpers
│       └── text_filters.py    # Text filtering
├── frontend/
│   ├── index.html             # Main HTML
│   ├── app.js                 # Application initialization
│   ├── audio.js               # Audio management (VAD, recording)
│   ├── avatar.js              # 3D avatar rendering
│   ├── chat.js                # Chat UI
│   ├── assistant-manager.js   # Assistant API client
│   ├── settings.js            # Settings panel UI
│   ├── ui-controller.js       # Mode management
│   ├── message-processor.js   # Message processing
│   ├── manual-mode-controller.js  # Manual mode logic
│   ├── rhasspy-mode-controller.js # Rhasspy mode logic
│   ├── styles.css             # Styling
│   └── models/                # 3D models
│       └── indian_woman_in_saree.glb
├── venv/                      # Python virtual environment (auto-created)
├── START_SERVERS.sh           # Linux/macOS startup script
├── START_SERVERS.bat          # Windows startup script
├── backend.log                # Backend logs (auto-created)
├── backend_errors.log          # Backend error logs (auto-created)
├── frontend.log                # Frontend logs (auto-created)
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

### Startup Issues

**Problem**: `Python is not installed`
- **Solution**: Install Python 3.9+ from [python.org](https://www.python.org/downloads/) and ensure it's on PATH

**Problem**: `pip is not available`
- **Solution**: Python 3.9+ includes pip. If missing, install it: `python -m ensurepip --upgrade`

**Problem**: `Port 5000/8000 already in use`
- **Solution**: The start script automatically kills processes on these ports. If running manually:
  ```bash
  # Linux/macOS
  lsof -ti tcp:5000 | xargs kill -9
  lsof -ti tcp:8000 | xargs kill -9
  
  # Windows (PowerShell)
  Get-NetTCPConnection -LocalPort 5000 -State Listen | ForEach-Object { Stop-Process -Id $_.OwningProcess -Force }
  Get-NetTCPConnection -LocalPort 8000 -State Listen | ForEach-Object { Stop-Process -Id $_.OwningProcess -Force }
  ```

**Problem**: `ffmpeg not found`
- **Solution**: The start script installs ffmpeg automatically. Check `ffmpeg_install.log` for status. Or install manually:
  - macOS: `brew install ffmpeg`
  - Ubuntu/Debian: `sudo apt-get install ffmpeg`
  - Windows: `choco install ffmpeg` or `winget install Gyan.FFmpeg`

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

**Problem**: `BadRequestError: Invalid 'limit'`
- **Solution**: OpenAI API has limits. The backend automatically caps limit values to 100.

### Frontend Issues

**Problem**: `Failed to fetch`
- **Solution**: Ensure backend is running on `localhost:5000`

**Problem**: Browser cache issues
- **Solution**: Hard refresh (Ctrl+Shift+R or Cmd+Shift+R) or use incognito mode

**Problem**: Microphone not working
- **Solution**: Grant microphone permissions in browser

**Problem**: Wake word not detecting
- **Solution**: Adjust `WAKEWORD_THRESHOLD` in `.env` (lower = more sensitive)

**Problem**: UI not updating after operations
- **Solution**: The UI automatically refreshes after operations. If issues persist, check browser console for errors.

### Audio Issues

**Problem**: No audio playback
- **Solution**: Check browser audio permissions and volume

**Problem**: Choppy audio
- **Solution**: Check network connection and backend logs

**Problem**: Voice not detected
- **Solution**: Speak louder or adjust microphone sensitivity

### Assistant/Knowledge Base Issues

**Problem**: `Only 1 knowledge base can be selected per assistant`
- **Solution**: This is an OpenAI API limitation. Each assistant can have only one vector store attached.

**Problem**: File counts not updating
- **Solution**: The UI refreshes automatically after file operations. If counts are stale, wait a few seconds or manually refresh.

**Problem**: Assistant update fails when changing model
- **Solution**: OpenAI doesn't support changing the model of an existing assistant. Create a new assistant with the desired model instead.

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
- Check console logs for debugging
- Review backend logs in `backend.log` and `backend_errors.log`

## Acknowledgments

- OpenAI for GPT-4, Whisper, and Assistant APIs
- Three.js for 3D rendering
- openWakeWord for wake word detection
- Flask for backend framework
