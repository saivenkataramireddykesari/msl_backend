from fastapi import FastAPI, Depends, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import date
import os
import models, schemas, database
from database import get_db, engine

# Create tables
models.Base.metadata.create_all(bind=engine)

app = FastAPI(title="MSL Engagement Management System")

# CORS configuration from environment variables
cors_origins = os.getenv("CORS_ORIGINS", "*")
if cors_origins == "*":
    allow_origins = ["*"]
else:
    allow_origins = [origin.strip() for origin in cors_origins.split(",")]

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=allow_origins,
    allow_credentials=True,
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
    db_doctor = models.Doctor(**doctor.dict())
    db.add(db_doctor)
    db.commit()
    db.refresh(db_doctor)
    return db_doctor

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
    
@app.delete("/api/doctors/{doctor_id}")
def delete_doctor(doctor_id: int, db: Session = Depends(get_db)):
    """Delete a doctor"""
    doctor = db.query(models.Doctor).filter(models.Doctor.id == doctor_id).first()
    if not doctor:
        raise HTTPException(status_code=404, detail="Doctor not found")
    
    db.delete(doctor)
    db.commit()
    return {"message": "Doctor deleted successfully"}

# ==================== REQUESTS ====================

@app.post("/api/requests", response_model=schemas.Request)
def create_request(request: schemas.RequestCreate, db: Session = Depends(get_db)):
    """Create a new MSL engagement request"""
    # Debug: Log incoming request data
    request_data = request.dict()
    print(f"DEBUG - Received request data: {request_data}")
    print(f"DEBUG - Territory from request: '{request.territory}'")
    print(f"DEBUG - Region from request: '{request.region}'")
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
            objective=request.objective,
            expected_outcome=request.expected_outcome,
            priority=request.priority,
            notes=request.notes,
            user_classification=request.user_classification
        )
        
        print(f"DEBUG - Request object created with territory='{db_request.territory}', region='{db_request.region}'")
        
        db.add(db_request)
        db.commit()
        db.refresh(db_request)
        
        print(f"DEBUG - After commit: ID={db_request.id}, territory='{db_request.territory}', region='{db_request.region}'")
        
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
    db: Session = Depends(get_db)
):
    # Query requests with doctor name
    query = db.query(models.Request, models.Doctor.name.label("doctor_name")).join(
        models.Doctor, models.Request.doctor_id == models.Doctor.id
    )

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

    if role:
        query = query.filter(models.Request.requested_by_role == role)

    results = query.order_by(models.Request.created_at.desc()).all()

    # Build response manually to ensure all fields are included
    response_data = []
    for request, doctor_name in results:
        response_data.append({
            "id": request.id,
            "doctor_id": request.doctor_id,
            "doctor_name": doctor_name,
            "territory": request.territory,
            "region": request.region,
            "therapy_area": request.therapy_area,
            "objective": request.objective,
            "expected_outcome": request.expected_outcome,
            "priority": request.priority,
            "user_classification": request.user_classification,
            "requested_by": request.requested_by,
            "requested_by_role": request.requested_by_role,
            "created_at": request.created_at.isoformat() if request.created_at else None
        })
    
    return response_data

@app.get("/api/requests/{request_id}", response_model=schemas.Request)
def get_request(request_id: int, db: Session = Depends(get_db)):
    """Get a specific request with all details"""
    request = db.query(models.Request).filter(models.Request.id == request_id).first()
    if not request:
        raise HTTPException(status_code=404, detail="Request not found")
    return request

@app.put("/api/requests/{request_id}/user-classification")
def update_request_user_classification(
    request_id: int,
    user_classification: str,
    db: Session = Depends(get_db)
):
    """Update request user classification (potential or non-potential)"""
    valid_classifications = ["potential", "non-potential"]
    if user_classification not in valid_classifications:
        raise HTTPException(status_code=400, detail="Invalid user classification. Must be 'potential' or 'non-potential'")
    
    request = db.query(models.Request).filter(models.Request.id == request_id).first()
    if not request:
        raise HTTPException(status_code=404, detail="Request not found")
    
    request.user_classification = user_classification
    db.commit()
    return {"message": "User classification updated successfully"}

# ==================== DOCTOR INTERACTIONS ====================

@app.post("/api/doctor-interactions", response_model=schemas.DoctorInteraction)
def create_doctor_interaction(
    interaction: schemas.DoctorInteractionCreate,
    db: Session = Depends(get_db)
):
    """Log a doctor interaction"""
    # Verify request exists
    request = db.query(models.Request).filter(models.Request.id == interaction.request_id).first()
    if not request:
        raise HTTPException(status_code=404, detail="Request not found")
    
    db_interaction = models.DoctorInteraction(**interaction.dict())
    db.add(db_interaction)
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

# ==================== OFFICE ACTIVITIES ====================

@app.post("/api/office-activities", response_model=schemas.OfficeActivity)
def create_office_activity(
    activity: schemas.OfficeActivityCreate,
    db: Session = Depends(get_db)
):
    """Log an office activity"""
    db_activity = models.OfficeActivity(**activity.dict())
    db.add(db_activity)
    db.commit()
    db.refresh(db_activity)
    return db_activity

@app.get("/api/office-activities", response_model=List[schemas.OfficeActivity])
def get_office_activities(msl_username: Optional[str] = None, db: Session = Depends(get_db)):
    """Get all office activities, optionally filtered by MSL"""
    query = db.query(models.OfficeActivity)
    if msl_username:
        query = query.filter(models.OfficeActivity.msl_username == msl_username)
    activities = query.order_by(models.OfficeActivity.activity_date.desc()).all()
    return activities

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
    
    # Get doctor interactions
    interactions = db.query(models.DoctorInteraction).filter(
        models.DoctorInteraction.request_id == request_id
    ).all()
    
    for interaction in interactions:
        logs.append(schemas.ActivityLog(
            id=interaction.id,
            type="doctor_interaction",
            date=interaction.visit_date,
            title=f"Doctor Visit: {interaction.doctor_name}",
            details=interaction.summary,
            created_at=interaction.created_at
        ))
    
    # Sort by date (latest first)
    logs.sort(key=lambda x: x.date, reverse=True)
    
    return logs

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)