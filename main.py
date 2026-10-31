import os
from dotenv import load_dotenv
from sqlalchemy import or_

load_dotenv()

from fastapi import FastAPI, Depends, HTTPException, Query, Body, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import extract, func, cast, String, distinct
from typing import List, Optional
from datetime import date, datetime, timedelta
from calendar import month_name
import os
import models
import schemas
import database
from database import get_db, engine
from constants import REQUEST_CREATION_ROLES
from services.hierarchy_service import HierarchyService

# Do not drop/create tables to preserve existing data
# models.Base.metadata.drop_all(bind=engine)
models.Base.metadata.create_all(bind=engine)

# Auto-migrate request_date column if missing
with engine.connect() as conn:
    try:
        from sqlalchemy import text, inspect
        inspector = inspect(engine)
        if 'requests' in inspector.get_table_names():
            columns = [c['name'] for c in inspector.get_columns('requests')]
            if 'request_date' not in columns:
                conn.execute(text("ALTER TABLE requests ADD COLUMN request_date DATE;"))
                conn.commit()
                print("DEBUG: Added 'request_date' column to 'requests' table.")
        if 'tour_plans' in inspector.get_table_names():
            tp_columns = [c['name'] for c in inspector.get_columns('tour_plans')]
            if 'assigned_so_email' not in tp_columns:
                conn.execute(text("ALTER TABLE tour_plans ADD COLUMN assigned_so_email VARCHAR(255) NULL;"))
                conn.commit()
                print("DEBUG: Added 'assigned_so_email' column to 'tour_plans' table.")
    except Exception as e:
        print(f"DEBUG: Auto-migration note: {e}")

app = FastAPI(title="Scientific Officer Management System")

# CORS middleware — allow all origins for dev compatibility
# Load CORS_ORIGINS from environment, fallback to a default list if not set
# CORS_ORIGINS_STR = os.getenv("CORS_ORIGINS", "http://localhost:5173,http://localhost:3000,https://msl-frontend.netlify.app,https://so.pulsepharma.net")
# CORS_ORIGINS = [origin.strip() for origin in CORS_ORIGINS_STR.split(',')]

app.add_middleware(
    CORSMiddleware,
     allow_origins=[
        "https://so.pulsepharma.net",
        "http://localhost:5173",
        "http://localhost:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.post("/api/login", response_model=schemas.LoginResponse)
def login(login_data: schemas.LoginRequest, db: Session = Depends(get_db)):
    """Login using employee_id and password"""
    # Normalize the employee ID: strip whitespace and convert to uppercase for case-insensitive comparison
    normalized_employee_id = login_data.employee_id.strip().upper()
    
    # Find user by Emp_Code with case-insensitive comparison
    user = db.query(models.User).filter(
        func.upper(func.trim(models.User.Emp_Code)) == normalized_employee_id
    ).first()
    
    if not user:
        print(f"DEBUG: Login failed - User not found for employee_id: {login_data.employee_id} (normalized: {normalized_employee_id})")
        raise HTTPException(status_code=401, detail="Invalid employee ID or password")
    
    # If user has no password set, reject password-based login
    if user.password is None:
        raise HTTPException(status_code=401, detail="Password not set for this user. Use passwordless login.")
    
    # Simple password check (no hashing as requested)
    if user.password != login_data.password:
        raise HTTPException(status_code=401, detail="Invalid employee ID or password")
    
    return {
        "username": user.Emp_Name,
        "role": user.Role,
        "employee_id": user.Emp_Code,
        "message": "Login successful",
        "territory": user.Territory,
        "region": user.Region,
        "division": user.Division,
        "bl_territory": user.Territory if user.Role in ["BL", "BH"] else None,
        "bl_region": user.Region if user.Role in ["BL", "BM", "BH"] else None,
    }

@app.post("/api/login-by-employee-id", response_model=schemas.LoginResponse)
def login_by_employee_id(login_data: schemas.UrlLoginRequest, db: Session = Depends(get_db)):
    """Login using employee_id only (passwordless)"""
    # Normalize the employee ID: strip whitespace and convert to uppercase for case-insensitive comparison
    normalized_employee_id = login_data.employee_id.strip().upper()
    
    print(f"DEBUG: Passwordless login attempt - Original: '{login_data.employee_id}', Normalized: '{normalized_employee_id}'")
    
    # Use func.upper for case-insensitive comparison in the database
    user = db.query(models.User).filter(
        func.upper(func.trim(models.User.Emp_Code)) == normalized_employee_id
    ).first()
    
    if not user:
        print(f"DEBUG: Passwordless login failed - User not found for normalized ID: {normalized_employee_id}")
        # List available Emp_Codes for debugging (first 10)
        available_codes = db.query(models.User.Emp_Code).limit(10).all()
        print(f"DEBUG: Sample Emp_Codes in DB: {[code[0] for code in available_codes if code[0]]}")
        raise HTTPException(status_code=401, detail="Invalid employee ID")
    
    return {
        "username": user.Emp_Name,
        "role": user.Role,
        "employee_id": user.Emp_Code,
        "message": "Login successful",
        "territory": user.Territory,
        "region": user.Region,
        "division": user.Division,
        "bl_territory": user.Territory if user.Role in ["BL", "BH"] else None,
        "bl_region": user.Region if user.Role in ["BL", "BM", "BH"] else None,
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
    users = db.query(models.User).filter(models.User.Role.in_(msl_roles)).all()
    return [
        {
            "id": u.id,
            "username": u.Emp_Name,
            "employee_id": u.Emp_Code,
            "role": u.Role,
        }
        for u in users
    ]

# ==================== BRANDS ====================
@app.post("/api/brands", response_model=schemas.Brand)
def create_brand(brand: schemas.BrandCreate, db: Session = Depends(get_db)):
    db_brand = models.Brand(**brand.model_dump())
    db.add(db_brand)
    db.commit()
    db.refresh(db_brand)
    return db_brand

@app.get("/api/brands")
def get_brands(
    division: Optional[str] = Query(None),
    db: Session = Depends(get_db)
):
    print("Division received:", division)

    query = db.query(models.Brand)

    if division:
        print("Filtering by:", division)
    brands = query.all()

    print("Returned:", len(brands))
    return brands

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
    """Create a new doctor with transaction safety"""
    try:
        db_doctor = models.Doctor(**doctor.model_dump())
        db.add(db_doctor)
        db.commit()
        db.refresh(db_doctor)
        print(f"DEBUG - Doctor created successfully: ID={db_doctor.id}, Name={db_doctor.name}")
        return db_doctor
    except Exception as e:
        db.rollback()
        print(f"ERROR - Failed to create doctor: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Failed to create doctor: {str(e)}")

# ==================== CASCADING DROPDOWNS FOR BL ====================
# NOTE: These routes MUST be defined BEFORE the /api/doctors/{doctor_id} route
# because FastAPI matches routes in order and {doctor_id} would catch "regions", etc.

@app.get("/api/new-request/access-data")
def get_access_data(
    current_user_employee_id: str = Query(..., description="Employee ID of the current logged in user"),
    db: Session = Depends(get_db)
):
    """ Returns all dynamically filtered regions, territories, patches, and doctors based on the organizational reporting hierarchy."""
    hierarchy_service = HierarchyService(db)
    print("HierarchyService initialized") # Added line
    
    # Fetch user details for initial logging
    current_user = db.query(models.User).filter(
        func.upper(func.trim(models.User.Emp_Code)) == current_user_employee_id.strip().upper()
    ).first()

    # Add requested debug logs
    print(f"DEBUG ACCESS: Employee: {current_user.Emp_Name if current_user else 'N/A'}")
    print(f"DEBUG ACCESS: Role: {current_user.Role if current_user else 'N/A'}")
    print(f"DEBUG ACCESS: Division: {current_user.Division if current_user else 'N/A'}")

    # Get all accessible data from the hierarchy service
    accessible_employees_raw = hierarchy_service.get_all_accessible_employees(current_user_employee_id)
    accessible_territories_raw = hierarchy_service.get_all_accessible_territories(current_user_employee_id)
    print(f"DEBUG ACCESS: Accessible territories (from hierarchy): {accessible_territories_raw}")
    
    regions = hierarchy_service.get_accessible_regions(current_user_employee_id)
    territories = hierarchy_service.get_accessible_territories_for_dropdown(current_user_employee_id)
    # No territory is selected during initial page load.
    # Patches will be loaded after the user selects a territory.
    patches = []

    print("DEBUG (main.py): No territory selected, patches initialized as []")
    doctors = hierarchy_service.get_accessible_doctors(current_user_employee_id)
    
    # We can just return them as dictionaries or use the schema implicitly if we return the models.
    # To keep payload small, return limited doctor info
    doctors_data = [
        {
            "id": d.id,
            "name": d.name,
            "speciality": d.speciality,
            "region": d.region,
            "territory": d.territory,
            "bm_territory": d.bm_territory,
            "bl_territory": d.bl_territory,
            "bh_territory": d.bh_territory,
            "sbuh_territory": d.sbuh_territory,
            "patch": d.patch,
            "is_priority_doctor": d.is_priority_doctor
        } for d in doctors
    ]
    
    response_payload = {
        "regions": regions,
        "territories": territories,
        "patches": patches,
        "doctors": doctors_data
    }
    print(f"DEBUG (Step 10): API Response: {response_payload}")
    return response_payload

@app.get("/api/doctors/regions")
def get_regions_by_bl_location(
    current_user_employee_id: Optional[str] = Query(None, description="Employee ID of the current user"),
    current_user_role: Optional[str] = Query(None, description="Role of the current user"),
    db: Session = Depends(get_db)
):
    """Get unique regions. If the user is a BL, filter by their assigned region."""
    all_regions_query = db.query(models.Doctor.region).distinct()
    
    if current_user_role in ["BL", "BM"] and current_user_employee_id:
        # Fetch the user's assigned region
        current_user = db.query(models.User).filter(models.User.Emp_Code == current_user_employee_id).first()
        if current_user and current_user.Region:
            print(f"DEBUG: User {current_user_employee_id} found with region: '{current_user.Region}' and role: '{current_user.Role}'")
            query = all_regions_query.filter(models.Doctor.region == current_user.Region)
        else:
            print(f"DEBUG: User {current_user_employee_id} not found or no region assigned. Returning all regions.")
            query = all_regions_query
    else:
        print(f"DEBUG: Not a BL/BM user or no employee ID provided. Returning all regions. Role: {current_user_role}, ID: {current_user_employee_id}")
        query = all_regions_query
    
    raw_regions = query.all()
    regions = [r[0] for r in raw_regions if r[0]]
    print(f"DEBUG: Regions query results after filtering: {regions}")
    return sorted(regions)

@app.get("/api/doctors/territories")
def get_territories_by_region(
    region: str = Query(..., description="Region to filter by"),
    current_user_employee_id: Optional[str] = Query(None, description="Employee ID of the current user"),
    current_user_role: Optional[str] = Query(None, description="Role of the current user"),
    db: Session = Depends(get_db)
):
    """Get unique territories based on selected region and optional BL location"""
    query = db.query(models.Doctor.territory).filter(
        models.Doctor.region == region
    ).distinct()
    
    if current_user_role in ("BL", "BH") and current_user_employee_id:
        bl_user = db.query(models.User).filter(models.User.Emp_Code == current_user_employee_id).first()
        if bl_user and bl_user.Territory:
            query = query.filter(models.Doctor.territory == bl_user.Territory)

    raw_territories = query.all()
    print(f"DEBUG: Raw territories from DB for region {region}: {raw_territories}")
    territories = [t[0] for t in raw_territories if t[0]]
    return sorted(territories)

@app.get("/api/doctors/patches")
def get_patches_by_territory(
    territory: str = Query(..., description="Selected territory"),
    region: Optional[str] = Query(None, description="Selected region"),
    current_user_employee_id: Optional[str] = Query(None),
    current_user_role: Optional[str] = Query(None),
    db: Session = Depends(get_db)
):
    """
    Get patches for the selected territory.

    The selected territory can exist in ANY hierarchy column:
        territory
        bm_territory
        bl_territory
        bh_territory
        sbuh_territory
    """

    print("=" * 70)
    print("PATCH DEBUG START")
    print(f"Selected territory: {territory}")
    print(f"Selected region: {region}")
    print(f"Current employee: {current_user_employee_id}")
    print(f"Current role: {current_user_role}")

    if not territory:
        print("PATCH API: No territory received")
        return []

    # =========================================================
    # 1. CHECK USER ACCESS
    # =========================================================

    if current_user_role in ("BL", "BH") and current_user_employee_id:

        hierarchy_service = HierarchyService(db)

        accessible_territories = (
            hierarchy_service.get_all_accessible_territories(
                current_user_employee_id
            )
        )

        normalized_selected = territory.strip().upper()

        normalized_accessible = {
            t.strip().upper()
            for t in accessible_territories
            if t
        }

        print(
            f"Accessible territory count: "
            f"{len(normalized_accessible)}"
        )

        print(
            f"Selected territory accessible: "
            f"{normalized_selected in normalized_accessible}"
        )

        if normalized_selected not in normalized_accessible:
            print(
                f"PATCH API: Territory '{territory}' "
                f"is NOT accessible"
            )
            return []

    # =========================================================
    # 2. NORMALIZE SELECTED VALUES
    # =========================================================

    selected_territory = territory.strip().upper()

    # =========================================================
    # 3. START QUERY
    # =========================================================

    query = db.query(models.Doctor)

    # =========================================================
    # 4. FILTER SELECTED TERRITORY ACROSS ALL HIERARCHY
    # =========================================================

    territory_filter = or_(
        func.upper(func.trim(models.Doctor.territory))
        == selected_territory,

        func.upper(func.trim(models.Doctor.bm_territory))
        == selected_territory,

        func.upper(func.trim(models.Doctor.bl_territory))
        == selected_territory,

        func.upper(func.trim(models.Doctor.bh_territory))
        == selected_territory,

        func.upper(func.trim(models.Doctor.sbuh_territory))
        == selected_territory
    )

    query = query.filter(territory_filter)

    # =========================================================
    # 5. REGION FILTER
    # =========================================================

    if region:
        selected_region = region.strip().upper()

        query = query.filter(
            func.upper(func.trim(models.Doctor.region))
            == selected_region
        )

    # =========================================================
    # 6. DEBUG DOCTOR COUNT
    # =========================================================

    doctors = query.all()

    print(
        f"Doctors matching territory"
        f"{' + region' if region else ''}: "
        f"{len(doctors)}"
    )

    # =========================================================
    # 7. GET DISTINCT PATCHES
    # =========================================================

    rows = query.with_entities(
        models.Doctor.patch
    ).distinct().all()

    patches = sorted(
        {
            row[0].strip()
            for row in rows
            if row[0] and row[0].strip()
        }
    )

    print(f"Distinct patches: {patches}")
    print(f"Patch count: {len(patches)}")

    print("=" * 70)
    print("PATCH DEBUG END")

    return patches

@app.get("/api/doctors/by-location")
def get_doctors_by_location(
    region: Optional[str] = Query(None),
    territory: Optional[str] = Query(None),
    patch: Optional[str] = Query(None),
    bl_territory: Optional[str] = Query(None),
    db: Session = Depends(get_db)
):
    """
    Get doctors using the selected hierarchy territory.

    The selected territory may exist in:
        - territory
        - bm_territory
        - bl_territory
        - bh_territory
        - sbuh_territory
    """

    print("=" * 70)
    print("DOCTOR FETCH DEBUG START")
    print(f"Region: {region}")
    print(f"Selected Territory: {territory}")
    print(f"Patch: {patch}")
    print(f"BL Territory: {bl_territory}")

    query = db.query(models.Doctor)

    # ---------------------------------------------------------
    # REGION
    # ---------------------------------------------------------
    if region:
        selected_region = region.strip().upper()

        query = query.filter(
            func.upper(func.trim(models.Doctor.region))
            == selected_region
        )

    # ---------------------------------------------------------
    # TERRITORY
    # Search selected territory in ALL hierarchy columns
    # ---------------------------------------------------------
    if territory:
        selected_territory = territory.strip().upper()

        territory_filter = or_(
            func.upper(func.trim(models.Doctor.territory))
            == selected_territory,

            func.upper(func.trim(models.Doctor.bm_territory))
            == selected_territory,

            func.upper(func.trim(models.Doctor.bl_territory))
            == selected_territory,

            func.upper(func.trim(models.Doctor.bh_territory))
            == selected_territory,

            func.upper(func.trim(models.Doctor.sbuh_territory))
            == selected_territory
        )

        query = query.filter(territory_filter)

    # ---------------------------------------------------------
    # PATCH
    # ---------------------------------------------------------
    if patch:
        selected_patch = patch.strip().upper()

        query = query.filter(
            func.upper(func.trim(models.Doctor.patch))
            == selected_patch
        )

    # ---------------------------------------------------------
    # FETCH DOCTORS
    # ---------------------------------------------------------
    doctors = query.order_by(models.Doctor.name).all()

    print(f"DOCTORS FOUND: {len(doctors)}")

    for doctor in doctors[:10]:
        print(
            f"ID={doctor.id}, "
            f"Name={doctor.name}, "
            f"Territory={doctor.territory}, "
            f"BM={doctor.bm_territory}, "
            f"BL={doctor.bl_territory}, "
            f"BH={doctor.bh_territory}, "
            f"SBUH={doctor.sbuh_territory}, "
            f"Patch={doctor.patch}"
        )

    print("DOCTOR FETCH DEBUG END")
    print("=" * 70)

    return doctors

@app.get("/api/doctors/search", response_model=List[schemas.Doctor])
def search_doctors(
    search: str = Query("", description="Search term for doctor name or speciality"),
    region: Optional[str] = Query(None, description="Filter by region"),
    territory: Optional[str] = Query(None, description="Filter by territory"),
    patch: Optional[str] = Query(None, description="Filter by patch"),
    bl_territory: Optional[str] = Query(None, description="Filter by BL territory"),
    db: Session = Depends(get_db)
):
    """
    Search for doctors by name or speciality, filtered by region, territory, patch, and BL territory.
    """
    query = db.query(models.Doctor)

    if region:
        query = query.filter(models.Doctor.region == region)

    if territory:
        query = query.filter(models.Doctor.territory == territory)

    if patch:
        query = query.filter(models.Doctor.patch == patch)

    if bl_territory:
        query = query.filter(models.Doctor.bl_territory == bl_territory)
    
    if search:
        search_pattern = f"%{search}%"
        query = query.filter(
            (models.Doctor.name.ilike(search_pattern)) |
            (models.Doctor.speciality.ilike(search_pattern))
        )

    doctors = query.order_by(models.Doctor.name).all()
    return doctors

# ==================== DOCTOR SPECIFIC ROUTES ====================
# These MUST come after the cascading routes above

@app.get("/api/doctors/all_details")
def get_all_doctors_details(db: Session = Depends(get_db)):
    """Temporarily get all doctor details for debugging."""
    doctors = db.query(models.Doctor).all()
    return [{
        "id": doctor.id,
        "name": doctor.name,
        "speciality": doctor.speciality,
        "therapy_area": doctor.therapy_area,
        "is_priority_doctor": doctor.is_priority_doctor,
        "division": doctor.division,
        "territory": doctor.territory,
        "emp_code": doctor.emp_code,
        "emp_name": doctor.emp_name,
        "region": doctor.region,
        "patch": doctor.patch,
        "doctor_id_ext": doctor.doctor_id_ext,
        "uid_number": doctor.uid_number,
        "bm_territory": doctor.bm_territory,
        "bl_territory": doctor.bl_territory,
        "bh_territory": doctor.bh_territory,
        "sbuh_territory": doctor.sbuh_territory,
    } for doctor in doctors]

@app.get("/api/doctor-interactions/by-date-user", response_model=List[schemas.DoctorInteraction])
def get_interactions_by_date_user(
    visit_date: date,
    logged_by: str,
    db: Session = Depends(get_db)
):
    """Get all doctor interactions logged by a specific user on a specific date"""
    interactions = db.query(models.DoctorInteraction).options(
        joinedload(models.DoctorInteraction.brands)
    ).filter(
        models.DoctorInteraction.logged_by == logged_by,
        models.DoctorInteraction.visit_date == visit_date
    ).order_by(models.DoctorInteraction.visit_date.desc()).all()
    return interactions

@app.get("/api/doctor-interactions/by-user", response_model=List[schemas.DoctorInteraction])
def get_interactions_by_user(
    logged_by: str,
    db: Session = Depends(get_db)
):
    """Get all doctor interactions logged by a specific user"""
    interactions = db.query(models.DoctorInteraction).options(
        joinedload(models.DoctorInteraction.brands)
    ).filter(
        models.DoctorInteraction.logged_by == logged_by
    ).order_by(models.DoctorInteraction.visit_date.desc()).all()
    return interactions


@app.get("/api/doctors/{doctor_id}", response_model=schemas.Doctor)
def get_doctor(doctor_id: int, db: Session = Depends(get_db)):
    """Get a specific doctor by ID"""
    doctor = db.query(models.Doctor).filter(models.Doctor.id == doctor_id).first()
    if not doctor:
        raise HTTPException(status_code=404, detail="Doctor not found")
    return doctor

@app.post("/api/doctors/{doctor_id}/duplicate", response_model=schemas.Doctor)
def duplicate_doctor(doctor_id: int, db: Session = Depends(get_db)):
    """Duplicate a doctor with transaction safety"""
    try:
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
        print(f"DEBUG - Doctor duplicated successfully: Original ID={doctor_id}, New ID={new_doctor.id}")
        return new_doctor
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        print(f"ERROR - Failed to duplicate doctor: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Failed to duplicate doctor: {str(e)}")

@app.delete("/api/doctors/{doctor_id}")
def delete_doctor(doctor_id: int, db: Session = Depends(get_db)):
    """Delete a doctor with transaction safety"""
    try:
        doctor = db.query(models.Doctor).filter(models.Doctor.id == doctor_id).first()
        if not doctor:
            raise HTTPException(status_code=404, detail="Doctor not found")
        
        doctor_name = doctor.name
        db.delete(doctor)
        db.commit()
        print(f"DEBUG - Doctor deleted successfully: ID={doctor_id}, Name={doctor_name}")
        return {"message": "Doctor deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        print(f"ERROR - Failed to delete doctor: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Failed to delete doctor: {str(e)}")

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

def verify_request_creation_permission(request: schemas.RequestCreate):
    if request.requested_by_role not in REQUEST_CREATION_ROLES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not authorized to raise requests."
        )

@app.post("/api/requests", response_model=schemas.Request, dependencies=[Depends(verify_request_creation_permission)])
def create_request(request: schemas.RequestCreate, db: Session = Depends(get_db)):
    """Create a new MSL engagement request"""
    # Debug: Log incoming request data
    request_data = request.model_dump()
    print(f"DEBUG - Received request data: {request_data}")
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
            request_date=request.request_date or date.today(),
            territory=doctor.territory,
            region=doctor.region,
            requested_by=request.requested_by,
            requested_by_role=request.requested_by_role,
            therapy_area=doctor.therapy_area,
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

def resolve_user_match_strings(db: Session, username: str) -> List[str]:
    if not username:
        return []
    
    matches = {username, username.strip()}
    clean_username = ' '.join(username.split())
    matches.add(clean_username)
    matches.add(clean_username.replace(' ', '  '))
    
    user_filters = [
        models.User.Emp_Code == username,
        models.User.Emp_Name.ilike(f"%{clean_username}%"),
        func.replace(models.User.Emp_Name, '  ', ' ').ilike(f"%{clean_username}%")
    ]
    if hasattr(models.User, 'username'):
        user_filters.append(models.User.username == username)

    try:
        users = db.query(models.User).filter(or_(*user_filters)).all()
        for u in users:
            if getattr(u, 'Emp_Code', None):
                matches.add(u.Emp_Code)
            if getattr(u, 'Emp_Name', None):
                emp_name = u.Emp_Name
                matches.add(emp_name)
                c_name = ' '.join(emp_name.split())
                matches.add(c_name)
                matches.add(c_name.replace(' ', '  '))
    except Exception as e:
        print(f"Warning resolving user match strings for '{username}': {e}")
        
    return [m for m in matches if m]

@app.get("/api/requests")
def get_requests(
    search: Optional[str] = None,
    territory: Optional[str] = None,
    region: Optional[str] = None,
    division: Optional[str] = None,
    therapy: Optional[str] = None,
    requested_by: Optional[str] = None,
    role: Optional[str] = None,
    username: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """
    Get requests for the logged-in user.

    IMPORTANT:
    - Region and territory come directly from the requests table.
    - Doctor name is resolved using:
        1. doctors.id
        2. doctors.doctor_id_ext
    - Requests are NOT removed if a doctor record cannot be matched.
    """

    try:
        print("=" * 70)
        print("REQUEST FETCH DEBUG")
        print(f"Role: {repr(role)}")
        print(f"Username: {repr(username)}")

        # ============================================================
        # 1. COUNT DOCTOR INTERACTIONS
        # ============================================================

        interaction_count_subq = db.query(
            models.DoctorInteraction.request_id,
            func.count(models.DoctorInteraction.id).label("visit_count")
        ).group_by(
            models.DoctorInteraction.request_id
        ).subquery()

        # ============================================================
        # 2. DOCTOR NAME SUBQUERY
        # Check logged activity first, then fallback to Doctor table
        # ============================================================

        interaction_doc_subq = db.query(
            models.DoctorInteraction.doctor_name
        ).filter(
            models.DoctorInteraction.request_id == models.Request.id,
            models.DoctorInteraction.doctor_name.isnot(None),
            models.DoctorInteraction.doctor_name != ""
        ).order_by(models.DoctorInteraction.id.desc()).limit(1).scalar_subquery()

        doctor_table_subq = db.query(
            models.Doctor.name
        ).filter(
            or_(
                models.Doctor.id == models.Request.doctor_id,
                models.Doctor.doctor_id_ext == cast(models.Request.doctor_id, String)
            )
        ).limit(1).scalar_subquery()

        doctor_name_subq = func.coalesce(interaction_doc_subq, doctor_table_subq)

        doctor_div_subq = db.query(
            models.Doctor.division
        ).filter(
            or_(
                models.Doctor.id == models.Request.doctor_id,
                models.Doctor.doctor_id_ext == cast(models.Request.doctor_id, String)
            )
        ).limit(1).scalar_subquery()

        # ============================================================
        # 3. MAIN QUERY
        # ============================================================

        query = db.query(
            models.Request,

            # Doctor name resolved separately
            doctor_name_subq.label("doctor_name"),

            # Use values stored in requests
            models.Request.territory.label("request_territory"),
            models.Request.region.label("request_region"),
            doctor_div_subq.label("doctor_division"),

            # Visit count
            interaction_count_subq.c.visit_count
        ).outerjoin(
            interaction_count_subq,
            models.Request.id == interaction_count_subq.c.request_id
        )

        # ============================================================
        # 4. ROLE FILTER
        # ============================================================

        if role in ["MSL", "Scientific Officer"]:
            if username:
                user_matches = resolve_user_match_strings(db, username)
                print(f"Filtering by assigned_msl using match strings: {user_matches}")
                match_conds = []
                for m in user_matches:
                    match_conds.append(models.Request.assigned_msl.ilike(m))
                    match_conds.append(func.replace(models.Request.assigned_msl, '  ', ' ').ilike(' '.join(m.split())))
                if match_conds:
                    query = query.filter(or_(*match_conds))

        elif role in ["BL", "BM", "BH", "SBUH", "BE"]:
            if username:
                user_matches = resolve_user_match_strings(db, username)
                print(f"Filtering by requested_by using match strings: {user_matches}")
                match_conds = []
                for m in user_matches:
                    match_conds.append(models.Request.requested_by.ilike(m))
                    match_conds.append(func.replace(models.Request.requested_by, '  ', ' ').ilike(' '.join(m.split())))
                if match_conds:
                    query = query.filter(or_(*match_conds))

        # ============================================================
        # 5. SEARCH DOCTOR
        # ============================================================

        if search:
            search_pattern = f"%{search}%"

            query = query.filter(
                or_(
                    db.query(models.DoctorInteraction.id).filter(
                        models.DoctorInteraction.request_id == models.Request.id,
                        models.DoctorInteraction.doctor_name.ilike(search_pattern)
                    ).exists(),
                    db.query(models.Doctor.id).filter(
                        or_(
                            models.Doctor.id == models.Request.doctor_id,
                            models.Doctor.doctor_id_ext == cast(models.Request.doctor_id, String)
                        ),
                        models.Doctor.name.ilike(search_pattern)
                    ).exists()
                )
            )

        # ============================================================
        # 6. TERRITORY FILTER
        #
        # IMPORTANT:
        # Use Request.territory, NOT Doctor.territory.
        # ============================================================

        if territory:
            query = query.filter(
                models.Request.territory == territory
            )

        # ============================================================
        # 7. REGION FILTER
        #
        # IMPORTANT:
        # Use Request.region, NOT Doctor.region.
        # ============================================================

        if region:
            query = query.filter(
                models.Request.region == region
            )

        if division:
            query = query.filter(
                db.query(models.Doctor.id).filter(
                    or_(
                        models.Doctor.id == models.Request.doctor_id,
                        models.Doctor.doctor_id_ext == cast(models.Request.doctor_id, String)
                    ),
                    func.upper(func.trim(models.Doctor.division)) == division.strip().upper()
                ).exists()
            )

        # ============================================================
        # 8. THERAPY FILTER
        # ============================================================

        if therapy:
            query = query.filter(
                models.Request.therapy_area == therapy
            )

        # ============================================================
        # 9. REQUESTED BY FILTER
        # ============================================================

        if requested_by:
            query = query.filter(
                models.Request.requested_by == requested_by
            )

        # ============================================================
        # 10. EXECUTE QUERY
        # ============================================================

        results = query.order_by(
            models.Request.created_at.desc()
        ).all()

        print(f"DEBUG - Requests found: {len(results)}")

        # ============================================================
        # 11. BUILD RESPONSE
        # ============================================================

        response_data = []

        for (
            request,
            doctor_name,
            request_territory,
            request_region,
            doctor_division,
            visit_count
        ) in results:

            response_data.append({

                # ----------------------------------------------------
                # Request ID
                # ----------------------------------------------------

                "id": request.id,

                # ----------------------------------------------------
                # Doctor
                # ----------------------------------------------------

                "doctor_id": request.doctor_id,
                "doctor_name": doctor_name,
                "division": doctor_division or "",

                # ----------------------------------------------------
                # Region / Territory
                # IMPORTANT:
                # These come from requests table.
                # ----------------------------------------------------

                "region": request_region,
                "territory": request_territory,

                # ----------------------------------------------------
                # Request information
                # ----------------------------------------------------

                "therapy_area": request.therapy_area,

                "brand": request.brand,
                "objective": request.objective,
                "expected_outcome": request.expected_outcome,
                "priority": request.priority,
                "notes": request.notes,

                # ----------------------------------------------------
                # Brand 2
                # ----------------------------------------------------

                "brand2": request.brand2,
                "objective2": request.objective2,
                "expected_outcome2": request.expected_outcome2,
                "priority2": request.priority2,
                "notes2": request.notes2,

                # ----------------------------------------------------
                # Classification
                # ----------------------------------------------------

                "user_classification": request.user_classification,

                # ----------------------------------------------------
                # Users
                # ----------------------------------------------------

                "requested_by": request.requested_by,
                "requested_by_role": request.requested_by_role,
                "assigned_msl": request.assigned_msl,

                # ----------------------------------------------------
                # Status
                # ----------------------------------------------------

                "request_status": (
                    request.request_status
                    or "Pending"
                ),

                "rx_status_brand1": request.rx_status_brand1,
                "rx_status_brand2": request.rx_status_brand2,

                # ----------------------------------------------------
                # Visits
                # ----------------------------------------------------

                "num_visits": visit_count or 0,

                # ----------------------------------------------------
                # Dates
                # ----------------------------------------------------

                "request_date": (
                    request.request_date.isoformat()
                    if request.request_date
                    else (
                        request.created_at.date().isoformat()
                        if request.created_at
                        else None
                    )
                ),

                "created_at": (
                    request.created_at.isoformat()
                    if request.created_at
                    else None
                )
            })

        # ============================================================
        # 12. DEBUG OUTPUT
        # ============================================================

        print(
            f"DEBUG - Returning {len(response_data)} requests"
        )

        for item in response_data[:10]:
            print(
                f"  Request #{item['id']} | "
                f"Doctor: {item['doctor_name']} | "
                f"Region: {item['region']} | "
                f"Territory: {item['territory']}"
            )

        print("=" * 70)

        return response_data

    except Exception as e:

        print("=" * 70)
        print("ERROR - Failed to fetch requests")
        print(f"ERROR: {str(e)}")

        import traceback
        traceback.print_exc()

        print("=" * 70)

        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch requests: {str(e)}"
        )


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
    if role in ["MSL", "Scientific Officer"] and username:
        user_matches = resolve_user_match_strings(db, username)
        req_msl = request.assigned_msl or ""
        req_msl_clean = ' '.join(req_msl.split()).lower()
        is_assigned = any(
            m.lower() == req_msl_clean or
            m.lower() in req_msl_clean or
            req_msl_clean in m.lower()
            for m in user_matches
        )
        if not is_assigned and req_msl:
            raise HTTPException(status_code=403, detail="Access denied. You are not assigned to this request.")
            
    return request

@app.put("/api/requests/bulk-assign")
def bulk_assign_requests(
    assign_data: schemas.RequestBulkAssign,
    db: Session = Depends(get_db)
):
    """Bulk assign/reassign multiple requests to a single MSL/Scientific Officer"""
    try:
        if not assign_data.request_ids:
            raise HTTPException(status_code=400, detail="No request IDs provided")

        requests = db.query(models.Request).filter(models.Request.id.in_(assign_data.request_ids)).all()
        if not requests:
            raise HTTPException(status_code=404, detail="No matching requests found")

        updated_count = 0
        new_msl = assign_data.assigned_msl

        for request in requests:
            previous_msl = request.assigned_msl
            if previous_msl != new_msl:
                request.assigned_msl = new_msl
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

                log_entry = models.RequestAssignmentLog(
                    request_id=request.id,
                    assigned_by=assign_data.assigned_by,
                    previous_msl=previous_msl,
                    new_msl=new_msl
                )
                db.add(log_entry)
                updated_count += 1

        db.commit()
        return {
            "message": f"Successfully updated {updated_count} request(s)",
            "updated_count": updated_count,
            "assigned_msl": new_msl
        }
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        print(f"ERROR - Failed bulk assign: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Failed to bulk assign requests: {str(e)}")


@app.put("/api/requests/{request_id}/assign")
def assign_request(
    request_id: int,
    assign_data: schemas.RequestAssign,
    db: Session = Depends(get_db)
):
    """Assign/Reassign a request to an MSL and log the assignment history with transaction safety"""
    try:
        request = db.query(models.Request).filter(models.Request.id == request_id).first()
        if not request:
            raise HTTPException(status_code=404, detail="Request not found")
        
        previous_msl = request.assigned_msl
        new_msl = assign_data.assigned_msl
        
        # Only log and update if there's an actual change
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
            print(f"DEBUG - Request {request_id} assigned successfully: {previous_msl} -> {new_msl}")
            
        return {
            "message": "Request assigned successfully",
            "assigned_msl": request.assigned_msl
        }
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        print(f"ERROR - Failed to assign request {request_id}: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Failed to assign request: {str(e)}")

@app.put("/api/requests/{request_id}/date")
def update_request_date(
    request_id: int,
    request_date: Optional[str] = Query(None, description="New request date YYYY-MM-DD"),
    payload: Optional[dict] = Body(None),
    db: Session = Depends(get_db)
):
    """Update request date with transaction safety"""
    try:
        date_str = request_date
        if not date_str and payload and isinstance(payload, dict):
            date_str = payload.get("request_date")

        if not date_str:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="request_date is required"
            )

        if isinstance(date_str, date):
            target_date = date_str
        else:
            try:
                target_date = date.fromisoformat(str(date_str).strip())
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid date format. Expected YYYY-MM-DD."
                )

        request = db.query(models.Request).filter(models.Request.id == request_id).first()
        if not request:
            raise HTTPException(status_code=404, detail="Request not found")

        request.request_date = target_date
        db.commit()
        db.refresh(request)
        print(f"DEBUG - Request {request_id} request date updated to {target_date}")
        return {
            "message": "Request date updated successfully",
            "request_date": request.request_date.isoformat()
        }
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        print(f"ERROR - Failed to update request date for request {request_id}: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Failed to update request date: {str(e)}")

@app.put("/api/requests/{request_id}/user-classification")
def update_request_user_classification(
    request_id: int,
    user_classification: str = Query(..., description="User classification: potential, non-potential, or default"),
    db: Session = Depends(get_db)
):
    """Update request user classification (potential, non-potential, or default) and sync to doctor profile with transaction safety"""
    try:
        valid_classifications = ["potential", "non-potential", "default"]
        if user_classification not in valid_classifications:
            raise HTTPException(status_code=400, detail="Invalid user classification. Must be 'potential', 'non-potential', or 'default'")
        
        request = db.query(models.Request).filter(models.Request.id == request_id).first()
        if not request:
            raise HTTPException(status_code=404, detail="Request not found")
        
        # Update request classification
        request.user_classification = user_classification
        
        # Sync to doctor profile - update the doctor's priority status based on classification
        doctor = db.query(models.Doctor).filter(models.Doctor.id == request.doctor_id).first()
        if doctor:
            if user_classification == "potential":
                doctor.is_priority_doctor = True
            elif user_classification == "non-potential":
                doctor.is_priority_doctor = False
            # For "default", keep the doctor's current priority status
        
        db.commit()
        print(f"DEBUG - Request {request_id} user classification updated: {user_classification}, Doctor priority updated: {doctor is not None}")
        return {
            "message": "User classification updated successfully",
            "user_classification": user_classification,
            "doctor_updated": doctor is not None
        }
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        print(f"ERROR - Failed to update user classification for request {request_id}: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Failed to update user classification: {str(e)}")

@app.put("/api/requests/{request_id}/rx-status")
def update_rx_status(
    request_id: int,
    rx_status_brand1: Optional[str] = Query(None, description="RX status for brand 1: potential, non-potential, default"),
    rx_status_brand2: Optional[str] = Query(None, description="RX status for brand 2: potential, non-potential, default"),
    db: Session = Depends(get_db)
):
    """Update per-brand RX status for a request with transaction safety"""
    try:
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
        print(f"DEBUG - Request {request_id} RX status updated: Brand1={request.rx_status_brand1}, Brand2={request.rx_status_brand2}")
        return {
            "message": "RX status updated successfully",
            "rx_status_brand1": request.rx_status_brand1,
            "rx_status_brand2": request.rx_status_brand2
        }
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        print(f"ERROR - Failed to update RX status for request {request_id}: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Failed to update RX status: {str(e)}")

# ==================== DOCTOR INTERACTIONS ====================

@app.post("/api/doctor-interactions", response_model=schemas.DoctorInteraction)
def create_doctor_interaction(
    interaction: schemas.DoctorInteractionCreate,
    db: Session = Depends(get_db)
):
    """Log a doctor interaction with dynamic brand details"""
    if interaction.visit_date:
        today = date.today()
        ninety_days_ago = today - timedelta(days=90)
        if interaction.visit_date < ninety_days_ago or interaction.visit_date > today:
            raise HTTPException(
                status_code=400,
                detail=f"Visit date must be within the last 90 days ({ninety_days_ago} to {today})."
            )

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
        
        if activity_date:
            today = date.today()
            ninety_days_ago = today - timedelta(days=90)
            if activity_date < ninety_days_ago or activity_date > today:
                raise HTTPException(
                    status_code=400,
                    detail=f"Activity date must be within the last 90 days ({ninety_days_ago} to {today})."
                )
        
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
    """Get all activities for an MSL, dynamically syncing doctor visits and work types across office activities and field interactions"""
    try:
        print(f"DEBUG - Fetching activities for msl_username: {msl_username}")
        query = db.query(models.OfficeActivity)
        if msl_username:
            query = query.filter(models.OfficeActivity.msl_username == msl_username)
        office_activities = query.order_by(models.OfficeActivity.activity_date.desc()).all()

        # Build map of doctor interaction counts per date for this user
        if msl_username:
            interactions = db.query(
                models.DoctorInteraction.visit_date,
                func.count(models.DoctorInteraction.id)
            ).filter(
                models.DoctorInteraction.logged_by == msl_username
            ).group_by(models.DoctorInteraction.visit_date).all()
            interactions_by_user_date = {(msl_username, v_date): cnt for v_date, cnt in interactions}
        else:
            interactions = db.query(
                models.DoctorInteraction.logged_by,
                models.DoctorInteraction.visit_date,
                func.count(models.DoctorInteraction.id)
            ).group_by(
                models.DoctorInteraction.logged_by,
                models.DoctorInteraction.visit_date
            ).all()
            interactions_by_user_date = {(usr, v_date): cnt for usr, v_date, cnt in interactions if usr}

        # Track existing (msl_username, activity_date) pairs
        existing_pairs = set()
        for a in office_activities:
            pair = (a.msl_username, a.activity_date)
            existing_pairs.add(pair)
            doc_count = interactions_by_user_date.get(pair, 0)
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

        # Synthesize field activity entries for days where doctor visits occurred without office activity
        field_activities = []
        for (user_name, visit_date), doc_count in interactions_by_user_date.items():
            if (user_name, visit_date) not in existing_pairs and doc_count > 0:
                synthetic_id = - (abs(hash(f"{user_name}_{visit_date}")) % 10000000) - 1
                field_act = schemas.OfficeActivity(
                    id=synthetic_id,
                    msl_username=user_name,
                    activity_date=visit_date,
                    activity_category="Call Supported",
                    summary=f"Supported {doc_count} doctor visit{'s' if doc_count > 1 else ''} (Field Call)",
                    linked_outputs=None,
                    work_type="call supported",
                    hours_worked=0.0,
                    doctors_visited=doc_count,
                    created_at=datetime.combine(visit_date, datetime.min.time())
                )
                field_activities.append(field_act)

        all_activities = sorted(
            list(office_activities) + field_activities,
            key=lambda x: x.activity_date,
            reverse=True
        )
        print(f"DEBUG - Found {len(all_activities)} total activities ({len(office_activities)} office, {len(field_activities)} field-only)")
        return all_activities
    except Exception as e:
        print(f"ERROR - Failed to fetch activities: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Failed to fetch activities: {str(e)}")

@app.get("/api/office-activities/users", response_model=List[str])
def get_office_activity_users(db: Session = Depends(get_db)):
    """Get unique list of MSL usernames who have logged activities or doctor interactions"""
    act_users = [u[0] for u in db.query(models.OfficeActivity.msl_username).distinct().all() if u[0]]
    int_users = [u[0] for u in db.query(models.DoctorInteraction.logged_by).distinct().all() if u[0]]
    return sorted(list(set(act_users + int_users)))

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
        # Get brand names from the brands relationship
        brand_names = []
        if interaction.brands:
            brand_names = [b.brand_name for b in interaction.brands if b.brand_name]
        
        logs.append(schemas.ActivityLog(
            id=interaction.id,
            type="doctor_interaction",
            date=interaction.visit_date,
            title=f"Visit by {interaction.logged_by or 'Unknown'}",
            details=interaction.objections,
            created_at=interaction.created_at,
            brands=brand_names if brand_names else None,
            logged_by=interaction.logged_by
        ))
    
    # Sort by date (latest first)
    logs.sort(key=lambda x: x.date, reverse=True)
    
    return logs

# ==================== DEBUG: check logged_by values ====================

@app.get("/api/reports/debug-names")
def debug_employee_names(
    employee_id: str = Query(..., description="Employee ID to check"),
    db: Session = Depends(get_db)
):
    """Debug: compare Emp_Name in Users table vs logged_by in DoctorInteraction and msl_username in OfficeActivity"""
    user = db.query(models.User).filter(models.User.Emp_Code == employee_id).first()
    if not user:
        raise HTTPException(status_code=404, detail=f"User with Emp_Code={employee_id} not found")

    sample_interactions = db.query(models.DoctorInteraction.logged_by).distinct().limit(20).all()
    sample_activities = db.query(models.OfficeActivity.msl_username).distinct().limit(20).all()

    return {
        "user_Emp_Code": user.Emp_Code,
        "user_Emp_Name": user.Emp_Name,
        "distinct_logged_by_values_sample": [r[0] for r in sample_interactions],
        "distinct_msl_username_values_sample": [r[0] for r in sample_activities],
    }

# ==================== MONTHLY EMPLOYEE SUMMARY REPORT ====================

@app.get("/api/reports/roles")
def get_user_roles(db: Session = Depends(get_db)):
    """Get list of distinct user roles"""
    roles = db.query(models.User.Role).distinct().all()
    roles_list = sorted([r[0].strip() for r in roles if r[0] and r[0].strip()])
    return roles_list

@app.get("/api/reports/monthly-summary", response_model=schemas.MonthlyReportResponse)
def get_monthly_employee_summary(
    month: int = Query(..., ge=1, le=12, description="Month (1-12)"),
    year: int = Query(..., ge=2000, le=2100, description="Year (e.g., 2024)"),
    employee_ids: Optional[str] = Query(None, description="Comma-separated employee IDs"),
    role: Optional[str] = Query(None, description="Filter by user role"),
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
            target_employee_ids = [eid.strip() for eid in employee_ids.split(",") if eid.strip()]
        
        # Get all users or filter by specific employee IDs / role
        users_query = db.query(models.User)
        if target_employee_ids:
            users_query = users_query.filter(models.User.Emp_Code.in_(target_employee_ids))
        if role and role.strip() and role.strip().lower() != "all":
            users_query = users_query.filter(models.User.Role == role.strip())
        
        users = users_query.all()
        
        if not users:
            raise HTTPException(status_code=404, detail="No employees found for the specified criteria")
        
        # Prepare month name
        month_name_str = month_name[month]
        
        # Initialize report data
        employee_summaries = []
        total_doctor_visits_all = 0
        total_office_activities_all = 0
        total_hours_worked_all = 0.0
        
        # Process each employee
        for user in users:
            print(f"DEBUG: Processing report for employee {user.Emp_Name} (ID: {user.Emp_Code})")

            # Get doctor interactions for this user in the specified month
            print(f"DEBUG: Querying doctor interactions for {user.Emp_Name} (Month: {month}, Year: {year})")
            doctor_interactions = db.query(models.DoctorInteraction).filter(
                models.DoctorInteraction.logged_by == user.Emp_Name,
                extract("month", models.DoctorInteraction.visit_date) == month,
                extract("year", models.DoctorInteraction.visit_date) == year
            ).options(
                joinedload(models.DoctorInteraction.brands),
                joinedload(models.DoctorInteraction.request).joinedload(models.Request.doctor)
            ).order_by(models.DoctorInteraction.visit_date.desc()).all()
            print(f"DEBUG: Found {len(doctor_interactions)} doctor interactions for {user.Emp_Name}")
            
            # Get office activities for this user in the specified month
            print(f"DEBUG: Querying office activities for {user.Emp_Name} (Month: {month}, Year: {year})")
            office_activities = db.query(models.OfficeActivity).filter(
                models.OfficeActivity.msl_username == user.Emp_Name,
                extract("month", models.OfficeActivity.activity_date) == month,
                extract("year", models.OfficeActivity.activity_date) == year
            ).order_by(models.OfficeActivity.activity_date.desc()).all()
            print(f"DEBUG: Found {len(office_activities)} office activities for {user.Emp_Name}")
            
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
            
            # Format doctor interactions for response with doctor & request metadata
            formatted_interactions = [
                schemas.MonthlySummaryDoctorInteraction(
                    id=di.id,
                    doctor_name=di.doctor_name,
                    visit_date=di.visit_date,
                    objections=di.objections,
                    brands=di.brands,
                    speciality=di.request.doctor.speciality if di.request and di.request.doctor else None,
                    therapy_area=di.request.doctor.therapy_area if di.request and di.request.doctor else (di.request.therapy_area if di.request else None),
                    division=di.request.doctor.division if di.request and di.request.doctor else None,
                    territory=di.request.doctor.territory if di.request and di.request.doctor else (di.request.territory if di.request else None),
                    region=di.request.doctor.region if di.request and di.request.doctor else (di.request.region if di.request else None),
                    patch=di.request.doctor.patch if di.request and di.request.doctor else None,
                    is_priority_doctor=di.request.doctor.is_priority_doctor if di.request and di.request.doctor else None,
                    requested_by=di.request.requested_by if di.request else None,
                    requested_by_role=di.request.requested_by_role if di.request else None,
                    request_id=di.request_id
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
            
            # Get direct reportings from User table
            reports_query = db.query(models.User).filter(
                func.upper(func.trim(models.User.Reporting_Manager_Code)) == user.Emp_Code.strip().upper()
            ).all()
            direct_reports_data = [
                {
                    "employee_id": r.Emp_Code,
                    "employee_name": r.Emp_Name,
                    "role": r.Role,
                    "territory": r.Territory,
                    "hq": r.HQ,
                    "region": r.Region
                } for r in reports_query
            ]

            # Create employee summary
            employee_summary = schemas.EmployeeMonthlySummary(
                employee_id=user.Emp_Code,
                employee_name=user.Emp_Name,
                role=user.Role,
                territory=user.Territory,
                hq=user.HQ,
                region=user.Region,
                reporting_manager=user.Reporting_Manager,
                reporting_manager_code=user.Reporting_Manager_Code,
                direct_reports=direct_reports_data,
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

@app.get("/api/reports/daily-summary", response_model=schemas.DailyReportResponse)
def get_daily_employee_summary(
    report_date: date = Query(..., description="Date for the daily report (YYYY-MM-DD)"),
    employee_ids: Optional[str] = Query(None, description="Comma-separated employee IDs (e.g., 'E9250,E5057')"),
    role: Optional[str] = Query(None, description="Filter by user role"),
    db: Session = Depends(get_db)
):
    """
    Get daily working summary report for specified employees.
    If employee_ids is not provided, returns report for all employees (optionally filtered by role).
    """
    try:
        # Parse employee IDs if provided
        target_employee_ids = []
        if employee_ids:
            target_employee_ids = [eid.strip() for eid in employee_ids.split(",") if eid.strip()]
        
        # Get all users or filter by specific employee IDs / role
        users_query = db.query(models.User)
        if target_employee_ids:
            users_query = users_query.filter(models.User.Emp_Code.in_(target_employee_ids))
        if role and role.strip() and role.strip().lower() != "all":
            users_query = users_query.filter(models.User.Role == role.strip())
        
        users = users_query.all()
        
        if not users:
            raise HTTPException(status_code=404, detail="No employees found for the specified criteria")

        employee_summaries = []
        
        for user in users:
            # Get doctor interactions for this user on the specified date
            doctor_interactions = db.query(models.DoctorInteraction).filter(
                models.DoctorInteraction.logged_by == user.Emp_Name,
                models.DoctorInteraction.visit_date == report_date
            ).options(
                joinedload(models.DoctorInteraction.brands),
                joinedload(models.DoctorInteraction.request).joinedload(models.Request.doctor)
            ).order_by(models.DoctorInteraction.visit_date.desc()).all()
            
            # Get office activities for this user on the specified date
            office_activities = db.query(models.OfficeActivity).filter(
                models.OfficeActivity.msl_username == user.Emp_Name,
                models.OfficeActivity.activity_date == report_date
            ).order_by(models.OfficeActivity.activity_date.desc()).all()

            # Calculate unique doctors visited
            unique_doctors = set()
            for interaction in doctor_interactions:
                unique_doctors.add(interaction.doctor_name)

            # Calculate total hours worked from office activities
            total_hours = sum(a.hours_worked or 0.0 for a in office_activities)

            # Determine overall work type for the day
            calculated_work_type = "nothing done"
            if total_hours > 0.0 and len(doctor_interactions) > 0:
                calculated_work_type = "both done"
            elif total_hours > 0.0:
                calculated_work_type = "worked at office"
            elif len(doctor_interactions) > 0:
                calculated_work_type = "call supported"
            else:
                calculated_work_type = "nothing done"

            # Format doctor interactions for response with doctor & request metadata
            formatted_interactions = [
                schemas.MonthlySummaryDoctorInteraction(
                    id=di.id,
                    doctor_name=di.doctor_name,
                    visit_date=di.visit_date,
                    objections=di.objections,
                    brands=di.brands,
                    speciality=di.request.doctor.speciality if di.request and di.request.doctor else None,
                    therapy_area=di.request.doctor.therapy_area if di.request and di.request.doctor else (di.request.therapy_area if di.request else None),
                    division=di.request.doctor.division if di.request and di.request.doctor else None,
                    territory=di.request.doctor.territory if di.request and di.request.doctor else (di.request.territory if di.request else None),
                    region=di.request.doctor.region if di.request and di.request.doctor else (di.request.region if di.request else None),
                    patch=di.request.doctor.patch if di.request and di.request.doctor else None,
                    is_priority_doctor=di.request.doctor.is_priority_doctor if di.request and di.request.doctor else None,
                    requested_by=di.request.requested_by if di.request else None,
                    requested_by_role=di.request.requested_by_role if di.request else None,
                    request_id=di.request_id
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

            employee_summary = schemas.EmployeeDailySummary(
                employee_id=user.Emp_Code,
                employee_name=user.Emp_Name,
                role=user.Role,
                territory=user.Territory,
                hq=user.HQ,
                region=user.Region,
                reporting_manager=user.Reporting_Manager,
                reporting_manager_code=user.Reporting_Manager_Code,
                report_date=report_date,
                day_name=report_date.strftime("%A"),  # Full weekday name
                total_doctor_visits=len(doctor_interactions),
                unique_doctors_visited=len(unique_doctors),
                doctor_interactions=formatted_interactions,
                total_office_activities=len(office_activities),
                total_hours_worked=round(total_hours, 2),
                office_activities=formatted_activities,
                work_type=calculated_work_type
            )
            employee_summaries.append(employee_summary)

        report = schemas.DailyReportResponse(
            report_date=report_date,
            report_day_name=report_date.strftime("%A"),
            generated_at=datetime.utcnow(),
            employees=employee_summaries
        )
        return report
    
    except HTTPException:
        raise
    except Exception as e:
        print(f"ERROR - Failed to generate daily report: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Failed to generate daily report: {str(e)}")

# ==================== PLANNED VISITS REPORT ====================

@app.get("/api/planned-visits", response_model=schemas.PlannedVisitsResponse)
def get_planned_visits(
    region: Optional[str] = Query(None, description="Filter by region"),
    territory: Optional[str] = Query(None, description="Filter by territory"),
    scientific_officer: Optional[str] = Query(None, description="Filter by assigned MSL/Scientific Officer"),
    requested_by: Optional[str] = Query(None, description="Filter by BL name"),
    month: Optional[int] = Query(None, description="Month filter (1-12)"),
    year: Optional[int] = Query(None, description="Year filter (e.g. 2026)"),
    search: Optional[str] = Query(None, description="Search across fields"),
    db: Session = Depends(get_db)
):
    """
    Get requests raised by BLs for all scientific officers, aggregated with region, territory, requested date, and count of planned doctors.
    """
    try:
        if not isinstance(region, str): region = None
        if not isinstance(territory, str): territory = None
        if not isinstance(scientific_officer, str): scientific_officer = None
        if not isinstance(requested_by, str): requested_by = None
        if not isinstance(search, str): search = None
        if not isinstance(month, int) and month is not None:
            try: month = int(month)
            except: month = None
        if not isinstance(year, int) and year is not None:
            try: year = int(year)
            except: year = None

        # Query requests raised by BLs (case-insensitive check on requested_by_role)
        query = db.query(models.Request).filter(
            func.upper(func.trim(models.Request.requested_by_role)).in_(["BL", "BM", "BH", "SBUH", "BE"])
        )

        req_date_col = func.coalesce(models.Request.request_date, func.date(models.Request.created_at))

        if month:
            query = query.filter(extract("month", req_date_col) == month)
        if year:
            query = query.filter(extract("year", req_date_col) == year)

        if region:
            query = query.filter(models.Request.region == region)
        if territory:
            query = query.filter(models.Request.territory == territory)
        if scientific_officer:
            if scientific_officer.lower() == "unassigned":
                query = query.filter(
                    or_(models.Request.assigned_msl.is_(None), func.trim(models.Request.assigned_msl) == "")
                )
            else:
                query = query.filter(models.Request.assigned_msl.ilike(f"%{scientific_officer}%"))
        if requested_by:
            query = query.filter(models.Request.requested_by.ilike(f"%{requested_by}%"))

        all_requests = query.all()

        # Batch load doctors map for fast lookup
        doctor_ids = [r.doctor_id for r in all_requests if r.doctor_id]
        doctors_map = {}
        if doctor_ids:
            doctors = db.query(models.Doctor).filter(models.Doctor.id.in_(doctor_ids)).all()
            for d in doctors:
                doctors_map[d.id] = d

        groups_map = {}
        so_set = set()
        regions_set = set()
        territories_set = set()

        for r in all_requests:
            so_name = r.assigned_msl.strip() if r.assigned_msl and r.assigned_msl.strip() else "Unassigned"
            reg = r.region or "N/A"
            terr = r.territory or "N/A"
            req_date_str = (
                r.request_date.isoformat()
                if r.request_date
                else (r.created_at.date().isoformat() if r.created_at else "N/A")
            )
            bl_name = r.requested_by or "N/A"

            if reg != "N/A":
                regions_set.add(reg)
            if terr != "N/A":
                territories_set.add(terr)
            so_set.add(so_name)

            doc = doctors_map.get(r.doctor_id)
            doc_name = doc.name if doc else f"Doctor #{r.doctor_id}"

            # Grouping key
            group_key = (so_name, reg, terr, req_date_str, bl_name)

            if group_key not in groups_map:
                groups_map[group_key] = {
                    "scientific_officer": so_name,
                    "region": reg,
                    "territory": terr,
                    "requested_date": req_date_str,
                    "requested_by": bl_name,
                    "requested_by_role": r.requested_by_role or "BL",
                    "doctors": []
                }

            groups_map[group_key]["doctors"].append(
                schemas.PlannedVisitDoctorDetail(
                    request_id=r.id,
                    doctor_id=r.doctor_id,
                    doctor_name=doc_name,
                    speciality=doc.speciality if doc else None,
                    patch=doc.patch if doc else None,
                    brand=r.brand,
                    brand2=r.brand2,
                    status=r.request_status or "Pending",
                    user_classification=r.user_classification or "default"
                )
            )

        # Build response list
        visit_groups = []
        idx = 1
        for (so_name, reg, terr, req_date_str, bl_name), data in groups_map.items():
            # Apply search filter if present
            if search:
                s_lower = search.lower()
                matches_search = (
                    s_lower in so_name.lower()
                    or s_lower in reg.lower()
                    or s_lower in terr.lower()
                    or s_lower in bl_name.lower()
                    or s_lower in req_date_str.lower()
                    or any(s_lower in d.doctor_name.lower() for d in data["doctors"])
                )
                if not matches_search:
                    continue

            visit_groups.append(
                schemas.PlannedVisitGroup(
                    id=str(idx),
                    scientific_officer=data["scientific_officer"],
                    region=data["region"],
                    territory=data["territory"],
                    requested_date=data["requested_date"],
                    requested_by=data["requested_by"],
                    requested_by_role=data["requested_by_role"],
                    count_planned_doctors=len(data["doctors"]),
                    doctors=data["doctors"]
                )
            )
            idx += 1

        # Sort by requested_date desc, scientific_officer asc
        visit_groups.sort(key=lambda x: (x.requested_date or "", x.scientific_officer), reverse=True)

        total_planned_doctors = sum(g.count_planned_doctors for g in visit_groups)

        return schemas.PlannedVisitsResponse(
            total_planned_visits=len(visit_groups),
            total_planned_doctors=total_planned_doctors,
            total_scientific_officers=len(so_set),
            scientific_officers_list=sorted(list(so_set)),
            regions_list=sorted(list(regions_set)),
            territories_list=sorted(list(territories_set)),
            planned_visits=visit_groups
        )

    except Exception as e:
        print(f"ERROR - Failed to fetch planned visits: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Failed to fetch planned visits: {str(e)}")

# ==================== TOUR PLANS ====================

@app.get("/api/tour-plans/meta")
def get_tour_plan_meta(db: Session = Depends(get_db)):
    """Returns available divisions and scientific officers for creating a tour plan"""
    try:
        doc_divs = db.query(models.Doctor.division).filter(models.Doctor.division.isnot(None)).distinct().all()
        user_divs = db.query(models.User.Division).filter(models.User.Division.isnot(None)).distinct().all()
        
        all_divs = set()
        for (d,) in doc_divs:
            if d and d.strip():
                all_divs.add(d.strip())
        for (d,) in user_divs:
            if d and d.strip():
                all_divs.add(d.strip())
        
        divisions_list = sorted(list(all_divs))

        msl_users = db.query(models.User).filter(
            models.User.Role.in_(["MSL", "Scientific Officer"])
        ).order_by(models.User.Emp_Name).all()

        so_list = [
            {
                "id": u.id,
                "name": u.Emp_Name or "Unknown",
                "employee_code": u.Emp_Code or "",
                "email": u.email1 or "",
                "role": u.Role or "Scientific Officer"
            }
            for u in msl_users
        ]

        return {
            "divisions": divisions_list,
            "scientific_officers": so_list
        }
    except Exception as e:
        print(f"Error fetching tour plan metadata: {e}")
        raise HTTPException(status_code=500, detail=str(e))

DIVISION_TERRITORY_PREFIXES = {
    "NUCLEUS": ["NUC-"],
    "MAXIMUS": ["MAX-"],
    "NUTRIUS": ["ZEN-", "NUT-"],
    "GLADIUS": ["GLA-"],
    "STIMULUS": ["STI-", "GLST-"],
    "IMPETUS": ["IMP-"],
    "GLAMUS": ["GLST-", "GLA-", "GLAM-"]
}

NON_TERRITORY_TOKENS = {
    "BE", "BM", "BL", "DIR", "DIR-1", "DIR-2", "DIR-3", "PE", "NE", "TE", 
    "HR", "GPM", "SPM", "MM", "PM", "MH", "AVP", "SBUH", "BH", "BT", "BRE", 
    "TRAINEE EXECUTIVE", "KAE", "SBE", "ZE-PE", "ZE-SPM", "ADMIN-HR", "ADMIN", "DEFAULT"
}

@app.get("/api/tour-plans/territories")
def get_tour_plan_territories(
    divisions: Optional[str] = Query(None, description="Comma-separated divisions"),
    db: Session = Depends(get_db)
):
    """Returns distinct, cleaned territories for selected divisions"""
    try:
        if not divisions:
            return []

        div_list = [d.strip() for d in divisions.split(",") if d.strip()]
        if not div_list:
            return []

        doc_terrs = db.query(models.Doctor.territory).filter(
            models.Doctor.division.in_(div_list),
            models.Doctor.territory.isnot(None)
        ).distinct().all()

        user_terrs = db.query(models.User.Territory).filter(
            models.User.Division.in_(div_list),
            models.User.Territory.isnot(None)
        ).distinct().all()

        doc_bl_terrs = db.query(models.Doctor.bl_territory).filter(
            models.Doctor.division.in_(div_list),
            models.Doctor.bl_territory.isnot(None)
        ).distinct().all()

        all_terrs = set()
        for group in (doc_terrs, user_terrs, doc_bl_terrs):
            for (t,) in group:
                if t:
                    cleaned = t.strip()
                    cleaned_up = cleaned.upper()
                    if (
                        cleaned_up
                        and cleaned_up not in NON_TERRITORY_TOKENS
                        and len(cleaned) > 2
                        and not cleaned_up.startswith("DIR-")
                        and not cleaned_up.startswith("ADMIN")
                    ):
                        all_terrs.add(cleaned)

        return sorted(list(all_terrs))
    except Exception as e:
        print(f"Error fetching territories for divisions: {e}")
        raise HTTPException(status_code=500, detail=str(e))

def get_matching_bls_for_tour_plan(
    db: Session,
    divisions: List[str],
    territories: List[str]
) -> List[models.User]:
    """
    Finds ONLY the Business Leaders (BLs) that correspond to BOTH the selected divisions
    AND selected territories.
    """
    if not divisions or not territories:
        return []

    norm_divs = [d.strip().upper() for d in divisions if d and d.strip()]
    norm_terrs = [t.strip().upper() for t in territories if t and t.strip()]
    if not norm_divs or not norm_terrs:
        return []

    # 1. Fetch BL candidates strictly within the selected divisions
    bl_candidates = db.query(models.User).filter(
        func.upper(func.trim(models.User.Role)) == "BL",
        func.upper(func.trim(models.User.Division)).in_(norm_divs)
    ).all()

    if not bl_candidates:
        return []

    def get_territory_div(t: str) -> Optional[str]:
        t_up = t.strip().upper()
        for div, prefixes in DIVISION_TERRITORY_PREFIXES.items():
            if any(t_up.startswith(p) for p in prefixes):
                return div
        return None

    matched_bls = []
    seen_ids = set()

    for bl in bl_candidates:
        if bl.id in seen_ids:
            continue
        bl_div = (bl.Division or "").strip().upper()
        bl_terr = (bl.Territory or "").strip().upper()
        bl_hq = (bl.HQ or "").strip().upper()
        bl_base = bl_terr[:-3] if bl_terr.endswith("-BL") else bl_terr

        # Filter territories relevant for this candidate BL's division:
        # Either the territory has this division's prefix, or has no recognized division prefix (e.g. city name)
        relevant_terrs = [
            t for t in norm_terrs
            if get_territory_div(t) is None or get_territory_div(t) == bl_div
        ]
        if not relevant_terrs:
            continue

        target_bl_identifiers = set(relevant_terrs)

        # 2a. Doctor table mapping: doctor territory -> bl_territory within this division
        doc_bl_terrs = db.query(models.Doctor.bl_territory).filter(
            func.upper(func.trim(models.Doctor.division)) == bl_div,
            func.upper(func.trim(models.Doctor.territory)).in_(relevant_terrs),
            models.Doctor.bl_territory.isnot(None)
        ).distinct().all()
        for (bl_t,) in doc_bl_terrs:
            if bl_t and bl_t.strip():
                target_bl_identifiers.add(bl_t.strip().upper())

        # 2b. User table mapping for BM: BM territory -> Area_Name (which is BL territory)
        bm_bl_terrs = db.query(models.User.Area_Name).filter(
            func.upper(func.trim(models.User.Role)) == "BM",
            func.upper(func.trim(models.User.Division)) == bl_div,
            func.upper(func.trim(models.User.Territory)).in_(relevant_terrs),
            models.User.Area_Name.isnot(None)
        ).distinct().all()
        for (area,) in bm_bl_terrs:
            if area and area.strip():
                target_bl_identifiers.add(area.strip().upper())

        # 2c. User table mapping for Field reps: Field territory -> BM Area_Name -> BL Area_Name
        field_bm_terrs = db.query(models.User.Area_Name).filter(
            func.upper(func.trim(models.User.Role)).in_(["BE", "MR", "FE", "TE", "NE", "PE", "SBE", "TRAINEE EXECUTIVE"]),
            func.upper(func.trim(models.User.Division)) == bl_div,
            func.upper(func.trim(models.User.Territory)).in_(relevant_terrs),
            models.User.Area_Name.isnot(None)
        ).distinct().all()
        bm_names = [t[0].strip().upper() for t in field_bm_terrs if t[0] and t[0].strip()]
        if bm_names:
            bm_to_bl = db.query(models.User.Area_Name).filter(
                func.upper(func.trim(models.User.Role)) == "BM",
                func.upper(func.trim(models.User.Territory)).in_(bm_names),
                models.User.Area_Name.isnot(None)
            ).distinct().all()
            for (area,) in bm_to_bl:
                if area and area.strip():
                    target_bl_identifiers.add(area.strip().upper())

        # 3. Match candidate BL against target identifiers and HQ
        is_match = False
        if bl_terr and bl_terr in target_bl_identifiers:
            is_match = True
        elif bl_hq and bl_hq in target_bl_identifiers:
            is_match = True
        else:
            for t in relevant_terrs:
                if bl_base and (t == bl_base or t.startswith(bl_base + "-") or t.startswith(bl_base + "_")):
                    is_match = True
                    break
                if bl_hq and (bl_hq == t or bl_hq in t or t.endswith("-" + bl_hq) or f"-{bl_hq}-" in t):
                    is_match = True
                    break

        if is_match:
            seen_ids.add(bl.id)
            matched_bls.append(bl)

    return matched_bls

@app.post("/api/tour-plans")
def create_tour_plan(
    plan: schemas.TourPlanCreate,
    current_user_role: Optional[str] = Query(None),
    current_user_name: Optional[str] = Query(None),
    db: Session = Depends(get_db)
):
    """
    Only Asst General Manager (or Admin) can create a tour plan.
    Saves the plan, assigns it to a Scientific Officer,
    and triggers email notifications to the assigned Scientific Officer and relevant Business Leaders (BLs).
    """
    try:
        caller_role = (current_user_role or plan.created_by_role or "").strip()
        allowed_roles = ["Asst General Manager", "Associate Vice President", "Admin", "admin"]
        if caller_role not in allowed_roles:
            raise HTTPException(
                status_code=403,
                detail="Access denied: Only Asst General Manager role can create a tour plan."
            )

        if plan.from_date < date.today():
            raise HTTPException(
                status_code=400,
                detail="From Date cannot be in the past. Please select current or future date."
            )

        if plan.from_date > plan.to_date:
            raise HTTPException(
                status_code=400,
                detail="From Date cannot be later than To Date."
            )

        if not plan.divisions:
            raise HTTPException(
                status_code=400,
                detail="Please select at least one division."
            )

        if not plan.territories:
            raise HTTPException(
                status_code=400,
                detail="Please select at least one territory."
            )

        if not plan.assigned_so:
            raise HTTPException(
                status_code=400,
                detail="Please select a Scientific Officer to assign the tour plan."
            )

        import json
        from calendar import month_name
        from services.email_service import send_email, build_tour_plan_email_html

        month_val = plan.month or month_name[plan.from_date.month]
        year_val = plan.year or str(plan.from_date.year)

        today = date.today()
        month_list = list(month_name)
        plan_year_num = None
        try:
            plan_year_num = int(year_val)
        except (ValueError, TypeError):
            pass

        if plan_year_num is not None:
            plan_month_num = month_list.index(month_val) if month_val in month_list else plan.from_date.month
            if plan_year_num < today.year or (plan_year_num == today.year and plan_month_num < today.month):
                raise HTTPException(
                    status_code=400,
                    detail="Tour Plan Month and Year cannot be in the past. Please select current or future month and year."
                )
        creator_name = current_user_name or plan.created_by or "Asst General Manager"

        # 1. Resolve Assigned Scientific Officer User & Email
        so_user = None
        if plan.assigned_so_id:
            so_user = db.query(models.User).filter(models.User.id == plan.assigned_so_id).first()
        if not so_user and plan.assigned_so_code:
            so_user = db.query(models.User).filter(models.User.Emp_Code == plan.assigned_so_code).first()
        if not so_user and plan.assigned_so:
            so_user = db.query(models.User).filter(
                models.User.Role.in_(["MSL", "Scientific Officer"]),
                models.User.Emp_Name == plan.assigned_so
            ).first()

        so_name = (so_user.Emp_Name if so_user else plan.assigned_so) or "Scientific Officer"
        
        target_so_email = None
        if getattr(plan, "assigned_so_email", None) and plan.assigned_so_email.strip():
            target_so_email = plan.assigned_so_email.strip()
            # If so_user exists and has no email, save it permanently in User table
            if so_user and (not so_user.email1 or not so_user.email1.strip()):
                so_user.email1 = target_so_email
                db.commit()
                db.refresh(so_user)
        elif so_user and so_user.email1 and so_user.email1.strip():
            target_so_email = so_user.email1.strip()

        # 2. Persist Tour Plan Record
        db_plan = models.TourPlan(
            from_date=plan.from_date,
            to_date=plan.to_date,
            month=month_val,
            year=year_val,
            divisions=json.dumps(plan.divisions),
            territories=json.dumps(plan.territories),
            assigned_so=plan.assigned_so,
            assigned_so_id=plan.assigned_so_id,
            assigned_so_code=plan.assigned_so_code,
            assigned_so_email=target_so_email,
            created_by=creator_name,
            created_by_emp_code=plan.created_by_emp_code,
            created_by_role=caller_role,
            remarks=plan.remarks or "",
            status="Planned"
        )
        db.add(db_plan)
        db.commit()
        db.refresh(db_plan)

        # 3. Trigger Email Notifications
        email_summary = {
            "scientific_officer": None,
            "business_leaders": []
        }

        plan_dict = {
            "from_date": plan.from_date,
            "to_date": plan.to_date,
            "month": month_val,
            "year": year_val,
            "divisions": plan.divisions,
            "territories": plan.territories,
            "assigned_so": plan.assigned_so,
            "assigned_so_email": target_so_email,
            "remarks": plan.remarks
        }

        # 3a. Email to Assigned Scientific Officer
        if target_so_email:
            so_subject = f"New Tour Plan Assigned ({plan.from_date} to {plan.to_date}) | Pulse Scientific Office"
            so_html = build_tour_plan_email_html(
                recipient_name=so_name,
                recipient_role="Scientific Officer",
                is_so=True,
                plan_data=plan_dict,
                created_by_name=creator_name
            )
            res = send_email(to_email=target_so_email, subject=so_subject, html_content=so_html)
            email_summary["scientific_officer"] = {
                "name": so_name,
                "role": "Scientific Officer",
                "email": target_so_email,
                "status": "sent" if res.get("success") else "failed",
                "simulated": res.get("simulated", False),
                "error": res.get("error") if not res.get("success") else None
            }
        else:
            email_summary["scientific_officer"] = {
                "name": so_name,
                "role": "Scientific Officer",
                "email": None,
                "status": "not_sent",
                "reason": "No email address registered for this Scientific Officer"
            }

        # 3b. Email ONLY to Business Leaders (BLs) matching selected division and territories
        bl_users = get_matching_bls_for_tour_plan(
            db=db,
            divisions=plan.divisions,
            territories=plan.territories
        )

        seen_emails = set()
        for bl in bl_users:
            bl_email = (bl.email1 or "").strip()
            bl_name = bl.Emp_Name or bl.Territory or "Business Leader"
            bl_div = bl.Division or ""
            bl_terr = bl.Territory or ""
            if bl_email and bl_email not in seen_emails:
                seen_emails.add(bl_email)
                bl_subject = f"Tour Plan Notification: {bl_div or 'Division'} ({plan.from_date} to {plan.to_date}) | Pulse Scientific Office"
                bl_html = build_tour_plan_email_html(
                    recipient_name=bl_name,
                    recipient_role=f"Business Leader ({bl_div})",
                    is_so=False,
                    plan_data=plan_dict,
                    created_by_name=creator_name
                )
                res = send_email(to_email=bl_email, subject=bl_subject, html_content=bl_html)
                email_summary["business_leaders"].append({
                    "name": bl_name,
                    "role": f"Business Leader ({bl_div})" if bl_div else "Business Leader",
                    "email": bl_email,
                    "division": bl_div,
                    "territory": bl_terr,
                    "status": "sent" if res.get("success") else "failed",
                    "simulated": res.get("simulated", False),
                    "error": res.get("error") if not res.get("success") else None
                })
            elif not bl_email:
                email_summary["business_leaders"].append({
                    "name": bl_name,
                    "role": f"Business Leader ({bl_div})" if bl_div else "Business Leader",
                    "email": None,
                    "division": bl_div,
                    "territory": bl_terr,
                    "status": "not_sent",
                    "reason": "No email address registered"
                })

        # Calculate delivery stats
        so_status = email_summary["scientific_officer"]["status"] if email_summary["scientific_officer"] else "not_sent"
        bl_sent_count = len([b for b in email_summary["business_leaders"] if b["status"] == "sent"])
        bl_failed_count = len([b for b in email_summary["business_leaders"] if b["status"] == "failed"])
        bl_skipped_count = len([b for b in email_summary["business_leaders"] if b["status"] == "not_sent"])
        total_recipients = (1 if email_summary["scientific_officer"] else 0) + len(email_summary["business_leaders"])
        total_sent = (1 if so_status == "sent" else 0) + bl_sent_count

        email_summary["stats"] = {
            "total_recipients": total_recipients,
            "total_sent": total_sent,
            "total_failed": (1 if so_status == "failed" else 0) + bl_failed_count,
            "total_skipped": (1 if so_status == "not_sent" else 0) + bl_skipped_count,
            "so_sent": so_status == "sent",
            "bl_sent_count": bl_sent_count,
            "bl_total_count": len(email_summary["business_leaders"])
        }

        # Persist email_status in tour_plans record
        db_plan.email_status = json.dumps(email_summary)
        db.commit()
        db.refresh(db_plan)

        return {
            "message": "Tour plan created successfully and notifications triggered",
            "plan": {
                "id": db_plan.id,
                "from_date": db_plan.from_date,
                "to_date": db_plan.to_date,
                "month": db_plan.month,
                "year": db_plan.year,
                "divisions": plan.divisions,
                "territories": plan.territories,
                "assigned_so": db_plan.assigned_so,
                "assigned_so_id": db_plan.assigned_so_id,
                "assigned_so_code": db_plan.assigned_so_code,
                "assigned_so_email": db_plan.assigned_so_email,
                "created_by": db_plan.created_by,
                "created_by_role": db_plan.created_by_role,
                "status": db_plan.status,
                "remarks": db_plan.remarks,
                "email_status": email_summary,
                "created_at": db_plan.created_at
            },
            "emails_triggered": email_summary
        }

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        print(f"Error creating tour plan: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Failed to create tour plan: {str(e)}")

@app.get("/api/tour-plans")
def get_tour_plans(
    role: Optional[str] = None,
    username: Optional[str] = None,
    employee_id: Optional[str] = None,
    division: Optional[str] = None,
    month: Optional[str] = None,
    year: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """
    Get tour plans filtered according to role:
    - Asst General Manager / Admin: sees all tour plans
    - Scientific Officer: sees plans assigned to them
    - BL: sees plans matching their division or territory
    """
    import json
    try:
        query = db.query(models.TourPlan)

        if month:
            query = query.filter(models.TourPlan.month == month)
        if year:
            query = query.filter(models.TourPlan.year == year)

        plans = query.order_by(models.TourPlan.from_date.desc()).all()

        result = []
        user_role = (role or "").strip()

        # If BL role, find BL's division and territory
        bl_division = (division or "").strip()
        bl_territory = ""
        if user_role == "BL" and (username or employee_id):
            bl_user = None
            if employee_id:
                bl_user = db.query(models.User).filter(
                    func.upper(func.trim(models.User.Emp_Code)) == employee_id.strip().upper()
                ).first()
            if not bl_user and username:
                bl_user = db.query(models.User).filter(
                    func.upper(func.trim(models.User.Emp_Name)) == username.strip().upper()
                ).first()
            if bl_user:
                if bl_user.Division:
                    bl_division = bl_user.Division.strip()
                if bl_user.Territory:
                    bl_territory = bl_user.Territory.strip()

        for p in plans:
            try:
                p_divs = json.loads(p.divisions) if p.divisions else []
            except Exception:
                p_divs = [d.strip() for d in p.divisions.split(",") if d.strip()]

            try:
                p_terrs = json.loads(p.territories) if p.territories else []
            except Exception:
                p_terrs = [t.strip() for t in p.territories.split(",") if t.strip()]

            # Role filtering logic
            if user_role in ["Asst General Manager", "Associate Vice President", "Admin", "admin", ""]:
                # Full visibility
                pass
            elif user_role in ["MSL", "Scientific Officer"]:
                # Visibility only if assigned to this SO
                matches_so = False
                if username and p.assigned_so.strip().lower() == username.strip().lower():
                    matches_so = True
                if employee_id and p.assigned_so_code and p.assigned_so_code.strip().lower() == employee_id.strip().lower():
                    matches_so = True
                if not matches_so:
                    continue
            elif user_role == "BL":
                # Visibility if BL's division AND territory matches, or if BL was notified in email_status
                matches_bl = False
                p_email_status = json.loads(p.email_status) if getattr(p, 'email_status', None) else None
                if p_email_status and isinstance(p_email_status.get("business_leaders"), list):
                    for bl_entry in p_email_status["business_leaders"]:
                        if username and bl_entry.get("name") and bl_entry["name"].strip().lower() == username.strip().lower():
                            matches_bl = True
                            break
                        if bl_user and bl_user.email1 and bl_entry.get("email") and bl_entry["email"].strip().lower() == bl_user.email1.strip().lower():
                            matches_bl = True
                            break
                        if bl_territory and bl_entry.get("territory") and bl_entry["territory"].strip().upper() == bl_territory.strip().upper():
                            matches_bl = True
                            break

                if not matches_bl:
                    div_matches = bl_division and any(d.strip().lower() == bl_division.strip().lower() for d in p_divs)
                    if div_matches:
                        if bl_territory:
                            bl_terr_upper = bl_territory.strip().upper()
                            bl_base = bl_terr_upper[:-3] if bl_terr_upper.endswith('-BL') else bl_terr_upper
                            for t in p_terrs:
                                t_upper = t.strip().upper()
                                if t_upper == bl_terr_upper or t_upper == bl_base or t_upper.startswith(bl_base + '-') or t_upper.startswith(bl_base + '_'):
                                    matches_bl = True
                                    break
                                if bl_user and bl_user.HQ and bl_user.HQ.strip().upper() in t_upper:
                                    matches_bl = True
                                    break
                            if not matches_bl:
                                doc_match = db.query(models.Doctor.id).filter(
                                    func.upper(func.trim(models.Doctor.division)) == bl_division.strip().upper(),
                                    func.upper(func.trim(models.Doctor.bl_territory)) == bl_terr_upper,
                                    func.upper(func.trim(models.Doctor.territory)).in_([t.strip().upper() for t in p_terrs])
                                ).first()
                                if doc_match:
                                    matches_bl = True
                        else:
                            matches_bl = True
                if not matches_bl:
                    continue
            else:
                if bl_division and not any(d.lower() == bl_division.lower() for d in p_divs):
                    continue

            # Calculate assigned doctors count for this tour plan:
            # Doctors assigned with requests within the plan date range for the selected divisions and territories
            assigned_docs_count = 0
            total_master_docs_count = 0
            territory_doc_counts = {}
            division_doc_counts = {}

            if p_divs and p_terrs and p.from_date and p.to_date:
                try:
                    norm_divs = [d.strip().upper() for d in p_divs if d.strip()]
                    norm_terrs = [t.strip().upper() for t in p_terrs if t.strip()]

                    # Distinct doctors who have requests in this date range
                    assigned_docs_count = db.query(func.count(distinct(models.Request.doctor_id))).join(
                        models.Doctor, models.Request.doctor_id == models.Doctor.id
                    ).filter(
                        func.upper(func.trim(models.Doctor.division)).in_(norm_divs),
                        func.upper(func.trim(models.Doctor.territory)).in_(norm_terrs),
                        models.Request.request_date >= p.from_date,
                        models.Request.request_date <= p.to_date
                    ).scalar() or 0

                    # Total doctors in master database for these divisions and territories
                    total_master_docs_count = db.query(func.count(models.Doctor.id)).filter(
                        func.upper(func.trim(models.Doctor.division)).in_(norm_divs),
                        func.upper(func.trim(models.Doctor.territory)).in_(norm_terrs)
                    ).scalar() or 0

                    # Breakdown by territory (assigned doctors with requests in date range)
                    terr_counts = db.query(
                        func.upper(func.trim(models.Doctor.territory)),
                        func.count(distinct(models.Request.doctor_id))
                    ).join(
                        models.Doctor, models.Request.doctor_id == models.Doctor.id
                    ).filter(
                        func.upper(func.trim(models.Doctor.division)).in_(norm_divs),
                        func.upper(func.trim(models.Doctor.territory)).in_(norm_terrs),
                        models.Request.request_date >= p.from_date,
                        models.Request.request_date <= p.to_date
                    ).group_by(func.upper(func.trim(models.Doctor.territory))).all()
                    territory_doc_counts = {t[0]: t[1] for t in terr_counts}

                    # Breakdown by division
                    div_counts = db.query(
                        func.upper(func.trim(models.Doctor.division)),
                        func.count(distinct(models.Request.doctor_id))
                    ).join(
                        models.Doctor, models.Request.doctor_id == models.Doctor.id
                    ).filter(
                        func.upper(func.trim(models.Doctor.division)).in_(norm_divs),
                        func.upper(func.trim(models.Doctor.territory)).in_(norm_terrs),
                        models.Request.request_date >= p.from_date,
                        models.Request.request_date <= p.to_date
                    ).group_by(func.upper(func.trim(models.Doctor.division))).all()
                    division_doc_counts = {d[0]: d[1] for d in div_counts}
                except Exception as cnt_err:
                    print(f"Error calculating doctor counts for plan {p.id}: {cnt_err}")

            result.append({
                "id": p.id,
                "from_date": p.from_date,
                "to_date": p.to_date,
                "month": p.month,
                "year": p.year,
                "divisions": p_divs,
                "territories": p_terrs,
                "assigned_so": p.assigned_so,
                "assigned_so_id": p.assigned_so_id,
                "assigned_so_code": p.assigned_so_code,
                "assigned_so_email": getattr(p, "assigned_so_email", None),
                "created_by": p.created_by,
                "created_by_emp_code": p.created_by_emp_code,
                "created_by_role": p.created_by_role,
                "status": p.status,
                "remarks": p.remarks,
                "assigned_doctors_count": assigned_docs_count,
                "total_doctors_count": total_master_docs_count,
                "territory_doctor_counts": territory_doc_counts,
                "division_doctor_counts": division_doc_counts,
                "email_status": json.loads(p.email_status) if getattr(p, 'email_status', None) else None,
                "created_at": p.created_at,
                "updated_at": p.updated_at
            })

        return result

    except Exception as e:
        print(f"Error fetching tour plans: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/tour-plans/{plan_id}")
def get_tour_plan_detail(
    plan_id: int,
    db: Session = Depends(get_db)
):
    """
    Get detailed tour plan with assigned doctor requests and territory breakdowns.
    """
    import json
    plan = db.query(models.TourPlan).filter(models.TourPlan.id == plan_id).first()
    if not plan:
        raise HTTPException(status_code=404, detail="Tour plan not found")

    try:
        p_divs = json.loads(plan.divisions) if plan.divisions else []
    except Exception:
        p_divs = [d.strip() for d in plan.divisions.split(",") if d.strip()]

    try:
        p_terrs = json.loads(plan.territories) if plan.territories else []
    except Exception:
        p_terrs = [t.strip() for t in plan.territories.split(",") if t.strip()]

    norm_divs = [d.strip().upper() for d in p_divs if d.strip()]
    norm_terrs = [t.strip().upper() for t in p_terrs if t.strip()]

    # Query assigned doctor requests within date range and matching divisions/territories
    assigned_requests = []
    if norm_divs and norm_terrs and plan.from_date and plan.to_date:
        reqs = db.query(models.Request).join(
            models.Doctor, models.Request.doctor_id == models.Doctor.id
        ).filter(
            func.upper(func.trim(models.Doctor.division)).in_(norm_divs),
            func.upper(func.trim(models.Doctor.territory)).in_(norm_terrs),
            models.Request.request_date >= plan.from_date,
            models.Request.request_date <= plan.to_date
        ).order_by(models.Request.request_date.asc(), models.Doctor.name.asc()).all()

        for r in reqs:
            doc = r.doctor
            assigned_requests.append({
                "request_id": r.id,
                "doctor_id": r.doctor_id,
                "doctor_name": doc.name if doc else "N/A",
                "speciality": doc.speciality if doc else "",
                "division": doc.division if doc else "",
                "territory": doc.territory if doc else "",
                "patch": getattr(doc, "patch", "") if doc else "",
                "is_priority_doctor": getattr(doc, "is_priority_doctor", False) if doc else False,
                "mr_name": getattr(doc, "emp_name", "") if doc else "",
                "request_date": r.request_date.isoformat() if r.request_date else None,
                "requested_by": r.requested_by,
                "requested_by_role": r.requested_by_role,
                "brand": r.brand,
                "brand2": r.brand2,
                "objective": r.objective,
                "expected_outcome": r.expected_outcome,
                "priority": r.priority,
                "request_status": r.request_status,
                "assigned_msl": r.assigned_msl
            })

    # Summary statistics
    total_assigned_doctors = len(set(r["doctor_id"] for r in assigned_requests))
    total_master_docs = db.query(func.count(models.Doctor.id)).filter(
        func.upper(func.trim(models.Doctor.division)).in_(norm_divs),
        func.upper(func.trim(models.Doctor.territory)).in_(norm_terrs)
    ).scalar() or 0

    return {
        "id": plan.id,
        "from_date": plan.from_date,
        "to_date": plan.to_date,
        "month": plan.month,
        "year": plan.year,
        "divisions": p_divs,
        "territories": p_terrs,
        "assigned_so": plan.assigned_so,
        "assigned_so_id": plan.assigned_so_id,
        "assigned_so_code": plan.assigned_so_code,
        "assigned_so_email": getattr(plan, "assigned_so_email", None),
        "created_by": plan.created_by,
        "created_by_emp_code": plan.created_by_emp_code,
        "created_by_role": plan.created_by_role,
        "status": plan.status,
        "remarks": plan.remarks,
        "email_status": json.loads(plan.email_status) if getattr(plan, "email_status", None) else None,
        "created_at": plan.created_at,
        "updated_at": plan.updated_at,
        "assigned_doctors_count": total_assigned_doctors,
        "total_doctors_count": total_master_docs,
        "assigned_requests": assigned_requests
    }

@app.delete("/api/tour-plans/{plan_id}")
def delete_tour_plan(
    plan_id: int,
    current_user_role: Optional[str] = Query(None),
    db: Session = Depends(get_db)
):
    """Allows Asst General Manager or Admin to delete a tour plan"""
    caller_role = (current_user_role or "").strip()
    if caller_role not in ["Asst General Manager", "Associate Vice President", "Admin", "admin"]:
        raise HTTPException(status_code=403, detail="Permission denied")
    
    plan = db.query(models.TourPlan).filter(models.TourPlan.id == plan_id).first()
    if not plan:
        raise HTTPException(status_code=404, detail="Tour plan not found")
    
    db.delete(plan)
    db.commit()
    return {"message": "Tour plan deleted successfully", "id": plan_id}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)

