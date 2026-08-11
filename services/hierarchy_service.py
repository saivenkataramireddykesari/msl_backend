from typing import List, Dict, Set, Optional, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import func
from models import User, Doctor
from sqlalchemy import or_

class HierarchyService:
    """
    Service to manage organizational hierarchy and data access filtering.
    """
    def __init__(self, db: Session):
        self.db = db

    def get_all_accessible_data(self, emp_code: str) -> Tuple[Set[str], Set[str]]:
        """
        Core traversal logic using BFS.
        Optimized to load hierarchy data into memory first to avoid N+1 queries.
        Returns a tuple of (accessible_employee_ids, accessible_territories)
        """
        print(f"Entered get_all_accessible_data() for Employee ID: {emp_code}") # Added line
        # Load all users once
        all_users = self.db.query(User).all()
        
        # Build dictionaries for in-memory traversal
        reports_dict: Dict[str, List[User]] = {}
        territory_children_dict: Dict[str, List[User]] = {}
        user_by_emp_code: Dict[str, User] = {}
        
        for u in all_users:
            # Populate user_by_emp_code
            if u.Emp_Code:
                user_by_emp_code[u.Emp_Code.strip().upper()] = u
                
            # Populate reports_dict (Manager Code -> Direct Reports)
            if u.Reporting_Manager_Code:
                mgr_code = u.Reporting_Manager_Code.strip().upper()
                if mgr_code not in reports_dict:
                    reports_dict[mgr_code] = []
                reports_dict[mgr_code].append(u)
                
            # Populate territory_children_dict (Area_Name -> Child Users)
            if u.Area_Name:
                if u.Area_Name not in territory_children_dict:
                    territory_children_dict[u.Area_Name] = []
                territory_children_dict[u.Area_Name].append(u)

        accessible_employees = set()
        accessible_territories = set()
        
        # 1. Start with logged in employee
        normalized_emp_code = emp_code.strip().upper()
        self_user = user_by_emp_code.get(normalized_emp_code)

        # DEBUG: Step 1 - Logged in employee details
        if self_user:
            print(f"DEBUG (Step 1): Logged in Employee Found:")
            print(f"DEBUG (Step 1): Employee Code: {self_user.Emp_Code}")
            print(f"DEBUG (Step 1): Employee Name: {self_user.Emp_Name}")
            print(f"DEBUG (Step 1): Territory: {self_user.Territory}")
            print(f"DEBUG (Step 1): Area_Name: {self_user.Area_Name}")
            print(f"DEBUG (Step 1): Reporting_Manager_Code: {self_user.Reporting_Manager_Code}")
            print(f"DEBUG (Step 1): Role: {self_user.Role}")
        else:
            print(f"DEBUG (Step 1): Logged in Employee with Emp_Code {emp_code} NOT Found.")

        
        if self_user:
            if self_user.Emp_Code:
                accessible_employees.add(self_user.Emp_Code)
            if self_user.Territory:
                accessible_territories.add(self_user.Territory)
                
        # 2. Find direct reports using dict
        direct_reports = reports_dict.get(normalized_emp_code, [])

        # DEBUG: Step 2 - Direct Reports
        print(f"DEBUG (Step 2): Manager: {normalized_emp_code}")
        if direct_reports:
            for report in direct_reports:
                print(f"DEBUG (Step 2): Found: {report.Emp_Code}")
            print(f"DEBUG (Step 2): Total Direct Reports Found: {len(direct_reports)}")
        else:
            print(f"DEBUG (Step 2): No Direct Reports Found for {normalized_emp_code}")
        
        queue = []
        
        for report in direct_reports:
            if report.Emp_Code:
                accessible_employees.add(report.Emp_Code)
            if report.Territory and report.Territory not in accessible_territories:
                accessible_territories.add(report.Territory)
                queue.append(report.Territory)
                print(f"DEBUG (Step 3): Added to BFS queue (direct report): {report.Territory}")
                
        # 3. BFS Traversal
        while queue:
            current_territory = queue.pop(0)
            print(f"DEBUG (Step 7): Current Territory: {current_territory}") # Modified line
            
            # Find children using dict
            children = territory_children_dict.get(current_territory, [])
            print(f"DEBUG (Step 7): Children Found: {len(children)}") # Added line
            for child in children:
                print(f"DEBUG (Step 7): Child Territory: {child.Territory}, Child Area_Name: {child.Area_Name}") # Modified line
                if child.Emp_Code and child.Emp_Code not in accessible_employees:
                    accessible_employees.add(child.Emp_Code)
                
                if child.Territory and child.Territory not in accessible_territories:
                    accessible_territories.add(child.Territory)
                    queue.append(child.Territory)
                    print(f"DEBUG (Step 3): Added to BFS queue (child territory): {child.Territory}")
                    
        print(f"DEBUG (Step 8): BFS Finished.")
        print(f"DEBUG (Step 8): Accessible Employees: {accessible_employees}")
        print(f"DEBUG (Step 8): Accessible Territories: {accessible_territories}")
        return accessible_employees, accessible_territories

    def _normalize_territory_name(self, territory_name: str, division_prefix: Optional[str] = None) -> str:
        if not territory_name:
            return ""
        
        normalized = territory_name.strip().upper()
        
        # Prefixes to be removed unless they match the division_prefix
        prefixes = ["MAX-", "NUC-", "ZEN-", "IMP-", "GLST-", "STI-", "GLA-"]
        
        for prefix in prefixes:
            if normalized.startswith(prefix):
                # If a division_prefix is provided and matches, keep it as is.
                # Example: division_prefix="MAX", territory="MAX-NIZAMABAD" -> "MAX-NIZAMABAD"
                # Example: division_prefix="NUC", territory="MAX-NIZAMABAD" -> "NIZAMABAD" (prefix removed)
                if division_prefix and normalized.startswith(division_prefix.upper()):
                    return normalized
                
                # Remove the prefix if it's not the desired division_prefix or no division_prefix is given
                normalized = normalized[len(prefix):]
                break # Assume only one prefix needs to be removed
        
        return normalized.strip()

    def get_direct_reports(self, emp_code: str) -> List[User]:
        return self.db.query(User).filter(
            func.upper(func.trim(User.Reporting_Manager_Code)) == emp_code.strip().upper()
        ).all()

    def get_child_employees(self, parent_territory: str) -> List[User]:
        if not parent_territory:
            return []
        return self.db.query(User).filter(User.Area_Name == parent_territory).all()

    def get_all_accessible_employees(self, emp_code: str) -> List[str]:
        employees, _ = self.get_all_accessible_data(emp_code)
        return sorted(list(employees))

    def get_all_accessible_territories(self, emp_code: str) -> List[str]:
        _, territories = self.get_all_accessible_data(emp_code)
        return sorted(list(territories))

    def get_accessible_regions(self, emp_code: str) -> List[str]:
        # Get the current user's division to apply correct normalization
        current_user = self.db.query(User).filter(
            func.upper(func.trim(User.Emp_Code)) == emp_code.strip().upper()
        ).first()
        user_division = current_user.Division if current_user else None
        
        accessible_territories_raw = self.get_all_accessible_territories(emp_code)
        if not accessible_territories_raw:
            return []

        # Normalize accessible territories for database query
        accessible_territories_upper = {
                t.strip().upper()
                for t in accessible_territories_raw
                if t
            }
        
        print(f"DEBUG (Step 9): Accessible territories from hierarchy (raw): {accessible_territories_raw}")
        print(f"DEBUG (Step 9): Accessible territories from hierarchy (normalized): {accessible_territories_upper}")

        # Construct OR clauses for filtering doctor regions
        doctor_territory_filters = [
            func.upper(func.trim(Doctor.territory)).in_(accessible_territories_upper),
            func.upper(func.trim(Doctor.bm_territory)).in_(accessible_territories_upper),
            func.upper(func.trim(Doctor.bl_territory)).in_(accessible_territories_upper),
            func.upper(func.trim(Doctor.bh_territory)).in_(accessible_territories_upper),
            func.upper(func.trim(Doctor.sbuh_territory)).in_(accessible_territories_upper)
        ]

        # Get regions from Doctor table, applying normalization and filtering
        doctor_regions_query = self.db.query(Doctor.region).filter(
            or_(*doctor_territory_filters)
        ).distinct()
        doctor_regions = doctor_regions_query.all()
        
        print(f"DEBUG (Step 7): Doctor Regions (raw query result): {doctor_regions}")
        
        # Get regions from User table (assuming User.Territory is already in the hierarchy format)
        user_regions = self.db.query(User.Region).filter(
            User.Territory.in_(accessible_territories_raw) # User.Territory should match hierarchy output
        ).distinct().all()
        print(f"DEBUG (Step 7): User Regions (raw query result): {user_regions}")
        
        all_regions = set()
        for r in doctor_regions:
            if r[0]:
                all_regions.add(r[0])
        for r in user_regions:
            if r[0]:
                all_regions.add(r[0])
        
        print(f"DEBUG ACCESS: Regions found: {sorted(list(all_regions))}")
        print(f"DEBUG (Step 7): Final Regions (set): {sorted(list(all_regions))}")
        return sorted(list(all_regions))


    def get_accessible_patches(self, emp_code: str) -> List[str]:
        # Get the current user's division to apply correct normalization
        current_user = self.db.query(User).filter(
            func.upper(func.trim(User.Emp_Code)) == emp_code.strip().upper()
        ).first()
        user_division = current_user.Division if current_user else None
        
        accessible_territories_raw = self.get_all_accessible_territories(emp_code)
        if not accessible_territories_raw:
            return []

        # Normalize accessible territories for database query
        accessible_territories_upper = {
            self._normalize_territory_name(t, user_division) for t in accessible_territories_raw
        }
        
        print(f"DEBUG (Step 9): Territories used for Doctor.territory.in_ (raw, patches): {accessible_territories_raw}")
        print(f"DEBUG (Step 9): Territories used for Doctor.territory.in_ (normalized, patches): {accessible_territories_upper}")
            
        # Construct OR clauses for filtering doctor patches
        doctor_territory_filters = [
            func.upper(func.trim(Doctor.territory)).in_(accessible_territories_upper),
            func.upper(func.trim(Doctor.bm_territory)).in_(accessible_territories_upper),
            func.upper(func.trim(Doctor.bl_territory)).in_(accessible_territories_upper),
            func.upper(func.trim(Doctor.bh_territory)).in_(accessible_territories_upper),
            func.upper(func.trim(Doctor.sbuh_territory)).in_(accessible_territories_upper)
        ]
        
        patches = self.db.query(Doctor.patch).filter(
            or_(*doctor_territory_filters)
        ).distinct().all()

        print(f"DEBUG (Patches): Raw patches query result: {patches}")
        print(f"DEBUG ACCESS: Patches found: {sorted([p[0] for p in patches if p[0]])}")
        
        return sorted([p[0] for p in patches if p[0]])

    def get_accessible_territories_for_dropdown(
        self,
        emp_code: str
    ) -> List[dict]:
        """
        Return all territories accessible through the User hierarchy,
        along with their regions.

        IMPORTANT:
        Territory access comes from the User hierarchy, NOT the Doctor table.
        """

        print("=" * 80)
        print("DEBUG TERRITORY DROPDOWN START")
        print(f"Employee: {emp_code}")

        # ---------------------------------------------------------
        # 1. Get accessible territories from hierarchy
        # ---------------------------------------------------------
        accessible_territories_raw = self.get_all_accessible_territories(emp_code)

        print(
            f"DEBUG: Accessible territories from hierarchy: "
            f"{accessible_territories_raw}"
        )

        if not accessible_territories_raw:
            print("DEBUG: No accessible territories")
            print("DEBUG TERRITORY DROPDOWN END")
            return []

        accessible_territories = {
            t.strip().upper()
            for t in accessible_territories_raw
            if t and t.strip()
        }

        # ---------------------------------------------------------
        # 2. Get Region + Territory directly from User table
        # ---------------------------------------------------------
        user_rows = self.db.query(
            User.Region,
            User.Territory
        ).filter(
            User.Territory.isnot(None)
        ).all()

        print(
            f"DEBUG: User territory rows found: "
            f"{len(user_rows)}"
        )

        territory_region_map = {}

        # ---------------------------------------------------------
        # 3. Build territory -> region mapping
        # ---------------------------------------------------------
        for region, territory in user_rows:

            if not territory:
                continue

            territory_clean = territory.strip()
            territory_upper = territory_clean.upper()

            if territory_upper not in accessible_territories:
                continue

            region_clean = region.strip() if region else None

            if not region_clean:
                continue

            if territory_upper not in territory_region_map:
                territory_region_map[territory_upper] = set()

            territory_region_map[territory_upper].add(region_clean)

        # ---------------------------------------------------------
        # 4. Build final response
        # ---------------------------------------------------------
        final_territories = []

        for territory in sorted(accessible_territories):

            regions = territory_region_map.get(
                territory,
                set()
            )

            for region in sorted(regions):

                final_territories.append({
                    "name": territory,
                    "region": region
                })

        # ---------------------------------------------------------
        # 5. DEBUG
        # ---------------------------------------------------------
        print(
            f"DEBUG: Territory -> Region mapping: "
            f"{territory_region_map}"
        )

        print(
            f"DEBUG: Final territories: "
            f"{final_territories}"
        )

        print(
            f"DEBUG: Final territory count: "
            f"{len(final_territories)}"
        )

        print("DEBUG TERRITORY DROPDOWN END")
        print("=" * 80)

        return final_territories

        def get_accessible_patches_for_dropdown(self, emp_code: str, selected_territory: Optional[str] = None) -> List[dict]:
            # Get the current user's division to apply correct normalization
            current_user = self.db.query(User).filter(
                func.upper(func.trim(User.Emp_Code)) == emp_code.strip().upper()
            ).first()
            user_division = current_user.Division if current_user else None

            accessible_territories_raw = self.get_all_accessible_territories(emp_code)
            if not accessible_territories_raw:
                print(f"DEBUG (Patches for Dropdown): No accessible territories for {emp_code}")
                return []
            
            # Normalize accessible territories for database query
            accessible_territories_upper = {
                t.strip().upper()
                for t in accessible_territories_raw
                if t
            }

            print(f"DEBUG (Patches for Dropdown): Accessible territories from hierarchy (raw): {accessible_territories_raw}")
            print(f"DEBUG (Patches for Dropdown): Accessible territories from hierarchy (normalized): {accessible_territories_upper}")
            print(f"DEBUG (Patches for Dropdown): Selected territory: {selected_territory}")

            # Construct OR clauses for filtering doctor patches
            doctor_territory_filters = [
                func.upper(func.trim(Doctor.territory)).in_(accessible_territories_upper),
                func.upper(func.trim(Doctor.bm_territory)).in_(accessible_territories_upper),
                func.upper(func.trim(Doctor.bl_territory)).in_(accessible_territories_upper),
                func.upper(func.trim(Doctor.bh_territory)).in_(accessible_territories_upper),
                func.upper(func.trim(Doctor.sbuh_territory)).in_(accessible_territories_upper)
            ]

            query = self.db.query(Doctor.patch).filter(
                or_(*doctor_territory_filters)
            )

            if selected_territory:
                selected_territory_upper = selected_territory.strip().upper()

                query = query.filter(
                    or_(
                        func.upper(func.trim(Doctor.territory)) == selected_territory_upper,
                        func.upper(func.trim(Doctor.bm_territory)) == selected_territory_upper,
                        func.upper(func.trim(Doctor.bl_territory)) == selected_territory_upper,
                        func.upper(func.trim(Doctor.bh_territory)) == selected_territory_upper,
                        func.upper(func.trim(Doctor.sbuh_territory)) == selected_territory_upper
                    )
                )

            patches_raw = query.distinct().all()
            
            final_patches = sorted([p[0] for p in patches_raw if p[0] and p[0].strip()])
            
            print(f"DEBUG ACCESS: Patches found: {final_patches}")
            print(f"DEBUG (Patches for Dropdown): Raw patches query result: {patches_raw}")
            print(f"DEBUG (Patches for Dropdown): Final formatted patches: {final_patches}")
            return [{"name": p} for p in final_patches]


    def get_accessible_doctors(self, emp_code: str) -> List[Doctor]:
        # Get the current user's division to apply correct normalization
        current_user = self.db.query(User).filter(
            func.upper(func.trim(User.Emp_Code)) == emp_code.strip().upper()
        ).first()
        user_division = current_user.Division if current_user else None

        accessible_territories_raw = self.get_all_accessible_territories(emp_code)
        if not accessible_territories_raw:
            return []
        
        # Normalize accessible territories for database query
        accessible_territories_upper = {
            t.strip().upper()
            for t in accessible_territories_raw
            if t
        }
        
        print(f"DEBUG (Step 6): Accessible territories from hierarchy (raw, doctors): {accessible_territories_raw}")
        print(f"DEBUG (Step 6): Accessible territories from hierarchy (normalized, doctors): {accessible_territories_upper}")
            
        # Construct OR clauses for filtering doctors
        doctor_territory_filters = [
            func.upper(func.trim(Doctor.territory)).in_(accessible_territories_upper),
            func.upper(func.trim(Doctor.bm_territory)).in_(accessible_territories_upper),
            func.upper(func.trim(Doctor.bl_territory)).in_(accessible_territories_upper),
            func.upper(func.trim(Doctor.bh_territory)).in_(accessible_territories_upper),
            func.upper(func.trim(Doctor.sbuh_territory)).in_(accessible_territories_upper)
        ]

        doctors = self.db.query(Doctor).filter(
            or_(*doctor_territory_filters)
        ).all()
        
        # Add new debug log as per task requirement
        doctor_table_matching_territories = set()
        for d in doctors:
            if d.territory:
                doctor_table_matching_territories.add(d.territory)
            if d.bm_territory:
                doctor_table_matching_territories.add(d.bm_territory)
            if d.bl_territory:
                doctor_table_matching_territories.add(d.bl_territory)
            if d.bh_territory:
                doctor_table_matching_territories.add(d.bh_territory)
            if d.sbuh_territory:
                doctor_table_matching_territories.add(d.sbuh_territory)

        print(f"DEBUG ACCESS: Doctor table matching territories: {sorted(list(doctor_table_matching_territories))}")
        print(f"DEBUG ACCESS: Doctors found: {len(doctors)}")
        
        return doctors
