"""Memory classification and expiry system"""
from datetime import datetime, timedelta, timezone
from typing import Dict, Optional, Tuple

MONTHS = {
    "jan": 1, "january": 1,
    "feb": 2, "february": 2,
    "mar": 3, "march": 3,
    "apr": 4, "april": 4,
    "may": 5,
    "jun": 6, "june": 6,
    "jul": 7, "july": 7,
    "aug": 8, "august": 8,
    "sep": 9, "september": 9,
    "oct": 10, "october": 10,
    "nov": 11, "november": 11,
    "dec": 12, "december": 12,
}

def _try_parse_event_date(now: datetime, content: str) -> Optional[str]:
    """
    Best-effort date extraction from text.
    Returns ISO datetime string (UTC) if found.
    """
    import re
    s = (content or "").strip()
    if not s:
        return None

    # ISO date: 2025-12-31
    m = re.search(r'\b(20\d{2})-(\d{1,2})-(\d{1,2})\b', s)
    if m:
        y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
        try:
            dt = datetime(y, mo, d, 9, 0, tzinfo=timezone.utc)
            return dt.isoformat()
        except Exception:
            pass

    # Month name + day (+ optional year): March 5, 2026 OR 5th January OR January 5th
    # Try "Month Day" format first
    m = re.search(r'\b([A-Za-z]{3,9})\s+(\d{1,2})(?:st|nd|rd|th)?(?:,?\s*(20\d{2}))?\b', s)
    if m:
        mon_raw, day_raw, year_raw = m.group(1).lower(), m.group(2), m.group(3)
        mon = MONTHS.get(mon_raw)
        if mon:
            day = int(day_raw)
            year = int(year_raw) if year_raw else now.year
            # If no year and date already passed this year, assume next year.
            try:
                dt = datetime(year, mon, day, 9, 0, tzinfo=timezone.utc)
                if not year_raw and dt < now:
                    dt = datetime(year + 1, mon, day, 9, 0, tzinfo=timezone.utc)
                return dt.isoformat()
            except Exception:
                pass
    
    # Try "Day Month" format: 5th January, 5 January
    m = re.search(r'\b(\d{1,2})(?:st|nd|rd|th)?\s+([A-Za-z]{3,9})(?:,?\s*(20\d{2}))?\b', s)
    if m:
        day_raw, mon_raw, year_raw = m.group(1), m.group(2).lower(), m.group(3)
        mon = MONTHS.get(mon_raw)
        if mon:
            day = int(day_raw)
            year = int(year_raw) if year_raw else now.year
            # If no year and date already passed this year, assume next year.
            try:
                dt = datetime(year, mon, day, 9, 0, tzinfo=timezone.utc)
                if not year_raw and dt < now:
                    dt = datetime(year + 1, mon, day, 9, 0, tzinfo=timezone.utc)
                return dt.isoformat()
            except Exception:
                pass

    # Relative dates with specific day: "next month 5th January" or "next month January 5th"
    s_lower = s.lower()
    # Check for "next month" followed by a date
    if "next month" in s_lower:
        # Try to find a specific date after "next month"
        next_month_match = re.search(r'next month\s+(?:(\d{1,2})(?:st|nd|rd|th)?\s+)?([A-Za-z]{3,9})(?:\s+(\d{1,2})(?:st|nd|rd|th)?)?', s_lower)
        if next_month_match:
            # Try to extract day and month
            day_raw = next_month_match.group(1) or next_month_match.group(3)
            mon_raw = next_month_match.group(2)
            
            if day_raw and mon_raw:
                mon = MONTHS.get(mon_raw.lower())
                if mon:
                    day = int(day_raw)
                    # Use the extracted month and day, calculate year
                    # If the date has already passed this year, use next year
                    year = now.year
                    try:
                        dt = datetime(year, mon, day, 9, 0, tzinfo=timezone.utc)
                        # If date already passed this year, use next year
                        if dt < now:
                            dt = datetime(year + 1, mon, day, 9, 0, tzinfo=timezone.utc)
                        return dt.isoformat()
                    except Exception:
                        pass
        # Fallback: just return next month date
        if now.month == 12:
            return datetime(now.year + 1, 1, now.day, 9, 0, tzinfo=timezone.utc).isoformat()
        else:
            return datetime(now.year, now.month + 1, now.day, 9, 0, tzinfo=timezone.utc).isoformat()
    
    if "tomorrow" in s_lower:
        return (now + timedelta(days=1)).isoformat()
    if "next week" in s_lower:
        return (now + timedelta(days=7)).isoformat()

    return None

def classify_memory(role: str, content: str, context: Optional[Dict] = None) -> Dict[str, any]:
    """
    Classify memory by durability and set expiry.
    Returns dict with durability and expires_at.
    """
    now = datetime.now(timezone.utc)
    content_lower = content.lower()

    # Event detection (generic): if we can infer a date and it looks like an event
    event_keywords = ["exam", "midterm", "final", "test", "interview", "meeting", "appointment", "deadline", "call", "session", 
                      "birthday", "party", "celebration", "wedding", "anniversary", "event", "play", "show", "concert", "trip"]
    event_date = _try_parse_event_date(now, content)
    is_eventish = any(k in content_lower for k in event_keywords) and bool(event_date)
    
    # Parent role classifications
    if role == "parent":
        # Check for events first (birthday, party, school events, etc.)
        parent_event_keywords = ["birthday", "party", "celebration", "school event", "parent-teacher", "field trip", "play", "show"]
        parent_event_date = _try_parse_event_date(now, content)
        if any(keyword in content_lower for keyword in parent_event_keywords) and parent_event_date:
            out = {
                "durability": "medium",
                "expires_at": (datetime.fromisoformat(parent_event_date.replace('Z', '+00:00')) + timedelta(days=1)).isoformat() if parent_event_date else (now + timedelta(days=30)).isoformat(),
                "type": "event",
                "event_date": parent_event_date
            }
            return out
        
        if any(keyword in content_lower for keyword in ["fridge", "grocery", "shopping list", "buy"]):
            return {
                "durability": "ephemeral",
                "expires_at": (now + timedelta(days=7)).isoformat()
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
            out = {
                "durability": "medium",
                "expires_at": (now + timedelta(days=expires_days)).isoformat()
            }
            if event_date:
                out["type"] = "event"
                out["event_date"] = event_date
            return out
        
        if any(keyword in content_lower for keyword in ["homework", "assignment", "due"]):
            return {
                "durability": "ephemeral",
                "expires_at": (now + timedelta(days=14)).isoformat()
            }
    
    # Job role classifications
    if role == "job":
        if any(keyword in content_lower for keyword in ["applied to", "application", "interview", "rejected", "offer"]):
            out = {
                "durability": "long",
                "expires_at": None  # No expiry, but will decay over time
            }
            if "interview" in content_lower and event_date:
                out["type"] = "event"
                out["event_date"] = event_date
            return out
        
        if any(keyword in content_lower for keyword in ["networking", "coffee chat", "meeting"]):
            out = {
                "durability": "medium",
                "expires_at": (now + timedelta(days=60)).isoformat()
            }
            if event_date:
                out["type"] = "event"
                out["event_date"] = event_date
            return out
    
    # Default classification
    out = {
        "durability": "medium",
        "expires_at": (now + timedelta(days=90)).isoformat()
    }
    if is_eventish:
        out["type"] = "event"
        out["event_date"] = event_date
    return out

