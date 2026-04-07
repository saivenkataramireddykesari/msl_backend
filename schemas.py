from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime, date

# Doctor Schemas
class DoctorBase(BaseModel):
    name: str
    speciality: Optional[str] = None
    therapy_area: Optional[str] = None
    is_priority_doctor: bool = True

    # Excel columns
    division: Optional[str] = None
    territory: Optional[str] = None
    emp_code: Optional[str] = None
    emp_name: Optional[str] = None
    region: Optional[str] = None
    doctor_id_ext: Optional[str] = None
    uid_number: Optional[str] = None
    bm_territory: Optional[str] = None
    bl_territory: Optional[str] = None
    bh_territory: Optional[str] = None
    sbuh_territory: Optional[str] = None

class DoctorCreate(DoctorBase):
    pass

class Doctor(DoctorBase):
    id: int
    
    class Config:
        from_attributes = True

# Doctor Interaction Schemas
class DoctorInteractionBase(BaseModel):
    doctor_name: str
    visit_date: date
    topics_discussed: Optional[str] = None
    scientific_depth: Optional[str] = None
    engagement_quality_interest: Optional[str] = None
    engagement_quality_participation: Optional[str] = None
    engagement_quality_objection: Optional[str] = None
    summary: Optional[str] = None

class DoctorInteractionCreate(DoctorInteractionBase):
    request_id: int

class DoctorInteraction(DoctorInteractionBase):
    id: int
    request_id: int
    created_at: datetime
    
    class Config:
        from_attributes = True

# Office Activity Schemas
class OfficeActivityBase(BaseModel):
    activity_date: date
    activity_category: str
    summary: Optional[str] = None
    linked_outputs: Optional[str] = None

class OfficeActivityCreate(OfficeActivityBase):
    msl_username: str

class OfficeActivity(OfficeActivityBase):
    id: int
    msl_username: str
    created_at: datetime
    
    class Config:
        from_attributes = True

# Request Schemas
class RequestBase(BaseModel):
    doctor_id: int
    territory: Optional[str] = None
    region: Optional[str] = None

    therapy_area: Optional[str] = None
    objective: Optional[str] = None
    expected_outcome: Optional[str] = None
    priority: Optional[str] = None
    notes: Optional[str] = None
    user_classification: Optional[str] = "potential"

class RequestCreate(RequestBase):
    requested_by: str
    requested_by_role: str

class Request(RequestBase):
    id: int
    requested_by: str
    requested_by_role: str
    created_at: datetime
    doctor: Optional[Doctor] = None
    doctor_interactions: List[DoctorInteraction] = []
    
    class Config:
        from_attributes = True

class RequestSummary(BaseModel):
    id: int
    doctor_id: int
    requested_by: str
    requested_by_role: str
    territory: Optional[str] = None
    region: Optional[str] = None

    therapy_area: Optional[str] = None
    objective: Optional[str] = None
    expected_outcome: Optional[str] = None
    priority: Optional[str] = None
    user_classification: str
    created_at: datetime
    doctor_name: Optional[str] = None
    
    class Config:
        from_attributes = True
    
# User Schemas
class UserBase(BaseModel):
    username: str
    employee_id: str
    role: str

class UserCreate(UserBase):
    password: str

class User(UserBase):
    id: int
    created_at: datetime
    
    class Config:
        from_attributes = True

# Login Schemas
class LoginRequest(BaseModel):
    employee_id: str
    password: str

class LoginResponse(BaseModel):
    username: str
    role: str
    employee_id: str
    message: str

# Activity Log Response
class ActivityLog(BaseModel):
    id: int
    type: str  # "doctor_interaction" or "office_activity"
    date: date
    title: str
    details: Optional[str] = None
    created_at: datetime
    
    class Config:
        from_attributes = True