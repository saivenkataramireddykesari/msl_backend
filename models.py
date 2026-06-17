from sqlalchemy import Column, Integer, Float, String, DateTime, Text, Boolean, ForeignKey, Date
from sqlalchemy.orm import relationship
from database import Base
from datetime import datetime

class InteractionBrand(Base):
    """Stores brand-specific details for doctor interactions (dynamic, unlimited brands)"""
    __tablename__ = "interaction_brands"
    
    id = Column(Integer, primary_key=True, index=True)
    interaction_id = Column(Integer, ForeignKey("doctor_interactions.id", ondelete="CASCADE"), nullable=False)
    brand_name = Column(String(255), nullable=False)  # Brand name (e.g., Aztor, Rozucor, or custom)
    objective = Column(Text, nullable=True)  # Objective for this brand
    insights_marketing = Column(Text, nullable=True)  # Insights for marketing for this brand
    topics_discussed = Column(Text, nullable=True)  # Topics discussed for this brand
    summary = Column(Text, nullable=True)  # Summary for this brand
    outcomes = Column(String(255), nullable=True)  # Outcomes for this brand
    interest_level = Column(String(100), nullable=True)  # Interest level for this brand
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationship
    interaction = relationship("DoctorInteraction", back_populates="brands")

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
    brand = Column(String(255), nullable=True)  # Reverted to 'brand'
    objective = Column(Text, nullable=True)     # Reverted to 'objective'
    expected_outcome = Column(Text, nullable=True) # Reverted
    priority = Column(String(50), nullable=True)   # Reverted
    notes = Column(Text, nullable=True)         # Reverted
    brand2 = Column(String(255), nullable=True)  # Keep 'brand2'
    objective2 = Column(Text, nullable=True)     # New field
    expected_outcome2 = Column(Text, nullable=True) # New field
    priority2 = Column(String(50), nullable=True)   # New field
    notes2 = Column(Text, nullable=True)         # New field
    user_classification = Column(String(50), default="default")
    assigned_msl = Column(String(255), nullable=True)
    request_status = Column(String(50), default="Pending", nullable=False)  # Pending, In Progress, Completed
    
    # Per-brand RX status tracking
    rx_status_brand1 = Column(String(50), nullable=True)  # RX status for brand 1 (e.g., Potential, Non-Potential, Default)
    rx_status_brand2 = Column(String(50), nullable=True)  # RX status for brand 2 (null if no brand2)
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
    topics_discussed = Column(Text, nullable=True)  # Legacy: kept for backward compatibility
    summary = Column(Text, nullable=True)  # Legacy: kept for backward compatibility
    outcomes = Column(String(255), nullable=True)  # Legacy: kept for backward compatibility
    brand_discussed = Column(String(255), nullable=True)  # Legacy: kept for backward compatibility
    brand2_discussed = Column(String(255), nullable=True)  # Legacy: kept for backward compatibility
    interest_level = Column(String(100), nullable=True)  # Legacy: kept for backward compatibility
    brand2_interest_level = Column(String(100), nullable=True)  # Legacy: kept for backward compatibility
    objections = Column(Text, nullable=True)
    insights_for_marketing = Column(Text, nullable=True)  # Legacy: kept for backward compatibility
    # Per-brand topics and summaries (Legacy)
    brand2_topics = Column(Text, nullable=True)  # Legacy: kept for backward compatibility
    brand2_summary = Column(Text, nullable=True)  # Legacy: kept for backward compatibility
    brand2_outcomes = Column(String(255), nullable=True)  # Legacy: kept for backward compatibility
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    request = relationship("Request", back_populates="doctor_interactions")
    brands = relationship("InteractionBrand", back_populates="interaction", cascade="all, delete-orphan")

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

# Configuration Models for Dynamic Data
class Brand(Base):
    """Stores available brands for selection"""
    __tablename__ = "brands"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False, unique=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

class Priority(Base):
    """Stores available priority levels"""
    __tablename__ = "priorities"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(50), nullable=False, unique=True)
    display_order = Column(Integer, default=0)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

class UserClassification(Base):
    """Stores available user classifications"""
    __tablename__ = "user_classifications"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(50), nullable=False, unique=True)
    display_name = Column(String(100), nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

class RXStatus(Base):
    """Stores available RX status options"""
    __tablename__ = "rx_statuses"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(50), nullable=False, unique=True)
    display_name = Column(String(100), nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

class InterestLevel(Base):
    """Stores available interest level options"""
    __tablename__ = "interest_levels"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(50), nullable=False, unique=True)
    display_order = Column(Integer, default=0)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

class Outcome(Base):
    """Stores available outcome options for interactions"""
    __tablename__ = "outcomes"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False, unique=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

class ActivityCategory(Base):
    """Stores available activity categories for office activities"""
    __tablename__ = "activity_categories"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False, unique=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

class RequestStatus(Base):
    """Stores available request statuses"""
    __tablename__ = "request_statuses"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(50), nullable=False, unique=True)
    display_name = Column(String(100), nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
