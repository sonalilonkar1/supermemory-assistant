"""Supermemory API client wrapper"""
import os
import requests
import json
from typing import List, Dict, Optional
from datetime import datetime, timezone

SUPERMEMORY_API_KEY = os.getenv('SUPERMEMORY_API_KEY')
SUPERMEMORY_API_URL = os.getenv('SUPERMEMORY_API_URL', 'https://api.supermemory.ai/v3')

def get_supermemory_headers():
    """Get headers for Supermemory API requests"""
    return {
        'x-api-key': SUPERMEMORY_API_KEY,
        'Authorization': f'Bearer {SUPERMEMORY_API_KEY}',
        'Content-Type': 'application/json'
    }

def upsert_profile_memory(user_id: str, profile_json: dict):
    """Store or update user profile in Supermemory"""
    try:
        profile_id = f"{user_id}-profile"
        container_tags = [f"{user_id}-profile", "profile", "static"]
        
        # Search for existing profile memory
        search_url = f'{SUPERMEMORY_API_URL}/search/search'
        search_payload = {
            'query': f'user profile {user_id}',
            'limit': 1,
            'containerTags': container_tags
        }
        
        existing = None
        try:
            response = requests.post(
                search_url,
                headers=get_supermemory_headers(),
                json=search_payload
            )
            if response.status_code == 200:
                results = response.json().get('results', [])
                if results:
                    existing = results[0]
        except:
            pass  # If search fails, we'll create new
        
        # Create or update memory
        memory_text = json.dumps(profile_json)
        metadata = {
            'type': 'user_profile',
            'user_id': user_id,
            'createdAt': datetime.now(timezone.utc).isoformat()
        }
        
        if existing:
            # Update existing
            memory_id = existing.get('id')
            url = f'{SUPERMEMORY_API_URL}/memories/{memory_id}'
            payload = {
                'text': memory_text,
                'metadata': metadata
            }
            response = requests.put(url, headers=get_supermemory_headers(), json=payload)
        else:
            # Create new
            url = f'{SUPERMEMORY_API_URL}/memories'
            payload = {
                'text': memory_text,
                'metadata': metadata,
                'containerTags': container_tags
            }
            response = requests.post(url, headers=get_supermemory_headers(), json=payload)
        
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"Error upserting profile memory: {e}")
        return None

def get_profile_memory(user_id: str) -> Optional[dict]:
    """Retrieve user profile from Supermemory"""
    try:
        container_tags = [f"{user_id}-profile", "profile", "static"]
        
        search_url = f'{SUPERMEMORY_API_URL}/search/search'
        payload = {
            'query': f'user profile {user_id}',
            'limit': 1,
            'containerTags': container_tags
        }
        
        response = requests.post(
            search_url,
            headers=get_supermemory_headers(),
            json=payload
        )
        response.raise_for_status()
        
        results = response.json().get('results', [])
        if results:
            memory = results[0]
            text = memory.get('text', '')
            try:
                return json.loads(text)
            except:
                return None
        return None
    except Exception as e:
        print(f"Error getting profile memory: {e}")
        return None

def search_memories(user_id: str, query: str, role: Optional[str] = None, limit: int = 10) -> List[Dict]:
    """Search memories using Supermemory API"""
    try:
        container_tags = [user_id] if user_id != 'default' else []
        if role:
            container_tags.append(f"{user_id}-{role}")
        
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
        results = data.get('results', [])
        
        # Filter out expired memories (+ enforce strict mode if provided)
        now = datetime.now(timezone.utc)
        filtered_results = []
        for mem in results:
            metadata = mem.get('metadata', {})
            # Strict mode separation: only return memories explicitly tagged for this role
            if role:
                mem_mode = (metadata or {}).get('mode')
                if mem_mode != role:
                    continue
            expires_at = metadata.get('expires_at')
            if expires_at:
                try:
                    expiry = datetime.fromisoformat(expires_at.replace('Z', '+00:00'))
                    if expiry < now:
                        continue  # Skip expired memories
                except:
                    pass  # If parsing fails, include the memory
            
            filtered_results.append(mem)
        
        return filtered_results
    except Exception as e:
        print(f"Error searching memories: {e}")
        return []

def get_recent_memories(user_id: str, role: Optional[str] = None, limit: int = 5) -> List[Dict]:
    """Get recent memories (episodic context)"""
    try:
        container_tags = [user_id] if user_id != 'default' else []
        if role:
            container_tags.append(f"{user_id}-{role}")
        
        print(f"[Get Recent Memories] Fetching for user_id={user_id}, role={role}, limit={limit}")
        print(f"[Get Recent Memories] Container tags: {container_tags}")
        
        # Try /documents/documents endpoint first (same format as get_memories uses)
        url = f'{SUPERMEMORY_API_URL}/documents/documents'
        payload = {
            'page': 1,
            'limit': limit,
            'sort': 'createdAt',
            'order': 'desc',
            'containerTags': container_tags
        }
        
        try:
            print(f"[Get Recent Memories] Trying POST {url}")
            response = requests.post(
                url,
                headers=get_supermemory_headers(),
                json=payload
            )
            response.raise_for_status()
            data = response.json()
            print(f"[Get Recent Memories] ✅ Success! Response keys: {data.keys() if isinstance(data, dict) else 'list'}")
            
            # Handle different response formats
            memories = []
            if isinstance(data, dict):
                memories = data.get('documents', data.get('memories', []))
            elif isinstance(data, list):
                memories = data
            else:
                memories = []
            
            # Filter expired (+ enforce strict mode if provided) and return as list
            now = datetime.now(timezone.utc)
            filtered = []
            for mem in memories:
                metadata = mem.get('metadata', {})
                # Strict mode separation: only return memories explicitly tagged for this role
                if role:
                    mem_mode = (metadata or {}).get('mode')
                    if mem_mode != role:
                        continue
                expires_at = metadata.get('expires_at')
                if expires_at:
                    try:
                        expiry = datetime.fromisoformat(expires_at.replace('Z', '+00:00'))
                        if expiry < now:
                            continue  # Skip expired
                    except:
                        pass
                
                # Normalize memory format - handle both 'text' and 'content' fields
                if 'content' in mem and 'text' not in mem:
                    mem['text'] = mem['content']
                filtered.append(mem)
            
            print(f"[Get Recent Memories] Returning {len(filtered)} memories (after filtering expired)")
            return filtered[:limit]
            
        except requests.exceptions.HTTPError as e:
            print(f"[Get Recent Memories] ❌ /documents/documents failed: {e.response.status_code} - {e.response.text[:200]}")
            
            # Fallback: Try /memories endpoint
            try:
                url_alt = f'{SUPERMEMORY_API_URL}/memories'
                payload_alt = {
                    'limit': limit,
                    'sort': 'createdAt',
                    'order': 'desc',
                    'containerTags': container_tags
                }
                print(f"[Get Recent Memories] Trying POST {url_alt} as fallback")
                response = requests.post(
                    url_alt,
                    headers=get_supermemory_headers(),
                    json=payload_alt
                )
                response.raise_for_status()
                data = response.json()
                memories = data.get('memories', data.get('documents', data if isinstance(data, list) else []))
                
                # Filter expired
                now = datetime.now(timezone.utc)
                filtered = []
                for mem in memories:
                    metadata = mem.get('metadata', {})
                    # Strict mode separation: only return memories explicitly tagged for this role
                    if role:
                        mem_mode = (metadata or {}).get('mode')
                        if mem_mode != role:
                            continue
                    expires_at = metadata.get('expires_at')
                    if expires_at:
                        try:
                            expiry = datetime.fromisoformat(expires_at.replace('Z', '+00:00'))
                            if expiry < now:
                                continue
                        except:
                            pass
                    if 'content' in mem and 'text' not in mem:
                        mem['text'] = mem['content']
                    filtered.append(mem)
                
                print(f"[Get Recent Memories] ✅ Fallback success! Returning {len(filtered)} memories")
                return filtered[:limit]
            except Exception as e2:
                print(f"[Get Recent Memories] ❌ Fallback also failed: {e2}")
                raise e  # Re-raise original error
        
    except Exception as e:
        print(f"[Get Recent Memories] ❌❌❌ Error getting recent memories: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return []

def create_memory(user_id: str, text: str, metadata: dict, role: Optional[str] = None):
    """Create a new memory in Supermemory"""
    try:
        container_tags = [user_id] if user_id != 'default' else []
        if role:
            container_tags.append(f"{user_id}-{role}")
        
        print(f"[Memory Creation] Attempting to create memory for user_id={user_id}, role={role}")
        print(f"[Memory Creation] Text preview: {text[:100]}...")
        
        # Try /documents endpoint first (v3 format)
        url = f'{SUPERMEMORY_API_URL}/documents'
        payload = {
            'content': text,  # Try 'content' field first
            'metadata': metadata,
            'containerTags': container_tags
        }
        
        try:
            print(f"[Memory Creation] Trying POST {url} with 'content' field")
            response = requests.post(
                url,
                headers=get_supermemory_headers(),
                json=payload
            )
            response.raise_for_status()
            result = response.json()
            print(f"[Memory Creation] ✅ Success! Memory ID: {result.get('id', 'unknown')}")
            return result
        except requests.exceptions.HTTPError as e:
            print(f"[Memory Creation] ❌ Failed with 'content' field: {e.response.status_code} - {e.response.text[:200]}")
            # Try alternative format with 'text' instead of 'content'
            if e.response.status_code == 400:
                payload_alt = {
                    'text': text,
                    'metadata': metadata,
                    'containerTags': container_tags
                }
                try:
                    print(f"[Memory Creation] Trying POST {url} with 'text' field")
                    response = requests.post(
                        url,
                        headers=get_supermemory_headers(),
                        json=payload_alt
                    )
                    response.raise_for_status()
                    result = response.json()
                    print(f"[Memory Creation] ✅ Success with 'text' field! Memory ID: {result.get('id', 'unknown')}")
                    return result
                except requests.exceptions.HTTPError as e2:
                    print(f"[Memory Creation] ❌ Failed with 'text' field: {e2.response.status_code} - {e2.response.text[:200]}")
            
            # Try /memories endpoint as fallback
            url_alt = f'{SUPERMEMORY_API_URL}/memories'
            payload_mem = {
                'text': text,
                'metadata': metadata,
                'containerTags': container_tags
            }
            try:
                print(f"[Memory Creation] Trying POST {url_alt} as fallback")
                response = requests.post(
                    url_alt,
                    headers=get_supermemory_headers(),
                    json=payload_mem
                )
                response.raise_for_status()
                result = response.json()
                print(f"[Memory Creation] ✅ Success with /memories endpoint! Memory ID: {result.get('id', 'unknown')}")
                return result
            except requests.exceptions.HTTPError as e3:
                print(f"[Memory Creation] ❌ All endpoints failed. Last error: {e3.response.status_code} - {e3.response.text[:200]}")
                raise e3  # Re-raise to be caught by outer handler
    except Exception as e:
        print(f"[Memory Creation] ❌❌❌ Error creating memory: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        # Don't fail the entire request if memory creation fails
        return None

