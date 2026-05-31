from pymongo import MongoClient, ASCENDING, DESCENDING
from pymongo.errors import ConnectionFailure, OperationFailure
from typing import Optional, Dict, List, Tuple
import os


class MaterialDatabase:
    def __init__(self, host: str = None, port: int = None, db_name: str = None):
        self.host = host or os.getenv('MONGO_HOST', 'localhost')
        self.port = port or int(os.getenv('MONGO_PORT', '27017'))
        self.db_name = db_name or os.getenv('MONGO_DB', 'phononic_materials')
        self.client = None
        self.db = None
        self.collection = None

    def connect(self) -> bool:
        try:
            self.client = MongoClient(self.host, self.port, serverSelectionTimeoutMS=5000)
            self.client.admin.command('ping')
            self.db = self.client[self.db_name]
            self.collection = self.db['materials']
            self._create_indexes()
            return True
        except ConnectionFailure:
            return False

    def _create_indexes(self):
        if self.collection is None:
            return

        try:
            existing_indexes = self.collection.index_information()

            if 'name_1_density_1' not in existing_indexes:
                self.collection.create_index(
                    [('name', ASCENDING), ('density', ASCENDING)],
                    unique=True,
                    name='name_1_density_1',
                    background=True
                )

            if 'density_1_sound_velocity_longitudinal_1' not in existing_indexes:
                self.collection.create_index(
                    [('density', ASCENDING), ('sound_velocity_longitudinal', ASCENDING)],
                    name='density_1_sound_velocity_longitudinal_1',
                    background=True
                )

            if 'sound_velocity_shear_1' not in existing_indexes:
                self.collection.create_index(
                    [('sound_velocity_shear', ASCENDING)],
                    name='sound_velocity_shear_1',
                    background=True,
                    sparse=True
                )

        except OperationFailure as e:
            if 'already exists' not in str(e):
                print(f"Warning: Could not create indexes: {e}")

    def disconnect(self):
        if self.client:
            self.client.close()

    def add_material(self, name: str, density: float, sound_velocity_longitudinal: float,
                     sound_velocity_shear: float = 0.0, description: str = "") -> Optional[str]:
        material = {
            "name": name,
            "density": density,
            "sound_velocity_longitudinal": sound_velocity_longitudinal,
            "sound_velocity_shear": sound_velocity_shear,
            "description": description
        }
        existing = self.collection.find_one({"name": name})
        if existing:
            self.collection.update_one({"name": name}, {"$set": material})
            return str(existing['_id'])
        result = self.collection.insert_one(material)
        return str(result.inserted_id)

    def get_material(self, name: str) -> Optional[Dict]:
        material = self.collection.find_one(
            {"name": name},
            hint=[("name", ASCENDING), ("density", ASCENDING)]
        )
        if material:
            material['_id'] = str(material['_id'])
        return material

    def get_all_materials(self) -> List[Dict]:
        materials = list(self.collection.find().sort("name", ASCENDING))
        for mat in materials:
            mat['_id'] = str(mat['_id'])
        return materials

    def find_materials_by_properties(self, density_range: Optional[Tuple[float, float]] = None,
                                       velocity_range: Optional[Tuple[float, float]] = None,
                                       limit: int = 100) -> List[Dict]:
        query = {}
        if density_range:
            query["density"] = {"$gte": density_range[0], "$lte": density_range[1]}
        if velocity_range:
            query["sound_velocity_longitudinal"] = {"$gte": velocity_range[0], "$lte": velocity_range[1]}

        materials = list(
            self.collection.find(query)
            .hint([("density", ASCENDING), ("sound_velocity_longitudinal", ASCENDING)])
            .sort([("density", ASCENDING), ("sound_velocity_longitudinal", ASCENDING)])
            .limit(limit)
        )
        for mat in materials:
            mat['_id'] = str(mat['_id'])
        return materials

    def delete_material(self, name: str) -> bool:
        result = self.collection.delete_one({"name": name})
        return result.deleted_count > 0

    def initialize_default_materials(self):
        default_materials = [
            {"name": "Air", "density": 1.21, "sound_velocity_longitudinal": 343.0,
             "sound_velocity_shear": 0.0, "description": "Air at room temperature"},
            {"name": "Water", "density": 1000.0, "sound_velocity_longitudinal": 1480.0,
             "sound_velocity_shear": 0.0, "description": "Water at 20°C"},
            {"name": "Steel", "density": 7850.0, "sound_velocity_longitudinal": 5960.0,
             "sound_velocity_shear": 3235.0, "description": "Structural steel"},
            {"name": "Aluminum", "density": 2700.0, "sound_velocity_longitudinal": 6420.0,
             "sound_velocity_shear": 3040.0, "description": "Pure aluminum"},
            {"name": "Silicon", "density": 2330.0, "sound_velocity_longitudinal": 9330.0,
             "sound_velocity_shear": 5840.0, "description": "Single crystal silicon"},
            {"name": "Epoxy", "density": 1140.0, "sound_velocity_longitudinal": 2530.0,
             "sound_velocity_shear": 1160.0, "description": "Epoxy resin"},
            {"name": "Rubber", "density": 1100.0, "sound_velocity_longitudinal": 1000.0,
             "sound_velocity_shear": 30.0, "description": "Soft rubber"},
            {"name": "Glass", "density": 2500.0, "sound_velocity_longitudinal": 5640.0,
             "sound_velocity_shear": 3280.0, "description": "Fused silica glass"},
            {"name": "Copper", "density": 8960.0, "sound_velocity_longitudinal": 4760.0,
             "sound_velocity_shear": 2325.0, "description": "Pure copper"},
            {"name": "PMMA", "density": 1180.0, "sound_velocity_longitudinal": 2770.0,
             "sound_velocity_shear": 1430.0, "description": "Polymethyl methacrylate (acrylic)"}
        ]
        for mat in default_materials:
            self.add_material(**mat)
