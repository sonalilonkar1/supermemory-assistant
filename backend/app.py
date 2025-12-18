from flask import Flask, request, jsonify
from flask_cors import CORS
import os
from dotenv import load_dotenv
import openai
from datetime import datetime
import requests
import json

load_dotenv()

app = Flask(__name__)
CORS(app)

# Configuration
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
SUPERMEMORY_API_KEY = os.getenv('SUPERMEMORY_API_KEY')
SUPERMEMORY_API_URL = os.getenv('SUPERMEMORY_API_URL', 'https://api.supermemory.ai/v3')
PARALLEL_API_KEY = os.getenv('PARALLEL_API_KEY')
EXA_API_KEY = os.getenv('EXA_API_KEY')

# Validate required API keys
if not OPENAI_API_KEY:
    print("WARNING: OPENAI_API_KEY not set. Chat functionality will not work.")
if not SUPERMEMORY_API_KEY:
    print("WARNING: SUPERMEMORY_API_KEY not set. Memory functionality will not work.")

# Initialize OpenAI client
from openai import OpenAI
client = OpenAI(api_key=OPENAI_API_KEY) if OPENAI_API_KEY else None

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
    try:
        # Try the search endpoint
        url = f'{SUPERMEMORY_API_URL}/search'
        payload = {
            'query': query,
            'limit': limit,
            'containerTags': [profile_id] if profile_id else []
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
        # Handle different response formats
        if 'results' in data:
            return data
        elif 'documents' in data:
            return {'results': data.get('documents', [])}
        else:
            return {'results': data if isinstance(data, list) else []}
    except Exception as e:
        print(f"Error searching memories: {e}")
        # Return empty results instead of failing
        return {'results': []}

def create_memory(profile_id, text, metadata=None):
    """Create a new memory using Supermemory API"""
    try:
        # Try /memories endpoint first
        url = f'{SUPERMEMORY_API_URL}/memories'
        payload = {
            'text': text,
            'metadata': metadata or {},
            'containerTags': [profile_id] if profile_id else []
        }
        if metadata and metadata.get('mode'):
            payload['containerTags'] = [f"{profile_id}-{metadata.get('mode')}"]
        
        response = requests.post(
            url,
            headers=get_supermemory_headers(),
            json=payload
        )
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"Error creating memory: {e}")
        # Don't fail the entire request if memory creation fails
        return None

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

@app.route('/api/health', methods=['GET'])
def health():
    """Health check endpoint"""
    return jsonify({'status': 'ok'})

@app.route('/api/chat', methods=['POST'])
def chat():
    """Main chat endpoint"""
    try:
        data = request.json
        user_id = data.get('userId', 'default')
        mode = data.get('mode', 'student')
        messages = data.get('messages', [])
        use_search = data.get('useSearch', False)
        
        # Join multiple rapid messages into one
        user_message = ' '.join(messages) if isinstance(messages, list) else messages
        
        # Get profile ID (can be based on userId and mode)
        profile_id = f"{user_id}-{mode}" if user_id != 'default' else DEFAULT_PROFILE_ID
        
        # Search memories
        memory_results = search_memories(profile_id, user_message, mode=mode)
        memory_context = ''
        if memory_results.get('results'):
            memory_context = '\n'.join([
                f"- {mem.get('text', '')}" 
                for mem in memory_results['results'][:5]
            ])
        
        # Web search if requested
        web_results = []
        web_context = ''
        tools_used = []
        
        if use_search or any(keyword in user_message.lower() for keyword in ['search', 'latest', 'news', 'find']):
            web_results = web_search(user_message)
            if web_results:
                web_context = '\n'.join([
                    f"- {result.get('title', '')}: {result.get('snippet', result.get('text', ''))}"
                    for result in web_results[:3]
                ])
                tools_used.append({'name': 'web.search', 'status': 'success'})
        
        # Build context for LLM
        system_prompt = f"""You are a helpful personal assistant in {mode} mode. 
You have access to the user's memories and can search the web when needed.

Mode-specific context:
- Student mode: Help with homework, study planning, deadlines, academic advice
- Parent mode: Help with family planning, kids' activities, scheduling, family organization
- Job mode: Help with job applications, interview prep, career advice, networking

Use the user's memories to provide personalized responses. Be proactive and helpful."""

        user_prompt = f"""User message: {user_message}

{f'Relevant memories:\n{memory_context}' if memory_context else ''}
{f'\nWeb search results:\n{web_context}' if web_context else ''}

Provide a helpful response. If appropriate, break your response into multiple parts for clarity."""

        # Call OpenAI
        if not client:
            raise ValueError("OpenAI client not initialized. Please set OPENAI_API_KEY in your .env file.")
        
        try:
            response = client.chat.completions.create(
                model='gpt-3.5-turbo',  # Changed from gpt-4 to gpt-3.5-turbo for better compatibility
                messages=[
                    {'role': 'system', 'content': system_prompt},
                    {'role': 'user', 'content': user_prompt}
                ],
                temperature=0.7,
                max_tokens=1000
            )
            assistant_reply = response.choices[0].message.content
        except Exception as openai_error:
            # Handle OpenAI API errors gracefully
            error_str = str(openai_error)
            if 'quota' in error_str.lower() or 'insufficient_quota' in error_str.lower() or '429' in error_str:
                assistant_reply = f"I'm sorry, but I've reached my API quota limit. Please check your OpenAI billing or try again later. In the meantime, here's a basic response:\n\nBased on your message '{user_message}', I'd be happy to help once the API quota is restored."
            elif 'rate_limit' in error_str.lower() or '429' in error_str:
                assistant_reply = f"I'm experiencing rate limits. Please wait a moment and try again. Your message was: '{user_message}'"
            else:
                # For other errors, provide a helpful fallback
                assistant_reply = f"I encountered an issue connecting to the AI service. Your message was: '{user_message}'. Please check your API configuration or try again later."
            print(f"OpenAI API error (using fallback): {openai_error}")
        
        # Split response into multiple messages if it contains clear sections
        replies = [assistant_reply]
        if '\n\n' in assistant_reply or '**' in assistant_reply:
            # Split by double newlines or markdown headers
            parts = assistant_reply.split('\n\n')
            if len(parts) > 1:
                replies = [part.strip() for part in parts if part.strip()]
        
        # Create memory of this interaction
        memory_text = f"User asked: {user_message}. Assistant replied: {assistant_reply[:200]}"
        memory_metadata = {
            'mode': mode,
            'source': 'chat',
            'createdAt': datetime.now().isoformat(),
            'userId': user_id
        }
        create_memory(profile_id, memory_text, memory_metadata)
        
        tools_used.append({'name': 'memory.search', 'status': 'success'})
        tools_used.append({'name': 'memory.write', 'status': 'success'})
        
        return jsonify({
            'replies': replies,
            'toolsUsed': tools_used
        })
        
    except Exception as e:
        import traceback
        error_trace = traceback.format_exc()
        error_str = str(e)
        print(f"Error in chat endpoint: {e}")
        print(f"Traceback: {error_trace}")
        
        # Provide user-friendly error messages
        if 'quota' in error_str.lower() or 'insufficient_quota' in error_str.lower():
            error_message = 'OpenAI API quota exceeded. Please check your OpenAI billing or upgrade your plan.'
        elif 'rate_limit' in error_str.lower():
            error_message = 'Rate limit exceeded. Please wait a moment and try again.'
        elif 'api_key' in error_str.lower() or 'authentication' in error_str.lower():
            error_message = 'API key issue. Please check your OPENAI_API_KEY in the .env file.'
        else:
            error_message = f'An error occurred: {error_str}. Please check backend logs for details.'
        
        return jsonify({
            'error': error_message,
            'details': 'Make sure OPENAI_API_KEY is set correctly in your .env file and you have sufficient quota.'
        }), 500

@app.route('/api/proactive', methods=['GET'])
def proactive():
    """Generate proactive message based on recent memories"""
    try:
        mode = request.args.get('mode', 'student')
        user_id = request.args.get('userId', 'default')
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

        if not client:
            return jsonify({'message': None})
        
        response = client.chat.completions.create(
            model='gpt-3.5-turbo',  # Changed from gpt-4 to gpt-3.5-turbo for better compatibility
            messages=[
                {'role': 'system', 'content': 'You are a helpful assistant that generates proactive conversation starters.'},
                {'role': 'user', 'content': prompt}
            ],
            temperature=0.8,
            max_tokens=150
        )
        
        message = response.choices[0].message.content.strip()
        
        return jsonify({'message': message})
        
    except Exception as e:
        print(f"Error in proactive endpoint: {e}")
        return jsonify({'message': None})

@app.route('/api/memories', methods=['GET'])
def get_memories_endpoint():
    """Get memories for a user and mode"""
    try:
        mode = request.args.get('mode', 'student')
        user_id = request.args.get('userId', 'default')
        profile_id = f"{user_id}-{mode}" if user_id != 'default' else DEFAULT_PROFILE_ID
        
        memories_data = get_memories(profile_id, mode=mode)
        return jsonify(memories_data)
        
    except Exception as e:
        print(f"Error getting memories: {e}")
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

if __name__ == '__main__':
    app.run(debug=True, port=5000)

