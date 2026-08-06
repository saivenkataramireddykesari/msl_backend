from typing import List, Dict, Set
from sqlalchemy.orm import Session
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import os

from models import HierarchyMetricsAgg

class HierarchyService:
    """
    Service to manage territory hierarchy filtering.
    """
    def __init__(self, db: Session):
        self.db = db
        # Cache for hierarchy data to avoid repeated database queries
        self._parent_to_children: Dict[str, Set[str]] = None
        self._all_territories: Set[str] = None

    def _load_hierarchy_data(self):
        """
        Loads all hierarchy data from the database into memory.
        This method is designed to be called only once.
        """
        if self._parent_to_children is None:
            print("Loading hierarchy data from database...")
            hierarchy_records = self.db.query(HierarchyMetricsAgg).all()
            
            self._parent_to_children = {}
            self._all_territories = set()

            for record in hierarchy_records:
                parent = record.Area_Name
                child = record.Territory
                emp_code = record.Emp_Code

                # Ignore rows where Emp_Code = 'Vacant'
                if emp_code and emp_code.upper() == 'VACANT':
                    continue
                
                if parent and child:
                    if parent not in self._parent_to_children:
                        self._parent_to_children[parent] = set()
                    self._parent_to_children[parent].add(child)
                    self._all_territories.add(parent)
                    self._all_territories.add(child)
                elif parent: # Case where a territory is a parent but not a child of anything else directly listed
                    self._all_territories.add(parent)
                elif child: # Case where a territory is a child but its parent is not directly listed as an Area_Name
                    self._all_territories.add(child)

            print(f"Hierarchy data loaded. Total unique territories: {len(self._all_territories)}")

    def get_all_child_territories(self, territory: str) -> List[str]:
        """
        Recursively collects all descendant territories for a given territory,
        including the input territory itself.
        
        Args:
            territory: The starting territory to find descendants for.
            
        Returns:
            A unique list of all child territories, including the input territory.
        """
        self._load_hierarchy_data() # Ensure data is loaded
        
        if territory not in self._all_territories:
            # If the territory is not in our hierarchy data, return just itself.
            # This handles cases where a territory might be a leaf node or an isolated entry.
            return [territory]

        all_descendants = set()
        visited = set()

        def _collect_descendants(current_territory: str):
            if current_territory in visited:
                return
            
            visited.add(current_territory)
            all_descendants.add(current_territory)

            # Check if current_territory is a parent
            if current_territory in self._parent_to_children:
                for child in self._parent_to_children[current_territory]:
                    _collect_descendants(child)

        _collect_descendants(territory)
        
        return sorted(list(all_descendants))
