from fastapi import FastAPI, Depends, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from sqlalchemy import extract, func
from typing import List, Optional
from datetime import date, datetime
from calendar import month_name
import os
import models, schemas, database
from database import get_db, engine

# Create tables
models.Base.metadata.create_all(bind=engine)

app = FastAPI(title="MSL Engagement Management System")

# CORS middleware — allow all origins for dev compatibility
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)



@app.post("/api/login", response_model=schemas.LoginResponse)
def login(login_data: schemas.LoginRequest, db: Session = Depends(get_db)):
    """Login using employee_id and password"""
    # Find user by employee_id
    user = db.query(models.User).filter(models.User.employee_id == login_data.employee_id).first()
    
    if not user:
        raise HTTPException(status_code=401, detail="Invalid employee ID or password")
    
    # Simple password check (no hashing as requested)
    if user.password != login_data.password:
        raise HTTPException(status_code=401, detail="Invalid employee ID or password")
    
    return {
        "username": user.username,
        "role": user.role,
        "employee_id": user.employee_id,
        "message": "Login successful"
    }

@app.get("/api/users", response_model=List[schemas.User])
def get_users(db: Session = Depends(get_db)):
    """Get all users"""
    users = db.query(models.User).all()
    return users

@app.get("/api/users/msls")
def get_msl_users(db: Session = Depends(get_db)):
    """Get only MSL and Scientific Officer users for assignment dropdown"""
    msl_roles = ["MSL", "Scientific Officer"]
    users = db.query(models.User).filter(models.User.role.in_(msl_roles)).all()
    return [
        {
            "id": u.id,
            "username": u.username,
            "employee_id": u.employee_id,
            "role": u.role,
        }
        for u in users
    ]

# ==================== DOCTORS ====================

@app.get("/api/doctors", response_model=List[schemas.Doctor])
def get_doctors(
    priority_only: bool = Query(False, description="Filter priority doctors only"),
    db: Session = Depends(get_db)
):
    """Get all doctors, optionally filtered by priority"""
    query = db.query(models.Doctor)
    if priority_only:
        query = query.filter(models.Doctor.is_priority_doctor == True)
    doctors = query.order_by(
        models.Doctor.is_priority_doctor.desc(),
        models.Doctor.name
    ).all()
    return doctors

@app.post("/api/doctors", response_model=schemas.Doctor)
def create_doctor(doctor: schemas.DoctorCreate, db: Session = Depends(get_db)):
    """Create a new doctor"""
    db_doctor = models.Doctor(**doctor.model_dump())
    db.add(db_doctor)
    db.commit()
    db.refresh(db_doctor)
    return db_doctor

# ==================== CASCADING DROPDOWNS FOR BL ====================
# NOTE: These routes MUST be defined BEFORE the /api/doctors/{doctor_id} route
# because FastAPI matches routes in order and {doctor_id} would catch "regions", etc.


@app.get("/api/doctors/regions")
def get_regions_by_bl_location(
    bl_territory: Optional[str] = Query(None, description="Filter by BL territory"),
    db: Session = Depends(get_db)
):
    """Get unique regions based on BL location (bl_territory)"""
    query = db.query(models.Doctor.region).distinct()
    
    if bl_territory:
        query = query.filter(models.Doctor.bl_territory == bl_territory)
    
    regions = [r[0] for r in query.all() if r[0]]
    return sorted(regions)

@app.get("/api/doctors/territories")
def get_territories_by_region(
    region: str = Query(..., description="Region to filter by"),
    bl_territory: Optional[str] = Query(None, description="Optional BL territory filter"),
    db: Session = Depends(get_db)
):
    """Get unique territories based on selected region and optional BL location"""
    query = db.query(models.Doctor.territory).filter(
        models.Doctor.region == region
    ).distinct()
    
    if bl_territory:
        query = query.filter(models.Doctor.bl_territory == bl_territory)
    
    territories = [t[0] for t in query.all() if t[0]]
    return sorted(territories)

@app.get("/api/doctors/patches")
def get_patches_by_territory(
    territory: str = Query(..., description="Territory to filter by"),
    region: Optional[str] = Query(None, description="Optional region filter"),
    bl_territory: Optional[str] = Query(None, description="Optional BL territory filter"),
    db: Session = Depends(get_db)
):
    """Get unique patches based on selected territory, region and optional BL location"""
    query = db.query(models.Doctor.patch).filter(
        models.Doctor.territory == territory
    ).distinct()
    
    if region:
        query = query.filter(models.Doctor.region == region)
    
    if bl_territory:
        query = query.filter(models.Doctor.bl_territory == bl_territory)
    
    patches = [p[0] for p in query.all() if p[0]]
    return sorted(patches)

@app.get("/api/doctors/by-location")
def get_doctors_by_location(
    region: Optional[str] = Query(None, description="Filter by region"),
    territory: Optional[str] = Query(None, description="Filter by territory"),
    patch: Optional[str] = Query(None, description="Filter by patch"),
    bl_territory: Optional[str] = Query(None, description="Filter by BL territory"),
    db: Session = Depends(get_db)
):
    """Get doctors filtered by region, territory, patch and optional BL location"""
    query = db.query(models.Doctor)
    
    if region:
        query = query.filter(models.Doctor.region == region)
    
    if territory:
        query = query.filter(models.Doctor.territory == territory)
    
    if patch:
        query = query.filter(models.Doctor.patch == patch)
    
    if bl_territory:
        query = query.filter(models.Doctor.bl_territory == bl_territory)
    
    doctors = query.order_by(models.Doctor.name).all()
    return doctors

# ==================== DOCTOR SPECIFIC ROUTES ====================
# These MUST come after the cascading routes above

@app.get("/api/doctors/{doctor_id}", response_model=schemas.Doctor)
def get_doctor(doctor_id: int, db: Session = Depends(get_db)):
    """Get a specific doctor by ID"""
    doctor = db.query(models.Doctor).filter(models.Doctor.id == doctor_id).first()
    if not doctor:
        raise HTTPException(status_code=404, detail="Doctor not found")
    return doctor

@app.post("/api/doctors/{doctor_id}/duplicate", response_model=schemas.Doctor)
def duplicate_doctor(doctor_id: int, db: Session = Depends(get_db)):
    """Duplicate a doctor"""
    doctor = db.query(models.Doctor).filter(models.Doctor.id == doctor_id).first()
    if not doctor:
        raise HTTPException(status_code=404, detail="Doctor not found")
    
    # Create a duplicate with "(Copy)" suffix
    new_doctor = models.Doctor(
        name=f"{doctor.name} (Copy)",
        speciality=doctor.speciality,
        therapy_area=doctor.therapy_area,
        is_priority_doctor=doctor.is_priority_doctor,
        division=doctor.division,
        territory=doctor.territory,
        emp_code=doctor.emp_code,
        emp_name=doctor.emp_name,
        region=doctor.region,
        patch=doctor.patch,
        doctor_id_ext=doctor.doctor_id_ext,
        uid_number=doctor.uid_number,
        bm_territory=doctor.bm_territory,
        bl_territory=doctor.bl_territory,
        bh_territory=doctor.bh_territory,
        sbuh_territory=doctor.sbuh_territory,
    )
    db.add(new_doctor)
    db.commit()
    db.refresh(new_doctor)
    return new_doctor

@app.delete("/api/doctors/{doctor_id}")
def delete_doctor(doctor_id: int, db: Session = Depends(get_db)):
    """Delete a doctor"""
    doctor = db.query(models.Doctor).filter(models.Doctor.id == doctor_id).first()
    if not doctor:
        raise HTTPException(status_code=404, detail="Doctor not found")
    
    db.delete(doctor)
    db.commit()
    return {"message": "Doctor deleted successfully"}

@app.get("/api/doctor-interactions", response_model=List[schemas.DoctorInteraction])
def get_doctor_history(
    doctor_name: str = Query(...),
    db: Session = Depends(get_db)
):
    """Get interaction history by doctor name"""
    interactions = db.query(models.DoctorInteraction).filter(
        models.DoctorInteraction.doctor_name == doctor_name
    ).order_by(models.DoctorInteraction.visit_date.desc()).all()

    return interactions

# ==================== REQUESTS ====================

@app.post("/api/requests", response_model=schemas.Request)
def create_request(request: schemas.RequestCreate, db: Session = Depends(get_db)):
    """Create a new MSL engagement request"""
    # Debug: Log incoming request data
    request_data = request.model_dump()
    print(f"DEBUG - Received request data: {request_data}")
    print(f"DEBUG - Territory from request: \'{request.territory}\'")
    print(f"DEBUG - Region from request: \'{request.region}\'")
    print(f"DEBUG - Doctor ID: {request.doctor_id}")
    
    # Verify doctor exists
    doctor = db.query(models.Doctor).filter(models.Doctor.id == request.doctor_id).first()
    if not doctor:
        print(f"DEBUG - Doctor not found for ID: {request.doctor_id}")
        raise HTTPException(status_code=404, detail="Doctor not found")
    
    print(f"DEBUG - Doctor found: {doctor.name}")
    
    try:
        # Create request with explicit field assignment
        db_request = models.Request(
            doctor_id=request.doctor_id,
            territory=request.territory,
            region=request.region,
            requested_by=request.requested_by,
            requested_by_role=request.requested_by_role,
            therapy_area=request.therapy_area,
            brand=request.brand,             # Reverted
            objective=request.objective,     # Reverted
            expected_outcome=request.expected_outcome, # Reverted
            priority=request.priority,       # Reverted
            notes=request.notes,             # Reverted
            brand2=request.brand2,
            objective2=request.objective2,
            expected_outcome2=request.expected_outcome2,
            priority2=request.priority2,
            notes2=request.notes2,
            request_status="Pending"
        )
        
        print(f"DEBUG - Request object created with territory=\'{db_request.territory}\'", "region=\'{db_request.region}\'")
        
        db.add(db_request)
        db.commit()
        db.refresh(db_request)
        
        print(f"DEBUG - After commit: ID={db_request.id}, territory=\'{db_request.territory}\'", "region=\'{db_request.region}\'")
        
        return db_request
    except Exception as e:
        print(f"DEBUG - Error creating request: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/requests")
def get_requests(
    search: Optional[str] = None,
    territory: Optional[str] = None,
    region: Optional[str] = None,
    therapy: Optional[str] = None,
    requested_by: Optional[str] = None,
    role: Optional[str] = None,
    username: Optional[str] = None,
    db: Session = Depends(get_db)
):
    # Subquery: count doctor interactions per request
    interaction_count_subq = db.query(
        models.DoctorInteraction.request_id,
        func.count(models.DoctorInteraction.id).label("visit_count")
    ).group_by(models.DoctorInteraction.request_id).subquery()

    # Query requests with doctor name, division, and visit count
    query = db.query(
        models.Request,
        models.Doctor.name.label("doctor_name"),
        models.Doctor.division.label("division"),
        interaction_count_subq.c.visit_count
    ).join(
        models.Doctor, models.Request.doctor_id == models.Doctor.id
    ).outerjoin(
        interaction_count_subq, models.Request.id == interaction_count_subq.c.request_id
    )

    # Filter based on role and username
    if role in ["MSL", "Scientific Officer"]:
        if username:
            query = query.filter(models.Request.assigned_msl == username)
    elif role in ["BL", "BM"]:
        if username:
            query = query.filter(models.Request.requested_by == username)

    if search:
        query = query.filter(models.Doctor.name.ilike(f"%{search}%"))

    if territory:
        query = query.filter(models.Request.territory == territory)

    if region:
        query = query.filter(models.Request.region == region)

    if therapy:
        query = query.filter(models.Request.therapy_area == therapy)

    if requested_by:
        query = query.filter(models.Request.requested_by == requested_by)

    results = query.order_by(models.Request.created_at.desc()).all()

    # Build response manually to ensure all fields are included
    response_data = []
    for request, doctor_name, division, visit_count in results:
        response_data.append({
            "id": request.id,
            "doctor_id": request.doctor_id,
            "doctor_name": doctor_name,
            "territory": request.territory,
            "region": request.region,
            "therapy_area": request.therapy_area,
            "brand": request.brand,
            "objective": request.objective,
            "expected_outcome": request.expected_outcome,
            "priority": request.priority,
            "notes": request.notes,
            "brand2": request.brand2,
            "objective2": request.objective2,
            "expected_outcome2": request.expected_outcome2,
            "priority2": request.priority2,
            "notes2": request.notes2,
            "user_classification": request.user_classification,
            "requested_by": request.requested_by,
            "requested_by_role": request.requested_by_role,
            "assigned_msl": request.assigned_msl,
            "request_status": request.request_status or "Pending",
            "rx_status_brand1": request.rx_status_brand1,
            "rx_status_brand2": request.rx_status_brand2,
            "num_visits": visit_count or 0,
            "created_at": request.created_at.isoformat() if request.created_at else None
        })
    
    return response_data

@app.get("/api/requests/{request_id}", response_model=schemas.Request)
def get_request(
    request_id: int,
    role: Optional[str] = None,
    username: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """Get a specific request with all details"""
    request = db.query(models.Request).filter(models.Request.id == request_id).first()
    if not request:
        raise HTTPException(status_code=404, detail="Request not found")
        
    # Enforce that MSLs can only view requests assigned to them
    if role in ["MSL", "Scientific Officer"]:
        if request.assigned_msl != username:
            raise HTTPException(status_code=403, detail="Access denied. You are not assigned to this request.")
            
    return request

@app.put("/api/requests/{request_id}/assign")
def assign_request(
    request_id: int,
    assign_data: schemas.RequestAssign,
    db: Session = Depends(get_db)
):
    """Assign/Reassign a request to an MSL and log the assignment history"""
    request = db.query(models.Request).filter(models.Request.id == request_id).first()
    if not request:
        raise HTTPException(status_code=404, detail="Request not found")
    
    previous_msl = request.assigned_msl
    new_msl = assign_data.assigned_msl
    
    # Only log and update if there\\'s an actual change
    if previous_msl != new_msl:
        request.assigned_msl = new_msl
        
        # Auto-update request_status and brand statuses based on assignment
        if new_msl:
            request.request_status = "In Progress"
            request.brand1_status = "In Progress"
            if request.brand2:
                request.brand2_status = "In Progress"
        else:
            request.request_status = "Pending"
            request.brand1_status = "Pending"
            if request.brand2:
                request.brand2_status = "Pending"
        
        # Create history log entry
        log_entry = models.RequestAssignmentLog(
            request_id=request_id,
            assigned_by=assign_data.assigned_by,
            previous_msl=previous_msl,
            new_msl=new_msl
        )
        db.add(log_entry)
        db.commit()
        db.refresh(request)
        
    return {
        "message": "Request assigned successfully",
        "assigned_msl": request.assigned_msl
    }

@app.put("/api/requests/{request_id}/user-classification")
def update_request_user_classification(
    request_id: int,
    user_classification: str = Query(..., description="User classification: potential, non-potential, or default"),
    db: Session = Depends(get_db)
):
    """Update request user classification (potential, non-potential, or default) and sync to doctor profile"""
    valid_classifications = ["potential", "non-potential", "default"]
    if user_classification not in valid_classifications:
        raise HTTPException(status_code=400, detail="Invalid user classification. Must be \\'potential\\', \\'non-potential\\', or \\'default\\'")
    
    request = db.query(models.Request).filter(models.Request.id == request_id).first()
    if not request:
        raise HTTPException(status_code=404, detail="Request not found")
    
    # Update request classification
    request.user_classification = user_classification
    
    # Sync to doctor profile - update the doctor\\'s priority status based on classification
    doctor = db.query(models.Doctor).filter(models.Doctor.id == request.doctor_id).first()
    if doctor:
        if user_classification == "potential":
            doctor.is_priority_doctor = True
        elif user_classification == "non-potential":
            doctor.is_priority_doctor = False
        # For "default", keep the doctor\\'s current priority status
    
    db.commit()
    return {
        "message": "User classification updated successfully",
        "user_classification": user_classification,
        "doctor_updated": doctor is not None
    }

@app.put("/api/requests/{request_id}/rx-status")
def update_rx_status(
    request_id: int,
    rx_status_brand1: Optional[str] = Query(None, description="RX status for brand 1: potential, non-potential, default"),
    rx_status_brand2: Optional[str] = Query(None, description="RX status for brand 2: potential, non-potential, default"),
    db: Session = Depends(get_db)
):
    """Update per-brand RX status for a request"""
    valid_statuses = ["potential", "non-potential", "default"]
    
    request = db.query(models.Request).filter(models.Request.id == request_id).first()
    if not request:
        raise HTTPException(status_code=404, detail="Request not found")
    
    if rx_status_brand1 is not None:
        if rx_status_brand1 not in valid_statuses:
            raise HTTPException(status_code=400, detail=f"Invalid rx_status_brand1. Must be one of: {valid_statuses}")
        request.rx_status_brand1 = rx_status_brand1
    
    if rx_status_brand2 is not None:
        if rx_status_brand2 not in valid_statuses:
            raise HTTPException(status_code=400, detail=f"Invalid rx_status_brand2. Must be one of: {valid_statuses}")
        request.rx_status_brand2 = rx_status_brand2
    
    db.commit()
    return {
        "message": "RX status updated successfully",
        "rx_status_brand1": request.rx_status_brand1,
        "rx_status_brand2": request.rx_status_brand2
    }

# ==================== DOCTOR INTERACTIONS ====================

@app.post("/api/doctor-interactions", response_model=schemas.DoctorInteraction)
def create_doctor_interaction(
    interaction: schemas.DoctorInteractionCreate,
    db: Session = Depends(get_db)
):
    """Log a doctor interaction with dynamic brand details"""
    # Verify request exists
    request = db.query(models.Request).filter(models.Request.id == interaction.request_id).first()
    if not request:
        raise HTTPException(status_code=404, detail="Request not found")
    
    # Extract brands data if provided
    brands_data = interaction.brands if hasattr(interaction, 'brands') and interaction.brands else []
    
    # Create the interaction without the brands field
    interaction_dict = interaction.model_dump(exclude={'brands'})
    db_interaction = models.DoctorInteraction(**interaction_dict)
    db.add(db_interaction)
    db.commit()
    db.refresh(db_interaction)
    
    # Create brand entries if provided
    if brands_data:
        for brand_data in brands_data:
            db_brand = models.InteractionBrand(
                interaction_id=db_interaction.id,
                brand_name=brand_data.brand_name,
                objective=brand_data.objective,
                insights_marketing=brand_data.insights_marketing,
                topics_discussed=brand_data.topics_discussed,
                summary=brand_data.summary,
                outcomes=brand_data.outcomes,
                interest_level=brand_data.interest_level
            )
            db.add(db_brand)
        db.commit()
    
    db.refresh(db_interaction)
    return db_interaction

@app.get("/api/requests/{request_id}/interactions", response_model=List[schemas.DoctorInteraction])
def get_doctor_interactions(request_id: int, db: Session = Depends(get_db)):
    """Get all doctor interactions for a request"""
    interactions = db.query(models.DoctorInteraction).filter(
        models.DoctorInteraction.request_id == request_id
    ).order_by(models.DoctorInteraction.visit_date.desc()).all()
    return interactions

@app.get("/api/doctor-interactions/by-doctor", response_model=List[schemas.DoctorInteraction])
def get_interactions_by_doctor(doctor_name: str, db: Session = Depends(get_db)):
    """Get all interactions for a doctor by name across all MSLs/requests"""
    interactions = db.query(models.DoctorInteraction).filter(
        models.DoctorInteraction.doctor_name == doctor_name
    ).order_by(models.DoctorInteraction.visit_date.desc()).all()
    return interactions

@app.get("/api/doctor-interactions/by-date-user", response_model=List[schemas.DoctorInteraction])
def get_interactions_by_date_user(
    visit_date: date,
    logged_by: str,
    db: Session = Depends(get_db)
):
    """Get all doctor interactions logged by a specific user on a specific date"""
    interactions = db.query(models.DoctorInteraction).filter(
        models.DoctorInteraction.logged_by == logged_by,
        models.DoctorInteraction.visit_date == visit_date
    ).order_by(models.DoctorInteraction.created_at.desc()).all()
    return interactions

# ==================== OFFICE ACTIVITIES ====================

@app.post("/api/office-activities", response_model=schemas.OfficeActivity)
def create_office_activity(
    activity: schemas.OfficeActivityCreate,
    db: Session = Depends(get_db)
):
    """Log an office activity with auto-calculated doctor visits based on date"""
    try:
        print(f"DEBUG - Received activity data: {activity.model_dump()}")
        activity_dict = activity.model_dump()
        hours = activity_dict.get("hours_worked") or 0.0
        activity_date = activity_dict.get("activity_date")
        
        # Auto-calculate doctor visits: count doctor interactions on the activity date
        # for the same MSL user
        msl_username = activity_dict.get("msl_username")
        auto_doctors_visited = 0
        
        if activity_date and msl_username:
            # Count doctor interactions where logged_by matches msl_username and visit_date matches activity_date
            auto_doctors_visited = db.query(models.DoctorInteraction).filter(
                models.DoctorInteraction.logged_by == msl_username,
                models.DoctorInteraction.visit_date == activity_date
            ).count()
            print(f"DEBUG - Found {auto_doctors_visited} doctor visits for {msl_username} on {activity_date}")
        
        # Store the auto-calculated value
        activity_dict["doctors_visited"] = auto_doctors_visited
        
        # Calculate work_type based on updated rules:
        # hours > 0 -> office; doctors > 0 -> field; both -> both done
        if hours > 0.0 and auto_doctors_visited > 0:
            calculated_work_type = "both done"
        elif hours > 0.0:
            calculated_work_type = "worked at office"
        elif auto_doctors_visited > 0:
            calculated_work_type = "call supported"
        else:
            calculated_work_type = "nothing done"
            
        activity_dict["work_type"] = calculated_work_type
        print(f"DEBUG - Calculated work_type: {calculated_work_type}, doctors_visited: {auto_doctors_visited}")
        
        db_activity = models.OfficeActivity(**activity_dict)
        db.add(db_activity)
        db.commit()
        db.refresh(db_activity)
        print(f"DEBUG - Activity saved successfully with ID: {db_activity.id}")
        return db_activity
    except Exception as e:
        print(f"ERROR - Failed to save activity: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Failed to save activity: {str(e)}")

@app.get("/api/office-activities", response_model=List[schemas.OfficeActivity])
def get_office_activities(msl_username: Optional[str] = None, db: Session = Depends(get_db)):
    """Get all office activities, dynamically updating doctors_visited and work_type based on current doctor interactions"""
    try:
        print(f"DEBUG - Fetching activities for msl_username: {msl_username}")
        query = db.query(models.OfficeActivity)
        if msl_username:
            query = query.filter(models.OfficeActivity.msl_username == msl_username)
        activities = query.order_by(models.OfficeActivity.activity_date.desc()).all()
        print(f"DEBUG - Found {len(activities)} activities")
        
        # Dynamically sync/count matching doctor visits and update the local object properties before serialization
        for a in activities:
            doc_count = db.query(models.DoctorInteraction).filter(
                models.DoctorInteraction.logged_by == a.msl_username,
                models.DoctorInteraction.visit_date == a.activity_date
            ).count()
            a.doctors_visited = doc_count
            
            hours = a.hours_worked or 0.0
            if hours > 0.0 and doc_count > 0:
                a.work_type = "both done"
            elif hours > 0.0:
                a.work_type = "worked at office"
            elif doc_count > 0:
                a.work_type = "call supported"
            else:
                a.work_type = "nothing done"
                
            print(f"  - ID: {a.id}, Date: {a.activity_date}, User: {a.msl_username}, Hours: {a.hours_worked}, Auto-counted Doctors: {a.doctors_visited}, Calculated Work Type: {a.work_type}")
            
        return activities
    except Exception as e:
        print(f"ERROR - Failed to fetch activities: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Failed to fetch activities: {str(e)}")

@app.get("/api/office-activities/users", response_model=List[str])
def get_office_activity_users(db: Session = Depends(get_db)):
    """Get unique list of MSL usernames who have logged activities"""
    users = db.query(models.OfficeActivity.msl_username).distinct().all()
    # Filter out None values and return flat list
    return [u[0] for u in users if u[0]]

# ==================== SUMMARY VIEW ====================

@app.get("/api/requests/{request_id}/logs", response_model=List[schemas.ActivityLog])
def get_request_logs(request_id: int, db: Session = Depends(get_db)):
    """Get all activity logs (interactions + office activities) for a request, sorted by date"""
    # Verify request exists
    request = db.query(models.Request).filter(models.Request.id == request_id).first()
    if not request:
        raise HTTPException(status_code=404, detail="Request not found")
    
    logs = []
    
    # Get doctor interactions with their brands
    interactions = db.query(models.DoctorInteraction).filter(
        models.DoctorInteraction.request_id == request_id
    ).all()
    
    for interaction in interactions:
        # Get brand names from the new brands relationship
        brand_names = []
        if interaction.brands:
            brand_names = [b.brand_name for b in interaction.brands if b.brand_name]
        # Fallback to legacy fields if no brands array
        if not brand_names:
            if interaction.brand_discussed:
                brand_names.append(interaction.brand_discussed)
            if interaction.brand2_discussed:
                brand_names.append(interaction.brand2_discussed)
        
        logs.append(schemas.ActivityLog(
            id=interaction.id,
            type="doctor_interaction",
            date=interaction.visit_date,
            title=f"Visit by {interaction.logged_by or 'Unknown'}",
            details=interaction.summary,
            created_at=interaction.created_at,
            brands=brand_names if brand_names else None,
            logged_by=interaction.logged_by
        ))
    
    # Sort by date (latest first)
    logs.sort(key=lambda x: x.date, reverse=True)
    
    return logs

# ==================== MONTHLY EMPLOYEE SUMMARY REPORT ====================

@app.get("/api/reports/monthly-summary", response_model=schemas.MonthlyReportResponse)
def get_monthly_employee_summary(
    month: int = Query(..., ge=1, le=12, description="Month (1-12)"),
    year: int = Query(..., ge=2000, le=2100, description="Year (e.g., 2024)"),
    employee_ids: Optional[str] = Query(None, description="Comma-separated employee IDs (e.g., \'E9250,E5057\')"),
    db: Session = Depends(get_db)
):
    """
    Get monthly working summary report for specified employees.
    If employee_ids is not provided, returns report for all employees.
    """
    try:
        # Parse employee IDs if provided
        target_employee_ids = []
        if employee_ids:
            target_employee_ids = [eid.strip() for eid in employee_ids.split(",")]
        
        # Get all users or filter by specific employee IDs
        users_query = db.query(models.User)
        if target_employee_ids:
            users_query = users_query.filter(models.User.employee_id.in_(target_employee_ids))
        
        users = users_query.all()
        
        if not users:
            raise HTTPException(status_code=404, detail="No employees found with the specified IDs")
        
        # Prepare month name
        month_name_str = month_name[month]
        
        # Initialize report data
        employee_summaries = []
        total_doctor_visits_all = 0
        total_office_activities_all = 0
        total_hours_worked_all = 0.0
        
        # Process each employee
        for user in users:
            # Get doctor interactions for this user in the specified month
            doctor_interactions = db.query(models.DoctorInteraction).filter(
                models.DoctorInteraction.logged_by == user.username,
                extract("month", models.DoctorInteraction.visit_date) == month,
                extract("year", models.DoctorInteraction.visit_date) == year
            ).order_by(models.DoctorInteraction.visit_date.desc()).all()
            
            # Get office activities for this user in the specified month
            office_activities = db.query(models.OfficeActivity).filter(
                models.OfficeActivity.msl_username == user.username,
                extract("month", models.OfficeActivity.activity_date) == month,
                extract("year", models.OfficeActivity.activity_date) == year
            ).order_by(models.OfficeActivity.activity_date.desc()).all()
            
            # Calculate unique doctors visited
            unique_doctors = set()
            for interaction in doctor_interactions:
                unique_doctors.add(interaction.doctor_name)
            
            # Calculate work type breakdown
            work_type_breakdown = {"both done": 0, "worked at office": 0, "call supported": 0, "nothing done": 0}
            for activity in office_activities:
                if activity.work_type in work_type_breakdown:
                    work_type_breakdown[activity.work_type] += 1
            
            # Calculate activity category breakdown
            activity_category_breakdown = {}
            for activity in office_activities:
                category = activity.activity_category
                activity_category_breakdown[category] = activity_category_breakdown.get(category, 0) + 1
            
            # Calculate total hours worked
            total_hours = sum(a.hours_worked or 0.0 for a in office_activities)
            
            # Build daily summary
            daily_summary_map = {}
            
            # Add doctor interactions to daily summary
            for interaction in doctor_interactions:
                day_key = interaction.visit_date.isoformat()
                if day_key not in daily_summary_map:
                    daily_summary_map[day_key] = {
                        "date": day_key,
                        "day": interaction.visit_date.day,
                        "doctor_visits": 0,
                        "office_activities": 0,
                        "hours_worked": 0.0,
                        "work_type": None
                    }
                daily_summary_map[day_key]["doctor_visits"] += 1
            
            # Add office activities to daily summary
            for activity in office_activities:
                day_key = activity.activity_date.isoformat()
                if day_key not in daily_summary_map:
                    daily_summary_map[day_key] = {
                        "date": day_key,
                        "day": activity.activity_date.day,
                        "office_activities": 0,
                        "hours_worked": 0.0,
                        "work_type": activity.work_type
                    }
                daily_summary_map[day_key]["office_activities"] += 1
                daily_summary_map[day_key]["hours_worked"] += activity.hours_worked or 0.0
                if not daily_summary_map[day_key]["work_type"]:
                    daily_summary_map[day_key]["work_type"] = activity.work_type
            
            # Convert daily summary map to sorted list
            daily_summary = sorted(daily_summary_map.values(), key=lambda x: x["date"])
            
            # Format doctor interactions for response
            formatted_interactions = [
                schemas.MonthlySummaryDoctorInteraction(
                    id=di.id,
                    doctor_name=di.doctor_name,
                    visit_date=di.visit_date,
                    topics_discussed=di.topics_discussed,
                    summary=di.summary,
                    outcomes=di.outcomes,
                    brand_discussed=di.brand_discussed,
                    interest_level=di.interest_level
                ) for di in doctor_interactions
            ]
            
            # Format office activities for response
            formatted_activities = [
                schemas.MonthlySummaryOfficeActivity(
                    id=oa.id,
                    activity_date=oa.activity_date,
                    activity_category=oa.activity_category,
                    summary=oa.summary,
                    linked_outputs=oa.linked_outputs,
                    work_type=oa.work_type,
                    hours_worked=oa.hours_worked,
                    doctors_visited=oa.doctors_visited
                ) for oa in office_activities
            ]
            
            # Create employee summary
            employee_summary = schemas.EmployeeMonthlySummary(
                employee_id=user.employee_id,
                employee_name=user.username,
                month=month,
                year=year,
                month_name=month_name_str,
                total_doctor_visits=len(doctor_interactions),
                unique_doctors_visited=len(unique_doctors),
                doctor_interactions=formatted_interactions,
                total_office_activities=len(office_activities),
                total_hours_worked=round(total_hours, 2),
                office_activities=formatted_activities,
                work_type_breakdown=work_type_breakdown,
                activity_category_breakdown=activity_category_breakdown,
                daily_summary=daily_summary
            )
            
            employee_summaries.append(employee_summary)
            
            # Update overall totals
            total_doctor_visits_all += len(doctor_interactions)
            total_office_activities_all += len(office_activities)
            total_hours_worked_all += total_hours
        
        # Create the final report response
        report = schemas.MonthlyReportResponse(
            report_month=month,
            report_year=year,
            report_month_name=month_name_str,
            generated_at=datetime.utcnow(),
            employees=employee_summaries,
            total_employees=len(employee_summaries),
            total_doctor_visits_all=total_doctor_visits_all,
            total_office_activities_all=total_office_activities_all,
            total_hours_worked_all=round(total_hours_worked_all, 2)
        )
        
        return report
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"ERROR - Failed to generate monthly report: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Failed to generate report: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
