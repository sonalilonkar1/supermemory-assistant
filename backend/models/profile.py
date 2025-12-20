"""User profile models for multi-role assistant"""
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Optional

@dataclass
class ParentProfile:
    """Parent role profile data"""
    kids: List[Dict] = field(default_factory=list)
    schools: List[str] = field(default_factory=list)
    recurring_events: List[str] = field(default_factory=list)
    
    def to_dict(self):
        return asdict(self)

@dataclass
class StudentProfile:
    """Student role profile data"""
    degree: str = ""
    year: str = ""
    courses: List[str] = field(default_factory=list)
    upcoming_exams: List[Dict] = field(default_factory=list)
    
    def to_dict(self):
        return asdict(self)

@dataclass
class JobProfile:
    """Job seeker role profile data"""
    target_roles: List[str] = field(default_factory=list)
    target_locations: List[str] = field(default_factory=list)
    salary_band: str = ""
    companies_of_interest: List[str] = field(default_factory=list)
    
    def to_dict(self):
        return asdict(self)

@dataclass
class UserProfile:
    """Complete user profile with all roles"""
    user_id: str
    name: str
    city: str = ""
    parent: ParentProfile = field(default_factory=ParentProfile)
    student: StudentProfile = field(default_factory=StudentProfile)
    job: JobProfile = field(default_factory=JobProfile)
    
    def to_dict(self):
        return {
            'user_id': self.user_id,
            'name': self.name,
            'city': self.city,
            'parent': self.parent.to_dict(),
            'student': self.student.to_dict(),
            'job': self.job.to_dict()
        }
    
    @classmethod
    def from_dict(cls, data: dict):
        """Create UserProfile from dictionary"""
        parent = ParentProfile(**data.get('parent', {}))
        student = StudentProfile(**data.get('student', {}))
        job = JobProfile(**data.get('job', {}))
        
        return cls(
            user_id=data.get('user_id', ''),
            name=data.get('name', ''),
            city=data.get('city', ''),
            parent=parent,
            student=student,
            job=job
        )

