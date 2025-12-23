# Supermemory Assistant

A full-stack personal assistant with dynamic, customizable modes, powered by Supermemory API for long-term memory, Google Gemini for intelligent responses, and web search capabilities.

## Features

### 🎯 Dynamic Assistant Modes
Create unlimited custom modes for different life roles! Each mode maintains its own chat history, memories, and persona while automatically borrowing relevant context from other modes.

- **Pre-built Templates**: Start with templates like Student, Parent, Job-Hunt, Fitness, Fashion
- **Custom Modes**: Create your own modes with custom names, emojis, descriptions, and base roles
- **Mode Isolation**: Each mode has separate chat history, memories, and memory graph visualization
- **Cross-Mode Intelligence**: The assistant automatically accesses relevant information from other modes when helpful

### ✨ Core Features

#### Memory & Context
- **Memory Integration**: Built-in Supermemory profiles, search, and write capabilities
- **Long-term Memory**: Persistent storage of conversations, facts, events, and documents
- **Memory Classification**: Automatic classification of memories by type (fact, event, document) and durability
- **Cross-Mode Context**: Intelligent borrowing of relevant context from other modes without merging personas

#### Chat & Interaction
- **Proactive Messaging**: Mode-specific conversation starters appear as regular chat messages when you start typing
- **Web Search**: Powered by Parallel.ai or Exa.ai for real-time information
- **Multiple Message Handling**: Batches rapid messages into single conversation turns
- **Tool Calling Visibility**: Real-time display of tools used (memory search, web search, etc.)
- **Markdown Rendering**: Rich text formatting in chat responses (bold, italics, lists, headings)

#### Memory Management
- **Memory View**: Browse all memories filtered by mode
- **Memory Editing**: Update or delete memories through an intuitive UI
- **Memory Graph**: Visual graph representation with two views:
  - **Advanced View**: Interactive visualization using `@supermemory/memory-graph` package
  - **Custom View**: Custom SVG-based graph with different node shapes (circles, squares, diamonds)
- **Refresh Button**: Reload memory graph data on demand

#### File & Document Processing
- **File Upload**: Upload documents (PDF, DOCX, XLSX, CSV, TXT) and images (with OCR)
- **Smart Summarization**: Automatically generates concise summaries instead of storing full file content
- **Memory Creation**: Extracted content is classified and stored as memories with proper mode tagging

#### Integrations & Connectors
- **Supermemory Connectors**: Direct integration with:
  - Google Drive
  - Notion
  - OneDrive
  - GitHub
  - Web Crawler
- **Calendar Import**: Upload `.ics` files to create event memories
- **OAuth Flow**: Secure authentication for connector services
- **Manual Sync**: Trigger manual syncs for connected services

#### Events & Scheduling
- **Upcoming Events**: Unified view of all events across all modes (user-defined, template, and default)
- **Event Extraction**: Automatic detection and classification of time-based memories
- **Clean Display**: Shows only event title and date/time, no duplicates

## Tech Stack

- **Backend**: Python + Flask
- **Frontend**: Next.js 14 + React + TypeScript
- **Memory**: Supermemory API v3
- **LLM**: Google Gemini 2.5 Flash
- **Web Search**: Parallel.ai / Exa.ai
- **Database**: SQLite (with SQLAlchemy ORM)
- **Authentication**: JWT tokens with bcrypt password hashing

## Project Structure

```
supermemory-assistant/
├── backend/
│   ├── app.py                    # Flask API server
│   ├── calendar_routes.py       # Calendar import routes
│   ├── models/                   # Database models
│   │   └── __init__.py          # User, Conversation, Message, Task, UserMode, Connector
│   ├── services/
│   │   ├── llm.py               # Gemini LLM integration
│   │   ├── memory_orchestrator.py  # Context building
│   │   ├── memory_classifier.py    # Memory classification
│   │   ├── supermemory_client.py   # Supermemory API client
│   │   ├── file_processor.py      # File upload & text extraction
│   │   └── integrations.py        # Connector integrations
│   ├── auth.py                  # Authentication utilities
│   ├── requirements.txt         # Python dependencies
│   └── .env.example             # Environment variables template
├── frontend/
│   ├── app/
│   │   ├── page.tsx             # Main page
│   │   ├── layout.tsx           # Root layout
│   │   └── login/
│   │       └── page.tsx         # Login page
│   ├── components/
│   │   ├── Chat.jsx             # Chat interface
│   │   ├── Memories.jsx        # Memory list view
│   │   ├── MemoryGraph.jsx     # Memory graph visualization
│   │   ├── ModeSelector.jsx    # Mode selection & creation
│   │   └── Connectors.jsx       # Connector management
│   ├── styles/                  # CSS modules
│   ├── lib/
│   │   ├── auth.ts             # Frontend auth utilities
│   │   └── axios.ts            # API client
│   ├── package.json
│   └── next.config.js
├── docs/
│   ├── CALENDAR_GUIDE.md       # How to get .ics files
│   ├── n8n/
│   │   └── payload-examples.md # n8n webhook examples
│   └── plan.md                 # Project plan
└── README.md
```

## Setup Instructions

### Prerequisites
- Python 3.8+
- Node.js 18+
- API Keys:
  - Google Gemini API key
  - Supermemory API key
  - Parallel.ai or Exa.ai API key (optional, for web search)
  - N8N_WEBHOOK_SECRET (optional, for n8n integration)

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
```env
GEMINI_API_KEY=your_gemini_api_key_here
SUPERMEMORY_API_KEY=your_supermemory_api_key_here
SUPERMEMORY_API_URL=https://api.supermemory.ai/v3
SUPERMEMORY_PROFILE_ID=default-profile
PARALLEL_API_KEY=your_parallel_api_key_here
EXA_API_KEY=your_exa_api_key_here
N8N_WEBHOOK_SECRET=your_n8n_secret_here  # Optional
DATABASE_URL=sqlite:///supermemory.db
SECRET_KEY=your-secret-key-change-in-production
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

### Authentication
- `POST /api/auth/signup` - User registration
- `POST /api/auth/login` - User login
- `GET /api/auth/me` - Get current user info

### Chat & Messaging
- `POST /api/chat` - Main chat endpoint
- `GET /api/proactive?mode=<mode>&userId=<userId>` - Get proactive message

### Modes Management
- `GET /api/modes` - Get all user-defined modes
- `POST /api/modes` - Create a new mode
- `DELETE /api/modes/<mode_key>` - Delete a mode
- `GET /api/mode-templates` - Get pre-built mode templates

### Memories
- `GET /api/memories?mode=<mode>&userId=<userId>` - Get all memories for a mode
- `DELETE /api/memories/<memory_id>` - Delete a memory
- `PUT /api/memories/<memory_id>` - Update a memory

### Memory Graph
- `GET /api/memory-graph?mode=<mode>&userId=<userId>` - Get memory graph data (nodes & edges)

### Events
- `GET /api/events/upcoming?userId=<userId>` - Get upcoming events from all modes

### File Upload
- `POST /api/upload` - Upload and process files (form-data: `file`, `mode`)
  - Supports: PDF, DOCX, XLSX, CSV, TXT, images (with OCR)
  - Returns: Summary-based memory (not full content)

### Connectors
- `GET /api/connectors` - List all connected services
- `POST /api/connectors/<provider>/connect` - Connect a service
- `POST /api/connectors/<provider>/callback` - OAuth callback handler
- `POST /api/connectors/<provider>/sync` - Manual sync trigger
- `DELETE /api/connectors/<provider>` - Disconnect a service

### Calendar
- `POST /api/calendar/import` - Import calendar events from `.ics` file (form-data: `file`, `mode`)

### n8n Integration (Advanced)
- `POST /api/n8n/ingest` - Webhook endpoint for n8n workflows
  - Header: `X-N8N-SECRET: <secret>`
  - Body: See `docs/n8n/payload-examples.md`

### Health Check
- `GET /api/health` - Health check endpoint

## Usage

### Getting Started

1. **Sign Up / Login**: Create an account or log in to your existing account
2. **Create or Select a Mode**: 
   - Choose from pre-built templates (Student, Parent, Job, etc.)
   - Or create a custom mode with your own name, emoji, and description
3. **Start Chatting**: Type messages in the chat interface
   - Proactive messages will appear automatically when you start typing
   - Tool calls are shown by default to see what the assistant is doing

### Managing Modes

- **Add Mode**: Click "+ Add Mode" button, fill in details or select a template
- **Switch Modes**: Use the mode selector dropdown to switch between modes
- **Delete Mode**: Click the delete icon next to a mode (only for user-created modes)

### File Uploads

1. Click the paperclip icon in the chat input
2. Select a file or drag and drop
3. The file will be processed and a summary-based memory will be created
4. Full content is stored in metadata for reference, but only the summary is displayed

### Connectors

1. Navigate to the "Connectors" tab
2. Click "Connect" on any available service (Google Drive, Notion, etc.)
3. Complete OAuth flow if required
4. Click "Sync" to manually trigger a sync
5. For Calendar: Upload an `.ics` file using the Calendar card
   - See `docs/CALENDAR_GUIDE.md` for instructions on getting `.ics` files

### Upcoming Events

- Navigate to the "Upcoming" tab
- View all events from all modes in a unified timeline
- Events show only title and date/time (no duplicates)

### Memory Graph

- Navigate to the "Memory Graph" tab
- Toggle between "Advanced View" (interactive) and "Custom View" (SVG-based)
- Click nodes to see details
- Use the refresh button to reload graph data

## Key Features Explained

### Dynamic Modes
Each mode is completely isolated in the UI (separate chat history, memories, graph) but the underlying AI can intelligently borrow relevant context from other modes. This gives you separation where you need it and intelligence where it helps.

### Proactive Messaging
The assistant analyzes your recent memories and generates mode-specific, actionable conversation starters. These appear as regular chat messages (not floating UI) when you start typing or switch modes.

### File Upload Summarization
When you upload a file, the system:
1. Extracts text content (PDF, images via OCR, DOCX, etc.)
2. Uses LLM to generate a concise 2-3 sentence summary
3. Stores the summary as the memory text (what you see)
4. Stores full content in metadata for reference

### Cross-Mode Context Borrowing
All modes automatically borrow relevant context from other modes. This is built-in and automatic - you don't need to configure it. The AI decides what's relevant based on the conversation.

### Memory Classification
Memories are automatically classified by:
- **Type**: fact, event, document
- **Durability**: short-term, medium-term, long-term
- **Expiry**: Automatic expiry dates for time-sensitive memories

### Calendar Import
Upload `.ics` files to create event memories. Events are automatically:
- Classified as type "event"
- Tagged with `event_date` metadata
- Included in the "Upcoming Events" view
- Deduplicated to prevent multiple entries

## Environment Variables

| Variable | Description | Required |
|----------|-------------|----------|
| `GEMINI_API_KEY` | Google Gemini API key for LLM | Yes |
| `SUPERMEMORY_API_KEY` | Supermemory API key | Yes |
| `SUPERMEMORY_API_URL` | Supermemory API base URL | No (defaults to v3) |
| `SUPERMEMORY_PROFILE_ID` | Default profile ID | No |
| `PARALLEL_API_KEY` | Parallel.ai API key | No (for web search) |
| `EXA_API_KEY` | Exa.ai API key | No (for web search) |
| `N8N_WEBHOOK_SECRET` | Secret for n8n webhook authentication | No |
| `DATABASE_URL` | Database connection string | No (defaults to SQLite) |
| `SECRET_KEY` | Flask secret key for sessions | Yes |

## Development

### Backend Development
- The Flask server runs in debug mode by default
- API endpoints are CORS-enabled for frontend communication
- All Supermemory API calls include comprehensive error handling
- Database migrations are handled automatically on startup

### Frontend Development
- Uses Next.js 14 with App Router
- React components are modular and reusable
- CSS modules for component styling
- TypeScript for type safety

### Database Schema
- **Users**: User accounts with authentication
- **UserModes**: User-defined custom modes
- **Connectors**: Connected external services
- **Conversations**: Chat conversation history
- **Messages**: Individual chat messages
- **Tasks**: Task management (future feature)

## Contributing

This project was built as part of the Supermemory challenge. Contributions to improve the memory graph visualization, add new connectors, or enhance the mode system are welcome!

## License

MIT

## Acknowledgments

- [Supermemory](https://supermemory.ai) for the memory API
- [Google Gemini](https://ai.google.dev/) for intelligent responses
- [Parallel.ai](https://parallel.ai) and [Exa.ai](https://exa.ai) for web search capabilities
- [Next.js](https://nextjs.org/) for the frontend framework

## Additional Documentation

- [Calendar Import Guide](docs/CALENDAR_GUIDE.md) - How to get `.ics` files from various calendar services
- [n8n Payload Examples](docs/n8n/payload-examples.md) - Examples for n8n webhook integration
- [Project Plan](docs/plan.md) - Original project plan and requirements
