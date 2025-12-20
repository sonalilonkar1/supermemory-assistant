"""Memory classification and expiry system"""
from datetime import datetime, timedelta, timezone
from typing import Dict, Optional

def classify_memory(role: str, content: str, context: Optional[Dict] = None) -> Dict[str, any]:
    """
    Classify memory by durability and set expiry.
    Returns dict with durability and expires_at.
    """
    now = datetime.now(timezone.utc)
    content_lower = content.lower()
    
    # Parent role classifications
    if role == "parent":
        if any(keyword in content_lower for keyword in ["fridge", "grocery", "shopping list", "buy"]):
            return {
                "durability": "ephemeral",
                "expires_at": (now + timedelta(days=7)).isoformat()
            }
        
        if any(keyword in content_lower for keyword in ["school event", "parent-teacher", "field trip"]):
            # Try to extract date from context or content
            expires_days = 30
            if context and context.get('event_date'):
                try:
                    event_date = datetime.fromisoformat(context['event_date'])
                    expires_at = event_date + timedelta(days=1)
                    return {
                        "durability": "medium",
                        "expires_at": expires_at.isoformat()
                    }
                except:
                    pass
            return {
                "durability": "medium",
                "expires_at": (now + timedelta(days=expires_days)).isoformat()
            }
    
    # Student role classifications
    if role == "student":
        if any(keyword in content_lower for keyword in ["exam", "midterm", "final", "test"]):
            expires_days = 30
            if context and context.get('exam_date'):
                try:
                    exam_date = datetime.fromisoformat(context['exam_date'])
                    expires_at = exam_date + timedelta(days=7)
                    return {
                        "durability": "medium",
                        "expires_at": expires_at.isoformat()
                    }
                except:
                    pass
            return {
                "durability": "medium",
                "expires_at": (now + timedelta(days=expires_days)).isoformat()
            }
        
        if any(keyword in content_lower for keyword in ["homework", "assignment", "due"]):
            return {
                "durability": "ephemeral",
                "expires_at": (now + timedelta(days=14)).isoformat()
            }
    
    # Job role classifications
    if role == "job":
        if any(keyword in content_lower for keyword in ["applied to", "application", "interview", "rejected", "offer"]):
            return {
                "durability": "long",
                "expires_at": None  # No expiry, but will decay over time
            }
        
        if any(keyword in content_lower for keyword in ["networking", "coffee chat", "meeting"]):
            return {
                "durability": "medium",
                "expires_at": (now + timedelta(days=60)).isoformat()
            }
    
    # Default classification
    return {
        "durability": "medium",
        "expires_at": (now + timedelta(days=90)).isoformat()
    }

