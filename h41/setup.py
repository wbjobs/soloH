from setuptools import setup, find_packages

setup(
    name="mdcompress",
    version="0.1.0",
    description="Molecular Dynamics trajectory compression using Graph Neural Networks",
    author="MDCompress Team",
    packages=find_packages(),
    install_requires=[
        "torch>=2.0.0",
        "torch-geometric>=2.3.0",
        "mdanalysis>=2.4.0",
        "numpy>=1.24.0",
        "scipy>=1.10.0",
        "tqdm>=4.65.0",
        "pyyaml>=6.0",
    ],
    entry_points={
        "console_scripts": [
            "mdcompress=mdcompress.cli:main",
        ],
    },
    python_requires=">=3.9",
)
