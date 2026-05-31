from setuptools import setup, find_packages

with open('README.md', 'r', encoding='utf-8') as f:
    long_description = f.read()

setup(
    name='sariw',
    version='1.0.0',
    description='SAR Image Internal Wave Detection and Analysis Tool',
    long_description=long_description,
    long_description_content_type='text/markdown',
    author='SAR Internal Wave Team',
    packages=find_packages(),
    install_requires=[
        'numpy>=1.21.0',
        'opencv-python>=4.5.0',
        'scikit-image>=0.18.0',
        'rasterio>=1.2.0',
        'pyproj>=3.0.0',
        'scipy>=1.7.0',
        'matplotlib>=3.4.0',
        'simplekml>=1.3.6',
        'click>=8.0.0',
        'tqdm>=4.62.0',
    ],
    entry_points={
        'console_scripts': [
            'sariw=sariw.cli:main',
        ],
    },
    classifiers=[
        'Programming Language :: Python :: 3.8',
        'Programming Language :: Python :: 3.9',
        'Programming Language :: Python :: 3.10',
        'License :: OSI Approved :: MIT License',
        'Operating System :: OS Independent',
        'Topic :: Scientific/Engineering :: Image Processing',
        'Topic :: Scientific/Engineering :: GIS',
    ],
    python_requires='>=3.8',
)
