from pydantic import BaseModel
from typing import Optional, Dict, List, Any
from datetime import datetime

class SyllabusBase(BaseModel):
    # 수업기본정보 관련 필드들
    course_name: Optional[str] = None
    course_code: Optional[str] = None
    year_semester: Optional[str] = None
    course_type: Optional[str] = None
    credits: Optional[str] = None
    class_time: Optional[str] = None
    department: Optional[str] = None
    
    # 담당교수정보 관련 필드들
    professor_name: Optional[str] = None
    professor_email: Optional[str] = None
    phone: Optional[str] = None
    office: Optional[str] = None
    office_hours: Optional[str] = None
    homepage: Optional[str] = None
    
    # 강의계획 관련 필드들
    course_overview: Optional[str] = None
    objectives: Optional[str] = None
    learning_outcomes: Optional[str] = None
    textbooks: Optional[str] = None
    equipment: Optional[str] = None
    evaluation_method: Optional[str] = None
    
    # 주별강의계획 (JSON 배열)
    weekly_plans: Optional[List[Dict[str, Any]]] = None

class SyllabusCreate(SyllabusBase):
    course_id: str

class SyllabusUpdate(SyllabusBase):
    pass

class SyllabusInDBBase(SyllabusBase):
    id: int
    course_id: str
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True

class Syllabus(SyllabusInDBBase):
    pass
