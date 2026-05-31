from setuptools import setup, find_packages

setup(
    name='sea_ice_drift',
    version='2.0.0',
    description='Sea Ice Drift Estimation with Deep Learning and Kinematic Analysis',
    author='Sea Ice Drift Team',
    packages=find_packages(),
    install_requires=[
        'numpy>=1.21.0',
        'scipy>=1.7.0',
        'opencv-python>=4.5.0',
        'scikit-image>=0.18.0',
        'h5py>=3.6.0',
        'netCDF4>=1.5.8',
        'pyproj>=3.3.0',
        'matplotlib>=3.5.0',
        'cartopy>=0.20.0',
        'xarray>=0.20.0',
        'pandas>=1.3.0',
        'scikit-learn>=1.0.0',
    ],
    extras_require={
        'deeplearning': [
            'torch>=1.10.0',
            'torchvision>=0.11.0',
        ],
    },
    entry_points={
        'console_scripts': [
            'sea-ice-drift=sea_ice_drift.main:main',
        ],
    },
    python_requires='>=3.8',
)
