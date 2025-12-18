# Quick Setup Guide

## Step 1: Backend Setup

```bash
cd backend
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

Create a `.env` file in the `backend` directory with:
```
GEMINI_API_KEY=your_key_here
SUPERMEMORY_API_KEY=your_key_here
SUPERMEMORY_API_URL=https://api.supermemory.ai/v3
PARALLEL_API_KEY=your_key_here  # Optional
EXA_API_KEY=your_key_here  # Optional
```

Run the backend:
```bash
# Option 1: Use python3 (recommended if you have a python alias)
python3 app.py

# Option 2: Use the run script
./run.sh

# Option 3: Use the venv Python directly
./venv/bin/python3 app.py
```

## Step 2: Frontend Setup

In a new terminal:
```bash
cd frontend
npm install
npm run dev
```

## Step 3: Access the App

Open your browser to `http://localhost:3000`

## Getting API Keys

1. **Google Gemini**: Get from https://ai.google.dev/ (click "Get API Key")
2. **Supermemory**: Get from https://supermemory.ai (sign up and get API key)
3. **Parallel.ai**: Get from https://parallel.ai (optional)
4. **Exa.ai**: Get from https://exa.ai (optional)

## Troubleshooting

- **Backend won't start**: Make sure all dependencies are installed and `.env` file exists
- **Frontend can't connect**: Ensure backend is running on port 5001
- **API errors**: Check that your API keys are correct and have sufficient credits
- **CORS errors**: The backend has CORS enabled, but if issues persist, check the Flask-CORS configuration

