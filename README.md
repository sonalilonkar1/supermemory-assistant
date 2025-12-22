# Supermemory Assistant

A full-stack personal assistant with three specialized modes, powered by Supermemory API for long-term memory, Google Gemini for intelligent responses, and web search capabilities.

## Features

### 🎯 Three Assistant Modes
- **🎓 Student Assistant**: Help with homework, study planning, deadlines, and academic advice
- **👨‍👩‍👧 Parent / Family Planner**: Help with family planning, kids' activities, scheduling, and organization
- **💼 Job-Hunt Assistant**: Help with job applications, interview prep, career advice, and networking

### ✨ Core Features
- **Memory Integration**: Built-in Supermemory profiles, search, and write capabilities
- **Web Search**: Powered by Parallel.ai or Exa.ai for real-time information
- **Proactive Messaging**: Initiates conversations based on user context and recent memories
- **Memory Management**: View, edit, and delete memories through an intuitive UI
- **Memory Visualization**: Visual graph representation of memories and their relationships
- **Multiple Message Handling**: Batches rapid messages into single conversation turns
- **Tool Calling Visibility**: Real-time display of tools used (memory search, web search, etc.)
- **Multiple Response Messages**: Splits long responses into multiple messages for clarity

## Tech Stack

- **Backend**: Python + Flask
- **Frontend**: React + Vite
- **Memory**: Supermemory API
- **LLM**: Google Gemini Pro
- **Web Search**: Parallel.ai / Exa.ai

## Project Structure

```
supermemory-assistant/
├── backend/
│   ├── app.py              # Flask API server
│   ├── requirements.txt    # Python dependencies
│   └── .env.example        # Environment variables template
├── frontend/
│   ├── src/
│   │   ├── components/     # React components
│   │   │   ├── Chat.jsx
│   │   │   ├── Memories.jsx
│   │   │   ├── MemoryGraph.jsx
│   │   │   └── ModeSelector.jsx
│   │   ├── App.jsx
│   │   └── main.jsx
│   ├── package.json
│   └── vite.config.js
└── README.md
```

## Setup Instructions

### Prerequisites
- Python 3.8+
- Node.js 16+
- API Keys:
  - Google Gemini API key
  - Supermemory API key
  - Parallel.ai or Exa.ai API key (optional, for web search)

### Backend Setup

1. Navigate to the backend directory:
```bash
cd backend
```

2. Create a virtual environment:
```bash
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Create a `.env` file:
```bash
cp .env.example .env
```

5. Edit `.env` and add your API keys:
```
GEMINI_API_KEY=your_gemini_api_key_here
SUPERMEMORY_API_KEY=your_supermemory_api_key_here
SUPERMEMORY_API_URL=https://api.supermemory.ai/v3
SUPERMEMORY_PROFILE_ID=default-profile
PARALLEL_API_KEY=your_parallel_api_key_here
EXA_API_KEY=your_exa_api_key_here
```

6. Run the Flask server:
```bash
python app.py
```

The backend will run on `http://localhost:5001`

### Frontend Setup

1. Navigate to the frontend directory:
```bash
cd frontend
```

2. Install dependencies:
```bash
npm install
```

3. Start the development server:
```bash
npm run dev
```

The frontend will run on `http://localhost:3000`

## API Endpoints

### `GET /api/health`
Health check endpoint.

### `POST /api/chat`
Main chat endpoint.

**Request:**
```json
{
  "userId": "user123",
  "mode": "student",
  "messages": ["Hello", "How are you?"],
  "useSearch": false
}
```

**Response:**
```json
{
  "replies": [
    "Hello! I'm here to help...",
    "I can assist with..."
  ],
  "toolsUsed": [
    {"name": "memory.search", "status": "success"},
    {"name": "memory.write", "status": "success"}
  ]
}
```

### `GET /api/proactive?mode=student&userId=user123`
Get proactive message based on recent memories.

**Response:**
```json
{
  "message": "You mentioned a midterm next week. Want help planning revision?"
}
```

### `GET /api/memories?mode=student&userId=user123`
Get all memories for a user and mode.

### `DELETE /api/memories/:id`
Delete a specific memory.

### `PUT /api/memories/:id`
Update a memory.

**Request:**
```json
{
  "text": "Updated memory text",
  "metadata": {"mode": "student"}
}
```

## Usage

1. **Select a Mode**: Choose between Student, Parent, or Job mode using the mode selector
2. **Start Chatting**: Type messages in the chat interface
3. **Use Web Search**: Toggle "Use Web Search" for queries requiring real-time information
4. **View Memories**: Navigate to the Memories tab to see all stored memories
5. **Manage Memories**: Edit or delete memories as needed
6. **Explore Graph**: View the Memory Graph to see relationships between memories

## Key Features Explained

### Multiple Rapid Messages
The frontend batches messages sent within 1.5 seconds into a single conversation turn, as specified in the requirements.

### Proactive Messaging
When you open the app, the assistant analyzes recent memories and suggests conversation starters relevant to your current context.

### Memory Graph
The memory graph visualizes memories as nodes, with connections based on mode and temporal proximity. For a more advanced visualization, integrate the `@supermemory/memory-graph` package.

## Development

### Backend Development
- The Flask server runs in debug mode by default
- API endpoints are CORS-enabled for frontend communication
- All Supermemory API calls include error handling

### Frontend Development
- Uses Vite for fast development
- React components are modular and reusable
- CSS modules for component styling

## Environment Variables

| Variable | Description | Required |
|----------|-------------|----------|
| `GEMINI_API_KEY` | Google Gemini API key for LLM | Yes |
| `SUPERMEMORY_API_KEY` | Supermemory API key | Yes |
| `SUPERMEMORY_API_URL` | Supermemory API base URL | No (defaults to v3) |
| `SUPERMEMORY_PROFILE_ID` | Default profile ID | No |
| `PARALLEL_API_KEY` | Parallel.ai API key | No (for web search) |
| `EXA_API_KEY` | Exa.ai API key | No (for web search) |

## Contributing

This project was built as part of the Supermemory challenge. Contributions to improve the memory graph visualization and overall design are welcome!

## License

MIT

## Acknowledgments

- [Supermemory](https://supermemory.ai) for the memory API
- [Google Gemini](https://ai.google.dev/) for intelligent responses
- [Parallel.ai](https://parallel.ai) and [Exa.ai](https://exa.ai) for web search capabilities



## New features
- Calendar import: POST /api/calendar/import (upload .ics) or use the Connectors tab to import .ics files and create event memories (type=event, event_date).
- Tool visibility: tool calls are shown by default in chat (no toggle needed).
- File upload: upload docs/images to create memories.

## Calendar import (quick steps)
- In Connectors, use the "Calendar (.ics)" card to upload an .ics file.
- Backend endpoint: POST /api/calendar/import (form-data: file=.ics, mode=<mode>).

## Tool visibility
- Chat now shows tools used (memory.search, memory.write, web.search) by default.
