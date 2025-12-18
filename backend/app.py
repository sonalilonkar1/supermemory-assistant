from flask import Flask, request, jsonify
from flask_cors import CORS
import os
from dotenv import load_dotenv
import google.genai as genai
from datetime import datetime
import requests
import json

load_dotenv()

app = Flask(__name__)
CORS(app)

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
    # Build container tags
    container_tags = [profile_id] if profile_id else []
    if metadata and metadata.get('mode'):
        container_tags.append(f"{profile_id}-{metadata.get('mode')}")
    
    try:
        # Supermemory API v3 uses /documents endpoint for creating memories
        # Try format with 'content' field first
        url = f'{SUPERMEMORY_API_URL}/documents'
        payload = {
            'content': text,
            'containerTags': container_tags,
        }
        if metadata:
            payload['metadata'] = metadata
        
        response = requests.post(
            url,
            headers=get_supermemory_headers(),
            json=payload
        )
        response.raise_for_status()
        return response.json()
    except requests.exceptions.HTTPError as e:
        # Try alternative endpoint format if first fails
        if e.response.status_code == 400:
            try:
                # Alternative format: try with 'text' instead of 'content'
                url = f'{SUPERMEMORY_API_URL}/documents'
                payload = {
                    'text': text,
                    'containerTags': container_tags,
                }
                if metadata:
                    payload['metadata'] = metadata
                
                response = requests.post(
                    url,
                    headers=get_supermemory_headers(),
                    json=payload
                )
                response.raise_for_status()
                return response.json()
            except Exception as e2:
                error_detail = e2.response.text if hasattr(e2, 'response') and hasattr(e2.response, 'text') else str(e2)
                print(f"Error creating memory (alternative format): {e2}")
                print(f"Response: {error_detail}")
        else:
            error_detail = e.response.text if hasattr(e, 'response') and hasattr(e.response, 'text') else str(e)
            print(f"Error creating memory: {e}")
            print(f"Response: {error_detail}")
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

        # Call Gemini
        if not client or not model_name:
            raise ValueError("Gemini client not initialized. Please set GEMINI_API_KEY in your .env file.")
        
        try:
            # Combine system and user prompts for Gemini
            full_prompt = f"{system_prompt}\n\n{user_prompt}"
            
            # Use the new google.genai API
            from google.genai import types
            response = client.models.generate_content(
                model=model_name,
                contents=full_prompt,
                config=types.GenerateContentConfig(
                    temperature=0.7,
                    max_output_tokens=1000,
                )
            )
            # Extract text from response
            assistant_reply = response.text if hasattr(response, 'text') else str(response.candidates[0].content.parts[0].text)
        except Exception as gemini_error:
            # Handle Gemini API errors gracefully
            error_str = str(gemini_error)
            if 'quota' in error_str.lower() or 'quota_exceeded' in error_str.lower() or '429' in error_str:
                assistant_reply = f"I'm sorry, but I've reached my API quota limit. Please check your Google Cloud billing or try again later. In the meantime, here's a basic response:\n\nBased on your message '{user_message}', I'd be happy to help once the API quota is restored."
            elif 'rate_limit' in error_str.lower() or '429' in error_str:
                assistant_reply = f"I'm experiencing rate limits. Please wait a moment and try again. Your message was: '{user_message}'"
            else:
                # For other errors, provide a helpful fallback
                assistant_reply = f"I encountered an issue connecting to the AI service. Your message was: '{user_message}'. Please check your API configuration or try again later."
            print(f"Gemini API error (using fallback): {gemini_error}")
        
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

