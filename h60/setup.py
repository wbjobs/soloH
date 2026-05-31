from setuptools import setup, find_packages

setup(
    name="lightfield_depth",
    version="1.0.0",
    description="Light Field Camera Depth Estimation Toolkit",
    author="LightField Depth Team",
    packages=find_packages(),
    install_requires=[
        "numpy>=1.21.0",
        "opencv-python>=4.5.0",
        "scipy>=1.7.0",
        "matplotlib>=3.4.0",
        "pillow>=9.0.0",
        "pyyaml>=6.0",
        "tqdm>=4.62.0",
    ],
    entry_points={
        "console_scripts": [
            "lf-depth=lightfield_depth.cli:main",
        ],
    },
    python_requires=">=3.8",
)
