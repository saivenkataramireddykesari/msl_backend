from sqlalchemy import Column, Integer, Float, String, DateTime, Text, Boolean, ForeignKey, Date
from sqlalchemy.orm import relationship
from database import Base
from datetime import datetime

class Doctor(Base):
    __tablename__ = "doctors"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)           # Dr_Name
    speciality = Column(String(255), nullable=True)       # Speciality (replaces therapy_area)
    therapy_area = Column(String(255), nullable=True)     # kept for backward compat / grouping
    is_priority_doctor = Column(Boolean, default=True)    # all seeded doctors are priority

    # Fields from Excel
    division = Column(String(255), nullable=True)         # Division
    territory = Column(String(255), nullable=True)        # Territory (MR location)
    emp_code = Column(String(100), nullable=True)         # Emp_Code
    emp_name = Column(String(255), nullable=True)         # Emp_Name (MR name)
    region = Column(String(255), nullable=True)           # Region
    patch = Column(String(255), nullable=True)            # Patch - for cascading dropdown
    doctor_id_ext = Column(String(100), nullable=True)    # Doctor_ID (external)
    uid_number = Column(String(100), nullable=True)       # uid_number
    bm_territory = Column(String(255), nullable=True)     # BM_Territory
    bl_territory = Column(String(255), nullable=True)     # BL_Territory
    bh_territory = Column(String(255), nullable=True)     # BH_Territory
    sbuh_territory = Column(String(255), nullable=True)   # SBUH_Territory

    # Relationship
    requests = relationship("Request", back_populates="doctor")

class Request(Base):
    __tablename__ = "requests"
    
    id = Column(Integer, primary_key=True, index=True)
    doctor_id = Column(Integer, ForeignKey("doctors.id"), nullable=False)
    territory = Column(String(255), nullable=True)
    region = Column(String(255), nullable=True)
    requested_by = Column(String(100), nullable=False)
    requested_by_role = Column(String(50), nullable=False)
    therapy_area = Column(String(255), nullable=True)
    objective = Column(Text, nullable=True)
    expected_outcome = Column(Text, nullable=True)
    priority = Column(String(50), nullable=True)
    notes = Column(Text, nullable=True)
    brand = Column(String(255), nullable=True)
    user_classification = Column(String(50), default="default")
    assigned_msl = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    doctor = relationship("Doctor", back_populates="requests")
    doctor_interactions = relationship("DoctorInteraction", back_populates="request", cascade="all, delete-orphan")
    assignment_logs = relationship("RequestAssignmentLog", back_populates="request", cascade="all, delete-orphan")

class DoctorInteraction(Base):
    __tablename__ = "doctor_interactions"
    
    id = Column(Integer, primary_key=True, index=True)
    request_id = Column(Integer, ForeignKey("requests.id"), nullable=False)
    logged_by = Column(String(255), nullable=True)  # MSL username who logged this visit
    doctor_name = Column(String(255), nullable=False)
    visit_date = Column(Date, nullable=False)
    topics_discussed = Column(Text, nullable=True)
    summary = Column(Text, nullable=True)
    outcomes = Column(String(255), nullable=True)
    brand_discussed = Column(String(255), nullable=True)
    interest_level = Column(String(100), nullable=True)
    objections = Column(Text, nullable=True)
    insights_for_marketing = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationship
    request = relationship("Request", back_populates="doctor_interactions")

class OfficeActivity(Base):
    __tablename__ = "office_activities"
    
    id = Column(Integer, primary_key=True, index=True)
    msl_username = Column(String(255), nullable=False)
    activity_date = Column(Date, nullable=False)
    activity_category = Column(String(100), nullable=False)
    summary = Column(Text, nullable=True)
    linked_outputs = Column(Text, nullable=True)
    work_type = Column(String(100), nullable=True)  # 'worked at office', 'call supported', 'both done', 'nothing done'
    hours_worked = Column(Float, nullable=True)
    doctors_visited = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

class RequestAssignmentLog(Base):
    __tablename__ = "request_assignment_logs"
    
    id = Column(Integer, primary_key=True, index=True)
    request_id = Column(Integer, ForeignKey("requests.id", ondelete="CASCADE"), nullable=False)
    assigned_by = Column(String(255), nullable=False)
    previous_msl = Column(String(255), nullable=True)
    new_msl = Column(String(255), nullable=True)
    assigned_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationship
    request = relationship("Request", back_populates="assignment_logs")

class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(255), nullable=False)
    password = Column(String(255), nullable=False)
    employee_id = Column(String(50), unique=True, nullable=False)
    role = Column(String(100), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)