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
    patch: Optional[str] = None
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

# Interaction Brand Schemas (for dynamic brand entries)
class InteractionBrandBase(BaseModel):
    brand_name: str
    objective: Optional[str] = None
    insights_marketing: Optional[str] = None
    topics_discussed: Optional[str] = None
    summary: Optional[str] = None
    outcomes: Optional[str] = None
    interest_level: Optional[str] = None

class InteractionBrandCreate(InteractionBrandBase):
    pass

class InteractionBrand(InteractionBrandBase):
    id: int
    interaction_id: int
    created_at: datetime
    
    class Config:
        from_attributes = True

# Doctor Interaction Schemas
class DoctorInteractionBase(BaseModel):
    doctor_name: str
    visit_date: date
    logged_by: Optional[str] = None
    topics_discussed: Optional[str] = None  # Legacy field
    summary: Optional[str] = None  # Legacy field
    outcomes: Optional[str] = None  # Legacy field
    brand_discussed: Optional[str] = None  # Legacy field
    brand2_discussed: Optional[str] = None  # Legacy field
    interest_level: Optional[str] = None  # Legacy field
    brand2_interest_level: Optional[str] = None  # Legacy field
    objections: Optional[str] = None
    insights_for_marketing: Optional[str] = None  # Legacy field
    brand2_topics: Optional[str] = None  # Legacy field
    brand2_summary: Optional[str] = None  # Legacy field
    brand2_outcomes: Optional[str] = None  # Legacy field
    brands: Optional[List[InteractionBrandBase]] = []  # New dynamic brands array

class DoctorInteractionCreate(DoctorInteractionBase):
    request_id: int

class DoctorInteraction(DoctorInteractionBase):
    id: int
    request_id: int
    created_at: datetime
    brands: List[InteractionBrand] = []
    
    class Config:
        from_attributes = True

# Office Activity Schemas
class OfficeActivityBase(BaseModel):
    activity_date: date
    activity_category: str
    summary: Optional[str] = None
    linked_outputs: Optional[str] = None
    work_type: Optional[str] = None
    hours_worked: Optional[float] = None
    doctors_visited: Optional[int] = None

class OfficeActivityCreate(OfficeActivityBase):
    msl_username: str

class OfficeActivity(OfficeActivityBase):
    id: int
    msl_username: str
    created_at: datetime
    
    class Config:
        from_attributes = True

class RequestAssignmentLog(BaseModel):
    id: int
    request_id: int
    assigned_by: str
    previous_msl: Optional[str] = None
    new_msl: Optional[str] = None
    assigned_at: datetime

    class Config:
        from_attributes = True

class RequestAssign(BaseModel):
    assigned_msl: Optional[str] = None
    assigned_by: str

# Request Schemas
class RequestBase(BaseModel):
    doctor_id: int
    territory: Optional[str] = None
    region: Optional[str] = None
    therapy_area: Optional[str] = None
    brand: Optional[str] = None
    objective: Optional[str] = None
    expected_outcome: Optional[str] = None
    priority: Optional[str] = None
    notes: Optional[str] = None
    brand2: Optional[str] = None
    objective2: Optional[str] = None
    expected_outcome2: Optional[str] = None
    priority2: Optional[str] = None
    notes2: Optional[str] = None
    user_classification: Optional[str] = "default"
    assigned_msl: Optional[str] = None
    request_status: Optional[str] = "Pending"
    rx_status_brand1: Optional[str] = None
    rx_status_brand2: Optional[str] = None

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
    assignment_logs: List[RequestAssignmentLog] = []
    
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
    brand: Optional[str] = None
    objective: Optional[str] = None
    expected_outcome: Optional[str] = None
    priority: Optional[str] = None
    notes: Optional[str] = None
    brand2: Optional[str] = None
    objective2: Optional[str] = None
    expected_outcome2: Optional[str] = None
    priority2: Optional[str] = None
    notes2: Optional[str] = None
    user_classification: str
    assigned_msl: Optional[str] = None
    request_status: Optional[str] = "Pending"
    rx_status_brand1: Optional[str] = None
    rx_status_brand2: Optional[str] = None
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
    brands: Optional[List[str]] = None  # List of brand names discussed
    logged_by: Optional[str] = None  # MSL who logged the visit
    
    class Config:
        from_attributes = True

# Monthly Summary Report Schemas
class MonthlySummaryDoctorInteraction(BaseModel):
    id: int
    doctor_name: str
    visit_date: date
    topics_discussed: Optional[str] = None
    summary: Optional[str] = None
    outcomes: Optional[str] = None
    brand_discussed: Optional[str] = None
    interest_level: Optional[str] = None
    brands: List[InteractionBrand] = []  # New dynamic brands
    
    class Config:
        from_attributes = True

class MonthlySummaryOfficeActivity(BaseModel):
    id: int
    activity_date: date
    activity_category: str
    summary: Optional[str] = None
    linked_outputs: Optional[str] = None
    work_type: Optional[str] = None
    hours_worked: Optional[float] = None
    doctors_visited: Optional[int] = None
    
    class Config:
        from_attributes = True

class EmployeeMonthlySummary(BaseModel):
    employee_id: str
    employee_name: str
    month: int
    year: int
    month_name: str
    
    # Doctor Interactions Summary
    total_doctor_visits: int
    unique_doctors_visited: int
    doctor_interactions: List[MonthlySummaryDoctorInteraction]
    
    # Office Activities Summary
    total_office_activities: int
    total_hours_worked: float
    office_activities: List[MonthlySummaryOfficeActivity]
    
    # Work Type Breakdown
    work_type_breakdown: dict  # e.g., {"both done": 5, "worked at office": 3, "call supported": 2}
    
    # Activity Categories Breakdown
    activity_category_breakdown: dict  # e.g., {"Admin": 3, "Training": 2}
    
    # Daily Summary
    daily_summary: List[dict]  # Day-by-day breakdown
    
    class Config:
        from_attributes = True

class MonthlyReportResponse(BaseModel):
    report_month: int
    report_year: int
    report_month_name: str
    generated_at: datetime
    employees: List[EmployeeMonthlySummary]
    
    # Overall Statistics
    total_employees: int
    total_doctor_visits_all: int
    total_office_activities_all: int
    total_hours_worked_all: float
    
    class Config:
        from_attributes = True
