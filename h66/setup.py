from setuptools import setup, find_packages

setup(
    name="heat_inv",
    version="0.1.0",
    description="Thermal conductivity inverse problem solver using FEniCS",
    author="Thermal Inversion Team",
    packages=find_packages(),
    install_requires=[
        "numpy>=1.21.0",
        "scipy>=1.7.0",
        "fenics>=2019.1.0",
        "meshio>=5.0.0",
        "pyvista>=0.32.0",
        "trimesh>=3.9.0",
        "click>=8.0.0",
        "PyYAML>=5.4.0",
        "tqdm>=4.62.0",
        "h5py>=3.2.0",
    ],
    entry_points={
        "console_scripts": [
            "heat-inv=heat_inv.cli:main",
        ],
    },
    python_requires=">=3.8",
)
