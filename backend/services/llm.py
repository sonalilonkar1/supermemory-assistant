"""LLM service for Gemini calls and prompt building"""
import os
import google.genai as genai
from typing import Dict, Any, List
from .memory_orchestrator import format_memories

# Initialize Gemini client
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
if GEMINI_API_KEY:
    client = genai.Client(api_key=GEMINI_API_KEY)
    model_name = 'gemini-2.5-flash'
else:
    client = None
    model_name = None

def build_prompt(role: str, message: str, ctx: Dict[str, Any]) -> str:
    """Build prompt for Gemini with context bundle"""
    
    role_descriptions = {
        "parent": "Parent Planner - Help with family planning, kids' activities, scheduling, and family organization",
        "student": "Student Coach - Help with homework, study planning, deadlines, and academic advice",
        "job": "Job-Hunt Assistant - Help with job applications, interview prep, career advice, and networking"
    }
    
    role_desc = role_descriptions.get(role, "Personal Assistant")
    
    prompt = f"""You are a multi-role personal assistant. Current role: {role_desc}.

Static user profile (high level):
{format_static_profile(ctx.get("static_profile", {}))}

Recent relevant events / messages:
{format_memories(ctx.get("recent_memories", []))}

Long-term memories:
{format_memories(ctx.get("long_term_memories", []))}

User message:
\"\"\"{message}\"\"\"

Respond in a way that uses the profile and memories when helpful, but do NOT restate them unless needed.
If you need more information, ask concise clarifying questions.
Be proactive and helpful. Break long responses into clear sections if needed.
"""
    return prompt

def format_static_profile(profile: Dict[str, Any]) -> str:
    """Format static profile for prompt"""
    if not profile:
        return "No profile information available."
    
    lines = []
    if profile.get('name'):
        lines.append(f"Name: {profile['name']}")
    if profile.get('city'):
        lines.append(f"Location: {profile['city']}")
    
    # Role-specific fields
    if profile.get('kids'):
        lines.append(f"Kids: {', '.join([k.get('name', str(k)) for k in profile['kids']])}")
    if profile.get('schools'):
        lines.append(f"Schools: {', '.join(profile['schools'])}")
    if profile.get('degree'):
        lines.append(f"Degree: {profile['degree']} ({profile.get('year', '')})")
    if profile.get('courses'):
        lines.append(f"Courses: {', '.join(profile['courses'])}")
    if profile.get('target_roles'):
        lines.append(f"Target Roles: {', '.join(profile['target_roles'])}")
    if profile.get('companies_of_interest'):
        lines.append(f"Companies of Interest: {', '.join(profile['companies_of_interest'])}")
    
    return "\n".join(lines) if lines else "No profile information available."

def call_gemini(user_id: str, role: str, message: str, context_bundle: Dict[str, Any]) -> tuple[str, List[Dict]]:
    """
    Call Gemini API with context bundle.
    Returns (reply_text, tool_traces)
    """
    if not client or not model_name:
        raise ValueError("Gemini client not initialized. Please set GEMINI_API_KEY in your .env file.")
    
    prompt = build_prompt(role, message, context_bundle)
    
    try:
        from google.genai import types
        response = client.models.generate_content(
            model=model_name,
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=0.7,
                max_output_tokens=2048,
            )
        )
        
        # Extract text from response
        if hasattr(response, 'text'):
            reply_text = response.text
        elif hasattr(response, 'candidates') and response.candidates:
            candidate = response.candidates[0]
            if hasattr(candidate, 'content') and hasattr(candidate.content, 'parts'):
                reply_text = ''.join([part.text for part in candidate.content.parts if hasattr(part, 'text')])
            else:
                reply_text = str(candidate)
        else:
            reply_text = str(response)
        
        # Check for truncation
        if hasattr(response, 'candidates') and response.candidates:
            finish_reason = getattr(response.candidates[0], 'finish_reason', None)
            if finish_reason and 'MAX_TOKENS' in str(finish_reason):
                reply_text += "\n\n[Note: Response may be truncated due to token limit. Ask me to continue if needed.]"
        
        # Tool traces (for now, just indicate what context was used)
        tool_traces = [
            {"name": "memory.search", "status": "success", "items_found": len(context_bundle.get("long_term_memories", []))},
            {"name": "memory.recent", "status": "success", "items_found": len(context_bundle.get("recent_memories", []))},
            {"name": "profile.slice", "status": "success" if context_bundle.get("static_profile") else "empty"}
        ]
        
        return reply_text, tool_traces
        
    except Exception as e:
        error_str = str(e)
        if 'quota' in error_str.lower() or '429' in error_str:
            raise Exception("Gemini API quota exceeded. Please check your Google Cloud billing.")
        elif 'rate_limit' in error_str.lower():
            raise Exception("Rate limit exceeded. Please wait a moment and try again.")
        else:
            raise Exception(f"Gemini API error: {error_str}")

