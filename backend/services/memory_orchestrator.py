"""Memory orchestrator for context engineering"""
from typing import Dict, Any, List
from datetime import datetime, timezone
from .supermemory_client import (
    get_profile_memory,
    search_memories,
    get_recent_memories
)
from models import UserProfile

def build_context_for_turn(user_id: str, role: str, user_message: str) -> Dict[str, Any]:
    """
    Build context bundle for a chat turn:
    - Static profile slice (role-specific)
    - Recent episodic context
    - Long-term relevant memories
    """
    # 1. Static profile slice
    profile_data = get_profile_memory(user_id)
    if profile_data:
        try:
            profile = UserProfile.from_dict(profile_data)
        except:
            profile = None
    else:
        profile = None
    
    static_slice = build_static_slice(profile, role) if profile else {}
    
    # 2. Recent episodic context (last N chat turns / tasks)
    recent = get_recent_memories(user_id, role=role, limit=5)
    
    # 3. Long-term search from Supermemory
    search_results = search_memories(
        user_id=user_id,
        query=user_message,
        role=role,
        limit=10
    )
    
    # 4. Re-rank and trim to context budget
    selected_long_term = rerank_and_trim(search_results, user_message, max_items=5)
    
    return {
        "static_profile": static_slice,
        "recent_memories": recent,
        "long_term_memories": selected_long_term,
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

