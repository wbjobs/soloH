from setuptools import setup, find_packages
from pathlib import Path

with open("requirements.txt") as f:
    requirements = f.read().splitlines()

setup(
    name="eddytester",
    version="1.0.0",
    description="Eddy Current Testing Signal Analysis Tool",
    author="Eddy Current Tester Team",
    package_dir={"": "src"},
    packages=find_packages(where="src"),
    python_requires=">=3.8",
    install_requires=requirements,
    entry_points={
        "console_scripts": [
            "eddytester=eddytester.cli:cli",
        ],
    },
    classifiers=[
        "Programming Language :: Python :: 3",
        "Operating System :: OS Independent",
        "Intended Audience :: Science/Research",
        "Topic :: Scientific/Engineering :: Physics",
    ],
)
