from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime

class AttachmentBase(BaseModel):
    course_id: str
    related_type: str  # e.g., 'notices', 'materials', 'assignments'
    related_id: int
    original_filename: str
    stored_filename: str
    file_size: Optional[int] = None
    file_type: Optional[str] = None
    download_url: Optional[str] = None
    storage_path: Optional[str] = None
    file_name: Optional[str] = None
    original_url: Optional[str] = None
    source_id: Optional[str] = None
    source_type: Optional[str] = None

class AttachmentCreate(AttachmentBase):
    pass

class AttachmentUpdate(BaseModel):
    course_id: Optional[str] = None
    related_type: Optional[str] = None
    related_id: Optional[int] = None
    original_filename: Optional[str] = None
    stored_filename: Optional[str] = None
    file_size: Optional[int] = None
    file_type: Optional[str] = None
    download_url: Optional[str] = None
    storage_path: Optional[str] = None
    file_name: Optional[str] = None
    original_url: Optional[str] = None
    source_id: Optional[str] = None
    source_type: Optional[str] = None

class AttachmentInDBBase(AttachmentBase):
    id: int
    created_at: datetime
    updated_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True

class Attachment(AttachmentInDBBase):
    file_url: Optional[str] = None  # For compatibility - computed from download_url or storage_path

class AttachmentList(BaseModel):
    attachments: List[Attachment]
    total: int
