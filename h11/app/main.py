from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from app.routers import materials_router, band_structure_router, transmission_router
from app.routers.advanced import router as advanced_router
from app.db import MaterialDatabase


@asynccontextmanager
async def lifespan(app: FastAPI):
    db = MaterialDatabase()
    if db.connect():
        db.initialize_default_materials()
        print("Connected to MongoDB and initialized default materials")
    else:
        print("Warning: Could not connect to MongoDB. Using fallback mode.")
    app.state.db = db
    yield
    db.disconnect()
    print("Disconnected from MongoDB")


app = FastAPI(
    title="Phononic Crystal Band Structure Calculator",
    description="""
    FastAPI service for computing phononic crystal band structures using the finite element method.
    Features:
    - 2D unit cell geometry with circular/square scatterers
    - SH and PSV elastic wave modes
    - Brillouin zone path generation for square, rectangular, hexagonal lattices
    - Generalized eigenvalue problem solver (scipy.sparse.linalg)
    - Phonon density of states (DOS) and group velocity calculation
    - Transfer matrix method for 1D transmission coefficients
    - MongoDB material database
    - Topological band analysis (Zak phase, Wilson loop, Chern numbers
    - Lossy material support with complex sound velocity
    - Multiscale homogenization (effective density, effective modulus)
    """,
    version="2.0.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(materials_router, prefix="/api/v1")
app.include_router(band_structure_router, prefix="/api/v1")
app.include_router(transmission_router, prefix="/api/v1")
app.include_router(advanced_router)


@app.get("/")
async def root():
    return {
        "name": "Phononic Crystal Band Structure Calculator",
        "version": "2.0.0",
        "endpoints": {
            "materials": "/api/v1/materials",
            "band_structure": "/api/v1/band-structure",
            "transmission": "/api/v1/transmission",
            "topological_analysis": "/api/v1/advanced/topological-analysis",
            "homogenization": "/api/v1/advanced/homogenization",
            "complex_band_structure": "/api/v1/advanced/complex-band-structure",
            "docs": "/docs",
            "openapi": "/openapi.json"
        }
    }


@app.get("/health")
async def health_check():
    return {"status": "healthy"}
