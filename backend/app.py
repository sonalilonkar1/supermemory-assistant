from flask import Flask, request, jsonify
from flask_cors import CORS
import os
from dotenv import load_dotenv
import google.genai as genai
from datetime import datetime, timezone
import requests
import json
import uuid
from typing import List, Dict
from models import db, User, Conversation, Message, Task, UserProfile
from services.memory_orchestrator import build_context_for_turn
from services.llm import call_gemini
from services.memory_classifier import classify_memory
from services.supermemory_client import upsert_profile_memory, get_profile_memory, create_memory
from auth import (
    hash_password, verify_password, generate_token, 
    verify_token, get_user_from_token, generate_user_id, init_bcrypt
)

load_dotenv()

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL', 'sqlite:///supermemory.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'your-secret-key-change-in-production')

# Initialize extensions
db.init_app(app)
init_bcrypt(app)
CORS(app, 
     supports_credentials=True,
     origins=["http://localhost:3000", "http://127.0.0.1:3000"],
     allow_headers=["Content-Type", "Authorization"],
     methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"])

# Create tables
with app.app_context():
    db.create_all()

# Configuration
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
SUPERMEMORY_API_KEY = os.getenv('SUPERMEMORY_API_KEY')
SUPERMEMORY_API_URL = os.getenv('SUPERMEMORY_API_URL', 'https://api.supermemory.ai/v3')
PARALLEL_API_KEY = os.getenv('PARALLEL_API_KEY')
EXA_API_KEY = os.getenv('EXA_API_KEY')

# Validate required API keys
if not GEMINI_API_KEY:
    print("WARNING: GEMINI_API_KEY not set. Chat functionality will not work.")
if not SUPERMEMORY_API_KEY:
    print("WARNING: SUPERMEMORY_API_KEY not set. Memory functionality will not work.")

# Initialize Gemini client
if GEMINI_API_KEY:
    client = genai.Client(api_key=GEMINI_API_KEY)
    # Use gemini-2.5-flash (fast) or gemini-2.5-pro (better quality)
    # Available models: gemini-2.5-flash, gemini-2.5-pro, gemini-pro-latest
    model_name = 'gemini-2.5-flash'  # Fast and efficient, or use 'gemini-2.5-pro' for better quality
else:
    client = None
    model_name = None

# Default profile ID - can be customized per user
DEFAULT_PROFILE_ID = os.getenv('SUPERMEMORY_PROFILE_ID', 'default-profile')

def get_supermemory_headers():
    """Get headers for Supermemory API requests"""
    # Supermemory API uses x-api-key header, but also supports Authorization Bearer
    return {
        'x-api-key': SUPERMEMORY_API_KEY,
        'Authorization': f'Bearer {SUPERMEMORY_API_KEY}',
        'Content-Type': 'application/json'
    }

def search_memories(profile_id, query, mode=None, limit=5):
    """Search memories using Supermemory API"""
    # Build container tags
    container_tags = [profile_id] if profile_id else []
    if mode:
        container_tags = [f"{profile_id}-{mode}"]
    
    try:
        # Try /search/search endpoint (v3 format)
        url = f'{SUPERMEMORY_API_URL}/search/search'
        payload = {
            'query': query,
            'limit': limit,
            'containerTags': container_tags
        }
        
        response = requests.post(
            url,
            headers=get_supermemory_headers(),
            json=payload
        )
        response.raise_for_status()
        data = response.json()
        # Handle different response formats
        if 'results' in data:
            return data
        elif 'documents' in data:
            return {'results': data.get('documents', [])}
        else:
            return {'results': data if isinstance(data, list) else []}
    except requests.exceptions.HTTPError as e:
        # Try alternative endpoint format if first fails
        if e.response.status_code == 400 or e.response.status_code == 404:
            try:
                # Try /search endpoint (simpler format)
                url = f'{SUPERMEMORY_API_URL}/search'
                payload = {
                    'query': query,
                    'limit': limit,
                    'containerTags': container_tags
                }
                
                response = requests.post(
                    url,
                    headers=get_supermemory_headers(),
                    json=payload
                )
                response.raise_for_status()
                data = response.json()
                if 'results' in data:
                    return data
                elif 'documents' in data:
                    return {'results': data.get('documents', [])}
                else:
                    return {'results': data if isinstance(data, list) else []}
            except Exception as e2:
                error_detail = e2.response.text if hasattr(e2, 'response') and hasattr(e2.response, 'text') else str(e2)
                print(f"Error searching memories (fallback): {e2}")
                print(f"Response: {error_detail}")
        else:
            error_detail = e.response.text if hasattr(e, 'response') and hasattr(e.response, 'text') else str(e)
            print(f"Error searching memories: {e}")
            print(f"Response: {error_detail}")
    except Exception as e:
        print(f"Error searching memories: {e}")
    # Return empty results instead of failing - chat will work without memory search
    return {'results': []}

# create_memory function is now imported from services.supermemory_client
# The old local function has been removed to avoid conflicts

def get_memories(profile_id, mode=None, limit=50):
    """Get memories for a profile"""
    try:
        # Supermemory API v3 uses /documents/documents endpoint with POST
        url = f'{SUPERMEMORY_API_URL}/documents/documents'
        payload = {
            'page': 1,
            'limit': limit,
            'sort': 'createdAt',
            'order': 'desc',
            'containerTags': [profile_id]  # Use containerTags instead of profileId
        }
        if mode:
            payload['containerTags'] = [f"{profile_id}-{mode}"]
        
        response = requests.post(
            url,
            headers=get_supermemory_headers(),
            json=payload
        )
        response.raise_for_status()
        data = response.json()
        # Handle response format
        if 'documents' in data:
            return {'memories': data.get('documents', [])}
        elif isinstance(data, list):
            return {'memories': data}
        else:
            return {'memories': []}
    except requests.exceptions.HTTPError as e:
        # Fallback: try GET /memories endpoint (older API format)
        if e.response.status_code == 404:
            try:
                url = f'{SUPERMEMORY_API_URL}/memories'
                params = {
                    'profileId': profile_id,
                    'limit': limit
                }
                if mode:
                    params['tags'] = mode
                response = requests.get(
                    url,
                    headers=get_supermemory_headers(),
                    params=params
                )
                response.raise_for_status()
                data = response.json()
                return {'memories': data.get('memories', data if isinstance(data, list) else [])}
            except Exception as e2:
                print(f"Error getting memories (fallback): {e2}")
                return {'memories': []}
        else:
            print(f"Error getting memories: {e}")
            return {'memories': []}
    except Exception as e:
        print(f"Error getting memories: {e}")
        return {'memories': []}

def delete_memory(memory_id):
    """Delete a memory using Supermemory API"""
    try:
        url = f'{SUPERMEMORY_API_URL}/memories/{memory_id}'
        response = requests.delete(
            url,
            headers=get_supermemory_headers()
        )
        response.raise_for_status()
        return True
    except Exception as e:
        print(f"Error deleting memory: {e}")
        return False

def update_memory(memory_id, text=None, metadata=None):
    """Update a memory using Supermemory API"""
    try:
        url = f'{SUPERMEMORY_API_URL}/memories/{memory_id}'
        payload = {}
        if text:
            payload['text'] = text
        if metadata:
            payload['metadata'] = metadata
        
        response = requests.put(
            url,
            headers=get_supermemory_headers(),
            json=payload
        )
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"Error updating memory: {e}")
        return None

def web_search_parallel(query):
    """Search the web using Parallel.ai"""
    try:
        url = 'https://api.parallel.ai/v1/search'
        headers = {
            'Authorization': f'Bearer {PARALLEL_API_KEY}',
            'Content-Type': 'application/json'
        }
        payload = {
            'query': query,
            'max_results': 5
        }
        response = requests.post(url, headers=headers, json=payload)
        response.raise_for_status()
        data = response.json()
        return data.get('results', [])
    except Exception as e:
        print(f"Error with Parallel.ai search: {e}")
        return []

def web_search_exa(query):
    """Search the web using Exa.ai"""
    try:
        url = 'https://api.exa.ai/search'
        headers = {
            'x-api-key': EXA_API_KEY,
            'Content-Type': 'application/json'
        }
        payload = {
            'query': query,
            'num_results': 5,
            'type': 'neural'
        }
        response = requests.post(url, headers=headers, json=payload)
        response.raise_for_status()
        data = response.json()
        return data.get('results', [])
    except Exception as e:
        print(f"Error with Exa.ai search: {e}")
        return []

def web_search(query, provider='parallel'):
    """Unified web search function"""
    if provider == 'exa' and EXA_API_KEY:
        return web_search_exa(query)
    elif PARALLEL_API_KEY:
        return web_search_parallel(query)
    return []

def write_back_memories(user_id: str, role: str, user_message: str, llm_response: str, context_bundle: Dict) -> List[str]:
    """Write back memories from conversation with classification"""
    memory_ids = []
    
    # Create session summary memory
    summary_text = f"User asked: {user_message[:150]}. Assistant provided guidance on this topic."
    classification = classify_memory(role, summary_text)
    
    metadata = {
        'mode': role,
        'source': 'chat',
        'createdAt': datetime.now(timezone.utc).isoformat(),
        'userId': user_id,
        'durability': classification.get('durability', 'medium'),
        'expires_at': classification.get('expires_at')
    }
    
    print(f"[Write Back] Creating summary memory: {summary_text[:80]}...")
    result = create_memory(user_id, summary_text, metadata, role=role)
    if result and result.get('id'):
        memory_ids.append(result['id'])
        print(f"[Write Back] ✅ Summary memory created: {result.get('id')}")
    else:
        print(f"[Write Back] ❌ Summary memory creation failed (result: {result})")
    
    # Extract important facts from response (simple heuristic)
    keywords = ['applied', 'deadline', 'exam', 'event', 'meeting']
    has_keywords = any(keyword in llm_response.lower() for keyword in keywords)
    print(f"[Write Back] Checking for important facts. Keywords found: {has_keywords}")
    
    if has_keywords:
        fact_text = f"Important: {llm_response[:200]}"
        fact_classification = classify_memory(role, fact_text)
        fact_metadata = {
            'mode': role,
            'source': 'chat',
            'type': 'fact',
            'createdAt': datetime.now(timezone.utc).isoformat(),
            'userId': user_id,
            'durability': fact_classification.get('durability', 'medium'),
            'expires_at': fact_classification.get('expires_at')
        }
        
        print(f"[Write Back] Creating fact memory: {fact_text[:80]}...")
        fact_result = create_memory(user_id, fact_text, fact_metadata, role=role)
        if fact_result and fact_result.get('id'):
            memory_ids.append(fact_result['id'])
            print(f"[Write Back] ✅ Fact memory created: {fact_result.get('id')}")
        else:
            print(f"[Write Back] ❌ Fact memory creation failed (result: {fact_result})")
    
    return memory_ids

@app.route('/api/health', methods=['GET'])
def health():
    """Health check endpoint"""
    return jsonify({'status': 'ok'})

# Authentication endpoints
@app.route('/api/auth/signup', methods=['POST'])
def signup():
    """User registration endpoint"""
    try:
        data = request.json
        email = data.get('email', '').strip().lower()
        password = data.get('password', '')
        name = data.get('name', '').strip()
        
        # Validation
        if not email or not password:
            return jsonify({'error': 'Email and password are required'}), 400
        
        if len(password) < 6:
            return jsonify({'error': 'Password must be at least 6 characters'}), 400
        
        # Check if user exists
        existing_user = User.query.filter_by(email=email).first()
        if existing_user:
            return jsonify({'error': 'User with this email already exists'}), 400
        
        # Create new user
        user_id = generate_user_id()
        password_hash = hash_password(password)
        
        new_user = User(
            id=user_id,
            email=email,
            password_hash=password_hash,
            name=name or email.split('@')[0]
        )
        
        db.session.add(new_user)
        db.session.commit()
        
        # Generate token
        token = generate_token(user_id)
        
        return jsonify({
            'token': token,
            'user': new_user.to_dict()
        }), 201
        
    except Exception as e:
        db.session.rollback()
        print(f"Error in signup: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': 'Failed to create account'}), 500

@app.route('/api/auth/login', methods=['POST'])
def login():
    """User login endpoint"""
    try:
        data = request.json
        email = data.get('email', '').strip().lower()
        password = data.get('password', '')
        
        if not email or not password:
            return jsonify({'error': 'Email and password are required'}), 400
        
        # Find user
        user = User.query.filter_by(email=email).first()
        if not user:
            return jsonify({'error': 'Invalid email or password'}), 401
        
        # Verify password
        if not verify_password(user.password_hash, password):
            return jsonify({'error': 'Invalid email or password'}), 401
        
        # Generate token
        token = generate_token(user.id)
        
        return jsonify({
            'token': token,
            'user': user.to_dict()
        }), 200
        
    except Exception as e:
        print(f"Error in login: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': 'Failed to login'}), 500

@app.route('/api/auth/me', methods=['GET'])
def get_current_user():
    """Get current authenticated user"""
    try:
        user = get_user_from_token(request)
        if not user:
            return jsonify({'error': 'Not authenticated'}), 401
        
        return jsonify({'user': user.to_dict()}), 200
    except Exception as e:
        print(f"Error getting current user: {e}")
        return jsonify({'error': 'Failed to get user'}), 500

@app.route('/api/chat', methods=['POST'])
def chat():
    """Main chat endpoint with orchestrator-based context engineering"""
    try:
        # Get authenticated user or use default
        user = get_user_from_token(request)
        user_id = user.id if user else 'default'
        
        data = request.json
        # Override with authenticated user if available
        if not user:
            user_id = data.get('userId', 'default')
        mode = data.get('mode', 'student')
        messages = data.get('messages', [])
        use_search = data.get('useSearch', False)
        
        # Join multiple rapid messages into one
        user_message = ' '.join(messages) if isinstance(messages, list) else messages
        
        # Build context bundle using orchestrator
        context_bundle = build_context_for_turn(user_id, mode, user_message)
        
        # Web search if requested
        web_results = []
        web_context = ''
        if use_search or any(keyword in user_message.lower() for keyword in ['search', 'latest', 'news', 'find']):
            web_results = web_search(user_message)
            if web_results:
                web_context = '\n'.join([
                    f"- {result.get('title', '')}: {result.get('snippet', result.get('text', ''))}"
                    for result in web_results[:3]
                ])
                context_bundle['web_search'] = web_context
        
        # Call Gemini with context bundle
        try:
            llm_response, tool_traces = call_gemini(
                user_id=user_id,
                role=mode,
                message=user_message,
                context_bundle=context_bundle
            )
            
            if web_results:
                tool_traces.append({'name': 'web.search', 'status': 'success'})
        except Exception as gemini_error:
            error_str = str(gemini_error)
            if 'quota' in error_str.lower() or '429' in error_str:
                llm_response = f"I'm sorry, but I've reached my API quota limit. Please check your Google Cloud billing or try again later."
                tool_traces = [{'name': 'gemini', 'status': 'error', 'error': 'quota_exceeded'}]
            elif 'rate_limit' in error_str.lower():
                llm_response = f"I'm experiencing rate limits. Please wait a moment and try again."
                tool_traces = [{'name': 'gemini', 'status': 'error', 'error': 'rate_limit'}]
            else:
                llm_response = f"I encountered an issue connecting to the AI service. Please check your API configuration or try again later."
                tool_traces = [{'name': 'gemini', 'status': 'error', 'error': str(gemini_error)}]
            print(f"Gemini API error: {gemini_error}")
        
        # Split response into multiple messages if it contains clear sections
        replies = [llm_response]
        if len(llm_response) > 200 and ('\n\n' in llm_response or '**' in llm_response or '##' in llm_response):
            parts = llm_response.split('\n\n')
            if len(parts) > 1:
                filtered_parts = [part.strip() for part in parts if part.strip() and len(part.strip()) > 20]
                if len(filtered_parts) > 1:
                    replies = filtered_parts
        
        # Write back memories with classification
        print(f"[Chat] Writing back memories for user_id={user_id}, mode={mode}")
        memory_ids = write_back_memories(user_id, mode, user_message, llm_response, context_bundle)
        print(f"[Chat] Memory creation result: {len(memory_ids)} memories created (IDs: {memory_ids})")
        
        # Save conversation history to database
        conversation_id = None
        if user_id != 'default':
            try:
                # Get or create conversation for this user and mode
                conversation = Conversation.query.filter_by(
                    user_id=user_id,
                    mode=mode
                ).order_by(Conversation.updated_at.desc()).first()
                
                # Create new conversation if none exists or if last one is older than 24 hours
                if not conversation:
                    should_create_new = True
                else:
                    # Compare datetimes - handle timezone-aware comparison
                    now = datetime.now(timezone.utc)
                    updated = conversation.updated_at
                    if updated.tzinfo is None:
                        # Make naive datetime timezone-aware
                        updated = updated.replace(tzinfo=timezone.utc)
                    time_diff = (now - updated).total_seconds()
                    should_create_new = time_diff > 86400
                
                if should_create_new:
                    conversation = Conversation(
                        id=str(uuid.uuid4()),
                        user_id=user_id,
                        mode=mode,
                        title=user_message[:50] + '...' if len(user_message) > 50 else user_message
                    )
                    db.session.add(conversation)
                    db.session.flush()
                
                conversation_id = conversation.id
                conversation.updated_at = datetime.now(timezone.utc)
                
                # Save user message
                user_msg = Message(
                    id=str(uuid.uuid4()),
                    conversation_id=conversation_id,
                    role='user',
                    content=user_message
                )
                db.session.add(user_msg)
                
                # Save assistant replies
                for reply in replies:
                    assistant_msg = Message(
                        id=str(uuid.uuid4()),
                        conversation_id=conversation_id,
                        role='assistant',
                        content=reply,
                        tools_used=json.dumps(tool_traces) if tool_traces else None
                    )
                    db.session.add(assistant_msg)
                
                db.session.commit()
            except Exception as db_error:
                print(f"Error saving conversation history: {db_error}")
                db.session.rollback()
                # Continue even if DB save fails
        
        return jsonify({
            'replies': replies,
            'toolsUsed': tool_traces,
            'conversationId': conversation_id,
            'savedMemoryIds': memory_ids
        })
        
    except Exception as e:
        import traceback
        error_trace = traceback.format_exc()
        error_str = str(e)
        print(f"Error in chat endpoint: {e}")
        print(f"Traceback: {error_trace}")
        
        # Provide user-friendly error messages
        if 'quota' in error_str.lower() or 'insufficient_quota' in error_str.lower() or 'quota_exceeded' in error_str.lower():
            error_message = 'Gemini API quota exceeded. Please check your Google Cloud billing or upgrade your plan.'
        elif 'rate_limit' in error_str.lower():
            error_message = 'Rate limit exceeded. Please wait a moment and try again.'
        elif 'api_key' in error_str.lower() or 'authentication' in error_str.lower():
            error_message = 'API key issue. Please check your GEMINI_API_KEY in the .env file.'
        else:
            error_message = f'An error occurred: {error_str}. Please check backend logs for details.'
        
        return jsonify({
            'error': error_message,
            'details': 'Make sure GEMINI_API_KEY is set correctly in your .env file and you have sufficient quota.'
        }), 500

# Profile Endpoints
@app.route('/api/profile', methods=['GET'])
def get_profile():
    """Get user profile from Supermemory"""
    try:
        user = get_user_from_token(request)
        if not user:
            return jsonify({'error': 'Unauthorized'}), 401
        
        profile_data = get_profile_memory(user.id)
        if profile_data:
            return jsonify({'profile': profile_data})
        else:
            return jsonify({'profile': None})
    except Exception as e:
        print(f"Error getting profile: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/profile', methods=['POST'])
def update_profile():
    """Create or update user profile in Supermemory"""
    try:
        user = get_user_from_token(request)
        if not user:
            return jsonify({'error': 'Unauthorized'}), 401
        
        data = request.json
        profile_data = data.get('profile', {})
        
        # Ensure user_id matches authenticated user
        profile_data['user_id'] = user.id
        profile_data['name'] = profile_data.get('name', user.name)
        
        # Validate and create UserProfile object
        try:
            profile = UserProfile.from_dict(profile_data)
        except Exception as e:
            return jsonify({'error': f'Invalid profile data: {str(e)}'}), 400
        
        # Store in Supermemory
        result = upsert_profile_memory(user.id, profile.to_dict())
        
        if result:
            return jsonify({'profile': profile.to_dict(), 'success': True})
        else:
            return jsonify({'error': 'Failed to save profile'}), 500
            
    except Exception as e:
        print(f"Error updating profile: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/proactive', methods=['GET'])
def proactive():
    """Generate proactive message based on recent memories"""
    try:
        # Get authenticated user or use default
        user = get_user_from_token(request)
        user_id = user.id if user else request.args.get('userId', 'default')
        
        mode = request.args.get('mode', 'student')
        profile_id = f"{user_id}-{mode}" if user_id != 'default' else DEFAULT_PROFILE_ID
        
        # Get recent memories
        memories_data = get_memories(profile_id, mode=mode, limit=10)
        memories = memories_data.get('memories', [])
        
        if not memories:
            return jsonify({'message': None})
        
        # Build context from recent memories
        recent_context = '\n'.join([
            f"- {mem.get('text', '')[:100]}"
            for mem in memories[:5]
        ])
        
        # Generate proactive suggestion
        prompt = f"""Based on these recent memories in {mode} mode:
{recent_context}

Generate a brief, helpful proactive message to start a conversation. Be specific and actionable.
Examples:
- Student: "You mentioned a midterm next week. Want help planning revision?"
- Parent: "You often add kids' activities on weekends. Want to plan this weekend?"
- Job: "You applied to X jobs recently. Want to draft follow-up emails?"

Keep it to one sentence, friendly and helpful."""

        if not client or not model_name:
            return jsonify({'message': None})
        
        try:
            system_context = 'You are a helpful assistant that generates proactive conversation starters.'
            full_prompt = f"{system_context}\n\n{prompt}"
            
            from google.genai import types
            response = client.models.generate_content(
                model=model_name,
                contents=full_prompt,
                config=types.GenerateContentConfig(
                    temperature=0.8,
                    max_output_tokens=150,
                )
            )
            # Extract text from response
            message = response.text if hasattr(response, 'text') else str(response.candidates[0].content.parts[0].text)
            message = message.strip()
        except Exception as e:
            print(f"Error generating proactive message: {e}")
            return jsonify({'message': None})
        
        return jsonify({'message': message})
        
    except Exception as e:
        print(f"Error in proactive endpoint: {e}")
        return jsonify({'message': None})

@app.route('/api/memories', methods=['GET'])
def get_memories_endpoint():
    """Get memories for a user and mode"""
    try:
        # Get authenticated user or use default
        user = get_user_from_token(request)
        user_id = user.id if user else request.args.get('userId', 'default')
        
        mode = request.args.get('mode', 'student')
        
        print(f"[Get Memories] Fetching memories for user_id={user_id}, mode={mode}")
        
        # Use the supermemory_client function directly with correct user_id and role
        from services.supermemory_client import get_recent_memories
        
        # Get recent memories (strictly filtered by role inside get_recent_memories)
        memories = get_recent_memories(user_id, role=mode, limit=50)
        
        # Format memories for frontend
        formatted_memories = []
        for mem in memories:
            # Handle different response formats from Supermemory API
            text = mem.get('text') or mem.get('content', '')
            metadata = mem.get('metadata', {})

            # Extra safety: enforce strict mode separation at the API boundary too
            if (metadata or {}).get('mode') != mode:
                continue
            
            formatted_memories.append({
                'id': mem.get('id', ''),
                'text': text,
                'metadata': metadata
            })
        
        print(f"[Get Memories] Found {len(formatted_memories)} memories")
        return jsonify({'memories': formatted_memories})
        
    except Exception as e:
        print(f"[Get Memories] ❌ Error getting memories: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'memories': []}), 500

@app.route('/api/memories/<memory_id>', methods=['DELETE'])
def delete_memory_endpoint(memory_id):
    """Delete a memory"""
    try:
        success = delete_memory(memory_id)
        if success:
            return jsonify({'success': True})
        else:
            return jsonify({'success': False, 'error': 'Failed to delete memory'}), 500
    except Exception as e:
        print(f"Error deleting memory: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/memories/<memory_id>', methods=['PUT'])
def update_memory_endpoint(memory_id):
    """Update a memory"""
    try:
        data = request.json
        text = data.get('text')
        metadata = data.get('metadata')
        
        result = update_memory(memory_id, text=text, metadata=metadata)
        if result:
            return jsonify(result)
        else:
            return jsonify({'error': 'Failed to update memory'}), 500
    except Exception as e:
        print(f"Error updating memory: {e}")
        return jsonify({'error': str(e)}), 500

# Conversation History Endpoints
@app.route('/api/conversations', methods=['GET'])
def get_conversations():
    """Get all conversations for a user, optionally filtered by mode"""
    try:
        user = get_user_from_token(request)
        if not user:
            return jsonify({'error': 'Unauthorized'}), 401
        
        mode = request.args.get('mode')
        limit = int(request.args.get('limit', 50))
        
        query = Conversation.query.filter_by(user_id=user.id)
        if mode:
            query = query.filter_by(mode=mode)
        
        conversations = query.order_by(Conversation.updated_at.desc()).limit(limit).all()
        
        return jsonify({
            'conversations': [conv.to_dict() for conv in conversations]
        })
    except Exception as e:
        print(f"Error getting conversations: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/conversations/<conversation_id>', methods=['GET'])
def get_conversation(conversation_id):
    """Get a specific conversation with all messages"""
    try:
        user = get_user_from_token(request)
        if not user:
            return jsonify({'error': 'Unauthorized'}), 401
        
        conversation = Conversation.query.filter_by(
            id=conversation_id,
            user_id=user.id
        ).first()
        
        if not conversation:
            return jsonify({'error': 'Conversation not found'}), 404
        
        result = conversation.to_dict()
        result['messages'] = [msg.to_dict() for msg in conversation.messages]
        
        return jsonify(result)
    except Exception as e:
        print(f"Error getting conversation: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/conversations/<conversation_id>', methods=['DELETE'])
def delete_conversation(conversation_id):
    """Delete a conversation"""
    try:
        user = get_user_from_token(request)
        if not user:
            return jsonify({'error': 'Unauthorized'}), 401
        
        conversation = Conversation.query.filter_by(
            id=conversation_id,
            user_id=user.id
        ).first()
        
        if not conversation:
            return jsonify({'error': 'Conversation not found'}), 404
        
        db.session.delete(conversation)
        db.session.commit()
        
        return jsonify({'success': True})
    except Exception as e:
        print(f"Error deleting conversation: {e}")
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

# Task Management Endpoints
@app.route('/api/tasks', methods=['GET'])
def get_tasks():
    """Get tasks for a user, optionally filtered by mode and status"""
    try:
        user = get_user_from_token(request)
        if not user:
            return jsonify({'error': 'Unauthorized'}), 401
        
        mode = request.args.get('mode')
        status = request.args.get('status')
        
        query = Task.query.filter_by(user_id=user.id)
        if mode:
            query = query.filter_by(mode=mode)
        if status:
            query = query.filter_by(status=status)
        
        tasks = query.order_by(Task.created_at.desc()).all()
        
        return jsonify({
            'tasks': [task.to_dict() for task in tasks]
        })
    except Exception as e:
        print(f"Error getting tasks: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/tasks', methods=['POST'])
def create_task():
    """Create a new task"""
    try:
        user = get_user_from_token(request)
        if not user:
            return jsonify({'error': 'Unauthorized'}), 401
        
        data = request.json
        task = Task(
            id=str(uuid.uuid4()),
            user_id=user.id,
            mode=data.get('mode', 'student'),
            title=data.get('title', ''),
            description=data.get('description'),
            status=data.get('status', 'pending'),
            priority=data.get('priority', 'medium'),
            due_date=datetime.fromisoformat(data['dueDate']) if data.get('dueDate') else None
        )
        
        db.session.add(task)
        db.session.commit()
        
        return jsonify(task.to_dict()), 201
    except Exception as e:
        print(f"Error creating task: {e}")
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@app.route('/api/tasks/<task_id>', methods=['PUT'])
def update_task(task_id):
    """Update a task"""
    try:
        user = get_user_from_token(request)
        if not user:
            return jsonify({'error': 'Unauthorized'}), 401
        
        task = Task.query.filter_by(
            id=task_id,
            user_id=user.id
        ).first()
        
        if not task:
            return jsonify({'error': 'Task not found'}), 404
        
        data = request.json
        if 'title' in data:
            task.title = data['title']
        if 'description' in data:
            task.description = data['description']
        if 'status' in data:
            task.status = data['status']
            if data['status'] == 'completed' and not task.completed_at:
                task.completed_at = datetime.now(timezone.utc)
            elif data['status'] != 'completed':
                task.completed_at = None
        if 'priority' in data:
            task.priority = data['priority']
        if 'dueDate' in data:
            task.due_date = datetime.fromisoformat(data['dueDate']) if data['dueDate'] else None
        if 'mode' in data:
            task.mode = data['mode']
        
        task.updated_at = datetime.now(timezone.utc)
        db.session.commit()
        
        return jsonify(task.to_dict())
    except Exception as e:
        print(f"Error updating task: {e}")
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@app.route('/api/tasks/<task_id>', methods=['DELETE'])
def delete_task(task_id):
    """Delete a task"""
    try:
        user = get_user_from_token(request)
        if not user:
            return jsonify({'error': 'Unauthorized'}), 401
        
        task = Task.query.filter_by(
            id=task_id,
            user_id=user.id
        ).first()
        
        if not task:
            return jsonify({'error': 'Task not found'}), 404
        
        db.session.delete(task)
        db.session.commit()
        
        return jsonify({'success': True})
    except Exception as e:
        print(f"Error deleting task: {e}")
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

# Memory Graph Endpoint
@app.route('/api/memory-graph', methods=['GET'])
def get_memory_graph():
    """Generate memory graph data with nodes and edges"""
    try:
        user = get_user_from_token(request)
        if not user:
            return jsonify({'error': 'Unauthorized'}), 401
        
        role = request.args.get('role')  # Optional filter by role
        user_id = user.id
        
        # Get all memories for the user (optionally filtered by role)
        from services.supermemory_client import get_recent_memories
        memories = get_recent_memories(user_id, role=role, limit=100)
        
        nodes = []
        edges = []
        node_ids = set()
        
        # User node
        user_node_id = f"user:{user_id}"
        nodes.append({
            "id": user_node_id,
            "label": user.name or "User",
            "type": "user",
            "role": "all"
        })
        node_ids.add(user_node_id)
        
        # Process memories to extract entities + always add a memory node
        edge_ids = set()
        for mem in memories:
            # Normalize memory text across API shapes
            text = mem.get('text') or mem.get('content') or mem.get('summary') or ''
            metadata = mem.get('metadata', {}) or {}
            mem_role = metadata.get('mode', role or 'all')
            mem_id = mem.get('id') or ''

            # Always add a "memory" node per memory so the graph is never empty
            memory_node_id = f"memory:{mem_id}" if mem_id else f"memory:local:{uuid.uuid4()}"
            if memory_node_id not in node_ids:
                nodes.append({
                    "id": memory_node_id,
                    "label": (text[:80] + "…") if len(text) > 80 else (text or "Memory"),
                    "type": "memory",
                    "role": mem_role,
                    "sourceId": mem_id,
                    "metadata": metadata
                })
                node_ids.add(memory_node_id)

            # Edge: user -> memory
            edge_id = f"{user_node_id}-{memory_node_id}"
            if edge_id not in edge_ids:
                edges.append({
                    "id": edge_id,
                    "source": user_node_id,
                    "target": memory_node_id,
                    "relation": "remembered"
                })
                edge_ids.add(edge_id)

            # Extract entities (simple pattern matching)
            entities = extract_entities(text, mem_role)
            for entity in entities:
                entity_id = entity['id']

                # Add entity node if not exists
                if entity_id not in node_ids:
                    nodes.append({
                        "id": entity_id,
                        "label": entity['label'],
                        "type": entity['type'],
                        "role": mem_role
                    })
                    node_ids.add(entity_id)

                # Edge: memory -> entity (stronger semantics than user -> entity)
                me_edge_id = f"{memory_node_id}-{entity_id}"
                if me_edge_id not in edge_ids:
                    edges.append({
                        "id": me_edge_id,
                        "source": memory_node_id,
                        "target": entity_id,
                        "relation": entity['relation']
                    })
                    edge_ids.add(me_edge_id)
        
        return jsonify({
            "nodes": nodes,
            "edges": edges
        })
    except Exception as e:
        print(f"Error generating memory graph: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

def extract_entities(text: str, role: str) -> List[Dict]:
    """Extract entities (courses, companies, kids, etc.) from memory text"""
    entities = []
    text_lower = text.lower()
    
    # Course/Exam/Topic entities (Student role)
    if role == 'student' or 'course' in text_lower or 'exam' in text_lower or 'test' in text_lower:
        import re
        # Look for course patterns: "CS101", "AI 101", "course: X"
        course_patterns = re.findall(r'\b([A-Z]{2,}\s?\d{3,})\b', text)
        for course in course_patterns:
            entities.append({
                "id": f"course:{course.replace(' ', '')}",
                "label": course,
                "type": "course",
                "relation": "studying"
            })
        
        # Exam patterns (handle lowercase subjects too, like "machine learning")
        exam_patterns = re.findall(r'\b(midterm|final|exam|test)\b[^a-zA-Z0-9]{0,10}(?:for|in)?\s*([A-Za-z][A-Za-z ]{2,40})', text)
        for exam_type, subject_raw in exam_patterns:
            subject = subject_raw.strip().rstrip('.').rstrip(',')
            # Avoid swallowing long trailing sentences
            subject = subject.split('  ')[0].strip()
            if subject:
                entities.append({
                    "id": f"exam:{subject.lower().replace(' ', '-')}-{exam_type}",
                    "label": f"{exam_type.title()} - {subject.title()}",
                    "type": "exam",
                    "relation": "preparing_for"
                })

        # Topic patterns (common ML topics)
        topic_keywords = [
            "machine learning",
            "applied machine learning",
            "neural networks",
            "deep learning",
            "linear regression",
            "logistic regression",
            "random forest",
            "decision trees",
            "svm",
            "k-means",
            "pca",
            "gradient descent",
            "backpropagation",
            "cnn",
            "rnn",
            "transformers",
        ]
        for kw in topic_keywords:
            if kw in text_lower:
                entities.append({
                    "id": f"topic:{kw.replace(' ', '-')}",
                    "label": kw.title(),
                    "type": "topic",
                    "relation": "studying"
                })
    
    # Company entities (Job role)
    if role == 'job' or 'company' in text_lower or 'applied' in text_lower:
        import re
        # Look for company names (capitalized words after "at", "to", "with")
        company_patterns = re.findall(r'(?:applied to|interview at|company|at)\s+([A-Z][a-zA-Z]+(?:\s+[A-Z][a-zA-Z]+)?)', text)
        for company in company_patterns:
            if len(company) > 2:  # Filter out short matches
                entities.append({
                    "id": f"company:{company.lower().replace(' ', '-')}",
                    "label": company,
                    "type": "company",
                    "relation": "applied_to" if "applied" in text_lower else "interested_in"
                })
    
    # Kid entities (Parent role)
    if role == 'parent' or 'kid' in text_lower or 'child' in text_lower:
        import re
        # Look for kid names (capitalized words after "kid", "child", "son", "daughter")
        kid_patterns = re.findall(r'(?:kid|child|son|daughter)\s+([A-Z][a-z]+)', text)
        for kid_name in kid_patterns:
            entities.append({
                "id": f"kid:{kid_name.lower()}",
                "label": kid_name,
                "type": "kid",
                "relation": "parent_of"
            })
    
    return entities

if __name__ == '__main__':
    app.run(debug=True, port=5001)

