import jwt
import uuid
from datetime import datetime, timedelta
from flask_bcrypt import Bcrypt
import os

# Bcrypt instance will be initialized in app.py
bcrypt = None

def init_bcrypt(app):
    """Initialize bcrypt with Flask app"""
    global bcrypt
    bcrypt = Bcrypt(app)
    return bcrypt

JWT_SECRET = os.getenv('JWT_SECRET', 'your-secret-key-change-in-production')
JWT_EXPIRATION_HOURS = 24 * 7  # 7 days

def generate_user_id():
    """Generate a unique user ID"""
    return str(uuid.uuid4())

def hash_password(password):
    """Hash a password"""
    return bcrypt.generate_password_hash(password).decode('utf-8')

def verify_password(password_hash, password):
    """Verify a password against its hash"""
    return bcrypt.check_password_hash(password_hash, password)

def generate_token(user_id):
    """Generate JWT token for user"""
    payload = {
        'user_id': user_id,
        'exp': datetime.utcnow() + timedelta(hours=JWT_EXPIRATION_HOURS),
        'iat': datetime.utcnow()
    }
    return jwt.encode(payload, JWT_SECRET, algorithm='HS256')

def verify_token(token):
    """Verify and decode JWT token"""
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=['HS256'])
        return payload.get('user_id')
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None

def get_user_from_token(request):
    """Extract user from Authorization header"""
    from models import User
    
    auth_header = request.headers.get('Authorization')
    if not auth_header:
        return None
    
    try:
        token = auth_header.split(' ')[1]  # Bearer <token>
        user_id = verify_token(token)
        if user_id:
            return User.query.get(user_id)
        return None
    except (IndexError, AttributeError):
        return None

