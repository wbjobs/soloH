import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.database import init_db, engine
from app.models.db import Base, ModelInfo
from sqlalchemy.orm import Session
from app.models.resnet import get_available_models


def initialize_database():
    print("Creating database tables...")
    Base.metadata.create_all(bind=engine)
    print("Database tables created successfully.")

    db = Session(bind=engine)
    try:
        print("\nInitializing model information...")
        available_models = get_available_models()

        for model_name, model_info in available_models.items():
            existing = db.query(ModelInfo).filter(ModelInfo.name == model_name).first()

            if existing:
                print(f"  Model {model_name} already exists, updating...")
                existing.description = model_info["description"]
                existing.in_channels = model_info["in_channels"]
                existing.threshold_angstrom = model_info["threshold"]
                existing.trained_on = "PDB dataset" if "pdb" in model_name.lower() else f"CASP{model_name.split('_')[-1].upper()} dataset"
                existing.training_samples = 150000 if "casp" in model_name.lower() else 100000
            else:
                print(f"  Adding model {model_name}...")
                db_model = ModelInfo(
                    name=model_name,
                    description=model_info["description"],
                    version="1.0.0",
                    in_channels=model_info["in_channels"],
                    threshold_angstrom=model_info["threshold"],
                    is_available=True,
                    is_default=(model_name == "resnet50_pdb"),
                    trained_on="PDB dataset" if "pdb" in model_name.lower() else f"CASP{model_name.split('_')[-1].upper()} dataset",
                    training_samples=150000 if "casp" in model_name.lower() else 100000
                )
                db.add(db_model)

        db.commit()
        print("\nModel information initialized successfully.")

        default_model = db.query(ModelInfo).filter(ModelInfo.is_default == True).first()
        if default_model:
            print(f"\nDefault model: {default_model.name}")

    except Exception as e:
        print(f"Error initializing model information: {e}")
        db.rollback()
        raise
    finally:
        db.close()

    print("\nDatabase initialization completed.")


if __name__ == "__main__":
    initialize_database()
