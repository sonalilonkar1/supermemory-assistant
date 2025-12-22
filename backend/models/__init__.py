"""Models package - database models and profile models"""
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()

class User(db.Model):
    """User model for authentication"""
    __tablename__ = 'users'
    
    id = db.Column(db.String(36), primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    name = db.Column(db.String(100), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    conversations = db.relationship('Conversation', backref='user', lazy=True, cascade='all, delete-orphan')
    
    def to_dict(self):
        """Convert user to dictionary (without password)"""
        return {
            'id': self.id,
            'email': self.email,
            'name': self.name,
            'createdAt': self.created_at.isoformat() if self.created_at else None
        }

class Conversation(db.Model):
    """Conversation model for storing chat sessions"""
    __tablename__ = 'conversations'
    
    id = db.Column(db.String(36), primary_key=True)
    user_id = db.Column(db.String(36), db.ForeignKey('users.id'), nullable=False, index=True)
    mode = db.Column(db.String(50), nullable=False, index=True)  # student, parent, job
    title = db.Column(db.String(200), nullable=True)  # Auto-generated or user-set title
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, index=True)
    
    # Relationships
    messages = db.relationship('Message', backref='conversation', lazy=True, cascade='all, delete-orphan', order_by='Message.created_at')
    
    def to_dict(self):
        """Convert conversation to dictionary"""
        return {
            'id': self.id,
            'userId': self.user_id,
            'mode': self.mode,
            'title': self.title,
            'createdAt': self.created_at.isoformat() if self.created_at else None,
            'updatedAt': self.updated_at.isoformat() if self.updated_at else None,
            'messageCount': len(self.messages) if self.messages else 0
        }

class Message(db.Model):
    """Message model for storing individual chat messages"""
    __tablename__ = 'messages'
    
    id = db.Column(db.String(36), primary_key=True)
    conversation_id = db.Column(db.String(36), db.ForeignKey('conversations.id'), nullable=False, index=True)
    role = db.Column(db.String(20), nullable=False)  # user or assistant
    content = db.Column(db.Text, nullable=False)
    tools_used = db.Column(db.Text, nullable=True)  # JSON string of tools used
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    
    def to_dict(self):
        """Convert message to dictionary"""
        import json
        tools = None
        if self.tools_used:
            try:
                tools = json.loads(self.tools_used)
            except:
                tools = []
        
        return {
            'id': self.id,
            'conversationId': self.conversation_id,
            'role': self.role,
            'content': self.content,
            'toolsUsed': tools,
            'createdAt': self.created_at.isoformat() if self.created_at else None
        }

class Task(db.Model):
    """Task model for mode-specific task management"""
    __tablename__ = 'tasks'
    
    id = db.Column(db.String(36), primary_key=True)
    user_id = db.Column(db.String(36), db.ForeignKey('users.id'), nullable=False, index=True)
    mode = db.Column(db.String(50), nullable=False, index=True)  # student, parent, job
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=True)
    status = db.Column(db.String(20), default='pending', index=True)  # pending, in_progress, completed, cancelled
    priority = db.Column(db.String(20), default='medium')  # low, medium, high
    due_date = db.Column(db.DateTime, nullable=True, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    completed_at = db.Column(db.DateTime, nullable=True)
    
    def to_dict(self):
        """Convert task to dictionary"""
        return {
            'id': self.id,
            'userId': self.user_id,
            'mode': self.mode,
            'title': self.title,
            'description': self.description,
            'status': self.status,
            'priority': self.priority,
            'dueDate': self.due_date.isoformat() if self.due_date else None,
            'createdAt': self.created_at.isoformat() if self.created_at else None,
            'updatedAt': self.updated_at.isoformat() if self.updated_at else None,
            'completedAt': self.completed_at.isoformat() if self.completed_at else None
        }

class UserMode(db.Model):
    """Custom modes (personas) defined by a user"""
    __tablename__ = 'user_modes'

    id = db.Column(db.String(36), primary_key=True)
    user_id = db.Column(db.String(36), db.ForeignKey('users.id'), nullable=False, index=True)
    key = db.Column(db.String(50), nullable=False, index=True)  # mode key used in API (slug)
    name = db.Column(db.String(120), nullable=False)
    emoji = db.Column(db.String(16), nullable=True)
    base_role = db.Column(db.String(50), nullable=True)  # student|parent|job (optional)
    description = db.Column(db.Text, nullable=True)
    # Stored as JSON strings for SQLite compatibility
    default_tags = db.Column(db.Text, nullable=True)        # JSON list[str]
    cross_mode_sources = db.Column(db.Text, nullable=True)  # JSON list[str] (mode keys)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)

    __table_args__ = (
        db.UniqueConstraint('user_id', 'key', name='uq_user_mode_key'),
    )

    def to_dict(self):
        import json
        try:
            default_tags = json.loads(self.default_tags) if self.default_tags else []
        except Exception:
            default_tags = []
        try:
            cross_mode_sources = json.loads(self.cross_mode_sources) if self.cross_mode_sources else []
        except Exception:
            cross_mode_sources = []

        return {
            'id': self.id,
            'userId': self.user_id,
            'key': self.key,
            'name': self.name,
            'emoji': self.emoji,
            'baseRole': self.base_role,
            'description': self.description,
            'defaultTags': default_tags,
            'crossModeSources': cross_mode_sources,
            'createdAt': self.created_at.isoformat() if self.created_at else None,
            'isCustom': True,
        }

# Export profile models
from .profile import UserProfile, ParentProfile, StudentProfile, JobProfile

__all__ = ['db', 'User', 'Conversation', 'Message', 'Task', 'UserMode', 'UserProfile', 'ParentProfile', 'StudentProfile', 'JobProfile']

