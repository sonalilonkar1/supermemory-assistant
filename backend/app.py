from flask import Flask, request, jsonify
from flask_cors import CORS
import os
from dotenv import load_dotenv
import google.genai as genai
from datetime import datetime, timezone
import requests
import json
import uuid
import re
from typing import List, Dict, Optional
import importlib
from calendar_routes import register_calendar_routes
from models import db, User, Conversation, Message, Task, UserMode, Connector, UserProfile
from services.memory_orchestrator import build_context_for_turn
from services.llm import call_gemini
from services.memory_classifier import classify_memory
from services.supermemory_client import upsert_profile_memory, get_profile_memory, create_memory
from auth import (
    hash_password, verify_password, generate_token, 
    verify_token, get_user_from_token, generate_user_id, init_bcrypt
)

load_dotenv()

N8N_WEBHOOK_SECRET = os.getenv('N8N_WEBHOOK_SECRET', '')

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

# Register calendar routes
register_calendar_routes(app)

# Create tables
with app.app_context():
    db.create_all()
    # Lightweight migration for existing SQLite DBs (no Alembic)
    def _ensure_columns(table_name: str, columns: Dict[str, str]):
        try:
            existing = [row[1] for row in db.session.execute(db.text(f"PRAGMA table_info({table_name})")).fetchall()]
            for col, col_sql in columns.items():
                if col not in existing:
                    db.session.execute(db.text(f"ALTER TABLE {table_name} ADD COLUMN {col} {col_sql}"))
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            print(f"[DB Migration] Skipping migration for {table_name}: {e}")

    _ensure_columns("user_modes", {
        "description": "TEXT",
        "default_tags": "TEXT",
        "cross_mode_sources": "TEXT",
    })
    
    # Ensure connectors table exists
    try:
        # Check if table exists
        table_exists = db.session.execute(db.text("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name='connectors'
        """)).fetchone()
        
        if not table_exists:
            # Create new table with correct column name
            db.session.execute(db.text("""
                CREATE TABLE connectors (
                    id VARCHAR(36) PRIMARY KEY,
                    user_id VARCHAR(36) NOT NULL,
                    provider VARCHAR(50) NOT NULL,
                    connection_id VARCHAR(255),
                    status VARCHAR(20) DEFAULT 'pending',
                    connector_metadata TEXT,
                    last_sync_at DATETIME,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(user_id, provider)
                )
            """))
            db.session.execute(db.text("CREATE INDEX idx_connectors_user_id ON connectors(user_id)"))
            db.session.execute(db.text("CREATE INDEX idx_connectors_provider ON connectors(provider)"))
            db.session.execute(db.text("CREATE INDEX idx_connectors_status ON connectors(status)"))
        else:
            # Table exists - check if we need to migrate from 'metadata' to 'connector_metadata'
            columns = [row[1] for row in db.session.execute(db.text("PRAGMA table_info(connectors)")).fetchall()]
            if 'metadata' in columns and 'connector_metadata' not in columns:
                # Migrate: rename metadata column to connector_metadata
                db.session.execute(db.text("ALTER TABLE connectors RENAME COLUMN metadata TO connector_metadata"))
        
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        print(f"[DB Migration] Skipping connectors table creation/migration: {e}")

    # Clean legacy mode keys with random suffix (e.g., student-722f) if the base key is free
    try:
        modes = UserMode.query.all()
        changed = False
        for m in modes:
            match = re.match(r"^(.*)-[0-9a-fA-F]{4}$", m.key or "")
            if match:
                base = match.group(1)
                clash = UserMode.query.filter_by(user_id=m.user_id, key=base).first()
                if not clash:
                    old_key = m.key
                    m.key = base
                    changed = True
                    print(f"[DB Migration] Renamed mode key {old_key} -> {base} for user {m.user_id}")
        if changed:
            db.session.commit()
    except Exception as e:
        db.session.rollback()
        print(f"[DB Migration] Error normalizing mode keys: {e}")

# Mode templates (suggestions). Not automatically created for a user.
MODE_TEMPLATES = [
    {
        "id": "student",
        "key": "student",
        "name": "Student Assistant",
        "emoji": "🎓",
        "baseRole": "student",
        "description": "Homework, study planning, deadlines, and academic advice.",
        "defaultTags": ["student"],
        "crossModeSources": ["job"],
        "isCustom": False,
    },
    {
        "id": "parent",
        "key": "parent",
        "name": "Parent / Family Planner",
        "emoji": "👨‍👩‍👧",
        "baseRole": "parent",
        "description": "Managing family activities, kids' schedules, and household organization.",
        "defaultTags": ["parent"],
        "crossModeSources": ["student"],
        "isCustom": False,
    },
    {
        "id": "job",
        "key": "job",
        "name": "Job-Hunt Assistant",
        "emoji": "💼",
        "baseRole": "job",
        "description": "Job applications, interview prep, resume strategy, and networking.",
        "defaultTags": ["job"],
        "crossModeSources": ["student"],
        "isCustom": False,
    },
    {
        "id": "fitness",
        "key": "fitness",
        "name": "Fitness / Health",
        "emoji": "💪",
        "baseRole": "fitness",
        "description": "Workouts, habits, nutrition, and health routines.",
        "defaultTags": ["fitness", "health"],
        "crossModeSources": [],
        "isCustom": False,
    },
    {
        "id": "fashion",
        "key": "fashion",
        "name": "Fashion / Style",
        "emoji": "💅",
        "baseRole": "fashion",
        "description": "Outfit planning, wardrobe, styling ideas, and shopping lists.",
        "defaultTags": ["fashion", "style"],
        "crossModeSources": [],
        "isCustom": False,
    },
]

def slugify_mode_key(name: str) -> str:
    import re
    s = (name or "").strip().lower()
    s = re.sub(r'[^a-z0-9]+', '-', s)
    s = re.sub(r'-{2,}', '-', s).strip('-')
    return s[:40] if s else "mode"

def resolve_mode(user_id: str, mode_key: str) -> Dict[str, any]:
    """
    Resolve an incoming mode key into:
    - modeKey: the actual scope key used for memory tagging/isolation
    - baseRole: controls behavior/profile slicing/cross-role policy (student|parent|job)
    - displayName: optional
    """
    mode_key = (mode_key or "student").strip()
    # Template keys (allow resolving even if user hasn't created it yet)
    for m in MODE_TEMPLATES:
        if m["key"] == mode_key:
            return {
                "modeKey": mode_key,
                "baseRole": m["baseRole"],
                "label": m["name"],
                "description": m.get("description", ""),
                "defaultTags": m.get("defaultTags", []),
                "crossModeSources": m.get("crossModeSources", []),
                "isCustom": False,
            }

    # Custom mode
    try:
        custom = UserMode.query.filter_by(user_id=user_id, key=mode_key).first()
        if custom:
            # Use the stored base_role, or default to mode_key if not set
            base = custom.base_role if custom.base_role else mode_key
            import json
            try:
                default_tags = json.loads(custom.default_tags) if custom.default_tags else []
            except Exception:
                default_tags = []
            try:
                stored_cross = json.loads(custom.cross_mode_sources) if custom.cross_mode_sources else []
            except Exception:
                stored_cross = []

            # If cross sources empty, default to all other modes (built-ins + user)
            cross_sources = stored_cross
            if not cross_sources:
                other = set()
                for t in MODE_TEMPLATES:
                    if t["key"] != mode_key:
                        other.add(t["key"])
                for um in UserMode.query.filter_by(user_id=user_id).all():
                    if um.key != mode_key:
                        other.add(um.key)
                cross_sources = list(other)

            return {
                "modeKey": mode_key,
                "baseRole": base,
                "label": custom.name,
                "description": custom.description or "",
                "defaultTags": default_tags,
                "crossModeSources": cross_sources,
                "isCustom": True,
            }
    except Exception:
        pass

    # Fallback
    return {
        "modeKey": mode_key,
        "baseRole": "student",
        "label": mode_key,
        "description": "",
        "defaultTags": [],
        "crossModeSources": [],
        "isCustom": True,
    }

@app.route('/api/modes', methods=['GET'])
def list_modes():
    """List user-defined modes (modes are user-created; templates are separate)"""
    user = get_user_from_token(request)
    if not user:
        return jsonify({'error': 'Unauthorized'}), 401

    custom = UserMode.query.filter_by(user_id=user.id).order_by(UserMode.created_at.asc()).all()
    modes = []
    for m in custom:
        md = m.to_dict()
        modes.append({
            "id": md["key"],
            "key": md["key"],
            "name": md["name"],
            "emoji": md.get("emoji") or "✨",
            "baseRole": md.get("baseRole") or "student",
            "description": md.get("description") or "",
            "defaultTags": md.get("defaultTags") or [],
            "crossModeSources": md.get("crossModeSources") or [],
            "isCustom": True,
        })
    return jsonify({"modes": modes})

@app.route('/api/mode-templates', methods=['GET'])
def list_mode_templates():
    """List suggested mode templates (not created until user chooses)."""
    return jsonify({"templates": MODE_TEMPLATES})

@app.route('/api/events/upcoming', methods=['GET'])
def upcoming_events():
    """Upcoming events merged across all user modes."""
    user = get_user_from_token(request)
    if not user:
        return jsonify({'error': 'Unauthorized'}), 401

    from services.supermemory_client import get_recent_memories
    now = datetime.now(timezone.utc)

    # Load all user-created modes
    user_modes = UserMode.query.filter_by(user_id=user.id).order_by(UserMode.created_at.asc()).all()
    mode_map = {m.key: {"name": m.name, "emoji": m.emoji or "✨"} for m in user_modes}
    
    # Also include template/default modes that might have memories
    template_modes = {
        "student": {"name": "Student Assistant", "emoji": "🎓"},
        "parent": {"name": "Parent / Family Planner", "emoji": "👨‍👩‍👧"},
        "job": {"name": "Job-Hunt Assistant", "emoji": "💼"},
        "fitness": {"name": "Fitness / Health", "emoji": "💪"},
        "fashion": {"name": "Fashion / Style", "emoji": "💅"},
        "default": {"name": "Default", "emoji": "✨"},
    }
    
    # Merge template modes into mode_map (user-created modes take precedence)
    for key, meta in template_modes.items():
        if key not in mode_map:
            mode_map[key] = meta

    events = []
    for mode_key, meta in mode_map.items():
        memories = get_recent_memories(user.id, role=mode_key, limit=200)
        for mem in memories:
            md = mem.get('metadata', {}) or {}
            if (md.get('mode') or mode_key) != mode_key:
                continue
            if md.get('type') != 'event':
                continue

            date_str = md.get('event_date') or md.get('expires_at')
            if not date_str:
                continue

            try:
                dt = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
            except Exception:
                continue

            # Keep future events only
            if dt < now:
                continue

            text = mem.get('text') or mem.get('content') or ''
            
            # Filter out assistant responses - only show events from user messages
            text_lower = text.lower().strip()
            # Skip if it's clearly an assistant response
            assistant_patterns = [
                'important:',  # Fact memories from assistant responses
                'thanks for letting me know',
                'assistant provided',
                'i see you have',
                'i noticed you',
                'want me to',
                'want to',
            ]
            if any(text_lower.startswith(pattern) for pattern in assistant_patterns):
                continue
            
            # Only include events that start with "User asked:" (user messages) or don't have assistant indicators
            if md.get('source') == 'chat' and not text_lower.startswith('user asked:'):
                # If it's from chat but doesn't start with "User asked:", it's likely an assistant response
                # Check if it contains common assistant response patterns
                if any(pattern in text_lower for pattern in ['assistant', 'thanks', 'i can help', 'want me']):
                    continue
            
            # Extract clean event title
            title = md.get('title') or ''
            if not title:
                # Try to extract event name from text patterns
                import re
                # Patterns: "Event: X", "X on Y", "X - Y", "X meeting", "X exam"
                patterns = [
                    r'Event:\s*(.+?)(?:\.|$|on|at)',
                    r'(.+?)\s+(?:on|at|tomorrow|next week|coming up)',
                    r'(.+?)\s+(?:meeting|exam|interview|appointment|event)',
                    r'^(.+?)(?:\s*-\s*.+)?$',  # First part before dash
                ]
                for pattern in patterns:
                    match = re.search(pattern, text, re.IGNORECASE)
                    if match:
                        title = match.group(1).strip()
                        # Clean up common prefixes
                        title = re.sub(r'^(User asked:|Assistant|Important:)\s*', '', title, flags=re.IGNORECASE)
                        if len(title) > 5 and len(title) < 100:
                            break
                
                # Fallback: use first sentence or first 60 chars
                if not title or len(title) < 5:
                    # Get first sentence
                    first_sentence = text.split('.')[0].split('!')[0].split('?')[0].strip()
                    if len(first_sentence) > 5 and len(first_sentence) <= 80:
                        title = first_sentence
                    else:
                        # Just use first 60 chars, clean up
                        title = text[:60].strip()
                        # Remove common prefixes
                        title = re.sub(r'^(User asked:|Assistant|Important:)\s*', '', title, flags=re.IGNORECASE)
                        if len(title) > 60:
                            title = title[:60].rstrip() + "…"
            
            # Clean up title
            title = title.strip()
            if len(title) > 80:
                title = title[:77] + "..."
            if not title:
                title = "Event"
            
            events.append({
                "id": mem.get('id'),
                "title": title,
                "date": dt.isoformat(),
                "modeId": mode_key,
                "modeName": meta["name"],
                "modeEmoji": meta["emoji"],
                "sourceText": text,
            })

    # Deduplicate events: if multiple events have same date and similar titles, keep only one
    deduplicated = []
    seen = set()
    for e in events:
        # Create a key based on date and normalized title
        date_key = e["date"][:10]  # Just the date part (YYYY-MM-DD)
        title_normalized = e["title"].lower().strip()[:50]  # First 50 chars, normalized
        dedup_key = f"{date_key}:{title_normalized}"
        
        # If we've seen a very similar event on the same date, skip it
        if dedup_key not in seen:
            seen.add(dedup_key)
            deduplicated.append(e)
    
    deduplicated.sort(key=lambda e: e["date"])
    limit = int(request.args.get('limit', 50))
    return jsonify({"events": deduplicated[:limit]})

@app.route('/api/modes', methods=['POST'])
def create_mode():
    """Create a new custom mode for the current user"""
    user = get_user_from_token(request)
    if not user:
        return jsonify({'error': 'Unauthorized'}), 401

    data = request.json or {}
    name = (data.get('name') or '').strip()
    emoji = (data.get('emoji') or '✨').strip()
    description = (data.get('description') or '').strip()
    default_tags = data.get('defaultTags') or []
    cross_sources = data.get('crossModeSources') or []

    if not name:
        return jsonify({'error': 'Mode name is required'}), 400

    # Generate mode key from name
    key = (data.get('key') or slugify_mode_key(name)).strip()
    
    # If base_role not provided, default to mode key (so each mode has its own baseRole)
    base_role = (data.get('baseRole') or key).strip()

    # Normalize list fields
    if not isinstance(default_tags, list):
        default_tags = []
    default_tags = [str(t).strip() for t in default_tags if str(t).strip()]
    if not isinstance(cross_sources, list):
        cross_sources = []
    cross_sources = [str(s).strip() for s in cross_sources if str(s).strip()]
    # Allow template keys like 'student'/'parent'/'job' because templates are not auto-created.
    # Uniqueness is still enforced per user below.

    # Ensure unique per user; do NOT append random suffix. If it exists, return it.
    exists = UserMode.query.filter_by(user_id=user.id, key=key).first()
    if exists:
        return jsonify({
            "mode": {
                "id": exists.key,
                "key": exists.key,
                "name": exists.name,
                "emoji": exists.emoji or "✨",
                "baseRole": exists.base_role or "student",
                "description": exists.description or "",
                "defaultTags": json.loads(exists.default_tags or "[]"),
                "crossModeSources": json.loads(exists.cross_mode_sources or "[]"),
                "isCustom": True,
            },
            "warning": "Mode already exists; returning existing mode."
        }), 200

    # Auto-borrow from all existing modes (built-ins + user modes)
    all_other_keys = set()
    # built-in templates
    for t in MODE_TEMPLATES:
        if t["key"] != key:
            all_other_keys.add(t["key"])
    # user modes
    for um in UserMode.query.filter_by(user_id=user.id).all():
        if um.key != key:
            all_other_keys.add(um.key)

    new_mode = UserMode(
        id=str(uuid.uuid4()),
        user_id=user.id,
        key=key,
        name=name,
        emoji=emoji[:4],
        base_role=base_role,
        description=description,
        default_tags=json.dumps(default_tags),
        cross_mode_sources=json.dumps(list(all_other_keys)),
    )
    db.session.add(new_mode)
    db.session.commit()

    return jsonify({
        "mode": {
            "id": new_mode.key,
            "key": new_mode.key,
            "name": new_mode.name,
            "emoji": new_mode.emoji or "✨",
            "baseRole": new_mode.base_role or "student",
            "description": new_mode.description or "",
            "defaultTags": default_tags,
            "crossModeSources": cross_sources,
            "isCustom": True,
        }
    }), 201

@app.route('/api/modes/<mode_key>', methods=['DELETE'])
def delete_mode(mode_key: str):
    """Delete a mode (does not delete memories; only removes the mode from the selector)"""
    user = get_user_from_token(request)
    if not user:
        return jsonify({'error': 'Unauthorized'}), 401
    
    # Cannot delete core built-in modes
    if mode_key in ['student', 'parent', 'job', 'default']:
        return jsonify({'error': 'Cannot delete core built-in modes'}), 400

    # Check if it's a custom mode
    mode = UserMode.query.filter_by(user_id=user.id, key=mode_key).first()
    if mode:
        db.session.delete(mode)
        db.session.commit()
        return jsonify({'success': True, 'message': 'Mode deleted successfully'})
    
    # If not found as custom mode, it might be a template mode (fitness, fashion)
    # These can be "deleted" by just not showing them (they're templates, not user data)
    # But we should return success since the user wants to remove it from their view
    return jsonify({'success': True, 'message': 'Mode removed from view'})

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

def check_duplicate_memory(user_id: str, role: str, user_message: str) -> Optional[Dict]:
    """Check if a similar memory already exists for this user message"""
    try:
        from services.supermemory_client import search_memories
        
        # Search for memories with similar user message context
        # Use the first part of user message as search query
        search_query = user_message[:100] if len(user_message) > 100 else user_message
        existing_memories = search_memories(user_id, search_query, role=role, limit=5)
        
        # Check for exact or very similar matches
        user_msg_lower = user_message.lower().strip()
        user_msg_words = set(user_msg_lower.split())
        
        for mem in existing_memories:
            mem_text = (mem.get('text') or mem.get('content') or '').lower()
            # Check if memory contains "User asked:" pattern with similar message
            if 'user asked:' in mem_text:
                # Extract the user message from memory text
                parts = mem_text.split('user asked:')
                if len(parts) > 1:
                    stored_msg = parts[1].split('.')[0].strip()[:150].lower()
                    stored_words = set(stored_msg.split())
                    
                    # Calculate similarity: if >70% words match, consider it duplicate
                    if len(user_msg_words) > 0:
                        similarity = len(user_msg_words & stored_words) / len(user_msg_words)
                        if similarity > 0.7 or stored_msg in user_msg_lower or user_msg_lower in stored_msg:
                            print(f"[Write Back] Found duplicate memory: {mem.get('id')} (similarity: {similarity:.2f})")
                            return mem
        
        return None
    except Exception as e:
        print(f"[Write Back] Error checking for duplicates: {e}")
        return None

def write_back_memories(user_id: str, role: str, user_message: str, llm_response: str, context_bundle: Dict) -> List[str]:
    """Write back memories from conversation with classification"""
    memory_ids = []
    
    # Create session summary memory
    summary_text = f"User asked: {user_message[:150]}. Assistant provided guidance on this topic."
    base_role = context_bundle.get("base_role") or role
    classification = classify_memory(base_role, summary_text)
    
    metadata = {
        'mode': role,  # mode key for strict UI separation
        'base_role': base_role,
        'source': 'chat',
        'createdAt': datetime.now(timezone.utc).isoformat(),
        'userId': user_id,
        'durability': classification.get('durability', 'medium'),
        'expires_at': classification.get('expires_at')
    }
    if classification.get('type'):
        metadata['type'] = classification.get('type')
    if classification.get('event_date'):
        metadata['event_date'] = classification.get('event_date')
    
    # Check for duplicate memory before creating
    duplicate = check_duplicate_memory(user_id, role, user_message)
    
    if duplicate:
        print(f"[Write Back] ⚠️ Duplicate memory detected, updating existing: {duplicate.get('id')}")
        # Update existing memory instead of creating new one
        try:
            from services.supermemory_client import SUPERMEMORY_API_URL, get_supermemory_headers
            import requests
            
            memory_id = duplicate.get('id')
            url = f'{SUPERMEMORY_API_URL}/memories/{memory_id}'
            
            # Update with new timestamp and response
            updated_text = f"User asked: {user_message[:150]}. Assistant provided guidance on this topic."
            payload = {
                'text': updated_text,
                'metadata': {**duplicate.get('metadata', {}), **metadata}
            }
            
            response = requests.put(url, headers=get_supermemory_headers(), json=payload)
            response.raise_for_status()
            memory_ids.append(memory_id)
            print(f"[Write Back] ✅ Updated existing memory: {memory_id}")
        except Exception as e:
            print(f"[Write Back] ❌ Failed to update duplicate memory: {e}")
            # Fall through to create new memory if update fails
            duplicate = None
    
    if not duplicate:
        print(f"[Write Back] Creating summary memory: {summary_text[:80]}...")
        # IMPORTANT: role=mode key to keep containerTags mode-scoped
        # Use defaultTags from mode config as extra container tags (for future boosting/filters)
        mode_cfg = context_bundle.get("mode_config") or {}
        extra_tags = []
        for t in (mode_cfg.get("defaultTags") or []):
            extra_tags.append(f"tag:{t}")
        result = create_memory(user_id, summary_text, metadata, role=role, extra_container_tags=extra_tags)
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
        fact_classification = classify_memory(base_role, fact_text)
        fact_metadata = {
            'mode': role,  # mode key for strict UI separation
            'base_role': base_role,
            'source': 'chat',
            'type': 'fact',
            'createdAt': datetime.now(timezone.utc).isoformat(),
            'userId': user_id,
            'durability': fact_classification.get('durability', 'medium'),
            'expires_at': fact_classification.get('expires_at')
        }
        # Don't classify assistant responses as events - only user messages should be events
        # Override event classification for assistant responses
        if fact_classification.get('type') == 'event':
            fact_metadata['type'] = 'fact'  # Keep as fact, not event
        elif fact_classification.get('type'):
            fact_metadata['type'] = fact_classification.get('type')
        # Don't set event_date for assistant responses
        # if fact_classification.get('event_date'):
        #     fact_metadata['event_date'] = fact_classification.get('event_date')
        
        print(f"[Write Back] Creating fact memory: {fact_text[:80]}...")
        fact_result = create_memory(user_id, fact_text, fact_metadata, role=role, extra_container_tags=extra_tags)
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

@app.route('/api/auth/delete-profile', methods=['DELETE'])
def delete_user_profile():
    """Delete user profile and all associated data"""
    user = get_user_from_token(request)
    if not user:
        return jsonify({'error': 'Unauthorized'}), 401
    
    user_id = user.id
    
    try:
        # Delete all user data
        # 1. Delete user modes
        UserMode.query.filter_by(user_id=user_id).delete()
        
        # 2. Delete connectors
        Connector.query.filter_by(user_id=user_id).delete()
        
        # 3. Delete conversations and messages
        conversations = Conversation.query.filter_by(user_id=user_id).all()
        for conv in conversations:
            Message.query.filter_by(conversation_id=conv.id).delete()
        Conversation.query.filter_by(user_id=user_id).delete()
        
        # 4. Delete tasks
        Task.query.filter_by(user_id=user_id).delete()
        
        # 5. Delete user account
        db.session.delete(user)
        db.session.commit()
        
        return jsonify({'success': True, 'message': 'User profile and all data deleted successfully'})
    except Exception as e:
        db.session.rollback()
        print(f"[Delete Profile] Error: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': f'Failed to delete profile: {str(e)}'}), 500

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
        mode_key = data.get('mode', 'student')
        messages = data.get('messages', [])
        use_search = data.get('useSearch', False)
        
        # Join multiple rapid messages into one
        user_message = ' '.join(messages) if isinstance(messages, list) else messages

        # Resolve custom mode -> base role (behavior) while keeping mode_key as the memory/conversation scope
        mode_info = resolve_mode(user_id, mode_key)
        mode_key = mode_info.get("modeKey", mode_key)
        base_role = mode_info.get("baseRole", mode_key)
        
        # Build context bundle using orchestrator
        context_bundle = build_context_for_turn(user_id, mode_info, user_message)
        
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
                role=base_role,
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
        print(f"[Chat] Writing back memories for user_id={user_id}, mode={mode_key}, base_role={base_role}")
        memory_ids = write_back_memories(user_id, mode_key, user_message, llm_response, context_bundle)
        print(f"[Chat] Memory creation result: {len(memory_ids)} memories created (IDs: {memory_ids})")
        
        # Save conversation history to database
        conversation_id = None
        if user_id != 'default':
            try:
                # Get or create conversation for this user and mode
                conversation = Conversation.query.filter_by(
                    user_id=user_id,
                    mode=mode_key
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
                        mode=mode_key,
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
    print(f"[Proactive] ===== PROACTIVE ENDPOINT CALLED =====")
    print(f"[Proactive] Request URL: {request.url}")
    print(f"[Proactive] Request args: {dict(request.args)}")
    try:
        # Get authenticated user or use default
        user = get_user_from_token(request)
        user_id = user.id if user else request.args.get('userId', 'default')
        
        mode_key = request.args.get('mode', 'student')
        print(f"[Proactive] Requested mode: '{mode_key}', userId: {user_id}")
        print(f"[Proactive] All request args: {dict(request.args)}")
        mode_info = resolve_mode(user_id, mode_key)
        mode_key = mode_info.get("modeKey", mode_key)
        mode_label = mode_info.get("label", mode_key)
        base_role = mode_info.get("baseRole", mode_key)
        print(f"[Proactive] Resolved mode_key: '{mode_key}', mode_label: '{mode_label}', base_role: '{base_role}'")
        print(f"[Proactive] Mode info: {mode_info}")
        
        # Get recent memories
        from services.supermemory_client import get_recent_memories
        memories = get_recent_memories(user_id, role=mode_key, limit=10)
        print(f"[Proactive] Found {len(memories)} recent memories")
        
        # If no memories, generate a welcoming message instead of returning None
        if not memories:
            print(f"[Proactive] No memories found, generating welcome message for {mode_label} mode")
            welcome_messages = {
                "student": "Hi! I'm here to help with your studies. What would you like to work on today?",
                "parent": "Hello! I can help with managing family activities, kids' schedules, and household organization. What do you need assistance with?",
                "job": "Hi there! I'm ready to help with your job search. What can I assist you with?",
                "fitness": "Hey! I'm here to help with your fitness and health goals. What would you like to focus on today?",
                "fitness-health": "Hey! I'm here to help with your fitness and health goals. What would you like to focus on today?",
                "fashion": "Hi! I'm here to help with your fashion and style choices. What would you like to work on today?"
            }
            # Try mode_key first (most specific), then check if it contains keywords, then fallback to mode_label
            # Don't use base_role as fallback since it might be "student" for fashion/fitness
            welcome_msg = welcome_messages.get(mode_key) or \
                         (welcome_messages.get("fitness") if mode_key and "fitness" in mode_key.lower() else None) or \
                         (welcome_messages.get("fashion") if mode_key and "fashion" in mode_key.lower() else None) or \
                         f"Hi! I'm your {mode_label} assistant. How can I help you today?"
            print(f"[Proactive] Returning welcome message for mode_key='{mode_key}', base_role='{base_role}', mode_label='{mode_label}'")
            print(f"[Proactive] Welcome message: '{welcome_msg}'")
            print(f"[Proactive] Available keys in welcome_messages: {list(welcome_messages.keys())}")
            return jsonify({'message': welcome_msg})
        
        # Build context from recent memories with metadata
        recent_context = []
        has_actionable_items = False
        
        for mem in memories[:5]:
            text = mem.get('text', '')[:200]
            metadata = mem.get('metadata', {})
            event_date = metadata.get('event_date')
            mem_type = metadata.get('type', 'memory')
            
            # Check if this memory has actionable content
            text_lower = text.lower()
            actionable_keywords = ['exam', 'test', 'deadline', 'meeting', 'event', 'interview', 'assignment', 
                                 'schedule', 'plan', 'goal', 'pta', 'activity', 'appointment', 'next week',
                                 'coming up', 'upcoming']
            if event_date or mem_type == 'event' or any(kw in text_lower for kw in actionable_keywords):
                has_actionable_items = True
            
            context_line = f"- {text}"
            if event_date:
                context_line += f" (Event date: {event_date})"
            if mem_type == 'event':
                context_line += " [EVENT]"
            recent_context.append(context_line)
        
        recent_context_str = '\n'.join(recent_context)
        
        # If no actionable items found in memories, still try to generate a helpful message
        # (but with a simpler prompt)
        if not has_actionable_items and len(memories) > 0:
            # Still generate a proactive message, but make it more general
            print(f"[Proactive] No actionable items found, but {len(memories)} memories available - generating general proactive message")
        
        # Get mode-specific context (base_role already set above)
        mode_description = mode_info.get("description", "")
        
        # Mode-specific proactive prompts
        mode_prompts = {
            "student": "You are a Student Assistant helping with homework, study planning, deadlines, and academic advice. Look for upcoming exams, assignments, study goals, or academic challenges. Suggest specific help like study plans, practice questions, or deadline reminders.",
            "parent": "You are a Parent/Family Assistant helping with managing family activities, kids' schedules, and household organization. Look for upcoming events, family activities, scheduling needs, or organizational tasks. Suggest specific help like activity planning, schedule coordination, or family reminders.",
            "job": "You are a Job-Hunt Assistant helping with job applications, interview prep, resume strategy, and networking. Look for job applications, interviews, networking opportunities, or career goals. Suggest specific help like interview prep, follow-up emails, or application strategies.",
            "fitness": "You are a Fitness/Health Assistant helping with workouts, exercise routines, nutrition, health goals, and wellness planning. Look for workout schedules, fitness goals, health habits, nutrition plans, or wellness activities. Suggest specific help like workout plans, meal planning, habit tracking, or health reminders.",
            "fashion": "You are a Fashion/Style Assistant helping with outfit planning, style choices, wardrobe organization, and fashion advice. Look for style questions, outfit needs, wardrobe planning, or fashion goals. Suggest specific help like outfit recommendations, wardrobe organization, style tips, or fashion inspiration."
        }
        
        # Use mode-specific prompt if available, otherwise use base_role, otherwise use mode_label/description
        if mode_key in mode_prompts:
            base_prompt = mode_prompts[mode_key]
        elif base_role in mode_prompts:
            base_prompt = mode_prompts[base_role]
        elif mode_description:
            base_prompt = f"You are a {mode_label} Assistant. {mode_description} Look for relevant activities, goals, or tasks. Suggest specific help related to this mode."
        else:
            base_prompt = mode_prompts["student"]
        
        # Generate proactive suggestion
        if has_actionable_items:
            prompt = f"""{base_prompt}

Recent memories in {mode_label} mode:
{recent_context_str}

CRITICAL RULES:
1. Generate a SPECIFIC actionable message based on the memories above
2. Reference a specific item from the memories (event name, exam subject, meeting type, etc.)
3. Offer concrete help (create schedule, prepare questions, draft email, etc.)
4. Be natural and conversational

Good examples (specific and actionable):
- "I see you have a machine learning exam next week. Want me to create a study schedule?"
- "There's a PTA meeting coming up. Need help preparing questions or organizing your notes?"
- "You have an interview scheduled. Want to practice common questions for that role?"
- "I noticed you're planning a family activity. Want help organizing the schedule?"
- "I see you're working on your fitness goals. Want me to create a workout plan?"
- "You mentioned starting a new exercise routine. Need help tracking your progress?"

Generate a helpful, specific proactive message. Make sure your response is complete and ends with a question or offer of help. Do not stop mid-sentence."""
        else:
            # More general prompt when no actionable items found
            prompt = f"""{base_prompt}

Recent memories in {mode_label} mode:
{recent_context_str}

Generate a helpful, conversational message that:
1. References something from the recent memories
2. Offers to help with a relevant task or question
3. Is natural and not generic
4. Is complete (at least 2-3 sentences)

Examples:
- "I see you've been discussing [topic from memories]. Want help with that?"
- "Based on our recent conversation, I can help you [relevant action]. Interested?"
- "I noticed [something specific from memories]. Want to explore that further?"

Generate a complete, helpful proactive message (at least 2-3 sentences). Do not stop mid-sentence."""

        if not client or not model_name:
            return jsonify({'message': None})
        
        try:
            system_context = f'You are a helpful assistant generating proactive conversation starters for {mode_label} mode. Be specific, actionable, and relevant to the user\'s actual context.'
            full_prompt = f"{system_context}\n\n{prompt}"
            
            from google.genai import types
            response = client.models.generate_content(
                model=model_name,
                contents=full_prompt,
                config=types.GenerateContentConfig(
                    temperature=0.7,  # Slightly higher for more natural responses
                    max_output_tokens=300,  # Increased further to prevent truncation
                    top_p=0.95,
                )
            )
            # Extract text from response (handle all parts)
            message = ""
            finish_reason = None
            
            if hasattr(response, 'text'):
                message = response.text
            elif hasattr(response, 'candidates') and response.candidates:
                candidate = response.candidates[0]
                
                # Check finish_reason
                if hasattr(candidate, 'finish_reason'):
                    finish_reason = candidate.finish_reason
                    print(f"[Proactive] Finish reason: {finish_reason}")
                
                # Check for safety ratings
                if hasattr(candidate, 'safety_ratings'):
                    safety_ratings = candidate.safety_ratings
                    print(f"[Proactive] Safety ratings: {safety_ratings}")
                
                if hasattr(candidate, 'content') and hasattr(candidate.content, 'parts'):
                    # Join all parts
                    message = ''.join([
                        part.text for part in candidate.content.parts 
                        if hasattr(part, 'text') and part.text
                    ])
                elif hasattr(candidate, 'content'):
                    message = str(candidate.content)
                else:
                    message = str(candidate)
            else:
                message = str(response)
            
            message = message.strip()
            
            # Log full message for debugging
            print(f"[Proactive] Full message extracted ({len(message)} chars): {message}")
            print(f"[Proactive] Finish reason: {finish_reason}")
            
            # Check if message seems incomplete (too short, no ending punctuation, or truncated)
            is_incomplete = (
                len(message) < 50 or  # Too short
                (finish_reason and 'MAX_TOKENS' in str(finish_reason)) or  # Hit token limit
                (not message.rstrip().endswith(('.', '!', '?')))  # No proper ending
            )
            
            if is_incomplete:
                print(f"[Proactive] Message seems incomplete ({len(message)} chars, finish_reason: {finish_reason}), using fallback")
                # Generate a simpler fallback message based on memories
                if memories and len(memories) > 0:
                    first_memory_text = memories[0].get('text', '')[:100]
                    # Extract key topic from memory
                    if first_memory_text:
                        # Simple extraction: take first 30-40 chars
                        topic = first_memory_text[:40].replace('\n', ' ').strip()
                        if len(topic) > 20:
                            message = f"I noticed you mentioned something about {topic}... Want to discuss this further or need help with it?"
                        else:
                            message = f"I see you've been working on something. Want to continue or need help?"
                    else:
                        message = f"Hi! I'm here to help with {mode_label.lower()} tasks. What can I assist you with?"
                else:
                    message = f"Hi! I'm your {mode_label} assistant. How can I help you today?"
            
            # Filter out generic/non-actionable messages
            if not message or len(message) < 10:
                return jsonify({'message': None})
            
            # Check for "None" response
            if message.lower().startswith('none'):
                return jsonify({'message': None})
            
            # Reject only very generic patterns (be more lenient)
            message_lower = message.lower()
            very_generic_patterns = [
                'want help with something',
                'need anything',
                'can i help',
                'how can i assist',
                'anything i can do'
            ]
            # Only reject if message is very short and contains very generic patterns
            if len(message) < 30 and any(pattern in message_lower for pattern in very_generic_patterns):
                print(f"[Proactive] Rejecting very generic message: {message[:50]}")
                return jsonify({'message': None})
            
            # Accept the message if it's reasonable length and not just "None"
            print(f"[Proactive] Accepting proactive message: {message[:100]}")
        except Exception as e:
            print(f"[Proactive] Error generating proactive message: {e}")
            import traceback
            traceback.print_exc()
            # On error, return a fallback welcome message instead of None
            welcome_messages = {
                "student": "Hi! I'm here to help with your studies. What would you like to work on today?",
                "parent": "Hello! I can help with managing family activities, kids' schedules, and household organization. What do you need assistance with?",
                "job": "Hi there! I'm ready to help with your job search. What can I assist you with?",
                "fitness": "Hey! I'm here to help with your fitness and health goals. What would you like to focus on today?",
                "fitness-health": "Hey! I'm here to help with your fitness and health goals. What would you like to focus on today?"
            }
            fallback_msg = welcome_messages.get(mode_key) or \
                          (welcome_messages.get("fitness") if mode_key and "fitness" in mode_key.lower() else None) or \
                          (welcome_messages.get("fashion") if mode_key and "fashion" in mode_key.lower() else None) or \
                          f"Hi! I'm your {mode_label} assistant. How can I help you today?"
            print(f"[Proactive] Returning fallback message due to error: {fallback_msg}")
            return jsonify({'message': fallback_msg})
        
        return jsonify({'message': message})
        
    except Exception as e:
        print(f"[Proactive] Error in proactive endpoint: {e}")
        import traceback
        traceback.print_exc()
        # Try to get mode info for fallback
        try:
            user = get_user_from_token(request)
            user_id = user.id if user else request.args.get('userId', 'default')
            mode_key = request.args.get('mode', 'student')
            mode_info = resolve_mode(user_id, mode_key)
            mode_key = mode_info.get("modeKey", mode_key)
            mode_label = mode_info.get("label", mode_key)
            base_role = mode_info.get("baseRole", mode_key)
            
            welcome_messages = {
                "student": "Hi! I'm here to help with your studies. What would you like to work on today?",
                "parent": "Hello! I can help with managing family activities, kids' schedules, and household organization. What do you need assistance with?",
                "job": "Hi there! I'm ready to help with your job search. What can I assist you with?",
                "fitness": "Hey! I'm here to help with your fitness and health goals. What would you like to focus on today?",
                "fitness-health": "Hey! I'm here to help with your fitness and health goals. What would you like to focus on today?"
            }
            fallback_msg = welcome_messages.get(mode_key) or \
                          (welcome_messages.get("fitness") if mode_key and "fitness" in mode_key.lower() else None) or \
                          (welcome_messages.get("fashion") if mode_key and "fashion" in mode_key.lower() else None) or \
                          f"Hi! I'm your {mode_label} assistant. How can I help you today?"
            print(f"[Proactive] Returning fallback message from outer exception handler: {fallback_msg}")
            return jsonify({'message': fallback_msg})
        except:
            return jsonify({'message': "Hi! How can I help you today?"})

@app.route('/api/memories', methods=['GET'])
def get_memories_endpoint():
    """Get memories for a user and mode"""
    try:
        # Get authenticated user or use default
        user = get_user_from_token(request)
        user_id = user.id if user else request.args.get('userId', 'default')
        
        mode = request.args.get('mode')  # Can be None for "all" filter
        
        print(f"[Get Memories] Fetching memories for user_id={user_id}, mode={mode or 'all'}")
        
        # Use the supermemory_client function directly with correct user_id and role
        from services.supermemory_client import get_recent_memories
        
        # Get recent memories (strictly filtered by role inside get_recent_memories if mode provided)
        # If mode is None, get_recent_memories will return all memories for the user
        memories = get_recent_memories(user_id, role=mode, limit=200 if mode is None else 50)
        
        # Format memories for frontend
        formatted_memories = []
        for mem in memories:
            # Handle different response formats from Supermemory API
            text = mem.get('text') or mem.get('content', '')
            metadata = mem.get('metadata', {})

            # Extra safety: enforce strict mode separation at the API boundary if mode is specified
            if mode and (metadata or {}).get('mode') != mode:
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
        
        role = request.args.get('role')  # Optional filter by mode_key (None = all modes)
        user_id = user.id
        
        # Get all memories for the user (optionally filtered by role)
        from services.supermemory_client import get_recent_memories
        memories = get_recent_memories(user_id, role=role, limit=200 if role is None else 100)
        
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
            mem_mode = metadata.get('mode', role or 'all')  # UI label + strict filter key
            mem_role = metadata.get('base_role', mem_mode)  # behavior for entity extraction
            mem_id = mem.get('id') or ''

            # Always add a "memory" node per memory so the graph is never empty
            memory_node_id = f"memory:{mem_id}" if mem_id else f"memory:local:{uuid.uuid4()}"
            if memory_node_id not in node_ids:
                nodes.append({
                    "id": memory_node_id,
                    "label": (text[:80] + "…") if len(text) > 80 else (text or "Memory"),
                    "type": "memory",
                    "role": mem_mode,
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
                        "role": mem_mode
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

def generate_file_summary(extracted_text: str, filename: str, file_type: str, base_role: str) -> str:
    """Generate a concise summary of file content using LLM"""
    try:
        GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
        if not GEMINI_API_KEY:
            # Fallback: return a simple summary if LLM is not available
            preview = extracted_text[:200].replace('\n', ' ')
            return f"Uploaded {file_type} file '{filename}': {preview}..."
        
        from google.genai import types
        client = genai.Client(api_key=GEMINI_API_KEY)
        model_name = 'gemini-2.5-flash'
        
        # Truncate text if too long (keep first 10000 chars for summary)
        text_for_summary = extracted_text[:10000] if len(extracted_text) > 10000 else extracted_text
        
        prompt = f"""You are analyzing a {file_type} file named "{filename}".

File content:
\"\"\"{text_for_summary}\"\"\"

Generate a concise summary (2-3 sentences, max 200 characters) describing what this file is about. Focus on:
- Main topic or purpose
- Key information or takeaways
- What someone would need to know about this file

Do not include the full content. Just a brief description.

Summary:"""
        
        response = client.models.generate_content(
            model=model_name,
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=0.3,
                max_output_tokens=150,
            )
        )
        
        # Extract text from response
        if hasattr(response, 'text'):
            summary = response.text.strip()
        elif hasattr(response, 'candidates') and response.candidates:
            candidate = response.candidates[0]
            if hasattr(candidate, 'content') and hasattr(candidate.content, 'parts'):
                summary = ''.join([part.text for part in candidate.content.parts if hasattr(part, 'text')]).strip()
            else:
                summary = str(candidate).strip()
        else:
            summary = str(response).strip()
        
        # Fallback if summary is too long or empty
        if not summary or len(summary) > 300:
            preview = extracted_text[:150].replace('\n', ' ')
            summary = f"Uploaded {file_type} file '{filename}': {preview}..."
        
        return summary
        
    except Exception as e:
        print(f"Error generating file summary: {e}")
        # Fallback: return a simple summary
        preview = extracted_text[:150].replace('\n', ' ')
        return f"Uploaded {file_type} file '{filename}': {preview}..."

# File Upload Endpoint
@app.route('/api/upload', methods=['POST'])
def upload_file():
    """Upload and process a file, creating memories from extracted content"""
    try:
        user = get_user_from_token(request)
        if not user:
            return jsonify({'error': 'Unauthorized'}), 401
        
        if 'file' not in request.files:
            return jsonify({'error': 'No file provided'}), 400
        
        file = request.files['file']
        mode_key = request.form.get('mode', 'student')
        
        if file.filename == '':
            return jsonify({'error': 'No file selected'}), 400
        
        # Process file using file_processor
        from services.file_processor import process_file_upload
        file_metadata = process_file_upload(file, user.id)
        
        if not file_metadata:
            return jsonify({'error': 'Failed to process file'}), 400
        
        extracted_text = file_metadata.get('extracted_text', '')
        if not extracted_text or len(extracted_text.strip()) < 10:
            return jsonify({'error': 'No text could be extracted from file'}), 400
        
        # Resolve mode config
        mode_info = resolve_mode(user.id, mode_key)
        mode_key = mode_info.get("modeKey", mode_key)
        base_role = mode_info.get("baseRole", mode_key)
        
        # Generate summary of file content
        filename = file_metadata.get('filename', 'unknown')
        file_type = file_metadata.get('file_type', 'document')
        summary_text = generate_file_summary(extracted_text, filename, file_type, base_role)
        
        # Classify memory based on summary
        classification = classify_memory(base_role, summary_text)
        
        # Create memory with summary as text, full content in metadata
        metadata = {
            'mode': mode_key,
            'base_role': base_role,
            'source': 'file_upload',
            'filename': filename,
            'file_type': file_type,
            'file_size': file_metadata.get('file_size'),
            'full_content': extracted_text,  # Store full content in metadata for search
            'createdAt': datetime.now(timezone.utc).isoformat(),
            'userId': user.id,
            'durability': classification.get('durability', 'medium'),
            'type': 'document'
        }
        if classification.get('type'):
            metadata['type'] = classification.get('type')
        if classification.get('event_date'):
            metadata['event_date'] = classification.get('event_date')
        
        # Create memories from file content
        mode_cfg = mode_info or {}
        extra_tags = []
        for t in (mode_cfg.get("defaultTags") or []):
            extra_tags.append(f"tag:{t}")
        
        memory_ids = []
        
        # 1. Create a summary memory for quick reference
        summary_metadata = metadata.copy()
        summary_metadata['is_summary'] = True
        summary_result = create_memory(user.id, summary_text, summary_metadata, role=mode_key, extra_container_tags=extra_tags)
        if summary_result and summary_result.get('id'):
            memory_ids.append(summary_result['id'])
            print(f"[File Upload] Created summary memory: {summary_result.get('id')}")
        
        # 2. Create content memories from the actual file content (chunked if large)
        # Chunk large text into manageable pieces (max 4000 chars per memory for content)
        content_chunks = []
        if len(extracted_text) > 4000:
            # Smart chunking: split by paragraphs, then by sentences if needed
            paragraphs = extracted_text.split('\n\n')
            current_chunk = ''
            for para in paragraphs:
                para = para.strip()
                if not para:
                    continue
                    
                # If adding this paragraph would exceed limit, save current chunk
                if len(current_chunk) + len(para) + 2 > 4000:
                    if current_chunk:
                        content_chunks.append(current_chunk.strip())
                    current_chunk = para
                else:
                    current_chunk += '\n\n' + para if current_chunk else para
            
            # Add remaining chunk
            if current_chunk:
                content_chunks.append(current_chunk.strip())
        else:
            content_chunks = [extracted_text] if extracted_text.strip() else []
        
        # Create a memory for each content chunk
        for i, chunk in enumerate(content_chunks):
            if not chunk or len(chunk.strip()) < 10:
                continue
                
            chunk_metadata = metadata.copy()
            chunk_metadata['is_content'] = True
            chunk_metadata['chunk_index'] = i
            chunk_metadata['total_chunks'] = len(content_chunks)
            if i == 0:
                chunk_metadata['is_first_chunk'] = True
            
            # Use chunk as memory text (actual content, not summary)
            chunk_result = create_memory(user.id, chunk, chunk_metadata, role=mode_key, extra_container_tags=extra_tags)
            if chunk_result and chunk_result.get('id'):
                memory_ids.append(chunk_result['id'])
                print(f"[File Upload] Created content memory chunk {i+1}/{len(content_chunks)}: {chunk_result.get('id')}")
        
        print(f"[File Upload] Created {len(memory_ids)} memories from file '{filename}' ({len(extracted_text)} chars)")
        
        return jsonify({
            'success': True,
            'memoryIds': memory_ids,
            'fileMetadata': {
                'filename': filename,
                'fileType': file_type,
                'fileSize': file_metadata.get('file_size'),
                'textLength': file_metadata.get('text_length'),
                'summary': summary_text,
                'chunksCreated': len(content_chunks) + 1  # +1 for summary
            }
        }), 201
        
    except Exception as e:
        print(f"Error uploading file: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

# Connector Management Endpoints
@app.route('/api/connectors', methods=['GET'])
def list_connectors():
    """List all connectors for the current user"""
    try:
        user = get_user_from_token(request)
        if not user:
            return jsonify({'error': 'Unauthorized'}), 401
        
        connectors = Connector.query.filter_by(user_id=user.id).all()
        return jsonify({
            'connectors': [conn.to_dict() for conn in connectors]
        })
    except Exception as e:
        print(f"Error listing connectors: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/connectors/<provider>/connect', methods=['POST'])
def connect_connector(provider: str):
    """Initiate connection to a connector provider"""
    try:
        user = get_user_from_token(request)
        if not user:
            return jsonify({'error': 'Unauthorized'}), 401
        
        data = request.json or {}
        redirect_url = data.get('redirectUrl', f'http://localhost:3000/connectors/callback')
        
        # Initiate connection via Supermemory API
        from services.integrations import get_connector_auth_url
        auth_info = get_connector_auth_url(user.id, provider, redirect_url)
        
        # Store connector state in database
        existing = Connector.query.filter_by(user_id=user.id, provider=provider).first()
        if existing:
            existing.connection_id = auth_info.get('connectionId')
            existing.status = 'pending' if auth_info.get('requiresOAuth') else 'connected'
            existing.updated_at = datetime.now(timezone.utc)
        else:
            connector = Connector(
                id=str(uuid.uuid4()),
                user_id=user.id,
                provider=provider,
                connection_id=auth_info.get('connectionId'),
                status='pending' if auth_info.get('requiresOAuth') else 'connected',
                connector_metadata=json.dumps(auth_info)
            )
            db.session.add(connector)
        
        db.session.commit()
        
        return jsonify({
            'authUrl': auth_info.get('authUrl'),
            'connectionId': auth_info.get('connectionId'),
            'requiresOAuth': auth_info.get('requiresOAuth', False)
        })
    except Exception as e:
        print(f"Error connecting {provider}: {e}")
        db.session.rollback()
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/api/connectors/<provider>/callback', methods=['POST'])
def connector_callback(provider: str):
    """Handle OAuth callback and update connection status"""
    try:
        user = get_user_from_token(request)
        if not user:
            return jsonify({'error': 'Unauthorized'}), 401
        
        data = request.json or {}
        connection_id = data.get('connectionId')
        
        if not connection_id:
            return jsonify({'error': 'connectionId required'}), 400
        
        # Process callback
        from services.integrations import process_connection_callback
        result = process_connection_callback(provider, connection_id, user.id)
        
        # Update connector in database
        connector = Connector.query.filter_by(user_id=user.id, provider=provider).first()
        if connector:
            connector.connection_id = connection_id
            connector.status = 'connected' if result.get('success') else 'error'
            connector.updated_at = datetime.now(timezone.utc)
            connector.last_sync_at = datetime.now(timezone.utc) if result.get('success') else None
            db.session.commit()
        
        return jsonify(result)
    except Exception as e:
        print(f"Error processing callback for {provider}: {e}")
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@app.route('/api/connectors/<provider>/sync', methods=['POST'])
def sync_connector(provider: str):
    """Trigger manual sync for a connector"""
    try:
        user = get_user_from_token(request)
        if not user:
            return jsonify({'error': 'Unauthorized'}), 401
        
        connector = Connector.query.filter_by(user_id=user.id, provider=provider).first()
        if not connector or not connector.connection_id:
            return jsonify({'error': 'Connector not found or not connected'}), 404
        
        from services.integrations import sync_connection
        result = sync_connection(connector.connection_id)
        
        if result.get('success'):
            connector.last_sync_at = datetime.now(timezone.utc)
            db.session.commit()
        
        return jsonify(result)
    except Exception as e:
        print(f"Error syncing {provider}: {e}")
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@app.route('/api/connectors/<provider>', methods=['DELETE'])
def disconnect_connector(provider: str):
    """Disconnect a connector"""
    try:
        user = get_user_from_token(request)
        if not user:
            return jsonify({'error': 'Unauthorized'}), 401
        
        connector = Connector.query.filter_by(user_id=user.id, provider=provider).first()
        if not connector:
            return jsonify({'error': 'Connector not found'}), 404
        
        # Disconnect via Supermemory API
        if connector.connection_id:
            from services.integrations import disconnect_connection
            disconnect_connection(connector.connection_id)
        
        # Remove from database
        db.session.delete(connector)
        db.session.commit()
        
        return jsonify({'success': True})
    except Exception as e:
        print(f"Error disconnecting {provider}: {e}")
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


# --- n8n ingest webhook (for unsupported connectors like Gmail/LinkedIn/Calendar) ---
@app.route('/api/n8n/ingest', methods=['POST'])
def ingest_from_n8n():
    """
    Accepts batched items from an n8n workflow and creates memories.
    Expected JSON:
    {
      "userId": "<user-id>",
      "mode": "default",
      "source": "gmail|linkedin|calendar|n8n",
      "items": [
        {
          "title": "...",
          "text": "...",
          "metadata": {...},
          "event_date": "YYYY-MM-DD",
          "type": "event|memory|document"
        }
      ]
    }
    Headers: X-N8N-SECRET must match env N8N_WEBHOOK_SECRET (if set).
    """
    try:
        if N8N_WEBHOOK_SECRET:
            provided = request.headers.get('X-N8N-SECRET')
            if provided != N8N_WEBHOOK_SECRET:
                return jsonify({'error': 'Unauthorized'}), 401

        data = request.json or {}
        user_id = data.get('userId') or data.get('user_id')
        if not user_id:
            return jsonify({'error': 'userId is required'}), 400

        mode_key = data.get('mode') or 'default'
        source = data.get('source') or 'n8n'
        items = data.get('items') or []
        if not isinstance(items, list) or len(items) == 0:
            return jsonify({'error': 'items must be a non-empty list'}), 400

        # Resolve mode config (cross-mode tags, etc.)
        mode_info = resolve_mode(user_id, mode_key) or {}
        mode_key = mode_info.get("modeKey", mode_key)
        base_role = mode_info.get("baseRole", mode_key)
        extra_tags = []
        for t in (mode_info.get("defaultTags") or []):
            extra_tags.append(f"tag:{t}")

        created_ids = []
        errors = []

        for idx, item in enumerate(items):
            text = item.get('text') or item.get('content') or item.get('body') or ''
            title = item.get('title') or item.get('subject') or ''
            if title and title not in (text or ''):
                text = f"{title}\n\n{text}".strip()

            if not text:
                errors.append({'index': idx, 'error': 'missing text'})
                continue

            metadata = (item.get('metadata') or {}).copy()
            metadata.update({
                'mode': mode_key,
                'base_role': base_role,
                'source': item.get('source') or source,
                'via': 'n8n',
                'userId': user_id
            })

            if item.get('event_date'):
                metadata['event_date'] = item.get('event_date')
                metadata.setdefault('type', 'event')
            if item.get('type'):
                metadata['type'] = item.get('type')

            # Classify to set durability/expiry/type if not provided
            classification = classify_memory(base_role, text)
            for k in ['durability', 'expires_at', 'type', 'event_date']:
                if classification.get(k) and k not in metadata:
                    metadata[k] = classification[k]

            try:
                result = create_memory(
                    user_id,
                    text,
                    metadata,
                    role=mode_key,
                    extra_container_tags=extra_tags
                )
                if result and result.get('id'):
                    created_ids.append(result['id'])
                else:
                    errors.append({'index': idx, 'error': 'create_memory failed'})
            except Exception as e:
                errors.append({'index': idx, 'error': str(e)})

        status = 207 if errors else 201
        return jsonify({
            'created': len(created_ids),
            'ids': created_ids,
            'errors': errors
        }), status
    except Exception as e:
        print(f"Error ingesting from n8n: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


# --- Calendar / ICS Import (simple) ---
def _parse_ics_events(ics_text: str):
    events = []
    current = {}
    for raw in (ics_text or "").splitlines():
        line = raw.strip()
        upper = line.upper()
        if upper.startswith("BEGIN:VEVENT"):
            current = {}
        elif upper.startswith("END:VEVENT"):
            if current.get("summary"):
                events.append(current)
            current = {}
        elif upper.startswith("SUMMARY:"):
            current["summary"] = line.split("SUMMARY:", 1)[1].strip()
        elif upper.startswith("DTSTART"):
            if ":" in line:
                dt_raw = line.split(":", 1)[1].strip()
                if "T" in dt_raw and len(dt_raw) >= 8:
                    yyyy = dt_raw[0:4]; mm = dt_raw[4:6]; dd = dt_raw[6:8]
                    current["event_date"] = f"{yyyy}-{mm}-{dd}"
                elif len(dt_raw) == 8:
                    yyyy = dt_raw[0:4]; mm = dt_raw[4:6]; dd = dt_raw[6:8]
                    current["event_date"] = f"{yyyy}-{mm}-{dd}"
    return events

@app.route('/api/calendar/import', methods=['POST'])
def import_calendar():
    """Import calendar events from an ICS file or text and create event memories."""
    try:
        user = get_user_from_token(request)
        if not user:
            return jsonify({'error': 'Unauthorized'}), 401

        mode = request.form.get('mode') or request.args.get('mode') or 'default'
        ics_text = None

        if 'file' in request.files:
            f = request.files['file']
            ics_text = f.read().decode('utf-8', errors='ignore')
        else:
            ics_text = request.form.get('ics') or request.get_data(as_text=True)

        if not ics_text:
            return jsonify({'error': 'No ICS content provided'}), 400

        events = _parse_ics_events(ics_text)
        if not events:
            return jsonify({'error': 'No events found in ICS'}), 400

        created = []
        for ev in events:
            summary = ev.get("summary") or "Calendar event"
            event_date = ev.get("event_date")
            text = f"Event: {summary}"
            metadata = {
                'mode': mode,
                'source': 'calendar_import',
                'type': 'event',
                'title': summary,
                'createdAt': datetime.now(timezone.utc).isoformat(),
                'userId': user.id
            }
            if event_date:
                metadata['event_date'] = event_date
                metadata['expires_at'] = event_date

            classification = classify_memory(mode, text)
            if classification.get('durability'):
                metadata['durability'] = classification['durability']
            if classification.get('expires_at') and not metadata.get('expires_at'):
                metadata['expires_at'] = classification['expires_at']

            result = create_memory(user.id, text, metadata, role=mode)
            if result and result.get('id'):
                created.append(result.get('id'))

        return jsonify({'imported': len(created), 'ids': created})
    except Exception as e:
        print(f"Error importing calendar: {e}")
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True, port=5001)