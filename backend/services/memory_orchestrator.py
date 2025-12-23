"""Memory orchestrator for context engineering"""
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone
from .supermemory_client import (
    get_profile_memory,
    search_memories,
    get_recent_memories
)
from models import UserProfile

def build_context_for_turn(user_id: str, mode_config: Dict[str, Any], user_message: str) -> Dict[str, Any]:
    """
    Build context bundle for a chat turn:
    - Static profile slice (based on base_role)
    - Recent episodic context (scoped to mode_key)
    - Long-term relevant memories (scoped to mode_key)
    - Optional cross-role context (scoped to canonical base roles)
    """
    mode_key = (mode_config or {}).get("modeKey") or (mode_config or {}).get("key") or "student"
    base_role = (mode_config or {}).get("baseRole") or mode_key
    # 1. Static profile slice
    profile_data = get_profile_memory(user_id)
    if profile_data:
        try:
            profile = UserProfile.from_dict(profile_data)
        except:
            profile = None
    else:
        profile = None
    
    static_slice = build_static_slice(profile, base_role) if profile else {}
    cross_role_static = build_cross_role_static(profile, base_role) if profile else {}
    
    # 2. Recent episodic context (last N chat turns / tasks)
    recent = get_recent_memories(user_id, role=mode_key, limit=5)
    
    # 3. Long-term search from Supermemory
    search_results = search_memories(
        user_id=user_id,
        query=user_message,
        role=mode_key,
        limit=10
    )
    
    # 4. Re-rank and trim to context budget
    selected_long_term = rerank_and_trim(search_results, user_message, max_items=5)

    # 5. Cross-role context (tight budget, only for assistant reasoning — UI still separated)
    # Cross-mode borrow sources are driven by mode config (dynamic modes)
    cross_sources = (mode_config or {}).get("crossModeSources") or []
    cross_role_memories: List[Dict] = []
    if cross_sources:
        merged: List[Dict] = []
        for source_mode in cross_sources:
            try:
                merged.extend(search_memories(user_id=user_id, query=user_message, role=source_mode, limit=6))
            except Exception:
                pass
        cross_role_memories = rerank_and_trim(merged, user_message, max_items=3)
    
    return {
        "active_mode": mode_key,
        "base_role": base_role,
        "mode_config": mode_config,
        "static_profile": static_slice,
        # Cross-role static slice is derived from base_role and stays small/safe
        "cross_role_static": cross_role_static,
        "recent_memories": recent,
        "long_term_memories": selected_long_term,
        "cross_role_memories": cross_role_memories,
    }

def build_static_slice(profile: UserProfile, role: str) -> dict:
    """Build role-specific static profile slice"""
    base = {
        "name": profile.name,
        "city": profile.city,
    }
    
    if role == "parent":
        return {
            **base,
            "kids": profile.parent.kids,
            "schools": profile.parent.schools,
            "recurring_events": profile.parent.recurring_events,
        }
    
    if role == "student":
        return {
            **base,
            "degree": profile.student.degree,
            "year": profile.student.year,
            "courses": profile.student.courses,
            "upcoming_exams": profile.student.upcoming_exams,
        }
    
    if role == "job":
        return {
            **base,
            "target_roles": profile.job.target_roles,
            "target_locations": profile.job.target_locations,
            "salary_band": profile.job.salary_band,
            "companies_of_interest": profile.job.companies_of_interest,
        }
    
    return base

def get_cross_roles_for(role: str) -> List[str]:
    """
    Which other roles are allowed to be consulted for context?
    Keep this conservative; the goal is 'borrow relevant facts', not merge personas.
    """
    if role == "job":
        return ["student"]  # education/courses are often relevant for resumes
    if role == "student":
        return ["job"]      # career goals can influence course planning
    if role == "parent":
        return ["student"]  # schedules/exams can affect family activities
    return []

def build_cross_role_static(profile: Optional[UserProfile], role: str) -> Dict[str, Any]:
    """
    Small, safe cross-role profile slice. This is *not* the full profile;
    it's a compact set of facts that are commonly relevant across roles.
    """
    if not profile:
        return {}

    # Job mode often needs education / courses / school name
    if role == "job":
        return {
            "education": {
                "degree": profile.student.degree,
                "year": profile.student.year,
                "courses": profile.student.courses,
            }
        }

    # Student mode can use job goals to tailor study strategy
    if role == "student":
        return {
            "career_goals": {
                "target_roles": profile.job.target_roles,
                "companies_of_interest": profile.job.companies_of_interest,
            }
        }

    # Parent mode can use student exam schedule (if present)
    if role == "parent":
        return {
            "school_schedule": {
                "upcoming_exams": profile.student.upcoming_exams,
                "courses": profile.student.courses,
            }
        }

    return {}

def rerank_and_trim(search_results: List[Dict], user_message: str, max_items: int = 5) -> List[Dict]:
    """
    Re-rank search results and trim to context budget.
    Simple relevance scoring based on keyword overlap.
    """
    if not search_results:
        return []
    
    # Simple scoring: count keyword matches
    user_keywords = set(user_message.lower().split())
    
    scored = []
    for mem in search_results:
        text = mem.get('text', '').lower()
        score = sum(1 for keyword in user_keywords if keyword in text)
        
        # Boost score for recent memories
        metadata = mem.get('metadata', {})
        created_at = metadata.get('createdAt')
        if created_at:
            try:
                created = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
                days_old = (datetime.now(timezone.utc) - created.replace(tzinfo=timezone.utc)).days
                if days_old < 7:
                    score += 1  # Boost recent memories
            except:
                pass
        
        scored.append((score, mem))
    
    # Sort by score (descending) and take top N
    scored.sort(key=lambda x: x[0], reverse=True)
    return [mem for _, mem in scored[:max_items]]

def format_memories(memories: List[Dict]) -> str:
    """Format memories for prompt inclusion"""
    if not memories:
        return "None"
    
    formatted = []
    for mem in memories:
        text = mem.get('text', '')
        metadata = mem.get('metadata', {})
        created = metadata.get('createdAt', '')
        
        # Truncate long memories
        if len(text) > 200:
            text = text[:200] + "..."
        
        formatted.append(f"- {text} (from {created[:10] if created else 'memory'})")
    
    return "\n".join(formatted)

